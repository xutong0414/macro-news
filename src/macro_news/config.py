from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path = Path(".env")) -> None:
    """Small .env loader so dry runs work before optional dependencies are installed."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    gemini_api_key: str | None
    gemini_model: str
    deepseek_api_key: str | None
    deepseek_model: str
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    brief_from_email: str | None
    brief_to_email: str | None
    timezone: str
    run_mode: str
    output_dir: Path
    log_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "gemini"),
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY") or None,
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            smtp_host=os.getenv("SMTP_HOST") or None,
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER") or None,
            smtp_password=os.getenv("SMTP_PASSWORD") or None,
            brief_from_email=os.getenv("BRIEF_FROM_EMAIL") or None,
            brief_to_email=os.getenv("BRIEF_TO_EMAIL") or None,
            timezone=os.getenv("BRIEF_TIMEZONE", "Asia/Shanghai"),
            run_mode=os.getenv("BRIEF_RUN_MODE", "sample"),
            output_dir=Path(os.getenv("OUTPUT_DIR", "outputs")),
            log_dir=Path(os.getenv("LOG_DIR", "logs")),
        )

    def missing_for_send(self) -> list[str]:
        required = {
            "SMTP_HOST": self.smtp_host,
            "SMTP_USER": self.smtp_user,
            "SMTP_PASSWORD": self.smtp_password,
            "BRIEF_FROM_EMAIL": self.brief_from_email,
            "BRIEF_TO_EMAIL": self.brief_to_email,
        }
        return [key for key, value in required.items() if not value]

