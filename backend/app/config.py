"""
Configuration & Environment Variables
"""

from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@postgres:5432/ai_ba_agent"
    SQLALCHEMY_ECHO: bool = False
    
    # JWT & Auth
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Service connection
    AUTH_SERVICE_URL: str = "http://auth_service:5001"
    RAG_SERVICE_URL: str = "http://rag_service:5002"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://frontend:3000",
        "http://localhost",
    ]
    
    # Environment
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # External APIs
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Google Drive
    GOOGLE_DRIVE_CREDENTIALS_JSON: str = ""   # JSON string of service account
    GOOGLE_DRIVE_CREDENTIALS_PATH: str = ""   # or file path in container
    GOOGLE_DRIVE_FOLDER_ID: str = ""

    # ElevenLabs Scribe v2 STT
    ELEVENLABS_API_KEY: str = ""
    BACKEND_URL: str = "http://backend:5000"  # used in STT callback URL

    # n8n Workflow Automation
    N8N_WEBHOOK_URL: str = ""  # e.g. http://n8n:5678/webhook/document-upload

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
