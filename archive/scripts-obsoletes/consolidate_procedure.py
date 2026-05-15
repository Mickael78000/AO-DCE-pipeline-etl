#!/usr/bin/env python3
"""
Script de consolidation des procédures de marchés publics.

Implémente le contrat métier CONSOLIDATION-RULE-001 :
- Distinction procedure_source / procedure_consolidee
- Détection des incohérences entre source et contraintes juridiques
- Hiérarchie : seuil > régime > preuve JOUE > source explicite

Auteur: Pipeline AO-DCE
Version: 1.0 — 14 mai 2026
"""

import csv
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


# ============================================================================
# CONFIGURATION DES SEUILS 2026
# ============================================================================

SEUILS_MAPA = 40000  # Seuil MAPA uniforme pour tous les marchés

SEUILS_FORMALISES = {
    # (type_acheteur, type_marche, regime) -> seuil HT
    ("etat", "services", "marches_ordinaires"): 140000,
    ("etat", "fournitures", "marches_ordinaires"): 140000,
    ("etat", "travaux", "marches_ordinaires"): 5382000,
    
    ("collectivite_territoriale", "services", "marches_ordinaires"): 216000,
    ("collectivite_territoriale", "fournitures", "marches_ordinaires"): 216000,
    ("collectivite_territoriale", "travaux", "marches_ordinaires"): 5382000,
    
    ("etablissement_public", "services", "marches_ordinaires"): 216000,
    ("etablissement_public", "fournitures", "marches_ordinaires"): 216000,
    ("etablissement_public", "travaux", "marches_ordinaires"): 5382000,
    
    # Régime défense et sécurité
    ("etat", "services", "defense_securite"): 443000,
    ("etat", "fournitures", "defense_securite"): 443000,
    ("etat", "travaux", "defense_securite"): 443000,
    ("etablissement_public", "services", "defense_securite"): 443000,
    ("etablissement_public", "fournitures", "defense_securite"): 443000,
}


# ============================================================================
# STRUCTURES DE DONNÉES
# ============================================================================

@dataclass
class ConsolidationResult:
    """Résultat de la consolidation d'une procédure."""
    procedure_source: str
    source_procedure_evidence: str
    procedure_consolidee: str
    procedure_regime: str
    conflit_coherence: str
    motif_conflit: str
    seuil_applicable_ht: Optional[int]
    montant_estime_ht: Optional[int]
    ratio_montant_sur_seuil: Optional[float]
    priorite_juridique: str
    niveau_confiance: str
    procedure_verdict: str
    verdict_final: str
    notes: str


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def parse_montant(montant_str: str) -> Optional[int]:
    """
    Extrait la valeur numérique d'un montant en euros HT.
    
    Gère les formats:
    - "18.02 M€ HT" -> 18020000
    - "140000 EUR" -> 140000
    - "18 020 000" -> 18020000
    - "18,02" (en millions) -> 18020000
    """
    if not montant_str or montant_str.strip() in ("", "None", "null", "-", "nan"):
        return None
    
    text = str(montant_str).strip().upper()
    
    # Détecter les millions
    multiplicateur = 1
    if "M€" in text or "MILLION" in text or "M " in text:
        multiplicateur = 1000000
    elif "K€" in text or "K EUR" in text:
        multiplicateur = 1000
    
    # Extraire les chiffres
    # Gérer les séparateurs français (espace, point pour milliers, virgule pour décimales)
    # Nettoyer d'abord
    text_clean = text.replace(" HT", "").replace("EUR", "").replace("€", "")
    text_clean = text_clean.replace("M", "").replace("K", "").replace("MILLION", "")
    
    # Remplacer les espaces et points par rien (séparateurs de milliers)
    text_clean = text_clean.replace(" ", "").replace("'", "").replace("\xa0", "")
    
    # Gérer la virgule comme séparateur décimal
    if "," in text_clean and "." in text_clean:
        # Format: 1.234,56 ou 1,234.56
        # En français: espace ou point = milliers, virgule = décimales
        if text_clean.rfind(",") > text_clean.rfind("."):
            # 1.234,56 -> 1234.56
            text_clean = text_clean.replace(".", "").replace(",", ".")
        else:
            # 1,234.56 -> 1234.56
            text_clean = text_clean.replace(",", "")
    elif "," in text_clean:
        # Possiblement séparateur de milliers (1,234) ou décimal (18,02)
        # Si après la virgule il y a 1-2 chiffres et que c'est la fin -> décimal
        parts = text_clean.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Décimal: 18,02 -> 18020000 (si millions)
            text_clean = text_clean.replace(",", ".")
        else:
            # Milliers: 1,234,567 -> 1234567
            text_clean = text_clean.replace(",", "")
    
    # Extraction finale
    match = re.search(r'(\d+(?:\.\d+)?)', text_clean)
    if match:
        try:
            valeur = float(match.group(1))
            return int(valeur * multiplicateur)
        except ValueError:
            return None
    
    return None


