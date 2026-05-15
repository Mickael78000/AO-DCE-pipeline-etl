"""Phase ENRICH_JURIDIQUE - Enrichissement juridique avec regex.

Détection des procédures, régimes et typologies via patterns regex.
Basé sur enrich_procedure_juridique_v8.py
"""

import re
import pandas as pd
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Tuple


@dataclass
class EnrichJuridiqueConfig:
    """Configuration pour l'enrichissement juridique."""
    enabled: bool = False
    output_csv: Optional[Path] = None
    output_excel: Optional[Path] = None


# =============================================================================
# CONSTANTES ET MARQUEURS (REGEX-BASED)
# =============================================================================

SEUILS_FORMALISE = {
    'autorite_publique_centrale': 140000,
    'collectivite_territoriale_etablissement_public': 216000,
    'entite_adjudicatrice': 432000,
}

MARQUEURS_DEFENSE_SECURITE = [
    r"marche de defense et securite",
    r"marche de d[ée]fense et s[ée]curit[ée]",
    r"d[ée]fense et s[ée]curit[ée]",
    r"defense et securite",
    r"d[ée]fense nationale",
    r"defense nationale",
    r"s[ée]curit[ée] nationale",
    r"securite nationale",
    r"minist[èe]re des arm[ée]es",
    r"ministere des armees",
    r"minist[èe]re de la d[ée]fense",
    r"ministere de la defense",
    r"secret d[ée]fense",
    r"secret defense",
    r"confidentiel d[ée]fense",
    r"dirisi",
    r"cnd",
]

MARQUEURS_NEGOCIEE = [
    r"proc[ée]dure avec n[ée]gociation",
    r"procedure avec negociation",
    r"proc[ée]dure n[ée]goci[ée]e",
    r"procedure negociee",
    r"concurrentielle avec n[ée]gociation",
    r"concurrentielle avec negociation",
    r"n[ée]goci[ée]e avec publication pr[ée]alable",
    r"negociee avec publication prealable",
    r"n[ée]goci[ée]e avec publication pr[ée]alable d'un appel [àa] la concurrence",
    r"negociee avec publication prealable d'un appel a la concurrence",
    r"appel d'offres avec n[ée]gociation",
    r"appel d offres avec n[ée]gociation",
    r"appel d'offres avec negociation",
]

MARQUEURS_MAPA = [
    r"\bmapa\b",
    r"proc[ée]dure adapt[ée]e",
    r"procedure adaptee",
]

MARQUEURS_JOUE = [
    r"/joue/",
    r"journal officiel de l'union europ[ée]enne",
    r"journal officiel de l'union europeenne",
]

# Couleurs pour Excel
COULEURS = {
    'JOUE_PROUVE': {'fond': '2F6B9A', 'texte': 'FFFFFF'},
    'FORMALISEE_NEGOCIEE_DEFENSE_SECURITE': {'fond': '1E3A5F', 'texte': 'FFFFFF'},
    'FORMALISEE_SANS_PREUVE_JOUE': {'fond': 'E9EEF5', 'texte': '374151'},
    'MAPA_SOUS_SEUIL': {'fond': 'EAF3FF', 'texte': '1F4E79'},
    'INDETERMINE': {'fond': 'F3F4F6', 'texte': '4B5563'},
}


# =============================================================================
# FONCTIONS DE NORMALISATION
# =============================================================================

def normaliser_texte(value) -> str:
    """Normalise un texte pour la comparaison regex."""
    if value is None:
        return ""
    text = str(value).lower()
    text = text.replace("'", "'").replace("'", "'")
    text = text.replace("œ", "oe").replace("æ", "ae")
    text = text.replace("–", "-").replace("—", "-")
    text = " ".join(text.split())
    return text


def construire_texte_source(row: dict, champs: list) -> str:
    """Concatène plusieurs champs pour la recherche regex."""
    valeurs = []
    for champ in champs:
        val = row.get(champ)
        if val is not None and str(val).strip():
            valeurs.append(normaliser_texte(val))
    return " ".join(valeurs)


def contient_marqueur(texte: str, marqueurs: list) -> tuple:
    """Vérifie si un texte contient l'un des patterns regex."""
    for pattern in marqueurs:
        match = re.search(pattern, texte, re.IGNORECASE)
        if match:
            return True, match.group(0)
    return False, None


# =============================================================================
# FONCTIONS DE DÉTECTION (REGEX-BASED)
# =============================================================================

def detecter_categorie_regime(row: dict) -> tuple:
    """Détecte le régime juridique (défense/sécurité vs ordinaire) via regex."""
    champs_recherche = [
        'reference', 'titre', 'notes_verification', 'raisons_verification',
        'procedure_type', 'acheteur'
    ]
    texte_complet = construire_texte_source(row, champs_recherche)
    
    trouve, marqueur = contient_marqueur(texte_complet, MARQUEURS_DEFENSE_SECURITE)
    
    if trouve:
        return "defense_securite", f"Marqueur explicite: '{marqueur}'"
    
    return "marches_ordinaires", "Aucun marqueur défense/sécurité détecté"


