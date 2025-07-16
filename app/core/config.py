"""
Madagascar License System Configuration
Compatible with Pydantic v2 and modern dependencies for Render.com
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict, Any, Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """Application settings for Madagascar License System
    
    TODO: Configuration Enhancements
    ================================
    - TODO: Add location-specific configuration settings
    - TODO: Add device registration settings
    - TODO: Add printing system configuration
    - TODO: Add external integration settings (when needed)
    - TODO: Add production vs development environment configurations
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Madagascar Driver's License System"
    VERSION: str = "1.0.0"
    
    # Development/Debug Configuration
    DEBUG: bool = False
    
    # Security Configuration
    SECRET_KEY: str = "your-very-secure-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # CORS Configuration - Specific origins required for credentials mode
    ALLOWED_ORIGINS: str = "https://linc-print-frontend.vercel.app,https://linc-print-frontend-git-main-schuttebjs-projects.vercel.app,https://linc-print-frontend-schuttebjs-projects.vercel.app,http://localhost:3000,http://localhost:5173"
    ALLOWED_HOSTS: str = "*"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Convert ALLOWED_ORIGINS string to list and add Vercel preview domains"""
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        try:
            import json
            origins = json.loads(self.ALLOWED_ORIGINS)
        except:
            origins = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
            origins = [origin for origin in origins if origin]
        
        # Add common Vercel preview patterns
        preview_patterns = [
            "https://linc-print-frontend-git-main-schuttebjs-projects.vercel.app",
            "https://linc-print-frontend-schuttebjs-projects.vercel.app"
        ]
        origins.extend(preview_patterns)
        
        return origins
    
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
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/madagascar_license"
    DB_SSL_MODE: str = "prefer"
    
    # File Storage Configuration
    FILE_STORAGE_PATH: str = "/var/madagascar-license-data"
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/gif,image/bmp,image/tiff"
    ALLOWED_DOCUMENT_TYPES: str = "application/pdf,image/jpeg,image/png"
    
    @property
    def allowed_image_types_list(self) -> List[str]:
        try:
            import json
            return json.loads(self.ALLOWED_IMAGE_TYPES)
        except:
            return [mime_type.strip() for mime_type in self.ALLOWED_IMAGE_TYPES.split(",")]
    
    @property
    def allowed_document_types_list(self) -> List[str]:
        try:
            import json
            return json.loads(self.ALLOWED_DOCUMENT_TYPES)
        except:
            return [mime_type.strip() for mime_type in self.ALLOWED_DOCUMENT_TYPES.split(",")]
    
    # Country Configuration
    COUNTRY_CODE: str = "MG"
    COUNTRY_NAME: str = "Madagascar"
    CURRENCY: str = "MGA"
    
    # Madagascar-specific settings
    SUPPORTED_ID_TYPES: List[str] = ["CIN", "CNI", "PASSPORT", "BIRTH_CERT"]
    SUPPORTED_LANGUAGES: List[str] = ["mg", "fr", "en"]
    DEFAULT_LANGUAGE: str = "mg"
    
    # License types available in Madagascar
    AVAILABLE_LICENSE_TYPES: List[str] = ["A", "B", "C", "D", "EB", "EC"]
    
    # Age requirements for license types (Madagascar-specific)
    AGE_REQUIREMENTS: Dict[str, int] = {
        "A": 16,    # Motorcycle
        "B": 18,    # Light vehicle
        "C": 21,    # Heavy vehicle
        "D": 24     # Bus/taxi
    }
    
    # Fee structure (in Malagasy Ariary)
    FEE_STRUCTURE: Dict[str, float] = {
        "learners_license": 25000.00,      # ~5 USD
        "drivers_license": 50000.00,       # ~10 USD
        "license_renewal": 40000.00,       # ~8 USD
        "duplicate_license": 30000.00,     # ~6 USD
        "international_permit": 75000.00    # ~15 USD
    }
    
    # System Performance
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 30
    
    # Audit Configuration
    AUDIT_LOG_RETENTION_DAYS: int = 2555  # 7 years
    ENABLE_FILE_AUDIT_LOGS: bool = True
    ENABLE_PERFORMANCE_MONITORING: bool = True
    
    # Card Production
    CARD_PRODUCTION_MODE: str = "local"
    ISO_18013_COMPLIANCE: bool = True
    
    def get_file_storage_path(self) -> Path:
        """Get file storage path for Madagascar"""
        base_path = Path(self.FILE_STORAGE_PATH)
        
        # For development, use local static folder if production path doesn't exist
        if not base_path.exists() and self.ENVIRONMENT == "development":
            # Use static folder relative to app directory
            from pathlib import Path
            app_dir = Path(__file__).parent.parent
            local_storage = app_dir.parent / "static" / "uploads"
            local_storage.mkdir(parents=True, exist_ok=True)
            return local_storage
        
        return base_path / self.COUNTRY_CODE


settings = Settings()


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


def get_settings() -> Settings:
    """Get application settings instance"""
    return Settings()


def get_madagascar_config() -> MadagascarConfig:
    """Get Madagascar-specific configuration"""
    return MadagascarConfig() 