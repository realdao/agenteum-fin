from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

from src.errors import ErrorType, ProviderError

AssetType = Literal["stock", "fund", "index"]

# A 股双前缀路由：两位前缀可无歧义地区分场内基金与深证/国证指数。
# 创业板 300/301 以 "30"/"31" 开头，不在表内，回落到单前缀股票路由。
_A_SHARE_TWO_DIGIT_ROUTES: dict[str, tuple[str, AssetType]] = {
    "50": ("sh", "fund"),
    "51": ("sh", "fund"),
    "56": ("sh", "fund"),
    "58": ("sh", "fund"),
    "15": ("sz", "fund"),
    "16": ("sz", "fund"),
    "18": ("sz", "fund"),
    "39": ("sz", "index"),
}

FUND_ROUTING_HINT = (
    "该代码为场内基金（ETF/LOF，沪市 50/51/56/58、深市 15/16/18 开头）。"
    "基金 K 线可用 stock_kline；行情/净值/涨跌幅等其他基金数据请用 "
    "iwencai_query(domain=market)。"
)

INDEX_ROUTING_HINT = (
    "该代码为指数。指数 K 线可用 stock_kline（上证系列指数需显式 .SH 后缀，"
    "如 000001.SH；深证/国证系列 399xxx 可用裸码）；指数点位/涨跌幅请用 "
    "iwencai_query(domain=index)；指数成分股请用 iwencai_query(domain=astock)。"
)


class NormalizedSymbol(BaseModel):
    market: str
    exchange: str
    symbol: str
    display_symbol: str
    asset_type: AssetType = "stock"


def normalize_symbol(raw: str) -> NormalizedSymbol:
    value = raw.strip().upper()
    explicit_hk = value.startswith("HK") or value.endswith(".HK")
    explicit_exchange = _explicit_exchange(value)
    value = re.sub(r"^(SH|SZ|BJ|HK)", "", value)
    suffix = None
    if "." in value:
        value, suffix = value.split(".", 1)
    if not value.isdigit():
        raise ProviderError(
            error_type=ErrorType.INVALID_SYMBOL,
            provider=None,
            message=f"Invalid stock symbol: {raw}",
        )
    if explicit_hk or suffix == "HK" or len(value) == 5:
        # 显式港股（HK 前缀或 .HK 后缀）时自动补零到 5 位，如 700.HK -> 00700.HK。
        if explicit_hk or suffix == "HK":
            value = value.zfill(5)
        if len(value) != 5:
            raise ProviderError(
                error_type=ErrorType.INVALID_SYMBOL,
                provider=None,
                message="Hong Kong symbols must normalize to five digits.",
            )
        return NormalizedSymbol(
            market="hk",
            exchange="hk",
            symbol=value,
            display_symbol=f"{value}.HK",
        )
    if len(value) != 6:
        raise ProviderError(
            error_type=ErrorType.INVALID_SYMBOL,
            provider=None,
            message="A-share symbols must normalize to six digits.",
        )
    effective_exchange = suffix.lower() if suffix is not None else explicit_exchange
    exchange, asset_type = _a_share_route(value, explicit_exchange=effective_exchange)
    if suffix is not None and suffix.lower() != exchange:
        raise ProviderError(
            error_type=ErrorType.INVALID_SYMBOL,
            provider=None,
            message=f"Symbol suffix {suffix} does not match inferred exchange {exchange}.",
        )
    return NormalizedSymbol(
        market="a_share",
        exchange=exchange,
        symbol=value,
        display_symbol=f"{value}.{exchange.upper()}",
        asset_type=asset_type,
    )


def stock_only_routing_message(asset_type: AssetType) -> str:
    """面向仅支持个股的 stock_* 工具的路由提示文案。"""
    if asset_type == "fund":
        return f"stock_* 基本面/公告类工具仅支持股票代码。{FUND_ROUTING_HINT}"
    return f"stock_* 基本面/公告类工具仅支持股票代码。{INDEX_ROUTING_HINT}"


def require_stock_symbol(symbol: NormalizedSymbol) -> None:
    """面向仅支持个股的 stock_* 工具：基金/指数代码直接报错并给出路由提示。"""
    if symbol.asset_type == "stock":
        return
    raise ProviderError(
        error_type=ErrorType.INVALID_SYMBOL,
        provider=None,
        message=stock_only_routing_message(symbol.asset_type),
    )


def _explicit_exchange(value: str) -> str | None:
    match = re.match(r"^(SH|SZ|BJ|HK)", value)
    return match.group(1).lower() if match else None


def _a_share_route(symbol: str, *, explicit_exchange: str | None) -> tuple[str, AssetType]:
    two_digit = _A_SHARE_TWO_DIGIT_ROUTES.get(symbol[:2])
    if two_digit is not None:
        return two_digit
    # 上证系列指数（000xxx）与深市股票码空间重叠（000001=平安银行 vs 上证指数）：
    # 裸码按股票路由保持向后兼容，显式 sh（前缀或后缀）时识别为指数。
    # 注意：显式交易所前缀仅用于此处消歧，不做一致性校验（如 SZ561360 静默
    # 归一化为 561360.SH，属存量语义；后缀冲突仍会报错），因为双前缀码段的
    # 交易所归属唯一，前缀写错不会导致错误路由。
    if symbol.startswith("000") and explicit_exchange == "sh":
        return "sh", "index"
    if symbol.startswith(("6", "9")):
        return "sh", "stock"
    if symbol.startswith(("0", "2", "3")):
        return "sz", "stock"
    if symbol.startswith(("4", "8")):
        return "bj", "stock"
    raise ProviderError(
        error_type=ErrorType.INVALID_SYMBOL,
        provider=None,
        message=(
            f"Unsupported A-share prefix: {symbol[0]}. "
            "可转债/国债等债券代码（110/111/113/118/123/127/128 等开头）"
            "与其他非股票证券不在支持范围内；场内基金请改用 stock_kline（K线）"
            "或 iwencai_query(domain=market)。"
        ),
    )
