"""Settings from environment variables (see .env.example)."""
import os
from dataclasses import dataclass

from app.money import parse_split


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    db_ssl: bool
    allowed_user_ids: frozenset[int]
    split: list[tuple[str, int]]
    currency: str
    webhook_base_url: str
    port: int


def load_settings() -> Settings:
    def required(name: str) -> str:
        value = os.getenv(name, "").strip()
        if not value:
            raise RuntimeError(f"Environment variable {name} is not set")
        return value

    ids = os.getenv("ALLOWED_USER_IDS", "").replace(" ", "")
    return Settings(
        bot_token=required("BOT_TOKEN"),
        database_url=required("DATABASE_URL"),
        db_ssl=os.getenv("DB_SSL", "true").lower() == "true",
        allowed_user_ids=frozenset(int(x) for x in ids.split(",") if x),
        split=parse_split(os.getenv("SPLIT", "Общий счёт:40,Накопления:40,Личное:20")),
        currency=os.getenv("CURRENCY", "₽"),
        webhook_base_url=os.getenv("WEBHOOK_BASE_URL", os.getenv("RENDER_EXTERNAL_URL", "")),
        port=int(os.getenv("PORT", "8080")),
    )
