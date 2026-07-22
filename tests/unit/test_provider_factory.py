import pytest

from src.config import Settings
from src.errors import ErrorType, ProviderError
from src.provider_factory import build_services


def test_build_services_rejects_unknown_provider_configuration():
    with pytest.raises(ProviderError) as raised:
        build_services(Settings(AGENTEUM_FIN_PROFILE_PROVIDER="unknown"))

    assert raised.value.error_type == ErrorType.CONFIG_ERROR
    assert raised.value.provider == "profile"


def test_build_services_allows_disabling_optional_providers():
    services = build_services(
        Settings(
            AGENTEUM_FIN_A_KLINE_PROVIDER="none",
            AGENTEUM_FIN_F10_PROVIDER="none",
            AGENTEUM_FIN_ANNOUNCEMENTS_PROVIDER="none",
        )
    )

    assert services.kline_service.a_share_provider is None
    assert services.f10_service.provider is None
    assert services.announcement_service.provider is None


def test_build_services_disables_iwencai_with_none():
    services = build_services(Settings(AGENTEUM_FIN_IWENCAI_PROVIDER="none"))

    assert services.iwencai_service is None


def test_build_services_rejects_unknown_iwencai_provider():
    with pytest.raises(ProviderError) as raised:
        build_services(Settings(AGENTEUM_FIN_IWENCAI_PROVIDER="unknown"))

    assert raised.value.error_type == ErrorType.CONFIG_ERROR
    assert raised.value.provider == "iwencai"


def test_build_services_builds_iwencai_service_by_default():
    services = build_services(Settings())

    assert services.iwencai_service is not None
    assert services.iwencai_service.client.name == "iwencai"
