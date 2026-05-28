import os

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database connection
    postgres_url: PostgresDsn = Field(env='postgres_url')

    # Kafka consumer
    kafka_bootstrap_servers: str = Field(default='localhost:9092', env='kafka_bootstrap_servers')
    kafka_order_feedback_created_topic: str = Field(
        default='orders.order-feedback-created',
        env='kafka_order_feedback_created_topic',
    )
    kafka_order_feedback_created_dlq_topic: str = Field(
        default='orders.order-feedback-created.dlq',
        env='kafka_order_feedback_created_dlq_topic',
    )
    kafka_consumer_group_id: str = Field(
        default='users-order-feedback-created',
        env='kafka_consumer_group_id',
    )

    # Order feedback events consumer retry
    consumer_retry_max_attempts: int = Field(default=5, env='consumer_retry_max_attempts')
    consumer_retry_initial_seconds: float = Field(
        default=1.0, env='consumer_retry_initial_seconds'
    )
    consumer_retry_cap_seconds: float = Field(default=30.0, env='consumer_retry_cap_seconds')

    # Local app runtime
    app_host: str = Field(default='localhost', env='app_host')
    app_port: int = Field(default=8000, env='app_port')
    app_reload: bool = Field(default=True, env='app_reload')

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        extra = 'allow'