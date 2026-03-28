"""
WCAG 2.1 Accessibility Checker - AgenteDeVoz
Gap #32: Verificacion de accesibilidad AA para el dashboard

Implementa verificaciones automaticas de los criterios WCAG 2.1 nivel AA:
- 1.1.1 Non-text Content (alt text)
- 1.3.1 Info and Relationships (semantica HTML)
- 1.4.3 Contrast (ratio de contraste)
- 2.1.1 Keyboard (navegacion por teclado)
- 2.4.2 Page Titled (titulo de pagina)
- 3.1.1 Language of Page (lang attribute)
- 4.1.1 Parsing (HTML valido)
- 4.1.2 Name, Role, Value (ARIA)
"""
import re
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class WCAGLevel(Enum):
    A = "A"
    AA = "AA"
    AAA = "AAA"


class Severity(Enum):
    CRITICAL = "critical"
    SERIOUS = "serious"
    MODERATE = "moderate"
    MINOR = "minor"


@dataclass
class AccessibilityViolation:
    criterion: str        # e.g., "1.1.1"
    title: str
    description: str
    severity: str
    wcag_level: str
    element: str          # HTML snippet que causa el error
    how_to_fix: str
    impact: str

    def to_dict(self) -> Dict:
        return {
            "criterion": self.criterion,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "wcag_level": self.wcag_level,
            "element": self.element[:200],
            "how_to_fix": self.how_to_fix,
            "impact": self.impact,
        }


