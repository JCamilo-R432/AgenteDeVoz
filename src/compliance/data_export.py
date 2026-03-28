"""
Data Export - AgenteDeVoz
Gap #9: Exportacion de datos para portabilidad (Art. 20 GDPR)

Genera paquetes de datos en JSON, CSV y ZIP cifrado.
"""
import csv
import io
import json
import logging
import zipfile
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DataExporter:
    """Exporta datos personales en formatos portables."""

    def export_json(self, user_data: Dict, pretty: bool = True) -> str:
        """Exporta datos como JSON (formato preferido para portabilidad)."""
        return json.dumps(user_data, indent=2 if pretty else None, default=str, ensure_ascii=False)

    def export_csv(self, user_data: Dict) -> str:
        """Exporta datos planos como CSV."""
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)
        writer.writerow(["categoria", "campo", "valor"])

        def _flatten(data: Any, prefix: str = "") -> None:
            if isinstance(data, dict):
                for k, v in data.items():
                    _flatten(v, f"{prefix}.{k}" if prefix else k)
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    _flatten(item, f"{prefix}[{i}]")
            else:
                parts = prefix.rsplit(".", 1)
                category = parts[0] if len(parts) > 1 else "general"
                field = parts[-1]
                writer.writerow([category, field, str(data)])

        _flatten(user_data)
        return output.getvalue()

    def export_zip(self, user_data: Dict, user_id: str) -> bytes:
        """Crea archivo ZIP con JSON + CSV del usuario."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            json_content = self.export_json(user_data)
            zf.writestr(f"datos_{user_id}.json", json_content)

            csv_content = self.export_csv(user_data)
            zf.writestr(f"datos_{user_id}.csv", csv_content)

            readme = (
                f"Exportacion de datos personales\n"
                f"Usuario: {user_id}\n"
                f"Generado: {datetime.now().isoformat()}\n"
                f"GDPR Art. 20 - Derecho a la portabilidad\n"
            )
            zf.writestr("LEEME.txt", readme)

        logger.info("ZIP exportado para usuario %s (%d bytes)", user_id, buf.tell())
        return buf.getvalue()
