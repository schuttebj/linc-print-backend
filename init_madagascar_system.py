#!/usr/bin/env python3
"""
Madagascar License System Initialization Script
Sets up default roles, permissions, and admin user
"""

import sys
import os
from datetime import datetime, timezone

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, create_tables
from app.core.security import get_password_hash
from app.models.user import User, Role, Permission, UserStatus, MadagascarIDType

def init_database():
    """Initialize database tables"""
    print("Creating database tables...")
    create_tables()
    print("✓ Database tables created")

def create_permissions(db: Session):
    """Create default permissions for Madagascar license system"""
    print("Creating default permissions...")
    
    permissions_data = [
        # User Management Permissions
        ("users.create", "Create Users", "Create new user accounts", "users", "user", "create"),
        ("users.read", "View Users", "View user information", "users", "user", "read"),
        ("users.update", "Update Users", "Update user information", "users", "user", "update"),
        ("users.delete", "Delete Users", "Delete user accounts", "users", "user", "delete"),
        ("users.activate", "Activate Users", "Activate user accounts", "users", "user", "activate"),
        ("users.deactivate", "Deactivate Users", "Deactivate user accounts", "users", "user", "deactivate"),
        ("users.audit", "View User Audit", "View user audit logs", "users", "user", "audit"),
        
        # Role Management Permissions
        ("roles.create", "Create Roles", "Create new roles", "roles", "role", "create"),
        ("roles.read", "View Roles", "View role information", "roles", "role", "read"),
        ("roles.update", "Update Roles", "Update role information", "roles", "role", "update"),
        ("roles.delete", "Delete Roles", "Delete roles", "roles", "role", "delete"),
        ("roles.assign_permissions", "Assign Role Permissions", "Assign permissions to roles", "roles", "role", "assign_permissions"),
        
        # Permission Management
        ("permissions.read", "View Permissions", "View permission information", "permissions", "permission", "read"),
        ("permissions.check_others", "Check Other User Permissions", "Check permissions for other users", "permissions", "permission", "check_others"),
        
        # License Application Permissions
        ("license_applications.create", "Create License Applications", "Create new license applications", "license_applications", "license_application", "create"),
        ("license_applications.read", "View License Applications", "View license applications", "license_applications", "license_application", "read"),
        ("license_applications.update", "Update License Applications", "Update license applications", "license_applications", "license_application", "update"),
        ("license_applications.delete", "Delete License Applications", "Delete license applications", "license_applications", "license_application", "delete"),
        ("license_applications.approve", "Approve License Applications", "Approve license applications", "license_applications", "license_application", "approve"),
        
        # Card Management Permissions
        ("card_management.order", "Order Cards", "Order new license cards", "card_management", "card", "order"),
        ("card_management.issue", "Issue Cards", "Issue completed cards", "card_management", "card", "issue"),
        ("card_management.reorder", "Reorder Cards", "Reorder replacement cards", "card_management", "card", "reorder"),
        ("card_management.approve", "Approve Card Orders", "Approve card printing orders", "card_management", "card", "approve"),
        ("card_management.qa_approve", "QA Approve Cards", "Quality assurance approval of cards", "card_management", "card", "qa_approve"),
        ("card_management.qa_reject", "QA Reject Cards", "Quality assurance rejection of cards", "card_management", "card", "qa_reject"),
        
        # Biometric Data Permissions
        ("biometric_data.capture", "Capture Biometric Data", "Capture biometric information", "biometric_data", "biometric", "capture"),
        ("biometric_data.view", "View Biometric Data", "View biometric information", "biometric_data", "biometric", "view"),
        ("biometric_data.update", "Update Biometric Data", "Update biometric information", "biometric_data", "biometric", "update"),
        
        # Payment Processing Permissions
        ("payment_processing.process", "Process Payments", "Process license payments", "payment_processing", "payment", "process"),
        ("payment_processing.view", "View Payments", "View payment history", "payment_processing", "payment", "view"),
        ("payment_processing.refund", "Process Refunds", "Process payment refunds", "payment_processing", "payment", "refund"),
        
        # Printing Permissions
        ("printing.local_print", "Local Printing", "Print at local location", "printing", "print_job", "local_print"),
        ("printing.cross_location_print", "Cross-Location Printing", "Print at other locations", "printing", "print_job", "cross_location_print"),
        ("printing.manage_queue", "Manage Print Queue", "Manage printing queue", "printing", "print_job", "manage_queue"),
        ("printing.monitor_status", "Monitor Printer Status", "Monitor printer status", "printing", "printer", "monitor_status"),
        
        # Reports Permissions
        ("reports.view_basic", "View Basic Reports", "View basic reports", "reports", "report", "view_basic"),
        ("reports.view_advanced", "View Advanced Reports", "View advanced analytics", "reports", "report", "view_advanced"),
        ("reports.export", "Export Reports", "Export report data", "reports", "report", "export"),
        
        # Location Management Permissions
        ("locations.create", "Create Locations", "Create new locations", "locations", "location", "create"),
        ("locations.read", "View Locations", "View location information", "locations", "location", "read"),
        ("locations.update", "Update Locations", "Update location information", "locations", "location", "update"),
        ("locations.delete", "Delete Locations", "Delete locations", "locations", "location", "delete"),
    ]
    
    created_permissions = {}
    
    for perm_name, display_name, description, category, resource, action in permissions_data:
        # Check if permission already exists
        existing = db.query(Permission).filter(Permission.name == perm_name).first()
        if not existing:
            permission = Permission(
                name=perm_name,
                display_name=display_name,
                description=description,
                category=category,
                resource=resource,
                action=action,
                is_system_permission=True
            )
            db.add(permission)
            db.flush()
            created_permissions[perm_name] = permission
        else:
            created_permissions[perm_name] = existing
    
    db.commit()
    print(f"✓ Created {len(permissions_data)} permissions")
    return created_permissions

