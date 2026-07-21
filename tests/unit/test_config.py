import logging

import pytest

from src.config import Settings, is_remote_bind_host


def test_settings_defaults_match_spec():
    settings = Settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8766
    assert settings.allow_remote is False
    assert settings.fin_request_timeout == 15.0
    assert settings.fin_retry_attempts == 1
    assert settings.fin_a_kline_provider == "mootdx"
    assert settings.fin_hk_kline_provider == "none"
    assert settings.fin_profile_provider == "tencent"
    assert settings.fin_financial_statements_provider == "sina"
    assert settings.fin_f10_provider == "mootdx"
    assert settings.fin_announcements_provider == "cninfo"
    assert settings.fin_research_reports_provider == "eastmoney"
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
