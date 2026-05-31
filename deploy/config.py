from pydantic import BaseSettings


class DeploySettings(BaseSettings):
    app_name: str = "Devin Automation Boilerplate"
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = DeploySettings()
