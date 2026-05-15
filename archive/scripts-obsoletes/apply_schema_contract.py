#!/usr/bin/env python3
"""
Script d'application stricte du contrat de colonnes canonique.

Garantit que chaque génération de CSV respecte exactement le schéma figé :
- CSV métier : 14 colonnes dans l'ordre canonique
- CSV audit : colonnes obligatoires + optionnelles selon le contrat

Auteur: Pipeline AO-DCE
Version: 1.0 — 14 mai 2026
"""

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum


class NiveauAlerte(Enum):
    """Niveaux d'alerte pour les écarts au contrat."""
    INFO = "info"
    AVERTISSEMENT = "avertissement"
    ERREUR = "erreur"
    BLOQUANT = "bloquant"


@dataclass
class EcartContrat:
    """Représente un écart détecté par rapport au contrat."""
    type_ecart: str  # 'colonne_inconnue', 'colonne_manquante', 'ordre_incorrect', 'type_incompatible'
    colonne: str
    niveau: NiveauAlerte
    message: str
    action: str  # 'ignore', 'ajoute', 'reordonne', 'bloque'


@dataclass
class RapportConformite:
    """Rapport complet de conformité au contrat."""
    version_contrat: str
    lignes_traitees: int = 0
    ecarts: List[EcartContrat] = field(default_factory=list)
    colonnes_conformes: List[str] = field(default_factory=list)
    colonnes_manquantes_creees: List[str] = field(default_factory=list)
    colonnes_inconnues_ignorees: List[str] = field(default_factory=list)
    
    def ajouter_ecart(self, ecart: EcartContrat):
        self.ecarts.append(ecart)
        if ecart.action == "ajoute":
            self.colonnes_manquantes_creees.append(ecart.colonne)
        elif ecart.action == "ignore":
            self.colonnes_inconnues_ignorees.append(ecart.colonne)
    
    def a_erreurs_bloquantes(self) -> bool:
        return any(e.niveau == NiveauAlerte.BLOQUANT for e in self.ecarts)
    
    def a_erreurs(self) -> bool:
        return any(e.niveau in (NiveauAlerte.ERREUR, NiveauAlerte.BLOQUANT) for e in self.ecarts)


