"""Utilitaires de validation et nettoyage pour l'extraction de données.

Ce module fournit des fonctions pour valider et nettoyer les données extraites,
avec des listes noires de faux positifs connus.
"""

import re
from typing import Optional

# =============================================================================
# BLACKLISTS - Titres génériques à rejeter
# =============================================================================

TITLE_BLACKLIST = {
    # Génériques - NE JAMAIS prendre comme titre final
    "Détail de la consultation",
    "Détail d'une consultation",
    "Titre",
    "Accord",
    "Fourniture",
    "Prestations de support",
    "Prestations",
    "Consultation",
    "Marché",
    "Appel d'offres",
    "Appel d'offre",
    "TMA",  # Trop générique seul
    "Prestation",  # Singulier générique
    # Placeholders
    "-",
    "",
    "...",
    "N/A",
    "Non disponible",
    "Non précisé",
    # Textes d'interface UI à rejeter
    "Aller au menu",
    "Aller au contenu",
    "Aller au menuAller au contenu",
}

# Patterns de titres trop courts ou génériques
TITLE_REJECT_PATTERNS = [
    r'^Prestations?\s+de\s+support$',
    r'^Accord\s+cadre$',
    r'^Fourniture\s*$',
    r'^Détail\s+de',
    r'^Titre\s*:?\s*$',
    # Textes DUME / helper d'interface PLACE
    r'^Je ne suis pas en charge',
    r'^Je réponds en candidat',
    r'^Aller au (menu|contenu)',
    # Dates/labels de champs qui peuvent remonter comme faux titres
    r'^Date (et heure |limite|de cl)',
    r'^\d{2}/\d{2}/\d{4}',
]

# =============================================================================
# BLACKLISTS - Acheteurs (catégories administratives, pas des noms)
# =============================================================================

BUYER_BLACKLIST = {
    # Catégories administratives - NE JAMAIS prendre comme acheteur final
    "Autres organismes",
    "Autorité publique centrale",
    "Autorité locale",
    "Autorité régionale",
    "Organisme de droit public",
    "Services d'administration générale",
    "Santé",
    "Protection de l'environnement",
    "Loisirs, culture et culte",
    "Services publics",
    "État",
    "Territoriale",
    "Hospitalière",
    # Rôles organisationnels (pas des noms)
    "Entreprise publique, contrôlée par une autorité publique centrale",
    "Etablissements et organismes de l'enseignement supérieur, de la recherche et de l'innovation",
    "TED eSender",
    "Organisation qui fournit des informations complémentaires",
    "TED-OP",
    "Organisation qui fournit les formulaires pour la réponse",
    "Organisme qui fournit les formulaires pour la réponse",
    # Génériques
    "Acheteur",
    "Organisme",
    "Organisation",
    "Autorité",
    "Administration",
    "Collectivité",
    # Placeholders
    "-",
    "",
    "...",
    "N/A",
    "Non identifié",
    "Acheteur non identifié",
    "Acheteur non clairement identifié",
    "Acheteur non clairement identifié dans l'extrait",
    "Acheteur non identifié dans l'extrait",
    "Organisme non identifié",
    "Organisme non identifié dans l'extrait",
    "Ville de ...",
    "Ville de ...",  # Placeholder ville
    # URLs (signe d'erreur d'extraction)
    "https://",
    "http://",
    "www.",
    # Textes d'interface UI (navigation, listes)
    "Retour à la liste",
    "Aller au menu",
    "Aller au contenu",
}

# Patterns pour détecter les catégories administratives
BUYER_REJECT_PATTERNS = [
    r'^Autres?\s+',
    r'^Activité\s+du',
    r'^Forme\s+juridique',
    r'^Organisme\s+de\s+droit',
    r'^Services?\s+d\'administration',
    r'^Autorité\s+',
    r'^Organisation\s+qui\s+fournit',
    r'^Organisme\s+qui\s+fournit',
    r'^Etablissements?\s+et\s+organismes',
    r'^Entreprise\s+publique',
    r'^TED\s+',
]

