"""Utilitaires CSV partagés pour les scripts AO-DCE."""

import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable


def read_csv(path: Path) -> tuple[List[Dict[str, str]], List[str]]:
    """
    Lit un fichier CSV et retourne les lignes et les noms de colonnes.
    
    Args:
        path: Chemin vers le fichier CSV
        
    Returns:
        Tuple (lignes, noms_colonnes)
    """
    with open(path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        rows = list(reader)
    return rows, fieldnames


def write_csv(
    path: Path,
    rows: List[Dict[str, Any]],
    fieldnames: Optional[List[str]] = None,
    extrasaction: str = 'ignore'
) -> None:
    """
    Écrit des lignes dans un fichier CSV.
    
    Args:
        path: Chemin de sortie
        rows: Lignes à écrire
        fieldnames: Noms des colonnes (auto-détecté si None)
        extrasaction: Action pour les champs extra ('ignore' ou 'raise')
    """
    if fieldnames is None and rows:
        fieldnames = list(rows[0].keys())
    
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction=extrasaction)
        writer.writeheader()
        writer.writerows(rows)


def update_csv_rows(
    input_path: Path,
    output_path: Path,
    transform_fn: Callable[[Dict[str, str]], Dict[str, str]],
    new_columns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Met à jour les lignes d'un CSV avec une fonction de transformation.
    
    Args:
        input_path: Fichier CSV source
        output_path: Fichier CSV de sortie
        transform_fn: Fonction qui transforme une ligne
        new_columns: Nouvelles colonnes à ajouter
        
    Returns:
        Statistiques de la transformation
    """
    rows, fieldnames = read_csv(input_path)
    
    # Ajouter les nouvelles colonnes
    if new_columns:
        for col in new_columns:
            if col not in fieldnames:
                fieldnames.append(col)
    
    # Transformer les lignes
    modified_count = 0
    transformed_rows = []
    
    for row in rows:
        original = row.copy()
        transformed = transform_fn(row)
        transformed_rows.append(transformed)
        
        if transformed != original:
            modified_count += 1
    
    # Écrire le résultat
    write_csv(output_path, transformed_rows, fieldnames)
    
    return {
        'total_rows': len(rows),
        'modified_rows': modified_count,
        'input_path': str(input_path),
        'output_path': str(output_path),
    }


def add_columns_to_csv(
    input_path: Path,
    output_path: Path,
    columns: List[str],
    default_value: str = ''
) -> None:
    """
    Ajoute des colonnes vides à un fichier CSV.
    
    Args:
        input_path: Fichier CSV source
        output_path: Fichier CSV de sortie  
        columns: Noms des colonnes à ajouter
        default_value: Valeur par défaut
    """
    rows, fieldnames = read_csv(input_path)
    
    for col in columns:
        if col not in fieldnames:
            fieldnames.append(col)
    
    # S'assurer que toutes les lignes ont les nouvelles colonnes
    for row in rows:
        for col in columns:
            if col not in row:
                row[col] = default_value
    
    write_csv(output_path, rows, fieldnames)
