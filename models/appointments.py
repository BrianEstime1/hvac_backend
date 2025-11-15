from .customer import db, Customers

class Appointments(db.Model):
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(
        db.Integer,
        db.ForeignKey('customers.customer_id'),
        nullable=False
    )
    date = db.Column(db.DateTime, nullable=False)
    time = db.Column(db.String(50), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='scheduled')
    created_at = db.Column(db.DateTime, default=db.func.now())

# access customer name directly
    customer = db.relationship('Customers', backref='appointments')

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'customer_name': f"{self.customer.first_name} {self.customer.last_name}" if self.customer else None,
            'date': self.date.isoformat() if self.date else None,
            'time': self.time,
            'service_type': self.service_type,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
