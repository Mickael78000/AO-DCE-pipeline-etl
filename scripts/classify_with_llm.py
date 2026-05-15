#!/usr/bin/env python3
"""
Classification LLM des acheteurs "inconnu" avec Ollama.

Utilise le modèle local pour classifier les acheteurs difficiles.
S'appuie sur le schéma extraction_rc.json pour la validation.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import read_csv, write_csv, get_output_path, get_project_root


# ============================================================================
# CHARGEMENT DU SCHÉMA RC
# ============================================================================

def load_rc_schema() -> Dict:
    """Charge le schéma extraction_rc.json pour les listes de valeurs."""
    schema_path = get_project_root() / "extraction_rc.json"
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Schéma RC non trouvé: {e}")
        return {}


def get_valid_categories(schema: Dict) -> List[str]:
    """Extrait les catégories normalisées valides."""
    return schema.get("closed_value_lists", {}).get("categorie_normee", [])


# Mapping entre catégories schéma et champs CSV
CATEGORY_MAPPING = {
    "Etat": ("etat", "etat"),
    "collectivite_territoriale": ("collectivite_territoriale", "territoriale"),
    "etablissement_public": ("etablissement_public", "etat"),
    "EPIC": ("etablissement_public", "etat"),
    "EPA": ("etablissement_public", "etat"),
    "GIP": ("etablissement_public", "etat"),
    "semi_public": ("etablissement_public", "etat"),
    "autre": ("inconnu", "inconnue"),
    "non_precise": ("inconnu", "inconnue"),
}


def validate_and_map(category: str, schema: Dict) -> Dict:
    """
    Valide la catégorie retournée par le LLM et la mappe vers les champs CSV.
    
    Args:
        category: Catégorie retournée par le LLM
        schema: Schéma RC chargé
        
    Returns:
        Dict avec type_acheteur, fonction_publique, valid
    """
    valid_categories = get_valid_categories(schema)
    
    # Normaliser la catégorie
    category_norm = category.lower().strip().replace(" ", "_")
    
    # Chercher dans les catégories valides
    for valid_cat in valid_categories:
        if category_norm == valid_cat.lower():
            type_acheteur, fonction_publique = CATEGORY_MAPPING.get(valid_cat, ("inconnu", "inconnue"))
            return {
                "type_acheteur": type_acheteur,
                "fonction_publique": fonction_publique,
                "categorie_normee": valid_cat,
                "valid": True
            }
    
    # Fallback approximatif
    if "etat" in category_norm and "public" not in category_norm:
        return {"type_acheteur": "etat", "fonction_publique": "etat", "categorie_normee": "Etat", "valid": False}
    elif "territoriale" in category_norm or "collectivite" in category_norm:
        return {"type_acheteur": "collectivite_territoriale", "fonction_publique": "territoriale", "categorie_normee": "collectivite_territoriale", "valid": False}
    elif "hospital" in category_norm:
        return {"type_acheteur": "etablissement_public", "fonction_publique": "hospitaliere", "categorie_normee": "etablissement_public", "valid": False}
    elif "etablissement" in category_norm or "epic" in category_norm or "epa" in category_norm:
        return {"type_acheteur": "etablissement_public", "fonction_publique": "etat", "categorie_normee": "etablissement_public", "valid": False}
    
    return {"type_acheteur": "inconnu", "fonction_publique": "inconnue", "categorie_normee": "non_precise", "valid": False}


def classify_with_ollama(acheteur: str, schema: Dict) -> dict:
    """Appelle Ollama pour classifier un acheteur avec validation schéma RC."""
    try:
        import requests
    except ImportError:
        print("❌ Module 'requests' manquant. Installez-le: pip install requests")
        sys.exit(1)
    
    # Récupérer les catégories valides du schéma
    valid_categories = get_valid_categories(schema)
    categories_str = ", ".join(valid_categories) if valid_categories else "Etat, collectivite_territoriale, etablissement_public, EPIC, EPA, GIP, semi_public, autre, non_precise"
    
    system_prompt = f"""Tu es un expert en droit des marchés publics français.
Ta mission: classer l'entité acheteuse selon sa catégorie administrative.

TU DOIS choisir EXACTEMENT une valeur parmi cette liste fermée:
{categories_str}

Réponds UNIQUEMENT en JSON avec ce format:
{{
  "categorie": "<valeur_de_la_liste>",
  "justification": "Explication courte basée sur les marqueurs textuels"
}}

Règles de classification:
- "Etat": Ministères, directions d'administration centrale, DNUM, services déconcentrés
- "collectivite_territoriale": Régions, départements, communes, métropoles, EPCI, syndicats intercommunaux, SPL
- "etablissement_public": EPA (CND, SHOM), EPIC (CEA, CNRS), universités, COMUE, écoles supérieures
- "EPIC": Établissements publics à caractère industriel et commercial
- "EPA": Établissements publics administratifs
- "GIP": Groupements d'intérêt public
- "semi_public": SEM, sociétés d'économie mixte
- "autre": Associations, entreprises privées, organismes de droit privé
- "non_precise": Impossible à déterminer

