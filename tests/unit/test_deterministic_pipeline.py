"""Tests de non-régression — pipeline strictement déterministe.

Vérifie que :
1. la taxonomie Fonction publique est respectée ;
2. les fallbacks non contractuels sont morts ;
3. validate_and_fix_row est idempotente ;
4. le pipeline nominal produit un CSV valide sur un mini corpus.

Règle absolue : aucun test ne doit dépendre du réseau.
"""

import csv
import tempfile
from pathlib import Path

import pytest

from ao_etl.pipeline.normalize_final_phase import run_normalize_phase
from ao_etl.normalize_fields import (
    ALLOWED_FONCTION_PUBLIQUE,
    normalize_fonction_publique,
    normalize_type_ao,
    normalize_type_marche,
    validate_and_fix_row,
)


# =============================================================================
# 1. TAXONOMIE Fonction publique
# =============================================================================

class TestFonctionPubliqueTaxonomy:
    """Toute valeur doit sortir dans {etat, territoriale, hospitaliere, -}."""

    VALID = {"etat", "territoriale", "hospitaliere", "-"}

    @pytest.mark.parametrize("val,expected", [
        ("etat",                     "etat"),
        ("Etat",                     "etat"),
        ("État",                     "etat"),
        ("territoriale",             "territoriale"),
        ("Territoriale",             "territoriale"),
        ("hospitaliere",             "hospitaliere"),
        ("Hospitalière",             "hospitaliere"),
        ("Hospitaliere",             "hospitaliere"),
        ("-",                        "-"),
        ("",                         "-"),
        ("hors_fonction_publique",   "-"),
        ("inconnue",                 "-"),
        ("inconnu",                  "-"),
        ("Quelque chose d'inconnu",  "-"),
        # libellés JOUE bruts
        ("Loisirs, culture et culte",               "etat"),
        ("Services d'administration générale",      "etat"),
        ("Autorité publique centrale",              "etat"),
        ("Organisme de droit public",               "etat"),
        ("Autorité locale",                         "territoriale"),
        ("Protection sociale",                      "territoriale"),
        ("Santé",                                   "hospitaliere"),
        ("Protection de l'environnement",           "etat"),
    ])
    def test_normalize_fonction_publique(self, val, expected):
        result = normalize_fonction_publique(val)
        assert result == expected, f"normalize_fonction_publique({val!r}) = {result!r}, attendu {expected!r}"
        assert result in self.VALID

    def test_all_outputs_in_taxonomy(self):
        inputs = [
            "etat", "Etat", "État", "territoriale", "Territoriale",
            "hospitaliere", "Hospitalière", "hors_fonction_publique",
            "inconnue", "inconnu", "", "-", "random garbage", "42",
        ]
        for val in inputs:
            result = normalize_fonction_publique(val)
            assert result in self.VALID, f"Valeur hors taxonomie: {result!r} (entrée: {val!r})"


# =============================================================================
# 3. STABILITÉ DU MAPPING — fallbacks supprimés
# =============================================================================

