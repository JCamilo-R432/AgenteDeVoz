"""Tests para CRM Integration (Gap #22)"""
import pytest
from src.integrations.salesforce_connector import SalesforceConnector
from src.integrations.hubspot_connector import HubSpotConnector
from src.integrations.crm_unified_api import CRMUnifiedAPI, CRMProvider


@pytest.fixture
def sf():
    return SalesforceConnector(
        instance_url="https://test.salesforce.com",
        client_id="test_client_id",
        client_secret="test_secret",
    )


@pytest.fixture
def hs():
    return HubSpotConnector(access_token="test_token_hs", portal_id="12345")


@pytest.fixture
def crm_sf(sf):
    return CRMUnifiedAPI(provider=CRMProvider.SALESFORCE, salesforce_connector=sf)


@pytest.fixture
def crm_hs(hs):
    return CRMUnifiedAPI(provider=CRMProvider.HUBSPOT, hubspot_connector=hs)


class TestSalesforceConnector:
    def test_authenticate_returns_true(self, sf):
        assert sf.authenticate() is True

    def test_token_cached_after_auth(self, sf):
        sf.authenticate()
        assert sf._access_token is not None

    def test_find_contact_colombia(self, sf):
        contact = sf.find_contact_by_phone("+573001234567")
        assert contact is not None
        assert contact.phone == "+573001234567"

    def test_find_contact_unknown_returns_none(self, sf):
        contact = sf.find_contact_by_phone("+11234567890")
        assert contact is None

    def test_create_case_returns_case(self, sf):
        case = sf.create_case(
            contact_id="003TEST001",
            subject="Problema de facturacion",
            description="El cobro fue incorrecto",
            priority="high",
        )
        assert case is not None
        assert case.subject == "Problema de facturacion"
        assert case.status == "New"

    def test_create_case_invalid_priority_defaults(self, sf):
        case = sf.create_case("003TEST001", "Asunto", "Desc", priority="ultra_high")
        assert case is not None

    def test_update_case_status_valid(self, sf):
        result = sf.update_case_status("5001CASE001", "Working")
        assert result is True

    def test_update_case_status_invalid(self, sf):
        result = sf.update_case_status("5001CASE001", "InvalidStatus")
        assert result is False

    def test_get_account_history(self, sf):
        history = sf.get_account_history("001ACC001")
        assert isinstance(history, list)


class TestHubSpotConnector:
    def test_find_contact_by_email(self, hs):
        contact = hs.find_contact_by_email("test@example.com")
        assert contact is not None
        assert contact.email == "test@example.com"

    def test_find_contact_invalid_email(self, hs):
        contact = hs.find_contact_by_email("invalidemail")
        assert contact is None

    def test_create_contact(self, hs):
        contact = hs.create_contact(
            email="new@test.com",
            first_name="Ana",
            last_name="Lopez",
            phone="+573009876543",
        )
        assert contact is not None
        assert contact.first_name == "Ana"

    def test_create_ticket(self, hs):
        ticket = hs.create_ticket(
            contact_id="hs_001",
            subject="Problema tecnico",
            description="No puedo iniciar sesion",
            priority="HIGH",
        )
        assert ticket is not None
        assert ticket.status == "OPEN"

    def test_update_ticket_status_valid(self, hs):
        result = hs.update_ticket_status("tkt_001", "CLOSED")
        assert result is True

    def test_update_ticket_status_invalid(self, hs):
        result = hs.update_ticket_status("tkt_001", "INVALID_STATUS")
        assert result is False

    def test_log_call(self, hs):
        result = hs.log_call("hs_001", duration_s=180, outcome="resolved")
        assert result is True


class TestCRMUnifiedAPI:
    def test_active_provider_salesforce(self, crm_sf):
        assert crm_sf.get_active_provider() == "salesforce"

    def test_active_provider_hubspot(self, crm_hs):
        assert crm_hs.get_active_provider() == "hubspot"

    def test_missing_connector_raises(self):
        with pytest.raises(ValueError):
            CRMUnifiedAPI(provider=CRMProvider.SALESFORCE)

    def test_find_contact_sf(self, crm_sf):
        contact = crm_sf.find_contact_by_phone("+573001234567")
        assert contact is not None
        assert contact.provider == "salesforce"

    def test_find_contact_hs(self, crm_hs):
        contact = crm_hs.find_contact_by_email("test@example.com")
        assert contact is not None
        assert contact.provider == "hubspot"

    def test_create_ticket_sf(self, crm_sf):
        ticket = crm_sf.create_ticket(
            contact_id="003TEST001",
            subject="Ticket unificado",
            description="Descripcion del problema",
            priority="medium",
        )
        assert ticket is not None
        assert ticket.provider == "salesforce"

    def test_create_ticket_hs(self, crm_hs):
        ticket = crm_hs.create_ticket(
            contact_id="hs_001",
            subject="Ticket unificado",
            description="Descripcion del problema",
            priority="medium",
        )
        assert ticket is not None
        assert ticket.provider == "hubspot"

    def test_update_ticket_sf(self, crm_sf):
        result = crm_sf.update_ticket_status("5001CASE001", "closed")
        assert result is True

    def test_log_call_hs(self, crm_hs):
        result = crm_hs.log_call("hs_001", 120, "resolved", "Todo resuelto")
        assert result is True

    def test_get_supported_providers(self, crm_sf):
        providers = crm_sf.get_supported_providers()
        assert "salesforce" in providers
        assert "hubspot" in providers
