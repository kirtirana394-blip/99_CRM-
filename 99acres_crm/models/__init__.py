from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="sales", nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Lead(db.Model):
    __tablename__ = "leads"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    client_name = db.Column(db.String(255), nullable=False)
    company_name = db.Column(db.String(255))
    phone = db.Column(db.String(50), index=True)
    alternate_phone = db.Column(db.String(50))
    email = db.Column(db.String(255), index=True)
    property_name = db.Column(db.String(255))
    property_type = db.Column(db.String(100))
    location = db.Column(db.String(255))
    requirement = db.Column(db.Text)
    budget = db.Column(db.String(100))
    area_required = db.Column(db.String(100))
    source = db.Column(db.String(100), default="99Acres", index=True)
    source_reference = db.Column(db.String(255), index=True)
    lead_status = db.Column(db.String(50), default="New Lead", index=True)
    lead_stage = db.Column(db.String(50), default="New Lead")
    priority = db.Column(db.String(20), default="Medium")
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    lead_date = db.Column(db.DateTime, default=datetime.utcnow)
    first_contact_date = db.Column(db.DateTime)
    next_followup_date = db.Column(db.DateTime, index=True)
    meeting_date = db.Column(db.DateTime)
    proposal_date = db.Column(db.DateTime)
    deal_date = db.Column(db.DateTime)
    deal_value = db.Column(db.Float, default=0)
    lost_reason = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    assignee = db.relationship("User", backref="leads")

class FollowUp(db.Model):
    __tablename__ = "followups"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    followup_at = db.Column(db.DateTime, nullable=False, index=True)
    activity_type = db.Column(db.String(50), default="Follow-up")
    notes = db.Column(db.Text)
    reminder = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default="Pending")
    completed_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lead = db.relationship("Lead", backref=db.backref("followups", cascade="all, delete-orphan"))
    assigned_user = db.relationship("User", foreign_keys=[assigned_user_id])

class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"))
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    due_date = db.Column(db.DateTime)
    priority = db.Column(db.String(20), default="Medium")
    status = db.Column(db.String(30), default="Pending")
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lead = db.relationship("Lead", backref="tasks")

class Note(db.Model):
    __tablename__ = "notes"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    note_text = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lead = db.relationship("Lead", backref=db.backref("notes_list", cascade="all, delete-orphan"))

class Meeting(db.Model):
    __tablename__ = "meetings"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    meeting_at = db.Column(db.DateTime, nullable=False)
    meeting_type = db.Column(db.String(50), default="Meeting")
    location = db.Column(db.String(255))
    participants = db.Column(db.Text)
    notes = db.Column(db.Text)
    status = db.Column(db.String(30), default="Scheduled")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lead = db.relationship("Lead", backref=db.backref("meetings", cascade="all, delete-orphan"))

class Proposal(db.Model):
    __tablename__ = "proposals"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    proposal_date = db.Column(db.DateTime, default=datetime.utcnow)
    proposal_value = db.Column(db.Float, default=0)
    proposal_status = db.Column(db.String(40), default="Draft")
    followup_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    lead = db.relationship("Lead", backref=db.backref("proposals", cascade="all, delete-orphan"))

class Deal(db.Model):
    __tablename__ = "deals"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    deal_date = db.Column(db.DateTime, nullable=False)
    deal_value = db.Column(db.Float, nullable=False)
    property_name = db.Column(db.String(255))
    client_name = db.Column(db.String(255))
    salesperson_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lead = db.relationship("Lead", backref=db.backref("deals", cascade="all, delete-orphan"))

class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class StageHistory(db.Model):
    __tablename__ = "stage_history"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    old_stage = db.Column(db.String(50))
    new_stage = db.Column(db.String(50), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    lead = db.relationship("Lead", backref=db.backref("stage_history", cascade="all, delete-orphan"))

class ImportHistory(db.Model):
    __tablename__ = "import_history"
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    total_records = db.Column(db.Integer, default=0)
    imported_records = db.Column(db.Integer, default=0)
    duplicate_records = db.Column(db.Integer, default=0)
    invalid_records = db.Column(db.Integer, default=0)