def determiner_seuil(
    type_acheteur: str,
    type_marche: str,
    categorie_regime: str
) -> Tuple[Optional[int], str]:
    """
    Détermine le seuil de procédure formalisée applicable.
    
    Retourne: (seuil_ht, priorite_appliquee)
    """
    # Normaliser les entrées
    acheteur = (type_acheteur or "").lower().strip()
    marche = (type_marche or "").lower().strip()
    regime = (categorie_regime or "").lower().strip()
    
    # Mapping type_acheteur
    if "etat" in acheteur:
        acheteur_key = "etat"
    elif "collectivite" in acheteur or "territoriale" in acheteur:
        acheteur_key = "collectivite_territoriale"
    elif "hopital" in acheteur or "hospitaliere" in acheteur:
        acheteur_key = "collectivite_territoriale"  # Même seuil
    elif "etablissement_public" in acheteur or "epic" in acheteur:
        acheteur_key = "etablissement_public"
    else:
        # Par défaut: autres pouvoirs adjudicateurs
        acheteur_key = "etablissement_public"
    
    # Mapping type_marche
    if "service" in marche:
        marche_key = "services"
    elif "fourniture" in marche:
        marche_key = "fournitures"
    elif "travaux" in marche:
        marche_key = "travaux"
    else:
        marche_key = "services"  # Par défaut
    
    # Mapping régime
    if "defense" in regime or "securite" in regime:
        regime_key = "defense_securite"
        priorite = "regime"
    else:
        regime_key = "marches_ordinaires"
        priorite = "seuil"
    
    # Chercher le seuil
    key = (acheteur_key, marche_key, regime_key)
    seuil = SEUILS_FORMALISES.get(key)
    
    if seuil is None:
        # Fallback: chercher sans régime défense
        key_fallback = (acheteur_key, marche_key, "marches_ordinaires")
        seuil = SEUILS_FORMALISES.get(key_fallback, 216000)
        priorite = "seuil (fallback)"
    
    return seuil, priorite


def detecter_procedure_source(row: Dict[str, str]) -> Tuple[str, str]:
    """
    Détecte la procédure source et son évidence.
    """
    procedure = (row.get("procedure_type", "") or "").strip().upper()
    
    if not procedure or procedure in ("INCONNU", "INDETERMINE", "NAN", "NONE", ""):
        return "INCONNUE", "Champ procedure_type vide ou non renseigné"
    
    # Mapping des valeurs
    if "MAPA" in procedure or "ADAPTE" in procedure:
        return "MAPA", f"Badge/champ explicite: {procedure}"
    elif "FORMALISE" in procedure:
        return "FORMALISEE", f"Badge/champ explicite: {procedure}"
    elif "NEGOCIE" in procedure:
        return "NEGOCIEE", f"Badge/champ explicite: {procedure}"
    elif "OUVERT" in procedure:
        return "OUVERTE", f"Badge/champ explicite: {procedure}"
    elif "RESTREINT" in procedure:
        return "RESTREINTE", f"Badge/champ explicite: {procedure}"
    
    return procedure, f"Valeur brute extraite: {procedure}"


