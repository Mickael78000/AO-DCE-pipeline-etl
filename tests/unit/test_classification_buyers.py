"""Tests unitaires et de non-régression pour ao_etl.classification.buyers.

Couvre :
- Contrat d'entrée strict (fichier manquant, colonnes manquantes)
- Protection écrasement (overwrite=False)
- Validation vocabulaire (type_acheteur, fonction_publique, *_source)
- Cas de régression critiques : classification déterministe stable
"""

import csv
import tempfile
from pathlib import Path

import pytest

from ao_etl.classification.buyers import (
    ALLOWED_FONCTION_PUBLIQUE,
    ALLOWED_SOURCE,
    ALLOWED_TYPE_ACHETEUR,
    REQUIRED_INPUT_COLUMNS,
    _COLUMNS_TO_STRIP,
    BuyerClassificationConfig,
    ClassificationInputError,
    _classify_row_rule,
    _norm,
    classify_buyers_rule_based,
    report_buyer_classification_quality,
    run_buyer_classification,
)


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

MINIMAL_FIELDNAMES = ["reference", "titre", "acheteur", "type_acheteur", "fonction_publique"]


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None):
    fn = fieldnames or MINIMAL_FIELDNAMES
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def sample_csv(tmp_path):
    """CSV minimal valide pour tests."""
    rows = [
        {"reference": "REF-001", "titre": "Marché test", "acheteur": "Ministère des Armées",
         "type_acheteur": "", "fonction_publique": ""},
        {"reference": "REF-002", "titre": "Marché CT", "acheteur": "Région Grand Est",
         "type_acheteur": "etat", "fonction_publique": "etat"},
    ]
    p = tmp_path / "input.csv"
    _write_csv(p, rows)
    return p


# ═══════════════════════════════════════════════════════════════════════════
# CONTRAT D'ENTRÉE
# ═══════════════════════════════════════════════════════════════════════════

