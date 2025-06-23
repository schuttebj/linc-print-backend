"""
Madagascar License System Configuration
Compatible with Pydantic v1 and older dependencies for Render.com
"""

from pydantic import BaseSettings
from typing import List, Dict, Any, Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """Application settings for Madagascar License System"""
    
    class Config:
        env_file = ".env"
        env_ignore_empty = True
        extra = "ignore"
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Madagascar Driver's License System"
    VERSION: str = "1.0.0"
    
    # Security Configuration
    SECRET_KEY: str = "your-very-secure-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours for office work
    
    # CORS Configuration
    ALLOWED_ORIGINS: str = "https://your-frontend.vercel.app,http://localhost:3000,http://localhost:5173"
    ALLOWED_HOSTS: str = "*"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Convert ALLOWED_ORIGINS string to list"""
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        try:
            import json
            return json.loads(self.ALLOWED_ORIGINS)
        except:
            origins = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
            return [origin for origin in origins if origin]
    
    @property
    def allowed_hosts_list(self) -> List[str]:
        """Convert ALLOWED_HOSTS string to list"""
        if self.ALLOWED_HOSTS == "*":
            return ["*"]
        try:
            import json
            return json.loads(self.ALLOWED_HOSTS)
        except:
            return [host.strip() for host in self.ALLOWED_HOSTS.split(",")]
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/madagascar_license_db"
    DB_SSL_MODE: str = "prefer"
    
    # File Storage Configuration
    FILE_STORAGE_PATH: str = "/var/madagascar-license-data"
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/gif,image/bmp,image/tiff"
    ALLOWED_DOCUMENT_TYPES: str = "application/pdf,image/jpeg,image/png"
    
    # Backup Configuration
    BACKUP_RETENTION_DAILY: int = 30
    BACKUP_RETENTION_WEEKLY: int = 12
    ENABLE_AUTO_BACKUP: bool = True
    
    @property
    def allowed_image_types_list(self) -> List[str]:
        """Convert ALLOWED_IMAGE_TYPES string to list"""
        try:
            import json
            return json.loads(self.ALLOWED_IMAGE_TYPES)
        except:
            return [mime_type.strip() for mime_type in self.ALLOWED_IMAGE_TYPES.split(",")]
    
    @property
    def allowed_document_types_list(self) -> List[str]:
        """Convert ALLOWED_DOCUMENT_TYPES string to list"""
        try:
            import json
            return json.loads(self.ALLOWED_DOCUMENT_TYPES)
        except:
            return [mime_type.strip() for mime_type in self.ALLOWED_DOCUMENT_TYPES.split(",")]
    
    # Audit Configuration
    AUDIT_LOG_RETENTION_DAYS: int = 2555  # 7 years
    ENABLE_FILE_AUDIT_LOGS: bool = True
    ENABLE_PERFORMANCE_MONITORING: bool = True
    
    # Madagascar Country Configuration
    COUNTRY_CODE: str = "MG"
    COUNTRY_NAME: str = "Madagascar"
    CURRENCY: str = "MGA"
    DEFAULT_LANGUAGE: str = "en"  # Start with English, translate to French later
    TIMEZONE: str = "Indian/Antananarivo"
    
    # Performance Configuration
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 30
    
    # Card Production Configuration
    CARD_PRODUCTION_MODE: str = "distributed"  # Madagascar uses distributed printing
    ISO_18013_COMPLIANCE: bool = True  # Driver's license standard
    ISO_7810_COMPLIANCE: bool = True   # National ID standard
    
    # Development Settings
    DEBUG: bool = False
    TESTING: bool = False
    
    def get_file_storage_path(self) -> Path:
        """Get file storage path for Madagascar"""
        return Path(self.FILE_STORAGE_PATH) / self.COUNTRY_CODE


class MadagascarConfig(BaseSettings):
    """Madagascar-specific configuration"""
    
    class Config:
        extra = "allow"
    
    country_code: str = "MG"
    country_name: str = "Madagascar"
    currency: str = "MGA"
    languages: List[str] = ["en", "fr", "mg"]  # English, French, Malagasy
    default_language: str = "en"
    
    # System modules available
    modules: Dict[str, bool] = {
        "users": True,
        "persons": True, 
        "applications": True,
        "printing": True,
        "reports": True,
        "locations": True
    }
    
    # Madagascar license types
    license_types: List[str] = [
        "A",   # Motorcycle
        "B",   # Light vehicle  
        "C",   # Heavy vehicle
        "D",   # Bus/taxi
        "EB",  # Light trailer
        "EC"   # Heavy trailer
    ]
    
    # Madagascar ID document types
    id_document_types: List[str] = [
        "CIN",       # Carte d'Identité Nationale (National ID)
        "CNI",       # Carte Nationale d'Identité  
        "PASSPORT",  # Passport
        "BIRTH_CERT" # Birth certificate (for minors)
    ]
    
    # Distributed printing configuration
    printing_config: Dict[str, Any] = {
        "type": "distributed",
        "cross_location_backup": True,
        "iso_standards": ["ISO_18013", "ISO_7810"],
        "barcode_standard": "PDF417",
        "locations": []  # Will be populated from database
    }
    
    # Age requirements for license types (Madagascar specific)
    age_requirements: Dict[str, int] = {
        "A": 16,    # Motorcycle
        "B": 18,    # Light vehicle
        "C": 21,    # Heavy vehicle
        "D": 24     # Bus/taxi
    }
    
    # Fee structure in Madagascar Ariary (MGA)
    fee_structure: Dict[str, float] = {
        "learners_license": 15000.00,      # ~$3.75 USD
        "drivers_license": 50000.00,       # ~$12.50 USD  
        "license_renewal": 40000.00,       # ~$10.00 USD
        "duplicate_license": 30000.00,     # ~$7.50 USD
        "prdp_application": 100000.00      # ~$25.00 USD
    }
    
    # User roles and permissions structure
    user_roles: Dict[str, Dict] = {
        "clerk": {
            "display_name": "License Clerk",
            "description": "Process license applications and basic card operations",
            "modules": ["persons", "applications", "printing"],
            "capabilities": [
                "license_applications.create",
                "license_applications.read",
                "license_applications.update",
                "card_management.order",
                "card_management.issue",
                "card_management.reorder",
                "biometric_data.capture",
                "biometric_data.view",
                "biometric_data.update",
                "payment_processing.process",
                "payment_processing.view"
            ]
        },
        "supervisor": {
            "display_name": "License Supervisor", 
            "description": "Supervise operations with approval authority",
            "inherits": "clerk",
            "additional_modules": ["reports"],
            "additional_capabilities": [
                "license_applications.approve",
                "card_management.approve",
                "card_management.qa_approve",
                "card_management.qa_reject",
                "reports.view_basic",
                "reports.view_advanced",
                "reports.export"
            ]
        },
        "printer": {
            "display_name": "Card Printer Operator",
            "description": "Specialized printing operations only",
            "modules": ["printing"],
            "capabilities": [
                "printing.local_print",
                "printing.cross_location_print", 
                "printing.manage_queue",
                "printing.monitor_status"
            ]
        }
    }


# Global settings instance
settings = Settings()

# Madagascar configuration instance  
madagascar_config = MadagascarConfig()


def get_settings() -> Settings:
    """Get application settings"""
    return settings


def get_madagascar_config() -> MadagascarConfig:
    """Get Madagascar-specific configuration"""
    return madagascar_config 