class SchemaContract:
    """Charge et valide le contrat de colonnes canonique."""
    
    def __init__(self, contrat_path: Path):
        self.contrat_path = contrat_path
        self.contrat = self._charger_contrat()
        self._valider_contrat()
    
    def _charger_contrat(self) -> Dict:
        """Charge le fichier JSON du contrat."""
        with open(self.contrat_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _valider_contrat(self):
        """Valide la structure du contrat chargé."""
        required_keys = ['version', 'csv_metier', 'csv_audit']
        for key in required_keys:
            if key not in self.contrat:
                raise ValueError(f"Contrat invalide: clé manquante '{key}'")
    
    @property
    def version(self) -> str:
        return self.contrat['version']
    
    def get_colonnes_metier(self) -> List[str]:
        """Retourne la liste canonique des colonnes métier dans l'ordre."""
        return [c['nom'] for c in self.contrat['csv_metier']['colonnes']]
    
    def get_colonnes_audit_obligatoires(self) -> List[str]:
        """Retourne la liste des colonnes audit obligatoires."""
        return self.contrat['csv_audit']['colonnes_obligatoires']
    
    def get_colonnes_audit_optionnelles(self) -> List[str]:
        """Retourne la liste des colonnes audit optionnelles."""
        return self.contrat['csv_audit'].get('colonnes_optionnelles', [])
    
    def get_all_colonnes_audit(self) -> List[str]:
        """Retourne toutes les colonnes audit (obligatoires + optionnelles)."""
        return (self.get_colonnes_audit_obligatoires() + 
                self.get_colonnes_audit_optionnelles())
    
    def is_strict_metier(self) -> bool:
        """Retourne True si le CSV métier est en mode strict."""
        return self.contrat['csv_metier'].get('strict', True)
    
    def get_politique_alerte(self, type_ecart: str) -> str:
        """Retourne la politique d'alerte pour un type d'écart."""
        politique = self.contrat.get('politique_evolution', {})
        alertes = politique.get('alertes', {})
        return alertes.get(type_ecart, 'AVERTISSEMENT')


class ContractValidator:
    """Valide et transforme les données selon le contrat canonique."""
    
    def __init__(self, contrat: SchemaContract):
        self.contrat = contrat
    
    def valider_et_transformer_metier(
        self, 
        rows: List[Dict], 
        colonnes_source: List[str]
    ) -> Tuple[List[Dict], RapportConformite]:
        """
        Valide et transforme les données pour le CSV métier.
        
        Retourne: (lignes_transformees, rapport)
        """
        rapport = RapportConformite(version_contrat=self.contrat.version)
        rapport.lignes_traitees = len(rows)
        
        colonnes_canoniques = self.contrat.get_colonnes_metier()
        colonnes_source_set = set(colonnes_source)
        colonnes_canoniques_set = set(colonnes_canoniques)
        
        # 1. Vérifier les colonnes inconnues (présentes dans source mais pas dans contrat)
        colonnes_inconnues = colonnes_source_set - colonnes_canoniques_set
        for col in sorted(colonnes_inconnues):
            politique = self.contrat.get_politique_alerte('colonne_inconnue_metier')
            niveau = NiveauAlerte.ERREUR if politique == 'ERREUR' else NiveauAlerte.AVERTISSEMENT
            rapport.ajouter_ecart(EcartContrat(
                type_ecart='colonne_inconnue',
                colonne=col,
                niveau=niveau,
                message=f"Colonne '{col}' présente dans source mais absente du contrat canonique",
                action='ignore'  # Ne pas inclure dans sortie
            ))
        
        # 2. Vérifier les colonnes manquantes (dans contrat mais pas dans source)
        colonnes_manquantes = colonnes_canoniques_set - colonnes_source_set
        for col in sorted(colonnes_manquantes):
            politique = self.contrat.get_politique_alerte('colonne_manquante_metier')
            rapport.ajouter_ecart(EcartContrat(
                type_ecart='colonne_manquante',
                colonne=col,
                niveau=NiveauAlerte.AVERTISSEMENT,
                message=f"Colonne '{col}' manquante dans source, créée vide",
                action='ajoute'
            ))
        
        # 3. Vérifier l'ordre des colonnes
        ordre_incorrect = False
        colonnes_communes = [c for c in colonnes_source if c in colonnes_canoniques_set]
        if colonnes_communes != [c for c in colonnes_canoniques if c in colonnes_source_set]:
            ordre_incorrect = True
            rapport.ajouter_ecart(EcartContrat(
                type_ecart='ordre_incorrect',
                colonne='(multiple)',
                niveau=NiveauAlerte.AVERTISSEMENT,
                message="Ordre des colonnes différent du canonique, réordonnancement automatique",
                action='reordonne'
            ))
        
        # Enregistrer les colonnes conformes
        rapport.colonnes_conformes = [c for c in colonnes_canoniques if c in colonnes_source_set and c not in colonnes_inconnues]
        
        # 4. Transformer les lignes selon le contrat
        rows_transformees = []
        for row in rows:
            new_row = {}
            # Ajouter les colonnes canoniques dans l'ordre
            for col in colonnes_canoniques:
                if col in colonnes_source_set:
                    new_row[col] = row.get(col, "")
                else:
                    # Colonne manquante: créer vide
                    new_row[col] = ""
            rows_transformees.append(new_row)
        
        return rows_transformees, rapport
    
    def valider_et_transformer_audit(
        self,
        rows: List[Dict],
        colonnes_source: List[str]
    ) -> Tuple[List[Dict], RapportConformite]:
        """
        Valide et transforme les données pour le CSV audit.
        
        Retourne: (lignes_transformees, rapport)
        """
        rapport = RapportConformite(version_contrat=self.contrat.version)
        rapport.lignes_traitees = len(rows)
        
        colonnes_obligatoires = self.contrat.get_colonnes_audit_obligatoires()
        colonnes_optionnelles = self.contrat.get_colonnes_audit_optionnelles()
        colonnes_attendues = set(colonnes_obligatoires + colonnes_optionnelles)
        colonnes_source_set = set(colonnes_source)
        
        # 1. Vérifier les colonnes inconnues
        colonnes_inconnues = colonnes_source_set - colonnes_attendues
        for col in sorted(colonnes_inconnues):
            rapport.ajouter_ecart(EcartContrat(
                type_ecart='colonne_inconnue',
                colonne=col,
                niveau=NiveauAlerte.AVERTISSEMENT,
                message=f"Colonne audit '{col}' non répertoriée dans le contrat",
                action='ignore'
            ))
        
        # 2. Vérifier les colonnes obligatoires manquantes
        colonnes_oblig_manquantes = set(colonnes_obligatoires) - colonnes_source_set
        for col in sorted(colonnes_oblig_manquantes):
            rapport.ajouter_ecart(EcartContrat(
                type_ecart='colonne_manquante',
                colonne=col,
                niveau=NiveauAlerte.AVERTISSEMENT,
                message=f"Colonne obligatoire '{col}' manquante dans source audit",
                action='ajoute'
            ))
        
        # 3. Construire la liste finale des colonnes audit
        # Ordre: colonnes obligatoires d'abord, puis optionnelles présentes, puis autres
        colonnes_finales = ['reference']  # Toujours en premier
        for col in colonnes_obligatoires:
            if col != 'reference' and col in colonnes_source:
                colonnes_finales.append(col)
        
        # Ajouter les colonnes optionnelles présentes
        for col in colonnes_optionnelles:
            if col in colonnes_source and col not in colonnes_finales:
                colonnes_finales.append(col)
        
        # 4. Transformer les lignes
        rows_transformees = []
        for row in rows:
            new_row = {}
            for col in colonnes_finales:
                new_row[col] = row.get(col, "")
            rows_transformees.append(new_row)
        
        return rows_transformees, rapport


def ecrire_csv(path: Path, rows: List[Dict], colonnes: List[str]):
    """Écrit un fichier CSV avec les colonnes spécifiées dans l'ordre."""
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=colonnes)
        writer.writeheader()
        writer.writerows(rows)


