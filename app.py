import base64
import logging
import os
from io import BytesIO
from typing import Optional
from flask import Flask, jsonify, request, g, send_file
from flask_cors import CORS
import sqlite3
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from auth import AuthConfigError, generate_token, require_auth
from database import (
    get_all_customers, get_all_invoices, get_customer_by_id, add_customer,
    get_customer_invoices, get_invoice_by_id, init_database, update_customer,
    update_invoice_status, delete_customer, create_invoice, update_invoice,
    delete_invoice, check_customer_has_invoices, get_unpaid_invoices_total,
    add_job_photo, get_photos_by_invoice, get_photos_by_customer, delete_job_photo,
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
    get_usage_by_appointment, get_usage_by_invoice, get_item_usage_history,
    # Quote functions
    create_quote, get_all_quotes, get_quote_by_id, update_quote,
    delete_quote, check_quote_has_invoices,
    set_invoice_signature,
    USE_POSTGRES, describe_database_url, get_db_connection
)
from validators import (
    validate_phone, validate_required_fields, validate_invoice_number,
    validate_numeric, validate_status, validate_customer_id,
    # Appointment validators
    validate_date, validate_time, validate_appointment_status,
    # Inventory validators
    validate_inventory_id, validate_category, validate_unit
)

try:
    import psycopg2
    DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg2.IntegrityError)
except ImportError:
    DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError,)

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def normalize_photo_data(photo_data):
    """Ensure photo_data includes a data URI prefix."""
    if not photo_data:
        return photo_data

    trimmed = photo_data.strip()
    if trimmed.startswith('data:image/'):
        return trimmed

    if trimmed.startswith('iVBORw0KGgo'):
        mime_type = 'png'
    elif trimmed.startswith('/9j/'):
        mime_type = 'jpeg'
    else:
        mime_type = 'jpeg'

    return f'data:image/{mime_type};base64,{trimmed}'

# CORS Configuration - Allow Vercel frontend
CORS(app, origins=[
    'https://hvac-frontend-eight.vercel.app',
    'https://hvac-frontend-git-main-brianestime1s-projects.vercel.app',
    'https://hvac-frontend-skxykklys-brianestime1s-projects.vercel.app',
    'http://localhost:5173',
    'http://localhost:3000'
], supports_credentials=True)

database_backend = "PostgreSQL" if USE_POSTGRES else "SQLite"
print(f"✅ Using {database_backend} database")


def _log_database_configuration():
    logger.info("Database backend selected: %s", database_backend)
    if USE_POSTGRES:
        logger.info("DATABASE_URL detected: %s", describe_database_url())
    else:
        logger.warning("DATABASE_URL not set; using local SQLite file hvac.db")


def _check_database_connectivity():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        result = cursor.fetchone()
        conn.close()
        logger.info("Database connectivity check passed with result: %s", result)
    except Exception:
        logger.exception("Database connectivity check failed")


_log_database_configuration()
_check_database_connectivity()

init_database()


def _strip_base64_prefix(signature_data: str) -> str:
    """Remove any data URL prefix from base64 signature data."""
    if not signature_data:
        return ''
    if signature_data.startswith('data:image/png;base64,'):
        return signature_data.split(',', 1)[1]
    return signature_data


def _decode_signature(signature_data: str) -> Optional[BytesIO]:
    """Decode base64 signature data into a binary buffer for PDF embedding."""
    cleaned_signature = _strip_base64_prefix(signature_data)
    if not cleaned_signature:
        return None

    try:
        signature_buffer = BytesIO(base64.b64decode(cleaned_signature))
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid signature data: %s", exc)
        raise

    signature_buffer.seek(0)
    return signature_buffer


