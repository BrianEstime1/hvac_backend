import sqlite3
from datetime import datetime

DATABASE = 'hvac.db'

def get_db_connection():
    """Helper function to connect to database"""
    conn = sqlite3.connect(DATABASE, timeout=20.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent access
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=20000')
    return conn

def init_database():
    """Initialize the database with required tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create customers table 
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )  
    ''')

    # Create invoices table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT NOT NULL UNIQUE,
            customer_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            scheduled_time TEXT,
            technician TEXT,
            work_performed TEXT,
            description TEXT,
            recommendations TEXT,
            labor_cost REAL DEFAULT 0,
            materials_cost REAL DEFAULT 0,
            tax_rate REAL DEFAULT 0.08,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')
    
    # Create appointments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            technician TEXT,
            service_type TEXT NOT NULL,
            notes TEXT,
            status TEXT DEFAULT 'scheduled',
            invoice_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        )
    ''')
    
    # Create inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            sku TEXT UNIQUE,
            quantity INTEGER DEFAULT 0,
            unit TEXT NOT NULL,
            cost_per_unit REAL DEFAULT 0,
            low_stock_threshold INTEGER DEFAULT 5,
            supplier TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create inventory_usage table (track parts used on jobs)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL,
            appointment_id INTEGER,
            invoice_id INTEGER,
            quantity_used INTEGER NOT NULL,
            date_used TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (inventory_id) REFERENCES inventory(id),
            FOREIGN KEY (appointment_id) REFERENCES appointments(id),
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Database initialized")


# [Rest of the file remains exactly the same - keeping all functions as is]
# ==================== CUSTOMER FUNCTIONS ====================

def add_customer(name, phone, address):
    """Add a new customer to the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO customers (name, phone, address)
        VALUES (?, ?, ?)
    ''', (name, phone, address))
    conn.commit()
    customer_id = cursor.lastrowid
    conn.close()
    return customer_id


def get_all_customers():
    """Retrieve all customers from the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM customers ORDER BY created_at DESC')
    customers = cursor.fetchall()
    conn.close()
    return customers


def get_customer_by_id(customer_id):
    """Retrieve a single customer by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
    customer = cursor.fetchone()
    conn.close()
    return customer


def update_customer(customer_id, name, phone, address):
    """Update customer details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE customers
        SET name = ?, phone = ?, address = ?
        WHERE id = ?
    ''', (name, phone, address, customer_id))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0


def delete_customer(customer_id):
    """Delete a customer from the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0


def check_customer_has_invoices(customer_id):
    """Check if customer has any invoices"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM invoices WHERE customer_id = ?', (customer_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def search_customers(search_term):
    """Search for customers by name"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM customers 
        WHERE name LIKE ?
        ORDER BY name
    ''', (f'%{search_term}%',))
    customers = cursor.fetchall()
    conn.close()
    return customers


def count_customers():
    """Count total number of customers"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM customers')
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ==================== INVOICE FUNCTIONS ====================

def create_invoice(customer_id, invoice_number, date, technician, work_performed, 
                   labor_cost, scheduled_time="", description="", recommendations=""):
    """Create a new invoice"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    materials_cost = 0
    tax_rate = 0.08
    
    cursor.execute('''
        INSERT INTO invoices (
            invoice_number, customer_id, date, scheduled_time, 
            technician, work_performed, description, recommendations,
            labor_cost, materials_cost, tax_rate
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (invoice_number, customer_id, date, scheduled_time, technician, 
          work_performed, description, recommendations, labor_cost, materials_cost, tax_rate))
    
    conn.commit()
    invoice_id = cursor.lastrowid
    conn.close()
    return invoice_id


def get_all_invoices():
    """Get all invoices with customer names"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT invoices.*, customers.name as customer_name, customers.phone
        FROM invoices
        JOIN customers ON invoices.customer_id = customers.id
        ORDER BY invoices.created_at DESC
    ''')
    invoices = cursor.fetchall()
    conn.close()
    return invoices


def get_invoice_by_id(invoice_id):
    """Get a single invoice with customer details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT invoices.*, customers.name as customer_name, 
               customers.phone, customers.address as customer_address
        FROM invoices
        JOIN customers ON invoices.customer_id = customers.id
        WHERE invoices.id = ?
    ''', (invoice_id,))
    invoice = cursor.fetchone()
    conn.close()
    return invoice


