"""
CRUD Audit Decorators for Madagascar License System
Provides reusable decorators to automatically log all CRUD operations with old/new value tracking
"""

import functools
from typing import Any, Dict, Optional, Union, Type, Callable
from fastapi import Request
from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect
import uuid
import json
from datetime import datetime

from app.services.audit_service import MadagascarAuditService, create_user_context, AuditLogData
from app.models.user import User
from app.models.base import BaseModel


class AuditHelper:
    """Helper class for extracting model data and managing audit operations"""
    
    @staticmethod
    def model_to_dict(model: BaseModel, exclude_fields: Optional[set] = None) -> Dict[str, Any]:
        """Convert SQLAlchemy model to dictionary, handling special types"""
        if not model:
            return {}
            
        exclude_fields = exclude_fields or {
            'created_at', 'updated_at', 'created_by', 'updated_by', 
            'is_active', 'deleted_at', 'deleted_by'
        }
        
        result = {}
        mapper = inspect(model.__class__)
        
        for column in mapper.columns:
            if column.name in exclude_fields:
                continue
                
            value = getattr(model, column.name, None)
            
            # Handle special types for JSON serialization
            if value is not None:
                if isinstance(value, uuid.UUID):
                    result[column.name] = str(value)
                elif isinstance(value, datetime):
                    result[column.name] = value.isoformat()
                elif hasattr(value, '__dict__'):  # Enum or complex object
                    result[column.name] = str(value)
                else:
                    result[column.name] = value
        
        return result
    
    @staticmethod
    def get_model_identifier(model: BaseModel) -> str:
        """Get a human-readable identifier for the model"""
        # Try common identifier fields in order of preference
        for field in ['name', 'title', 'display_name', 'username', 'email', 'id']:
            if hasattr(model, field):
                value = getattr(model, field)
                if value:
                    return str(value)
        return str(model.id) if hasattr(model, 'id') else 'unknown'
    
    @staticmethod
    def get_resource_type(model: Union[BaseModel, Type[BaseModel]]) -> str:
        """Get resource type name from model class"""
        if isinstance(model, type):
            return model.__name__.upper()
        return model.__class__.__name__.upper()


