from pydantic import BaseSettings, AnyUrl, Field


class Settings(BaseSettings):
    github_token: str = Field(..., env="GITHUB_TOKEN")
    github_repo: str = Field(..., env="GITHUB_REPO")
    github_webhook_secret: str = Field(..., env="GITHUB_WEBHOOK_SECRET")

    devin_api_key: str = Field(..., env="DEVIN_API_KEY")
    devin_org_id: str = Field(..., env="DEVIN_ORG_ID")
    devin_repo_urls: str = Field(..., env="DEVIN_REPO_URLS")
    devin_mode: str = Field("normal", env="DEVIN_MODE")

    database_url: str = Field("postgresql://postgres:postgres@db:5432/devin_automation", env="DATABASE_URL")
    log_file: str = Field("automation.log", env="LOG_FILE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