def calculer_ratio(montant: Optional[int], seuil: Optional[int]) -> Optional[float]:
    """Calcule le ratio montant / seuil."""
    if montant is None or seuil is None or seuil == 0:
        return None
    return round(montant / seuil, 2)


def evaluer_preuve_joue(row: Dict[str, str]) -> Tuple[bool, str]:
    """Évalue la présence d'une preuve de publication JOUE."""
    preuve = (row.get("preuve_joue_detectee", "") or "").lower().strip()
    source = row.get("source_preuve_joue", "") or ""
    
    if preuve in ("oui", "yes", "true", "1"):
        return True, source or "Preuve JOUE détectée"
    
    # Vérifier aussi la référence
    reference = (row.get("reference", "") or "").lower()
    if "joue" in reference or reference.startswith("13/"):
        return True, "Format référence JOUE"
    
    return False, "Aucune preuve JOUE détectée"


# ============================================================================
# LOGIQUE DE CONSOLIDATION
# ============================================================================

def consolider_procedure(row: Dict[str, str]) -> ConsolidationResult:
    """
    Applique la logique de consolidation au marché.
    
    Implémente le contrat métier CONSOLIDATION-RULE-001.
    """
    # ------------------------------------------------------------------------
    # ÉTAPE 1: Extraire les données source
    # ------------------------------------------------------------------------
    procedure_source, source_evidence = detecter_procedure_source(row)
    
    type_acheteur = row.get("type_acheteur", "") or ""
    fonction_publique = row.get("fonction_publique", "") or ""
    type_marche = row.get("type_marche", "") or ""
    categorie_regime = row.get("categorie_regime", "") or ""
    montant_str = row.get("montant_estime", "") or ""
    
    # ------------------------------------------------------------------------
    # ÉTAPE 2: Calculer les contraintes juridiques
    # ------------------------------------------------------------------------
    montant_ht = parse_montant(montant_str)
    seuil_ht, priorite_base = determiner_seuil(type_acheteur, type_marche, categorie_regime)
    ratio = calculer_ratio(montant_ht, seuil_ht)
    preuve_joue, source_joue = evaluer_preuve_joue(row)
    
    # ------------------------------------------------------------------------
    # ÉTAPE 3: Appliquer les règles de consolidation
    # ------------------------------------------------------------------------
    
    conflit = "non"
    motif = ""
    procedure_consolidee = "INDETERMINE"
    niveau_confiance = "moyen"
    verdict = ""
    notes = ""
    priorite = priorite_base
    
    # Cas 1: Source inconnue
    if procedure_source == "INCONNUE":
        if preuve_joue:
            procedure_consolidee = "JOUE_PROUVE"
            niveau_confiance = "fort"
            verdict = "Procédure source inconnue mais preuve JOUE détectée"
            priorite = "preuve_joue"
        else:
            procedure_consolidee = "INDETERMINE"
            niveau_confiance = "faible"
            verdict = "Procédure source inconnue, aucune preuve de formalisation"
            priorite = "indetermine"
    
    # Cas 2: Source = MAPA
    elif procedure_source == "MAPA":
        # Vérifier cohérence avec montant
        if ratio is not None and ratio > 1.0:
            # Conflit : MAPA avec montant supérieur au seuil formalisé
            conflit = "oui"
            
            # Vérifier si régime défense
            if "defense" in categorie_regime.lower() or "securite" in categorie_regime.lower():
                motif = f"Montant {format_montant(montant_ht)} HT très supérieur au seuil défense {seuil_ht:,} € HT (ratio ×{ratio}) ; MAPA incompatible avec régime défense"
                procedure_consolidee = "FORMALISEE_REQUISE"
                niveau_confiance = "moyen"
                verdict = "La procédure source MAPA a été lue mais rejetée comme qualification finale car incohérente avec le montant et le régime apparent du marché"
                priorite = "seuil"
                notes = "Badge « Procédure adaptée » conservé comme trace source. La procédure exacte de droit spécial n'est pas déduite ici."
            else:
                motif = f"Montant {format_montant(montant_ht)} HT supérieur au seuil formalisé {seuil_ht:,} € HT (ratio ×{ratio}), incompatible avec MAPA"
                procedure_consolidee = "FORMALISEE_REQUISE"
                niveau_confiance = "moyen"
                verdict = "La procédure source MAPA a été lue mais rejetée comme qualification finale car montant supérieur au seuil applicable"
                priorite = "seuil"
                notes = "Badge « Procédure adaptée » probablement issu d'une erreur de saisie ou de mapping automatique"
        else:
            # MAPA cohérent avec le montant
            procedure_consolidee = "MAPA_SOUS_SEUIL"
            niveau_confiance = "fort"
            verdict = "Procédure source MAPA cohérente avec le montant et le seuil applicable"
            priorite = "source_explicite"
    
    # Cas 3: Source = FORMALISEE
    elif procedure_source in ("FORMALISEE", "OUVERTE", "RESTREINTE"):
        if preuve_joue:
            procedure_consolidee = "JOUE_PROUVE"
            niveau_confiance = "fort"
            verdict = "Procédure formalisée confirmée par preuve de publication JOUE"
            priorite = "preuve_joue"
        else:
            procedure_consolidee = "FORMALISEE_SANS_PREUVE_JOUE"
            niveau_confiance = "moyen"
            verdict = "Procédure formalisée déclarée mais sans preuve explicite de publication JOUE"
            priorite = "source_explicite"
    
    # Cas 4: Source = NEGOCIEE
    elif procedure_source == "NEGOCIEE":
        procedure_consolidee = "FORMALISEE_NEGOCIEE"
        niveau_confiance = "fort"
        verdict = "Procédure avec négociation détectée, formalisée par nature"
        priorite = "source_explicite"
    
    # Cas 5: Autres cas
    else:
        procedure_consolidee = "INDETERMINE"
        niveau_confiance = "faible"
        verdict = f"Procédure source '{procedure_source}' non reconnue, qualification indéterminée"
        priorite = "indetermine"
    
    # ------------------------------------------------------------------------
    # ÉTAPE 4: Construire le résultat
    # ------------------------------------------------------------------------
    return ConsolidationResult(
        procedure_source=procedure_source,
        source_procedure_evidence=source_evidence,
        procedure_consolidee=procedure_consolidee,
        procedure_regime=categorie_regime or "marches_ordinaires",
        conflit_coherence=conflit,
        motif_conflit=motif,
        seuil_applicable_ht=seuil_ht,
        montant_estime_ht=montant_ht,
        ratio_montant_sur_seuil=ratio,
        priorite_juridique=priorite,
        niveau_confiance=niveau_confiance,
        procedure_verdict=verdict,
        verdict_final=f"{procedure_consolidee} - {verdict.lower()}",
        notes=notes
    )


