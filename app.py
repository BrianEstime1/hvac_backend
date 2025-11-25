from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from datetime import datetime
from database import (
    get_all_customers, get_all_invoices, get_customer_by_id, add_customer,
    get_customer_invoices, get_invoice_by_id, init_database, update_customer,
    update_invoice_status, delete_customer, create_invoice, update_invoice,
    delete_invoice, check_customer_has_invoices,
    # Appointment functions
    create_appointment, get_all_appointments, get_appointment_by_id,
    update_appointment, update_appointment_status, delete_appointment,
    get_customer_appointments, get_appointments_by_date, 
    get_appointments_by_technician, link_appointment_to_invoice,
    # Inventory functions
    create_inventory_item, get_all_inventory, get_inventory_by_id,
    update_inventory_item, adjust_inventory_quantity, delete_inventory_item,
    get_low_stock_items, get_inventory_by_category, search_inventory,
    calculate_total_inventory_value, record_inventory_usage,
    get_usage_by_appointment, get_usage_by_invoice, get_item_usage_history
)
from validators import (
    validate_phone, validate_required_fields, validate_invoice_number,
    validate_numeric, validate_status, validate_customer_id,
    # Appointment validators
    validate_date, validate_time, validate_appointment_status,
    # Inventory validators
    validate_inventory_id, validate_category, validate_unit
)

app = Flask(__name__)

# CORS Configuration - Allow Vercel frontend
CORS(app, origins=[
    'https://hvac-frontend-eight.vercel.app',
    'https://hvac-frontend-git-main-brianestime1s-projects.vercel.app',
    'https://hvac-frontend-skxykklys-brianestime1s-projects.vercel.app',
    'http://localhost:5173',
    'http://localhost:3000'
], supports_credentials=True)

init_database()


# ==================== DASHBOARD ENDPOINT ====================

@app.route('/api/dashboard/stats', methods=['GET'])
def api_get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        customers = get_all_customers()
        appointments = get_all_appointments()
        low_stock = get_low_stock_items()
        
        # Get upcoming appointments (today and future)
        today = datetime.now().date().isoformat()
        upcoming_appointments = [apt for apt in appointments if apt['appointment_date'] >= today and apt['status'] == 'scheduled']
        
        return jsonify({
            'total_customers': len(customers),
            'upcoming_appointments': len(upcoming_appointments),
            'low_stock_items': len(low_stock)
        })
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve stats: {str(e)}'}), 500


# ==================== CUSTOMER ENDPOINTS ====================

@app.route('/api/customers', methods=['GET'])
def api_get_customers():
    """Get all customers"""
    try:
        customers = get_all_customers()
        customer_list = [dict(c) for c in customers]
        return jsonify(customer_list)
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve customers: {str(e)}'}), 500


@app.route('/api/customers/<int:customer_id>', methods=['GET'])
def api_get_customer(customer_id):
    """Get single customer by ID"""
    try:
        customer = get_customer_by_id(customer_id)
        if customer:
            return jsonify(dict(customer))
        return jsonify({'error': 'Customer not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve customer: {str(e)}'}), 500


