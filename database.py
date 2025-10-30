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
        #create a table 
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS customers (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               name TEXT NOT NULL,
               phone TEXT NOT NULL,
               address TEXT,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
             )  
       ''' )

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

if __name__ == "__main__":
    # Initialize database
    init_database()
    
    # Test CREATE
    print("\n--- Testing CREATE ---")
    id1 = add_customer("John Doe", "(555) 123-4567", "123 Main St")
    id2 = add_customer("Jane Smith", "(555) 987-6543", "456 Oak Ave")
    print(f"Added customers with IDs: {id1}, {id2}")
    
    # Test READ ALL
    print("\n--- Testing READ ALL ---")
    customers = get_all_customers()
    for customer in customers:
        print(f"ID: {customer['id']}, Name: {customer['name']}, Phone: {customer['phone']}, Address: {customer['address']}")
    
    # Test READ ONE
    print("\n--- Testing READ ONE ---")
    customer = get_customer_by_id(id1)
    if customer:
        print(f"Found: Name: {customer['name']} at {customer['address']}")
    else:
        print("Customer not found!")
    
    # Test UPDATE
    print("\n--- Testing UPDATE ---")
    update_customer(id1, "John Doe Jr.", "(555) 111-2222", "789 New St")
    updated = get_customer_by_id(id1)
    if updated:
        print(f"Updated to: {updated['name']}, {updated['phone']}, {updated['address']}")
    
    # Test DELETE
    print("\n--- Testing DELETE ---")
    delete_customer(id2)
    remaining = get_all_customers()
    print(f"Remaining customers: {len(remaining)}")

    print("\n--- Testing Search ---")
    results = search_customers("John")
    print(f"Found {len(results)} customers matching 'John':")
    for customer in results:
        print(f"  - {customer['name']}")

    # Test COUNT
    print("\n--- Testing COUNT ---")
    total = count_customers()
    print(f"Total customers in database: {total}")
              
    

    
    print("\n✅ All CRUD operations working!")