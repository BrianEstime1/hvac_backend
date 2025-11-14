from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Customers(db.Model):
    __tablename__ = 'customers'

    customer_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100))      # ← Capital S
    last_name = db.Column(db.String(100))       # ← Capital S
    email = db.Column(db.String(100))           # ← Capital S
    phone = db.Column(db.String(15))            # ← Capital S
    address = db.Column(db.Text)                # ← Capital T (not db.text)
    created_at = db.Column(db.DateTime, default=db.func.now())  # ← DateTime

    def to_dict(self):
        return {
            'customer_id': self.customer_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }