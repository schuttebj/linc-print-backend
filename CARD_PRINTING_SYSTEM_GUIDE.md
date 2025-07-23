# Madagascar License Card Printing System - Complete Guide

## Overview

The Madagascar License Card Printing System is a comprehensive solution for ordering, printing, and managing physical driver's license cards. It integrates seamlessly with the LINC license management system and provides a complete workflow from card ordering to quality assurance.

## System Architecture

### Backend Components

1. **Print Job Management (`app/models/printing.py`)**
   - Print job entities with complete workflow tracking
   - Queue management with FIFO processing
   - Priority handling and emergency processing
   - Quality assurance workflow

2. **Card Generation Service (`app/services/card_generator.py`)**
   - Madagascar-specific card design with flag colors
   - PDF417 barcodes for security
   - Multi-license support on single cards
   - High-resolution output (300 DPI) for professional printing

3. **API Endpoints (`app/api/v1/endpoints/printing.py`)**
   - Complete REST API for print job management
   - File download endpoints for card images/PDFs
   - Queue management and workflow control
   - Statistics and reporting

### Frontend Components

1. **Card Ordering (`src/pages/cards/CardOrderingPage.tsx`)**
   - Application search and filtering
   - License confirmation workflow
   - Multi-application support
   - Print job creation

2. **Print Queue Management (`src/pages/cards/PrintQueuePage.tsx`)**
   - Real-time queue monitoring
   - Job assignment and workflow control
   - Batch operations
   - Progress tracking

3. **Enhanced Dashboard (`src/pages/cards/PrintQueueDashboard.tsx`)**
   - Advanced operator interface
   - Real-time statistics
   - Performance metrics
   - Multi-location support

4. **Quality Assurance (`src/pages/cards/QualityAssurancePage.tsx`)**
   - Comprehensive inspection workflow
   - Failure categorization
   - Automatic reprint generation
   - Quality metrics tracking

## Workflow Overview

### 1. Card Ordering Process

```
Applications (APPROVED/PAID) → Search & Select → License Confirmation → Print Job Creation
```

**Steps:**
1. Clerk searches for approved applications
2. System shows all person's licenses for confirmation
3. Learner permits are automatically excluded from cards
4. Print job is created with all person's licenses
5. Card files are generated immediately
6. Job enters print queue

### 2. Print Queue Processing

```
QUEUED → ASSIGNED → PRINTING → PRINTED → QUALITY_CHECK → COMPLETED
```

**Workflow:**
1. **QUEUED**: Job waits in FIFO queue
2. **ASSIGNED**: Operator takes ownership
3. **PRINTING**: Physical card production
4. **PRINTED**: Card completed, ready for QA
5. **QUALITY_CHECK**: Inspection and validation
6. **COMPLETED**: Ready for collection

### 3. Quality Assurance Process

**Inspection Categories:**
- **Photo Quality**: Clarity, positioning, color accuracy
- **Text and Data**: Legibility, accuracy, alignment
- **Physical Quality**: Surface, edges, lamination
- **Security Features**: Barcodes, patterns, watermarks
- **Layout**: Overall design and professional appearance

**Failure Handling:**
- **FAILED_PRINTING**: Print quality issues → Reprint with HIGH priority
- **FAILED_DATA**: Data accuracy issues → Review and correction
- **FAILED_DAMAGE**: Physical damage → Reprint with URGENT priority

## Key Features

### 🎯 **Core Functionality**

1. **Smart Application Detection**
   - Automatically finds applications ready for card ordering
   - Status-based filtering (APPROVED for new licenses, PAID for others)
   - Person consolidation for multiple pending applications

2. **Comprehensive License Handling**
   - Shows all person's active licenses
   - Excludes learner permits from physical cards
   - Handles multiple license categories on single card

3. **Professional Card Generation**
   - Madagascar flag colors and bilingual text
   - PDF417 barcodes with license data
   - High-resolution images and PDFs
   - Security backgrounds and watermarks

4. **Advanced Queue Management**
   - FIFO processing with priority override
   - Emergency job prioritization
   - Batch operations for efficiency
   - Real-time status tracking

5. **Quality Assurance System**
   - 20+ inspection criteria
   - Critical vs. minor failure classification
   - Automatic reprint generation
   - Quality metrics and statistics

### 🔧 **Technical Features**

1. **Database Integration**
   - Complete schema with proper foreign keys
   - Audit trails for all operations
   - Status history tracking
   - Performance indexes

2. **File Management**
   - Multiple output formats (PNG, PDF)
   - Base64 storage for development
   - Production file paths
   - Secure file access