class TestMappingStability:
    """Les fallbacks non contractuels ne doivent plus écrire dans les colonnes finales."""

    def test_type_ao_ignores_legacy_type_ao_field(self):
        from ao_etl.pipeline.normalize_final_phase import normalize_row
        row = {
            "Type d'AO": "-",
            "type_ao": "Appel d'offres ouvert (résidu LLM)",
            "procedure_type": "",
        }
        normalize_row(row)
        assert row["Type d'AO"] == "-", \
            "type_ao (résidu LLM) ne doit jamais alimenter Type d'AO"

    def test_type_ao_uses_procedure_type(self):
        from ao_etl.pipeline.normalize_final_phase import normalize_row
        row = {
            "Type d'AO": "-",
            "type_ao": "résidu LLM ne doit pas passer",
            "procedure_type": "Ouverte",
        }
        normalize_row(row)
        assert row["Type d'AO"] == "Ouverte"

    def test_type_not_deduced_from_lot_objet(self):
        # Si le fallback lot→Type était encore présent, il écrirait le libellé du lot.
        # On vérifie que normalize_type_marche rejette un libellé de lot libre.
        lot_objet = "Fourniture et installation de mobilier de bureau ergonomique"
        result = normalize_type_marche(lot_objet)
        assert result == "Fournitures", \
            "Un libellé de lot contenant 'Fourniture' doit mapper vers 'Fournitures' via taxonomie"

        random_lot = "Prestation de conseil en stratégie numérique"
        result2 = normalize_type_marche(random_lot)
        assert result2 == "-", \
            f"Un libellé de lot ambigu doit donner '-', pas {result2!r}"

    def test_fonction_publique_not_left_raw(self):
        row = {
            "Fonction publique": "Loisirs, culture et culte",
            "Type d'AO": "Ouverte",
            "Type": "Services",
        }
        validate_and_fix_row(row)
        assert row["Fonction publique"] in ALLOWED_FONCTION_PUBLIQUE, \
            "Une valeur JOUE brute doit être normalisée par validate_and_fix_row"

    def test_hors_fp_becomes_dash(self):
        row = {
            "Fonction publique": "hors_fonction_publique",
            "Type d'AO": "-",
            "Type": "-",
        }
        validate_and_fix_row(row)
        assert row["Fonction publique"] == "-"

    def test_inconnue_becomes_dash(self):
        row = {
            "Fonction publique": "inconnue",
            "Type d'AO": "-",
            "Type": "-",
        }
        validate_and_fix_row(row)
        assert row["Fonction publique"] == "-"


# =============================================================================
# 4. NORMALISATION CENTRALE — idempotence et corrections
# =============================================================================

class TestNormalizeFieldsIdempotence:
    """validate_and_fix_row doit être idempotente et corriger les variantes."""

    @pytest.mark.parametrize("fp_in,fp_expected", [
        ("Etat",                   "etat"),
        ("État",                   "etat"),
        ("Hospitalière",           "hospitaliere"),
        ("hors_fonction_publique", "-"),
        ("inconnue",               "-"),
        ("etat",                   "etat"),
        ("-",                      "-"),
    ])
    def test_normalize_fp_corrections(self, fp_in, fp_expected):
        row = {"Fonction publique": fp_in, "Type d'AO": "-", "Type": "-"}
        validate_and_fix_row(row)
        assert row["Fonction publique"] == fp_expected

    def test_idempotent_single_pass(self):
        rows = [
            {"Fonction publique": "Etat",                   "Type d'AO": "Ouverte",           "Type": "Services"},
            {"Fonction publique": "Hospitalière",            "Type d'AO": "procédure adaptée", "Type": "Fournitures"},
            {"Fonction publique": "hors_fonction_publique",  "Type d'AO": "-",                 "Type": "-"},
            {"Fonction publique": "etat",                   "Type d'AO": "MAPA",              "Type": "Travaux"},
        ]
        for row in rows:
            r1 = dict(row)
            validate_and_fix_row(r1)
            r2 = dict(r1)
            validate_and_fix_row(r2)
            assert r1 == r2, f"validate_and_fix_row n'est pas idempotente sur {row}"

    def test_valid_values_unchanged(self):
        row = {"Fonction publique": "etat", "Type d'AO": "MAPA", "Type": "Services"}
        original = dict(row)
        validate_and_fix_row(row)
        assert row == {"Fonction publique": "etat", "Type d'AO": "MAPA", "Type": "Services"}

    def test_does_not_touch_other_columns(self):
        row = {
            "Fonction publique": "etat",
            "Type d'AO": "-",
            "Type": "-",
            "Référence": "TEST-001",
            "Acheteur": "Ministère test",
            "some_other": "preserved",
        }
        validate_and_fix_row(row)
        assert row["Référence"] == "TEST-001"
        assert row["Acheteur"] == "Ministère test"
        assert row["some_other"] == "preserved"


# =============================================================================
# 5. PIPELINE NOMINAL — mini corpus
# =============================================================================