def _generate_invoice_pdf(invoice):
    """Create an invoice PDF that embeds the customer's signature."""
    invoice_data = dict(invoice)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = inch

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(margin, height - margin, "Invoice")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(margin, height - margin - 20, f"Invoice #: {invoice_data['invoice_number']}")
    pdf.drawString(margin, height - margin - 35, f"Date: {invoice_data['date']}")
    pdf.drawString(margin, height - margin - 50, f"Technician: {invoice_data['technician'] or 'N/A'}")

    pdf.drawString(margin, height - margin - 80, f"Customer: {invoice_data['customer_name']}")
    pdf.drawString(margin, height - margin - 95, f"Phone: {invoice_data['phone']}")
    pdf.drawString(margin, height - margin - 110, f"Address: {invoice_data['customer_address']}")

    pdf.drawString(margin, height - margin - 140, f"Work Performed: {invoice_data['work_performed']}")
    pdf.drawString(margin, height - margin - 155, f"Description: {invoice_data['description'] or 'N/A'}")

    pdf.drawString(margin, height - margin - 185, f"Subtotal: ${invoice_data['subtotal']:.2f}")
    pdf.drawString(margin, height - margin - 200, f"Tax: ${invoice_data['tax']:.2f} @ {invoice_data['tax_rate'] * 100:.2f}%")
    pdf.drawString(margin, height - margin - 215, f"Total: ${invoice_data['total']:.2f}")

    signature_buffer = _decode_signature(invoice_data['customer_signature'] or '')
    signature_section_y = margin + 120
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margin, signature_section_y + 30, "Customer Signature – Authorization to Begin Work")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(margin, signature_section_y + 10, "Signature:")

    signature_line_x = margin + 70
    signature_line_width = 200
    pdf.line(signature_line_x, signature_section_y, signature_line_x + signature_line_width, signature_section_y)

    if signature_buffer:
        image = ImageReader(signature_buffer)
        image_height = 80
        image_width = 200
        pdf.drawImage(
            image,
            signature_line_x,
            signature_section_y + 10,
            width=image_width,
            height=image_height,
            mask='auto'
        )

    authorization_text = invoice_data['authorization_status'] or ''
    signature_timestamp = invoice_data['signature_date'] or 'Not provided'
    pdf.drawString(
        margin,
        signature_section_y - 20,
        f"Authorization Status: {authorization_text} | Signed at: {signature_timestamp}"
    )

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


# ==================== AUTH ENDPOINTS ====================

@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    try:
        data = request.get_json() or {}
        password = data.get('password')

        expected_password = os.environ.get('APP_PASSWORD')
        if expected_password is None:
            return jsonify({'error': 'APP_PASSWORD environment variable is not set'}), 500

        if not password:
            return jsonify({'error': 'Password is required'}), 400

        if password != expected_password:
            return jsonify({'error': 'Invalid credentials'}), 401

        token = generate_token()
        return jsonify({'token': token})
    except AuthConfigError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 500


@app.route('/api/auth/verify', methods=['GET'])
@require_auth
def api_auth_verify():
    payload = getattr(g, 'jwt_payload', {})
    return jsonify({'valid': True, 'payload': payload})


# ==================== DASHBOARD ENDPOINT ====================

@app.route('/api/dashboard/stats', methods=['GET'])
@require_auth
def api_get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        customers = get_all_customers()
        appointments = get_all_appointments()
        low_stock = get_low_stock_items()
        unpaid_total, unpaid_count = get_unpaid_invoices_total()

        # Get upcoming appointments (today and future)
        today = datetime.now().date().isoformat()
        upcoming_appointments = [apt for apt in appointments if apt['appointment_date'] >= today and apt['status'] == 'scheduled']

        # Convert low_stock items to dictionaries
        low_stock_list = [dict(item) for item in low_stock]

        return jsonify({
            'total_customers': len(customers),
            'upcoming_appointments': len(upcoming_appointments),
            'low_stock_items': low_stock_list,
            'unpaid_total': unpaid_total,
            'unpaid_count': unpaid_count
        })
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve stats: {str(e)}'}), 500


# ==================== CUSTOMER ENDPOINTS ====================

@app.route('/api/customers', methods=['GET'])
@require_auth
def api_get_customers():
    """Get all customers"""
    try:
        customers = get_all_customers()
        customer_list = [dict(c) for c in customers]
        return jsonify(customer_list)
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve customers: {str(e)}'}), 500


@app.route('/api/customers/<int:customer_id>', methods=['GET'])
@require_auth
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
@require_auth
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
    
    except DB_INTEGRITY_ERRORS as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to create customer: {str(e)}'}), 500