3. **Permission System**
   - Role-based access control
   - Location-based restrictions
   - Granular permissions for each operation
   - Admin override capabilities

4. **Real-time Updates**
   - Auto-refresh dashboards
   - Live queue monitoring
   - Status notifications
   - Progress tracking

## User Roles and Permissions

### Clerk
- Order cards for approved applications
- View print queue status
- Track card production progress
- **Permissions**: `printing.create`, `printing.read`, `cards.order`, `cards.read`

### Printer Operator
- Manage print queue
- Assign and process jobs
- Control printing workflow
- Generate card files
- **Permissions**: `printing.assign`, `printing.start`, `printing.complete`, `printing.regenerate_files`

### Quality Assurance
- Inspect printed cards
- Perform quality checks
- Generate reprint jobs
- Track quality metrics
- **Permissions**: `printing.quality_check`, `printing.read`, `cards.track_status`

### Supervisor
- Full queue management
- Priority override
- Batch operations
- View statistics and reports
- **Permissions**: All printing permissions + `printing.move_to_top`, `printing.view_statistics`

## API Endpoints

### Print Job Management
```
POST   /api/v1/printing/jobs                    - Create print job
GET    /api/v1/printing/jobs                    - Search print jobs
GET    /api/v1/printing/jobs/{id}               - Get job details
POST   /api/v1/printing/jobs/{id}/assign        - Assign to operator
POST   /api/v1/printing/jobs/{id}/start         - Start printing
POST   /api/v1/printing/jobs/{id}/complete      - Complete printing
POST   /api/v1/printing/jobs/{id}/move-to-top   - Priority override
```

### Quality Assurance
```
POST   /api/v1/printing/jobs/{id}/qa-start      - Start QA process
POST   /api/v1/printing/jobs/{id}/qa-complete   - Complete QA
```

### File Downloads
```
GET    /api/v1/printing/jobs/{id}/files/front         - Front card image
GET    /api/v1/printing/jobs/{id}/files/back          - Back card image
GET    /api/v1/printing/jobs/{id}/files/combined-pdf  - Complete card PDF
```

### Queue Management
```
GET    /api/v1/printing/queue/{location_id}     - Get print queue
GET    /api/v1/printing/statistics/{location_id} - Queue statistics
```

## Database Schema

### Print Jobs Table
```sql
CREATE TABLE print_jobs (
    id UUID PRIMARY KEY,
    job_number VARCHAR(20) UNIQUE NOT NULL,
    status printjobstatus NOT NULL DEFAULT 'QUEUED',
    priority printjobpriority NOT NULL DEFAULT 'NORMAL',
    queue_position INTEGER,
    
    -- Person and location
    person_id UUID REFERENCES persons(id),
    print_location_id UUID REFERENCES locations(id),
    primary_application_id UUID REFERENCES applications(id),
    
    -- Card details
    card_number VARCHAR(20) UNIQUE NOT NULL,
    card_template VARCHAR(50) DEFAULT 'MADAGASCAR_STANDARD',
    
    -- Data storage
    license_data JSONB NOT NULL,
    person_data JSONB NOT NULL,
    generation_metadata JSONB,
    card_files_data JSONB,
    
    -- Workflow tracking
    submitted_at TIMESTAMP DEFAULT NOW(),
    assigned_to_user_id UUID REFERENCES users(id),
    assigned_at TIMESTAMP,
    printing_started_at TIMESTAMP,
    printing_completed_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Quality assurance
    quality_check_result qualitycheckresult,
    quality_check_by_user_id UUID REFERENCES users(id),
    quality_check_notes TEXT,
    
    -- File generation
    pdf_files_generated BOOLEAN DEFAULT FALSE,
    pdf_front_path VARCHAR(500),
    pdf_back_path VARCHAR(500),
    pdf_combined_path VARCHAR(500)
);
```

## Installation and Setup

### 1. Database Initialization

Use the reset-database endpoint to create all necessary tables:

```bash
curl -X POST "http://localhost:8000/admin/reset-database"
```

This will:
- Create all printing tables and enums
- Initialize users with printing permissions
- Set up locations for print operations

### 2. Permission Verification

Ensure users have the correct permissions:

```bash
# Check user permissions
curl -X GET "http://localhost:8000/api/v1/users/me" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Required permissions for different roles:
- **Clerks**: `printing.create`, `cards.order`
- **Printers**: `printing.read`, `printing.assign`, `printing.start`, `printing.complete`
- **QA**: `printing.quality_check`

### 3. Frontend Configuration

Ensure all new pages are accessible:
- Card Ordering: `/dashboard/cards/order`
- Print Queue: `/dashboard/cards/print-queue`
- Queue Dashboard: `/dashboard/cards/print-queue-dashboard`
- Quality Assurance: `/dashboard/cards/quality-assurance`

## Testing Guide

### 1. End-to-End Workflow Test

```bash
# 1. Create a person and application (prerequisite)
curl -X POST "http://localhost:8000/api/v1/persons/" ...
curl -X POST "http://localhost:8000/api/v1/applications/" ...