def print_rapport(rapport_metier: RapportConformite, rapport_audit: RapportConformite, 
                  metier_path: Path, audit_path: Path):
    """Affiche le rapport de conformité."""
    print()
    print("=" * 80)
    print("RAPPORT DE CONFORMITÉ AU CONTRAT DE COLONNES CANONIQUE")
    print("=" * 80)
    print(f"Version du contrat: {rapport_metier.version_contrat}")
    print(f"Lignes traitées: {rapport_metier.lignes_traitees}")
    print()
    
    # Section CSV Métier
    print("-" * 80)
    print("CSV MÉTIER")
    print("-" * 80)
    print(f"Colonnes conformes: {len(rapport_metier.colonnes_conformes)}")
    if rapport_metier.colonnes_conformes:
        for i, col in enumerate(rapport_metier.colonnes_conformes[:10], 1):
            print(f"  ✓ {col}")
        if len(rapport_metier.colonnes_conformes) > 10:
            print(f"  ... et {len(rapport_metier.colonnes_conformes) - 10} autres")
    
    if rapport_metier.colonnes_manquantes_creees:
        print()
        print(f"Colonnes manquantes créées: {len(rapport_metier.colonnes_manquantes_creees)}")
        for col in rapport_metier.colonnes_manquantes_creees:
            print(f"  ⚠ {col} (vide)")
    
    if rapport_metier.colonnes_inconnues_ignorees:
        print()
        print(f"Colonnes inconnues ignorées: {len(rapport_metier.colonnes_inconnues_ignorees)}")
        for col in rapport_metier.colonnes_inconnues_ignorees[:5]:
            print(f"  ✗ {col}")
        if len(rapport_metier.colonnes_inconnues_ignorees) > 5:
            print(f"  ... et {len(rapport_metier.colonnes_inconnues_ignorees) - 5} autres")
    
    if not rapport_metier.ecarts:
        print()
        print("  ✅ Aucun écart détecté - conformité parfaite")
    
    # Section CSV Audit
    print()
    print("-" * 80)
    print("CSV AUDIT")
    print("-" * 80)
    print(f"Colonnes obligatoires attendues: {len(rapport_audit.colonnes_conformes)}")
    
    if rapport_audit.colonnes_manquantes_creees:
        print()
        print(f"Colonnes obligatoires manquantes créées: {len(rapport_audit.colonnes_manquantes_creees)}")
        for col in rapport_audit.colonnes_manquantes_creees[:5]:
            print(f"  ⚠ {col} (vide)")
    
    if rapport_audit.colonnes_inconnues_ignorees:
        print()
        print(f"Colonnes inconnues ignorées: {len(rapport_audit.colonnes_inconnues_ignorees)}")
        for col in rapport_audit.colonnes_inconnues_ignorees[:3]:
            print(f"  ✗ {col}")
    
    if not rapport_audit.ecarts:
        print()
        print("  ✅ Aucun écart détecté - conformité parfaite")
    
    # Bilan final
    print()
    print("=" * 80)
    print("BILAN FINAL")
    print("=" * 80)
    
    total_ecarts = len(rapport_metier.ecarts) + len(rapport_audit.ecarts)
    total_bloquants = (
        sum(1 for e in rapport_metier.ecarts if e.niveau == NiveauAlerte.BLOQUANT) +
        sum(1 for e in rapport_audit.ecarts if e.niveau == NiveauAlerte.BLOQUANT)
    )
    
    if total_bloquants > 0:
        print(f"❌ {total_bloquants} erreur(s) bloquante(s) détectée(s)")
        print("   La génération doit être bloquée ou validée manuellement.")
    elif total_ecarts > 0:
        print(f"⚠️  {total_ecarts} écart(s) détecté(s), auto-corrigé(s)")
        print("   Les fichiers ont été générés avec les corrections automatiques.")
    else:
        print("✅ Conformité parfaite au contrat canonique")
    
    print()
    print("Fichiers générés:")
    print(f"  📄 {metier_path}")
    print(f"  📄 {audit_path}")
    
    return total_bloquants == 0