@app.route('/api/customers/<int:customer_id>', methods=['PUT'])
@require_auth
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
@require_auth
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
@require_auth
def api_get_customer_invoices(customer_id):
    """Get all invoices for a customer"""
    try:
        customer = get_customer_by_id(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        invoices = get_customer_invoices(customer_id)

        invoice_list = []
        for invoice in invoices:
            invoice_list.append({
                'id': invoice['id'],
                'invoice_number': invoice['invoice_number'],
                'date': invoice['date'],
                'technician': invoice['technician'],
                'work_performed': invoice['work_performed'],
                'customer_signature': invoice['customer_signature'],
                'signature_date': invoice['signature_date'],
                'authorization_status': invoice['authorization_status'],
                'total': invoice['total'],
                'status': invoice['status']
            })
        
        return jsonify({
            'customer': {'id': customer['id'], 'name': customer['name']},
            'invoice_count': len(invoice_list),
            'invoices': invoice_list
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve invoices: {str(e)}'}), 500


@app.route('/api/customers/<int:customer_id>/photos', methods=['GET'])
@require_auth
def api_get_customer_photos(customer_id):
    """Get all job photos for a customer"""
    try:
        customer = get_customer_by_id(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        photos = get_photos_by_customer(customer_id)
        photo_list = []
        for photo in photos:
            photo_list.append({
                'id': photo['id'],
                'invoice_id': photo['invoice_id'],
                'invoice_number': photo['invoice_number'],
                'photo_data': normalize_photo_data(photo['photo_data']),
                'caption': photo['caption'],
                'created_at': photo['created_at']
            })

        return jsonify({
            'customer': {'id': customer['id'], 'name': customer['name']},
            'photo_count': len(photo_list),
            'photos': photo_list
        })

    except Exception as e:
        return jsonify({'error': f'Failed to retrieve photos: {str(e)}'}), 500


# ==================== INVOICE ENDPOINTS ====================

@app.route('/api/invoices', methods=['GET'])
@require_auth
def api_get_invoices():
    """Get all invoices"""
    try:
        invoices = get_all_invoices()

        invoice_list = []
        for invoice in invoices:
            invoice_list.append({
                'id': invoice['id'],
                'invoice_number': invoice['invoice_number'],
                'customer_id': invoice['customer_id'],
                'customer_name': invoice['customer_name'],
                'customer_phone': invoice['phone'],
                'date': invoice['date'],
                'technician': invoice['technician'],
                'work_performed': invoice['work_performed'],
                'description': invoice['description'],
                'customer_signature': invoice['customer_signature'],
                'signature_date': invoice['signature_date'],
                'authorization_status': invoice['authorization_status'],
                'labor_cost': invoice['labor_cost'],
                'materials_cost': invoice['materials_cost'],
                'tax_rate': invoice['tax_rate'],
                'subtotal': invoice['subtotal'],
                'tax': invoice['tax'],
                'total': invoice['total'],
                'status': invoice['status'],
                'created_at': invoice['created_at']
            })
        
        return jsonify(invoice_list)
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve invoices: {str(e)}'}), 500


@app.route('/api/invoices/<int:invoice_id>', methods=['GET'])
@require_auth
def api_get_invoice(invoice_id):
    """Get single invoice"""
    try:
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404

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
            'customer_signature': invoice['customer_signature'],
            'signature_date': invoice['signature_date'],
            'authorization_status': invoice['authorization_status'],
            'costs': {
                'labor': invoice['labor_cost'],
                'materials': invoice['materials_cost'],
                'subtotal': invoice['subtotal'],
                'tax_rate': invoice['tax_rate'],
                'tax': invoice['tax'],
                'total': invoice['total']
            },
            'status': invoice['status'],
            'created_at': invoice['created_at']
        })

    except Exception as e:
        return jsonify({'error': f'Failed to retrieve invoice: {str(e)}'}), 500


@app.route('/api/invoices/<int:invoice_id>/pdf', methods=['GET'])
@require_auth
def api_get_invoice_pdf(invoice_id):
    """Generate and download an invoice PDF using the latest data."""
    try:
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404

        if not invoice['customer_signature']:
            return jsonify({'error': 'Signature is required before generating a PDF'}), 400

        pdf_buffer = _generate_invoice_pdf(invoice)

        filename = f"invoice_{invoice['invoice_number']}.pdf"
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': f'Failed to generate invoice PDF: {str(e)}'}), 500


@app.route('/api/invoices', methods=['POST'])
@require_auth
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

        # Validate materials cost
        is_valid, materials_cost = validate_numeric(
            data.get('materials_cost', 0), 'Materials cost', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': materials_cost}), 400

        # Validate tax rate
        is_valid, tax_rate = validate_numeric(
            data.get('tax_rate', 0.08), 'Tax rate', min_value=0, allow_none=True
        )
        if not is_valid:
            return jsonify({'error': tax_rate}), 400

        invoice_id = create_invoice(
            customer_id=data.get('customer_id'),
            invoice_number=data.get('invoice_number'),
            date=data.get('date'),
            technician=data.get('technician'),
            work_performed=data.get('work_performed'),
            labor_cost=labor_cost,
            materials_cost=materials_cost,
            tax_rate=tax_rate,
            scheduled_time=data.get('scheduled_time', ''),
            description=data.get('description', ''),
            recommendations=data.get('recommendations', '')
        )
        
        return jsonify({
            'message': 'Invoice created successfully',
            'id': invoice_id,
            'invoice_number': data.get('invoice_number')
        }), 201
    
    except DB_INTEGRITY_ERRORS as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to create invoice: {str(e)}'}), 500


@app.route('/api/invoices/<int:invoice_id>', methods=['PUT'])
@require_auth
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
    
    except DB_INTEGRITY_ERRORS as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to update invoice: {str(e)}'}), 500


@app.route('/api/invoices/<int:invoice_id>', methods=['DELETE'])
@require_auth
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
@require_auth
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


@app.route('/api/invoices/<int:invoice_id>/status', methods=['PATCH'])
@require_auth
def api_patch_invoice_status(invoice_id):
    """Update invoice status with optional payment details"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400

        new_status = data.get('status')
        valid_statuses = ['draft', 'sent', 'paid']
        is_valid, error = validate_status(new_status, valid_statuses)
        if not is_valid:
            return jsonify({'error': error}), 400

        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404

        paid_date = data.get('paid_date')
        payment_method = data.get('payment_method')

        update_invoice_status(invoice_id, new_status, paid_date, payment_method)

        response = {
            'message': 'Status updated successfully',
            'invoice_number': invoice['invoice_number'],
            'old_status': invoice['status'],
            'new_status': new_status
        }
        if new_status == 'paid':
            response['paid_date'] = paid_date
            response['payment_method'] = payment_method

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': f'Failed to update status: {str(e)}'}), 500


@app.route('/api/invoices/<int:invoice_id>/signature', methods=['POST'])
@require_auth
def api_save_invoice_signature(invoice_id):
    """Save base64-encoded customer signature for an invoice"""
    try:
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404

        if not request.is_json:
            return jsonify({'error': 'Request must be JSON with a signature field'}), 400

        data = request.get_json(silent=True) or {}
        signature = data.get('signature')
        if not signature:
            return jsonify({'error': 'Signature field is missing'}), 400

        signature_date = datetime.utcnow().isoformat()
        authorization_status = data.get('authorization_status', 'signed')

        success = set_invoice_signature(invoice_id, signature, signature_date, authorization_status)
        if not success:
            return jsonify({'error': 'Failed to save signature'}), 500

        return jsonify({
            'message': 'Signature saved successfully',
            'invoice_number': invoice['invoice_number'],
            'signature_date': signature_date,
            'authorization_status': authorization_status
        }), 200

    except Exception as e:
        return jsonify({'error': f'Failed to save signature: {str(e)}'}), 500


@app.route('/api/invoices/<int:invoice_id>/photos', methods=['POST'])
@require_auth
def api_add_job_photo(invoice_id):
    """Upload a job photo for an invoice"""
    try:
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404

        if not request.is_json:
            return jsonify({'error': 'Request must be JSON with photo_data'}), 400

        data = request.get_json(silent=True) or {}
        photo_data = data.get('photo_data')
        if not photo_data:
            return jsonify({'error': 'photo_data is required'}), 400

        caption = data.get('caption')
        normalized_photo_data = normalize_photo_data(photo_data)
        photo_id = add_job_photo(invoice_id, normalized_photo_data, caption)

        return jsonify({
            'message': 'Photo uploaded successfully',
            'id': photo_id,
            'invoice_id': invoice_id
        }), 201

    except Exception as e:
        return jsonify({'error': f'Failed to upload photo: {str(e)}'}), 500


@app.route('/api/invoices/<int:invoice_id>/photos', methods=['GET'])
@require_auth
def api_get_job_photos(invoice_id):
    """List all job photos for an invoice"""
    try:
        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404

        photos = get_photos_by_invoice(invoice_id)
        photo_list = []
        for photo in photos:
            photo_list.append({
                'id': photo['id'],
                'invoice_id': photo['invoice_id'],
                'photo_data': normalize_photo_data(photo['photo_data']),
                'caption': photo['caption'],
                'created_at': photo['created_at']
            })

        return jsonify(photo_list)

    except Exception as e:
        return jsonify({'error': f'Failed to retrieve photos: {str(e)}'}), 500


@app.route('/api/photos/<int:photo_id>', methods=['DELETE'])
@require_auth
def api_delete_job_photo(photo_id):
    """Delete a job photo"""
    try:
        deleted = delete_job_photo(photo_id)
        if not deleted:
            return jsonify({'error': 'Photo not found'}), 404

        return jsonify({
            'message': 'Photo deleted successfully',
            'id': photo_id
        })

    except Exception as e:
        return jsonify({'error': f'Failed to delete photo: {str(e)}'}), 500
@app.route('/api/invoices/<int:invoice_id>/photos/<int:photo_id>', methods=['DELETE'])
@require_auth
def api_delete_invoice_photo(invoice_id, photo_id):
    """Delete a job photo (alternate route)"""
    try:
        deleted = delete_job_photo(photo_id)
        if not deleted:
            return jsonify({'error': 'Photo not found'}), 404

        return jsonify({
            'message': 'Photo deleted successfully',
            'id': photo_id
        })

    except Exception as e:
        return jsonify({'error': f'Failed to delete photo: {str(e)}'}), 500


# ==================== QUOTE ENDPOINTS ====================

@app.route('/api/quotes', methods=['GET'])
@require_auth
def api_get_quotes():
    """Get all quotes"""
    try:
        quotes = get_all_quotes()
        quote_list = []
        for quote in quotes:
            quote_list.append({
                'id': quote['id'],
                'customer_id': quote['customer_id'],
                'customer_name': quote['customer_name'],
                'title': quote['title'],
                'description': quote['description'],
                'total': quote['total'],
                'status': quote['status'],
                'created_at': quote['created_at'],
                'updated_at': quote['updated_at']
            })

        return jsonify(quote_list)

    except Exception as e:
        return jsonify({'error': f'Failed to retrieve quotes: {str(e)}'}), 500


@app.route('/api/quotes/<int:quote_id>', methods=['GET'])
@require_auth
def api_get_quote(quote_id):
    """Get single quote"""
    try:
        quote = get_quote_by_id(quote_id)
        if not quote:
            return jsonify({'error': 'Quote not found'}), 404

        return jsonify({
            'id': quote['id'],
            'customer': {
                'id': quote['customer_id'],
                'name': quote['customer_name']
            },
            'title': quote['title'],
            'description': quote['description'],
            'total': quote['total'],
            'status': quote['status'],
            'created_at': quote['created_at'],
            'updated_at': quote['updated_at']
        })

    except Exception as e:
        return jsonify({'error': f'Failed to retrieve quote: {str(e)}'}), 500


@app.route('/api/quotes', methods=['POST'])
@require_auth
def api_create_quote():
    """Create new quote"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400

        # Validate required fields
        is_valid, error = validate_required_fields(data, ['customer_id', 'title'])
        if not is_valid:
            return jsonify({'error': error}), 400

        # Validate customer exists
        is_valid, customer_result = validate_customer_id(data.get('customer_id'))
        if not is_valid:
            return jsonify({'error': customer_result}), 404

        # Validate total
        is_valid, total_value = validate_numeric(
            data.get('total'), 'Total', min_value=0, allow_none=False
        )
        if not is_valid:
            return jsonify({'error': total_value}), 400

        # Validate status
        status = data.get('status', 'draft') or 'draft'
        valid_statuses = ['draft', 'sent', 'accepted', 'rejected']
        is_valid, status_error = validate_status(status, valid_statuses)
        if not is_valid:
            return jsonify({'error': status_error}), 400

        title = data.get('title', '').strip()
        description = data.get('description', '').strip()

        if not title:
            return jsonify({'error': 'Title cannot be empty'}), 400

        quote_id = create_quote(
            customer_id=customer_result['id'],
            title=title,
            description=description,
            total=total_value,
            status=status
        )

        return jsonify({
            'message': 'Quote created successfully',
            'id': quote_id,
            'status': status
        }), 201

    except DB_INTEGRITY_ERRORS as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to create quote: {str(e)}'}), 500


@app.route('/api/quotes/<int:quote_id>', methods=['PUT'])
@require_auth
def api_update_quote(quote_id):
    """Update quote"""
    try:
        quote = get_quote_by_id(quote_id)
        if not quote:
            return jsonify({'error': 'Quote not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400

        title = data.get('title', quote['title']).strip()
        description = data.get('description', quote['description'] or '').strip()

        # Validate total
        total_input = data.get('total', quote['total'])
        is_valid, total_value = validate_numeric(
            total_input, 'Total', min_value=0, allow_none=False
        )
        if not is_valid:
            return jsonify({'error': total_value}), 400

        # Validate status
        status = data.get('status', quote['status'])
        valid_statuses = ['draft', 'sent', 'accepted', 'rejected']
        is_valid, status_error = validate_status(status, valid_statuses)
        if not is_valid:
            return jsonify({'error': status_error}), 400

        if not title:
            return jsonify({'error': 'Title cannot be empty'}), 400

        success = update_quote(
            quote_id=quote_id,
            title=title,
            description=description,
            total=total_value,
            status=status
        )

        if success:
            return jsonify({'message': 'Quote updated successfully', 'id': quote_id})
        return jsonify({'error': 'Failed to update quote'}), 500

    except DB_INTEGRITY_ERRORS as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to update quote: {str(e)}'}), 500


@app.route('/api/quotes/<int:quote_id>', methods=['DELETE'])
@require_auth
def api_delete_quote(quote_id):
    """Delete quote (only if no linked invoices)"""
    try:
        quote = get_quote_by_id(quote_id)
        if not quote:
            return jsonify({'error': 'Quote not found'}), 404

        if check_quote_has_invoices(quote_id):
            return jsonify({
                'error': 'Cannot delete quote with existing invoices',
                'suggestion': 'Remove or update linked invoices first'
            }), 409

        delete_quote(quote_id)

        return jsonify({
            'message': 'Quote deleted successfully',
            'id': quote_id
        })

    except Exception as e:
        return jsonify({'error': f'Failed to delete quote: {str(e)}'}), 500


# ==================== APPOINTMENT ENDPOINTS ====================

@app.route('/api/appointments', methods=['GET'])
@require_auth
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
@require_auth
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
@require_auth
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
        logger.exception("Failed to create appointment")
        return jsonify({'error': f'Failed to create appointment: {str(e)}'}), 500


@app.route('/api/appointments/<int:appointment_id>', methods=['PUT'])
@require_auth
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
@require_auth
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
@require_auth
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
@require_auth
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
@require_auth
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
@require_auth
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
@require_auth
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
@require_auth
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
@require_auth
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
@require_auth
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
        
        # Normalize and validate category
        raw_category = (data.get('category') or '').strip().lower()
        is_valid, category = validate_category(raw_category)
        if not is_valid:
            return jsonify({'error': category}), 400
        
        # Validate unit (default to 'ea' if not provided)
        unit_value = data.get('unit', 'ea')
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
    
    except DB_INTEGRITY_ERRORS as e:
        return jsonify({'error': f'Database error (SKU may already exist): {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to create item: {str(e)}'}), 500


@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
@require_auth
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
        
        # Normalize and validate category
        raw_category = (data.get('category') or '').strip().lower()
        is_valid, category = validate_category(raw_category)
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
    
    except DB_INTEGRITY_ERRORS as e:
        return jsonify({'error': f'Database error (SKU may already exist): {str(e)}'}), 409
    except Exception as e:
        return jsonify({'error': f'Failed to update item: {str(e)}'}), 500


@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
@require_auth
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
@require_auth
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
@require_auth
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
@require_auth
def api_get_inventory_by_category(category):
    """Get all items in a category"""
    try:
        # Normalize and validate category from URL
        raw_category = (category or '').strip().lower()
        is_valid, validated_category = validate_category(raw_category)
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
@require_auth
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
@require_auth
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
@require_auth
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
@require_auth
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
@require_auth
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
@require_auth
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