IMPORTANT: La valeur "categorie" doit être EXACTEMENT l'une des valeurs de la liste, sans modification."""

    user_prompt = f'Classifie cet acheteur: "{acheteur}"'
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1",
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": False,
                "format": "json"
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        
        # Parse la réponse JSON
        try:
            llm_response = json.loads(result['response'])
            categorie = llm_response.get("categorie", "non_precise")
            justification = llm_response.get("justification", "")
            
            # Valider et mapper vers les champs CSV
            mapped = validate_and_map(categorie, schema)
            
            return {
                "type_acheteur": mapped["type_acheteur"],
                "fonction_publique": mapped["fonction_publique"],
                "categorie_normee": mapped["categorie_normee"],
                "valid": mapped["valid"],
                "llm_raw": categorie,
                "justification": justification
            }
        except json.JSONDecodeError:
            return {
                "type_acheteur": "inconnu",
                "fonction_publique": "inconnue",
                "categorie_normee": "non_precise",
                "valid": False,
                "llm_raw": "",
                "justification": "Erreur parsing JSON"
            }
    except Exception as e:
        return {
            "type_acheteur": "inconnu",
            "fonction_publique": "inconnue",
            "categorie_normee": "non_precise",
            "valid": False,
            "llm_raw": "",
            "justification": f"Erreur LLM: {str(e)[:50]}"
        }


def main():
    parser = argparse.ArgumentParser(description="Classification LLM des acheteurs avec schéma RC")
    parser.add_argument("--input", "-i", default="final-v4-classified.csv")
    parser.add_argument("--output", "-o", default="final-v4-llm-completed.csv")
    parser.add_argument("--dry-run", action="store_true", help="Simulation sans appel LLM")
    args = parser.parse_args()
    
    # Charger le schéma RC
    schema = load_rc_schema()
    if schema:
        categories = get_valid_categories(schema)
        print(f"📋 Schéma RC chargé: {len(categories)} catégories disponibles")
        print(f"   Catégories: {', '.join(categories[:5])}...")
    else:
        print("⚠️  Schéma RC non chargé, utilisation des valeurs par défaut")
    
    input_path = Path(args.input) if Path(args.input).exists() else get_output_path(args.input)
    output_path = Path(args.output) if "/" in args.output else get_output_path(args.output)
    
    rows, fieldnames = read_csv(input_path)
    
    # Ajouter colonnes LLM si manquantes
    new_columns = ["llm_classification", "llm_categorie_normee", "llm_justification", "llm_valid"]
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)
    
    # Trouver les lignes à classifier (type_acheteur inconnu ou vide)
    to_classify = [r for r in rows if r.get("Type", "") in ("", "-", "inconnu")]
    print(f"\n🔍 {len(to_classify)} acheteurs à classifier avec LLM")
    
    if args.dry_run:
        print("\n📋 Mode simulation (dry-run):")
        for row in to_classify[:3]:
            acheteur = row.get("Acheteur_clean") or row.get("Acheteur_auto", "N/A")
            print(f"  - {acheteur}")
        print(f"\n... et {len(to_classify) - 3} autres")
        return
    
    # Classifier avec LLM
    classified_count = 0
    valid_count = 0
    
    for i, row in enumerate(to_classify, 1):
        acheteur = row.get("Acheteur_clean") or row.get("Acheteur_auto", "")
        if not acheteur:
            continue
        
        print(f"\n[{i}/{len(to_classify)}] {acheteur[:50]}...")
        result = classify_with_ollama(acheteur, schema)
        
        # Mettre à jour la ligne si catégorie non-inconnue
        if result["type_acheteur"] != "inconnu":
            row["Type"] = result["type_acheteur"]
            row["Fonction publique"] = result["fonction_publique"]
            row["type_acheteur_source"] = "llm"
            row["fonction_publique_source"] = "llm"
            classified_count += 1
            if result["valid"]:
                valid_count += 1
        
        # Sauvegarder les métadonnées LLM
        row["llm_classification"] = result["type_acheteur"]
        row["llm_categorie_normee"] = result["categorie_normee"]
        row["llm_justification"] = result["justification"]
        row["llm_valid"] = "oui" if result["valid"] else "non"
        
        valid_marker = "✓" if result["valid"] else "~"
        print(f"   {valid_marker} {result['categorie_normee']} → {result['type_acheteur']} / {result['fonction_publique']}")
    
    # Sauvegarder
    write_csv(output_path, rows, fieldnames)
    
    print(f"\n✅ Terminé!")
    print(f"   Classifiés par LLM: {classified_count}/{len(to_classify)}")
    print(f"   Classifications valides (schéma RC): {valid_count}/{classified_count}")
    print(f"   Sortie: {output_path}")


if __name__ == "__main__":
    main()