def format_montant(montant: Optional[int]) -> str:
    """Formate un montant pour l'affichage."""
    if montant is None:
        return "N/A"
    if montant >= 1000000:
        return f"{montant / 1000000:.2f} M€"
    return f"{montant:,} €".replace(",", " ")


# ============================================================================
# TRAITEMENT CSV
# ============================================================================

def process_csv(input_path: Path, output_path: Path) -> Dict:
    """
    Traite le fichier CSV et génère la version consolidée.
    """
    # Lire le CSV source
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames.copy()
    
    # Nouvelles colonnes à ajouter
    new_columns = [
        "procedure_source",
        "source_procedure_evidence",
        "procedure_consolidee",
        "procedure_regime",
        "conflit_coherence",
        "motif_conflit",
        "seuil_applicable_ht",
        "montant_estime_ht_parsed",
        "ratio_montant_sur_seuil",
        "priorite_juridique",
        "niveau_confiance",
        "procedure_verdict",
        "verdict_final",
        "notes_consolidation"
    ]
    
    # Ajouter les nouvelles colonnes
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)
    
    # Traiter chaque ligne
    stats = {
        "total": len(rows),
        "conflits": 0,
        "mapa_rejetes": 0,
        "mapa_acceptes": 0,
        "joue_proves": 0,
        "formalises_sans_preuve": 0,
        "formalises_requis": 0,
        "indetermines": 0
    }
    
    for row in rows:
        result = consolider_procedure(row)
        
        # Mettre à jour les stats
        if result.conflit_coherence == "oui":
            stats["conflits"] += 1
        
        if result.procedure_consolidee == "MAPA_SOUS_SEUIL":
            stats["mapa_acceptes"] += 1
        elif result.procedure_consolidee == "JOUE_PROUVE":
            stats["joue_proves"] += 1
        elif result.procedure_consolidee == "FORMALISEE_SANS_PREUVE_JOUE":
            stats["formalises_sans_preuve"] += 1
        elif result.procedure_consolidee == "FORMALISEE_REQUISE":
            stats["formalises_requis"] += 1
            if result.procedure_source == "MAPA":
                stats["mapa_rejetes"] += 1
        elif result.procedure_consolidee == "INDETERMINE":
            stats["indetermines"] += 1
        
        # Enrichir la ligne
        row["procedure_source"] = result.procedure_source
        row["source_procedure_evidence"] = result.source_procedure_evidence
        row["procedure_consolidee"] = result.procedure_consolidee
        row["procedure_regime"] = result.procedure_regime
        row["conflit_coherence"] = result.conflit_coherence
        row["motif_conflit"] = result.motif_conflit
        row["seuil_applicable_ht"] = result.seuil_applicable_ht if result.seuil_applicable_ht else ""
        row["montant_estime_ht_parsed"] = result.montant_estime_ht if result.montant_estime_ht else ""
        row["ratio_montant_sur_seuil"] = result.ratio_montant_sur_seuil if result.ratio_montant_sur_seuil else ""
        row["priorite_juridique"] = result.priorite_juridique
        row["niveau_confiance"] = result.niveau_confiance
        row["procedure_verdict"] = result.procedure_verdict
        row["verdict_final"] = result.verdict_final
        row["notes_consolidation"] = result.notes
    
    # Écrire le CSV enrichi
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return stats


