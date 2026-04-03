"""
Auth Service Config
"""

from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    """Auth Service settings"""
    
    DATABASE_URL: str = "postgresql://user:password@postgres:5432/ai_ba_agent"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://frontend:3000",
        "http://localhost",
    ]
    
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
