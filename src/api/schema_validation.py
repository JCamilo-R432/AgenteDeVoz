"""
Schema Validation - AgenteDeVoz
Gap #28: Validacion de esquemas de request/response

Valida payloads de entrada y salida contra esquemas JSON Schema.
"""
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str]
    schema_name: str

    def to_dict(self) -> Dict:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "schema": self.schema_name,
        }


# Esquemas JSON Schema simplificados para los endpoints principales
SCHEMAS: Dict[str, Dict] = {
    "voice_process_request": {
        "type": "object",
        "required": ["session_id", "audio_base64"],
        "properties": {
            "session_id": {"type": "string", "minLength": 1},
            "audio_base64": {"type": "string", "minLength": 1},
            "language": {"type": "string", "enum": ["es", "en", "pt"]},
            "sample_rate": {"type": "integer", "minimum": 8000, "maximum": 48000},
        },
        "additionalProperties": False,
    },
    "voice_process_response": {
        "type": "object",
        "required": ["session_id", "response", "intent"],
        "properties": {
            "session_id": {"type": "string"},
            "response": {"type": "string"},
            "intent": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "language": {"type": "string"},
        },
    },
    "ticket_create_request": {
        "type": "object",
        "required": ["title", "description", "priority"],
        "properties": {
            "title": {"type": "string", "minLength": 3, "maxLength": 200},
            "description": {"type": "string", "minLength": 10},
            "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
            "session_id": {"type": "string"},
        },
    },
    "ticket_response": {
        "type": "object",
        "required": ["id", "title", "status", "created_at"],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "status": {"type": "string", "enum": ["open", "in_progress", "resolved", "closed"]},
            "priority": {"type": "string"},
            "created_at": {"type": "string"},
        },
    },
    "health_response": {
        "type": "object",
        "required": ["status"],
        "properties": {
            "status": {"type": "string", "enum": ["ok", "degraded", "down"]},
            "version": {"type": "string"},
            "uptime_seconds": {"type": "number"},
        },
    },
}


class SchemaValidation:
    """
    Validador de esquemas JSON para requests y responses de la API.
    Implementacion minimalista sin dependencias externas.
    Para produccion usar jsonschema o pydantic.
    """

    def __init__(self):
        self._schemas = dict(SCHEMAS)
        logger.info("SchemaValidation inicializado (%d esquemas)", len(self._schemas))

    def validate(self, schema_name: str, data: Any) -> ValidationResult:
        """
        Valida data contra el esquema especificado.

        Returns:
            ValidationResult con valid=True si pasa, o lista de errores
        """
        schema = self._schemas.get(schema_name)
        if not schema:
            return ValidationResult(
                valid=False,
                errors=[f"Esquema desconocido: {schema_name}"],
                schema_name=schema_name,
            )

        errors = self._validate_against_schema(data, schema, path="$")
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            schema_name=schema_name,
        )

    def _validate_against_schema(self, data: Any, schema: Dict, path: str) -> List[str]:
        """Validacion recursiva simplificada de JSON Schema."""
        errors: List[str] = []
        expected_type = schema.get("type")

        # Validar tipo
        if expected_type:
            if not self._check_type(data, expected_type):
                errors.append(f"{path}: esperado {expected_type}, obtenido {type(data).__name__}")
                return errors  # No continuar si el tipo es incorrecto

        if expected_type == "object" and isinstance(data, dict):
            # Validar campos requeridos
            for req in schema.get("required", []):
                if req not in data:
                    errors.append(f"{path}.{req}: campo requerido faltante")

            # Validar propiedades
            for prop, prop_schema in schema.get("properties", {}).items():
                if prop in data:
                    errors.extend(
                        self._validate_against_schema(data[prop], prop_schema, f"{path}.{prop}")
                    )

            # Validar additionalProperties
            if schema.get("additionalProperties") is False:
                extra = set(data.keys()) - set(schema.get("properties", {}).keys())
                for key in extra:
                    errors.append(f"{path}.{key}: propiedad adicional no permitida")

        elif expected_type == "string" and isinstance(data, str):
            if "minLength" in schema and len(data) < schema["minLength"]:
                errors.append(f"{path}: longitud {len(data)} < minLength {schema['minLength']}")
            if "maxLength" in schema and len(data) > schema["maxLength"]:
                errors.append(f"{path}: longitud {len(data)} > maxLength {schema['maxLength']}")
            if "enum" in schema and data not in schema["enum"]:
                errors.append(f"{path}: valor '{data}' no esta en {schema['enum']}")

        elif expected_type in ("number", "integer") and isinstance(data, (int, float)):
            if "minimum" in schema and data < schema["minimum"]:
                errors.append(f"{path}: {data} < minimum {schema['minimum']}")
            if "maximum" in schema and data > schema["maximum"]:
                errors.append(f"{path}: {data} > maximum {schema['maximum']}")

        return errors

    def _check_type(self, value: Any, expected: str) -> bool:
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "object": dict,
            "array": list,
            "null": type(None),
        }
        expected_py = type_map.get(expected)
        if expected_py is None:
            return True
        return isinstance(value, expected_py)

    def add_schema(self, name: str, schema: Dict) -> None:
        """Registra un esquema nuevo en tiempo de ejecucion."""
        self._schemas[name] = schema
        logger.debug("Esquema registrado: %s", name)

    def list_schemas(self) -> List[str]:
        return list(self._schemas.keys())
