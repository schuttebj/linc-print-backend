# Madagascar Driver's License System - Backend

A comprehensive backend API for managing driver's licenses in Madagascar, built with FastAPI and PostgreSQL.

## 🇲🇬 System Overview

This system provides secure, role-based management of driver's license applications, user management, and distributed printing capabilities specifically designed for Madagascar's licensing requirements.

### Key Features

- **Madagascar-Specific ID Support**: CIN/CNI ID number validation
- **Role-Based Access Control**: Clerk, Supervisor, and Printer roles
- **Distributed Printing**: Cross-location printing with shipment management  
- **ISO Compliance**: Ready for ISO 7810 (national IDs) and ISO 18013 (licenses)
- **Comprehensive Audit Trail**: Full audit logging for compliance
- **Multi-Currency Support**: Madagascar Ariary (MGA) with localization

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- pip or poetry

### Installation

1. **Clone and setup**:
   ```bash
   cd "LINC Print Backend"
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp env.example .env
   # Edit .env with your database credentials
   ```

3. **Initialize the system**:
   ```bash
   python init_madagascar_system.py
   ```

4. **Start the server**:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

5. **Access the API**:
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## 🔐 Default Credentials

After initialization, use these credentials:

| Username | Password | Role | Description |
|----------|----------|------|-------------|
| admin | MadagascarAdmin2024! | All roles | System administrator |
| clerk1 | Clerk123! | Clerk | License processing clerk |
| supervisor1 | Supervisor123! | Supervisor | Processing supervisor |
| printer1 | Printer123! | Printer | Print-only access |

## 📊 Database Configuration

### Production Database (Render.com)

```env
DATABASE_URL="postgresql://linc_print_user:RpXGDpwfEt69Er7vwctZs20VNpxYj5Eb@dpg-d1ckfd8dl3ps73fovhsg-a.oregon-postgres.render.com/linc_print"
```

### Connection Details

- **Hostname**: dpg-d1ckfd8dl3ps73fovhsg-a.oregon-postgres.render.com
- **Port**: 5432
- **Database**: linc_print
- **Username**: linc_print_user
- **Password**: RpXGDpwfEt69Er7vwctZs20VNpxYj5Eb

## 🔑 API Endpoints

### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/logout` - User logout  
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/change-password` - Change password
- `GET /api/v1/auth/me` - Current user info

### User Management
- `GET /api/v1/users/` - List users (paginated, searchable)
- `POST /api/v1/users/` - Create user
- `GET /api/v1/users/{id}` - Get user details
- `PUT /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Soft delete user

### Role Management
- `GET /api/v1/roles/` - List roles
- `POST /api/v1/roles/` - Create role
- `GET /api/v1/roles/{id}` - Get role details
- `PUT /api/v1/roles/{id}` - Update role

### Permission Management
- `GET /api/v1/permissions/` - List permissions
- `GET /api/v1/permissions/by-category` - Grouped by category
- `GET /api/v1/permissions/check/{permission}` - Check permission

## 👥 User Roles & Permissions

### Clerk Role
- Full application processing capabilities
- License application: create, read, update
- Card management: order, issue, reorder
- Biometric data: capture, view, update
- Payment processing
- Local printing access
- Basic reports

### Supervisor Role
- All clerk capabilities plus:
- License application approval
- Card order approval
- QA approval/rejection
- Payment refunds
- Advanced reports and analytics
- Data export capabilities

### Printer Role
- Print-only access for distributed printing:
- Local and cross-location printing
- Print queue management
- Printer status monitoring

## 🚀 Deployment

### Render.com Deployment

1. **Backend**: Deploy to Render.com with PostgreSQL database
2. **Environment**: Configure production environment variables
3. **Initialization**: Run init script to setup default data
4. **Monitoring**: Use Render's built-in monitoring

## 📝 API Documentation

- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **OpenAPI Schema**: http://localhost:8000/openapi.json
- **ReDoc**: http://localhost:8000/redoc

---

**Next Steps**: 
1. Deploy frontend (React/TypeScript)
2. Implement remaining modules (Persons, Applications, etc.)
3. Add ISO 18013 compliance features
4. Configure distributed printing workflow 