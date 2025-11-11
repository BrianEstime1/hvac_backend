from flask import Flask, jsonify, request
import sqlite3
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
    update_invoice_status,
    update_invoice,
    delete_invoice,
    check_customer_has_invoices
)
from validators import (
    validate_phone,
    validate_required_fields,
    validate_invoice_number,
    validate_numeric,
    validate_status,
    validate_customer_id
)

# Create Flask application
app = Flask(__name__)

# Initialize database when app starts
init_database()


# ==================== CUSTOMER ENDPOINTS ====================

@app.route('/customers', methods=['GET'])
def api_get_customers():
    """Get all customers - Returns JSON"""
    try:
        customers = get_all_customers()
        
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
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve customers: {str(e)}'}), 500


@app.route('/customers/<int:customer_id>', methods=['GET'])
def api_get_customer(customer_id):
    """Get single customer by ID"""
    try:
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
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve customer: {str(e)}'}), 500


@app.route('/customers', methods=['POST'])
def api_create_customer():
    """Create new customer - Expects JSON data"""
    try:
        data = request.get_json()

        # Check if JSON is valid 
        if not data:
            return jsonify({'error': 'Invalid JSON or missing Content-Type header'}), 400
        
        # Validate required fields
        is_valid, error = validate_required_fields(data, ['name', 'phone'])
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate and format phone number
        is_valid, phone_result = validate_phone(data.get('phone'))
        if not is_valid:
            return jsonify({'error': phone_result}), 400
        
        # Get data from request
        name = data.get('name').strip()
        phone = phone_result  # Use validated/formatted phone
        address = data.get('address', '').strip()
        
        # Create customer
        customer_id = add_customer(name, phone, address)
        
        return jsonify({
            'message': 'Customer created successfully',
            'id': customer_id,
            'phone': phone  # Return formatted phone
        }), 201
    
    except sqlite3.IntegrityError as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to create customer: {str(e)}'}), 500