def main():
    """Point d'entrée principal."""
    # Chemins
    contrat_path = Path('/home/michka/Documents/0-AO-DCE/config/contrat_colonnes_canonique.json')
    input_file = Path('/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v10.csv')
    metier_file = Path('/home/michka/Documents/0-AO-DCE/data/output/AO-metier-consolide-v10-contract.csv')
    audit_file = Path('/home/michka/Documents/0-AO-DCE/data/output/AO-audit-complet-v10-contract.csv')
    
    # Vérifications
    if not contrat_path.exists():
        print(f"❌ Erreur: Contrat canonique non trouvé: {contrat_path}")
        sys.exit(1)
    
    if not input_file.exists():
        print(f"❌ Erreur: Fichier source non trouvé: {input_file}")
        sys.exit(1)
    
    print("=" * 80)
    print("APPLICATION DU CONTRAT DE COLONNES CANONIQUE")
    print("=" * 80)
    
    # Charger le contrat
    try:
        contrat = SchemaContract(contrat_path)
        print(f"✅ Contrat chargé (version {contrat.version})")
        print(f"   CSV métier: {len(contrat.get_colonnes_metier())} colonnes canoniques")
        print(f"   CSV audit: {len(contrat.get_colonnes_audit_obligatoires())} colonnes obligatoires")
    except Exception as e:
        print(f"❌ Erreur chargement contrat: {e}")
        sys.exit(1)
    
    print()
    print(f"📁 Fichier source: {input_file}")
    print(f"📁 Fichier métier: {metier_file}")
    print(f"📁 Fichier audit: {audit_file}")
    print()
    
    # Lire le CSV source
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            colonnes_source = reader.fieldnames.copy()
        print(f"✅ CSV source lu: {len(rows)} lignes, {len(colonnes_source)} colonnes")
    except Exception as e:
        print(f"❌ Erreur lecture CSV: {e}")
        sys.exit(1)
    
    # Valider et transformer
    validator = ContractValidator(contrat)
    
    try:
        rows_metier, rapport_metier = validator.valider_et_transformer_metier(rows, colonnes_source)
        rows_audit, rapport_audit = validator.valider_et_transformer_audit(rows, colonnes_source)
    except Exception as e:
        print(f"❌ Erreur validation: {e}")
        sys.exit(1)
    
    # Vérifier s'il y a des erreurs bloquantes
    if rapport_metier.a_erreurs_bloquantes() or rapport_audit.a_erreurs_bloquantes():
        print()
        print("=" * 80)
        print("❌ ERREURS BLOQUANTES DÉTECTÉES")
        print("=" * 80)
        print("La génération a été interrompue car des erreurs bloquantes ont été détectées.")
        print("Veuillez corriger les problèmes ou forcer la génération avec --force.")
        sys.exit(1)
    
    # Écrire les fichiers
    try:
        ecrire_csv(metier_file, rows_metier, contrat.get_colonnes_metier())
        # Pour l'audit, utiliser les colonnes réellement présentes après transformation
        if rows_audit:
            colonnes_audit = list(rows_audit[0].keys())
            ecrire_csv(audit_file, rows_audit, colonnes_audit)
        print(f"✅ Fichiers CSV générés avec succès")
    except Exception as e:
        print(f"❌ Erreur écriture CSV: {e}")
        sys.exit(1)
    
    # Afficher le rapport
    success = print_rapport(rapport_metier, rapport_audit, metier_file, audit_file)
    
    if success:
        print()
        print("🎉 Traitement terminé avec succès")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
