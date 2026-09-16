# models.py
"""SQLAlchemy models for Yayath 99Acres CRM."""

from extensions import db
from datetime import datetime


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    role = db.Column(db.String(50), nullable=False, default='Sales Executive')  # Admin, Manager, Sales Executive
    status = db.Column(db.String(20), nullable=False, default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d') if self.created_at else ''
        }


class Lead(db.Model):
    __tablename__ = 'leads'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    source = db.Column(db.String(100), nullable=True, default='99acres')
    property_type = db.Column(db.String(100), nullable=True)
    budget = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), nullable=False, default='New')  
    # Statuses: New, Contacted, Qualified, Meeting Done, Proposal Sent, Active Pipeline, Deal Close, Lost
    priority = db.Column(db.String(20), nullable=False, default='Medium')
    assigned_to = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    notes = db.relationship('Note', backref='lead', lazy=True, cascade='all, delete-orphan')
    followups = db.relationship('FollowUp', backref='lead', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='lead', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'source': self.source,
            'property_type': self.property_type,
            'budget': self.budget,
            'location': self.location,
            'status': self.status,
            'priority': self.priority,
            'assigned_to': self.assigned_to,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'created_date': self.created_at.strftime('%Y-%m-%d') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
        }


class Note(db.Model):
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FollowUp(db.Model):
    __tablename__ = 'followups'

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(500), nullable=True)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=True)
    assigned_to = db.Column(db.String(255), nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.String(20), default='Medium')
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
