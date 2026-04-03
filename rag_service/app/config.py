"""
RAG Service Config
"""

from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    """RAG Service settings"""
    
    DATABASE_URL: str = "postgresql://user:password@postgres:5432/ai_ba_agent"
    
    # LLM
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    PRIMARY_MODEL: str = "deepseek/deepseek-chat"
    FALLBACK_MODEL: str = "openai/gpt-4o-mini"
    
    # Vector DB (Qdrant)
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_TIMEOUT: int = 30
    
    # Redis (Memory)
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Service URLs
    BACKEND_URL: str = "http://backend:5000"
    AUTH_SERVICE_URL: str = "http://auth_service:5001"
    
    # STT (Speech-to-Text)
    ELEVENLABS_API_KEY: str = ""
    DEEPGRAM_API_KEY: str = ""
    
    # External APIs
    GMAIL_SCOPES: List[str] = ["https://www.googleapis.com/auth/gmail.readonly"]
    GOOGLE_DRIVE_SCOPES: List[str] = ["https://www.googleapis.com/auth/drive.readonly"]
    
    # RAG/Embedding
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    
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