@app.route('/customers/<int:customer_id>', methods=['PUT'])
def api_update_customer(customer_id):
    """Update existing customer"""
    try:
        # Check if customer exists
        customer = get_customer_by_id(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON or missing Content-Type header'}), 400
        
        # Validate required fields
        is_valid, error = validate_required_fields(data, ['name', 'phone'])
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate and format phone number
        is_valid, phone_result = validate_phone(data.get('phone'))
        if not is_valid:
            return jsonify({'error': phone_result}), 400
        
        # Get data
        name = data.get('name').strip()
        phone = phone_result
        address = data.get('address', '').strip()
        
        # Update customer
        update_customer(customer_id, name, phone, address)
        
        return jsonify({
            'message': 'Customer updated successfully',
            'id': customer_id,
            'name': name,
            'phone': phone,
            'address': address
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to update customer: {str(e)}'}), 500


@app.route('/customers/<int:customer_id>', methods=['DELETE'])
def api_delete_customer(customer_id):
    """Delete a customer (only if they have no invoices)"""
    try:
        # Check if customer exists
        customer = get_customer_by_id(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        # Check if customer has invoices
        if check_customer_has_invoices(customer_id):
            return jsonify({
                'error': 'Cannot delete customer with existing invoices',
                'suggestion': 'Delete all customer invoices first'
            }), 409
        
        # Delete customer
        delete_customer(customer_id)
        
        return jsonify({
            'message': 'Customer deleted successfully',
            'id': customer_id
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to delete customer: {str(e)}'}), 500


# ==================== INVOICE ENDPOINTS ====================

@app.route('/invoices', methods=['GET'])
def api_get_invoices():
    """Get all invoices with customer information - Returns JSON"""
    try:
        invoices = get_all_invoices()
        
        invoice_list = []
        for invoice in invoices:
            # Calculate totals
            subtotal = invoice['labor_cost'] + invoice['materials_cost']
            tax = subtotal * invoice['tax_rate']
            total = subtotal + tax

            invoice_list.append({
                'id': invoice['id'],
                'invoice_number': invoice['invoice_number'],
                'customer_id': invoice['customer_id'],
                'customer_name': invoice['customer_name'],
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
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve invoices: {str(e)}'}), 500


@app.route('/invoices/<int:invoice_id>', methods=['GET'])
def api_get_invoice(invoice_id):
    """Get single invoice with all details"""
    try:
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
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve invoice: {str(e)}'}), 500


@app.route('/invoices', methods=['POST'])
def api_create_invoice():
    """Create new invoice - Expects JSON data"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Invalid JSON or missing Content-Type header'}), 400
        
        # Validate required fields
        required = ['customer_id', 'invoice_number', 'date', 'technician', 'work_performed']
        is_valid, error = validate_required_fields(data, required)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate customer exists
        is_valid, customer_result = validate_customer_id(data.get('customer_id'))
        if not is_valid:
            return jsonify({'error': customer_result}), 404
        
        # Validate invoice number is unique
        is_valid, error = validate_invoice_number(data.get('invoice_number'))
        if not is_valid:
            return jsonify({'error': error}), 409
        
        # Validate numeric fields
        is_valid, labor_cost = validate_numeric(
            data.get('labor_cost', 0), 
            'Labor cost', 
            min_value=0, 
            allow_none=True
        )
        if not is_valid:
            return jsonify({'error': labor_cost}), 400
        
        is_valid, materials_cost = validate_numeric(
            data.get('materials_cost', 0),
            'Materials cost',
            min_value=0,
            allow_none=True
        )
        if not is_valid:
            return jsonify({'error': materials_cost}), 400
        
        # Create invoice
        invoice_id = create_invoice(
            customer_id=data.get('customer_id'),
            invoice_number=data.get('invoice_number'),
            date=data.get('date'),
            technician=data.get('technician'),
            work_performed=data.get('work_performed'),
            labor_cost=labor_cost,
            scheduled_time=data.get('scheduled_time', ''),
            description=data.get('description', ''),
            recommendations=data.get('recommendations', '')
        )
        
        return jsonify({
            'message': 'Invoice created successfully',
            'id': invoice_id,
            'invoice_number': data.get('invoice_number')
        }), 201
    
    except sqlite3.IntegrityError as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to create invoice: {str(e)}'}), 500


@app.route('/invoices/<int:invoice_id>', methods=['PUT'])
def api_update_invoice(invoice_id):
    """Update an existing invoice"""
    try:
        # Check if invoice exists
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON or missing Content-Type header'}), 400
        
        # Validate required fields
        required = ['invoice_number', 'date', 'technician', 'work_performed']
        is_valid, error = validate_required_fields(data, required)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate invoice number (exclude current invoice from duplicate check)
        is_valid, error = validate_invoice_number(
            data.get('invoice_number'),
            exclude_id=invoice_id
        )
        if not is_valid:
            return jsonify({'error': error}), 409
        
        # Validate numeric fields
        is_valid, labor_cost = validate_numeric(
            data.get('labor_cost', 0),
            'Labor cost',
            min_value=0,
            allow_none=True
        )
        if not is_valid:
            return jsonify({'error': labor_cost}), 400
        
        is_valid, materials_cost = validate_numeric(
            data.get('materials_cost', 0),
            'Materials cost',
            min_value=0,
            allow_none=True
        )
        if not is_valid:
            return jsonify({'error': materials_cost}), 400
        
        is_valid, tax_rate = validate_numeric(
            data.get('tax_rate', 0.08),
            'Tax rate',
            min_value=0,
            allow_none=True
        )
        if not is_valid:
            return jsonify({'error': tax_rate}), 400
        
        # Update invoice
        success = update_invoice(
            invoice_id=invoice_id,
            invoice_number=data.get('invoice_number'),
            date=data.get('date'),
            technician=data.get('technician'),
            work_performed=data.get('work_performed'),
            labor_cost=labor_cost,
            materials_cost=materials_cost,
            scheduled_time=data.get('scheduled_time', ''),
            description=data.get('description', ''),
            recommendations=data.get('recommendations', ''),
            tax_rate=tax_rate
        )
        
        if success:
            return jsonify({
                'message': 'Invoice updated successfully',
                'id': invoice_id
            })
        else:
            return jsonify({'error': 'Failed to update invoice'}), 500
    
    except sqlite3.IntegrityError as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to update invoice: {str(e)}'}), 500


@app.route('/invoices/<int:invoice_id>', methods=['DELETE'])
def api_delete_invoice(invoice_id):
    """Delete an invoice"""
    try:
        # Check if invoice exists
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Delete invoice
        delete_invoice(invoice_id)
        
        return jsonify({
            'message': 'Invoice deleted successfully',
            'id': invoice_id,
            'invoice_number': invoice['invoice_number']
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to delete invoice: {str(e)}'}), 500


@app.route('/invoices/<int:invoice_id>/status', methods=['PUT'])
def api_update_invoice_status(invoice_id):
    """Update invoice status (draft → sent → paid → cancelled)"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Invalid JSON or missing Content-Type header'}), 400
        
        new_status = data.get('status')
        
        # Validate status
        valid_statuses = ['draft', 'sent', 'paid', 'cancelled']
        is_valid, error = validate_status(new_status, valid_statuses)
        if not is_valid:
            return jsonify({'error': error}), 400
        
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
    
    except Exception as e:
        return jsonify({'error': f'Failed to update status: {str(e)}'}), 500


@app.route('/customers/<int:customer_id>/invoices', methods=['GET'])
def api_get_customer_invoices(customer_id):
    """Get all invoices for a specific customer"""
    try:
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
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve customer invoices: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)