_MINI_CSV_ROWS = [
    {
        "Référence": "TEST-ETAT-001",
        "Intitulé synthétique": "Marché DSI Ministère",
        "Type d'AO": "MAPA",
        "Type": "Services",
        "Fonction publique": "etat",
        "Acheteur_auto": "Ministère de l'Intérieur",
        "Acheteur_manual": "",
        "Acheteur": "Ministère de l'Intérieur",
        "Acheteur_clean": "Ministère de l'Intérieur",
        "Localisation_auto": "Paris",
        "Localisation_manual": "",
        "Localisation": "Paris",
        "Localisation_clean": "Paris",
        "Date_limite_auto": "30/06/2026",
        "Date_limite_manual": "",
        "Date limite de remise des offres": "30/06/2026",
        "Durée initiale du marché": "12 mois",
        "Reconduction(s)": "-",
        "Estimation_auto": "50000",
        "Estimation_manual": "",
        "Estimation du marché": "50000",
        "URL source HTTPS": "https://www.boamp.fr/avis/detail/123",
        "Plateforme": "BOAMP",
        "match_status": "existing",
        "match_source": "test-etat.html",
        "review_needed": "",
        "extraction_notes": "test",
    },
    {
        "Référence": "TEST-TERR-002",
        "Intitulé synthétique": "Voirie Commune",
        "Type d'AO": "AOO",
        "Type": "Travaux",
        "Fonction publique": "Territoriale",  # variante à normaliser
        "Acheteur_auto": "Commune de Lyon",
        "Acheteur_manual": "",
        "Acheteur": "Commune de Lyon",
        "Acheteur_clean": "Commune de Lyon",
        "Localisation_auto": "Lyon (69)",
        "Localisation_manual": "",
        "Localisation": "Lyon (69)",
        "Localisation_clean": "Lyon (69)",
        "Date_limite_auto": "15/07/2026",
        "Date_limite_manual": "",
        "Date limite de remise des offres": "15/07/2026",
        "Durée initiale du marché": "6 mois",
        "Reconduction(s)": "-",
        "Estimation_auto": "200000",
        "Estimation_manual": "",
        "Estimation du marché": "200000",
        "URL source HTTPS": "https://www.boamp.fr/avis/detail/456",
        "Plateforme": "BOAMP",
        "match_status": "existing",
        "match_source": "test-terr.html",
        "review_needed": "",
        "extraction_notes": "test",
    },
    {
        "Référence": "TEST-HOSP-003",
        "Intitulé synthétique": "Matériel médical CHU",
        "Type d'AO": "AOO",
        "Type": "Fournitures",
        "Fonction publique": "Hospitalière",  # variante accentuée à normaliser
        "Acheteur_auto": "CHU de Bordeaux",
        "Acheteur_manual": "",
        "Acheteur": "CHU de Bordeaux",
        "Acheteur_clean": "CHU de Bordeaux",
        "Localisation_auto": "Bordeaux (33)",
        "Localisation_manual": "",
        "Localisation": "Bordeaux (33)",
        "Localisation_clean": "Bordeaux (33)",
        "Date_limite_auto": "01/08/2026",
        "Date_limite_manual": "",
        "Date limite de remise des offres": "01/08/2026",
        "Durée initiale du marché": "24 mois",
        "Reconduction(s)": "1",
        "Estimation_auto": "500000",
        "Estimation_manual": "",
        "Estimation du marché": "500000",
        "URL source HTTPS": "https://www.boamp.fr/avis/detail/789",
        "Plateforme": "BOAMP",
        "match_status": "existing",
        "match_source": "test-hosp.html",
        "review_needed": "",
        "extraction_notes": "test",
    },
    {
        "Référence": "TEST-AMBIGU-004",
        "Intitulé synthétique": "Prestations diverses",
        "Type d'AO": "-",
        "Type": "-",
        "Fonction publique": "hors_fonction_publique",  # doit devenir "-"
        "Acheteur_auto": "Association XYZ",
        "Acheteur_manual": "",
        "Acheteur": "Association XYZ",
        "Acheteur_clean": "Association XYZ",
        "Localisation_auto": "-",
        "Localisation_manual": "",
        "Localisation": "-",
        "Localisation_clean": "-",
        "Date_limite_auto": "-",
        "Date_limite_manual": "",
        "Date limite de remise des offres": "-",
        "Durée initiale du marché": "-",
        "Reconduction(s)": "-",
        "Estimation_auto": "-",
        "Estimation_manual": "",
        "Estimation du marché": "-",
        "URL source HTTPS": "-",
        "Plateforme": "-",
        "match_status": "existing",
        "match_source": "test-ambigu.html",
        "review_needed": "oui",
        "extraction_notes": "test",
    },
]

