import logging

import pytest

from src.config import Settings, is_remote_bind_host


def test_settings_defaults_match_spec(monkeypatch):
    # 隔离真实 .env 与环境变量，断言的是代码默认值而非本机配置。
    for var in (
        "AGENTEUM_HOST",
        "AGENTEUM_PORT",
        "AGENTEUM_ALLOW_REMOTE",
        "AGENTEUM_FIN_REQUEST_TIMEOUT",
        "AGENTEUM_FIN_RETRY_ATTEMPTS",
        "AGENTEUM_FIN_A_KLINE_PROVIDER",
        "AGENTEUM_FIN_HK_KLINE_PROVIDER",
        "AGENTEUM_FIN_PROFILE_PROVIDER",
        "AGENTEUM_FIN_FINANCIAL_STATEMENTS_PROVIDER",
        "AGENTEUM_FIN_FUNDAMENTAL_PROFILE_PROVIDER",
        "AGENTEUM_FIN_FUNDAMENTAL_FINANCIALS_PROVIDER",
        "AGENTEUM_FIN_ANNOUNCEMENTS_PROVIDER",
        "AGENTEUM_FIN_IWENCAI_PROVIDER",
    ):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)

    assert settings.host == "127.0.0.1"
    assert settings.port == 8766
    assert settings.allow_remote is False
    assert settings.fin_request_timeout == 15.0
    assert settings.fin_retry_attempts == 1
    assert settings.fin_a_kline_provider == "tencent"
    assert settings.fin_hk_kline_provider == "tencent"
    assert settings.fin_profile_provider == "tencent"
    assert settings.fin_financial_statements_provider == "sina"
    assert settings.fin_fundamental_profile_provider == "eastmoney"
    assert settings.fin_fundamental_financials_provider == "akshare"
    assert settings.fin_announcements_provider == "cninfo"
    assert settings.fin_iwencai_provider == "iwencai"


def test_iwencai_api_key_falls_back_to_skill_ecosystem_env(monkeypatch):
    # 显式传 None，隔离 .env / 环境变量中已配置密钥的影响。
    monkeypatch.delenv("IWENCAI_API_KEY", raising=False)
    assert Settings(AGENTEUM_FIN_IWENCAI_API_KEY=None).resolved_iwencai_api_key is None

    monkeypatch.setenv("IWENCAI_API_KEY", "eco-key")
    assert Settings(AGENTEUM_FIN_IWENCAI_API_KEY=None).resolved_iwencai_api_key == "eco-key"
    assert (
        Settings(AGENTEUM_FIN_IWENCAI_API_KEY="explicit-key").resolved_iwencai_api_key
        == "explicit-key"
    )


def test_remote_bind_requires_explicit_allow_remote():
    settings = Settings(AGENTEUM_HOST="0.0.0.0", AGENTEUM_ALLOW_REMOTE=False)

    with pytest.raises(ValueError):
        settings.validate_network_binding(logging.getLogger("test"))


def test_loopback_hosts_are_not_remote():
    assert is_remote_bind_host("127.0.0.1") is False
    assert is_remote_bind_host("localhost") is False
    assert is_remote_bind_host("0.0.0.0") is True
