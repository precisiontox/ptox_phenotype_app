import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")

    # SSH settings
    SSH_HOST = os.getenv("SSH_HOST")
    SSH_PORT = int(os.getenv("SSH_PORT", 22))
    SSH_USERNAME = os.getenv("SSH_USERNAME")
    SSH_PASSWORD = os.getenv("SSH_PASSWORD")

    SSH_PRIVATE_KEY = os.getenv("SSH_PRIVATE_KEY")
    SSH_PRIVATE_KEY_PASSWORD = os.getenv("SSH_PRIVATE_KEY_PASSWORD")

    # PostgreSQL settings
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    SQLALCHEMY_POOL_SIZE = int(os.getenv("SQLALCHEMY_POOL_SIZE", 5))
    SQLALCHEMY_MAX_OVERFLOW = int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", 10))
    SQLALCHEMY_POOL_PRE_PING = True

    @classmethod
    def validate(cls):
        required = [
            "SSH_HOST",
            "SSH_USERNAME",
            "DB_NAME",
            "DB_USER",
            "DB_PASSWORD",
        ]
        missing = [name for name in required if not getattr(cls, name)]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
