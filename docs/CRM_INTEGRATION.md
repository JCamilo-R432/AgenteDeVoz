# Integracion CRM (Gap #22)

## CRMs soportados
- **Salesforce** (REST API v58.0, OAuth2 client_credentials)
- **HubSpot** (API v3, Private App token)

## Uso con API unificada
```python
from src.integrations.crm_unified_api import CRMUnifiedAPI, CRMProvider
from src.integrations.salesforce_connector import SalesforceConnector

sf = SalesforceConnector(
    instance_url="https://miempresa.salesforce.com",
    client_id="CONSUMER_KEY",
    client_secret="CONSUMER_SECRET",
)
crm = CRMUnifiedAPI(provider=CRMProvider.SALESFORCE, salesforce_connector=sf)

# Buscar contacto
contact = crm.find_contact_by_phone("+573001234567")

# Crear ticket
ticket = crm.create_ticket(
    contact_id=contact.id,
    subject="Fallo en facturacion",
    description="El cobro fue duplicado",
    priority="high",
)

# Actualizar estado
crm.update_ticket_status(ticket.id, "closed")
```

## Usar HubSpot
```python
from src.integrations.hubspot_connector import HubSpotConnector

hs = HubSpotConnector(access_token="priv-na1-xxx")
crm = CRMUnifiedAPI(provider=CRMProvider.HUBSPOT, hubspot_connector=hs)
```

## Variables de entorno requeridas
```env
# Salesforce
SF_INSTANCE_URL=https://miempresa.salesforce.com
SF_CLIENT_ID=tu_consumer_key
SF_CLIENT_SECRET=tu_consumer_secret

# HubSpot
HS_ACCESS_TOKEN=priv-na1-xxx
HS_PORTAL_ID=12345678
```

## Mapeo de prioridades
| Unificada | Salesforce | HubSpot |
|-----------|------------|---------|
| low | Low | LOW |
| medium | Medium | MEDIUM |
| high | High | HIGH |
| critical | Critical | HIGH |