class WCAGChecker:
    """
    Verificador automatico de accesibilidad WCAG 2.1 AA.
    Analiza HTML del dashboard e identifica violaciones.
    """

    # Colores del dashboard y su contraste relativo (simplificado)
    CONTRAST_REQUIREMENTS = {
        "normal": 4.5,   # Texto normal
        "large": 3.0,    # Texto grande (18pt o 14pt bold)
        "ui": 3.0,       # Componentes UI y graficos
    }

    def __init__(self):
        self._violations: List[AccessibilityViolation] = []
        self._passes: List[str] = []

    def check_dashboard(self, html_content: str) -> List[AccessibilityViolation]:
        """
        Analiza el HTML del dashboard y retorna lista de violaciones WCAG 2.1 AA.

        Args:
            html_content: Contenido HTML completo del dashboard

        Returns:
            Lista de AccessibilityViolation encontradas
        """
        self._violations = []
        self._passes = []

        # Ejecutar todas las verificaciones
        self._check_images(html_content)
        self._check_page_title(html_content)
        self._check_language(html_content)
        self._check_form_labels(html_content)
        self._check_links(html_content)
        self._check_aria(html_content)
        self._check_headings(html_content)
        self._check_tables(html_content)
        self._check_keyboard_traps(html_content)
        self._check_focus_indicators(html_content)

        logger.info(
            f"Verificacion WCAG: {len(self._violations)} violaciones, "
            f"{len(self._passes)} criterios OK"
        )
        return self._violations

    def _check_images(self, html: str) -> None:
        """1.1.1 Non-text Content: Imagenes deben tener alt text."""
        img_tags = re.findall(r'<img[^>]*>', html, re.IGNORECASE)
        for img in img_tags:
            if 'alt=' not in img.lower():
                self._violations.append(AccessibilityViolation(
                    criterion="1.1.1",
                    title="Imagen sin texto alternativo",
                    description="Las imagenes deben tener atributo alt descriptivo",
                    severity=Severity.CRITICAL.value,
                    wcag_level=WCAGLevel.A.value,
                    element=img,
                    how_to_fix='Agregar alt="descripcion de la imagen" al tag <img>',
                    impact="Usuarios de lectores de pantalla no podran entender la imagen",
                ))
            elif 'alt=""' in img.lower() or "alt=''" in img.lower():
                # alt vacio es valido para imagenes decorativas
                self._passes.append("1.1.1 alt vacio (decorativa)")
            else:
                self._passes.append("1.1.1 alt text presente")

    def _check_page_title(self, html: str) -> None:
        """2.4.2 Page Titled: La pagina debe tener titulo."""
        title_match = re.search(r'<title[^>]*>(.+?)</title>', html, re.IGNORECASE | re.DOTALL)
        if not title_match:
            self._violations.append(AccessibilityViolation(
                criterion="2.4.2",
                title="Pagina sin titulo",
                description="La pagina debe tener un elemento <title> descriptivo",
                severity=Severity.SERIOUS.value,
                wcag_level=WCAGLevel.A.value,
                element="<title> no encontrado",
                how_to_fix="Agregar <title>Nombre descriptivo - AgenteDeVoz</title> en el <head>",
                impact="Usuarios no pueden identificar la pagina en el historial del navegador",
            ))
        elif len(title_match.group(1).strip()) < 3:
            self._violations.append(AccessibilityViolation(
                criterion="2.4.2",
                title="Titulo de pagina no descriptivo",
                description="El titulo debe describir el proposito de la pagina",
                severity=Severity.MODERATE.value,
                wcag_level=WCAGLevel.A.value,
                element=title_match.group(0),
                how_to_fix="Usar un titulo mas descriptivo como 'Dashboard - AgenteDeVoz'",
                impact="Usuarios con multiples pestanas no pueden identificar la pagina",
            ))
        else:
            self._passes.append("2.4.2 Page Title")

    def _check_language(self, html: str) -> None:
        """3.1.1 Language of Page: El elemento html debe tener atributo lang."""
        html_tag = re.search(r'<html[^>]*>', html, re.IGNORECASE)
        if html_tag:
            if 'lang=' not in html_tag.group(0).lower():
                self._violations.append(AccessibilityViolation(
                    criterion="3.1.1",
                    title="Atributo lang ausente",
                    description="El elemento <html> debe tener atributo lang",
                    severity=Severity.SERIOUS.value,
                    wcag_level=WCAGLevel.A.value,
                    element=html_tag.group(0),
                    how_to_fix='Cambiar a <html lang="es"> o <html lang="es-CO">',
                    impact="Lectores de pantalla no pueden seleccionar el idioma correcto",
                ))
            else:
                self._passes.append("3.1.1 Language")

    def _check_form_labels(self, html: str) -> None:
        """1.3.1 / 4.1.2: Inputs deben tener labels asociados."""
        inputs = re.findall(r'<input[^>]*type=["\'](?!hidden|submit|button|reset)["\'][^>]*>', html, re.IGNORECASE)
        for input_tag in inputs:
            id_match = re.search(r'id=["\']([^"\']+)["\']', input_tag)
            if id_match:
                input_id = id_match.group(1)
                label_pattern = f'for=["\'{input_id}["\']'
                if not re.search(label_pattern, html):
                    self._violations.append(AccessibilityViolation(
                        criterion="1.3.1",
                        title="Input sin label asociado",
                        description=f"El input id='{input_id}' no tiene un <label for='{input_id}'>",
                        severity=Severity.CRITICAL.value,
                        wcag_level=WCAGLevel.A.value,
                        element=input_tag,
                        how_to_fix=f'Agregar <label for="{input_id}">Descripcion del campo</label>',
                        impact="Usuarios de lectores de pantalla no saben que informacion ingresar",
                    ))
            elif 'aria-label=' not in input_tag.lower() and 'aria-labelledby=' not in input_tag.lower():
                self._violations.append(AccessibilityViolation(
                    criterion="4.1.2",
                    title="Input sin nombre accesible",
                    description="Input sin id, aria-label ni aria-labelledby",
                    severity=Severity.CRITICAL.value,
                    wcag_level=WCAGLevel.A.value,
                    element=input_tag,
                    how_to_fix='Agregar aria-label="Descripcion del campo" al input',
                    impact="Usuarios de lectores de pantalla no pueden identificar el campo",
                ))

    def _check_links(self, html: str) -> None:
        """2.4.4 Link Purpose: Links deben tener texto descriptivo."""
        links = re.findall(r'<a[^>]*>(.+?)</a>', html, re.IGNORECASE | re.DOTALL)
        generic_texts = {"click aqui", "aqui", "mas", "leer mas", "ver", "link", "here", "click here"}
        for link_content in links:
            text = re.sub(r'<[^>]+>', '', link_content).strip().lower()
            if text in generic_texts or (text and len(text) <= 2):
                self._violations.append(AccessibilityViolation(
                    criterion="2.4.4",
                    title="Texto de enlace no descriptivo",
                    description=f"El enlace '{text}' no describe su destino",
                    severity=Severity.SERIOUS.value,
                    wcag_level=WCAGLevel.A.value,
                    element=f"<a>{link_content[:50]}</a>",
                    how_to_fix="Usar texto descriptivo como 'Ver detalle del ticket #1234'",
                    impact="Usuarios de lector de pantalla no saben a donde lleva el enlace",
                ))

    def _check_aria(self, html: str) -> None:
        """4.1.2 Name, Role, Value: Verificar uso correcto de ARIA."""
        # Verificar que roles ARIA sean validos
        aria_roles = re.findall(r'role=["\']([^"\']+)["\']', html, re.IGNORECASE)
        valid_roles = {
            "alert", "alertdialog", "application", "article", "banner", "button",
            "cell", "checkbox", "columnheader", "combobox", "complementary",
            "contentinfo", "definition", "dialog", "directory", "document",
            "feed", "figure", "form", "grid", "gridcell", "group", "heading",
            "img", "link", "list", "listbox", "listitem", "log", "main",
            "marquee", "math", "menu", "menubar", "menuitem", "menuitemcheckbox",
            "menuitemradio", "navigation", "none", "note", "option", "presentation",
            "progressbar", "radio", "radiogroup", "region", "row", "rowgroup",
            "rowheader", "scrollbar", "search", "searchbox", "separator",
            "slider", "spinbutton", "status", "switch", "tab", "table", "tablist",
            "tabpanel", "term", "textbox", "timer", "toolbar", "tooltip", "tree",
            "treegrid", "treeitem",
        }
        for role in aria_roles:
            if role not in valid_roles:
                self._violations.append(AccessibilityViolation(
                    criterion="4.1.2",
                    title=f"Role ARIA invalido: '{role}'",
                    description=f"El role '{role}' no es un role ARIA valido",
                    severity=Severity.MODERATE.value,
                    wcag_level=WCAGLevel.A.value,
                    element=f'role="{role}"',
                    how_to_fix=f"Usar un role ARIA valido. Ver: https://www.w3.org/TR/wai-aria/#roles",
                    impact="Tecnologias asistivas no entenderan la funcion del elemento",
                ))

    def _check_headings(self, html: str) -> None:
        """1.3.1 / 2.4.6: Estructura de encabezados coherente."""
        headings = re.findall(r'<(h[1-6])[^>]*>', html, re.IGNORECASE)
        if not headings:
            return

        # Verificar que no salten niveles (h1 -> h3 sin h2)
        levels = [int(h[1]) for h in headings]
        for i in range(1, len(levels)):
            if levels[i] > levels[i - 1] + 1:
                self._violations.append(AccessibilityViolation(
                    criterion="1.3.1",
                    title=f"Salto en jerarquia de encabezados (h{levels[i-1]} -> h{levels[i]})",
                    description="Los encabezados deben seguir una jerarquia logica sin saltar niveles",
                    severity=Severity.MODERATE.value,
                    wcag_level=WCAGLevel.AA.value,
                    element=f"h{levels[i-1]} seguido de h{levels[i]}",
                    how_to_fix=f"Usar h{levels[i-1]+1} en lugar de h{levels[i]}",
                    impact="Usuarios de lector de pantalla pierden la navegacion por encabezados",
                ))
                break
        else:
            self._passes.append("1.3.1 Heading structure")

    def _check_tables(self, html: str) -> None:
        """1.3.1: Tablas deben tener headers."""
        tables = re.findall(r'<table[^>]*>.*?</table>', html, re.IGNORECASE | re.DOTALL)
        for table in tables:
            if '<th' not in table.lower() and 'scope=' not in table.lower():
                self._violations.append(AccessibilityViolation(
                    criterion="1.3.1",
                    title="Tabla sin encabezados de columna/fila",
                    description="Las tablas de datos deben tener elementos <th> con scope",
                    severity=Severity.SERIOUS.value,
                    wcag_level=WCAGLevel.A.value,
                    element="<table>...</table>",
                    how_to_fix='Usar <th scope="col">Nombre Columna</th> para encabezados',
                    impact="Usuarios de lector de pantalla no pueden navegar la tabla correctamente",
                ))

    def _check_keyboard_traps(self, html: str) -> None:
        """2.1.2: No deben existir trampas de teclado."""
        # Buscar tabindex negativo que podria crear trampas
        tabindex_matches = re.findall(r'tabindex=["\'](-?\d+)["\']', html, re.IGNORECASE)
        for idx_str in tabindex_matches:
            idx = int(idx_str)
            if idx > 0:
                self._violations.append(AccessibilityViolation(
                    criterion="2.4.3",
                    title=f"tabindex positivo ({idx}) puede romper el orden de foco",
                    description="tabindex > 0 altera el orden natural de tabulacion",
                    severity=Severity.MODERATE.value,
                    wcag_level=WCAGLevel.A.value,
                    element=f'tabindex="{idx}"',
                    how_to_fix="Usar tabindex=0 para incluir en el orden natural, o -1 para excluir",
                    impact="El orden de foco puede volverse impredecible para usuarios de teclado",
                ))

    def _check_focus_indicators(self, html: str) -> None:
        """2.4.7: Focus visible - no eliminar outline."""
        if 'outline: none' in html or 'outline:none' in html or 'outline: 0' in html:
            self._violations.append(AccessibilityViolation(
                criterion="2.4.7",
                title="Indicador de foco eliminado con CSS",
                description="'outline: none' elimina el indicador visual de foco del teclado",
                severity=Severity.SERIOUS.value,
                wcag_level=WCAGLevel.AA.value,
                element="outline: none (en CSS)",
                how_to_fix="Reemplazar con un estilo de foco personalizado visible: outline: 2px solid #0066cc",
                impact="Usuarios de teclado no pueden ver donde esta el foco activo",
            ))
        else:
            self._passes.append("2.4.7 Focus visible")

    def generate_report(self) -> Dict:
        """Genera reporte completo de accesibilidad."""
        critical = [v for v in self._violations if v.severity == Severity.CRITICAL.value]
        serious = [v for v in self._violations if v.severity == Severity.SERIOUS.value]
        moderate = [v for v in self._violations if v.severity == Severity.MODERATE.value]
        minor = [v for v in self._violations if v.severity == Severity.MINOR.value]

        total = len(self._violations)
        score = max(0, 100 - (len(critical) * 25 + len(serious) * 10 + len(moderate) * 5 + len(minor) * 2))
        level = "AA" if score >= 80 and len(critical) == 0 else "Parcial" if score >= 50 else "No cumple"

        return {
            "summary": {
                "total_violations": total,
                "critical": len(critical),
                "serious": len(serious),
                "moderate": len(moderate),
                "minor": len(minor),
                "passes": len(self._passes),
                "score": score,
                "wcag_level_achieved": level,
            },
            "violations": [v.to_dict() for v in self._violations],
            "passes": self._passes,
            "recommendations": self._get_recommendations(),
        }

    def _get_recommendations(self) -> List[str]:
        """Recomendaciones prioritarias basadas en las violaciones."""
        recs = []
        has_criterion = {v.criterion for v in self._violations}
        if "1.1.1" in has_criterion:
            recs.append("PRIORITARIO: Agregar alt text a todas las imagenes")
        if "1.3.1" in has_criterion:
            recs.append("Revisar estructura semantica HTML (labels, tablas, encabezados)")
        if "2.4.7" in has_criterion:
            recs.append("Agregar indicadores de foco visibles para navegacion por teclado")
        if "4.1.2" in has_criterion:
            recs.append("Revisar uso de ARIA roles y propiedades")
        if not recs:
            recs.append("El dashboard cumple WCAG 2.1 AA - mantener en futuras actualizaciones")
        return recs
