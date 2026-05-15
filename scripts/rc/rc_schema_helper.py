#!/usr/bin/env python3
"""
Validateur de schéma v4 + Helper de saisie pour extraction_rc.json

Usage:
    python rc_schema_helper.py validate --json extraction_rc.json
    python rc_schema_helper.py create --ref 2026-NEW01 --output new_market.json
    python rc_schema_helper.py fix --json extraction_rc.json --output fixed.json
    python rc_schema_helper.py template > template.json
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationError:
    """Représente une erreur de validation."""
    path: str  # Chemin dans le JSON (ex: "marches[0].acheteur.categorie_normee")
    field: str  # Nom du champ
    value: Any  # Valeur reçue
    expected: str  # Ce qui était attendu
    severity: str  # "error", "warning", "info"
    message: str  # Message explicatif


class RCSchemaValidator:
    """Validateur pour le schéma v4 de extraction_rc.json"""
    
    def __init__(self, schema_source: Optional[Path] = None):
        """Charge le schéma depuis un fichier de référence."""
        self.schema_source = schema_source or Path(__file__).parent / "extraction_rc.json"
        self.closed_lists: Dict[str, List[str]] = {}
        self.field_constraints: Dict[str, Any] = {}
        self._load_schema()
    
    def _load_schema(self):
        """Charge les métadonnées du schéma."""
        if not self.schema_source.exists():
            # Schéma par défaut si fichier non trouvé
            self.closed_lists = {
                "categorie_normee": ["Etat", "collectivite_territoriale", "etablissement_public", 
                                    "EPIC", "EPA", "GIP", "semi_public", "autre", "non_precise"],
                "type_marche_norme": ["services", "fournitures", "travaux", "prestations_intellectuelles",
                                     "accord_cadre_bc", "accord_cadre_mixte", "marche_composite", "non_precise"],
                "procedure_regime": ["droit_commun", "defense_et_securite", "autre", "non_precise"],
                "allotissement_statut": ["alloti", "non_alloti", "partiellement_alloti", "non_precise"],
                "statut_verification": ["verifie", "partiellement_verifie", "non_verifie", "ambigu"],
                "niveau_confiance": ["eleve", "moyen", "faible"],
                "nature_montant": ["global", "estimation", "plafond", "minimum", "non_precise"],
                "preuve_niveau": ["verifie", "deduit", "absent", "non_precise"],
                "ccag_mode_determination": ["mention_directe", "mention_bibliographie", "deduit_type_marche", 
                                           "deduit_lot", "non_precise"],
            }
            return
        
        with open(self.schema_source, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.closed_lists = data.get("closed_value_lists", {})
        self.field_constraints = data.get("field_constraints", {})
    
    def validate_market(self, market: Dict, index: int = 0) -> List[ValidationError]:
        """Valide un marché complet selon le schéma v4."""
        errors = []
        prefix = f"marches[{index}]"
        
        # 1. Validation des champs obligatoires
        required_fields = ["reference", "acheteur", "controle"]
        for field in required_fields:
            if field not in market or market[field] is None:
                errors.append(ValidationError(
                    path=f"{prefix}.{field}",
                    field=field,
                    value=None,
                    expected="présent",
                    severity="error",
                    message=f"Champ obligatoire '{field}' manquant"
                ))
        
        # 2. Validation acheteur
        if "acheteur" in market:
            errors.extend(self._validate_acheteur(market["acheteur"], f"{prefix}.acheteur"))
        
        # 3. Validation type_marche
        if "type_marche" in market:
            errors.extend(self._validate_enum(market["type_marche"], 
                "categorie_normee", "type_marche_norme", f"{prefix}.type_marche"))
        
        # 4. Validation procedure
        if "procedure" in market:
            errors.extend(self._validate_procedure(market["procedure"], f"{prefix}.procedure"))
        
        # 5. Validation allotissement
        if "allotissement" in market:
            errors.extend(self._validate_allotissement(market["allotissement"], 
                market.get("lots", []), f"{prefix}.allotissement"))
        
        # 6. Validation montants
        if "montants" in market:
            errors.extend(self._validate_montants(market["montants"], f"{prefix}.montants"))
        
        # 7. Validation ccag
        if "ccag" in market:
            errors.extend(self._validate_ccag(market["ccag"], f"{prefix}.ccag"))
        
        # 8. Validation controle
        if "controle" in market:
            errors.extend(self._validate_controle(market["controle"], f"{prefix}.controle"))
        
        # 9. Validation conflits (structure)
        if "conflits" in market:
            errors.extend(self._validate_conflits(market["conflits"], f"{prefix}.conflits"))
        
        # 10. Validation dates
        if "date_limite_remise_offres" in market:
            errors.extend(self._validate_date(market["date_limite_remise_offres"], 
                f"{prefix}.date_limite_remise_offres"))
        
        return errors
    
    def _validate_acheteur(self, acheteur: Dict, path: str) -> List[ValidationError]:
        """Valide la structure acheteur."""
        errors = []
        
        # categorie_normee obligatoire et dans enum
        if "categorie_normee" not in acheteur:
            errors.append(ValidationError(
                path=f"{path}.categorie_normee",
                field="categorie_normee",
                value=None,
                expected=f"une de: {', '.join(self.closed_lists.get('categorie_normee', []))}",
                severity="error",
                message="categorie_normee obligatoire dans acheteur"
            ))
        elif acheteur["categorie_normee"] not in self.closed_lists.get("categorie_normee", []):
            errors.append(ValidationError(
                path=f"{path}.categorie_normee",
                field="categorie_normee",
                value=acheteur["categorie_normee"],
                expected=f"une de: {', '.join(self.closed_lists.get('categorie_normee', []))}",
                severity="error",
                message=f"Valeur '{acheteur['categorie_normee']}' non dans enum categorie_normee"
            ))
        
        return errors
    
    def _validate_enum(self, obj: Dict, source_field: str, enum_name: str, path: str) -> List[ValidationError]:
        """Valide qu'un champ est dans une enum fermée."""
        errors = []
        value = obj.get(source_field) if isinstance(obj, dict) else obj
        
        if value is None:
            return errors  # Null autorisé généralement
        
        allowed = self.closed_lists.get(enum_name, [])
        if value not in allowed:
            errors.append(ValidationError(
                path=f"{path}.{source_field}",
                field=source_field,
                value=value,
                expected=f"une de: {', '.join(allowed)}",
                severity="error",
                message=f"Valeur '{value}' non autorisée dans {enum_name}"
            ))
        
        return errors
    
    def _validate_procedure(self, procedure: Dict, path: str) -> List[ValidationError]:
        """Valide la structure procedure."""
        errors = []
        
        # regime doit être dans enum
        if "regime" in procedure:
            regime = procedure["regime"]
            allowed = self.closed_lists.get("procedure_regime", [])
            if regime not in allowed:
                errors.append(ValidationError(
                    path=f"{path}.regime",
                    field="regime",
                    value=regime,
                    expected=f"une de: {', '.join(allowed)}",
                    severity="error",
                    message=f"regime '{regime}' non valide"
                ))
        
        # niveau_preuve doit être dans enum
        if "niveau_preuve" in procedure:
            niveau = procedure["niveau_preuve"]
            allowed = self.closed_lists.get("preuve_niveau", [])
            if niveau not in allowed:
                errors.append(ValidationError(
                    path=f"{path}.niveau_preuve",
                    field="niveau_preuve",
                    value=niveau,
                    expected=f"une de: {', '.join(allowed)}",
                    severity="error",
                    message=f"niveau_preuve '{niveau}' non valide"
                ))
        
        return errors
    
    def _validate_allotissement(self, allotissement: Dict, lots: List, path: str) -> List[ValidationError]:
        """Valide la cohérence allotissement/lots."""
        errors = []
        
        statut = allotissement.get("statut")
        nb_lots = allotissement.get("nombre_lots", 0)
        
        # statut dans enum
        allowed = self.closed_lists.get("allotissement_statut", [])
        if statut and statut not in allowed:
            errors.append(ValidationError(
                path=f"{path}.statut",
                field="statut",
                value=statut,
                expected=f"une de: {', '.join(allowed)}",
                severity="error",
                message=f"statut allotissement '{statut}' non valide"
            ))
        
        # Cohérence statut/nombre_lots
        if statut == "non_alloti" and nb_lots > 0:
            errors.append(ValidationError(
                path=f"{path}.nombre_lots",
                field="nombre_lots",
                value=nb_lots,
                expected="0 (car non_alloti)",
                severity="warning",
                message="allotissement non_alloti mais nombre_lots > 0"
            ))
        
        if statut == "alloti" and nb_lots == 0:
            errors.append(ValidationError(
                path=f"{path}.nombre_lots",
                field="nombre_lots",
                value=nb_lots,
                expected="> 0 (car alloti)",
                severity="warning",
                message="allotissement alloti mais nombre_lots = 0"
            ))
        
        # Cohérence avec tableau lots
        if statut == "alloti" and len(lots) != nb_lots:
            errors.append(ValidationError(
                path=f"{path}",
                field="lots",
                value=f"{len(lots)} lots",
                expected=f"{nb_lots} lots (coherent avec nombre_lots)",
                severity="warning",
                message=f"Incohérence: nombre_lots={nb_lots} mais {len(lots)} lots définis"
            ))
        
        return errors
    
    def _validate_montants(self, montants: Dict, path: str) -> List[ValidationError]:
        """Valide la structure montants."""
        errors = []
        
        for field in ["global", "estime", "maximum", "minimum"]:
            if field in montants and montants[field] is not None:
                montant = montants[field]
                
                # Vérifier structure minimale
                if not isinstance(montant, dict):
                    continue
                
                # nature dans enum
                nature = montant.get("nature")
                if nature:
                    allowed = self.closed_lists.get("nature_montant", [])
                    if nature not in allowed:
                        errors.append(ValidationError(
                            path=f"{path}.{field}.nature",
                            field="nature",
                            value=nature,
                            expected=f"une de: {', '.join(allowed)}",
                            severity="error",
                            message=f"nature montant '{nature}' non valide"
                        ))
                
                # valeur doit être nombre ou null
                valeur = montant.get("valeur")
                if valeur is not None and not isinstance(valeur, (int, float)):
                    errors.append(ValidationError(
                        path=f"{path}.{field}.valeur",
                        field="valeur",
                        value=valeur,
                        expected="nombre ou null",
                        severity="error",
                        message=f"valeur montant doit être un nombre, reçu: {type(valeur).__name__}"
                    ))
        
        # nature_marche doit être dans enum
        if "nature_marche" in montants:
            nature = montants["nature_marche"]
            allowed = self.closed_lists.get("type_marche_norme", [])
            if nature not in allowed:
                errors.append(ValidationError(
                    path=f"{path}.nature_marche",
                    field="nature_marche",
                    value=nature,
                    expected=f"une de: {', '.join(allowed)}",
                    severity="error",
                    message=f"nature_marche '{nature}' non valide"
                ))
        
        return errors
    
    def _validate_ccag(self, ccag: Dict, path: str) -> List[ValidationError]:
        """Valide la structure CCAG avec contraintes inter-champs."""
        errors = []
        
        mentionne = ccag.get("mentionne")
        principal = ccag.get("principal")
        categorie = ccag.get("categorie_normee")
        mode = ccag.get("mode_determination")
        
        # Contrainte: if_mentionne_false_then_principal_null
        if mentionne is False and principal is not None:
            errors.append(ValidationError(
                path=f"{path}.principal",
                field="principal",
                value=principal,
                expected="null (car mentionne=false)",
                severity="error",
                message="Contrainte schéma: si mentionne=false alors principal doit être null"
            ))
        
        # Contrainte: if_principal_non_null_then_mentionne_true
        if principal is not None and mentionne is not True:
            errors.append(ValidationError(
                path=f"{path}.mentionne",
                field="mentionne",
                value=mentionne,
                expected="true (car principal non null)",
                severity="error",
                message="Contrainte schéma: si principal non null alors mentionne doit être true"
            ))
        
        # categorie_normee dans enum
        if categorie:
            # CCAG a ses propres catégories ou utilise type_marche_norme
            pass  # Simplifié pour l'exemple
        
        # mode_determination dans enum
        if mode:
            allowed = self.closed_lists.get("ccag_mode_determination", [])
            if mode not in allowed:
                errors.append(ValidationError(
                    path=f"{path}.mode_determination",
                    field="mode_determination",
                    value=mode,
                    expected=f"une de: {', '.join(allowed)}",
                    severity="error",
                    message=f"mode_determination '{mode}' non valide"
                ))
        
        return errors
    
    def _validate_controle(self, controle: Dict, path: str) -> List[ValidationError]:
        """Valide la structure controle."""
        errors = []
        
        # statut_verification dans enum
        statut = controle.get("statut_verification")
        if statut:
            allowed = self.closed_lists.get("statut_verification", [])
            if statut not in allowed:
                errors.append(ValidationError(
                    path=f"{path}.statut_verification",
                    field="statut_verification",
                    value=statut,
                    expected=f"une de: {', '.join(allowed)}",
                    severity="error",
                    message=f"statut_verification '{statut}' non valide"
                ))
        
        # niveau_confiance dans enum
        niveau = controle.get("niveau_confiance")
        if niveau:
            allowed = self.closed_lists.get("niveau_confiance", [])
            if niveau not in allowed:
                errors.append(ValidationError(
                    path=f"{path}.niveau_confiance",
                    field="niveau_confiance",
                    value=niveau,
                    expected=f"une de: {', '.join(allowed)}",
                    severity="error",
                    message=f"niveau_confiance '{niveau}' non valide"
                ))
        
        return errors
    
    def _validate_conflits(self, conflits: List, path: str) -> List[ValidationError]:
        """Valide la structure des conflits."""
        errors = []
        
        if not isinstance(conflits, list):
            return [ValidationError(
                path=path,
                field="conflits",
                value=type(conflits).__name__,
                expected="liste",
                severity="error",
                message="conflits doit être une liste"
            )]
        
        for i, conflit in enumerate(conflits):
            required = ["champ", "valeur_source", "valeur_consolidee", "motif_conflit"]
            for field in required:
                if field not in conflit:
                    errors.append(ValidationError(
                        path=f"{path}[{i}].{field}",
                        field=field,
                        value=None,
                        expected="présent",
                        severity="warning",
                        message=f"Champ '{field}' recommandé dans conflit"
                    ))
        
        return errors
    
    def _validate_date(self, date_obj: Dict, path: str) -> List[ValidationError]:
        """Valide le format de date ISO 8601."""
        errors = []
        
        iso_value = date_obj.get("valeur_iso")
        if iso_value and iso_value is not None:
            # Pattern ISO 8601 basique: YYYY-MM-DDTHH:MM:SS+HH:MM
            import re
            pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$'
            if not re.match(pattern, iso_value):
                errors.append(ValidationError(
                    path=f"{path}.valeur_iso",
                    field="valeur_iso",
                    value=iso_value,
                    expected="format ISO 8601 (ex: 2026-06-04T17:00:00+02:00)",
                    severity="warning",
                    message="Format date ISO non standard"
                ))
        
        return errors
    
    def validate_file(self, data: Dict) -> Tuple[List[ValidationError], int]:
        """Valide tout le fichier extraction_rc.json."""
        all_errors = []
        
        # Vérifier métadonnées
        if "schema_version" not in data:
            all_errors.append(ValidationError(
                path="root",
                field="schema_version",
                value=None,
                expected="présent",
                severity="error",
                message="Métadonnée schema_version manquante"
            ))
        
        # Valider chaque marché
        marches = data.get("marches", [])
        for i, market in enumerate(marches):
            errors = self.validate_market(market, i)
            all_errors.extend(errors)
        
        return all_errors, len(marches)
    
    def print_report(self, errors: List[ValidationError], total_markets: int):
        """Affiche un rapport de validation formaté."""
        print(f"\n{'='*70}")
        print(f"RAPPORT DE VALIDATION - Schéma v4")
        print(f"{'='*70}")
        print(f"Marchés analysés: {total_markets}")
        print(f"Erreurs trouvées: {len([e for e in errors if e.severity == 'error'])}")
        print(f"Avertissements: {len([e for e in errors if e.severity == 'warning'])}")
        print(f"Infos: {len([e for e in errors if e.severity == 'info'])}")
        
        if not errors:
            print("\n✓ Aucune erreur détectée - Fichier conforme au schéma v4")
            return
        
        # Grouper par sévérité
        by_severity = {"error": [], "warning": [], "info": []}
        for e in errors:
            by_severity[e.severity].append(e)
        
        for severity, icon in [("error", "✗"), ("warning", "⚠"), ("info", "ℹ")]:
            if by_severity[severity]:
                print(f"\n{icon} {severity.upper()} ({len(by_severity[severity])}):")
                for e in by_severity[severity][:10]:  # Limiter à 10 par catégorie
                    print(f"   {e.path}")
                    print(f"   → {e.message}")
                    if e.value is not None:
                        print(f"     Valeur: {e.value}")
                if len(by_severity[severity]) > 10:
                    print(f"   ... et {len(by_severity[severity]) - 10} autres")


