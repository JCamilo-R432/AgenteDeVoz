"""
KB Sync - Sincronizacion de la base de conocimiento con fuentes externas
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class KBSync:
    """
    Sincroniza la base de conocimiento con fuentes externas:
    - Confluence / Notion (documentacion interna)
    - HubSpot Knowledge Base
    - Archivos Markdown del repositorio
    """

    def __init__(self, kb_manager):
        self._kb = kb_manager
        self._sync_log: List[Dict] = []

    def sync_from_markdown_dir(self, directory: str) -> Dict:
        """
        Importa articulos desde archivos .md en un directorio.

        Args:
            directory: Ruta al directorio con archivos Markdown

        Returns:
            Resultado de la sincronizacion
        """
        import os
        import glob

        imported = 0
        errors = []

        md_files = glob.glob(os.path.join(directory, "**/*.md"), recursive=True)
        for file_path in md_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Extraer titulo del primer H1
                lines = content.split("\n")
                title = "Sin titulo"
                for line in lines:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break

                # Determinar categoria por directorio
                dirname = os.path.basename(os.path.dirname(file_path))
                category = dirname if dirname in self._kb.CATEGORIES else "technical"

                self._kb.create_article(
                    title=title,
                    content=content,
                    category=category,
                    tags=[dirname, "imported", "markdown"],
                    author="sync",
                )
                imported += 1
            except Exception as e:
                errors.append({"file": file_path, "error": str(e)})

        result = {
            "source": "markdown",
            "directory": directory,
            "imported": imported,
            "errors": len(errors),
            "error_details": errors,
            "synced_at": datetime.utcnow().isoformat(),
        }
        self._sync_log.append(result)
        logger.info(f"Sync markdown: {imported} articulos importados, {len(errors)} errores")
        return result

    def sync_from_hubspot(self, api_key: str, portal_id: str) -> Dict:
        """
        Sincroniza desde HubSpot Knowledge Base.
        Requiere HubSpot API key con permisos de Knowledge Base.
        """
        # Implementacion real requiere hubspot-api-client
        # Por ahora retornamos estructura esperada
        logger.info("Sincronizacion con HubSpot (modo simulado)")
        result = {
            "source": "hubspot",
            "portal_id": portal_id,
            "imported": 0,
            "message": "Instalar hubspot-api-client y configurar credenciales",
            "synced_at": datetime.utcnow().isoformat(),
        }
        self._sync_log.append(result)
        return result

    def get_sync_log(self) -> List[Dict]:
        """Retorna el historial de sincronizaciones."""
        return self._sync_log
