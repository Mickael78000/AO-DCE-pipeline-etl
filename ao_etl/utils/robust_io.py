"""Utilitaires I/O robustes avec retry et gestion d'erreurs."""

import logging
import time
from pathlib import Path
from typing import Optional, Callable, Any
from functools import wraps

log = logging.getLogger(__name__)


def retry_on_error(max_retries: int = 3, delay: float = 0.5, 
                   exceptions: tuple = (Exception,)):
    """Décorateur pour retry une fonction en cas d'erreur."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)  # Backoff exponentiel
                        log.warning(f"{func.__name__} échoué (tentative {attempt + 1}/{max_retries}): {e}. Retry dans {wait_time:.1f}s...")
                        time.sleep(wait_time)
                    else:
                        log.error(f"{func.__name__} échoué après {max_retries} tentatives: {e}")
                        raise last_error
            return None
        return wrapper
    return decorator


@retry_on_error(max_retries=3, delay=0.5, exceptions=(IOError, OSError))
def safe_read_file(filepath: Path, encoding: str = 'utf-8') -> str:
    """Lecture sécurisée d'un fichier avec retry."""
    with open(filepath, 'r', encoding=encoding) as f:
        return f.read()


@retry_on_error(max_retries=3, delay=0.5, exceptions=(IOError, OSError))
def safe_write_file(filepath: Path, content: str, encoding: str = 'utf-8') -> None:
    """Écriture sécurisée avec création des dossiers parents si nécessaire."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    # Écriture atomique (temporaire puis rename)
    temp_path = filepath.with_suffix('.tmp')
    with open(temp_path, 'w', encoding=encoding) as f:
        f.write(content)
    temp_path.rename(filepath)


def safe_csv_read(filepath: Path, encoding: str = 'utf-8') -> tuple[list, list]:
    """Lecture CSV robuste avec gestion d'encodage."""
    import csv
    
    encodings_to_try = [encoding, 'utf-8-sig', 'latin-1', 'cp1252']
    
    for enc in encodings_to_try:
        try:
            with open(filepath, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                rows = list(reader)
                log.info(f"CSV lu avec encodage {enc}: {len(rows)} lignes")
                return rows, fieldnames
        except UnicodeDecodeError:
            continue
        except Exception as e:
            log.warning(f"Échec lecture avec {enc}: {e}")
            continue
    
    raise IOError(f"Impossible de lire {filepath} avec aucun encodage")


def safe_csv_write(filepath: Path, rows: list, fieldnames: list) -> None:
    """Écriture CSV atomique."""
    import csv
    
    filepath.parent.mkdir(parents=True, exist_ok=True)
    temp_path = filepath.with_suffix('.tmp')
    
    with open(temp_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    temp_path.rename(filepath)
    log.info(f"CSV écrit: {filepath} ({len(rows)} lignes)")
