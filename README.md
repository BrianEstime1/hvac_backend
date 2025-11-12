# HVAC Management System

Production-ready REST API for HVAC business management, currently managing real-world operations.

🔗 **Live API:** https://hvac-management-api.onrender.com



## 🎯 Overview
Built for a real HVAC business to manage customers, scheduling, invoicing, and inventory. Handles daily operations including appointment tracking, parts usage, and automated calculations.

## ✨ Core Features
- **Customer Management** - Complete CRUD with phone validation and formatting
- **Appointment Scheduling** - Status workflow tracking (scheduled → in-progress → completed)
- **Invoice Generation** - Automated tax calculation and status management
- **Inventory System** - Real-time stock tracking with low-stock alerts
- **Usage Tracking** - Audit trail linking parts to specific jobs
- **Business Intelligence** - Total inventory value, technician workload, daily schedules

## 🛠️ Technical Stack
**Backend:** Python 3, Flask REST API, SQLite  
**Architecture:** MVC pattern with separation of concerns  
**Validation:** Custom validation layer with formatted responses  
**Error Handling:** Comprehensive HTTP status codes (400, 404, 409, 500)

## 📊 Database Design
5 normalized tables with referential integrity:
- `customers` - Client information with contact details
- `invoices` - Billing with status workflow and tax calculation
- `appointments` - Job scheduling with technician assignment
- `inventory` - Parts/materials with cost and quantity tracking
- `inventory_usage` - Audit trail with foreign keys to appointments/invoices

## 🔌 API Endpoints (30+)

### Customer Management
- GET /customers - List all customers
- POST /customers - Create customer (validates phone format)
- GET /customers/<id> - Get customer details
- PUT /customers/<id> - Update customer
- DELETE /customers/<id> - Delete (prevented if invoices exist)

### Appointment Scheduling
- GET /appointments - List all appointments
- POST /appointments - Create appointment
- PUT /appointments/<id>/status - Update status workflow
- GET /appointments/date/<date> - Daily schedule
- GET /appointments/technician/<name> - Technician workload

### Inventory Management
- GET /inventory - List all items
- POST /inventory - Create item
- PUT /inventory/<id>/adjust - Adjust quantity
- GET /inventory/low-stock - Alert system
- GET /inventory/search?q=term - Search name/SKU
- POST /inventory/usage - Record parts used

### Invoice Management
- GET /invoices - List all invoices
- POST /invoices - Create invoice
- PUT /invoices/<id> - Update invoice
- PUT /invoices/<id>/status - Update status

## 🎯 Key Technical Implementations

**Atomic Transactions** - Inventory usage records parts used while preventing negative stock in a single transaction.

**SQL JOINs for Performance** - Multi-table queries return enriched data in single requests.

**Calculated Fields** - API computes totals, tax amounts on-the-fly to prevent data inconsistency.

**Status Workflows** - Enforces business logic for invoice/appointment state transitions.

**Audit Trail** - Complete traceability - every part used links to specific job and date.

## 🚀 Local Development
```bash
# Clone and setup
git clone [repository-url]
cd hvac_backend
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server
python app.py
```

## 📈 Business Impact
- Tracks inventory worth in real-time
- Identifies low-stock items for reordering
- Calculates materials cost per job
- Monitors technician workload distribution

## 🔐 Data Integrity
- Foreign key constraints prevent orphaned records
- Unique constraints on SKU and invoice numbers
- Validation prevents negative inventory
- Phone number formatting ensures consistency