class RCSchemaHelper:
    """Helper pour créer et modifier des marchés conformes au schéma."""
    
    def __init__(self, validator: RCSchemaValidator):
        self.validator = validator
    
    def create_template(self, reference: str, **kwargs) -> Dict:
        """Crée un template de marché vierge mais conforme."""
        now = datetime.now().isoformat()
        
        template = {
            "reference": reference,
            "reference_source": kwargs.get("reference_source", reference),
            "reference_consolidee": kwargs.get("reference_consolidee", reference),
            "identification_confiance": kwargs.get("identification_confiance", "moyen"),
            "titre": kwargs.get("titre", ""),
            "acheteur": {
                "nom": kwargs.get("acheteur_nom", ""),
                "structure_juridique": kwargs.get("acheteur_structure", ""),
                "categorie_normee": kwargs.get("categorie_normee", "non_precise"),
                "service_interne": kwargs.get("service_interne", ""),
                "identification_confiance": "moyen"
            },
            "lieu": {
                "adresse": kwargs.get("adresse", ""),
                "code_postal": kwargs.get("code_postal", ""),
                "ville": kwargs.get("ville", ""),
                "pays": kwargs.get("pays", "France"),
                "source_brute": kwargs.get("lieu_source", "")
            },
            "date_limite_remise_offres": {
                "valeur_iso": kwargs.get("date_iso", ""),
                "valeur_brute": kwargs.get("date_brute", ""),
                "fuseau_horaire": kwargs.get("fuseau", "Europe/Paris"),
                "source_brute": kwargs.get("date_source", "")
            },
            "plateforme_remise_offres": {
                "nom": kwargs.get("plateforme_nom", ""),
                "url": kwargs.get("plateforme_url", ""),
                "source_brute": kwargs.get("plateforme_source", "")
            },
            "type_marche": {
                "source": kwargs.get("type_source", ""),
                "consolide": kwargs.get("type_consolide", ""),
                "categorie_normee": kwargs.get("type_normee", "non_precise")
            },
            "procedure": {
                "source": kwargs.get("procedure_source", ""),
                "consolidee": kwargs.get("procedure_consolidee", ""),
                "regime": kwargs.get("regime", "droit_commun"),
                "niveau_preuve": "non_precise"
            },
            "duree": {
                "valeur": kwargs.get("duree_valeur", None),
                "unite": kwargs.get("duree_unite", "mois"),
                "structure": kwargs.get("duree_structure", ""),
                "source_brute": kwargs.get("duree_source", "")
            },
            "montants": {
                "global": self._create_montant_obj(kwargs.get("montant_global"), "global"),
                "estime": self._create_montant_obj(kwargs.get("montant_estime"), "estimation"),
                "maximum": self._create_montant_obj(kwargs.get("montant_max"), "plafond"),
                "minimum": self._create_montant_obj(kwargs.get("montant_min"), "minimum"),
                "nature_marche": kwargs.get("nature_marche", "non_precise")
            },
            "allotissement": {
                "statut": kwargs.get("allotissement", "non_precise"),
                "nombre_lots": kwargs.get("nb_lots", 0),
                "source_brute": kwargs.get("allotissement_source", "")
            },
            "ccag": {
                "mentionne": kwargs.get("ccag_mentionne", False),
                "source_brute": kwargs.get("ccag_source", ""),
                "principal": kwargs.get("ccag_principal", None),
                "categorie_normee": kwargs.get("ccag_categorie", "non_precise"),
                "mode_determination": kwargs.get("ccag_mode", "non_precise"),
                "niveau_preuve": kwargs.get("ccag_preuve", "absent"),
                "hypothese": kwargs.get("ccag_hypothese", "")
            },
            "lots": [],
            "criteres_selection": [],
            "dce": {
                "pieces_constitutives": []
            },
            "conflits": [],
            "controle": {
                "statut_verification": kwargs.get("statut_verif", "non_verifie"),
                "niveau_confiance": kwargs.get("niveau_conf", "moyen"),
                "qualite_extraction": kwargs.get("qualite", "moyenne"),
                "commentaire": kwargs.get("commentaire", "")
            },
            "source_extrait": {
                "fichier": kwargs.get("source_fichier", ""),
                "page": kwargs.get("source_page", None),
                "section": kwargs.get("source_section", ""),
                "citation_brute": kwargs.get("citation", "")
            }
        }
        
        return template
    
    def _create_montant_obj(self, valeur, nature):
        """Crée un objet montant standardisé."""
        return {
            "valeur": valeur,
            "devise": "EUR",
            "precision": "",
            "source_brute": "",
            "nature": nature if valeur is not None else "non_precise"
        }
    
    def interactive_create(self) -> Dict:
        """Mode interactif pour créer un marché."""
        print("\n" + "="*70)
        print("CREATION INTERACTIVE D'UN MARCHE (Schéma v4)")
        print("="*70)
        print("Laissez vide et appuyez Entrée pour valeur par défaut\n")
        
        def ask(prompt, default=""):
            val = input(f"{prompt} [{default}]: ").strip()
            return val if val else default
        
        # Informations de base
        reference = ask("Référence du marché (obligatoire)")
        if not reference:
            print("Erreur: Référence obligatoire")
            return None
        
        titre = ask("Titre/objet du marché")
        
        # Acheteur
        print("\n--- Acheteur ---")
        acheteur_nom = ask("Nom de l'acheteur")
        print(f"Catégories: {', '.join(self.validator.closed_lists.get('categorie_normee', []))}")
        categorie = ask("Catégorie normée", "non_precise")
        
        # Dates
        print("\n--- Date limite ---")
        date_brute = ask("Date brute (ex: 04/06/2026 à 17H00)")
        date_iso = ask("Date ISO (ex: 2026-06-04T17:00:00+02:00)", "")
        
        # Montants
        print("\n--- Montants (en euros, laisser vide si non publié) ---")
        try:
            montant_global = input("Montant global: ").strip()
            montant_global = int(montant_global) if montant_global else None
        except:
            montant_global = None
        
        try:
            montant_estime = input("Montant estimé: ").strip()
            montant_estime = int(montant_estime) if montant_estime else None
        except:
            montant_estime = None
        
        try:
            montant_max = input("Montant maximum: ").strip()
            montant_max = int(montant_max) if montant_max else None
        except:
            montant_max = None
        
        # Type et procédure
        print(f"\nTypes de marché: {', '.join(self.validator.closed_lists.get('type_marche_norme', []))}")
        type_normee = ask("Type normé", "non_precise")
        
        print(f"\nRégimes: {', '.join(self.validator.closed_lists.get('procedure_regime', []))}")
        regime = ask("Régime", "droit_commun")
        
        # Source
        print("\n--- Source ---")
        source_fichier = ask("Nom du fichier PDF source")
        
        # Créer le template
        market = self.create_template(
            reference=reference,
            titre=titre,
            acheteur_nom=acheteur_nom,
            categorie_normee=categorie,
            date_brute=date_brute,
            date_iso=date_iso,
            montant_global=montant_global,
            montant_estime=montant_estime,
            montant_max=montant_max,
            type_normee=type_normee,
            regime=regime,
            source_fichier=source_fichier
        )
        
        # Valider
        errors = self.validator.validate_market(market)
        if errors:
            print(f"\n⚠ {len(errors)} problèmes détectés:")
            for e in errors[:5]:
                print(f"   - {e.message}")
        else:
            print("\n✓ Structure valide")
        
        return market
    
    def fix_common_errors(self, data: Dict) -> Tuple[Dict, List[str]]:
        """Tente de corriger automatiquement les erreurs courantes."""
        fixes = []
        marches = data.get("marches", [])
        
        for i, market in enumerate(marches):
            # Fix 1: Normaliser les catégories (minuscule → enum)
            if "acheteur" in market:
                cat = market["acheteur"].get("categorie_normee", "")
                allowed = self.validator.closed_lists.get("categorie_normee", [])
                if cat and cat not in allowed:
                    # Essayer de matcher insensible à la casse
                    for allowed_cat in allowed:
                        if cat.lower() == allowed_cat.lower():
                            market["acheteur"]["categorie_normee"] = allowed_cat
                            fixes.append(f"marches[{i}].acheteur.categorie_normee: '{cat}' → '{allowed_cat}'")
                            break
            
            # Fix 2: Assurer cohérence CCAG
            if "ccag" in market:
                ccag = market["ccag"]
                if ccag.get("mentionne") is False and ccag.get("principal") is not None:
                    ccag["principal"] = None
                    fixes.append(f"marches[{i}].ccag.principal: mis à null (mentionne=false)")
                
                if ccag.get("principal") is not None and ccag.get("mentionne") is not True:
                    ccag["mentionne"] = True
                    fixes.append(f"marches[{i}].ccag.mentionne: mis à true (principal non null)")
            
            # Fix 3: Normaliser dates si format incorrect
            if "date_limite_remise_offres" in market:
                date_obj = market["date_limite_remise_offres"]
                iso = date_obj.get("valeur_iso", "")
                if iso and not iso.endswith("+02:00") and not iso.endswith("+01:00"):
                    if len(iso) == 19:  # Format sans timezone
                        date_obj["valeur_iso"] = iso + "+02:00"
                        fixes.append(f"marches[{i}].date_limite_remise_offres.valeur_iso: ajout timezone +02:00")
        
        return data, fixes


