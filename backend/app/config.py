from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    database_url: str = "sqlite:///agent_mvp.db"
    llm_provider: str = "mock"
    llm_model: str = "mock-model"
    llm_api_key: str = ""
    model_config_encryption_key: str = ""
    web_search_enabled: bool = True
    search_primary_provider: str = "searxng"
    search_fallback_enabled: bool = True
    search_fallback_providers: str = "duckduckgo,tavily"
    search_cache_ttl_seconds: int = 3600
    search_cache_max_size: int = 1000
    search_max_results: int = 5
    search_timeout_seconds: int = 10
    searxng_base_url: str = ""
    bocha_api_key: str = ""
    bocha_base_url: str = ""
    tavily_api_key: str = ""
    tavily_base_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


def get_settings() -> Settings:
    return Settings()
