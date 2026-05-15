#!/usr/bin/env python3
"""
Classification déterministe de type_acheteur et fonction_publique.

Entrée: CSV du pipeline (par défaut final-v4-juridique.csv)
Sortie: CSV avec type_acheteur et fonction_publique classifiés

Algorithme :
1. Normalisation préalable : les valeurs existantes non-standard sont corrigées
2. Règles sur le libellé `acheteur` : patterns insensibles à la casse/accents
3. Déduction de `fonction_publique` à partir de `type_acheteur` enrichi

Chaque ligne reçoit deux colonnes source (_source ∈ {"rule","original"})
"""

import argparse
from pathlib import Path
from typing import Dict, Any
from collections import Counter

# ── Import utilitaires partagés ─────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import read_csv, write_csv, normalize, contains_any, starts_with_any, normalize_keywords
from utils import get_output_path

# ── Chemins ─────────────────────────────────────────────────────────────────
# Par défaut, utilise le fichier généré par le pipeline (phase enrich_juridique)
DEFAULT_INPUT = "final-v4-juridique.csv"
DEFAULT_OUTPUT = "final-v4-classified.csv"

# ── Mots-clés (normalisés via utilitaire partagé) ────────────────────────────


# Marqueurs « État »
ETAT_KEYWORDS = normalize_keywords([
    "Ministère", "Ministre", "Direction générale", "DGFiP", "DGFIP",
    "Ministère des Armées", "Ministère de la Justice",
    "Direction du numérique", "DNUM",
    "Préfecture", "Service de l'État",
    "INSEE",
    "MINARM", "MINDEF", "DIRISI",
    "IFCE",  # Institut français du cheval et de l'équitation
])

# Marqueurs « collectivité territoriale »
CT_PREFIXES = normalize_keywords([
    "Ville de", "Commune de", "Mairie de",
])
CT_KEYWORDS = normalize_keywords([
    "Conseil départemental", "Conseil régional",
    "Région ",  # espace intentionnel pour éviter de matcher "régional"
    "Communauté de communes", "Communauté d'agglomération",
    "Communauté d agglomération",  # variante sans apostrophe
    "Métropole",
    "Syndicat intercommunal", "Syndicat mixte",
    "VILLE de",  # variante majuscule fréquente
    "Agglo",  # ex : Le Muretain Agglo
    "Communauté",  # communautés diverses
])

# Marqueurs « SPL » (Sociétés publiques locales, 100% capitaux CT)
# Les SPL sont des personnes morales de droit privé mais agissent
# exclusivement pour le compte de collectivités → classées CT.
SPL_KEYWORDS = normalize_keywords([
    "SPL ",  # ex: SPL SEMEA
    "Société publique locale",
])

# Marqueurs « SEM / économie mixte » → entreprise_privee
SEM_KEYWORDS = normalize_keywords([
    "Société d'économie mixte", "Societe d'economie mixte",
    "Société d economie mixte",  # variante sans apostrophe
    "SA d'économie mixte", "SA d economie mixte",
    "SEM ",  # ex: SEM GEG  (espace pour éviter faux positifs)
])

# Marqueurs hospitaliers
HOPITAL_KEYWORDS = normalize_keywords([
    "Centre hospitalier", "CHU ", "CHU-", "GHT ",
    "Hôpital", "Hopital",
    "Hospices civils", "AP-HP", "APHP",
    "GCS-UNIHA", "GCS UNIHA", "UNIHA",  # groupement de coopération sanitaire
])

# Marqueurs « établissement public » (non hospitalier, rattaché à l'État)
EP_ETAT_KEYWORDS = normalize_keywords([
    "Conservatoire national des arts et métiers", "Cnam",
    "Institut géographique national", "IGN",
    "Institut Français",
    "Haute Autorité de Santé",  # autorité administrative indépendante (AAI)
    "Académie",
    "UGAP", "Union des Groupements d'Achats Publics",
    "BRGM", "Bureau de Recherche",
    "Agence de l'Eau", "Agence de l eau",
    "Synchrotron",
    "ESADMM",  # école supérieure d'art et de design
    "EPPGHV",  # Établissement public du parc de la Villette
    "Supélec", "Supelec", "CentraleSupélec", "CentraleSupelec", "Centrale Supelec",
    "Université", "Universite", "COMUE",
    # Opérateurs / EPIC / EPA de l'État
    "CEA ", "CEA/",  # Commissariat à l'énergie atomique
    "CNRS",  # Centre national de la recherche scientifique
    "CNAF",  # Caisse nationale des allocations familiales
    "SHOM",  # Service hydrographique et océanographique
    "EOESRI",  # opérateur enseignement supérieur
])

