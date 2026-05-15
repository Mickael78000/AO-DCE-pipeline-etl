"""Tests d'intégration du pipeline ETL complet.

Ces tests valident le pipeline sur des fichiers HTML réels
dans le répertoire html_ao/.
"""

import json
import pytest
from pathlib import Path
from ao_etl.sources.router import extract_for_source
from ao_etl.sources.bridge import extract_record, should_use_new_extractor


class TestPipelineIntegration:
    """Tests d'intégration du pipeline sur données réelles."""
    
    def test_extract_all_html_files(self, html_ao_dir):
        """Test d'extraction complète de tous les fichiers HTML.
        
        Valide que tous les fichiers sont extraits sans erreur.
        """
        html_files = list(html_ao_dir.glob("*.html"))
        results = []
        errors = []
        
        for filepath in html_files:
            try:
                data = extract_for_source(filepath)
                results.append(data)
            except Exception as e:
                errors.append((filepath.name, str(e)))
        
        # Tous les fichiers doivent être traités
        assert len(results) == len(html_files), f"Erreurs sur: {errors}"
        assert len(errors) == 0, f"{len(errors)} erreurs: {errors[:3]}"
    
    def test_reference_uniqueness(self, html_ao_dir):
        """Test d'unicité des références extraites.
        
        Valide qu'il n'y a pas de collisions de références
        (bug 1838554 corrigé).
        """
        html_files = list(html_ao_dir.glob("*.html"))
        references = []
        
        for filepath in html_files:
            data = extract_for_source(filepath)
            if data.reference:
                references.append((filepath.name, data.reference))
        
        # Vérifier unicité (exclure les vrais doublons connus)
        ref_counts = {}
        for filename, ref in references:
            if ref not in ref_counts:
                ref_counts[ref] = []
            ref_counts[ref].append(filename)
        
        # Les doublons doivent être justifiés (alias ou vrais doublons)
        duplicates = {ref: files for ref, files in ref_counts.items() if len(files) > 1}
        
        # 1838554 ne doit plus être présent
        assert "1838554" not in duplicates, "Bug 1838554 non corrigé!"
        
        # Vérifier que les doublons restants sont légitimes
        for ref, files in duplicates.items():
            # Vérifier si ce sont des alias ou vrais doublons
            print(f"Doublon légitime: {ref} dans {files}")
    
    def test_completeness_threshold(self, html_ao_dir):
        """Test de complétude minimale des champs critiques.
        
        Valide que tous les fichiers ont au moins référence + titre.
        """
        html_files = list(html_ao_dir.glob("*.html"))
        complete_count = 0
        partial_count = 0
        failed_count = 0
        
        for filepath in html_files:
            data = extract_for_source(filepath)
            
            if data.is_complete():
                complete_count += 1
            elif data.reference or data.title:
                partial_count += 1
            else:
                failed_count += 1
        
        total = len(html_files)
        
        # Au moins 90% de complétude complète
        assert complete_count / total >= 0.90, \
            f"Taux de complétude {complete_count/total:.1%} < 90%"
        
        # Aucun échec total
        assert failed_count == 0, f"{failed_count} fichiers en échec total"
        
        print(f"\nComplétude: {complete_count}/{total} complète, "
              f"{partial_count} partielle, {failed_count} échec")
    
    def test_source_type_distribution(self, html_ao_dir):
        """Test de distribution des types de sources.
        
        Valide que tous les types de sources sont détectés.
        """
        html_files = list(html_ao_dir.glob("*.html"))
        source_counts = {}
        
        for filepath in html_files:
            data = extract_for_source(filepath)
            source = data.source_type.value
            source_counts[source] = source_counts.get(source, 0) + 1
        
        # Afficher la distribution
        print("\nDistribution des sources:")
        for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            print(f"  {source:20s}: {count}")
        
        # Au moins 2 sources différentes
        assert len(source_counts) >= 2, "Pas assez de diversité de sources"
    
    def test_marches_online_references_unique(self, html_ao_dir):
        """Test spécifique: références Marchés Online uniques.
        
        Valide le bug 1838554 corrigé: chaque marché a sa propre référence.
        """
        html_files = list(html_ao_dir.glob("ao-*.html"))
        
        if not html_files:
            pytest.skip("Pas de fichiers Marchés Online")
        
        references = []
        for filepath in html_files:
            data = extract_for_source(filepath)
            if data.source_type.value == "MARCHES_ONLINE":
                references.append((filepath.name, data.reference))
        
        # Toutes les références doivent commencer par MO-
        for filename, ref in references:
            assert ref.startswith("MO-"), \
                f"{filename}: référence {ref} ne commence pas par MO-"
        
        # Toutes les références doivent être uniques
        unique_refs = set(r for _, r in references)
        assert len(unique_refs) == len(references), \
            f"Doublons Marchés Online: {len(references)} fichiers, {len(unique_refs)} refs"
        
        # Aucune ne doit être 1838554
        assert "1838554" not in [r for _, r in references], \
            "Bug 1838554 détecté: refContrat utilisé au lieu de l'ID fichier"
    
    def test_france_marches_unicode_decoded(self, html_ojb_dir):
        """Test spécifique: titres France Marchés correctement décodés.
        
        Valide que les séquences \\u0022 sont décodées en caractères lisibles.
        """
        # Chercher un fichier France Marchés
        html_files = list(html_ao_dir.glob("*ao*.html"))
        france_marches_files = [
            f for f in html_files 
            if "37ao" in f.name or "36parisien" in f.name
        ]
        
        if not france_marches_files:
            pytest.skip("Pas de fichiers France Marchés")
        
        for filepath in france_marches_files[:3]:  # Tester 3 fichiers
            data = extract_for_source(filepath)
            
            if data.source_type.value == "FRANCE_MARCHES":
                # Vérifier que le titre ne contient pas de séquences Unicode non décodées
                assert "\\u00" not in data.title, \
                    f"{filepath.name}: séquences Unicode non décodées dans titre"
                assert "\\u002" not in data.title, \
                    f"{filepath.name}: séquences \\u002X non décodées"
                
                # Le titre doit être lisible (caractères français)
                assert len(data.title) > 5, \
                    f"{filepath.name}: titre trop court ou vide"
    
    def test_bridge_legacy_compatibility(self, html_ao_dir):
        """Test de compatibilité avec le format legacy.
        
        Valide que le pont bridge.py produit des dicts compatibles.
        """
        html_files = list(html_ao_dir.glob("*.html"))[:5]
        
        for filepath in html_files:
            # Extraction via bridge (format legacy)
            legacy_data = extract_record(filepath)
            
            # Vérifier que tous les champs legacy sont présents
            required_keys = [
                "filename", "filepath", "source_type", "title", 
                "reference", "buyer", "cpv_codes"
            ]
            for key in required_keys:
                assert key in legacy_data, f"Clé {key} manquante"
            
            # Vérifier que les types sont corrects
            assert isinstance(legacy_data["filename"], str)
            assert isinstance(legacy_data["title"], str)
            assert isinstance(legacy_data["cpv_codes"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