def audit_create(
    resource_type: Optional[str] = None,
    screen_reference: Optional[str] = None,
    exclude_fields: Optional[set] = None
):
    """Decorator for CREATE operations"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute the original function
            result = await func(*args, **kwargs) if hasattr(func, '__await__') else func(*args, **kwargs)
            
            try:
                # Extract context from function arguments
                db: Session = None
                current_user: User = None
                request: Request = None
                
                # Find db, user, and request in args/kwargs
                for arg in args:
                    if isinstance(arg, Session):
                        db = arg
                    elif isinstance(arg, User):
                        current_user = arg
                    elif isinstance(arg, Request):
                        request = arg
                
                for key, value in kwargs.items():
                    if key == 'db' and isinstance(value, Session):
                        db = value
                    elif key in ['current_user', 'user'] and isinstance(value, User):
                        current_user = value
                    elif key == 'request' and isinstance(value, Request):
                        request = value
                
                # Only audit if we have the necessary context
                if db and current_user and result:
                    audit_service = MadagascarAuditService(db)
                    
                    # Determine resource type and data
                    res_type = resource_type or AuditHelper.get_resource_type(result)
                    resource_id = str(result.id) if hasattr(result, 'id') else None
                    resource_data = AuditHelper.model_to_dict(result, exclude_fields)
                    
                    # Create user context
                    user_context = create_user_context(
                        current_user, 
                        request or type('MockRequest', (), {'client': type('Client', (), {'host': 'unknown'})(), 'headers': {}})()
                    )
                    
                    # Log the creation
                    audit_service.log_creation(
                        resource_type=res_type,
                        resource_id=resource_id,
                        resource_data=resource_data,
                        user_context=user_context,
                        screen_reference=screen_reference,
                        endpoint=request.url.path if request else None,
                        method=request.method if request else 'POST'
                    )
                    
            except Exception as e:
                # Don't let audit failures break the main operation
                print(f"Audit logging failed for CREATE operation: {e}")
            
            return result
        return wrapper
    return decorator


def audit_update(
    resource_type: Optional[str] = None,
    screen_reference: Optional[str] = None,
    exclude_fields: Optional[set] = None,
    get_old_data: Optional[Callable] = None
):
    """Decorator for UPDATE operations"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Capture old data before update
            old_data = {}
            db: Session = None
            current_user: User = None
            request: Request = None
            resource_id = None
            
            # Extract context and try to get old data
            for arg in args:
                if isinstance(arg, Session):
                    db = arg
                elif isinstance(arg, User):
                    current_user = arg
                elif isinstance(arg, Request):
                    request = arg
            
            for key, value in kwargs.items():
                if key == 'db' and isinstance(value, Session):
                    db = value
                elif key in ['current_user', 'user'] and isinstance(value, User):
                    current_user = value
                elif key == 'request' and isinstance(value, Request):
                    request = value
                elif key in ['id', 'resource_id', 'obj_id']:
                    resource_id = str(value)
            
            # Try to get old data if we have the necessary info
            if db and resource_id and get_old_data:
                try:
                    old_model = get_old_data(db, resource_id)
                    if old_model:
                        old_data = AuditHelper.model_to_dict(old_model, exclude_fields)
                except Exception:
                    pass
            
            # Execute the original function
            result = await func(*args, **kwargs) if hasattr(func, '__await__') else func(*args, **kwargs)
            
            try:
                # Only audit if we have the necessary context
                if db and current_user and result:
                    audit_service = MadagascarAuditService(db)
                    
                    # Get new data
                    new_data = AuditHelper.model_to_dict(result, exclude_fields)
                    res_type = resource_type or AuditHelper.get_resource_type(result)
                    resource_id = str(result.id) if hasattr(result, 'id') else resource_id
                    
                    # Create user context
                    user_context = create_user_context(
                        current_user, 
                        request or type('MockRequest', (), {'client': type('Client', (), {'host': 'unknown'})(), 'headers': {}})()
                    )
                    
                    # Log the data change
                    audit_service.log_data_change(
                        resource_type=res_type,
                        resource_id=resource_id,
                        old_data=old_data,
                        new_data=new_data,
                        user_context=user_context,
                        screen_reference=screen_reference,
                        endpoint=request.url.path if request else None,
                        method=request.method if request else 'PUT'
                    )
                    
            except Exception as e:
                # Don't let audit failures break the main operation
                print(f"Audit logging failed for UPDATE operation: {e}")
            
            return result
        return wrapper
    return decorator


