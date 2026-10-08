"""Configuration: every value from the environment (or a .env file outside
the repository), never from code. One object, read once at start.

Secrets (database password, OAuth and model keys) live only here, on the
server; nothing in this module is ever sent to a browser."""
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GNOSIS_", env_file=".env", extra="ignore")

    environment: str = Field("development", pattern="^(development|test|staging|production)$")
    database_url: SecretStr = SecretStr("postgresql+psycopg://gnosis@127.0.0.1:5432/gnosis")
    # public addresses, so nothing assumes a host or a hosting provider
    public_url: str = "http://localhost:5173"            # the learner app
    admin_url: str = "http://localhost:5174"             # the admin app
    api_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    log_json: bool = True
    # Step M2 (until our own sign-in, M3): the current app's server is the only
    # caller. It signs people in and tells the API who is acting, proving
    # itself with one of these tokens (comma-separated, so one can be rotated
    # without downtime). Never given to a browser.
    service_tokens: SecretStr = SecretStr("")
    timezone: str = "Asia/Taipei"        # the server's "today" for counts (as the old database function did)
    db_pool_size: int = 5
    db_timeout_seconds: float = 10.0

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def settings() -> Settings:
    return Settings()
