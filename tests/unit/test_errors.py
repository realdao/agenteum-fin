from src.errors import ErrorType, ProviderError, redact_payload


def test_provider_error_safe_repr_redacts_secrets_and_truncates_payload():
    error = ProviderError(
        error_type=ErrorType.AUTH_ERROR,
        provider="sina",
        message="bad key",
        http_status=401,
        payload={
            "api_key": "secret-key",
            "nested": {"authorization": "Bearer secret-token"},
            "body": "x" * 600,
        },
    )

    safe = error.safe_repr()

    assert safe["error_type"] == "auth_error"
    assert safe["provider"] == "sina"
    assert safe["payload"]["api_key"] == "[REDACTED]"
    assert safe["payload"]["nested"]["authorization"] == "[REDACTED]"
    assert safe["payload"]["body"].endswith("[TRUNCATED]")
    assert len(safe["payload"]["body"]) < 530


def test_error_type_contains_finance_specific_values():
    assert ErrorType.UNSUPPORTED_MARKET.value == "unsupported_market"
    assert ErrorType.UNSUPPORTED_ADJUSTMENT.value == "unsupported_adjustment"
    assert ErrorType.INVALID_SYMBOL.value == "invalid_symbol"


def test_redact_payload_handles_lists():
    payload = [{"token": "secret"}, {"value": "visible"}]

    assert redact_payload(payload)[0]["token"] == "[REDACTED]"
    assert redact_payload(payload)[1]["value"] == "visible"