def update_invoice(invoice_id, invoice_number, date, technician, work_performed,
                   labor_cost, materials_cost, scheduled_time="", description="", 
                   recommendations="", tax_rate=0.08):
    """Update an existing invoice"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE invoices
        SET invoice_number = ?, date = ?, scheduled_time = ?,
            technician = ?, work_performed = ?, description = ?,
            recommendations = ?, labor_cost = ?, materials_cost = ?, tax_rate = ?
        WHERE id = ?
    ''', (invoice_number, date, scheduled_time, technician, work_performed,
          description, recommendations, labor_cost, materials_cost, tax_rate, invoice_id))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0


def update_invoice_status(invoice_id, status):
    """Update invoice status (draft, sent, paid, cancelled)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE invoices
        SET status = ?
        WHERE id = ?
    ''', (status, invoice_id))
    conn.commit()
    conn.close()


def delete_invoice(invoice_id):
    """Delete an invoice"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM invoices WHERE id = ?', (invoice_id,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0


def get_customer_invoices(customer_id):
    """Get all invoices for a specific customer"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM invoices
        WHERE customer_id = ?
        ORDER BY created_at DESC
    ''', (customer_id,))
    invoices = cursor.fetchall()
    conn.close()
    return invoices


# ==================== APPOINTMENT FUNCTIONS ====================

def create_appointment(customer_id, appointment_date, appointment_time, 
                       service_type, technician="", notes=""):
    """Create a new appointment"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO appointments (
            customer_id, appointment_date, appointment_time,
            technician, service_type, notes, status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'scheduled')
    ''', (customer_id, appointment_date, appointment_time, 
          technician, service_type, notes))
    
    conn.commit()
    appointment_id = cursor.lastrowid
    conn.close()
    return appointment_id


def get_all_appointments():
    """Get all appointments with customer details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            appointments.*,
            customers.name as customer_name,
            customers.phone as customer_phone,
            customers.address as customer_address
        FROM appointments
        JOIN customers ON appointments.customer_id = customers.id
        ORDER BY appointments.appointment_date DESC, appointments.appointment_time DESC
    ''')
    
    appointments = cursor.fetchall()
    conn.close()
    return appointments


def get_appointment_by_id(appointment_id):
    """Get single appointment with customer details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            appointments.*,
            customers.name as customer_name,
            customers.phone as customer_phone,
            customers.address as customer_address
        FROM appointments
        JOIN customers ON appointments.customer_id = customers.id
        WHERE appointments.id = ?
    ''', (appointment_id,))
    
    appointment = cursor.fetchone()
    conn.close()
    return appointment


def update_appointment(appointment_id, appointment_date, appointment_time,
                       technician, service_type, notes):
    """Update appointment details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE appointments
        SET appointment_date = ?, appointment_time = ?,
            technician = ?, service_type = ?, notes = ?
        WHERE id = ?
    ''', (appointment_date, appointment_time, technician, 
          service_type, notes, appointment_id))
    
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0


def update_appointment_status(appointment_id, status):
    """Update appointment status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE appointments
        SET status = ?
        WHERE id = ?
    ''', (status, appointment_id))
    
    conn.commit()
    conn.close()


def link_appointment_to_invoice(appointment_id, invoice_id):
    """Link completed appointment to an invoice"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE appointments
        SET invoice_id = ?, status = 'completed'
        WHERE id = ?
    ''', (invoice_id, appointment_id))
    
    conn.commit()
    conn.close()


def delete_appointment(appointment_id):
    """Delete an appointment"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM appointments WHERE id = ?', (appointment_id,))
    
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0


def get_customer_appointments(customer_id):
    """Get all appointments for a customer"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM appointments
        WHERE customer_id = ?
        ORDER BY appointment_date DESC, appointment_time DESC
    ''', (customer_id,))
    
    appointments = cursor.fetchall()
    conn.close()
    return appointments


def get_appointments_by_date(date):
    """Get all appointments for a specific date"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            appointments.*,
            customers.name as customer_name,
            customers.phone as customer_phone
        FROM appointments
        JOIN customers ON appointments.customer_id = customers.id
        WHERE appointments.appointment_date = ?
        ORDER BY appointments.appointment_time
    ''', (date,))
    
    appointments = cursor.fetchall()
    conn.close()
    return appointments


def get_appointments_by_technician(technician):
    """Get all appointments for a specific technician"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            appointments.*,
            customers.name as customer_name,
            customers.phone as customer_phone
        FROM appointments
        JOIN customers ON appointments.customer_id = customers.id
        WHERE appointments.technician = ?
        ORDER BY appointments.appointment_date DESC, appointments.appointment_time DESC
    ''', (technician,))
    
    appointments = cursor.fetchall()
    conn.close()
    return appointments


# ==================== INVENTORY FUNCTIONS ====================

def create_inventory_item(name, category, unit, sku="", quantity=0, cost_per_unit=0, 
                          low_stock_threshold=5, supplier="", notes=""):
    """Create a new inventory item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO inventory (
            name, category, sku, quantity, unit, cost_per_unit,
            low_stock_threshold, supplier, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, category, sku, quantity, unit, cost_per_unit,
          low_stock_threshold, supplier, notes))
    
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return item_id