def audit_delete(
    resource_type: Optional[str] = None,
    screen_reference: Optional[str] = None,
    exclude_fields: Optional[set] = None,
    get_data_before_delete: Optional[Callable] = None
):
    """Decorator for DELETE operations"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Capture data before deletion
            old_data = {}
            db: Session = None
            current_user: User = None
            request: Request = None
            resource_id = None
            
            # Extract context
            for arg in args:
                if isinstance(arg, Session):
                    db = arg
                elif isinstance(arg, User):
                    current_user = arg
                elif isinstance(arg, Request):
                    request = arg
            
            for key, value in kwargs.items():
                if key == 'db' and isinstance(value, Session):
                    db = value
                elif key in ['current_user', 'user'] and isinstance(value, User):
                    current_user = value
                elif key == 'request' and isinstance(value, Request):
                    request = value
                elif key in ['id', 'resource_id', 'obj_id']:
                    resource_id = str(value)
            
            # Get data before deletion
            if db and resource_id and get_data_before_delete:
                try:
                    old_model = get_data_before_delete(db, resource_id)
                    if old_model:
                        old_data = AuditHelper.model_to_dict(old_model, exclude_fields)
                        if not resource_type:
                            resource_type = AuditHelper.get_resource_type(old_model)
                except Exception:
                    pass
            
            # Execute the original function
            result = await func(*args, **kwargs) if hasattr(func, '__await__') else func(*args, **kwargs)
            
            try:
                # Only audit if we have the necessary context
                if db and current_user and old_data:
                    audit_service = MadagascarAuditService(db)
                    
                    # Create user context
                    user_context = create_user_context(
                        current_user, 
                        request or type('MockRequest', (), {'client': type('Client', (), {'host': 'unknown'})(), 'headers': {}})()
                    )
                    
                    # Log the deletion
                    audit_service.log_deletion(
                        resource_type=resource_type or 'UNKNOWN',
                        resource_id=resource_id,
                        resource_data=old_data,
                        user_context=user_context,
                        screen_reference=screen_reference,
                        endpoint=request.url.path if request else None,
                        method=request.method if request else 'DELETE'
                    )
                    
            except Exception as e:
                # Don't let audit failures break the main operation
                print(f"Audit logging failed for DELETE operation: {e}")
            
            return result
        return wrapper
    return decorator


def audit_read(
    resource_type: Optional[str] = None,
    screen_reference: Optional[str] = None,
    sensitive_only: bool = True
):
    """Decorator for READ operations (only for sensitive data)"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute the original function
            result = await func(*args, **kwargs) if hasattr(func, '__await__') else func(*args, **kwargs)
            
            # Only log if this is marked as sensitive data
            if not sensitive_only:
                return result
            
            try:
                # Extract context
                db: Session = None
                current_user: User = None
                request: Request = None
                resource_id = None
                
                for arg in args:
                    if isinstance(arg, Session):
                        db = arg
                    elif isinstance(arg, User):
                        current_user = arg
                    elif isinstance(arg, Request):
                        request = arg
                
                for key, value in kwargs.items():
                    if key == 'db' and isinstance(value, Session):
                        db = value
                    elif key in ['current_user', 'user'] and isinstance(value, User):
                        current_user = value
                    elif key == 'request' and isinstance(value, Request):
                        request = value
                    elif key in ['id', 'resource_id', 'obj_id']:
                        resource_id = str(value)
                
                # Only audit if we have the necessary context
                if db and current_user:
                    audit_service = MadagascarAuditService(db)
                    
                    # Determine resource type and ID
                    if hasattr(result, '__class__'):
                        res_type = resource_type or AuditHelper.get_resource_type(result)
                        if hasattr(result, 'id'):
                            resource_id = str(result.id)
                    else:
                        res_type = resource_type or 'UNKNOWN'
                    
                    # Create user context
                    user_context = create_user_context(
                        current_user, 
                        request or type('MockRequest', (), {'client': type('Client', (), {'host': 'unknown'})(), 'headers': {}})()
                    )
                    
                    # Log the access
                    audit_service.log_view_access(
                        resource_type=res_type,
                        resource_id=resource_id,
                        user_context=user_context,
                        screen_reference=screen_reference,
                        endpoint=request.url.path if request else None,
                        method=request.method if request else 'GET'
                    )
                    
            except Exception as e:
                # Don't let audit failures break the main operation
                print(f"Audit logging failed for READ operation: {e}")
            
            return result
        return wrapper
    return decorator


# Convenience functions for common model operations
def get_application_by_id(db: Session, app_id: str):
    """Helper to get application for audit logging"""
    from app.models.application import Application
    return db.query(Application).filter(Application.id == app_id).first()


def get_person_by_id(db: Session, person_id: str):
    """Helper to get person for audit logging"""
    from app.models.person import Person
    return db.query(Person).filter(Person.id == person_id).first()


def get_transaction_by_id(db: Session, transaction_id: str):
    """Helper to get transaction for audit logging"""
    from app.models.transaction import Transaction
    return db.query(Transaction).filter(Transaction.id == transaction_id).first()


def get_user_by_id(db: Session, user_id: str):
    """Helper to get user for audit logging"""
    from app.models.user import User
    return db.query(User).filter(User.id == user_id).first()