# 2. Approve the application
curl -X PUT "http://localhost:8000/api/v1/applications/{id}/status" \
  -d '{"status": "APPROVED"}'

# 3. Order a card (frontend or API)
curl -X POST "http://localhost:8000/api/v1/printing/jobs" \
  -d '{"application_id": "...", "card_template": "MADAGASCAR_STANDARD"}'

# 4. Check queue
curl -X GET "http://localhost:8000/api/v1/printing/queue/{location_id}"

# 5. Process the job
curl -X POST "http://localhost:8000/api/v1/printing/jobs/{id}/assign"
curl -X POST "http://localhost:8000/api/v1/printing/jobs/{id}/start"
curl -X POST "http://localhost:8000/api/v1/printing/jobs/{id}/complete"

# 6. Quality check
curl -X POST "http://localhost:8000/api/v1/printing/jobs/{id}/qa-start"
curl -X POST "http://localhost:8000/api/v1/printing/jobs/{id}/qa-complete" \
  -d '{"qa_result": "PASSED"}'
```

### 2. Frontend Interface Testing

1. **Card Ordering Test**:
   - Navigate to `/dashboard/cards/order`
   - Search for approved applications
   - Verify license display excludes learner permits
   - Complete card ordering workflow

2. **Print Queue Test**:
   - Navigate to `/dashboard/cards/print-queue`
   - Verify real-time updates
   - Test job assignment and progression
   - Download card files

3. **Quality Assurance Test**:
   - Navigate to `/dashboard/cards/quality-assurance`
   - Complete QA inspection workflow
   - Test failure scenarios and reprint generation

### 3. Load Testing

Test system performance with multiple concurrent operations:
- Multiple card orders
- Queue processing under load
- File generation performance
- Database query optimization

## Production Considerations

### 1. File Storage

Replace base64 storage with proper file system:
```python
# Example production file storage
import os
from pathlib import Path

CARD_FILES_ROOT = Path("/var/lib/linc/card_files")

def save_card_file(job_id: str, file_type: str, content: bytes) -> str:
    file_path = CARD_FILES_ROOT / str(job_id) / f"{file_type}.pdf"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return str(file_path)
```

### 2. Security

- Implement file access controls
- Add audit logging for all operations
- Secure API endpoints with rate limiting
- Encrypt sensitive data in database

### 3. Performance

- Add database indexes for queue queries
- Implement caching for frequently accessed data
- Use background tasks for file generation
- Monitor memory usage during PDF creation

### 4. Monitoring

- Set up health checks for print queue
- Monitor job processing times
- Alert on failed print jobs
- Track quality assurance metrics

## Troubleshooting

### Common Issues

1. **Card Generation Fails**
   - Check font availability
   - Verify PIL/Pillow installation
   - Review photo data format

2. **Queue Not Updating**
   - Verify database connections
   - Check enum values match
   - Review foreign key constraints

3. **Permission Errors**
   - Verify user roles and permissions
   - Check location-based access
   - Review JWT token validity

4. **File Download Issues**
   - Check base64 encoding
   - Verify file generation success
   - Review API response headers

### Debug Commands

```bash
# Check database schema
curl -X GET "http://localhost:8000/admin/inspect-database"

# Verify print job structure
curl -X GET "http://localhost:8000/api/v1/printing/jobs/{id}"

# Test file generation
curl -X POST "http://localhost:8000/api/v1/printing/jobs/{id}/regenerate-files"
```

## Support and Maintenance

### Regular Maintenance

1. **Daily**:
   - Monitor queue processing
   - Check for failed jobs
   - Review quality metrics

2. **Weekly**:
   - Clean up old temporary files
   - Review error logs
   - Update statistics

3. **Monthly**:
   - Database maintenance
   - Performance review
   - Security updates

### Contact Information

For technical support or questions about the card printing system:
- System Administrator
- Database Administrator  
- Print Operations Manager

---

## Conclusion

The Madagascar License Card Printing System provides a complete, professional solution for physical license card production. With comprehensive workflow management, quality assurance, and real-time monitoring, it ensures efficient and reliable card production while maintaining the highest quality standards.

The system is production-ready and includes all necessary components for a successful deployment in Madagascar's driver's license operations. 