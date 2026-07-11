import re
from pathlib import Path

FIXTURES = Path(__file__).parents[1] / "fixtures"
PATTERNS = {
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    "email": re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "object-id": re.compile(r"(?<![a-f0-9])[a-f0-9]{24}(?![a-f0-9])", re.I),
    "uuid": re.compile(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", re.I),
    "authorization": re.compile(r'"(?:authorization|cookie|password)"\s*:\s*"(?!<)', re.I),
}


def test_contract_fixtures_contain_no_secrets() -> None:
    for path in FIXTURES.rglob("*.json"):
        text = path.read_text()
        for name, pattern in PATTERNS.items():
            assert not pattern.search(text), f"{name} found in {path}"
