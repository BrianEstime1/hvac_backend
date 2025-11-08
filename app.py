from flask import Flask, jsonify, request
from database import (
    get_all_customers, 
    get_customer_by_id, 
    add_customer,
    update_customer,
    delete_customer,
    init_database
)

# Create Flask application
app = Flask(__name__)

# Initialize database when app starts
init_database()


# ==================== CUSTOMER ENDPOINTS ====================

@app.route('/customers', methods=['GET'])
def api_get_customers():
    """Get all customers - Returns JSON"""
    customers = get_all_customers()
    
    # Convert sqlite3.Row objects to dictionaries
    customer_list = []
    for customer in customers:
        customer_list.append({
            'id': customer['id'],
            'name': customer['name'],
            'phone': customer['phone'],
            'address': customer['address'],
            'created_at': customer['created_at']
        })
    
    return jsonify(customer_list)


@app.route('/customers/<int:customer_id>', methods=['GET'])
def api_get_customer(customer_id):
    """Get single customer by ID"""
    customer = get_customer_by_id(customer_id)
    
    if customer:
        return jsonify({
            'id': customer['id'],
            'name': customer['name'],
            'phone': customer['phone'],
            'address': customer['address'],
            'created_at': customer['created_at']
        })
    else:
        return jsonify({'error': 'Customer not found'}), 404


@app.route('/customers', methods=['POST'])
def api_create_customer():
    """Create new customer - Expects JSON data"""
    data = request.get_json()
    
    # Get data from request
    name = data.get('name')
    phone = data.get('phone')
    address = data.get('address', '')
    
    # Validate required fields
    if not name or not phone:
        return jsonify({'error': 'Name and phone are required'}), 400
    
    # Create customer
    customer_id = add_customer(name, phone, address)
    
    return jsonify({
        'message': 'Customer created successfully',
        'id': customer_id
    }), 201


if __name__ == '__main__':
    app.run(debug=True, port=5001)