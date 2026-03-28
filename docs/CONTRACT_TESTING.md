# Contract Testing (Gap #28)

## Descripcion
Pruebas de contrato Consumer-Driven para garantizar compatibilidad entre
la API de AgenteDeVoz y sus consumidores (frontend, CRM, monitoring).

## Suites de contratos incluidos
| Suite | Proveedor | Consumidor |
|-------|-----------|------------|
| voice_api | agentevoz-api | voice-client |
| ticket_api | agentevoz-api | support-dashboard |
| health_api | agentevoz-api | monitoring |

## Ejecutar contratos
```bash
scripts/run_contract_tests.sh
# Reporte en: reports/contracts/contract_report.json
```

## Validacion de esquemas
```python
from src.api.schema_validation import SchemaValidation

validator = SchemaValidation()
result = validator.validate("voice_process_request", payload)
if not result.valid:
    raise ValueError(f"Payload invalido: {result.errors}")
```

## Agregar nuevo contrato
```python
from src.api.contract_tests import ContractTests, ContractSuite, ContractInteraction

ct = ContractTests()
ct.add_interaction("nuevo_servicio", ContractInteraction(
    description="Crear usuario",
    request_schema="user_create_request",
    response_schema="user_response",
    sample_request={"name": "Juan", "email": "juan@test.com"},
    sample_response={"id": "usr_001", "name": "Juan"},
    provider="user-api",
    consumer="frontend",
))
results = ct.run_suite("nuevo_servicio")
```

## Esquemas soportados
- `voice_process_request` / `voice_process_response`
- `ticket_create_request` / `ticket_response`
- `health_response`

## Integracion CI/CD
El script `run_contract_tests.sh` retorna exit code 1 si algun contrato falla.
Agregar en `.github/workflows/ci.yml`:
```yaml
- name: Contract Tests
  run: bash scripts/run_contract_tests.sh
```