def detecter_typologie_marche(row: dict) -> tuple:
    """Détecte la typologie (fournitures/services/travaux) via regex."""
    type_marche = normaliser_texte(row.get('type_marche', ''))
    titre = normaliser_texte(row.get('titre', ''))
    ccag = normaliser_texte(row.get('ccag_type', ''))
    
    indices = []
    
    # Patterns regex pour chaque catégorie
    mots_travaux = [
        r"travaux", r"construction", r"chantier", r"r[ée]habilitation", r"rehabilitation",
        r"gros oeuvre", r"gros-oeuvre", r"b[âa]timent", r"batiment", r"ouvrage"
    ]
    mots_fournitures = [
        r"fourniture", r"serveur", r"licence", r"mat[ée]riel", r"materiel",
        r"logiciel", r"[ée]quipement", r"equipement", r"hardware", r"material"
    ]
    mots_services = [
        r"service", r"prestation", r"assistance", r"conseil", r"expertise",
        r"infog[ée]rance", r"infogerance", r"maintenance", r"d[ée]veloppement",
        r"developpement", r"cloud", r"h[ée]bergement", r"hebergement", r"\btma\b",
        r"migration", r"int[ée]gration", r"integration", r"support"
    ]
    
    # Vérification via type_marche
    if type_marche == 'travaux':
        indices.append("type_marche='travaux'")
    elif type_marche == 'fournitures':
        indices.append("type_marche='fournitures'")
    elif type_marche == 'services':
        indices.append("type_marche='services'")
    
    # Vérification via CCAG
    if re.search(r"travaux", ccag, re.IGNORECASE):
        indices.append("CCAG travaux")
    elif re.search(r"fourniture", ccag, re.IGNORECASE):
        indices.append("CCAG fournitures")
    elif re.search(r"prestations_intellectuelles|tic|prestation", ccag, re.IGNORECASE):
        indices.append("CCAG prestations/services")
    
    # Comptage par catégorie avec regex
    count_travaux = sum(1 for p in mots_travaux if re.search(p, titre, re.IGNORECASE))
    count_fournitures = sum(1 for p in mots_fournitures if re.search(p, titre, re.IGNORECASE))
    count_services = sum(1 for p in mots_services if re.search(p, titre, re.IGNORECASE))
    
    max_count = max(count_travaux, count_fournitures, count_services)
    
    if count_travaux > 0 and count_travaux == max_count:
        return "travaux", "; ".join(indices) if indices else "indice titre"
    elif count_fournitures > 0 and count_fournitures == max_count:
        return "fournitures", "; ".join(indices) if indices else "indice titre"
    elif count_services > 0 and count_services == max_count:
        return "services", "; ".join(indices) if indices else "indice titre"
    
    if type_marche in ['travaux', 'fournitures', 'services']:
        return type_marche, f"type_marche='{type_marche}' (pas d'indice titre)"
    
    return "indetermine", "Aucun indice typologique clair"


def detecter_qualite_preuve_procedure(row: dict, typologie: str, categorie_regime: str) -> tuple:
    """Évalue la qualité de la preuve via regex."""
    procedure_type = normaliser_texte(row.get('procedure_type', ''))
    titre = normaliser_texte(row.get('titre', ''))
    notes = normaliser_texte(row.get('notes_verification', ''))
    raisons = normaliser_texte(row.get('raisons_verification', ''))
    
    # Vérification EXPLICITE dans procedure_type
    if procedure_type:
        trouve_mapa, _ = contient_marqueur(procedure_type, MARQUEURS_MAPA)
        trouve_neg, _ = contient_marqueur(procedure_type, MARQUEURS_NEGOCIEE)
        trouve_form = re.search(r'formalis[ée]e', procedure_type, re.IGNORECASE)
        trouve_joue = re.search(r'joue', procedure_type, re.IGNORECASE)
        
        if trouve_mapa or trouve_neg or trouve_form or trouve_joue:
            return "EXPLICITE", ""
    
    # Recherche dans autres champs
    texte_secondaire = f"{titre} {notes} {raisons}"
    
    negociee_secondaire, _ = contient_marqueur(texte_secondaire, MARQUEURS_NEGOCIEE)
    mapa_secondaire, _ = contient_marqueur(texte_secondaire, MARQUEURS_MAPA)
    
    # Détection conflits
    if procedure_type:
        if trouve_mapa and negociee_secondaire:
            return "CONTRADICTOIRE", "MAPA explicite mais mention de négociation"
        if trouve_form and mapa_secondaire:
            return "CONTRADICTOIRE", "Formalisée explicite mais mention MAPA"
        if categorie_regime == "defense_securite" and trouve_mapa:
            return "CONTRADICTOIRE", "Régime défense/sécurité avec MAPA"
    
    if negociee_secondaire:
        return "FORT_INDICE", ""
    
    if re.search(r'procedure|marche', texte_secondaire, re.IGNORECASE):
        return "FAIBLE_INDICE", ""
    
    return "ABSENTE", ""


