from __future__ import annotations

from dataclasses import dataclass

import httpx

from src.config import Settings
from src.errors import ErrorType, ProviderError
from src.providers.announcements.cninfo import CninfoAnnouncementProvider
from src.providers.f10.mootdx_f10 import MootdxF10Provider
from src.providers.financials.sina import SinaFinancialStatementsProvider
from src.providers.market_data.mootdx_kline import MootdxKlineProvider
from src.providers.profile.tencent import TencentProfileProvider
from src.providers.research.eastmoney import EastmoneyResearchReportProvider
from src.services.announcement_service import AnnouncementService
from src.services.financial_statement_service import FinancialStatementService
from src.services.research_report_service import ResearchReportService
from src.services.retry import RetryPolicy
from src.services.stock_f10_service import StockF10Service
from src.services.stock_kline_service import StockKlineService
from src.services.stock_news_service import StockNewsService
from src.services.stock_profile_service import StockProfileService


@dataclass(frozen=True)
class ServiceBundle:
    http_client: httpx.AsyncClient
    kline_service: StockKlineService
    profile_service: StockProfileService
    financial_service: FinancialStatementService
    f10_service: StockF10Service
    announcement_service: AnnouncementService
    research_report_service: ResearchReportService
    news_service: StockNewsService


def build_services(settings: Settings) -> ServiceBundle:
    http_client = httpx.AsyncClient(timeout=settings.fin_request_timeout)
    retry_policy = RetryPolicy.from_settings(settings)

    kline_service = StockKlineService(
        a_share_provider=_a_kline_provider(settings.fin_a_kline_provider),
        hk_provider=_hk_kline_provider(settings.fin_hk_kline_provider),
        retry_policy=retry_policy,
    )
    profile_service = StockProfileService(
        providers=[_profile_provider(settings.fin_profile_provider, http_client)],
        retry_policy=retry_policy,
    )
    financial_service = FinancialStatementService(
        provider=_financial_provider(
            settings.fin_financial_statements_provider,
            http_client,
        ),
        retry_policy=retry_policy,
    )
    f10_service = StockF10Service(
        provider=_f10_provider(settings.fin_f10_provider),
        retry_policy=retry_policy,
    )
    announcement_service = AnnouncementService(
        provider=_announcement_provider(settings.fin_announcements_provider, http_client),
        retry_policy=retry_policy,
    )
    research_report_service = ResearchReportService(
        provider=_research_provider(settings.fin_research_reports_provider, http_client),
        retry_policy=retry_policy,
    )
    news_service = StockNewsService(profile_service=profile_service)

    return ServiceBundle(
        http_client=http_client,
        kline_service=kline_service,
        profile_service=profile_service,
        financial_service=financial_service,
        f10_service=f10_service,
        announcement_service=announcement_service,
        research_report_service=research_report_service,
        news_service=news_service,
    )


def _a_kline_provider(provider_name: str):
    if provider_name == "mootdx":
        return MootdxKlineProvider()
    if provider_name == "none":
        return None
    raise _unknown_provider("a_kline", provider_name)


def _hk_kline_provider(provider_name: str):
    if provider_name == "none":
        return None
    raise _unknown_provider("hk_kline", provider_name)


def _profile_provider(provider_name: str, client: httpx.AsyncClient):
    if provider_name == "tencent":
        return TencentProfileProvider(client=client)
    raise _unknown_provider("profile", provider_name)


def _financial_provider(provider_name: str, client: httpx.AsyncClient):
    if provider_name == "sina":
        return SinaFinancialStatementsProvider(client=client)
    raise _unknown_provider("financial_statements", provider_name)


def _f10_provider(provider_name: str):
    if provider_name == "mootdx":
        return MootdxF10Provider()
    if provider_name == "none":
        return None
    raise _unknown_provider("f10", provider_name)


def _announcement_provider(provider_name: str, client: httpx.AsyncClient):
    if provider_name == "cninfo":
        return CninfoAnnouncementProvider(client=client)
    if provider_name == "none":
        return None
    raise _unknown_provider("announcements", provider_name)


def _research_provider(provider_name: str, client: httpx.AsyncClient):
    if provider_name == "eastmoney":
        return EastmoneyResearchReportProvider(client=client)
    if provider_name == "none":
        return None
    raise _unknown_provider("research_reports", provider_name)


def _unknown_provider(domain: str, provider_name: str) -> ProviderError:
    return ProviderError(
        error_type=ErrorType.CONFIG_ERROR,
        provider=domain,
        message=f"Unsupported {domain} provider: {provider_name}",
    )
