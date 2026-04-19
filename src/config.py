import os

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_url: PostgresDsn = Field(env='postgres_url')

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
