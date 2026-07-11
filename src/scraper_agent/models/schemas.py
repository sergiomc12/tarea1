"""Modelos Pydantic del dominio."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DiscoveryConfig(BaseModel):
    """Cómo descubrir URLs de artículos."""

    mode: str = "crawl"  # crawl | rss | both
    rss_feeds: list[str] = Field(default_factory=list)
    max_items_per_feed: int = 30
    sitemap_urls: list[str] = Field(default_factory=list)
    expand_sitemaps: bool = True
    article_link_pattern: str | None = None


class ScopeConfig(BaseModel):
    include_subdomains: bool = True
    max_depth: int = 6
    max_pages: int = 5000
    exclude_patterns: list[str] = Field(default_factory=list)


class ConcurrencyConfig(BaseModel):
    max_workers: int = 8
    requests_per_second_per_domain: float = 2.0


class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff_factor: float = 2.0


class RenderConfig(BaseModel):
    mode: str = "auto"  # auto | always | never


class AuthConfig(BaseModel):
    enabled: bool = False
    login_url: str = ""
    username_env: str = "SCRAPER_USERNAME"
    password_env: str = "SCRAPER_PASSWORD"


class AntiDetectionConfig(BaseModel):
    rotate_user_agent: bool = True
    random_delay_range: tuple[float, float] = (1.0, 3.0)
    proxies_env: str = "PROXY_LIST"
    session_warmup: bool = True
    chrome_client_hints: bool = True
    use_playwright_on_403: bool = False
    prefer_playwright: bool = False


class DateRangeConfig(BaseModel):
    """Filtro opcional por fecha de publicación."""

    model_config = ConfigDict(populate_by_name=True)

    from_date: str | None = Field(default=None, alias="from")
    to_date: str | None = Field(default=None, alias="to")


class OutputConfig(BaseModel):
    format: str = "json"
    path: str = "output/resultado.json"
    checkpoint_dir: str = "output/checkpoints"
    incremental: bool = True


class AppConfig(BaseModel):
    domain: str
    scope: ScopeConfig = Field(default_factory=ScopeConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    anti_detection: AntiDetectionConfig = Field(default_factory=AntiDetectionConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    respect_robots_txt: bool = True
    selectors: dict[str, str] = Field(default_factory=dict)
    date_range: DateRangeConfig | None = None


class CrawlRunSummary(BaseModel):
    """Resumen de corrida (formato nuevo scraper-schema)."""

    crawl_id: str
    domain: str
    total_pages_visited: int = 0
    total_articles_extracted: int = 0
    crawl_started_at: datetime
    crawl_finished_at: datetime | None = None
    robots_txt_respected: bool = True
