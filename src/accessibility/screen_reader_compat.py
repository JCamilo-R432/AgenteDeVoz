"""
Screen Reader Compatibility - Utilidades para compatibilidad con lectores de pantalla
"""
from typing import Dict, List


class ScreenReaderCompat:
    """
    Herramientas para mejorar la compatibilidad con lectores de pantalla
    en el dashboard de AgenteDeVoz.
    """

    def generate_aria_live_region(self, region_id: str, politeness: str = "polite") -> str:
        """
        Genera HTML para una region live de ARIA.
        Las regiones live anuncian cambios dinamicos a lectores de pantalla.

        Args:
            region_id: ID unico de la region
            politeness: "polite" (espera) o "assertive" (interrumpe)
        """
        return f'<div id="{region_id}" aria-live="{politeness}" aria-atomic="true" class="sr-only"></div>'

    def generate_skip_link(self, target_id: str = "main-content") -> str:
        """
        Genera un enlace para saltar al contenido principal.
        Requerido para WCAG 2.4.1 (Bypass Blocks).
        """
        return (
            f'<a href="#{target_id}" class="skip-link" '
            f'style="position:absolute;top:-40px;left:0;background:#0066cc;'
            f'color:white;padding:8px;z-index:9999;'
            f'transition:top 0.1s;">'
            f'Saltar al contenido principal'
            f'</a>'
        )

    def add_aria_labels_to_icons(self, icon_buttons: List[Dict]) -> List[str]:
        """
        Agrega aria-label a botones con solo iconos.

        Args:
            icon_buttons: Lista de dicts con {"icon": "...", "action": "..."}

        Returns:
            Lista de HTML strings con aria-label
        """
        result = []
        for btn in icon_buttons:
            html = (
                f'<button aria-label="{btn["action"]}" type="button">'
                f'<span aria-hidden="true">{btn["icon"]}</span>'
                f'</button>'
            )
            result.append(html)
        return result

    def get_css_sr_only(self) -> str:
        """CSS para la clase sr-only (visualmente oculto, accesible para lectores)."""
        return """
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}

.skip-link:focus {
    top: 0 !important;
}
"""

    def get_keyboard_nav_js(self) -> str:
        """JavaScript para mejorar la navegacion por teclado en el dashboard."""
        return """
// Navegacion por teclado para el dashboard
document.addEventListener('keydown', function(e) {
    // Escape cierra modales
    if (e.key === 'Escape') {
        const modal = document.querySelector('[role="dialog"][aria-modal="true"]');
        if (modal) {
            const closeBtn = modal.querySelector('[aria-label="Cerrar"]');
            if (closeBtn) closeBtn.click();
        }
    }
    // Alt+1: ir a navegacion principal
    if (e.altKey && e.key === '1') {
        const nav = document.querySelector('nav[aria-label="Principal"]');
        if (nav) nav.focus();
    }
    // Alt+2: ir al contenido principal
    if (e.altKey && e.key === '2') {
        const main = document.getElementById('main-content');
        if (main) main.focus();
    }
});
"""
