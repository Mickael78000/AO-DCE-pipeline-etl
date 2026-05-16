"""
ao_etl/match.py — Indexation des fichiers HTML et matching CSV <-> fichier.
N'importe que config. Aucune dépendance vers extract, detect ou transform.
"""

import logging
import re
from pathlib import Path

from ao_etl.config import WORKDIR

log = logging.getLogger(__name__)


def build_file_index(
    workdir: Path,
    html_cache: "dict[Path, dict] | None" = None,
) -> dict[str, Path]:
    """
    Index ref -> Path.
    Clés indexées pour chaque fichier :
    - stem complet
    - préfixe court (3boampXXX, ao-XXX-1, NN-NNNNN)
    - identifiant interne BOAMP/DGFIP si html_cache fourni
    """
    index: dict[str, Path] = {}
    for f in workdir.glob("*.html"):
        stem = f.stem
        index[stem] = f
        for pattern in [
            r"^((?:3boamp|13joue|36parisien|37ao)\d+)",
            r"^(ao-\d+-\d+)",
            r"^(\d+-\d+)",
        ]:
            mp = re.match(pattern, stem)
            if mp:
                index[mp.group(1)] = f
                break
    if html_cache:
        for path, data in html_cache.items():
            iref = data.get("_internal_ref", "").strip()
            if iref and iref not in index:
                index[iref] = path
                log.debug("Index internal_ref : %r -> %s", iref, path.name)
    return index


def match_row_to_file(
    row: dict,
    file_index: dict[str, Path],
    html_cache: dict[Path, dict],
    workdir: Path = WORKDIR,
) -> "Path | None":
    """
    Priorité décroissante :
    1. match_source exact (nom de fichier connu)
    2. Référence exacte dans l'index (stem, préfixe court ou internal_ref)
    3. Identifiant interne BOAMP via scan du cache (sécurité si index incomplet)
    4. Fuzzy très contrôlé : sous-chaîne uniquement si len >= 10
       ET ratio de couverture >= 0.8 (évite les préfixes courts ambigus)
    """
    ref    = row.get("Référence", "").strip()
    source = row.get("match_source", row.get("Source", "")).strip()

    # 1. match_source exact
    if source:
        p = workdir / source
        if p.exists():
            log.debug("Match source exact : %r", source)
            return p
        stem = Path(source).stem
        if stem in file_index:
            log.debug("Match source stem : %r", stem)
            return file_index[stem]

    # Normalise ref : retire les suffixes de type "(1re occurrence)"
    ref_norm = re.sub(r"\s*[\(\[].*", "", ref).strip()

    # 2. Référence exacte dans l'index
    if ref_norm in file_index:
        log.debug("Match exact : %r -> %s", ref_norm, file_index[ref_norm].name)
        return file_index[ref_norm]

    # 3. Identifiant interne BOAMP (scan du cache — sécurité)
    for path, data in html_cache.items():
        iref = data.get("_internal_ref", "").strip()
        if iref and iref == ref_norm:
            log.debug("Match internal_ref : %r -> %s", ref_norm, path.name)
            return path

    # 4. Fuzzy très contrôlé : longueur >= 10 ET ratio >= 0.8
    ref_lo = ref_norm.lower()
    if len(ref_lo) >= 10:
        for key, path in file_index.items():
            klo = key.lower()
            if len(klo) < 10:
                continue
            if ref_lo in klo or klo in ref_lo:
                shorter = min(len(ref_lo), len(klo))
                longer  = max(len(ref_lo), len(klo))
                if shorter / longer >= 0.8:
                    log.debug("Match fuzzy : %r ~ %r -> %s", ref_norm, key, path.name)
                    return path

    log.debug("Pas de match : %r", ref_norm)
    return None
