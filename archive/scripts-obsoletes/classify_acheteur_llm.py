#!/usr/bin/env python3
"""
Enrichissement LLM des cas résiduels type_acheteur=inconnu.

Ce script applique les résultats de la recherche web manuelle (effectuée par
le LLM avec vérification de sources) pour classifier les 12 lignes restantes
du CSV `final-v3-consolidated-classified-rule.csv`.

Chaque reclassification est tracée avec :
- type_acheteur_source = "llm"
- fonction_publique_source = "llm"
- classification_commentaire = justification + URLs sources
"""

import csv
from pathlib import Path

INPUT_CSV = Path(__file__).resolve().parent.parent / "data" / "output" / "final-v3-consolidated-classified-rule.csv"
OUTPUT_CSV = INPUT_CSV.parent / "final-v3-consolidated-classified-llm.csv"

# ── Base de connaissances issue de la recherche web ─────────────────────────
# Clé : libellé acheteur normalisé (lower stripped), pour matcher les doublons.
# Chaque entrée décrit la classification et les sources.

ACHETEUR_DB = {
    "sicio": {
        "type_acheteur": "collectivite_territoriale",
        "fonction_publique": "territoriale",
        "commentaire": (
            "Syndicat InterCommunal pour l'Informatique et ses Outils (SICIO), "
            "EPCI créé en 1973 regroupant 5 communes du Val-de-Marne. "
            "Un syndicat intercommunal est une collectivité territoriale."
        ),
        "urls": [
            "https://www.sicio.fr/",
            "https://comersis.fr/epci.php?epci=259400117",
        ],
    },
    "unicancer achats": {
        "type_acheteur": "etablissement_public",
        "fonction_publique": "hospitaliere",
        "commentaire": (
            "UNICANCER est un groupement de coopération sanitaire (GCS) "
            "de droit privé à but non lucratif, fédération hospitalière "
            "des 18 Centres de lutte contre le cancer (CLCC). "
            "Classé comme EP hospitalier car GCS exerçant une mission de "
            "service public hospitalier."
        ),
        "urls": [
            "https://www.unicancer.fr/fr/groupe-unicancer/gouvernance/organisation/",
            "https://www.unicancer.fr/fr/groupe-unicancer/qui-sommes-nous/",
        ],
    },
    "parlement wallon": {
        "type_acheteur": "inconnu",
        "fonction_publique": "hors_fonction_publique",
        "commentaire": (
            "Institution parlementaire belge (Région wallonne), hors du "
            "périmètre de la fonction publique française. Pas classifiable "
            "dans la nomenclature française des acheteurs publics."
        ),
        "urls": [
            "https://fr.wikipedia.org/wiki/Parlement_wallon",
            "https://www.parlement-wallonie.be/",
        ],
    },
    "compagnie nationale du rhône": {
        "type_acheteur": "entreprise_privee",
        "fonction_publique": "hors_fonction_publique",
        "commentaire": (
            "SA d'intérêt général créée en 1933, concessionnaire de l'État "
            "pour l'aménagement du Rhône. Forme juridique : société anonyme "
            "(capital détenu par Engie, CDC, collectivités). Personne morale "
            "de droit privé."
        ),
        "urls": [
            "https://www.societe.com/societe/compagnie-nationale-du-rhone-957520901.html",
            "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000000413346",
        ],
    },
    "association asf vacances": {
        "type_acheteur": "organisme_prive_interet_general",
        "fonction_publique": "hors_fonction_publique",
        "commentaire": (
            "Association loi 1901 d'action sociale au profit des agents "
            "des ministères économiques et financiers. Qualifiée d'« organisme "
            "de droit public » dans ses avis BOAMP mais forme juridique = "
            "association. Classée organisme privé d'intérêt général."
        ),
        "urls": [
            "https://www.asfvacances.fr/vl/inscriptions",
            "https://www.marchesonline.com/appels-offres/avis/services-de-transport-par-autocar-pour-les-sejours-d-e/ao-9369463-1",
        ],
    },
    "gaz electricité de grenoble": {
        "type_acheteur": "entreprise_privee",
        "fonction_publique": "hors_fonction_publique",
        "commentaire": (
            "SEM locale (Société Anonyme d'Économie Mixte Locale), "
            "détenue majoritairement par la Ville de Grenoble. "
            "Personne morale de droit privé malgré l'actionnariat public."
        ),
        "urls": [
            "https://fr.wikipedia.org/wiki/Gaz_%C3%A9lectricit%C3%A9_de_Grenoble",
            "https://www.ccomptes.fr/fr/publications/societe-deconomie-mixte-gaz-et-electricite-de-grenoble-sem-geg-38",
        ],
    },
    "gaz electricite de grenoble": {  # variante sans accent
        "type_acheteur": "entreprise_privee",
        "fonction_publique": "hors_fonction_publique",
        "commentaire": (
            "SEM locale (Société Anonyme d'Économie Mixte Locale), "
            "détenue majoritairement par la Ville de Grenoble. "
            "Personne morale de droit privé malgré l'actionnariat public."
        ),
        "urls": [
            "https://fr.wikipedia.org/wiki/Gaz_%C3%A9lectricit%C3%A9_de_Grenoble",
            "https://www.ccomptes.fr/fr/publications/societe-deconomie-mixte-gaz-et-electricite-de-grenoble-sem-geg-38",
        ],
    },
    "spl semea": {
        "type_acheteur": "collectivite_territoriale",
        "fonction_publique": "territoriale",
        "commentaire": (
            "Société Publique Locale (SPL), détenue à 100% par des "
            "collectivités territoriales (GrandAngoulême et Ville d'Angoulême). "
            "Transformée de SEM en SPL en 2016. Les SPL agissent exclusivement "
            "pour le compte de leurs actionnaires publics territoriaux."
        ),
        "urls": [
            "https://www.semea.fr/le-service-public-de-l-eau/actualites/la-semea-societe-publique-locale,82.html",
            "https://www.lesepl.fr/annuaire-entreprises-publiques-locales/spl-semea/",
        ],
    },
    "resa innovation et technologie sa en son nom et pour compte de resa sa intercommunale": {
        "type_acheteur": "entreprise_privee",
        "fonction_publique": "hors_fonction_publique",
        "commentaire": (
            "SA de droit belge (n° BCE 0724.552.089), filiale de RESA SA "
            "(intercommunale wallonne gestionnaire de réseau de distribution). "
            "Entité de droit privé étranger, hors fonction publique française."
        ),
        "urls": [
            "https://data.be/fr/societe/Resa-Innovation-Et-Technologie-SA-0724552089",
            "https://fr.wikipedia.org/wiki/RESA",
        ],
    },
    "organisation qui passe un marché subventionné par un pouvoir adjudicateur": {
        "type_acheteur": "inconnu",
        "fonction_publique": "hors_fonction_publique",
        "commentaire": (
            "Libellé générique BOAMP utilisé quand l'acheteur est une entité "
            "privée bénéficiant d'une subvention publique > 50% pour passer "
            "un marché (art. L2100-1 CCP). L'entité réelle n'est pas "
            "identifiable dans les données disponibles."
        ),
        "urls": [],
    },
}


