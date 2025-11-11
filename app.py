from flask import Flask, jsonify, request
from database import (
    get_all_customers,
    get_all_invoices,
    get_customer_by_id,
    add_customer,
    get_customer_invoices,
    get_invoice_by_id,
    init_database,
    update_customer,
    delete_customer,
    create_invoice,          
    update_invoice_status     
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

    #check if JSON is valid 
    if not data:
         return jsonify({'error': 'Invalid JSON or missing Content-Type'}), 400
    
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

@app.route('/invoices', methods=['GET'])
def api_get_invoices():
    """Get all invoices with customer information - Returns JSON"""
    invoices = get_all_invoices()
    
    # Convert sqlite3.Row objects to dictionaries
    invoice_list = []
    for invoice in invoices:
        # calculate totals
        subtotal = invoice['labor_cost'] + invoice['materials_cost']
        tax = subtotal * invoice['tax_rate']
        total = subtotal + tax

        invoice_list.append({
            'id': invoice['id'],
            'invoice_number': invoice['invoice_number'],
            'customer_id': invoice['customer_id'],
            'customer_name': invoice['customer_name'],  # ← From JOIN!
            'customer_phone': invoice['phone'],
            'date': invoice['date'],
            'technician': invoice['technician'],
            'work_performed': invoice['work_performed'],
            'labor_cost': invoice['labor_cost'],
            'materials_cost': invoice['materials_cost'],
            'tax_rate': invoice['tax_rate'],
            'subtotal': round(subtotal, 2),
            'tax': round(tax, 2),
            'total': round(total, 2),
            'status': invoice['status'],
            'created_at': invoice['created_at']

        })
    
    return jsonify(invoice_list)

@app.route('/invoices/<int:invoice_id>', methods=['GET'])
def api_get_invoice(invoice_id):
    """Get single invoice with all details"""
    invoice = get_invoice_by_id(invoice_id)
    
    if not invoice:
        return jsonify({'error': 'Invoice not found'}), 404
    
    # Calculate totals
    subtotal = invoice['labor_cost'] + invoice['materials_cost']
    tax = subtotal * invoice['tax_rate']
    total = subtotal + tax
    
    return jsonify({
        'id': invoice['id'],
        'invoice_number': invoice['invoice_number'],
        'customer': {
            'id': invoice['customer_id'],
            'name': invoice['customer_name'],
            'phone': invoice['phone'],
            'address': invoice['customer_address']
        },
        'date': invoice['date'],
        'scheduled_time': invoice['scheduled_time'],
        'technician': invoice['technician'],
        'work_performed': invoice['work_performed'],
        'description': invoice['description'],
        'recommendations': invoice['recommendations'],
        'costs': {
            'labor': invoice['labor_cost'],
            'materials': invoice['materials_cost'],
            'subtotal': round(subtotal, 2),
            'tax_rate': invoice['tax_rate'],
            'tax': round(tax, 2),
            'total': round(total, 2)
        },
        'status': invoice['status'],
        'created_at': invoice['created_at']
    }) 


@app.route('/invoices', methods=['POST'])
def api_create_invoice():
    """Create new invoice - Expects JSON data"""
    data = request.get_json()
    
    # Get data from request
    customer_id = data.get('customer_id')
    invoice_number = data.get('invoice_number')
    date = data.get('date')
    technician = data.get('technician')
    work_performed = data.get('work_performed')
    labor_cost = data.get('labor_cost')
    scheduled_time = data.get('scheduled_time', "")
    description = data.get('description', "")
    recommendations = data.get('recommendations', "")
    
# Validate required fields
    if not all([customer_id, invoice_number, date, technician, work_performed]):
        return jsonify({
            'error': 'Missing required fields',
            'required': ['customer_id', 'invoice_number', 'date', 'technician', 'work_performed']
        }), 400
    
    # Check if customer exists
    customer = get_customer_by_id(customer_id)
    if not customer:
        return jsonify({'error': f'Customer with ID {customer_id} not found'}), 404
    
    # Create invoice
    try:
        invoice_id = create_invoice(
            customer_id=customer_id,
            invoice_number=invoice_number,
            date=date,
            technician=technician,
            work_performed=work_performed,
            labor_cost=labor_cost,
            scheduled_time=scheduled_time,
            description=description,
            recommendations=recommendations
        )
        
        return jsonify({
            'message': 'Invoice created successfully',
            'id': invoice_id,
            'invoice_number': invoice_number
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/invoices/<int:invoice_id>/status', methods=['PUT'])
def api_update_invoice_status(invoice_id):
    """Update invoice status (draft → sent → paid → cancelled)"""
    data = request.get_json()
    new_status = data.get('status')
    
    # Validate status
    valid_statuses = ['draft', 'sent', 'paid', 'cancelled']
    if new_status not in valid_statuses:
        return jsonify({
            'error': 'Invalid status',
            'valid_statuses': valid_statuses
        }), 400
    
    # Check if invoice exists
    invoice = get_invoice_by_id(invoice_id)
    if not invoice:
        return jsonify({'error': 'Invoice not found'}), 404
    
    # Update status
    update_invoice_status(invoice_id, new_status)
    
    return jsonify({
        'message': 'Status updated successfully',
        'invoice_number': invoice['invoice_number'],
        'old_status': invoice['status'],
        'new_status': new_status
    })

@app.route('/customers/<int:customer_id>/invoices', methods=['GET'])
def api_get_customer_invoices(customer_id):
    """Get all invoices for a specific customer"""
    # Check if customer exists
    customer = get_customer_by_id(customer_id)
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    
    # Get their invoices
    invoices = get_customer_invoices(customer_id)
    
    # Format response
    invoice_list = []
    for invoice in invoices:
        subtotal = invoice['labor_cost'] + invoice['materials_cost']
        tax = subtotal * invoice['tax_rate']
        total = subtotal + tax
        
        invoice_list.append({
            'id': invoice['id'],
            'invoice_number': invoice['invoice_number'],
            'date': invoice['date'],
            'technician': invoice['technician'],
            'work_performed': invoice['work_performed'],
            'total': round(total, 2),
            'status': invoice['status']
        })
    
    return jsonify({
        'customer': {
            'id': customer['id'],
            'name': customer['name']
        },
        'invoice_count': len(invoice_list),
        'invoices': invoice_list
    })



if __name__ == '__main__':
    app.run(debug=True, port=5001)