"""
Accessibility Tests - Suite de pruebas automaticas de accesibilidad
"""
from .wcag_checker import WCAGChecker


def run_dashboard_accessibility_tests(html_content: str) -> dict:
    """
    Ejecuta la suite completa de tests de accesibilidad en el dashboard.

    Args:
        html_content: HTML del dashboard a verificar

    Returns:
        Reporte con violaciones, score y recomendaciones
    """
    checker = WCAGChecker()
    violations = checker.check_dashboard(html_content)
    report = checker.generate_report()

    print(f"\n=== REPORTE DE ACCESIBILIDAD WCAG 2.1 ===")
    print(f"Score: {report['summary']['score']}/100")
    print(f"Nivel alcanzado: {report['summary']['wcag_level_achieved']}")
    print(f"Violaciones: {report['summary']['total_violations']}")
    print(f"  - Criticas: {report['summary']['critical']}")
    print(f"  - Serias:   {report['summary']['serious']}")
    print(f"  - Moderadas:{report['summary']['moderate']}")
    print(f"Criterios OK: {report['summary']['passes']}")

    if report["recommendations"]:
        print("\nRecomendaciones:")
        for rec in report["recommendations"]:
            print(f"  • {rec}")

    return report