def est_mapa_explicite(row: dict) -> bool:
    """Vérifie si procedure_type contient MAPA via regex."""
    procedure_type = normaliser_texte(row.get('procedure_type', ''))
    trouve, _ = contient_marqueur(procedure_type, MARQUEURS_MAPA)
    return trouve


def est_procedure_negociee(row: dict) -> tuple:
    """Détecte procédure négociée via regex."""
    champs = ['procedure_type', 'titre', 'notes_verification', 'raisons_verification']
    texte = construire_texte_source(row, champs)
    return contient_marqueur(texte, MARQUEURS_NEGOCIEE)


def est_joue_prouve(row: dict) -> tuple:
    """Détecte preuve JOUE via regex."""
    reference = normaliser_texte(row.get('reference', ''))
    url_marche = normaliser_texte(row.get('url_marche', ''))
    fichier_source = normaliser_texte(row.get('fichier_source_html', ''))
    
    if re.search(r'/joue/', reference, re.IGNORECASE):
        return True, 'reference'
    if re.search(r'/joue/', url_marche, re.IGNORECASE):
        return True, 'url'
    if re.search(r'joue', fichier_source, re.IGNORECASE):
        return True, 'html'
    
    champs = ['notes_verification', 'raisons_verification', 'titre']
    texte = construire_texte_source(row, champs)
    trouve, _ = contient_marqueur(texte, MARQUEURS_JOUE)
    if trouve:
        return True, 'texte_source'
    
    return False, ''


def determiner_categorie_acheteur(row: dict) -> str:
    """Détermine la catégorie d'acheteur via regex."""
    type_acheteur = normaliser_texte(row.get('type_acheteur', ''))
    fonction_publique = normaliser_texte(row.get('fonction_publique', ''))
    acheteur = normaliser_texte(row.get('acheteur', ''))
    
    if (re.search(r'\betat\b', type_acheteur) or 
        re.search(r'\betat\b', fonction_publique) or
        re.search(r'minist[èe]re|dgfip', acheteur)):
        return 'autorite_publique_centrale'
    
    if re.search(r'collectivite|etablissement_public|groupement', type_acheteur):
        return 'collectivite_territoriale_etablissement_public_autre_acheteur'
    
    if re.search(r'entite_adjudicatrice|adjudicatrice', type_acheteur):
        return 'entite_adjudicatrice'
    
    return 'indetermine'


def determiner_seuil_applicable(categorie_acheteur: str, categorie_regime: str) -> Optional[int]:
    """Détermine le seuil applicable."""
    if categorie_regime == 'defense_securite':
        return None
    
    return SEUILS_FORMALISE.get(categorie_acheteur)


# =============================================================================
# DÉDUCTION FINALE
# =============================================================================

def deduire_niveau_procedure(row: dict, categorie_regime: str, qualite_preuve: str,
                              type_conflit: str) -> tuple:
    """Déduit le niveau de procédure selon l'arbre de décision."""
    # Étape 1: Conflits
    if type_conflit and qualite_preuve == "CONTRADICTOIRE":
        if "défense/sécurité avec MAPA" in type_conflit:
            return "INDETERMINE", f"Conflit majeur: {type_conflit}"
        if "MAPA explicite mais mention de négociation" in type_conflit:
            return "FORMALISEE_SANS_PREUVE_JOUE", "Conflit résolu: négociation prime sur MAPA"
        return "INDETERMINE", f"Conflit détecté: {type_conflit}"
    
    # Étape 2: Régime défense/sécurité
    if categorie_regime == "defense_securite":
        neg_trouve, marqueur_neg = est_procedure_negociee(row)
        if neg_trouve:
            return "FORMALISEE_NEGOCIEE_DEFENSE_SECURITE", \
                   f"Régime défense/sécurité; procédure négociée ('{marqueur_neg}')"
        
        joue_trouve, _ = est_joue_prouve(row)
        if joue_trouve:
            return "JOUE_PROUVE", "Régime défense/sécurité; publication JOUE"
        
        return "INDETERMINE", "Régime défense/sécurité; procédure indécrite"
    
    # Étape 3: Régime ordinaire
    neg_trouve, marqueur_neg = est_procedure_negociee(row)
    if neg_trouve:
        return "FORMALISEE_SANS_PREUVE_JOUE", \
               f"Procédure négociée détectée ('{marqueur_neg}'); classification formalisée"
    
    joue_trouve, _ = est_joue_prouve(row)
    if joue_trouve:
        return "JOUE_PROUVE", "Publication JOUE"
    
    if est_mapa_explicite(row):
        return "MAPA_SOUS_SEUIL", "MAPA explicite dans procedure_type"
    
    procedure_type = normaliser_texte(row.get('procedure_type', ''))
    if re.search(r'formalis[ée]e', procedure_type, re.IGNORECASE):
        return "FORMALISEE_SANS_PREUVE_JOUE", "Procédure formalisée explicite"
    
    if qualite_preuve == "ABSENTE":
        return "INDETERMINE", "Aucune preuve"
    
    return "INDETERMINE", "Preuve insuffisante"


