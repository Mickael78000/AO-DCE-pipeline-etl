#!/usr/bin/env python3
"""
Audit de contamination des extractions HTML
Vérifie que les champs extraits proviennent strictement du marché principal
et non de blocs annexes (avis similaires, recommandations, etc.)
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


@dataclass
class ContaminationDiagnostic:
    """Diagnostic de contamination pour un champ extrait."""
    reference: str
    champ_concerne: str
    valeur_extraite: str
    source_dom: str
    appartient_au_marche_principal: bool
    source_annexe_detectee: bool
    type_source_annexe: str
    risque_contamination: str  # faible/moyen/fort
    impact_sur_classification: str
    correction_recommandee: str


@dataclass
class AuditResult:
    """Résultat complet de l'audit pour un fichier HTML."""
    fichier: str
    reference_marche: str
    verdict_global: str  # PROPRE / PARTIELLEMENT_CONTAMINE / CONTAMINE
    diagnostics: list[ContaminationDiagnostic] = field(default_factory=list)
    zones_annexes_detectees: list[str] = field(default_factory=list)
    marche_principal_boundary: dict[str, Any] = field(default_factory=dict)


class HTMLContaminationAuditor:
    """Auditeur de contamination pour fichiers HTML de marchés publics."""

    # Patterns pour détecter les zones annexes
    ZONES_ANNEXES_PATTERNS = [
        (r"avis\s+similaires?", "avis_similaires"),
        (r"ces\s+avis\s+peuvent\s+vous\s+int[ée]resser", "recommandations"),
        (r"avis\s+du\s+m[êe]me\s+domaine", "meme_domaine"),
        (r"recevoir\s+des\s+avis\s+similaires", "alerte_similaires"),
        (r"voir\s+les\s+avis\s+similaires", "lien_similaires"),
        (r"vous\s+pourriez\s+[eê]tre\s+int[ée]ress[ée]", "suggestion"),
        (r"autres\s+avis", "autres_avis"),
        (r"march[ée]s\s+similaires", "marches_similaires"),
        (r"consultations?\s+similaires?", "consultations_similaires"),
    ]

    # Patterns pour identifier le conteneur principal selon le type de source
    MAIN_CONTAINERS = {
        "MARCHES_ONLINE": [
            {"selector": "div#detail_ao", "type": "id"},
            {"selector": "main#main-content", "type": "id"},
            {"selector": "div.refonte", "type": "class"},
            {"selector": "h1.title-avis", "type": "nearest_section"},
        ],
        "PLACE": [
            {"selector": "div#recap-consultation", "type": "id"},
            {"selector": "div.recap-infos-consultation", "type": "class"},
            {"selector": "div.panel-heading", "type": "nearest_section"},
        ],
        "BOAMP": [
            {"selector": "div.bloc-detail-annonce", "type": "class"},
            {"selector": "div#detailAnnonce", "type": "id"},
            {"selector": "main", "type": "tag"},
        ],
        "FRANCE_MARCHES": [
            {"selector": "div.detail-avis", "type": "class"},
            {"selector": "div#contenu", "type": "id"},
            {"selector": "article", "type": "tag"},
        ],
    }

    def __init__(self, html_path: Path):
        self.html_path = html_path
        self.html_content = html_path.read_text(encoding="utf-8")
        self.soup = BeautifulSoup(self.html_content, "html.parser")
        self.source_type = self._detect_source_type()
        self.main_container = self._identify_main_container()

    def _detect_source_type(self) -> str:
        """Détecte le type de source HTML."""
        text = self.soup.get_text("\n", strip=True).lower()
        name = self.html_path.name.lower()
        html_lower = self.html_content.lower()

        if (name.startswith("ao-") or
            "marchesonline" in html_lower or
            "title-avis" in html_lower):
            return "MARCHES_ONLINE"

        if "orgacronyme" in name or ("détail de la consultation" in text and "heure de paris" in text):
            return "PLACE"

        if ("marches-publics.gouv.fr" in html_lower or
            ("identifiant interne" in text and "nom officiel" in text)):
            return "BOAMP"

        if ("intitulé de l'appel d'offre public" in text or
            "weboramaitemtag" in html_lower):
            return "FRANCE_MARCHES"

        return "UNKNOWN"

    def _identify_main_container(self) -> Tag | None:
        """Identifie le conteneur DOM du marché principal."""
        configs = self.MAIN_CONTAINERS.get(self.source_type, [])

        for config in configs:
            selector = config["selector"]
            sel_type = config["type"]

            if sel_type == "id":
                elem = self.soup.select_one(selector)
                if elem:
                    return elem
            elif sel_type == "class":
                elems = self.soup.find_all(class_=selector.replace(".", "").replace("div", "").strip())
                if elems:
                    # Prendre le premier qui contient une référence au marché
                    for elem in elems:
                        text = elem.get_text(" ", strip=True).lower()
                        if any(kw in text for kw in ["appel d'offres", "marché", "consultation", "référence"]):
                            return elem
                    return elems[0]
            elif sel_type == "tag":
                elems = self.soup.find_all(selector)
                if elems:
                    return elems[0]
            elif sel_type == "nearest_section":
                # Trouver l'élément et remonter à sa section parente
                elem = self.soup.select_one(selector)
                if elem:
                    for parent in elem.parents:
                        if parent.name in ["section", "div", "main", "article"]:
                            return parent
                    return elem

        # Fallback: body
        return self.soup.body

    def detect_annex_zones(self) -> list[tuple[str, Tag]]:
        """Détecte toutes les zones annexes dans le document."""
        annexes = []
        text_content = self.soup.get_text("\n", strip=True)

        for pattern, zone_type in self.ZONES_ANNEXES_PATTERNS:
            matches = list(re.finditer(pattern, text_content, re.IGNORECASE))
            for match in matches:
                # Trouver l'élément DOM correspondant
                text_before = text_content[:match.start()]
                lines_before = text_before.count("\n")

                # Chercher un conteneur proche
                for elem in self.soup.find_all(text=re.compile(pattern, re.I)):
                    parent = elem.parent
                    for _ in range(5):  # Remonter jusqu'à 5 niveaux
                        if parent and parent.name in ["div", "section", "aside"]:
                            # Vérifier si ce parent est en dehors du conteneur principal
                            if self.main_container and parent != self.main_container:
                                if not self._is_inside(parent, self.main_container):
                                    annexes.append((zone_type, parent))
                                    break
                        parent = parent.parent if parent else None

        return annexes

    def _is_inside(self, child: Tag, parent: Tag) -> bool:
        """Vérifie si child est à l'intérieur de parent."""
        for p in child.parents:
            if p == parent:
                return True
        return False

    def is_inside_main_container(self, elem: Tag) -> bool:
        """Vérifie si un élément est à l'intérieur du conteneur principal."""
        if not self.main_container:
            return True  # Par défaut, considérer comme valide
        return self._is_inside(elem, self.main_container)

    def find_element_by_text(self, text: str, tag_name: str | None = None) -> Tag | None:
        """Trouve un élément contenant le texte spécifié."""
        search_tag = tag_name or ["div", "span", "p", "h1", "h2", "h3", "li", "td"]

        for elem in self.soup.find_all(search_tag, string=re.compile(re.escape(text)[:50], re.I)):
            return elem

        # Recherche plus large dans le texte
        for elem in self.soup.find_all(search_tag):
            if text[:50].lower() in elem.get_text(" ", strip=True).lower():
                return elem
        return None

    def audit_field(self, field_name: str, value: str, extraction_rule: str) -> ContaminationDiagnostic:
        """Audite un champ extrait pour détecter toute contamination."""
        if not value or len(value.strip()) < 2:
            return ContaminationDiagnostic(
                reference=self._extract_reference(),
                champ_concerne=field_name,
                valeur_extraite=value,
                source_dom=extraction_rule,
                appartient_au_marche_principal=True,  # Valeur vide = pas de contamination
                source_annexe_detectee=False,
                type_source_annexe="",
                risque_contamination="faible",
                impact_sur_classification="aucun",
                correction_recommandee="aucune - valeur vide"
            )

        # Chercher l'élément DOM source
        source_elem = self.find_element_by_text(value)
        source_dom = extraction_rule

        if source_elem:
            # Déterminer le chemin DOM
            path = []
            current = source_elem
            for _ in range(5):
                if current:
                    path.append(f"{current.name}" + (f".{'.'.join(current.get('class', []))}" if current.get('class') else ""))
                    current = current.parent
            source_dom = " > ".join(reversed(path)) if path else extraction_rule

            # Vérifier si dans le conteneur principal
            in_main = self.is_inside_main_container(source_elem)

            # Vérifier si dans une zone annexe
            annexes = self.detect_annex_zones()
            in_annex = False
            annex_type = ""

            for zone_type, zone_elem in annexes:
                if self._is_inside(source_elem, zone_elem):
                    in_annex = True
                    annex_type = zone_type
                    break

            # Déterminer le risque
            if in_annex:
                risque = "fort"
                impact = "critique - classification potentiellement invalide"
                correction = f"exclure la zone '{annex_type}' du parsing ou scoper l'extraction au conteneur principal"
            elif not in_main:
                risque = "moyen"
                impact = "élevé - données potentiellement hors contexte"
                correction = "vérifier le sélecteur et limiter au conteneur principal identifié"
            else:
                risque = "faible"
                impact = "aucun"
                correction = "aucune"

            return ContaminationDiagnostic(
                reference=self._extract_reference(),
                champ_concerne=field_name,
                valeur_extraite=value[:100] + "..." if len(value) > 100 else value,
                source_dom=source_dom,
                appartient_au_marche_principal=in_main and not in_annex,
                source_annexe_detectee=in_annex,
                type_source_annexe=annex_type,
                risque_contamination=risque,
                impact_sur_classification=impact,
                correction_recommandee=correction
            )

        # Si élément non trouvé, considérer comme risque moyen (extraction par regex)
        return ContaminationDiagnostic(
            reference=self._extract_reference(),
            champ_concerne=field_name,
            valeur_extraite=value[:100] + "..." if len(value) > 100 else value,
            source_dom=extraction_rule,
            appartient_au_marche_principal=True,  # On suppose que les regex ciblent le bon contenu
            source_annexe_detectee=False,
            type_source_annexe="",
            risque_contamination="moyen",
            impact_sur_classification="extraction par pattern - vérifier la portée",
            correction_recommandee="privilégier l'extraction DOM avec scope sur conteneur principal"
        )

    def _extract_reference(self) -> str:
        """Extrait la référence du marché depuis le HTML."""
        # Patterns par type de source
        text = self.soup.get_text("\n", strip=True)

        patterns = [
            r"Référence\s*[:\s]+([A-Za-z0-9\-]+)",
            r"Identifiant interne\s*[:\s]+([A-Za-z0-9\-]+)",
            r"AO\s*:\s*([A-Za-z0-9\-]+)",
        ]

        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return m.group(1)

        return self.html_path.stem

    def audit_extraction(self, extracted_data: dict[str, str] | None = None) -> AuditResult:
        """Effectue un audit complet de l'extraction."""
        reference = self._extract_reference()
        annexes = self.detect_annex_zones()

        diagnostics = []

        if extracted_data:
            for field_name, value in extracted_data.items():
                if field_name not in ["source_type", "extraction_notes"]:
                    diag = self.audit_field(field_name, value, "extraction_rule")
                    diagnostics.append(diag)
        else:
            # Audit structurel sans données extraites
            diag = ContaminationDiagnostic(
                reference=reference,
                champ_concerne="structure",
                valeur_extraite=f"Source: {self.source_type}",
                source_dom=str(self.main_container.name if self.main_container else "unknown"),
                appartient_au_marche_principal=True,
                source_annexe_detectee=len(annexes) > 0,
                type_source_annexe=", ".join(set(a[0] for a in annexes)) if annexes else "",
                risque_contamination="moyen" if annexes else "faible",
                impact_sur_classification="zones annexes detectees" if annexes else "structure propre",
                correction_recommandee="verifier le scope d'extraction" if annexes else "aucune"
            )
            diagnostics.append(diag)

        # Déterminer le verdict global
        has_contamination = any(d.source_annexe_detectee for d in diagnostics)
        has_risks = any(d.risque_contamination in ["moyen", "fort"] for d in diagnostics)

        if has_contamination:
            verdict = "CONTAMINE"
        elif has_risks:
            verdict = "PARTIELLEMENT_CONTAMINE"
        else:
            verdict = "PROPRE"

        return AuditResult(
            fichier=str(self.html_path),
            reference_marche=reference,
            verdict_global=verdict,
            diagnostics=diagnostics,
            zones_annexes_detectees=list(set(a[0] for a in annexes)),
            marche_principal_boundary={
                "container_tag": self.main_container.name if self.main_container else None,
                "container_class": self.main_container.get("class") if self.main_container else None,
                "container_id": self.main_container.get("id") if self.main_container else None,
            }
        )