def get_all_inventory():
    """Get all inventory items"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM inventory
        ORDER BY name
    ''')
    
    items = cursor.fetchall()
    conn.close()
    return items


def get_inventory_by_id(item_id):
    """Get single inventory item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM inventory WHERE id = ?', (item_id,))
    item = cursor.fetchone()
    conn.close()
    return item


def update_inventory_item(item_id, name, category, unit, sku="", quantity=0,
                          cost_per_unit=0, low_stock_threshold=5, supplier="", notes=""):
    """Update inventory item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE inventory
        SET name = ?, category = ?, sku = ?, quantity = ?, unit = ?,
            cost_per_unit = ?, low_stock_threshold = ?, supplier = ?, notes = ?
        WHERE id = ?
    ''', (name, category, sku, quantity, unit, cost_per_unit,
          low_stock_threshold, supplier, notes, item_id))
    
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0


def adjust_inventory_quantity(item_id, quantity_change):
    """Adjust inventory quantity (positive to add, negative to subtract)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current quantity
    cursor.execute('SELECT quantity FROM inventory WHERE id = ?', (item_id,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return False
    
    new_quantity = result['quantity'] + quantity_change
    
    # Don't allow negative inventory
    if new_quantity < 0:
        conn.close()
        return False
    
    cursor.execute('''
        UPDATE inventory
        SET quantity = ?
        WHERE id = ?
    ''', (new_quantity, item_id))
    
    conn.commit()
    conn.close()
    return True


def delete_inventory_item(item_id):
    """Delete inventory item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM inventory WHERE id = ?', (item_id,))
    
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0


def get_low_stock_items():
    """Get items below low stock threshold"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM inventory
        WHERE quantity <= low_stock_threshold
        ORDER BY quantity ASC
    ''')
    
    items = cursor.fetchall()
    conn.close()
    return items


def get_inventory_by_category(category):
    """Get all items in a category"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM inventory
        WHERE category = ?
        ORDER BY name
    ''', (category,))
    
    items = cursor.fetchall()
    conn.close()
    return items


def search_inventory(search_term):
    """Search inventory by name or SKU"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM inventory
        WHERE name LIKE ? OR sku LIKE ?
        ORDER BY name
    ''', (f'%{search_term}%', f'%{search_term}%'))
    
    items = cursor.fetchall()
    conn.close()
    return items


def calculate_total_inventory_value():
    """Calculate total value of all inventory"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT SUM(quantity * cost_per_unit) as total_value
        FROM inventory
    ''')
    
    result = cursor.fetchone()
    conn.close()
    return result['total_value'] if result['total_value'] else 0


# ==================== INVENTORY USAGE FUNCTIONS ====================

def record_inventory_usage(inventory_id, quantity_used, date_used, 
                           appointment_id=None, invoice_id=None, notes=""):
    """Record parts used on a job"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First, reduce inventory quantity
    cursor.execute('SELECT quantity FROM inventory WHERE id = ?', (inventory_id,))
    result = cursor.fetchone()
    
    if not result or result['quantity'] < quantity_used:
        conn.close()
        return None  # Not enough inventory
    
    new_quantity = result['quantity'] - quantity_used
    cursor.execute('UPDATE inventory SET quantity = ? WHERE id = ?', 
                   (new_quantity, inventory_id))
    
    # Record the usage
    cursor.execute('''
        INSERT INTO inventory_usage (
            inventory_id, appointment_id, invoice_id, 
            quantity_used, date_used, notes
        )
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (inventory_id, appointment_id, invoice_id, 
          quantity_used, date_used, notes))
    
    conn.commit()
    usage_id = cursor.lastrowid
    conn.close()
    return usage_id


def get_usage_by_appointment(appointment_id):
    """Get all parts used for an appointment"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            inventory_usage.*,
            inventory.name as item_name,
            inventory.sku,
            inventory.cost_per_unit,
            inventory.unit
        FROM inventory_usage
        JOIN inventory ON inventory_usage.inventory_id = inventory.id
        WHERE inventory_usage.appointment_id = ?
        ORDER BY inventory_usage.created_at
    ''', (appointment_id,))
    
    usage = cursor.fetchall()
    conn.close()
    return usage


def get_usage_by_invoice(invoice_id):
    """Get all parts used for an invoice"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            inventory_usage.*,
            inventory.name as item_name,
            inventory.sku,
            inventory.cost_per_unit,
            inventory.unit
        FROM inventory_usage
        JOIN inventory ON inventory_usage.inventory_id = inventory.id
        WHERE inventory_usage.invoice_id = ?
        ORDER BY inventory_usage.created_at
    ''', (invoice_id,))
    
    usage = cursor.fetchall()
    conn.close()
    return usage


def get_item_usage_history(inventory_id):
    """Get usage history for a specific inventory item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM inventory_usage
        WHERE inventory_id = ?
        ORDER BY date_used DESC
    ''', (inventory_id,))
    
    usage = cursor.fetchall()
    conn.close()
    return usage