def enrichir_ligne(row) -> dict:
    """Enrichit une ligne avec les colonnes juridiques (basé sur regex)."""
    result = {}
    
    # ÉTAPE 1: Régime
    categorie_regime, preuve_regime = detecter_categorie_regime(row)
    result['categorie_regime'] = categorie_regime
    result['preuve_regime'] = preuve_regime
    
    # ÉTAPE 2: Typologie
    typologie, preuve_typologie = detecter_typologie_marche(row)
    result['typologie_marche_verifiee'] = typologie
    result['preuve_typologie'] = preuve_typologie
    
    # ÉTAPE 3: Qualité preuve
    qualite_preuve, type_conflit = detecter_qualite_preuve_procedure(row, typologie, categorie_regime)
    result['qualite_preuve_procedure'] = qualite_preuve
    result['conflit_detecte'] = 'oui' if type_conflit else 'non'
    result['type_conflit'] = type_conflit
    
    # ÉTAPE 4: JOUE
    joue_trouve, source_joue = est_joue_prouve(row)
    result['preuve_joue_detectee'] = 'oui' if joue_trouve else 'non'
    result['source_preuve_joue'] = source_joue
    
    # ÉTAPE 5: Niveau procédure
    niveau, justification = deduire_niveau_procedure(row, categorie_regime, qualite_preuve, type_conflit)
    result['famille_procedure_deduite'] = niveau
    result['niveau_procedure_deduit'] = niveau
    result['justification_juridique_courte'] = justification
    
    # ÉTAPE 6: Seuil
    if categorie_regime == 'defense_securite' or typologie in ['travaux', 'indetermine']:
        result['seuil_formalise_applicable'] = ''
    else:
        categorie_acheteur = determiner_categorie_acheteur(row)
        seuil = determiner_seuil_applicable(categorie_acheteur, categorie_regime)
        result['seuil_formalise_applicable'] = str(seuil) if seuil else ''
    
    # ÉTAPE 7: Code couleur
    result['code_couleur_procedure'] = niveau
    
    return result


# =============================================================================
# FONCTIONS PRINCIPALES DU PIPELINE
# =============================================================================

def enrichir_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Enrichit tout le dataframe avec les champs juridiques."""
    print("🔍 Analyse juridique (regex-based) en cours...")
    
    enrichments = []
    for _, row in df.iterrows():
        enrichments.append(enrichir_ligne(row))
    
    df_enrich = pd.DataFrame(enrichments)
    df_result = pd.concat([df, df_enrich], axis=1)
    
    # Statistiques
    stats = df_enrich['famille_procedure_deduite'].value_counts()
    print(f"\n📊 Qualification procédure:")
    for niveau, count in stats.items():
        print(f"   - {niveau}: {count}")
    
    conflits = df_enrich['conflit_detecte'].value_counts()
    if 'oui' in conflits:
        print(f"\n⚠️ Conflits: {conflits['oui']} marchés")
    
    return df_result


def run_enrich_juridique(input_csv: Path, output_csv: Path) -> Dict:
    """Exécute l'enrichissement juridique complet."""
    print(f"📖 Lecture: {input_csv}")
    df = pd.read_csv(input_csv, sep=',', quotechar='"', encoding='utf-8')
    print(f"✅ {len(df)} lignes chargées")
    
    df_enriched = enrichir_dataframe(df)
    
    # Sauvegarde
    df_enriched.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"✅ CSV juridique: {output_csv}")
    
    stats = df_enriched['famille_procedure_deduite'].value_counts().to_dict()
    
    return {
        'output_csv': str(output_csv),
        'rows_processed': len(df),
        'stats': stats,
    }


def print_enrich_summary(stats: Dict) -> None:
    """Affiche le résumé de l'enrichissement."""
    print(f"\n[ENRICH_JURIDIQUE] Enrichissement terminé")
    print("=" * 50)
    print(f"  Lignes traitées: {stats.get('rows_processed', 0)}")
    print(f"  CSV sortie: {stats.get('output_csv', 'N/A')}")
    print("=" * 50)
