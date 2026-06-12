import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path: Path = Path(".env")) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class LoginConfig:
    login_url: str = os.getenv("LOGIN_URL", "https://app.icad.local/login")
    username: str = os.getenv("LOGIN_USERNAME", "")
    password: str = os.getenv("LOGIN_PASSWORD", "")
    headless: bool = _env_bool("HEADLESS", False)
    timeout_ms: int = int(os.getenv("TIMEOUT_MS", "10000"))


@dataclass(frozen=True)
class EmailConfig:
    enabled: bool = _env_bool("SEND_EMAIL", False)
    api_key: str = os.getenv("MAILJET_API_KEY", "")
    api_secret: str = os.getenv("MAILJET_API_SECRET", "")
    sender_email: str = os.getenv("EMAIL_SENDER", "automation@example.com")
    sender_name: str = os.getenv("EMAIL_SENDER_NAME", "Automation Test")
    recipient_email: str = os.getenv("EMAIL_RECIPIENT", "recipient@example.com")
    recipient_name: str = os.getenv("EMAIL_RECIPIENT_NAME", "Recipient")
    subject: str = os.getenv("EMAIL_SUBJECT", "Automation Test Report")
    body: str = os.getenv("EMAIL_BODY", "Attached automation test report.")
