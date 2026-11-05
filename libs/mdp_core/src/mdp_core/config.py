"""Configuration, read from the environment.

Nothing in this repo takes a credential or an endpoint from a literal in source.
The previous version of this project hardcoded five different API keys, which
then sat in a public git history for four years.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Kafka
    kafka_bootstrap: str = "localhost:19092"
    ticks_topic: str = "ticks.raw"
    ticks_dlq_topic: str = "ticks.dlq"
    ticks_late_topic: str = "ticks.late"
    bars_topic: str = "bars.1m"
    schema_registry_url: str = "http://localhost:18081"

    # ClickHouse
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_db: str = "market"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    # Feeds
    crypto_symbols: str = "BTC-USD,ETH-USD,SOL-USD"
    coinbase_ws_url: str = "wss://ws-feed.exchange.coinbase.com"

    # Batch sources
    fred_api_key: str = ""
    edgar_tickers: str = "AAPL,MSFT,GOOGL,AMZN,TSLA,META"
    # SEC requires a descriptive User-Agent with contact details.
    sec_user_agent: str = "market-data-pipeline (contact: set SEC_USER_AGENT)"

    # Observability. Empty disables tracing entirely.
    otel_exporter_otlp_endpoint: str = ""

    # Ops
    metrics_port: int = Field(default=9100, description="Prometheus scrape port")
    log_level: str = "INFO"

    @property
    def symbols(self) -> list[str]:
        return [s.strip() for s in self.crypto_symbols.split(",") if s.strip()]

    @property
    def edgar_ticker_list(self) -> list[str]:
        return [t.strip().upper() for t in self.edgar_tickers.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
