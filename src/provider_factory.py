from __future__ import annotations

from dataclasses import dataclass

import httpx

from src.config import Settings
from src.errors import ErrorType, ProviderError
from src.providers.announcements.cninfo import CninfoAnnouncementProvider
from src.providers.financials.sina import SinaFinancialStatementsProvider
from src.providers.fundamental.akshare_financials import AkshareFinancialsProvider
from src.providers.fundamental.eastmoney import EastmoneyFundamentalProvider
from src.providers.iwencai.client import IwencaiClient
from src.providers.market_data.mootdx_kline import MootdxKlineProvider
from src.providers.market_data.tencent_kline import TencentKlineProvider
from src.providers.profile.tencent import TencentProfileProvider
from src.services.announcement_service import AnnouncementService
from src.services.financial_statement_service import FinancialStatementService
from src.services.iwencai_service import IwencaiService
from src.services.retry import RetryPolicy
from src.services.stock_fundamental_snapshot_service import (
    StockFundamentalSnapshotService,
)
from src.services.stock_kline_service import StockKlineService
from src.services.stock_profile_service import StockProfileService


@dataclass(frozen=True)
class ServiceBundle:
    http_client: httpx.AsyncClient
    kline_service: StockKlineService
    profile_service: StockProfileService
    financial_service: FinancialStatementService
    snapshot_service: StockFundamentalSnapshotService
    announcement_service: AnnouncementService
    iwencai_service: IwencaiService | None


def build_services(settings: Settings) -> ServiceBundle:
    http_client = httpx.AsyncClient(timeout=settings.fin_request_timeout)
    retry_policy = RetryPolicy.from_settings(settings)

    quote_provider = _profile_provider(settings.fin_profile_provider, http_client)

    kline_service = StockKlineService(
        a_share_provider=_a_kline_provider(settings.fin_a_kline_provider, http_client),
        hk_provider=_hk_kline_provider(settings.fin_hk_kline_provider, http_client),
        retry_policy=retry_policy,
    )
    profile_service = StockProfileService(
        providers=[quote_provider],
        retry_policy=retry_policy,
    )
    financial_service = FinancialStatementService(
        provider=_financial_provider(
            settings.fin_financial_statements_provider,
            http_client,
        ),
        retry_policy=retry_policy,
    )
    snapshot_service = StockFundamentalSnapshotService(
        profile_provider=_fundamental_profile_provider(
            settings.fin_fundamental_profile_provider,
            http_client,
        ),
        financials_provider=_fundamental_financials_provider(
            settings.fin_fundamental_financials_provider,
        ),
        # 与 stock_profile 复用同一个腾讯行情 provider 实例（无状态，仅持有 httpx client）。
        quote_provider=quote_provider,
        retry_policy=retry_policy,
    )
    announcement_service = AnnouncementService(
        provider=_announcement_provider(settings.fin_announcements_provider, http_client),
        retry_policy=retry_policy,
    )
    iwencai_service = _iwencai_service(settings, http_client, retry_policy)

    return ServiceBundle(
        http_client=http_client,
        kline_service=kline_service,
        profile_service=profile_service,
        financial_service=financial_service,
        snapshot_service=snapshot_service,
        announcement_service=announcement_service,
        iwencai_service=iwencai_service,
    )


def _a_kline_provider(provider_name: str, client: httpx.AsyncClient):
    if provider_name == "mootdx":
        return MootdxKlineProvider()
    if provider_name == "tencent":
        return TencentKlineProvider(client=client)
    if provider_name == "none":
        return None
    raise _unknown_provider("a_kline", provider_name)


def _hk_kline_provider(provider_name: str, client: httpx.AsyncClient):
    if provider_name == "tencent":
        return TencentKlineProvider(client=client)
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


def _fundamental_profile_provider(provider_name: str, client: httpx.AsyncClient):
    if provider_name == "eastmoney":
        return EastmoneyFundamentalProvider(client=client)
    if provider_name == "none":
        return None
    raise _unknown_provider("fundamental_profile", provider_name)


def _fundamental_financials_provider(provider_name: str):
    if provider_name == "akshare":
        return AkshareFinancialsProvider()
    if provider_name == "none":
        return None
    raise _unknown_provider("fundamental_financials", provider_name)


def _announcement_provider(provider_name: str, client: httpx.AsyncClient):
    if provider_name == "cninfo":
        return CninfoAnnouncementProvider(client=client)
    if provider_name == "none":
        return None
    raise _unknown_provider("announcements", provider_name)


def _iwencai_service(
    settings: Settings,
    client: httpx.AsyncClient,
    retry_policy: RetryPolicy,
) -> IwencaiService | None:
    provider_name = settings.fin_iwencai_provider
    if provider_name == "none":
        return None
    if provider_name != "iwencai":
        raise _unknown_provider("iwencai", provider_name)
    return IwencaiService(
        client=IwencaiClient(client=client, api_key=settings.resolved_iwencai_api_key),
        retry_policy=retry_policy,
    )


def _unknown_provider(domain: str, provider_name: str) -> ProviderError:
    return ProviderError(
        error_type=ErrorType.CONFIG_ERROR,
        provider=domain,
        message=f"Unsupported {domain} provider: {provider_name}",
    )
