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
            AGENTEUM_FIN_RESEARCH_REPORTS_PROVIDER="none",
        )
    )

    assert services.kline_service.a_share_provider is None
    assert services.f10_service.provider is None
    assert services.announcement_service.provider is None
    assert services.research_report_service.provider is None


def test_build_services_wires_news_service_to_profile_service():
    services = build_services(
        Settings(
            AGENTEUM_FIN_A_KLINE_PROVIDER="none",
            AGENTEUM_FIN_F10_PROVIDER="none",
            AGENTEUM_FIN_ANNOUNCEMENTS_PROVIDER="none",
            AGENTEUM_FIN_RESEARCH_REPORTS_PROVIDER="none",
        )
    )

    assert services.news_service.profile_service is services.profile_service
