#!/usr/bin/env python3
"""
Wrapper pour exécuter des scripts Python avec le virtual environment activé.
Usage: python run_in_venv.py [script.py] [arguments...]

Exemples:
    python run_in_venv.py run_pipeline.py --classify-buyers
    python run_in_venv.py scripts/extract_all_descriptifs.py
    python run_in_venv.py tests/test_pipeline.py
"""

import sys
import os
import subprocess
from pathlib import Path


def find_venv():
    """Trouve le chemin du virtual environment."""
    script_dir = Path(__file__).parent.resolve()
    venv_path = script_dir / "venv"
    
    if venv_path.exists():
        return venv_path
    
    # Chercher dans les parents
    for parent in script_dir.parents:
        venv_path = parent / "venv"
        if venv_path.exists():
            return venv_path
    
    return None


def activate_venv_and_run(venv_path, script_path, args):
    """Active le venv et exécute le script."""
    python_executable = venv_path / "bin" / "python"
    
    if not python_executable.exists():
        print(f"❌ Erreur: Python du venv non trouvé à {python_executable}")
        sys.exit(1)
    
    # Construire la commande
    cmd = [str(python_executable), str(script_path)] + args
    
    # Exécuter avec le venv activé (environnement modifié)
    env = os.environ.copy()
    env['VIRTUAL_ENV'] = str(venv_path)
    env['PATH'] = str(venv_path / "bin") + ":" + env.get('PATH', '')
    
    print(f"✅ Activation du venv: {venv_path}")
    print(f"🚀 Exécution: {' '.join(cmd)}")
    print()
    
    # Exécuter le script
    result = subprocess.run(cmd, env=env)
    sys.exit(result.returncode)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n❌ Erreur: Aucun script spécifié")
        sys.exit(1)
    
    script_to_run = sys.argv[1]
    script_args = sys.argv[2:]
    
    # Vérifier si le venv est déjà actif
    in_venv = (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
        os.environ.get('VIRTUAL_ENV') is not None
    )
    
    if in_venv:
        # Déjà dans le venv, exécuter directement
        print("✅ Virtual environment déjà actif")
        script_path = Path(script_to_run)
        if not script_path.exists():
            print(f"❌ Erreur: Script non trouvé: {script_path}")
            sys.exit(1)
        
        # Exécuter le script directement
        import runpy
        sys.argv = [str(script_path)] + script_args
        runpy.run_path(str(script_path), run_name='__main__')
    else:
        # Vérifier si on est dans le venv
        venv_path = find_venv()
        if not venv_path:
            print("❌ Erreur: Virtual environment non trouvé")
            print("   → Créez-le avec: python3 -m venv venv")
            sys.exit(1)
        
        # Vérifier que le script existe
        script_path = Path(script_to_run)
        if not script_path.exists():
            print(f"❌ Erreur: Script non trouvé: {script_path}")
            sys.exit(1)
        
        # Activer le venv et exécuter
        activate_venv_and_run(venv_path, script_path, script_args)


if __name__ == '__main__':
    main()
