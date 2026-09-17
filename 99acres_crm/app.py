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

        # Auto-heal: Purge misaligned legacy leads so they are auto-refreshed cleanly
        try:
            from models import Lead, Note, FollowUp
            corrupted_count = Lead.query.filter(
                (Lead.listing_id.like('%Market%')) | 
                (Lead.listing_id.like('%Rent%')) | 
                (Lead.listing_id.like('%Sale%')) | 
                (Lead.listing_id.like('%Shop%')) |
                (Lead.name.like('Client %') & Lead.source.like('%Himmat%'))
            ).count()

            if corrupted_count > 0 or Lead.query.count() <= 10:
                Note.query.delete(synchronize_session=False)
                FollowUp.query.delete(synchronize_session=False)
                Lead.query.delete(synchronize_session=False)
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

        # Auto-sync Google Sheet leads on startup if empty
        if Lead.query.count() == 0:
            try:
                import urllib.request, urllib.parse, csv, io, re
                sheet_gids = [
                    {'name': 'July - Aug', 'gid': '0'},
                    {'name': 'Interested client', 'gid': '937006042'}
                ]
                sheet_id = '1VfFPHNkZ3ljCx_iT-GIRMZpxqgAVP4kdZptXlR6u7qc'

                for item in sheet_gids:
                    tab_name = item['name']
                    gid = item['gid']
                    url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}'
                    csv_bytes = urllib.request.urlopen(url, timeout=30).read()
                    csv_text = csv_bytes.decode('utf-8', errors='ignore')
                    reader = csv.reader(io.StringIO(csv_text))
                    rows = list(reader)
                    if not rows or len(rows) < 2:
                        continue

                    if gid == '937006042':
                        # Interested Client tab: S NO (0) | NAME (1) | NUMBER (2) | Loction (3) | BUDGET (4) | Requirement (5) | Remarks (6)
                        start_idx = 0
                        for idx, r in enumerate(rows):
                            if r and len(r) > 1 and ('S NO' in r[0] or 'NAME' in r[1] or 'NUMBER' in r[2]):
                                start_idx = idx
                                break

                        for r in rows[start_idx + 1:]:
                            if not r or len(r) < 3:
                                continue
                            raw_name = r[1].strip() if len(r) > 1 else ''
                            phone = r[2].strip() if len(r) > 2 else ''
                            if not raw_name and not phone:
                                continue

                            clean_name_num = re.sub(r'[^\d]', '', raw_name)
                            if not raw_name or (len(clean_name_num) >= 10 and raw_name.isdigit()):
                                name = f"Client {phone[-10:]}" if phone else "Client"
                            else:
                                name = raw_name

                            location = r[3].strip() if len(r) > 3 else ''
                            budget = r[4].strip() if len(r) > 4 else ''        # Price of Property
                            requirement = r[5].strip() if len(r) > 5 else ''   # Property Type / Specs
                            remarks = r[6].strip() if len(r) > 6 else ''       # Sunil Remarks

                            rem_lower = remarks.lower()
                            req_lower = requirement.lower()

                            if 'sunil' in rem_lower or 'sunil' in req_lower:
                                source_val = 'Sunil Data'
                            elif 'himmat' in rem_lower or 'himmat' in req_lower:
                                source_val = 'Himmat Data'
                            else:
                                source_val = '99acres'
                            status = 'Contacted'
                            if 'proposal' in rem_lower or 'proposal' in req_lower:
                                status = 'Proposal Sent'
                            elif 'visit' in rem_lower or 'site' in rem_lower:
                                status = 'Meeting Done'
                            elif 'hot' in rem_lower or 'hot' in req_lower:
                                status = 'Qualified'

                            priority = 'High' if ('hot' in rem_lower or 'hot' in req_lower or 'urgent' in req_lower) else 'Medium'

                            clean_name = name.lower().replace(' ', '.').replace('/', '')
                            email = f"{clean_name}@lead99.com"

                            lead = Lead(
                                name=name, email=email, phone=phone, source=source_val,
                                listing_id='',
                                property_type=requirement or 'Office Space', budget=budget,
                                location=location, status=status, priority=priority,
                                assigned_to='Admin Kiriti', is_imported=True,
                                sunil_remarks=remarks, created_at=datetime.utcnow()
                            )
                            db.session.add(lead)
                        continue

                    # Standard July-Aug Response tab
                    start_idx = 0
                    for idx, r in enumerate(rows):
                        if r and len(r) > 1 and ('S No' in r[0] or 'Date' in r[1] or 'Name' in r[2]):
                            start_idx = idx
                            break

                    for r in rows[start_idx + 1:]:
                        if not r or len(r) < 3:
                            continue

                        col2 = r[2].strip() if len(r) > 2 else ''
                        col3 = r[3].strip() if len(r) > 3 else ''
                        if not col2 or col2 in ('-', '', 'Name'):
                            continue

                        date_str = r[1].strip() if len(r) > 1 else ''
                        clean_col2 = re.sub(r'[^\d]', '', col2)

                        if len(clean_col2) >= 10 and (col2.isdigit() or col2.startswith('91-') or clean_col2 in col2.replace('-', '')):
                            phone = col2
                            location = col3
                            name = f"Client {clean_col2[-10:]}"
                        else:
                            name = col2
                            phone = col3
                            locality = r[7].strip() if len(r) > 7 else ''
                            project = r[8].strip() if len(r) > 8 else ''
                            location = f"{locality} ({project})" if (project and project != '-') else locality

                        listing_id = r[4].strip() if len(r) > 4 else ''
                        property_type = r[5].strip() if len(r) > 5 else ''
                        raw_budget = r[6].strip() if len(r) > 6 else ''
                        budget = '' if ('Himmat' in raw_budget or 'Sunil' in raw_budget) else raw_budget
                        response_from = r[9].strip() if len(r) > 9 else ''
                        sunil_remarks = r[10].strip() if len(r) > 10 else ''
                        telecaller_col = r[11].strip() if len(r) > 11 else ''

                        r_text = ' '.join(r).lower()
                        if 'sunil' in telecaller_col.lower() or 'sunil' in raw_budget.lower() or 'sunil data' in r_text:
                            source_val = 'Sunil Data'
                        elif 'himmat' in raw_budget or 'himmat' in r_text:
                            source_val = 'Himmat Data'
                        else:
                            source_val = '99acres'

                        created_at = None
                        if date_str:
                            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y']:
                                try:
                                    created_at = datetime.strptime(date_str, fmt)
                                    break
                                except ValueError:
                                    pass

                        if not created_at:
                            created_at = datetime(2026, 7, 20)

                        clean_name = name.lower().replace(' ', '.').replace('/', '')
                        email = f"{clean_name}@lead99.com"

                        lead = Lead(
                            name=name, email=email, phone=phone, source=source_val,
                            property_type=property_type or 'Office Space', budget=budget,
                            location=location, status='New', priority='Medium',
                            assigned_to='Admin Kiriti', is_imported=True,
                            sunil_remarks=sunil_remarks if sunil_remarks and sunil_remarks != 'NA' else '',
                            telecaller_remarks=telecaller_col if telecaller_col and telecaller_col != 'NA' else '',
                            listing_id=listing_id, response_from=response_from,
                            created_at=created_at
                        )
                        db.session.add(lead)
                db.session.commit()
            except Exception as e:
                print("Auto sync on startup error:", e)
                db.session.rollback()

        if Lead.query.count() == 0:
            leads_data = [
                Lead(name="Rahul Sharma", email="rahul.sharma@gmail.com", phone="9876543210",
                     source="99acres", property_type="Flat/Apartment", budget="50L - 75L",
                     location="Sector 62, Noida", status="New", priority="High", assigned_to="Admin Kiriti"),
                Lead(name="Priya Gupta", email="priya.gupta@yahoo.com", phone="9123456789",
                     source="99acres", property_type="House/Villa", budget="1Cr - 1.5Cr",
                     location="DLF Phase 3, Gurgaon", status="Contacted", priority="High", assigned_to="Admin Kiriti"),
                Lead(name="Amit Verma", email="amit.verma@hotmail.com", phone="9988776655",
                     source="99acres", property_type="Plot/Land", budget="30L - 50L",
                     location="Greater Noida West", status="Qualified", priority="Medium", assigned_to="Ravi Kumar"),
                Lead(name="Sneha Patel", email="sneha.patel@gmail.com", phone="8877665544",
                     source="99acres", property_type="Flat/Apartment", budget="75L - 1Cr",
                     location="Indirapuram, Ghaziabad", status="Meeting Done", priority="Medium", assigned_to="Neha Sharma"),
                Lead(name="Vikram Singh", email="vikram.singh@outlook.com", phone="7766554433",
                     source="99acres", property_type="Office Space", budget="1.5Cr - 2Cr",
                     location="Connaught Place, Delhi", status="Proposal Sent", priority="High", assigned_to="Ravi Kumar"),
                Lead(name="Anita Mehra", email="anita.mehra@gmail.com", phone="9654321098",
                     source="99acres", property_type="Flat/Apartment", budget="40L - 60L",
                     location="Vaishali, Ghaziabad", status="Deal Close", priority="Low", assigned_to="Admin Kiriti"),
                Lead(name="Deepak Kumar", email="deepak.kumar@gmail.com", phone="9012345678",
                     source="99acres", property_type="Shop/Showroom", budget="80L - 1Cr",
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
