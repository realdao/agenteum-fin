import logging

import pytest

from src.errors import ErrorType, ProviderError
from src.schemas import StockProfileData
from src.services.stock_profile_service import StockProfileService


class LoggingFakeProvider:
    name = "tencent"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def get_profiles(self, symbols):
        if self.fail:
            raise ProviderError(
                error_type=ErrorType.TIMEOUT,
                provider=self.name,
                message="timeout",
                http_status=504,
            )
        return [StockProfileData(symbol=symbol, name="贵州茅台") for symbol in symbols]


@pytest.mark.asyncio
async def test_service_logs_provider_success(caplog):
    service = StockProfileService(providers=[LoggingFakeProvider()])

    with caplog.at_level(logging.INFO, logger="agenteum_fin.provider"):
        await service.get_profiles(["600519"])

    record = caplog.records[0]
    assert record.operation == "stock_profile"
    assert record.provider == "tencent"
    assert record.market == "a_share"
    assert record.symbol == "600519.SH"
    assert record.status == "ok"
    assert record.fallback_count == 0


@pytest.mark.asyncio
async def test_service_logs_provider_failure(caplog):
    service = StockProfileService(providers=[LoggingFakeProvider(fail=True)])

    with (
        caplog.at_level(logging.INFO, logger="agenteum_fin.provider"),
        pytest.raises(ProviderError),
    ):
        await service.get_profiles(["600519"])

    record = caplog.records[0]
    assert record.status == "error"
    assert record.error_type == "timeout"
    assert record.http_status == 504


@pytest.mark.asyncio
async def test_service_logs_batch_call_without_single_symbol(caplog):
    service = StockProfileService(providers=[LoggingFakeProvider()])

    with caplog.at_level(logging.INFO, logger="agenteum_fin.provider"):
        await service.get_profiles(["600519", "00700"])

    record = caplog.records[0]
    assert record.operation == "stock_profile"
    assert record.symbol is None
    assert record.market is None
    assert record.status == "ok"