@app.route('/api/customers', methods=['POST'])
def api_create_customer():
    """Create new customer"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON or missing Content-Type header'}), 400
        
        # Validate required fields
        is_valid, error = validate_required_fields(data, ['name', 'phone'])
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate phone
        is_valid, phone_result = validate_phone(data.get('phone'))
        if not is_valid:
            return jsonify({'error': phone_result}), 400
        
        # Create customer
        name = data.get('name').strip()
        phone = phone_result
        address = data.get('address', '').strip()
        
        customer_id = add_customer(name, phone, address)
        
        return jsonify({
            'message': 'Customer created successfully',
            'id': customer_id,
            'phone': phone
        }), 201
    
    except sqlite3.IntegrityError as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to create customer: {str(e)}'}), 500


@app.route('/api/customers/<int:customer_id>', methods=['PUT'])
def api_update_customer(customer_id):
    """Update existing customer"""
    try:
        customer = get_customer_by_id(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        # Validate required fields
        is_valid, error = validate_required_fields(data, ['name', 'phone'])
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate phone
        is_valid, phone_result = validate_phone(data.get('phone'))
        if not is_valid:
            return jsonify({'error': phone_result}), 400
        
        name = data.get('name').strip()
        phone = phone_result
        address = data.get('address', '').strip()
        
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


@app.route('/api/customers/<int:customer_id>', methods=['DELETE'])
def api_delete_customer(customer_id):
    """Delete customer (only if no invoices)"""
    try:
        customer = get_customer_by_id(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        if check_customer_has_invoices(customer_id):
            return jsonify({
                'error': 'Cannot delete customer with existing invoices',
                'suggestion': 'Delete all customer invoices first'
            }), 409
        
        delete_customer(customer_id)
        
        return jsonify({
            'message': 'Customer deleted successfully',
            'id': customer_id
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to delete customer: {str(e)}'}), 500


@app.route('/api/customers/<int:customer_id>/invoices', methods=['GET'])
def api_get_customer_invoices(customer_id):
    """Get all invoices for a customer"""
    try:
        customer = get_customer_by_id(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        invoices = get_customer_invoices(customer_id)
        
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
            'customer': {'id': customer['id'], 'name': customer['name']},
            'invoice_count': len(invoice_list),
            'invoices': invoice_list
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve invoices: {str(e)}'}), 500


# ==================== INVOICE ENDPOINTS ====================

@app.route('/api/invoices', methods=['GET'])
def api_get_invoices():
    """Get all invoices"""
    try:
        invoices = get_all_invoices()
        
        invoice_list = []
        for invoice in invoices:
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


@app.route('/api/invoices/<int:invoice_id>', methods=['GET'])
def api_get_invoice(invoice_id):
    """Get single invoice"""
    try:
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
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


@app.route('/api/invoices', methods=['POST'])
def api_create_invoice():
    """Create new invoice"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        # Validate required fields
        required = ['customer_id', 'invoice_number', 'date', 'technician', 'work_performed']
        is_valid, error = validate_required_fields(data, required)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate customer exists
        is_valid, customer_result = validate_customer_id(data.get('customer_id'))
        if not is_valid:
            return jsonify({'error': customer_result}), 404
        
        # Validate invoice number unique
        is_valid, error = validate_invoice_number(data.get('invoice_number'))
        if not is_valid:
            return jsonify({'error': error}), 409
        
        # Validate labor cost
        is_valid, labor_cost = validate_numeric(
            data.get('labor_cost', 0), 'Labor cost', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': labor_cost}), 400
        
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


@app.route('/api/invoices/<int:invoice_id>', methods=['PUT'])
def api_update_invoice(invoice_id):
    """Update invoice"""
    try:
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        # Validate required fields
        required = ['invoice_number', 'date', 'technician', 'work_performed']
        is_valid, error = validate_required_fields(data, required)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate invoice number (exclude current invoice)
        is_valid, error = validate_invoice_number(
            data.get('invoice_number'), exclude_id=invoice_id
        )
        if not is_valid:
            return jsonify({'error': error}), 409
        
        # Validate numeric fields
        is_valid, labor_cost = validate_numeric(
            data.get('labor_cost', 0), 'Labor cost', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': labor_cost}), 400
        
        is_valid, materials_cost = validate_numeric(
            data.get('materials_cost', 0), 'Materials cost', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': materials_cost}), 400
        
        is_valid, tax_rate = validate_numeric(
            data.get('tax_rate', 0.08), 'Tax rate', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': tax_rate}), 400
        
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
            return jsonify({'message': 'Invoice updated successfully', 'id': invoice_id})
        return jsonify({'error': 'Failed to update invoice'}), 500
    
    except sqlite3.IntegrityError as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to update invoice: {str(e)}'}), 500


@app.route('/api/invoices/<int:invoice_id>', methods=['DELETE'])
def api_delete_invoice(invoice_id):
    """Delete invoice"""
    try:
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        delete_invoice(invoice_id)
        
        return jsonify({
            'message': 'Invoice deleted successfully',
            'id': invoice_id,
            'invoice_number': invoice['invoice_number']
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to delete invoice: {str(e)}'}), 500


@app.route('/api/invoices/<int:invoice_id>/status', methods=['PUT'])
def api_update_invoice_status(invoice_id):
    """Update invoice status"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        new_status = data.get('status')
        valid_statuses = ['draft', 'sent', 'paid', 'cancelled']
        is_valid, error = validate_status(new_status, valid_statuses)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        update_invoice_status(invoice_id, new_status)
        
        return jsonify({
            'message': 'Status updated successfully',
            'invoice_number': invoice['invoice_number'],
            'old_status': invoice['status'],
            'new_status': new_status
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to update status: {str(e)}'}), 500


# ==================== APPOINTMENT ENDPOINTS ====================

@app.route('/api/appointments', methods=['GET'])
def api_get_appointments():
    """Get all appointments"""
    try:
        appointments = get_all_appointments()
        
        appointment_list = []
        for apt in appointments:
            appointment_list.append({
                'id': apt['id'],
                'customer_id': apt['customer_id'],
                'customer_name': apt['customer_name'],
                'customer_phone': apt['customer_phone'],
                'customer_address': apt['customer_address'],
                'appointment_date': apt['appointment_date'],
                'appointment_time': apt['appointment_time'],
                'technician': apt['technician'],
                'service_type': apt['service_type'],
                'notes': apt['notes'],
                'status': apt['status'],
                'invoice_id': apt['invoice_id'],
                'created_at': apt['created_at']
            })
        
        return jsonify(appointment_list)
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve appointments: {str(e)}'}), 500


@app.route('/api/appointments/<int:appointment_id>', methods=['GET'])
def api_get_appointment(appointment_id):
    """Get single appointment"""
    try:
        apt = get_appointment_by_id(appointment_id)
        if not apt:
            return jsonify({'error': 'Appointment not found'}), 404
        
        return jsonify({
            'id': apt['id'],
            'customer': {
                'id': apt['customer_id'],
                'name': apt['customer_name'],
                'phone': apt['customer_phone'],
                'address': apt['customer_address']
            },
            'appointment_date': apt['appointment_date'],
            'appointment_time': apt['appointment_time'],
            'technician': apt['technician'],
            'service_type': apt['service_type'],
            'notes': apt['notes'],
            'status': apt['status'],
            'invoice_id': apt['invoice_id'],
            'created_at': apt['created_at']
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve appointment: {str(e)}'}), 500


@app.route('/api/appointments', methods=['POST'])
def api_create_appointment():
    """Create new appointment"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        # Validate required fields
        required = ['customer_id', 'appointment_date', 'appointment_time']
        is_valid, error = validate_required_fields(data, required)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate customer exists
        is_valid, customer_result = validate_customer_id(data.get('customer_id'))
        if not is_valid:
            return jsonify({'error': customer_result}), 404
        
        # Validate date
        is_valid, date_result = validate_date(data.get('appointment_date'))
        if not is_valid:
            return jsonify({'error': date_result}), 400
        
        # Validate time
        is_valid, time_result = validate_time(data.get('appointment_time'))
        if not is_valid:
            return jsonify({'error': time_result}), 400
        
        # Use description as service_type if service_type not provided
        service_type = data.get('service_type') or data.get('notes') or 'Service Call'
        
        appointment_id = create_appointment(
            customer_id=data.get('customer_id'),
            appointment_date=date_result,
            appointment_time=time_result,
            service_type=service_type,
            technician=data.get('technician', ''),
            notes=data.get('notes', '')
        )
        
        return jsonify({
            'message': 'Appointment created successfully',
            'id': appointment_id
        }), 201
    
    except Exception as e:
        return jsonify({'error': f'Failed to create appointment: {str(e)}'}), 500


@app.route('/api/appointments/<int:appointment_id>', methods=['PUT'])
def api_update_appointment(appointment_id):
    """Update appointment"""
    try:
        apt = get_appointment_by_id(appointment_id)
        if not apt:
            return jsonify({'error': 'Appointment not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        # Validate required fields
        required = ['appointment_date', 'appointment_time', 'service_type']
        is_valid, error = validate_required_fields(data, required)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate date
        is_valid, date_result = validate_date(data.get('appointment_date'))
        if not is_valid:
            return jsonify({'error': date_result}), 400
        
        # Validate time
        is_valid, time_result = validate_time(data.get('appointment_time'))
        if not is_valid:
            return jsonify({'error': time_result}), 400
        
        success = update_appointment(
            appointment_id=appointment_id,
            appointment_date=date_result,
            appointment_time=time_result,
            technician=data.get('technician', ''),
            service_type=data.get('service_type'),
            notes=data.get('notes', '')
        )
        
        if success:
            return jsonify({'message': 'Appointment updated successfully', 'id': appointment_id})
        return jsonify({'error': 'Failed to update appointment'}), 500
    
    except Exception as e:
        return jsonify({'error': f'Failed to update appointment: {str(e)}'}), 500


@app.route('/api/appointments/<int:appointment_id>', methods=['DELETE'])
def api_delete_appointment(appointment_id):
    """Delete appointment"""
    try:
        apt = get_appointment_by_id(appointment_id)
        if not apt:
            return jsonify({'error': 'Appointment not found'}), 404
        
        delete_appointment(appointment_id)
        
        return jsonify({
            'message': 'Appointment deleted successfully',
            'id': appointment_id
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to delete appointment: {str(e)}'}), 500


@app.route('/api/appointments/<int:appointment_id>/status', methods=['PUT'])
def api_update_appointment_status(appointment_id):
    """Update appointment status"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        new_status = data.get('status')
        is_valid, error = validate_appointment_status(new_status)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        apt = get_appointment_by_id(appointment_id)
        if not apt:
            return jsonify({'error': 'Appointment not found'}), 404
        
        update_appointment_status(appointment_id, new_status)
        
        return jsonify({
            'message': 'Status updated successfully',
            'old_status': apt['status'],
            'new_status': new_status
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to update status: {str(e)}'}), 500


@app.route('/api/appointments/<int:appointment_id>/link-invoice', methods=['PUT'])
def api_link_appointment_to_invoice(appointment_id):
    """Link appointment to invoice (marks as completed)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        invoice_id = data.get('invoice_id')
        if not invoice_id:
            return jsonify({'error': 'invoice_id is required'}), 400
        
        # Check appointment exists
        apt = get_appointment_by_id(appointment_id)
        if not apt:
            return jsonify({'error': 'Appointment not found'}), 404
        
        # Check invoice exists
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        link_appointment_to_invoice(appointment_id, invoice_id)
        
        return jsonify({
            'message': 'Appointment linked to invoice and marked completed',
            'appointment_id': appointment_id,
            'invoice_id': invoice_id
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to link appointment: {str(e)}'}), 500


@app.route('/api/customers/<int:customer_id>/appointments', methods=['GET'])
def api_get_customer_appointments(customer_id):
    """Get all appointments for a customer"""
    try:
        customer = get_customer_by_id(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        appointments = get_customer_appointments(customer_id)
        
        appointment_list = []
        for apt in appointments:
            appointment_list.append({
                'id': apt['id'],
                'appointment_date': apt['appointment_date'],
                'appointment_time': apt['appointment_time'],
                'technician': apt['technician'],
                'service_type': apt['service_type'],
                'status': apt['status'],
                'invoice_id': apt['invoice_id']
            })
        
        return jsonify({
            'customer': {'id': customer['id'], 'name': customer['name']},
            'appointment_count': len(appointment_list),
            'appointments': appointment_list
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve appointments: {str(e)}'}), 500


@app.route('/api/appointments/date/<date>', methods=['GET'])
def api_get_appointments_by_date(date):
    """Get all appointments for a specific date"""
    try:
        # Validate date format
        is_valid, date_result = validate_date(date)
        if not is_valid:
            return jsonify({'error': date_result}), 400
        
        appointments = get_appointments_by_date(date_result)
        
        appointment_list = []
        for apt in appointments:
            appointment_list.append({
                'id': apt['id'],
                'appointment_time': apt['appointment_time'],
                'customer_name': apt['customer_name'],
                'customer_phone': apt['customer_phone'],
                'technician': apt['technician'],
                'service_type': apt['service_type'],
                'status': apt['status']
            })
        
        return jsonify({
            'date': date_result,
            'appointment_count': len(appointment_list),
            'appointments': appointment_list
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve appointments: {str(e)}'}), 500


@app.route('/api/appointments/technician/<technician>', methods=['GET'])
def api_get_appointments_by_technician(technician):
    """Get all appointments for a specific technician"""
    try:
        appointments = get_appointments_by_technician(technician)
        
        appointment_list = []
        for apt in appointments:
            appointment_list.append({
                'id': apt['id'],
                'appointment_date': apt['appointment_date'],
                'appointment_time': apt['appointment_time'],
                'customer_name': apt['customer_name'],
                'customer_phone': apt['customer_phone'],
                'service_type': apt['service_type'],
                'status': apt['status']
            })
        
        return jsonify({
            'technician': technician,
            'appointment_count': len(appointment_list),
            'appointments': appointment_list
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve appointments: {str(e)}'}), 500


# ==================== INVENTORY ENDPOINTS ====================

@app.route('/api/inventory', methods=['GET'])
def api_get_inventory():
    """Get all inventory items"""
    try:
        items = get_all_inventory()
        
        item_list = []
        for item in items:
            total_value = item['quantity'] * item['cost_per_unit']
            is_low_stock = item['quantity'] <= item['low_stock_threshold']
            
            item_list.append({
                'id': item['id'],
                'name': item['name'],
                'category': item['category'],
                'sku': item['sku'],
                'quantity': item['quantity'],
                'unit': item['unit'],
                'cost_per_unit': item['cost_per_unit'],
                'total_value': round(total_value, 2),
                'low_stock_threshold': item['low_stock_threshold'],
                'is_low_stock': is_low_stock,
                'supplier': item['supplier'],
                'notes': item['notes'],
                'created_at': item['created_at']
            })
        
        return jsonify(item_list)
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve inventory: {str(e)}'}), 500


@app.route('/api/inventory/<int:item_id>', methods=['GET'])
def api_get_inventory_item(item_id):
    """Get single inventory item"""
    try:
        item = get_inventory_by_id(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        total_value = item['quantity'] * item['cost_per_unit']
        is_low_stock = item['quantity'] <= item['low_stock_threshold']
        
        return jsonify({
            'id': item['id'],
            'name': item['name'],
            'category': item['category'],
            'sku': item['sku'],
            'quantity': item['quantity'],
            'unit': item['unit'],
            'cost_per_unit': item['cost_per_unit'],
            'total_value': round(total_value, 2),
            'low_stock_threshold': item['low_stock_threshold'],
            'is_low_stock': is_low_stock,
            'supplier': item['supplier'],
            'notes': item['notes'],
            'created_at': item['created_at']
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve item: {str(e)}'}), 500


@app.route('/api/inventory', methods=['POST'])
def api_create_inventory_item():
    """Create new inventory item"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        # Validate required fields
        required = ['name', 'category']
        is_valid, error = validate_required_fields(data, required)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate category
        is_valid, category = validate_category(data.get('category'))
        if not is_valid:
            return jsonify({'error': category}), 400
        
        # Validate unit (default to 'each' if not provided)
        unit_value = data.get('unit', 'each')
        is_valid, unit = validate_unit(unit_value)
        if not is_valid:
            return jsonify({'error': unit}), 400
        
        # Validate numeric fields
        is_valid, quantity = validate_numeric(
            data.get('quantity', 0), 'Quantity', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': quantity}), 400
        
        is_valid, cost = validate_numeric(
            data.get('cost_per_unit', 0), 'Cost per unit', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': cost}), 400
        
        is_valid, threshold = validate_numeric(
            data.get('low_stock_threshold', 5), 'Low stock threshold', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': threshold}), 400
        
        item_id = create_inventory_item(
            name=data.get('name'),
            category=category,
            unit=unit,
            sku=data.get('sku', ''),
            quantity=int(quantity),
            cost_per_unit=cost,
            low_stock_threshold=int(threshold),
            supplier=data.get('supplier', ''),
            notes=data.get('notes', '')
        )
        
        return jsonify({
            'message': 'Inventory item created successfully',
            'id': item_id
        }), 201
    
    except sqlite3.IntegrityError as e:
        return jsonify({'error': f'Database error (SKU may already exist): {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to create item: {str(e)}'}), 500


@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
def api_update_inventory_item(item_id):
    """Update inventory item"""
    try:
        item = get_inventory_by_id(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        # Validate required fields
        required = ['name', 'category', 'unit']
        is_valid, error = validate_required_fields(data, required)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate category
        is_valid, category = validate_category(data.get('category'))
        if not is_valid:
            return jsonify({'error': category}), 400
        
        # Validate unit
        is_valid, unit = validate_unit(data.get('unit'))
        if not is_valid:
            return jsonify({'error': unit}), 400
        
        # Validate numeric fields
        is_valid, quantity = validate_numeric(
            data.get('quantity', 0), 'Quantity', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': quantity}), 400
        
        is_valid, cost = validate_numeric(
            data.get('cost_per_unit', 0), 'Cost per unit', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': cost}), 400
        
        is_valid, threshold = validate_numeric(
            data.get('low_stock_threshold', 5), 'Low stock threshold', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': threshold}), 400
        
        success = update_inventory_item(
            item_id=item_id,
            name=data.get('name'),
            category=category,
            unit=unit,
            sku=data.get('sku', ''),
            quantity=int(quantity),
            cost_per_unit=cost,
            low_stock_threshold=int(threshold),
            supplier=data.get('supplier', ''),
            notes=data.get('notes', '')
        )
        
        if success:
            return jsonify({'message': 'Inventory item updated successfully', 'id': item_id})
        return jsonify({'error': 'Failed to update item'}), 500
    
    except sqlite3.IntegrityError as e:
        return jsonify({'error': f'Database error (SKU may already exist): {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to update item: {str(e)}'}), 500


@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
def api_delete_inventory_item(item_id):
    """Delete inventory item"""
    try:
        item = get_inventory_by_id(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        delete_inventory_item(item_id)
        
        return jsonify({
            'message': 'Inventory item deleted successfully',
            'id': item_id
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to delete item: {str(e)}'}), 500


@app.route('/api/inventory/<int:item_id>/adjust', methods=['PUT'])
def api_adjust_inventory(item_id):
    """Adjust inventory quantity (add or subtract)"""
    try:
        item = get_inventory_by_id(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        quantity_change = data.get('quantity_change')
        if quantity_change is None:
            return jsonify({'error': 'quantity_change is required'}), 400
        
        try:
            quantity_change = int(quantity_change)
        except (ValueError, TypeError):
            return jsonify({'error': 'quantity_change must be an integer'}), 400
        
        success = adjust_inventory_quantity(item_id, quantity_change)
        
        if not success:
            return jsonify({'error': 'Adjustment would result in negative inventory'}), 400
        
        # Get updated item
        updated_item = get_inventory_by_id(item_id)
        
        return jsonify({
            'message': 'Inventory adjusted successfully',
            'id': item_id,
            'old_quantity': item['quantity'],
            'quantity_change': quantity_change,
            'new_quantity': updated_item['quantity']
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to adjust inventory: {str(e)}'}), 500


@app.route('/api/inventory/low-stock', methods=['GET'])
def api_get_low_stock():
    """Get items below low stock threshold"""
    try:
        items = get_low_stock_items()
        
        item_list = []
        for item in items:
            item_list.append({
                'id': item['id'],
                'name': item['name'],
                'category': item['category'],
                'sku': item['sku'],
                'quantity': item['quantity'],
                'low_stock_threshold': item['low_stock_threshold'],
                'unit': item['unit'],
                'supplier': item['supplier']
            })
        
        return jsonify({
            'count': len(item_list),
            'items': item_list
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve low stock items: {str(e)}'}), 500


@app.route('/api/inventory/category/<category>', methods=['GET'])
def api_get_inventory_by_category(category):
    """Get all items in a category"""
    try:
        # Validate category
        is_valid, validated_category = validate_category(category)
        if not is_valid:
            return jsonify({'error': validated_category}), 400
        
        items = get_inventory_by_category(validated_category)
        
        item_list = []
        for item in items:
            item_list.append({
                'id': item['id'],
                'name': item['name'],
                'sku': item['sku'],
                'quantity': item['quantity'],
                'unit': item['unit'],
                'cost_per_unit': item['cost_per_unit']
            })
        
        return jsonify({
            'category': validated_category,
            'count': len(item_list),
            'items': item_list
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve items: {str(e)}'}), 500


@app.route('/api/inventory/search', methods=['GET'])
def api_search_inventory():
    """Search inventory by name or SKU"""
    try:
        search_term = request.args.get('q', '')
        if not search_term:
            return jsonify({'error': 'Search term (q) is required'}), 400
        
        items = search_inventory(search_term)
        
        item_list = []
        for item in items:
            item_list.append({
                'id': item['id'],
                'name': item['name'],
                'category': item['category'],
                'sku': item['sku'],
                'quantity': item['quantity'],
                'unit': item['unit']
            })
        
        return jsonify({
            'search_term': search_term,
            'count': len(item_list),
            'items': item_list
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to search inventory: {str(e)}'}), 500


@app.route('/api/inventory/value', methods=['GET'])
def api_get_inventory_value():
    """Get total inventory value"""
    try:
        total_value = calculate_total_inventory_value()
        
        return jsonify({
            'total_inventory_value': round(total_value, 2)
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to calculate inventory value: {str(e)}'}), 500


# ==================== INVENTORY USAGE ENDPOINTS ====================

@app.route('/api/inventory/usage', methods=['POST'])
def api_record_usage():
    """Record parts used on a job"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        # Validate required fields
        required = ['inventory_id', 'quantity_used', 'date_used']
        is_valid, error = validate_required_fields(data, required)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Validate inventory exists
        is_valid, item = validate_inventory_id(data.get('inventory_id'))
        if not is_valid:
            return jsonify({'error': item}), 404
        
        # Validate quantity
        is_valid, quantity = validate_numeric(
            data.get('quantity_used'), 'Quantity used', min_value=1
        )
        if not is_valid:
            return jsonify({'error': quantity}), 400
        
        # Validate date
        is_valid, date_result = validate_date(data.get('date_used'))
        if not is_valid:
            return jsonify({'error': date_result}), 400
        
        usage_id = record_inventory_usage(
            inventory_id=data.get('inventory_id'),
            quantity_used=int(quantity),
            date_used=date_result,
            appointment_id=data.get('appointment_id'),
            invoice_id=data.get('invoice_id'),
            notes=data.get('notes', '')
        )
        
        if not usage_id:
            return jsonify({'error': 'Insufficient inventory quantity'}), 400
        
        return jsonify({
            'message': 'Usage recorded successfully',
            'id': usage_id
        }), 201
    
    except Exception as e:
        return jsonify({'error': f'Failed to record usage: {str(e)}'}), 500


@app.route('/api/appointments/<int:appointment_id>/inventory-usage', methods=['GET'])
def api_get_appointment_usage(appointment_id):
    """Get all parts used for an appointment"""
    try:
        # Check appointment exists
        apt = get_appointment_by_id(appointment_id)
        if not apt:
            return jsonify({'error': 'Appointment not found'}), 404
        
        usage = get_usage_by_appointment(appointment_id)
        
        usage_list = []
        total_cost = 0
        
        for u in usage:
            cost = u['quantity_used'] * u['cost_per_unit']
            total_cost += cost
            
            usage_list.append({
                'id': u['id'],
                'item_name': u['item_name'],
                'sku': u['sku'],
                'quantity_used': u['quantity_used'],
                'unit': u['unit'],
                'cost_per_unit': u['cost_per_unit'],
                'total_cost': round(cost, 2),
                'date_used': u['date_used'],
                'notes': u['notes']
            })
        
        return jsonify({
            'appointment_id': appointment_id,
            'parts_used_count': len(usage_list),
            'total_parts_cost': round(total_cost, 2),
            'parts': usage_list
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve usage: {str(e)}'}), 500


@app.route('/api/invoices/<int:invoice_id>/inventory-usage', methods=['GET'])
def api_get_invoice_usage(invoice_id):
    """Get all parts used for an invoice"""
    try:
        # Check invoice exists
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        usage = get_usage_by_invoice(invoice_id)
        
        usage_list = []
        total_cost = 0
        
        for u in usage:
            cost = u['quantity_used'] * u['cost_per_unit']
            total_cost += cost
            
            usage_list.append({
                'id': u['id'],
                'item_name': u['item_name'],
                'sku': u['sku'],
                'quantity_used': u['quantity_used'],
                'unit': u['unit'],
                'cost_per_unit': u['cost_per_unit'],
                'total_cost': round(cost, 2),
                'date_used': u['date_used'],
                'notes': u['notes']
            })
        
        return jsonify({
            'invoice_id': invoice_id,
            'parts_used_count': len(usage_list),
            'total_parts_cost': round(total_cost, 2),
            'parts': usage_list
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve usage: {str(e)}'}), 500


@app.route('/api/inventory/<int:item_id>/usage-history', methods=['GET'])
def api_get_item_usage_history(item_id):
    """Get usage history for an inventory item"""
    try:
        # Check item exists
        item = get_inventory_by_id(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        usage = get_item_usage_history(item_id)
        
        usage_list = []
        total_used = 0
        
        for u in usage:
            total_used += u['quantity_used']
            usage_list.append({
                'id': u['id'],
                'quantity_used': u['quantity_used'],
                'date_used': u['date_used'],
                'appointment_id': u['appointment_id'],
                'invoice_id': u['invoice_id'],
                'notes': u['notes'],
                'created_at': u['created_at']
            })
        
        return jsonify({
            'item_id': item_id,
            'item_name': item['name'],
            'total_quantity_used': total_used,
            'usage_count': len(usage_list),
            'usage_history': usage_list
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve usage history: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)