# =============================================================================
# FONCTIONS DE VALIDATION
# =============================================================================

def is_valid_title(title: Optional[str]) -> bool:
    """Vérifie si un titre est valide (pas un faux positif).
    
    Args:
        title: Titre candidat à valider
        
    Returns:
        True si le titre est valide, False sinon
    """
    if not title:
        return False
    
    title_clean = title.strip()
    
    # Rejeter les titres vides ou trop courts
    if len(title_clean) < 10:
        return False
    
    # Rejeter les titres dans la blacklist exacte
    if title_clean in TITLE_BLACKLIST:
        return False
    
    # Rejeter les titres correspondant aux patterns
    for pattern in TITLE_REJECT_PATTERNS:
        if re.match(pattern, title_clean, re.IGNORECASE):
            return False
    
    return True


def is_valid_buyer(buyer: Optional[str]) -> bool:
    """Vérifie si un acheteur est valide (pas une catégorie administrative).
    
    Args:
        buyer: Nom d'acheteur candidat à valider
        
    Returns:
        True si l'acheteur est valide, False sinon
    """
    if not buyer:
        return False
    
    buyer_clean = buyer.strip()
    
    # Rejeter les acheteurs vides ou trop courts
    if len(buyer_clean) < 3:
        return False
    
    # Rejeter les acheteurs dans la blacklist exacte
    if buyer_clean in BUYER_BLACKLIST:
        return False
    
    # Rejeter les URLs
    if buyer_clean.startswith(('http://', 'https://', 'www.')):
        return False
    
    # Rejeter les catégories correspondant aux patterns
    for pattern in BUYER_REJECT_PATTERNS:
        if re.match(pattern, buyer_clean, re.IGNORECASE):
            return False
    
    # Vérifier que ce n'est pas juste une catégorie entre parenthèses
    if re.match(r'^\([^)]+\)$', buyer_clean):
        return False
    
    return True


def clean_text(text: Optional[str]) -> str:
    """Nettoie le texte extrait (espaces, sauts de ligne, ponctuation).
    
    Args:
        text: Texte brut à nettoyer
        
    Returns:
        Texte nettoyé
    """
    if not text:
        return ""
    
    # Supprimer les balises HTML résiduelles
    text = re.sub(r'<[^>]+>', '', text)
    
    # Normaliser les espaces
    text = ' '.join(text.split())
    
    # Supprimer les espaces autour
    text = text.strip()
    
    # Supprimer la ponctuation finale excessive
    text = re.sub(r'[.]{3,}$', '...', text)
    
    return text


def pick_best_candidate(candidates: list[str], 
                        validator_func,
                        prefer_longer: bool = True) -> Optional[str]:
    """Sélectionne le meilleur candidat parmi une liste.
    
    Args:
        candidates: Liste de candidats à évaluer
        validator_func: Fonction de validation (is_valid_title ou is_valid_buyer)
        prefer_longer: Si True, privilégie les textes plus longs (moins génériques)
        
    Returns:
        Meilleur candidat valide, ou None si aucun n'est valide
    """
    valid_candidates = []
    
    for candidate in candidates:
        cleaned = clean_text(candidate)
        if validator_func(cleaned):
            valid_candidates.append(cleaned)
    
    if not valid_candidates:
        return None
    
    if prefer_longer:
        # Trier par longueur décroissante (plus long = plus spécifique)
        valid_candidates.sort(key=len, reverse=True)
    
    return valid_candidates[0]


# =============================================================================
# FONCTIONS DE TRAÇABILITÉ
# =============================================================================

def log_extraction_rule(notes: list, field: str, rule: str, value: str) -> None:
    """Ajoute une note de traçabilité pour une règle d'extraction.
    
    Args:
        notes: Liste de notes à enrichir
        field: Nom du champ (title, buyer, etc.)
        rule: Nom de la règle appliquée
        value: Valeur extraite
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    notes.append(f"[{timestamp}] {field}: {rule} → '{value[:50]}...'" if len(value) > 50 
                 else f"[{timestamp}] {field}: {rule} → '{value}'")