# Marqueurs « entités privées / hors FP »
PRIVE_KEYWORDS = normalize_keywords([
    " SA ", " SAS ", " GIP ",
    "SA en son nom",
    "Intercommunale",  # forme belge/étrangère
    "Parlement Wallon",  # institution étrangère
    "Association ",
    "Compagnie Nationale du Rhône",  # SA d'intérêt général
    "UNICANCER",  # GCS de droit privé
    "Organisation qui passe un marché subventionné",  # entité privée subventionnée
])

# ── Fonction de classification ──────────────────────────────────────────────

def classify_row(row: dict) -> dict:
    """Classifie une ligne et retourne les champs enrichis."""

    acheteur_raw = row.get("Acheteur_clean") or row.get("Acheteur_auto", "")
    ta_orig = row.get("Type", "").strip()
    fp_orig = row.get("Fonction publique", "").strip()

    acheteur_n = normalize(acheteur_raw)

    # -- Étape 0 : normaliser les valeurs existantes non-standard -----------
    # "hopital" n'est pas dans le référentiel → établissement_public
    ta = ta_orig
    if ta.lower() == "hopital":
        ta = "etablissement_public"
    # "Etat" → "etat"
    fp = fp_orig
    if fp.lower() == "etat":
        fp = "etat"

    ta_before = ta  # pour tracer si rule a changé
    fp_before = fp

    # -- Étape 1 : règles sur type_acheteur ---------------------------------

    # 1a. Marqueurs hospitaliers (priorité haute, avant collectivité)
    if contains_any(acheteur_n, HOPITAL_KEYWORDS):
        ta = "etablissement_public"

    # 1b. Établissements publics nommément identifiés (CEA, CNRS, COMUE, etc.)
    #     Testé AVANT les marqueurs État génériques pour éviter que CEA/CNRS
    #     soient classés « etat » au lieu de « etablissement_public ».
    elif contains_any(acheteur_n, EP_ETAT_KEYWORDS):
        ta = "etablissement_public"

    # 1c. Marqueurs « État » (ministères, directions générales, MINARM, etc.)
    elif contains_any(acheteur_n, ETAT_KEYWORDS):
        ta = "etat"

    # 1d. Collectivités territoriales (préfixes + mots-clés)
    elif starts_with_any(acheteur_n, CT_PREFIXES) or contains_any(acheteur_n, CT_KEYWORDS):
        ta = "collectivite_territoriale"

    # 1e. SPL (Société publique locale) → collectivite_territoriale
    elif contains_any(acheteur_n, SPL_KEYWORDS):
        ta = "collectivite_territoriale"

    # 1f. SEM (Société d'économie mixte) → entreprise_privee
    elif contains_any(acheteur_n, SEM_KEYWORDS):
        ta = "entreprise_privee"

    # 1g. Entités privées / hors fonction publique
    elif contains_any(acheteur_n, PRIVE_KEYWORDS):
        ta = "inconnu"  # fallback privé sans catégorie précise

    # 1h. Si toujours vide ou "inconnu", on ne touche pas
    if not ta:
        ta = "inconnu"

    # -- Étape 2 : règles sur fonction_publique -----------------------------

    is_hospital_marker = contains_any(acheteur_n, HOPITAL_KEYWORDS)
    is_prive_marker = contains_any(acheteur_n, PRIVE_KEYWORDS) and not is_hospital_marker

    is_sem_marker = contains_any(acheteur_n, SEM_KEYWORDS)

    if ta == "collectivite_territoriale":
        fp = "territoriale"
    elif ta == "etat":
        fp = "etat"
    elif ta == "etablissement_public":
        if is_hospital_marker:
            fp = "hospitaliere"
        else:
            fp = "etat"  # EP rattaché à l'État
    elif ta == "entreprise_privee" or is_prive_marker or is_sem_marker:
        fp = "hors_fonction_publique"

    if not fp or fp.lower() in ("", "inconnue", "inconnu"):
        fp = "inconnue"

    # -- Étape 3 : déterminer les sources -----------------------------------
    # On compare au *original brut* pour savoir si on a modifié
    ta_source = "original" if ta == ta_orig else "rule"
    fp_source = "original" if fp == fp_orig else "rule"

    # Corrections de normalisation pure (hopital→etablissement_public, Etat→etat)
    # sont aussi des "rule"
    # (déjà couvert car ta_orig / fp_orig sont les valeurs brutes)

    row["Type"] = ta
    row["Fonction publique"] = fp
    row["type_acheteur_source"] = ta_source
    row["fonction_publique_source"] = fp_source

    return row