def audit_single_file(html_path: Path, extracted_data: dict[str, str] | None = None) -> AuditResult:
    """Audite un seul fichier HTML."""
    auditor = HTMLContaminationAuditor(html_path)
    return auditor.audit_extraction(extracted_data)


def run_audit_on_directory(directory: Path, output_path: Path | None = None) -> list[AuditResult]:
    """Lance l'audit sur tous les fichiers HTML d'un répertoire."""
    results = []

    html_files = list(directory.glob("*.html"))
    print(f"Audit de {len(html_files)} fichiers HTML dans {directory}")

    for html_path in sorted(html_files):
        try:
            result = audit_single_file(html_path)
            results.append(result)
            print(f"  [{result.verdict_global}] {html_path.name}")
        except Exception as e:
            print(f"  [ERREUR] {html_path.name}: {e}")

    # Générer le rapport
    if output_path:
        generate_audit_report(results, output_path)

    return results


def generate_audit_report(results: list[AuditResult], output_path: Path) -> None:
    """Génère un rapport d'audit structuré."""
    report_lines = [
        "# Rapport d'Audit de Contamination des Extractions HTML",
        "",
        "## Résumé Exécutif",
        "",
    ]

    # Statistiques globales
    total = len(results)
    propre = sum(1 for r in results if r.verdict_global == "PROPRE")
    partiel = sum(1 for r in results if r.verdict_global == "PARTIELLEMENT_CONTAMINE")
    contamine = sum(1 for r in results if r.verdict_global == "CONTAMINE")

    report_lines.extend([
        f"- **Total fichiers analysés**: {total}",
        f"- **PROPRE**: {propre} ({propre/total*100:.1f}%)",
        f"- **PARTIELLEMENT_CONTAMINE**: {partiel} ({partiel/total*100:.1f}%)",
        f"- **CONTAMINE**: {contamine} ({contamine/total*100:.1f}%)",
        "",
        "## Détail par Fichier",
        "",
    ])

    for result in results:
        emoji = {"PROPRE": "✅", "PARTIELLEMENT_CONTAMINE": "⚠️", "CONTAMINE": "❌"}.get(result.verdict_global, "❓")
        report_lines.extend([
            f"### {emoji} {result.fichier.split('/')[-1]}",
            "",
            f"- **Référence**: `{result.reference_marche}`",
            f"- **Verdict**: {result.verdict_global}",
            f"- **Zones annexes détectées**: {', '.join(result.zones_annexes_detectees) if result.zones_annexes_detectees else 'Aucune'}",
            "",
        ])

        if result.diagnostics:
            report_lines.append("#### Diagnostics par champ")
            report_lines.append("")
            for diag in result.diagnostics:
                status = "✅" if diag.appartient_au_marche_principal else "❌"
                report_lines.extend([
                    f"- **{status} {diag.champ_concerne}**",
                    f"  - Valeur: `{diag.valeur_extraite[:60]}{'...' if len(diag.valeur_extraite) > 60 else ''}`",
                    f"  - Source DOM: `{diag.source_dom[:60]}`",
                    f"  - Appartient au marché principal: {diag.appartient_au_marche_principal}",
                    f"  - Source annexe: {diag.source_annexe_detectee} ({diag.type_source_annexe})",
                    f"  - Risque: **{diag.risque_contamination}**",
                    f"  - Correction: {diag.correction_recommandee}",
                ])
            report_lines.append("")

    # Recommandations globales
    report_lines.extend([
        "## Recommandations Globales",
        "",
    ])

    if contamine > 0:
        report_lines.extend([
            "### Actions Prioritaires (Fichiers CONTAMINES)",
            "",
            "1. **Restreindre le scope des sélecteurs CSS** aux conteneurs principaux identifiés:",
        ])
        for result in results:
            if result.verdict_global == "CONTAMINE" and result.marche_principal_boundary:
                container = result.marche_principal_boundary
                tag = container.get("container_tag", "div")
                id_attr = container.get("container_id", "N/A")
                class_attr = container.get("container_class", [])
                class_str = ".".join(class_attr) if class_attr else "N/A"
                report_lines.append(f"   - `{result.fichier.split('/')[-1]}`: scoper à `{tag}#{id_attr}` ou `{tag}.{class_str}`")
        report_lines.append("")

    report_lines.extend([
        "### Bonnes Pratiques d'Extraction",
        "",
        "1. **Toujours identifier le conteneur principal** avant d'extraire des champs",
        "2. **Utiliser des sélecteurs descendants** (ex: `#main-container .field-value`)",
        "3. **Exclure explicitement** les zones avec IDs/classes: `avis-similaires`, `recommandations`, `related-content`",
        "4. **Vérifier la cohérence** entre tous les champs extraits (procédure, montant, acheteur, lieu)",
        "5. **Tracer l'origine DOM** de chaque valeur extraite pour l'audit",
        "",
    ])

    output_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nRapport généré: {output_path}")


