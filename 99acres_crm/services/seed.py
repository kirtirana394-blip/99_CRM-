import os
from models import db, User, Lead
from services.auth import set_password

def seed_local_admin():
    if User.query.first():
        return
    username = os.getenv("ADMIN_USERNAME","admin")
    email = os.getenv("ADMIN_EMAIL","admin@example.com")
    password = os.getenv("ADMIN_PASSWORD","ChangeMe123!")
    user = User(username=username, email=email, role="admin", active=True)
    set_password(user, password)
    db.session.add(user)
    db.session.flush()
    samples = [
        Lead(lead_id="DEMO-001", client_name="Rahul Sharma", company_name="Demo Realty",
             phone="9876543210", email="rahul@example.com", location="Gurugram",
             requirement="Managed office space", budget="₹20L", area_required="2500 sq ft",
             source="99Acres", priority="High", assigned_to=user.id),
        Lead(lead_id="DEMO-002", client_name="Neha Kapoor", company_name="Kapoor Ventures",
             phone="9811111111", email="neha@example.com", location="Gurugram",
             requirement="Private office", budget="₹12L", area_required="1500 sq ft",
             source="99Acres", priority="Medium", assigned_to=user.id),
    ]
    db.session.add_all(samples)
    db.session.commit()
