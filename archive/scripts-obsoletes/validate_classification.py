#!/usr/bin/env python3
"""
Validation du vocabulaire et rapport de contrôle qualité
pour la classification type_acheteur / fonction_publique.

Sous-tâches :
1. Vérification vocabulaire fermé → CSV d'anomalies si violations.
2. Rapport QA synthétique → Markdown.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ── Chemins ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent / "data" / "output"
INPUT_CSV = BASE_DIR / "final-v3-consolidated-classified-llm.csv"
BAD_CSV = BASE_DIR / "final-v3-bad_classification.csv"
REPORT_MD = BASE_DIR / "report-buyer-classification-quality.md"

# ── Vocabulaire autorisé ────────────────────────────────────────────────────
ALLOWED_TYPE_ACHETEUR = frozenset([
    "etat",
    "collectivite_territoriale",
    "etablissement_public",
    "entreprise_privee",
    "organisme_prive_interet_general",
    "inconnu",
])

ALLOWED_FONCTION_PUBLIQUE = frozenset([
    "etat",
    "territoriale",
    "hospitaliere",
    "hors_fonction_publique",
    "inconnue",
])


# ── 1. Vérification de vocabulaire ─────────────────────────────────────────

def validate_vocabulary(df: pd.DataFrame) -> pd.DataFrame:
    """Retourne un DataFrame des lignes hors vocabulaire autorisé."""
    bad_ta = ~df["type_acheteur"].isin(ALLOWED_TYPE_ACHETEUR)
    bad_fp = ~df["fonction_publique"].isin(ALLOWED_FONCTION_PUBLIQUE)
    bad_mask = bad_ta | bad_fp

    bad_df = df[bad_mask].copy()
    bad_df["violation"] = ""

    for idx in bad_df.index:
        reasons = []
        ta = df.at[idx, "type_acheteur"]
        fp = df.at[idx, "fonction_publique"]
        if ta not in ALLOWED_TYPE_ACHETEUR:
            reasons.append(f"type_acheteur='{ta}' hors vocabulaire")
        if fp not in ALLOWED_FONCTION_PUBLIQUE:
            reasons.append(f"fonction_publique='{fp}' hors vocabulaire")
        bad_df.at[idx, "violation"] = " ; ".join(reasons)

    return bad_df


# ── 2. Rapport QA ──────────────────────────────────────────────────────────

def report_buyer_classification_quality(csv_path: Path) -> str:
    """Génère un rapport Markdown de contrôle qualité et le retourne."""

    df = pd.read_csv(csv_path, dtype=str).fillna("")
    n = len(df)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = []
    lines.append(f"# Rapport de contrôle qualité — Classification acheteurs")
    lines.append(f"")
    lines.append(f"- **Date** : {now}")
    lines.append(f"- **Fichier source** : `{csv_path.name}`")
    lines.append(f"- **Lignes totales** : {n}")
    lines.append(f"")

    # ── Validation vocabulaire ──────────────────────────────────────────
    bad_df = validate_vocabulary(df)
    lines.append(f"## 1. Validation du vocabulaire")
    lines.append(f"")
    if len(bad_df) == 0:
        lines.append(f"✅ **Aucune violation** — toutes les valeurs de `type_acheteur` et "
                      f"`fonction_publique` appartiennent au vocabulaire autorisé.")
    else:
        lines.append(f"⚠️ **{len(bad_df)} ligne(s) hors vocabulaire** — écrites dans "
                      f"`{BAD_CSV.name}`.")
        lines.append(f"")
        lines.append(f"| reference | acheteur | violation |")
        lines.append(f"|---|---|---|")
        for _, row in bad_df.iterrows():
            lines.append(f"| {row['reference']} | {row['acheteur'][:50]} | {row['violation']} |")
        # Écrire le CSV d'anomalies
        bad_df.to_csv(BAD_CSV, index=False)
    lines.append(f"")

    # ── Distribution type_acheteur ──────────────────────────────────────
    lines.append(f"## 2. Distribution `type_acheteur`")
    lines.append(f"")
    ta_dist = df["type_acheteur"].value_counts().sort_index()
    lines.append(f"| type_acheteur | count | % |")
    lines.append(f"|---|---:|---:|")
    for val, cnt in ta_dist.items():
        lines.append(f"| {val} | {cnt} | {cnt/n*100:.1f}% |")
    lines.append(f"")

    # ── Distribution fonction_publique ──────────────────────────────────
    lines.append(f"## 3. Distribution `fonction_publique`")
    lines.append(f"")
    fp_dist = df["fonction_publique"].value_counts().sort_index()
    lines.append(f"| fonction_publique | count | % |")
    lines.append(f"|---|---:|---:|")
    for val, cnt in fp_dist.items():
        lines.append(f"| {val} | {cnt} | {cnt/n*100:.1f}% |")
    lines.append(f"")

    # ── Distribution des sources ────────────────────────────────────────
    lines.append(f"## 4. Sources de classification")
    lines.append(f"")

    if "type_acheteur_source" in df.columns:
        lines.append(f"### `type_acheteur_source`")
        lines.append(f"")
        ta_src = df["type_acheteur_source"].value_counts().sort_index()
        lines.append(f"| source | count | % |")
        lines.append(f"|---|---:|---:|")
        for val, cnt in ta_src.items():
            lines.append(f"| {val} | {cnt} | {cnt/n*100:.1f}% |")
        lines.append(f"")

    if "fonction_publique_source" in df.columns:
        lines.append(f"### `fonction_publique_source`")
        lines.append(f"")
        fp_src = df["fonction_publique_source"].value_counts().sort_index()
        lines.append(f"| source | count | % |")
        lines.append(f"|---|---:|---:|")
        for val, cnt in fp_src.items():
            lines.append(f"| {val} | {cnt} | {cnt/n*100:.1f}% |")
        lines.append(f"")

    # ── Cas à surveiller ────────────────────────────────────────────────
    lines.append(f"## 5. Cas à surveiller")
    lines.append(f"")

    unknowns_ta = df[df["type_acheteur"] == "inconnu"]
    unknowns_fp = df[df["fonction_publique"] == "inconnue"]

    lines.append(f"### `type_acheteur = \"inconnu\"` ({len(unknowns_ta)} ligne(s))")
    lines.append(f"")
    if len(unknowns_ta) == 0:
        lines.append(f"Aucune.")
    else:
        lines.append(f"| reference | acheteur | fp | ta_source |")
        lines.append(f"|---|---|---|---|")
        for _, row in unknowns_ta.iterrows():
            lines.append(f"| {row['reference']} | {row['acheteur'][:60]} "
                         f"| {row['fonction_publique']} | {row.get('type_acheteur_source','')} |")
    lines.append(f"")

    lines.append(f"### `fonction_publique = \"inconnue\"` ({len(unknowns_fp)} ligne(s))")
    lines.append(f"")
    if len(unknowns_fp) == 0:
        lines.append(f"Aucune.")
    else:
        lines.append(f"| reference | acheteur | ta | fp_source |")
        lines.append(f"|---|---|---|---|")
        for _, row in unknowns_fp.iterrows():
            lines.append(f"| {row['reference']} | {row['acheteur'][:60]} "
                         f"| {row['type_acheteur']} | {row.get('fonction_publique_source','')} |")
    lines.append(f"")

    # ── Anomalies depuis bad CSV ────────────────────────────────────────
    lines.append(f"### Lignes hors vocabulaire")
    lines.append(f"")
    if len(bad_df) == 0:
        lines.append(f"Aucune — le fichier `{BAD_CSV.name}` n'a pas été créé.")
    else:
        lines.append(f"Voir `{BAD_CSV.name}` ({len(bad_df)} ligne(s)).")
    lines.append(f"")

    # ── Matrice croisée ─────────────────────────────────────────────────
    lines.append(f"## 6. Matrice croisée type_acheteur × fonction_publique")
    lines.append(f"")
    cross = pd.crosstab(df["type_acheteur"], df["fonction_publique"], margins=True)
    lines.append(cross.to_markdown())
    lines.append(f"")

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if not INPUT_CSV.exists():
        print(f"ERREUR: {INPUT_CSV} introuvable.", file=sys.stderr)
        sys.exit(1)

    report = report_buyer_classification_quality(INPUT_CSV)

    # Écrire le rapport
    REPORT_MD.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n{'='*70}")
    print(f"Rapport écrit dans : {REPORT_MD}")

    # Résumé bad CSV
    if BAD_CSV.exists():
        bad = pd.read_csv(BAD_CSV)
        print(f"CSV d'anomalies    : {BAD_CSV} ({len(bad)} lignes)")
    else:
        print(f"CSV d'anomalies    : aucune anomalie détectée, fichier non créé.")


if __name__ == "__main__":
    main()