class TestInputContract:

    def test_file_not_found(self, tmp_dir):
        with pytest.raises(ClassificationInputError, match="introuvable"):
            classify_buyers_rule_based(tmp_dir / "nope.csv", tmp_dir / "out.csv")

    def test_missing_columns(self, tmp_dir):
        p = tmp_dir / "bad.csv"
        with open(p, "w") as f:
            f.write("reference,titre\nREF,T\n")
        with pytest.raises(ClassificationInputError, match="acheteur"):
            classify_buyers_rule_based(p, tmp_dir / "out.csv")

    def test_valid_csv_accepted(self, sample_csv, tmp_dir):
        stats = classify_buyers_rule_based(sample_csv, tmp_dir / "out.csv")
        assert stats["total"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# CONTRAT DE SORTIE — OVERWRITE
# ═══════════════════════════════════════════════════════════════════════════

class TestOverwriteProtection:

    def test_overwrite_false_blocks(self, sample_csv, tmp_dir):
        out = tmp_dir / "out.csv"
        out.write_text("existing")
        with pytest.raises(FileExistsError, match="existe déjà"):
            classify_buyers_rule_based(sample_csv, out, overwrite=False)

    def test_overwrite_true_allows(self, sample_csv, tmp_dir):
        out = tmp_dir / "out.csv"
        out.write_text("existing")
        stats = classify_buyers_rule_based(sample_csv, out, overwrite=True)
        assert stats["total"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# VOCABULAIRE
# ═══════════════════════════════════════════════════════════════════════════

class TestVocabulary:

    def test_allowed_type_acheteur_is_frozenset(self):
        assert isinstance(ALLOWED_TYPE_ACHETEUR, frozenset)

    def test_allowed_fonction_publique_is_frozenset(self):
        assert isinstance(ALLOWED_FONCTION_PUBLIQUE, frozenset)

    def test_allowed_source_is_frozenset(self):
        assert isinstance(ALLOWED_SOURCE, frozenset)
        assert ALLOWED_SOURCE == {"original", "rule"}

    def test_qa_detects_bad_source(self, tmp_dir):
        rows = [
            {"reference": "REF-001", "titre": "T", "acheteur": "Test",
             "type_acheteur": "etat", "fonction_publique": "etat",
             "type_acheteur_source": "magic", "fonction_publique_source": "rule"},
        ]
        p = tmp_dir / "input.csv"
        fn = MINIMAL_FIELDNAMES + ["type_acheteur_source", "fonction_publique_source"]
        _write_csv(p, rows, fn)

        qa = report_buyer_classification_quality(p, bad_csv_path=tmp_dir / "bad.csv")
        assert qa.bad_count == 1
        assert "type_acheteur_source='magic'" in qa.bad_rows[0]["violation"]


# ═══════════════════════════════════════════════════════════════════════════
# RÉGRESSION : comportement identique Phase A et Phase B
# ═══════════════════════════════════════════════════════════════════════════

# Chaque tuple : (acheteur, type_acheteur attendu, fonction_publique attendue)
# Cas classés par RÈGLES uniquement (pas besoin de LLM)
REGRESSION_CASES = [
    ("Région Grand Est", "collectivite_territoriale", "territoriale"),
    ("Région Nouvelle-Aquitaine", "collectivite_territoriale", "territoriale"),
    ("Centre Hospitalier de l'Agglomération de Nevers", "etablissement_public", "hospitaliere"),
    ("CEA / DIF", "etablissement_public", "etat"),
    ("CNRS", "etablissement_public", "etat"),
    ("CNAF Établissement public", "etablissement_public", "etat"),
    ("EOESRI / SUPELEC - Centrale SUPELEC", "etablissement_public", "etat"),
    ("SHOM", "etablissement_public", "etat"),
    ("SPL SEMEA", "collectivite_territoriale", "territoriale"),
    ("Compagnie Nationale du Rhône", "inconnu", "hors_fonction_publique"),
]


class TestRegressionCases:
    """Vérifie que les 12 cas critiques restent stables.

    Si une règle future casse l'un de ces cas, le test échouera
    explicitement avec le nom de l'acheteur concerné.
    """

    @pytest.mark.parametrize("acheteur,expected_ta,expected_fp", REGRESSION_CASES,
                             ids=[c[0][:30] for c in REGRESSION_CASES])
    def test_deterministic_classification(self, acheteur, expected_ta, expected_fp):
        row = {
            "reference": "TEST",
            "titre": "test",
            "acheteur": acheteur,
            "type_acheteur": "",
            "fonction_publique": "",
        }
        result = _classify_row_rule(row)
        assert result["type_acheteur"] == expected_ta, (
            f"Régression type_acheteur pour '{acheteur}': "
            f"attendu='{expected_ta}', obtenu='{result['type_acheteur']}'"
        )
        assert result["fonction_publique"] == expected_fp, (
            f"Régression fonction_publique pour '{acheteur}': "
            f"attendu='{expected_fp}', obtenu='{result['fonction_publique']}'"
        )
        assert result["type_acheteur_source"] == "rule"
        assert result["fonction_publique_source"] == "rule"


# SICIO : non capturé par les règles, on teste juste que
# les règles ne le classent PAS à tort.
class TestSICIONotMisclassified:
    def test_sicio_remains_inconnu_by_rules(self):
        row = {
            "reference": "TEST",
            "titre": "test",
            "acheteur": "SICIO",
            "type_acheteur": "",
            "fonction_publique": "",
        }
        result = _classify_row_rule(row)
        assert result["type_acheteur"] == "inconnu"


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════════════

class TestOrchestration:

    def test_rule_only_pipeline(self, sample_csv, tmp_dir):
        config = BuyerClassificationConfig(enabled=True)
        stats = run_buyer_classification(sample_csv, config)
        assert stats["rule_stats"]["total"] == 2
        assert stats["qa"]["bad_count"] == 0
        assert Path(stats["output_csv"]).is_file()

    def test_canonical_output_naming(self, sample_csv, tmp_dir):
        config = BuyerClassificationConfig(enabled=True)
        stats = run_buyer_classification(sample_csv, config)
        out = Path(stats["output_csv"])
        assert out.name == "input-classified-rule.csv"


# ═══════════════════════════════════════════════════════════════════════════
# SCHÉMA FINAL DU CSV
# ═══════════════════════════════════════════════════════════════════════════

class TestFinalSchema:
    """Vérifie que le CSV final ne contient pas les colonnes internes."""

    def test_final_csv_no_internal_columns(self, sample_csv, tmp_dir):
        config = BuyerClassificationConfig(enabled=True)
        stats = run_buyer_classification(sample_csv, config)
        final = Path(stats["output_csv"])
        with open(final, newline="", encoding="utf-8") as f:
            cols = set(csv.DictReader(f).fieldnames)
        for col in _COLUMNS_TO_STRIP:
            assert col not in cols, f"Colonne interne '{col}' encore présente dans le CSV final"
        # Colonnes métier obligatoires
        assert "type_acheteur" in cols
        assert "fonction_publique" in cols

    def test_final_csv_no_internal_columns_extra(self, tmp_dir):
        rows = [
            {"reference": "R", "titre": "T", "acheteur": "Acme",
             "type_acheteur": "inconnu", "fonction_publique": "inconnue",
             "sous_type_fonction_publique": "detail", "procedure_label": "Ouvert"},
        ]
        p = tmp_dir / "with-extra.csv"
        fn = MINIMAL_FIELDNAMES + ["sous_type_fonction_publique", "procedure_label"]
        _write_csv(p, rows, fn)
        config = BuyerClassificationConfig(enabled=True)
        stats = run_buyer_classification(p, config)
        assert Path(stats["output_csv"]).is_file()
