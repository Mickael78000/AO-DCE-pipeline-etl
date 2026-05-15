"""Construction du prompt de consolidation LLM par ligne CSV + HTML source.

Stratégie :
- Pré-extraire du HTML les blocs pertinents (procédure, CPV, nature, CCAG…).
- Construire un objet resolved_hints structuré avec signaux déjà classés par source.
- Passer au LLM un contexte compact et hiérarchisé, pas un HTML brut de 200 Ko.
- Le système de priorité est documenté dans le prompt : CSV > notes > HTML > inférence.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

_HTML_FOCUS_MAX_CHARS = 6000
_HTML_PATTERN_MAX_RESULTS = 3


# =============================================================================
# Extraction HTML ciblée
# =============================================================================

def _strip_tags(text: str) -> str:
    """Supprime les balises HTML et normalise les espaces."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&nbsp;|&#0?39;|&#160;', ' ', text)
    text = re.sub(r'&[a-z]{2,6};', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def _decode_unicode_escapes(text: str) -> str:
    """Décode les séquences \\uXXXX présentes dans les attributs JSON inline."""
    def _replace(m: re.Match) -> str:
        try:
            return chr(int(m.group(1), 16))
        except (ValueError, OverflowError):
            return m.group(0)
    return re.sub(r'\\u([0-9A-Fa-f]{4})', _replace, text)


def _extract_html_block(html: str, patterns: List[str], context_chars: int = 300) -> str:
    """Extrait les N premiers passages HTML qui correspondent aux patterns donnés."""
    results = []
    for pat in patterns:
        for m in re.finditer(pat, html, re.IGNORECASE):
            start = max(0, m.start() - 60)
            end = min(len(html), m.end() + context_chars)
            fragment = _strip_tags(html[start:end])
            fragment = _decode_unicode_escapes(fragment)
            if len(fragment) > 20:
                results.append(fragment)
            if len(results) >= _HTML_PATTERN_MAX_RESULTS:
                break
        if len(results) >= _HTML_PATTERN_MAX_RESULTS:
            break
    return " | ".join(dict.fromkeys(results))  # déduplique en préservant l'ordre


def extract_html_signals(html: Optional[str]) -> Dict[str, str]:
    """Extrait les signaux métier clés du HTML source.

    Retourne un dict avec les clés : procedure, nature, cpv, ccag,
    location, deadline, duration, amount, title_html.
    Chaque valeur est une chaîne de texte déjà nettoyée et courte.
    """
    if not html:
        return {}

    signals: Dict[str, str] = {}

    # Titre depuis balise <title> ou méta description
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if m:
        signals["title_html"] = _strip_tags(m.group(1))[:200]

    # Procédure
    proc = _extract_html_block(html, [
        r'proc[eé]dure\s*(?:adapt[eé]e|formalis[eé]e|n[eé]goci[eé]e)',
        r'appel\s+d.offres?\s+(?:ouvert|restreint)',
        r'accord[\s-]cadre',
        r'dialogue\s+comp[eé]titif',
        r'proc[eé]dure\s*<',
        r'type_procedure',
        r'BT-105-Procedure',
    ], context_chars=200)
    if proc:
        signals["procedure"] = proc[:500]

    # Nature du marché
    nature = _extract_html_block(html, [
        r'nature\s+(?:du|principale\s+du)\s+march[eé]',
        r'BT-23[^"]{0,30}',
        r'nature\s*:\s*(?:services?|fournitures?|travaux)',
    ], context_chars=150)
    if nature:
        signals["nature"] = nature[:300]

    # CPV — capture les codes numériques CPV (8 chiffres)
    cpv_codes = re.findall(r'\b([0-9]{8}(?:-[0-9])?)\b', html)
    if cpv_codes:
        # déduplique tout en préservant l'ordre
        seen: dict = {}
        for c in cpv_codes:
            seen[c] = None
        signals["cpv_codes"] = ",".join(list(seen.keys())[:10])

    # Libellés CPV (texte autour des codes)
    cpv_labels = _extract_html_block(html, [
        r'cpv[^>]{0,50}>',
        r'nomenclature\s+(?:principale|suppl[eé]mentaire)',
        r'code\s+CPV',
        r'data-labels-key="code\|name\|cpv',
    ], context_chars=200)
    if cpv_labels:
        signals["cpv_labels"] = cpv_labels[:400]

    # CCAG
    ccag = _extract_html_block(html, [
        r'CCAG[\s\-](?:TIC|PI|FCS|travaux|MOE)',
        r'cahier\s+des\s+clauses\s+administratives',
        r'prestations?\s+intellectuelles',
        r'fournitures\s+courantes',
    ], context_chars=200)
    if ccag:
        signals["ccag"] = ccag[:300]

    # Localisation / lieu d'exécution
    loc = _extract_html_block(html, [
        r'lieu\s+(?:d.ex[eé]cution|de\s+livraison|principal)',
        r'BT-?727',
        r'NUTS\s*:?\s*[A-Z]{2}[0-9A-Z]{0,4}',
        r'code\s+postal\s*:?\s*[0-9]{5}',
    ], context_chars=150)
    if loc:
        signals["location"] = loc[:300]

    # Date limite
    deadline = _extract_html_block(html, [
        r'date\s+limite\s+(?:de\s+)?(?:r[eé]ception|remise|d[eé]p[oô]t)',
        r'date\s+et\s+heure\s+limite',
        r'\b(0?[1-9]|[12][0-9]|3[01])[\/\-\.](0?[1-9]|1[012])[\/\-\.](20[0-9]{2})',
        r'BT-131',
    ], context_chars=150)
    if deadline:
        signals["deadline"] = deadline[:200]

    # Durée du marché
    duration = _extract_html_block(html, [
        r'dur[eé]e\s+(?:du|de\s+l[a\']?)\s+(?:march[eé]|contrat|accord)',
        r'dur[eé]e\s+(?:initiale|pr[eé]visionnelle)',
        r'BT-36',
        r'\b([0-9]+)\s+(?:mois|ans?)\b',
    ], context_chars=150)
    if duration:
        signals["duration"] = duration[:200]

    # Montant estimé
    amount = _extract_html_block(html, [
        r'valeur\s+(?:estim[eé]e?|totale|du\s+march[eé])',
        r'montant\s+(?:estim[eé]|total|maximum)',
        r'BT-27[0-9]',
        r'[0-9\s]+[€]\s*(?:HT|TTC)',
        r'[0-9]+[\s][0-9]+\s*EUR',
    ], context_chars=150)
    if amount:
        signals["amount"] = amount[:200]

    return signals


# =============================================================================
# Construction du resolved_hints
# =============================================================================

def _v(row: dict, *keys: str) -> str:
    """Retourne la première valeur non-vide parmi les clés, ou ''."""
    for k in keys:
        val = row.get(k, "")
        if val and val.strip() not in ("", "-", "None", "none"):
            return val.strip()
    return ""


def build_resolved_hints(row: dict, html_signals: Dict[str, str], source_file: str) -> dict:
    """Construit un dict structuré des indices déjà résolus, classés par source.

    Ce dict est transmis au LLM comme contexte principal.
    Il élimine le bruit du HTML brut en faveur de signaux pré-classifiés.
    """
    ref = _v(row, "Référence")
    return {
        "reference": ref,
        "source_file": source_file,
        "source_platform": _v(row, "source_type", "Plateforme"),
        "source_url": _v(row, "URL source HTTPS"),

        # ── Signaux CSV déterministes (priorité 1) ──
        "csv_title": _v(row, "Intitulé synthétique"),
        "csv_buyer": _v(row, "Acheteur_auto", "Acheteur_clean", "Acheteur_manual"),
        "csv_location": _v(row, "Localisation_auto", "Localisation_clean",
                           "Localisation_manual", "Localisation"),
        "csv_deadline": _v(row, "Date_limite_auto", "Date_limite_manual",
                           "Date limite de remise des offres"),
        "csv_duration": _v(row, "Durée initiale du marché"),
        "csv_renewals": _v(row, "Reconduction(s)"),
        "csv_estimated_amount": _v(row, "Estimation_auto", "Estimation_manual",
                                    "Estimation du marché"),
        "csv_type_ao": _v(row, "Type d'AO"),
        "csv_type_contrat": _v(row, "Type"),
        "csv_fonction_publique": _v(row, "Fonction publique"),

        # ── Notes d’extraction (priorité 2) ──
        # Peuvent contenir des signaux structurés : buyer:, title:, CPV, location, deadline
        # selon la source (marches_online, boamp, joue, etc.)
        "extraction_notes": _v(row, "extraction_notes"),

        # ── Signaux extraits du HTML (priorité 3) ──
        "html_title": html_signals.get("title_html", ""),
        "html_procedure": html_signals.get("procedure", ""),
        "html_nature": html_signals.get("nature", ""),
        "html_cpv_codes": html_signals.get("cpv_codes", ""),
        "html_cpv_labels": html_signals.get("cpv_labels", ""),
        "html_ccag": html_signals.get("ccag", ""),
        "html_location": html_signals.get("location", ""),
        "html_deadline": html_signals.get("deadline", ""),
        "html_duration": html_signals.get("duration", ""),
        "html_amount": html_signals.get("amount", ""),
    }


# =============================================================================
# Prompts
# =============================================================================

_SYSTEM_PROMPT = """\
Tu es le moteur d'arbitrage et de normalisation métier du pipeline AO-DCE.
Tu reçois un objet JSON `resolved_hints` contenant des indices pré-classifiés sur un marché public.
Tu dois produire un objet JSON consolidé, strict, sans texte autour.

════════════════════════════════════════════
RÈGLES ABSOLUES
════════════════════════════════════════════
1. Ne jamais inventer une donnée absente de toutes les sources.
2. Ne jamais écraser un champ `csv_*` fiable avec une hypothèse plus faible.
3. status = "found"    → valeur explicite dans une source.
4. status = "inferred" → déduite par une règle métier traçable.
5. status = "missing"  → non déterminable avec les sources disponibles.
6. Ne jamais forcer status="found" si la donnée est une inférence.
7. Retourner UNIQUEMENT le JSON, sans markdown, sans texte avant ou après.

════════════════════════════════════════════
PRIORITÉ DES SOURCES (décroissante)
════════════════════════════════════════════
P1 — Champs csv_* : valeurs extraites de façon déterministe. À préserver sauf contradiction forte dans le HTML.
P2 — extraction_notes : signaux de l'extracteur Python. Fiables si présents.
P3 — Signaux html_* : extraits ciblés du HTML source.
P4 — Inférence contrôlée par règle fermée (voir taxonomies ci-dessous).

════════════════════════════════════════════
TAXONOMIES FERMÉES (valeurs autorisées uniquement)
════════════════════════════════════════════

buyer_type (obligatoire si csv_buyer est non-vide) :
  "etat" | "collectivite_territoriale" | "hopital" | "etablissement_public"
  | "groupement_achat" | "entreprise_publique" | "organisme_prive_mission_publique"
  | "autre" | "inconnu"

  Règles d'inférence :
  - Ministère, Direction générale, DINSIC, ANSSI, DGFIP, Préfecture → "etat"
  - Région, Département, Commune, Métropole, EPCI, Agglomération, Mairie, Ville, Conseil → "collectivite_territoriale"
  - CHU, CHR, CH, GHT, EHPAD, ARS → "hopital"
  - Université, Rectorat, CNRS, INRAE, INRIA, EPA, EPIC, Établissement public → "etablissement_public"
  - Centrale d'achat, Groupement, UGAP, RESAH, CAIH → "groupement_achat"
  - EDF, SNCF, RATP, La Poste, FranceAgriMer → "entreprise_publique"
  - Si aucune règle ne s'applique clairement → "inconnu"

fonction_publique :
  "etat" | "territoriale" | "hospitaliere" | "inconnue"
  Déduis-le depuis buyer_type :
  - etat, etablissement_public → "etat"
  - collectivite_territoriale → "territoriale"
  - hopital → "hospitaliere"
  - entreprise_publique, groupement_achat → "etat" si tutelle État, sinon "inconnue"
  - autre / inconnu → "inconnue"

procedure_family (valeurs fermées) :
  "mapa" | "procedure_negociee" | "appel_offres_ouvert" | "appel_offres_restreint"
  | "dialogue_competitif" | "accord_cadre" | "marche_subsequent" | "concours"
  | "sans_objet" | "inconnue"

  Règles : "procédure adaptée" / "MAPA" → "mapa"
           "appel d'offres ouvert" / "AOO" / "procédure ouverte" → "appel_offres_ouvert"
           "appel d'offres restreint" / "AOR" → "appel_offres_restreint"
           "procédure négociée" / "NEGOCIEE" → "procedure_negociee"
           "accord-cadre" / "accord cadre" seul → "accord_cadre"
           "marché subséquent" → "marche_subsequent"
           "dialogue compétitif" → "dialogue_competitif"
  Si "procédure formalisée" sans détail : inférer depuis montant/contexte si possible, sinon "appel_offres_ouvert" (inferred).

formalisation_type :
  "formalise" | "adapte" | "inconnu"
  Règles : mapa → "adapte" ; appel_offres_ouvert, appel_offres_restreint, procedure_negociee, dialogue_competitif → "formalise"
  Si "procédure formalisée" dans le HTML → "formalise" (found)
  Si "procédure adaptée" dans le HTML → "adapte" (found)

contract_nature :
  "services" | "fournitures" | "travaux" | "mixte" | "inconnu"
  Règles d'inférence depuis titre/HTML :
  - SI, infogérance, hébergement, cloud, cybersécurité, maintenance applicative, développement, AMOA, AMOE, conseil, formation → "services"
  - Serveurs, matériels, équipements, postes, stockage, licences → "fournitures"
  - Construction, rénovation, BTP, travaux → "travaux"
  - Mélange explicite → "mixte"

ccag_type :
  "moe" | "travaux" | "fournitures_courantes_services" | "tic" | "prestations_intellectuelles" | "inconnu"
  Règles :
  - SI, infogérance, hébergement, cloud, maintenance applicative → "tic" (inferred)
  - AMOA, AMOE, études, conseil, assistance à maîtrise d'ouvrage → "prestations_intellectuelles" (inferred)
  - Fournitures, matériels, licences → "fournitures_courantes_services" (inferred)
  - Travaux → "travaux" (inferred)
  - Si CCAG explicitement mentionné dans html_ccag → found avec la valeur trouvée

cpv_main / cpv_list :
  - Utilise html_cpv_codes en priorité. Le premier code pertinent est cpv_main.
  - Si html_cpv_labels fournit des libellés, ajoute-les dans la justification.
  - cpv_list = liste dédupliquée de tous les codes identifiés.
  - Ne met pas missing si html_cpv_codes est non-vide.

deadline_final :
  Format YYYY-MM-DD HH:MM:SS. Si heure absente : utiliser 00:00:00.
  Si csv_deadline est déjà au bon format, réutilise-le directement (found, high).

estimated_amount :
  Normalise en entier (EUR, HT) si possible. Ex: "150 000 EUR HT" → 150000.
  Si csv_estimated_amount est déjà présent, réutilise-le (found, high).

════════════════════════════════════════════
CALCUL DE manual_review_required
════════════════════════════════════════════
Mettre à true si :
- buyer_final est missing
- deadline_final est missing
- procedure_family est "inconnue"
- plusieurs signaux contradictoires sur un même champ

════════════════════════════════════════════
FORMAT DE SORTIE OBLIGATOIRE (JSON strict)
════════════════════════════════════════════
{
  "record_id": "string",
  "source_trace": {
    "source_file": "string",
    "source_platform": "string",
    "source_url": null,
    "input_reference": "string"
  },
  "final_fields": {
    "reference":            {"value": "string|null", "status": "found|inferred|missing", "confidence": "high|medium|low", "justification": "string"},
    "title":                {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "buyer_final":          {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "buyer_type":           {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "fonction_publique":    {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "fonction_publique_detail": {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "procedure_label":      {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "procedure_family":     {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "formalisation_type":   {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "contract_nature":      {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "ccag_type":            {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "cpv_main":             {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "cpv_list":             {"value": ["string"], "status": "...", "confidence": "...", "justification": "..."},
    "location_final":       {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "deadline_final":       {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "duration_initial":     {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "renewals":             {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."},
    "estimated_amount":     {"value": "string|null", "status": "...", "confidence": "...", "justification": "..."}
  },
  "control": {
    "manual_review_required": false,
    "review_reasons": [],
    "quality_flags": []
  }
}"""


def build_user_prompt(
    row: dict,
    html_content: Optional[str],
    source_file: str,
) -> str:
    """Construit le prompt utilisateur avec un objet resolved_hints structuré.

    Au lieu de passer le HTML brut, extrait les signaux utiles et les classe
    par source de priorité. Le LLM reçoit un contexte compact et hiérarchisé.
    """
    html_signals = extract_html_signals(html_content)
    hints = build_resolved_hints(row, html_signals, source_file)

    ref = hints["reference"] or source_file
    lines = [
        "=== MARCHÉ À CONSOLIDER ===",
        f"record_id: {ref}",
        "",
        "=== INDICES RÉSOLUS (resolved_hints) ===",
        json.dumps(hints, ensure_ascii=False, indent=2),
        "",
        "=== INSTRUCTION ===",
        "Applique les règles du système et retourne le JSON de consolidation.",
        "Ne produis aucun texte hors du JSON.",
        f"record_id = {ref}",
    ]
    return "\n".join(lines)


def get_system_prompt() -> str:
    return _SYSTEM_PROMPT
