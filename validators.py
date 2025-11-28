"""
Validation functions for HVAC API
All validators return (is_valid, result_or_error_message)
"""
import logging
import re
from datetime import datetime

from database import get_db_connection

logger = logging.getLogger(__name__)

def validate_phone(phone):
    """Validate and format phone number to (555) 123-4567 format"""
    if not phone:
        return False, "Phone number is required"
    
    # Remove all non-digit characters
    cleaned = re.sub(r'[^\d]', '', phone)
    
    # Must be exactly 10 digits
    if len(cleaned) != 10:
        return False, "Phone must be 10 digits (e.g., 5551234567)"
    
    # Format as (555) 123-4567
    formatted = f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
    return True, formatted


def validate_required_fields(data, required_fields):
    """Check if all required fields are present and not empty"""
    missing = []
    for field in required_fields:
        if field not in data or not data[field]:
            missing.append(field)
    
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    return True, None


def validate_invoice_number(invoice_number, exclude_id=None):
    """Check if invoice number already exists (exclude_id used for updates)"""
    if not invoice_number:
        return False, "Invoice number is required"
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if exclude_id:
            cursor.execute(
                'SELECT id FROM invoices WHERE invoice_number = ? AND id != ?',
                (invoice_number, exclude_id)
            )
        else:
            cursor.execute(
                'SELECT id FROM invoices WHERE invoice_number = ?',
                (invoice_number,)
            )

        exists = cursor.fetchone()

        if exists:
            return False, f"Invoice number '{invoice_number}' already exists"
        return True, None
    except Exception:
        logger.exception("Invoice number validation failed")
        return False, "Error validating invoice number"
    finally:
        conn.close()


def validate_numeric(value, field_name, min_value=0, allow_none=False):
    """Validate that a value is a valid number >= min_value"""
    if value is None:
        if allow_none:
            return True, 0
        return False, f"{field_name} is required"
    
    try:
        num = float(value)
        if num < min_value:
            return False, f"{field_name} must be at least {min_value}"
        return True, num
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid number"


def validate_status(status, valid_statuses):
    """Validate that status is one of the allowed values"""
    if status not in valid_statuses:
        return False, f"Status must be one of: {', '.join(valid_statuses)}"
    return True, None


def validate_customer_id(customer_id):
    """Check if customer exists in database"""
    if not customer_id:
        return False, "Customer ID is required"
    
    try:
        customer_id = int(customer_id)
    except (ValueError, TypeError):
        return False, "Customer ID must be a valid integer"
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        customer = cursor.fetchone()

        if not customer:
            return False, f"Customer with ID {customer_id} not found"

        return True, customer
    except Exception:
        logger.exception("Failed to validate customer ID %s", customer_id)
        return False, f"Customer with ID {customer_id} not found"
    finally:
        conn.close()


def validate_date(date_string):
    """Validate date format (YYYY-MM-DD)"""
    if not date_string:
        return False, "Date is required"
    
    # Basic format check - exactly YYYY-MM-DD
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(pattern, date_string):
        return False, "Date must be in format YYYY-MM-DD (e.g., 2025-01-15)"
    
    # Check if valid date
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True, date_string
    except ValueError:
        return False, "Invalid date (e.g., month cannot be 13)"


def validate_time(time_string):
    """Validate time format (HH:MM AM/PM or HH:MM)"""
    if not time_string:
        return False, "Time is required"
    
    # Accept formats like "10:00 AM", "14:00", "2:30 PM"
    time_string = time_string.strip()
    
    # Just check it's not empty and has reasonable format
    if ':' not in time_string:
        return False, "Time must include ':' (e.g., 10:00 AM or 14:00)"
    
    return True, time_string


def validate_appointment_status(status):
    """Validate appointment status"""
    valid_statuses = ['scheduled', 'in-progress', 'completed', 'cancelled']
    if status not in valid_statuses:
        return False, f"Status must be one of: {', '.join(valid_statuses)}"
    return True, None


def validate_inventory_id(inventory_id):
    """Check if inventory item exists"""
    if not inventory_id:
        return False, "Inventory ID is required"
    
    try:
        inventory_id = int(inventory_id)
    except (ValueError, TypeError):
        return False, "Inventory ID must be a valid integer"
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM inventory WHERE id = ?', (inventory_id,))
        item = cursor.fetchone()

        if not item:
            return False, f"Inventory item with ID {inventory_id} not found"

        return True, item
    except Exception:
        logger.exception("Failed to validate inventory ID %s", inventory_id)
        return False, f"Inventory item with ID {inventory_id} not found"
    finally:
        conn.close()


def validate_category(value):
    """Validate inventory category - case-insensitive and whitespace-tolerant"""
    if value is None or value == '':
        return False, "Category is required"
    
    # Normalize: trim whitespace and convert to lowercase
    category = str(value).strip().lower()
    
    valid_categories = ['parts', 'tools', 'refrigerant', 'supplies', 'equipment', 'other']
    
    if category not in valid_categories:
        return False, f"Category must be one of: {', '.join(valid_categories)}"
    
    return True, category


def validate_unit(unit):
    """Validate unit of measurement"""
    if not unit:
        return False, "Unit is required"
    
    valid_units = ['ea', 'lbs', 'oz', 'gal', 'ft', 'box', 'case', 'roll', 'set']
    unit_lower = unit.lower()
    
    if unit_lower not in valid_units:
        return False, f"Unit must be one of: {', '.join(valid_units)}"
    
    return True, unit_lower