def enrich_row(row: dict) -> dict:
    """Enrichit une ligne si elle est dans la base de connaissances LLM."""
    acheteur_key = row["acheteur"].strip().lower()

    # Chercher une correspondance exacte ou partielle
    match = ACHETEUR_DB.get(acheteur_key)

    if not match:
        return row  # pas de modification

    # Ne modifier que les lignes encore « inconnu » ou « inconnue »
    ta_changed = False
    fp_changed = False

    if row["type_acheteur"] == "inconnu" and match["type_acheteur"] != "inconnu":
        row["type_acheteur"] = match["type_acheteur"]
        row["type_acheteur_source"] = "llm"
        ta_changed = True

    if row["fonction_publique"] in ("inconnue", "hors_fonction_publique"):
        if match["fonction_publique"] != row["fonction_publique"]:
            row["fonction_publique"] = match["fonction_publique"]
            row["fonction_publique_source"] = "llm"
            fp_changed = True

    # Ajouter le commentaire si on a touché quelque chose
    if ta_changed or fp_changed:
        urls_str = " ; ".join(match["urls"]) if match["urls"] else "N/A"
        row["classification_commentaire"] = f"{match['commentaire']} Sources: {urls_str}"
    else:
        row["classification_commentaire"] = ""

    return row


def main():
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        if "classification_commentaire" not in fieldnames:
            fieldnames.append("classification_commentaire")
        rows = list(reader)

    # Initialiser la colonne commentaire pour toutes les lignes
    for row in rows:
        if "classification_commentaire" not in row:
            row["classification_commentaire"] = ""

    # Enrichir
    enriched = [enrich_row(row) for row in rows]

    # Écrire
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched)

    # ── Rapport ────────────────────────────────────────────────────────────
    ta_llm = [r for r in enriched if r.get("type_acheteur_source") == "llm"]
    fp_llm = [r for r in enriched if r.get("fonction_publique_source") == "llm"]

    print(f"{'='*70}")
    print("RAPPORT D'ENRICHISSEMENT LLM (recherche web)")
    print(f"{'='*70}")
    print(f"Fichier source  : {INPUT_CSV}")
    print(f"Fichier produit : {OUTPUT_CSV}")
    print(f"Lignes totales  : {len(enriched)}")
    print()
    print(f"type_acheteur modifié par LLM     : {len(ta_llm)} / {len(enriched)}")
    print(f"fonction_publique modifié par LLM  : {len(fp_llm)} / {len(enriched)}")
    print()

    all_modified = [r for r in enriched if r.get("type_acheteur_source") == "llm"
                    or r.get("fonction_publique_source") == "llm"]
    if all_modified:
        print("Détail des modifications LLM :")
        print(f"{'-'*70}")
        for r in all_modified:
            print(f"  [{r['reference']}] {r['acheteur']}")
            print(f"    type_acheteur     = {r['type_acheteur']} (source={r['type_acheteur_source']})")
            print(f"    fonction_publique = {r['fonction_publique']} (source={r['fonction_publique_source']})")
            if r.get("classification_commentaire"):
                print(f"    commentaire: {r['classification_commentaire'][:120]}...")
            print()

    # Distribution finale
    from collections import Counter
    ta_dist = Counter(r["type_acheteur"] for r in enriched)
    fp_dist = Counter(r["fonction_publique"] for r in enriched)
    print("Distribution finale type_acheteur :")
    for k, v in sorted(ta_dist.items()):
        print(f"  {k}: {v}")
    print("\nDistribution finale fonction_publique :")
    for k, v in sorted(fp_dist.items()):
        print(f"  {k}: {v}")

    # Lignes encore inconnues
    still_unknown = [r for r in enriched
                     if r["type_acheteur"] == "inconnu" or r["fonction_publique"] == "inconnue"]
    print(f"\nLignes encore non classifiées : {len(still_unknown)}")
    for r in still_unknown:
        print(f"  [{r['reference']}] {r['acheteur']} → ta={r['type_acheteur']}, fp={r['fonction_publique']}")


if __name__ == "__main__":
    main()
