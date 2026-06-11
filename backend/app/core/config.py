from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ========== MySQL ==========
    db_host: str = Field(default="127.0.0.1")
    db_port: int = Field(default=3306)
    db_user: str = Field(default="root")
    db_password: str = Field(default="")
    db_name: str = Field(default="simplerag")

    # ========== Qdrant ==========
    qdrant_host: str = Field(default="127.0.0.1")
    qdrant_port: int = Field(default=6333)
    qdrant_api_key: str = Field(default="")
    qdrant_collection_name: str = Field(default="simplerag")

    # ========== LLM 模型 ==========
    openai_model: str = Field(default="gpt-4o-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="https://api.openai.com/v1")

    # ========== 应用 ==========
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=7500)
    debug: bool = Field(default=False)

    # ========== JWT ==========
    jwt_secret_key: str = Field(default="change-me-to-a-random-secret")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_days: int = Field(default=7)

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
