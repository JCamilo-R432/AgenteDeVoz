"""
Tests para WCAG 2.1 Accessibility Checker (Gap #32)
"""
import pytest
from src.accessibility.wcag_checker import WCAGChecker, AccessibilityViolation, Severity
from src.accessibility.screen_reader_compat import ScreenReaderCompat


VALID_HTML = """<!DOCTYPE html>
<html lang="es">
<head><title>Dashboard AgenteDeVoz - Monitor</title></head>
<body>
<a href="#main-content">Saltar al contenido</a>
<nav aria-label="Principal">
<a href="/dashboard">Ver reporte de conversaciones activas</a>
</nav>
<main id="main-content" tabindex="-1">
<h1>Dashboard</h1>
<h2>Conversaciones</h2>
<img src="logo.png" alt="Logo AgenteDeVoz">
<form>
<label for="search">Buscar ticket</label>
<input id="search" type="text">
</form>
<table>
<thead><tr><th scope="col">ID</th><th scope="col">Estado</th></tr></thead>
<tbody><tr><td>TKT-001</td><td>Abierto</td></tr></tbody>
</table>
</main>
</body>
</html>"""

INVALID_HTML = """<!DOCTYPE html>
<html>
<head></head>
<body>
<img src="chart.png">
<a href="/dashboard">aqui</a>
<input type="text">
<input type="email" id="email">
<table>
<tr><td>ID</td><td>Estado</td></tr>
</table>
<div style="outline: none; outline:none;">contenido</div>
</body>
</html>"""


class TestWCAGChecker:
    def setup_method(self):
        self.checker = WCAGChecker()

    def test_valid_html_has_fewer_violations(self):
        violations = self.checker.check_dashboard(VALID_HTML)
        valid_count = len(violations)

        checker2 = WCAGChecker()
        invalid_violations = checker2.check_dashboard(INVALID_HTML)
        assert len(invalid_violations) >= valid_count

    def test_missing_alt_detected(self):
        violations = self.checker.check_dashboard(INVALID_HTML)
        criterion_ids = [v.criterion for v in violations]
        assert "1.1.1" in criterion_ids

    def test_missing_title_detected(self):
        violations = self.checker.check_dashboard(INVALID_HTML)
        criterion_ids = [v.criterion for v in violations]
        assert "2.4.2" in criterion_ids

    def test_missing_lang_detected(self):
        violations = self.checker.check_dashboard(INVALID_HTML)
        criterion_ids = [v.criterion for v in violations]
        assert "3.1.1" in criterion_ids

    def test_generic_link_text_detected(self):
        violations = self.checker.check_dashboard(INVALID_HTML)
        criterion_ids = [v.criterion for v in violations]
        assert "2.4.4" in criterion_ids

    def test_table_without_headers_detected(self):
        violations = self.checker.check_dashboard(INVALID_HTML)
        criterion_ids = [v.criterion for v in violations]
        assert "1.3.1" in criterion_ids

    def test_outline_none_detected(self):
        violations = self.checker.check_dashboard(INVALID_HTML)
        criterion_ids = [v.criterion for v in violations]
        assert "2.4.7" in criterion_ids

    def test_valid_html_no_title_violation(self):
        violations = self.checker.check_dashboard(VALID_HTML)
        title_violations = [v for v in violations if v.criterion == "2.4.2"]
        assert len(title_violations) == 0

    def test_valid_html_no_lang_violation(self):
        violations = self.checker.check_dashboard(VALID_HTML)
        lang_violations = [v for v in violations if v.criterion == "3.1.1"]
        assert len(lang_violations) == 0

    def test_violation_has_required_fields(self):
        violations = self.checker.check_dashboard(INVALID_HTML)
        assert len(violations) > 0
        v = violations[0]
        assert v.criterion
        assert v.title
        assert v.description
        assert v.severity in [s.value for s in Severity]
        assert v.how_to_fix
        assert v.impact

    def test_generate_report_structure(self):
        self.checker.check_dashboard(INVALID_HTML)
        report = self.checker.generate_report()
        assert "summary" in report
        assert "violations" in report
        assert "recommendations" in report
        assert "total_violations" in report["summary"]
        assert "score" in report["summary"]

    def test_report_score_range(self):
        self.checker.check_dashboard(INVALID_HTML)
        report = self.checker.generate_report()
        score = report["summary"]["score"]
        assert 0 <= score <= 100

    def test_perfect_html_score(self):
        checker = WCAGChecker()
        checker.check_dashboard(VALID_HTML)
        report = checker.generate_report()
        # HTML valido debe tener score mayor que HTML invalido
        checker2 = WCAGChecker()
        checker2.check_dashboard(INVALID_HTML)
        report2 = checker2.generate_report()
        assert report["summary"]["score"] >= report2["summary"]["score"]

    def test_violation_to_dict(self):
        v = AccessibilityViolation(
            criterion="1.1.1",
            title="Test",
            description="Descripcion",
            severity="critical",
            wcag_level="A",
            element="<img>",
            how_to_fix="Agregar alt",
            impact="Lectores de pantalla",
        )
        d = v.to_dict()
        assert d["criterion"] == "1.1.1"
        assert "element" in d

    def test_tabindex_positive_detected(self):
        html_with_tabindex = '<html lang="es"><head><title>Test</title></head><body><div tabindex="5">contenido</div></body></html>'
        violations = self.checker.check_dashboard(html_with_tabindex)
        criterion_ids = [v.criterion for v in violations]
        assert "2.4.3" in criterion_ids


class TestScreenReaderCompat:
    def setup_method(self):
        self.sr = ScreenReaderCompat()

    def test_generate_aria_live_region(self):
        html = self.sr.generate_aria_live_region("notifications")
        assert 'aria-live="polite"' in html
        assert 'id="notifications"' in html

    def test_generate_aria_live_assertive(self):
        html = self.sr.generate_aria_live_region("alerts", "assertive")
        assert 'aria-live="assertive"' in html

    def test_generate_skip_link(self):
        link = self.sr.generate_skip_link()
        assert "skip-link" in link
        assert "#main-content" in link
        assert "Saltar al contenido" in link

    def test_add_aria_labels_to_icons(self):
        buttons = [
            {"icon": "X", "action": "Cerrar dialogo"},
            {"icon": "?", "action": "Mostrar ayuda"},
        ]
        result = self.sr.add_aria_labels_to_icons(buttons)
        assert len(result) == 2
        assert 'aria-label="Cerrar dialogo"' in result[0]
        assert 'aria-hidden="true"' in result[0]

    def test_css_sr_only(self):
        css = self.sr.get_css_sr_only()
        assert ".sr-only" in css
        assert "position: absolute" in css

    def test_keyboard_nav_js(self):
        js = self.sr.get_keyboard_nav_js()
        assert "keydown" in js
        assert "Escape" in js