def create_roles(db: Session, permissions: dict):
    """Create default roles for Madagascar license system"""
    print("Creating default roles...")
    
    # Define clerk role permissions
    clerk_permissions = [
        "license_applications.create", "license_applications.read", "license_applications.update",
        "card_management.order", "card_management.issue", "card_management.reorder",
        "biometric_data.capture", "biometric_data.view", "biometric_data.update",
        "payment_processing.process", "payment_processing.view",
        "printing.local_print", "printing.monitor_status",
        "reports.view_basic"
    ]
    
    # Define supervisor role permissions (inherits clerk + additional)
    supervisor_permissions = clerk_permissions + [
        "license_applications.approve", "card_management.approve",
        "card_management.qa_approve", "card_management.qa_reject",
        "payment_processing.refund", "reports.view_advanced", "reports.export"
    ]
    
    # Define printer role permissions
    printer_permissions = [
        "printing.local_print", "printing.cross_location_print",
        "printing.manage_queue", "printing.monitor_status"
    ]
    
    roles_data = [
        ("clerk", "Clerk", "License office clerk with full application processing capabilities", clerk_permissions),
        ("supervisor", "Supervisor", "Supervisor with all clerk capabilities plus approvals and reports", supervisor_permissions),
        ("printer", "Printer", "Print-only access for distributed printing", printer_permissions)
    ]
    
    created_roles = {}
    
    for role_name, display_name, description, role_permissions in roles_data:
        # Check if role already exists
        existing = db.query(Role).filter(Role.name == role_name).first()
        if not existing:
            role = Role(
                name=role_name,
                display_name=display_name,
                description=description,
                is_system_role=True,
                level=0
            )
            db.add(role)
            db.flush()
            
            # Assign permissions to role
            role_permission_objects = []
            for perm_name in role_permissions:
                if perm_name in permissions:
                    role_permission_objects.append(permissions[perm_name])
            
            role.permissions = role_permission_objects
            created_roles[role_name] = role
        else:
            created_roles[role_name] = existing
    
    db.commit()
    print(f"✓ Created {len(created_roles)} roles")
    return created_roles