def main():
    """Point d'entrée principal."""
    if len(sys.argv) < 2:
        print("Usage: python audit_extraction_contamination.py <chemin_fichier_ou_repertoire>")
        print("Exemples:")
        print("  python audit_extraction_contamination.py data/raw/html/ao-9592936-1.html")
        print("  python audit_extraction_contamination.py data/raw/html/")
        sys.exit(1)

    path = Path(sys.argv[1])

    if not path.exists():
        print(f"Erreur: {path} n'existe pas")
        sys.exit(1)

    if path.is_file():
        # Audit d'un seul fichier
        result = audit_single_file(path)
        print(f"\n=== Audit: {path.name} ===")
        print(f"Référence: {result.reference_marche}")
        print(f"Verdict: {result.verdict_global}")
        print(f"Zones annexes: {result.zones_annexes_detectees}")
        print(f"Conteneur principal: {result.marche_principal_boundary}")
        print("\nDiagnostics:")
        for diag in result.diagnostics:
            print(f"  - {diag.champ_concerne}: {diag.risque_contamination}")
            print(f"    Appartient au marché principal: {diag.appartient_au_marche_principal}")
            if diag.source_annexe_detectee:
                print(f"    ⚠️ SOURCE ANNEXE: {diag.type_source_annexe}")
    else:
        # Audit d'un répertoire
        output_path = path.parent / "RAPPORT_AUDIT_CONTAMINATION.md"
        run_audit_on_directory(path, output_path)


if __name__ == "__main__":
    main()
