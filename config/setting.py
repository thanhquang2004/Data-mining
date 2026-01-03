"""
Application settings using Pydantic Settings.
"""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    
    # Application
    APP_NAME: str = "Job Crawler API"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    
    @property
    def DATA_DIR(self) -> Path:
        return self.BASE_DIR / "data"
    
    @property
    def RAW_DATA_DIR(self) -> Path:
        return self.DATA_DIR / "raw"
    
    @property
    def PROCESSED_DATA_DIR(self) -> Path:
        return self.DATA_DIR / "processed"
    
    @property
    def CERTS_DIR(self) -> Path:
        return self.BASE_DIR / "certs"
    
    # Database
    MYSQL_USER: str = "crawler_user"
    MYSQL_PASSWORD: str = "crawler_pass"
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "job_crawler"
    DATABASE_URL: Optional[str] = None
    
    # Database SSL
    DB_SSL_ENABLED: bool = False
    DB_SSL_CA: Optional[str] = None
    DB_SSL_CERT: Optional[str] = None
    DB_SSL_KEY: Optional[str] = None
    DB_SSL_CHECK_HOSTNAME: bool = True
    DB_SSL_VERIFY_IDENTITY: bool = True
    
    # Crawler
    CRAWLER_COOKIES_PATH: Optional[str] = None
    CRAWLER_HEADLESS: bool = True
    CRAWLER_DELAY_MIN: float = 2.0
    CRAWLER_DELAY_MAX: float = 5.0
    
    def model_post_init(self, __context) -> None:
        """Build DATABASE_URL if not provided."""
        if not self.DATABASE_URL:
            object.__setattr__(
                self, 
                "DATABASE_URL",
                f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
                f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            )
    
    def get_ssl_args(self) -> dict:
        """Get SSL arguments for database connection."""
        if not self.DB_SSL_ENABLED:
            return {}
        
        ssl_args = {}
        certs_dir = self.CERTS_DIR
        
        if self.DB_SSL_CA:
            ca_path = Path(self.DB_SSL_CA) if Path(self.DB_SSL_CA).is_absolute() else certs_dir / self.DB_SSL_CA
            ssl_args["ca"] = str(ca_path)
        
        if self.DB_SSL_CERT:
            cert_path = Path(self.DB_SSL_CERT) if Path(self.DB_SSL_CERT).is_absolute() else certs_dir / self.DB_SSL_CERT
            ssl_args["cert"] = str(cert_path)
        
        if self.DB_SSL_KEY:
            key_path = Path(self.DB_SSL_KEY) if Path(self.DB_SSL_KEY).is_absolute() else certs_dir / self.DB_SSL_KEY
            ssl_args["key"] = str(key_path)
        
        if not self.DB_SSL_CHECK_HOSTNAME:
            ssl_args["check_hostname"] = False
        
        if not self.DB_SSL_VERIFY_IDENTITY:
            ssl_args["verify_identity"] = False
        
        return {"ssl": ssl_args} if ssl_args else {}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
