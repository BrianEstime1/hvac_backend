import base64
import logging
import os
import secrets
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
import stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
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
    get_quote_by_signing_token, set_quote_signing_token, set_quote_signature,
    set_invoice_signature,
    get_setting, set_setting,
    get_invoice_by_signing_token, set_invoice_signing_token,
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