def create_admin_user(db: Session, roles: dict):
    """Create default admin user"""
    print("Creating admin user...")
    
    # Check if admin user already exists
    admin = db.query(User).filter(User.username == "admin").first()
    if admin:
        print("✓ Admin user already exists")
        return admin
    
    # Create admin user
    admin = User(
        username="admin",
        email="admin@madagascar-license.gov.mg",
        password_hash=get_password_hash("MadagascarAdmin2024!"),
        first_name="System",
        last_name="Administrator",
        display_name="System Administrator",
        madagascar_id_number="ADM001",
        id_document_type=MadagascarIDType.CIN,
        phone_number="+261340000000",
        employee_id="ADM001",
        department="IT Administration",
        country_code="MG",
        province="Antananarivo",
        region="Analamanga",
        office_location="Central Office",
        language="en",
        timezone="Indian/Antananarivo",
        currency="MGA",
        status=UserStatus.ACTIVE,
        is_superuser=True,
        is_verified=True
    )
    
    db.add(admin)
    db.flush()
    
    # Assign all roles to admin
    admin.roles = list(roles.values())
    
    db.commit()
    print("✓ Admin user created")
    print(f"   Username: admin")
    print(f"   Password: MadagascarAdmin2024!")
    print(f"   Email: admin@madagascar-license.gov.mg")
    
    return admin

def create_sample_users(db: Session, roles: dict):
    """Create sample users for testing"""
    print("Creating sample users...")
    
    sample_users = [
        {
            "username": "clerk1",
            "email": "clerk1@madagascar-license.gov.mg",
            "password": "Clerk123!",
            "first_name": "Marie",
            "last_name": "Razafy",
            "madagascar_id_number": "CIN123456789",
            "employee_id": "CLK001",
            "department": "License Processing",
            "roles": ["clerk"]
        },
        {
            "username": "supervisor1", 
            "email": "supervisor1@madagascar-license.gov.mg",
            "password": "Supervisor123!",
            "first_name": "Jean",
            "last_name": "Rakoto",
            "madagascar_id_number": "CIN987654321",
            "employee_id": "SUP001",
            "department": "License Processing",
            "roles": ["supervisor"]
        },
        {
            "username": "printer1",
            "email": "printer1@madagascar-license.gov.mg", 
            "password": "Printer123!",
            "first_name": "Paul",
            "last_name": "Andry",
            "madagascar_id_number": "CIN456789123",
            "employee_id": "PRT001",
            "department": "Card Production",
            "roles": ["printer"]
        }
    ]
    
    created_count = 0
    for user_data in sample_users:
        # Check if user already exists
        existing = db.query(User).filter(User.username == user_data["username"]).first()
        if not existing:
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                password_hash=get_password_hash(user_data["password"]),
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                madagascar_id_number=user_data["madagascar_id_number"],
                id_document_type=MadagascarIDType.CIN,
                employee_id=user_data["employee_id"],
                department=user_data["department"],
                country_code="MG",
                province="Antananarivo",
                region="Analamanga",
                language="en",
                timezone="Indian/Antananarivo",
                currency="MGA",
                status=UserStatus.ACTIVE,
                is_verified=True
            )
            
            # Assign roles
            user_roles = [roles[role_name] for role_name in user_data["roles"] if role_name in roles]
            user.roles = user_roles
            
            db.add(user)
            created_count += 1
    
    db.commit()
    print(f"✓ Created {created_count} sample users")
    
    if created_count > 0:
        print("Sample user credentials:")
        for user_data in sample_users:
            print(f"   {user_data['username']} / {user_data['password']}")

def main():
    """Main initialization function"""
    print("🇲🇬 Initializing Madagascar Driver's License System")
    print("=" * 50)
    
    try:
        # Initialize database
        init_database()
        
        # Create database session
        db = SessionLocal()
        
        try:
            # Create permissions
            permissions = create_permissions(db)
            
            # Create roles
            roles = create_roles(db, permissions)
            
            # Create admin user
            admin = create_admin_user(db, roles)
            
            # Create sample users
            create_sample_users(db, roles)
            
            print("\n" + "=" * 50)
            print("✅ Madagascar License System initialized successfully!")
            print("\nNext steps:")
            print("1. Update your .env file with the database URL")
            print("2. Start the application: python -m uvicorn app.main:app --reload")
            print("3. Access the API docs at: http://localhost:8000/docs")
            print("4. Login with admin credentials to create more users")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"\n❌ Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 