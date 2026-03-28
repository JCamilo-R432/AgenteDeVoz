"""Tests para APIVersioning (Gap #27)"""
import pytest
from src.api.versioning import APIVersioning, APIVersion, VersionStatus


@pytest.fixture
def versioning():
    return APIVersioning()


class TestVersionResolution:
    def test_resolve_v1(self, versioning):
        version = versioning.resolve_version(url_version="v1")
        assert version is not None
        assert version.version == "v1"

    def test_resolve_v2(self, versioning):
        version = versioning.resolve_version(url_version="v2")
        assert version is not None
        assert version.version == "v2"

    def test_resolve_without_prefix(self, versioning):
        version = versioning.resolve_version(url_version="2")
        assert version is not None
        assert version.version == "v2"

    def test_resolve_unknown_returns_none(self, versioning):
        version = versioning.resolve_version(url_version="v99")
        assert version is None

    def test_resolve_from_header(self, versioning):
        version = versioning.resolve_version(header_version="v2")
        assert version is not None

    def test_url_takes_precedence_over_header(self, versioning):
        version = versioning.resolve_version(url_version="v1", header_version="v2")
        assert version.version == "v1"

    def test_default_version_when_none(self, versioning):
        version = versioning.resolve_version()
        assert version is not None
        assert version.version == versioning.DEFAULT_VERSION


class TestVersionStatus:
    def test_v1_is_deprecated(self, versioning):
        version = versioning.resolve_version("v1")
        assert version.status == VersionStatus.DEPRECATED

    def test_v2_is_active(self, versioning):
        version = versioning.resolve_version("v2")
        assert version.status == VersionStatus.ACTIVE

    def test_sunset_version_not_available(self, versioning):
        versioning.register_version(APIVersion(
            version="v0",
            status=VersionStatus.SUNSET,
            release_date="2023-01-01",
        ))
        result = versioning.resolve_version("v0")
        assert result is None


class TestDeprecationHeaders:
    def test_deprecated_version_has_headers(self, versioning):
        v1 = versioning.resolve_version("v1")
        headers = versioning.get_deprecation_headers(v1)
        assert "Deprecation" in headers

    def test_deprecated_has_sunset_header(self, versioning):
        v1 = versioning.resolve_version("v1")
        headers = versioning.get_deprecation_headers(v1)
        assert "Sunset" in headers

    def test_active_version_no_deprecation_header(self, versioning):
        v2 = versioning.resolve_version("v2")
        headers = versioning.get_deprecation_headers(v2)
        assert "Deprecation" not in headers

    def test_deprecated_has_link_header(self, versioning):
        v1 = versioning.resolve_version("v1")
        headers = versioning.get_deprecation_headers(v1)
        assert "Link" in headers


class TestFeatureSupport:
    def test_v2_supports_emotion_detection(self, versioning):
        assert versioning.is_feature_supported("v2", "emotion_detection") is True

    def test_v1_not_supports_multi_language(self, versioning):
        assert versioning.is_feature_supported("v1", "multi_language") is False

    def test_both_support_voice_process(self, versioning):
        assert versioning.is_feature_supported("v1", "voice_process") is True
        assert versioning.is_feature_supported("v2", "voice_process") is True

    def test_unknown_version_feature(self, versioning):
        assert versioning.is_feature_supported("v99", "any_feature") is False


class TestMigrationGuide:
    def test_v1_to_v2_guide(self, versioning):
        guide = versioning.get_migration_guide("v1", "v2")
        assert isinstance(guide, str)
        assert len(guide) > 0

    def test_unknown_migration(self, versioning):
        guide = versioning.get_migration_guide("v1", "v99")
        assert "No hay guia" in guide


class TestVersionList:
    def test_list_versions_not_empty(self, versioning):
        versions = versioning.list_versions()
        assert len(versions) >= 2

    def test_list_versions_has_required_keys(self, versioning):
        versions = versioning.list_versions()
        for v in versions:
            assert "version" in v
            assert "status" in v
            assert "features" in v

    def test_register_custom_version(self, versioning):
        versioning.register_version(APIVersion(
            version="v3",
            status=VersionStatus.ACTIVE,
            release_date="2026-01-01",
            supported_features={"all"},
        ))
        versions = versioning.list_versions()
        codes = [v["version"] for v in versions]
        assert "v3" in codes
