import os

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database connection
    postgres_url: PostgresDsn = Field(env='postgres_url')

    # Local app runtime
    app_host: str = Field(default='localhost', env='app_host')
    app_port: int = Field(default=8000, env='app_port')
    app_reload: bool = Field(default=True, env='app_reload')

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        extra = 'allow'