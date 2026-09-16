# app.py
"""Yayath Spaces CRM - Flask Application."""

from flask import Flask
from config import Config
from extensions import db
from datetime import datetime, timedelta
from sqlalchemy import text


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    from routes import api_bp, web_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(web_bp)

    with app.app_context():
        db.create_all()

        # Safe schema alter for new columns (user_id_name, password, is_imported)
        try:
            db.session.execute(text("ALTER TABLE users ADD COLUMN user_id_name VARCHAR(100);"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("ALTER TABLE users ADD COLUMN password VARCHAR(255) DEFAULT 'Password@123';"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("ALTER TABLE leads ADD COLUMN is_imported BOOLEAN DEFAULT FALSE;"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("ALTER TABLE leads ADD COLUMN sunil_remarks TEXT;"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("ALTER TABLE leads ADD COLUMN telecaller_remarks TEXT;"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("ALTER TABLE leads ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE;"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("ALTER TABLE leads ADD COLUMN deleted_at DATETIME;"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("ALTER TABLE leads ADD COLUMN listing_id VARCHAR(100);"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("ALTER TABLE leads ADD COLUMN response_from VARCHAR(100);"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.execute(text("UPDATE users SET user_id_name = 'Kirti Rana', name = 'Kirti Rana', email = 'kirti@yayathspaces.com' WHERE user_id_name = 'kiriti' OR user_id_name = 'ADMIN-001' OR email = 'kiriti@yayathspaces.com';"))
            db.session.execute(text("UPDATE users SET user_id_name = 'ravi' WHERE user_id_name = 'MGR-002' OR email = 'ravi@yayathspaces.com';"))
            db.session.execute(text("UPDATE users SET user_id_name = 'neha' WHERE user_id_name = 'EDITOR-003' OR email = 'neha@yayathspaces.com';"))
            db.session.execute(text("UPDATE users SET user_id_name = 'suresh' WHERE user_id_name = 'VIEWER-004' OR email = 'suresh@yayathspaces.com';"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Auto-heal misaligned imported leads & restore exact Google Sheet dates
        try:
            import re, urllib.request, urllib.parse, csv, io
            from models import Lead

            # Fetch Sep tab CSV to build exact date map
            sheet_id = '1VfFPHNkZ3ljCx_iT-GIRMZpxqgAVP4kdZptXlR6u7qc'
            url_sep = f'https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=Sep'
            data_sep = urllib.request.urlopen(url_sep, timeout=15).read().decode('utf-8')
            reader_sep = csv.reader(io.StringIO(data_sep))
            rows_sep = list(reader_sep)

            sep_dates = {}
            for r in rows_sep[1:]:
                if len(r) > 3:
                    d_str = r[1].strip()
                    phone = r[3].strip()
                    name = r[2].strip()
                    if d_str:
                        for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
                            try:
                                dt = datetime.strptime(d_str, fmt)
                                if phone: sep_dates[phone.replace('-', '').strip()] = dt
                                if name: sep_dates[name.lower().strip()] = dt
                                break
                            except ValueError:
                                pass

            misaligned_leads = Lead.query.all()
            for l in misaligned_leads:
                if not l.name:
                    continue

                # Realign misaligned fields
                clean_num = re.sub(r'[^\d]', '', l.name)
                if len(clean_num) >= 10 and (l.name.isdigit() or l.name.startswith('91-') or clean_num in l.name.replace('-', '')):
                    real_phone = l.name.strip()
                    real_loc = l.phone.strip() if (l.phone and not re.sub(r'[^\d]', '', l.phone).isdigit()) else (l.location or '')
                    l.phone = real_phone
                    l.location = real_loc
                    l.name = f"Client {real_phone[-10:]}"
                    if l.budget and 'Himmat' in l.budget:
                        l.source = 'Himmat Data'
                        l.budget = ''

                # Restore exact date
                phone_key = (l.phone or '').replace('-', '').strip()
                name_key = (l.name or '').lower().strip()
                if phone_key in sep_dates:
                    l.created_at = sep_dates[phone_key]
                elif name_key in sep_dates:
                    l.created_at = sep_dates[name_key]
                elif l.is_imported and l.created_at.date() == datetime.utcnow().date():
                    # Default July/August leads to July 2026
                    l.created_at = datetime(2026, 7, 20)

            db.session.commit()
        except Exception as e:
            print("Auto-heal error:", e)
            db.session.rollback()

        # Auto-seed sample users (Admin, Editor, Viewer, Manager) and leads if empty
        from models import Lead, Note, FollowUp, User, Task
        if User.query.count() == 0:
            users_data = [
                User(name="Kirti Rana", email="kirti@yayathspaces.com", user_id_name="Kirti Rana", password="SuperPassword123", role="Admin"),
                User(name="Ravi Kumar", email="ravi@yayathspaces.com", user_id_name="ravi", password="Password@123", role="Manager"),
                User(name="Neha Sharma", email="neha@yayathspaces.com", user_id_name="neha", password="Password@123", role="Editor"),
                User(name="Suresh Verma", email="suresh@yayathspaces.com", user_id_name="suresh", password="Password@123", role="Viewer"),
            ]
            db.session.add_all(users_data)
            db.session.commit()

        if Lead.query.count() == 0:
            leads_data = [
                Lead(name="Rahul Sharma", email="rahul.sharma@gmail.com", phone="9876543210",
                     source="99acres", property_type="Flat/Apartment", budget="50L - 75L",
                     location="Sector 62, Noida", status="New", priority="High", assigned_to="Admin Kiriti"),
                Lead(name="Priya Gupta", email="priya.gupta@yahoo.com", phone="9123456789",
                     source="99acres", property_type="House/Villa", budget="1Cr - 1.5Cr",
                     location="DLF Phase 3, Gurgaon", status="Contacted", priority="High", assigned_to="Admin Kiriti"),
                Lead(name="Amit Verma", email="amit.verma@hotmail.com", phone="9988776655",
                     source="Direct", property_type="Plot/Land", budget="30L - 50L",
                     location="Greater Noida West", status="Qualified", priority="Medium", assigned_to="Ravi Kumar"),
                Lead(name="Sneha Patel", email="sneha.patel@gmail.com", phone="8877665544",
                     source="99acres", property_type="Flat/Apartment", budget="75L - 1Cr",
                     location="Indirapuram, Ghaziabad", status="Meeting Done", priority="Medium", assigned_to="Neha Sharma"),
                Lead(name="Vikram Singh", email="vikram.singh@outlook.com", phone="7766554433",
                     source="Direct", property_type="Office Space", budget="1.5Cr - 2Cr",
                     location="Connaught Place, Delhi", status="Proposal Sent", priority="High", assigned_to="Ravi Kumar"),
                Lead(name="Anita Mehra", email="anita.mehra@gmail.com", phone="9654321098",
                     source="99acres", property_type="Flat/Apartment", budget="40L - 60L",
                     location="Vaishali, Ghaziabad", status="Deal Close", priority="Low", assigned_to="Admin Kiriti"),
                Lead(name="Deepak Kumar", email="deepak.kumar@gmail.com", phone="9012345678",
                     source="Direct", property_type="Shop/Showroom", budget="80L - 1Cr",
                     location="Karol Bagh, Delhi", status="Lost", priority="Medium", assigned_to="Suresh Verma"),
                Lead(name="Kavita Rani", email="kavita.rani@yahoo.com", phone="8901234567",
                     source="99acres", property_type="Flat/Apartment", budget="25L - 40L",
                     location="Raj Nagar Extension, Ghaziabad", status="New", priority="High", assigned_to="Neha Sharma"),
            ]
            db.session.add_all(leads_data)
            db.session.commit()

            notes = [
                Note(lead_id=1, content="Customer is very interested in 2BHK flat near metro station."),
                Note(lead_id=1, content="Called customer, he prefers east-facing flat."),
                Note(lead_id=2, content="Looking for independent house with garden. Budget flexible."),
                Note(lead_id=3, content="Wants plot for investment purpose. Ready to visit site."),
                Note(lead_id=5, content="Needs 2000 sq ft office space. Proposal sent via email."),
            ]
            db.session.add_all(notes)
            db.session.commit()

            followups = [
                FollowUp(lead_id=1, description="Call back for site visit", scheduled_at=datetime.utcnow() + timedelta(hours=2)),
                FollowUp(lead_id=2, description="Send property brochure via WhatsApp", scheduled_at=datetime.utcnow() + timedelta(hours=5)),
                FollowUp(lead_id=4, description="Share flat options near metro", scheduled_at=datetime.utcnow() + timedelta(days=1)),
                FollowUp(lead_id=5, description="Schedule office space visit", scheduled_at=datetime.utcnow() - timedelta(hours=1)),
            ]
            db.session.add_all(followups)
            db.session.commit()

            tasks = [
                Task(title="Follow up with Vikram regarding Proposal", lead_id=5, assigned_to="Ravi Kumar", priority="High"),
                Task(title="Site visit arrangement for Rahul", lead_id=1, assigned_to="Admin Kiriti", priority="High"),
                Task(title="Send quarterly inventory sheet to Priya", lead_id=2, assigned_to="Neha Sharma", priority="Medium"),
            ]
            db.session.add_all(tasks)
            db.session.commit()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
