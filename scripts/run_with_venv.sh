#!/bin/bash
# Template de script avec activation automatique du virtual environment
# Usage: source run_with_venv.sh [commande]

set -e

# ==========================================
# ACTIVATION DU VIRTUAL ENVIRONMENT
# ==========================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
VENV_PATH="${PROJECT_ROOT}/venv"

# Fonction pour activer le venv
activate_venv() {
    # Vérifier si le venv existe
    if [ ! -d "$VENV_PATH" ]; then
        echo "❌ Erreur: Virtual environment non trouvé à ${VENV_PATH}"
        echo "   → Créez-le avec: python3 -m venv venv"
        echo "   → Puis installez les dépendances: pip install -r requirements.txt"
        return 1
    fi
    
    # Activer le venv
    source "${VENV_PATH}/bin/activate"
    
    # Vérifier que Python du venv est utilisé
    PYTHON_VERSION=$(python --version 2>&1)
    echo "✅ Virtual environment activé: ${PYTHON_VERSION}"
    
    return 0
}

# Fonction pour vérifier les dépendances
check_dependencies() {
    if ! python -c "import pandas, requests, bs4" 2>/dev/null; then
        echo "❌ Erreur: Dépendances manquantes"
        echo "   → Installez-les avec: pip install -r requirements.txt"
        return 1
    fi
    echo "✅ Dépendances OK"
    return 0
}

# Si exécuté directement avec une commande
if [ "$0" = "${BASH_SOURCE[0]}" ]; then
    # Activer le venv
    activate_venv || exit 1
    check_dependencies || exit 1
    
    # Exécuter la commande passée en argument
    if [ $# -eq 0 ]; then
        echo "Usage: $0 [commande]"
        echo "Exemple: $0 python run_pipeline.py"
        exit 1
    fi
    
    echo "🚀 Exécution: $@"
    exec "$@"
fi

# Si sourcé, exporter les fonctions pour usage dans d'autres scripts
export -f activate_venv
export -f check_dependencies
export VENV_PATH
export PROJECT_ROOT
