from decimal import Decimal

import pytest

from ebinexpy.config import ClientConfig
from ebinexpy.core.logging import REDACTED, redact, redact_text
from ebinexpy.core.money import as_decimal, quantize_money


def test_decimal_conversion_and_quantization() -> None:
    assert as_decimal(0.1) == Decimal("0.1")
    assert quantize_money("0.965") == Decimal("0.97")


def test_redacts_structured_and_text_secrets() -> None:
    assert redact({"authorization": "Bearer value", "safe": 1}) == {
        "authorization": REDACTED,
        "safe": 1,
    }
    assert "token-value" not in redact_text("?authorization=token-value&x=1")


def test_config_rejects_insecure_endpoint() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        ClientConfig(http_base_url="http://example.test")