_FIELDNAMES = list(_MINI_CSV_ROWS[0].keys())


def _write_mini_csv(path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        w.writeheader()
        w.writerows(_MINI_CSV_ROWS)


class TestNominalPipelineMiniCorpus:
    """Pipeline minimal sur 4 lignes représentatives — sans LLM."""

    def test_normalize_phase_on_mini_csv(self, tmp_path):
        from ao_etl.pipeline.normalize_final_phase import run_normalize_phase

        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"
        _write_mini_csv(input_csv)

        stats = run_normalize_phase(input_csv, output_csv)

        assert output_csv.exists()
        assert stats["total_rows"] == 4
        assert not stats["errors"], f"Erreurs inattendues: {stats['errors']}"

        with open(output_csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 4

        for row in rows:
            fp = row.get("Fonction publique", "")
            assert fp in ALLOWED_FONCTION_PUBLIQUE, \
                f"Ref {row.get('Référence')}: Fonction publique={fp!r} hors taxonomie"

    def test_normalize_phase_fixes_variantes(self, tmp_path):
        from ao_etl.pipeline.normalize_final_phase import run_normalize_phase

        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"
        _write_mini_csv(input_csv)

        run_normalize_phase(input_csv, output_csv)

        with open(output_csv, newline="", encoding="utf-8") as f:
            rows = {r["Référence"]: r for r in csv.DictReader(f)}

        assert rows["TEST-TERR-002"]["Fonction publique"] == "territoriale"
        assert rows["TEST-HOSP-003"]["Fonction publique"] == "hospitaliere"
        assert rows["TEST-AMBIGU-004"]["Fonction publique"] == "-"
        assert rows["TEST-ETAT-001"]["Fonction publique"] == "etat"

    def test_no_llm_error_on_nominal_path(self, tmp_path):
        from ao_etl.pipeline.normalize_final_phase import run_normalize_phase

        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"
        _write_mini_csv(input_csv)

        try:
            run_normalize_phase(input_csv, output_csv)
        except LLMDisabledError:
            pytest.fail("LLMDisabledError levée sur le chemin nominal — régression détectée")

    def test_required_columns_present(self, tmp_path):
        from ao_etl.pipeline.normalize_final_phase import run_normalize_phase

        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"
        _write_mini_csv(input_csv)
        run_normalize_phase(input_csv, output_csv)

        with open(output_csv, newline="", encoding="utf-8") as f:
            fieldnames = csv.DictReader(f).fieldnames or []

        required = ["Référence", "Type d'AO", "Type", "Fonction publique",
                    "URL source HTTPS", "Acheteur"]
        for col in required:
            assert col in fieldnames, f"Colonne requise absente du CSV final: {col!r}"

    def test_normalize_produces_canonical_columns(self, tmp_path):
        """normalize_final_phase doit produire les colonnes canoniques minuscules
        attendues par classify_buyers et excel_export."""
        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        with open(input_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "Référence", "Intitulé synthétique", "Acheteur_clean",
                "Acheteur_auto", "Fonction publique",
                "Date limite de remise des offres", "URL source HTTPS",
                "Plateforme", "Type d'AO", "Type",
            ])
            w.writeheader()
            w.writerow({
                "Référence": "REF-001",
                "Intitulé synthétique": "Test marché",
                "Acheteur_clean": "Mairie de Test",
                "Acheteur_auto": "",
                "Fonction publique": "territoriale",
                "Date limite de remise des offres": "2026-06-01",
                "URL source HTTPS": "https://example.com",
                "Plateforme": "FRANCE_MARCHES",
                "Type d'AO": "Ouverte",
                "Type": "Services",
            })

        run_normalize_phase(input_csv, output_csv)

        with open(output_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        canonical = ["reference", "titre", "acheteur", "type_acheteur",
                     "fonction_publique", "date_limite_remise_offres",
                     "url_marche", "plateforme_source"]
        for col in canonical:
            assert col in fieldnames, f"Colonne canonique absente: {col!r}"

        row = rows[0]
        assert row["reference"] == "REF-001"
        assert row["titre"] == "Test marché"
        assert row["acheteur"] == "Mairie de Test"
        assert row["fonction_publique"] == "territoriale"
        assert row["type_acheteur"] == "-"
