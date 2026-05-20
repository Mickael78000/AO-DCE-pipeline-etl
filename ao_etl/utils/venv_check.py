#!/usr/bin/env python3
"""
Utilitaire de vérification et activation du virtual environment.
Ce module peut être importé au début des scripts pour s'assurer que le venv est actif.
"""

import sys
import os
from pathlib import Path


def ensure_venv_activated():
    """
    Vérifie que le virtual environment est activé.
    Si ce n'est pas le cas, affiche un message d'erreur explicite.
    
    À utiliser au début des scripts:
        from ao_etl.utils.venv_check import ensure_venv_activated
        ensure_venv_activated()
    """
    # Vérifier si on est dans un venv
    in_venv = (
        hasattr(sys, 'real_prefix') or  # venv Python < 3.10
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or  # venv Python >= 3.10
        os.environ.get('VIRTUAL_ENV') is not None  # Variable d'environnement
    )
    
    if not in_venv:
        script_name = Path(sys.argv[0]).name
        venv_path = Path(__file__).parent.parent.parent / "venv"
        
        print(f"""
❌ ERREUR: Virtual environment non activé

Le script '{script_name}' nécessite un environnement virtuel Python.

Solution:
    1. Activez le venv:
       source venv/bin/activate
       
    2. Ou exécutez via le venv:
       venv/bin/python {script_name}
       
    3. Ou utilisez le script shell qui active automatiquement le venv:
       ./run_full_pipeline.sh

Venv attendu: {venv_path}
""")
        sys.exit(1)
    
    # Vérifier les dépendances critiques
    try:
        import pandas
        import requests
    except ImportError as e:
        print(f"""
❌ ERREUR: Dépendances manquantes

Le module '{e.name}' n'est pas installé dans le venv.

Solution:
    pip install -r requirements.txt
""")
        sys.exit(1)
    
    return True


def get_venv_info():
    """Retourne les informations sur le venv actuel."""
    return {
        'in_venv': (
            hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
            os.environ.get('VIRTUAL_ENV') is not None
        ),
        'python_executable': sys.executable,
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'virtual_env_path': os.environ.get('VIRTUAL_ENV', 'N/A'),
        'sys_prefix': sys.prefix,
    }


if __name__ == '__main__':
    # Mode diagnostic
    info = get_venv_info()
    print("=" * 50)
    print("VIRTUAL ENVIRONMENT DIAGNOSTIC")
    print("=" * 50)
    for key, value in info.items():
        print(f"  {key}: {value}")
    print("=" * 50)
    
    if info['in_venv']:
        print("✅ Virtual environment actif")
    else:
        print("❌ Virtual environment NON actif")
        sys.exit(1)
