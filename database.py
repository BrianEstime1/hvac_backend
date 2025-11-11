import sqlite3
from datetime import datetime

DATABASE = 'hvac.db'

def get_db_connection():
    """Helper function to connect to database"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # this lets us access columns by name
    return conn

def init_database():
    """Initialize the database with required tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
        #create customer table 
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS customers (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               name TEXT NOT NULL,
               phone TEXT NOT NULL,
               address TEXT,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
             )  
       ''' )

    #create invoices table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT NOT NULL,
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

    #commit changes and close connection
    conn.commit()
    conn.close()
    print("Database initialized")

def add_customer(name, phone, address):
    """Add a new customer to the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO customers (name, phone, address)
        VALUES (?, ?, ?)
    ''', (name, phone, address))
    conn.commit()
    customer_id = cursor.lastrowid # get the id before closing the connection
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

def update_customer(customer_id, name, phone, address, none):
    """Update customer details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE customers
        SET name = ?, phone = ?, address = ?
        WHERE id = ?
    ''', (name, phone, address, customer_id))

    conn.commit()
    conn.close()
    print(f"Customer {customer_id} updated.")

def delete_customer(customer_id):
    """Delete a customer from the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
    
    conn.commit()
    conn.close()
    print(f"Customer {customer_id} deleted.")

def search_customers(search_term):
    """Search for customers by name"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # LIKE allows partial matches (e.g., "john" finds "John Doe")
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
    count = cursor.fetchone()[0] # fetchone returns a tuple, [0] gets the count value
    
    conn.close()
    return count

# ==================== INVOICE FUNCTIONS ====================

def create_invoice(customer_id, invoice_number, date, technician, work_performed, 
                   labor_cost, scheduled_time="", description="", recommendations=""):
    """Create a new invoice"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate totals
    materials_cost = 0  # We'll add materials later
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
    
    # JOIN to get customer name
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
    conn.close()


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

if __name__ == "__main__":
    # Initialize database
    init_database()
    
    print("\n=== TESTING CUSTOMERS ===")
    # Create customers
    customer1 = add_customer("John Doe", "(555) 123-4567", "123 Main St")
    customer2 = add_customer("Jane Smith", "(555) 987-6543", "456 Oak Ave")
    print(f"Created customers: {customer1}, {customer2}")
    
    print("\n=== TESTING INVOICES ===")
    # Create invoices
    invoice1 = create_invoice(
        customer_id=customer1,
        invoice_number="INV-2025-001",
        date="2025-11-02",
        technician="Mike Johnson",
        work_performed="AC Repair - Compressor replacement",
        labor_cost=150.00,
        scheduled_time="10:00 AM",
        description="Replaced faulty compressor unit",
        recommendations="Schedule annual maintenance in 6 months"
    )
    print(f"✅ Created invoice: INV-2025-001 (ID: {invoice1})")
    
    invoice2 = create_invoice(
        customer_id=customer1,
        invoice_number="INV-2025-002",
        date="2025-11-02",
        technician="Sarah Lee",
        work_performed="Filter Replacement",
        labor_cost=75.00,
        scheduled_time="2:00 PM"
    )
    print(f"✅ Created invoice: INV-2025-002 (ID: {invoice2})")
    
    # Get all invoices
    print("\n--- All Invoices (with JOIN) ---")
    invoices = get_all_invoices()
    for inv in invoices:
        subtotal = inv['labor_cost'] + inv['materials_cost']
        tax = subtotal * inv['tax_rate']
        grand_total = subtotal + tax
        print(f"📄 {inv['invoice_number']}: {inv['customer_name']} - ${grand_total:.2f} [{inv['status']}]")
        print(f"   Tech: {inv['technician']}, Work: {inv['work_performed']}")
    
    # Get customer's invoices
    print(f"\n--- Invoices for {customer1} (John Doe) ---")
    customer_invoices = get_customer_invoices(customer1)
    print(f"Found {len(customer_invoices)} invoice(s)")
    
    # Get single invoice with details
    print("\n--- Invoice Details ---")
    invoice_detail = get_invoice_by_id(invoice1)
    if invoice_detail:
        print(f"Invoice: {invoice_detail['invoice_number']}")
        print(f"Customer: {invoice_detail['customer_name']} - {invoice_detail['phone']}")
        print(f"Address: {invoice_detail['customer_address']}")
        print(f"Work: {invoice_detail['work_performed']}")
        print(f"Labor: ${invoice_detail['labor_cost']:.2f}")
        print(f"Status: {invoice_detail['status']}")
    
    # Update status
    print("\n--- Update Invoice Status ---")
    update_invoice_status(invoice1, 'paid')
    updated = get_invoice_by_id(invoice1)
    print(f"✅ Invoice {updated['invoice_number']} status changed to: {updated['status']}")
    
    print("\n✅ All operations working! Database has customers AND invoices!")