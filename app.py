from flask import Flask, request, jsonify
from models.customer import db, Customers 
import re
from models.appointments import Appointments

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///customers.db'  
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# create db 
with app.app_context():
    db.create_all()
    with app.app_context():
        db.create_all() #now creates appointments

# phone validation 
def validate_phone(phone):
    return bool(re.match(r'^\+?1?\d{9,15}$', phone))

# get all 
@app.route('/customers', methods=['GET'])
def get_customers():
    customers = Customers.query.all()
    return jsonify([c.to_dict() for c in customers]), 200 

# post
@app.route('/customers', methods=['POST'])
def create_customer():
    data = request.get_json()
    required = ['first_name', 'last_name', 'phone']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    if not validate_phone(data['phone']):
        return jsonify({'error': 'Invalid phone number format'}), 400
    
    customer = Customers(**data)  # ← Changed to Customers
    db.session.add(customer)
    db.session.commit()
    return jsonify(customer.to_dict()), 201

# get one 
@app.route('/customers/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    c = Customers.query.get_or_404(customer_id)  # ← Changed to Customers
    return jsonify(c.to_dict())

# put 
@app.route('/customers/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    c = Customers.query.get_or_404(customer_id)  # ← Changed to Customers
    data = request.get_json()
    if 'phone' in data and not validate_phone(data['phone']):
        return jsonify({'error': 'Invalid phone number format'}), 400
    for key, value in data.items():
        setattr(c, key, value)
    db.session.commit()
    return jsonify(c.to_dict())

# delete
@app.route('/customers/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    c = Customers.query.get_or_404(customer_id)  # ← Changed to Customers
    db.session.delete(c)
    db.session.commit()
    return '', 204

@app.route('/appointments', methods=['GET'])
def get_appointments():
    appointments = Appointments.query.all()
    return jsonify([a.to_dict() for a in appointments]), 200

@app.route('/appointments', methods=['POST'])
def create_appointment():
    data = request.get_json()
    required = ['customer_id', 'date', 'time', 'service_type']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    appointment = Appointments(**data)
    db.session.add(appointment)
    db.session.commit()
    return jsonify(appointment.to_dict()), 201

if __name__ == '__main__':
    app.run(debug=True , port=5002)