def main():
    """Point d'entrée principal."""
    input_file = Path('/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v9.csv')
    output_file = Path('/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v10.csv')
    
    if not input_file.exists():
        print(f"❌ Erreur: {input_file} n'existe pas")
        sys.exit(1)
    
    print("=" * 70)
    print("CONSOLIDATION DES PROCÉDURES DE MARCHÉS PUBLICS")
    print("Contrat métier: CONSOLIDATION-RULE-001 v1.0")
    print("=" * 70)
    print()
    
    print(f"📁 Fichier source: {input_file}")
    print(f"📁 Fichier sortie: {output_file}")
    print()
    
    # Traitement
    stats = process_csv(input_file, output_file)
    
    # Rapport
    print("=" * 70)
    print("STATISTIQUES DE CONSOLIDATION")
    print("=" * 70)
    print(f"  Total lignes traitées:     {stats['total']}")
    print(f"  Conflits détectés:         {stats['conflits']}")
    print()
    print("RÉPARTITION DES PROCÉDURES CONSOLIDÉES:")
    print(f"  MAPA acceptés (cohérents): {stats['mapa_acceptes']}")
    print(f"  MAPA rejetés (conflits):   {stats['mapa_rejetes']}")
    print(f"  JOUE prouvés:              {stats['joue_proves']}")
    print(f"  Formalisés sans preuve:    {stats['formalises_sans_preuve']}")
    print(f"  Formalisés requis:         {stats['formalises_requis']}")
    print(f"  Indéterminés:              {stats['indetermines']}")
    print()
    print(f"✅ Fichier consolidé généré: {output_file}")
    print()
    print("Nouvelles colonnes ajoutées:")
    print("  - procedure_source, source_procedure_evidence")
    print("  - procedure_consolidee, procedure_regime")
    print("  - conflit_coherence, motif_conflit")
    print("  - seuil_applicable_ht, montant_estime_ht_parsed, ratio_montant_sur_seuil")
    print("  - priorite_juridique, niveau_confiance")
    print("  - procedure_verdict, verdict_final, notes_consolidation")


if __name__ == '__main__':
    main()