def cmd_validate(args):
    """Commande: valider un fichier JSON."""
    json_file = Path(args.json)
    if not json_file.exists():
        print(f"✗ Fichier non trouvé: {json_file}")
        return 1
    
    validator = RCSchemaValidator()
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    errors, total = validator.validate_file(data)
    validator.print_report(errors, total)
    
    return 0 if not any(e.severity == "error" for e in errors) else 1


def cmd_create(args):
    """Commande: créer un nouveau marché."""
    validator = RCSchemaValidator()
    helper = RCSchemaHelper(validator)
    
    if args.interactive:
        market = helper.interactive_create()
        if market is None:
            return 1
    else:
        # Mode ligne de commande
        market = helper.create_template(
            reference=args.ref,
            titre=args.titre,
            acheteur_nom=args.acheteur,
            categorie_normee=args.categorie
        )
    
    # Sortie
    output = args.output
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(market, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Marché sauvegardé dans: {output}")
    else:
        print("\n" + json.dumps(market, ensure_ascii=False, indent=2))
    
    return 0


def cmd_template(args):
    """Commande: afficher un template vierge."""
    validator = RCSchemaValidator()
    helper = RCSchemaHelper(validator)
    
    template = helper.create_template("EXAMPLE-2026-001")
    
    # Ajouter commentaires explicatifs
    commented = {
        "_commentaire": "Template de marché conforme au schéma v4",
        "_enums_disponibles": validator.closed_lists,
        "marche": template
    }
    
    print(json.dumps(commented, ensure_ascii=False, indent=2))
    return 0


def cmd_fix(args):
    """Commande: corriger automatiquement les erreurs courantes."""
    json_file = Path(args.json)
    if not json_file.exists():
        print(f"✗ Fichier non trouvé: {json_file}")
        return 1
    
    validator = RCSchemaValidator()
    helper = RCSchemaHelper(validator)
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Validation avant
    print("Validation avant correction...")
    errors_before, total = validator.validate_file(data)
    validator.print_report(errors_before, total)
    
    # Correction
    print("\n" + "="*70)
    print("CORRECTION AUTOMATIQUE")
    print("="*70)
    
    data, fixes = helper.fix_common_errors(data)
    
    if fixes:
        print(f"\n{len(fixes)} corrections appliquées:")
        for fix in fixes[:20]:
            print(f"  ✓ {fix}")
        if len(fixes) > 20:
            print(f"  ... et {len(fixes) - 20} autres")
    else:
        print("\nAucune correction automatique applicable")
    
    # Validation après
    print("\n" + "="*70)
    print("Validation après correction...")
    print("="*70)
    
    errors_after, _ = validator.validate_file(data)
    validator.print_report(errors_after, total)
    
    # Sauvegarde
    output = Path(args.output) if args.output else json_file
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Fichier sauvegardé: {output}")
    print(f"  Erreurs avant: {len([e for e in errors_before if e.severity == 'error'])}")
    print(f"  Erreurs après: {len([e for e in errors_after if e.severity == 'error'])}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Validateur de schéma v4 + Helper pour extraction_rc.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Valider un fichier
  python rc_schema_helper.py validate --json extraction_rc.json
  
  # Créer un marché interactif
  python rc_schema_helper.py create --interactive --output new_market.json
  
  # Afficher le template
  python rc_schema_helper.py template > template_reference.json
  
  # Corriger automatiquement
  python rc_schema_helper.py fix --json extraction_rc.json --output fixed.json
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")
    
    # Commande validate
    val_parser = subparsers.add_parser("validate", help="Valider un fichier JSON")
    val_parser.add_argument("--json", "-j", required=True, help="Fichier JSON à valider")
    
    # Commande create
    create_parser = subparsers.add_parser("create", help="Créer un nouveau marché")
    create_parser.add_argument("--interactive", "-i", action="store_true", help="Mode interactif")
    create_parser.add_argument("--ref", "-r", help="Référence du marché")
    create_parser.add_argument("--titre", "-t", help="Titre du marché")
    create_parser.add_argument("--acheteur", "-a", help="Nom de l'acheteur")
    create_parser.add_argument("--categorie", "-c", default="non_precise", help="Catégorie normée")
    create_parser.add_argument("--output", "-o", help="Fichier de sortie (sinon stdout)")
    
    # Commande template
    subparsers.add_parser("template", help="Afficher un template de marché")
    
    # Commande fix
    fix_parser = subparsers.add_parser("fix", help="Corriger automatiquement les erreurs courantes")
    fix_parser.add_argument("--json", "-j", required=True, help="Fichier JSON à corriger")
    fix_parser.add_argument("--output", "-o", help="Fichier de sortie (sinon écrase l'original)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    commands = {
        "validate": cmd_validate,
        "create": cmd_create,
        "template": cmd_template,
        "fix": cmd_fix,
    }
    
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