def print_report(
    classified: list[dict],
    orig_rows: dict,
    input_path: Path,
    output_path: Path
) -> None:
    """Affiche le rapport de classification."""
    ta_changed = [r for r in classified if r["type_acheteur_source"] == "rule"]
    fp_changed = [r for r in classified if r["fonction_publique_source"] == "rule"]

    print(f"{'='*70}")
    print(f"RAPPORT DE CLASSIFICATION DÉTERMINISTE")
    print(f"{'='*70}")
    print(f"Fichier source : {input_path}")
    print(f"Fichier produit: {output_path}")
    print(f"Lignes totales : {len(classified)}")
    print()
    print(f"type_acheteur modifié par règle : {len(ta_changed)} / {len(classified)}")
    print(f"fonction_publique modifié par règle : {len(fp_changed)} / {len(classified)}")
    print()

    if ta_changed or fp_changed:
        all_changed = {r["Référence"] for r in ta_changed} | {r["Référence"] for r in fp_changed}
        print(f"Détail des {len(all_changed)} lignes modifiées :")
        print(f"{'-'*70}")

        for r in classified:
            if r["Référence"] in all_changed:
                orig = orig_rows[r["Référence"]]
                changes = []
                if r["type_acheteur_source"] == "rule":
                    changes.append(f"  type_acheteur: {orig['Type']!r} → {r['Type']!r}")
                if r["fonction_publique_source"] == "rule":
                    changes.append(f"  fonction_publique: {orig['Fonction publique']!r} → {r['Fonction publique']!r}")
                print(f"  [{r['Référence']}] {r.get('Acheteur_clean', r.get('Acheteur_auto', 'N/A'))}")
                for c in changes:
                    print(c)
                print()

    # Distribution finale
    ta_dist = Counter(r["Type"] for r in classified)
    fp_dist = Counter(r["Fonction publique"] for r in classified)
    print("Distribution finale type_acheteur :")
    for k, v in sorted(ta_dist.items()):
        print(f"  {k}: {v}")
    print("\nDistribution finale fonction_publique :")
    for k, v in sorted(fp_dist.items()):
        print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(
        description="Classification déterministe des acheteurs"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=None,
        help=f"Fichier CSV d'entrée (défaut: {DEFAULT_INPUT})"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help=f"Fichier CSV de sortie (défaut: {DEFAULT_OUTPUT})"
    )
    args = parser.parse_args()

    # Déterminer le chemin d'entrée
    if args.input:
        input_path = args.input
        # Si le fichier n'existe pas tel quel, essayer dans data/output/
        if not input_path.exists() and not input_path.is_absolute():
            alt_path = get_output_path(input_path.name)
            if alt_path.exists():
                input_path = alt_path
    else:
        input_path = get_output_path(DEFAULT_INPUT)
    
    # Déterminer le chemin de sortie
    if args.output:
        output_path = args.output
    else:
        output_path = get_output_path(DEFAULT_OUTPUT)
    
    # Vérifier que le fichier d'entrée existe
    if not input_path.exists():
        print(f"❌ Erreur: Fichier non trouvé: {input_path}")
        print(f"   Cherché également dans: {get_output_path(input_path.name)}")
        sys.exit(1)
    
    rows, fieldnames = read_csv(input_path)
    fieldnames += ["type_acheteur_source", "fonction_publique_source"]

    classified = [classify_row(row) for row in rows]
    write_csv(output_path, classified, fieldnames)

    # Relecture pour le rapport
    orig_rows = {r["Référence"]: r for r in rows}
    print_report(classified, orig_rows, input_path, output_path)


if __name__ == "__main__":
    main()
