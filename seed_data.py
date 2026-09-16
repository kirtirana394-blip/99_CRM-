# seed_data.py
"""Insert sample leads into the CRM database."""

from app import create_app
from extensions import db
from models import Lead, Note, FollowUp
from datetime import datetime, timedelta

app = create_app()

with app.app_context():
    # Only seed if table is empty
    if Lead.query.count() == 0:
        leads_data = [
            Lead(name="Rahul Sharma", email="rahul.sharma@gmail.com", phone="9876543210",
                 source="99acres", property_type="Flat/Apartment", budget="50L - 75L",
                 location="Sector 62, Noida", status="New", priority="High", assigned_to="Kirti"),
            Lead(name="Priya Gupta", email="priya.gupta@yahoo.com", phone="9123456789",
                 source="MagicBricks", property_type="House/Villa", budget="1Cr - 1.5Cr",
                 location="DLF Phase 3, Gurgaon", status="Contacted", priority="High", assigned_to="Kirti"),
            Lead(name="Amit Verma", email="amit.verma@hotmail.com", phone="9988776655",
                 source="99acres", property_type="Plot/Land", budget="30L - 50L",
                 location="Greater Noida West", status="Qualified", priority="Medium", assigned_to="Ravi"),
            Lead(name="Sneha Patel", email="sneha.patel@gmail.com", phone="8877665544",
                 source="Referral", property_type="Flat/Apartment", budget="75L - 1Cr",
                 location="Indirapuram, Ghaziabad", status="New", priority="Medium", assigned_to="Kirti"),
            Lead(name="Vikram Singh", email="vikram.singh@outlook.com", phone="7766554433",
                 source="Walk-in", property_type="Office Space", budget="1.5Cr - 2Cr",
                 location="Connaught Place, Delhi", status="Negotiation", priority="High", assigned_to="Ravi"),
            Lead(name="Anita Mehra", email="anita.mehra@gmail.com", phone="9654321098",
                 source="99acres", property_type="Flat/Apartment", budget="40L - 60L",
                 location="Vaishali, Ghaziabad", status="Converted", priority="Low", assigned_to="Kirti"),
            Lead(name="Deepak Kumar", email="deepak.kumar@gmail.com", phone="9012345678",
                 source="Housing.com", property_type="Shop/Showroom", budget="80L - 1Cr",
                 location="Karol Bagh, Delhi", status="Lost", priority="Medium", assigned_to="Ravi"),
            Lead(name="Kavita Rani", email="kavita.rani@yahoo.com", phone="8901234567",
                 source="99acres", property_type="Flat/Apartment", budget="25L - 40L",
                 location="Raj Nagar Extension, Ghaziabad", status="New", priority="High", assigned_to="Kirti"),
        ]
        db.session.add_all(leads_data)
        db.session.commit()
        print(f"Inserted {len(leads_data)} sample leads.")

        # Add some notes
        notes = [
            Note(lead_id=1, content="Customer is very interested in 2BHK flat near metro station."),
            Note(lead_id=1, content="Called customer, he prefers east-facing flat."),
            Note(lead_id=2, content="Looking for independent house with garden. Budget flexible."),
            Note(lead_id=3, content="Wants plot for investment purpose. Ready to visit site."),
            Note(lead_id=5, content="Needs 2000 sq ft office space. Meeting scheduled."),
        ]
        db.session.add_all(notes)
        db.session.commit()
        print(f"Inserted {len(notes)} sample notes.")

        # Add some follow-ups
        followups = [
            FollowUp(lead_id=1, description="Call back for site visit", scheduled_at=datetime.utcnow() + timedelta(hours=2)),
            FollowUp(lead_id=2, description="Send property brochure via WhatsApp", scheduled_at=datetime.utcnow() + timedelta(hours=5)),
            FollowUp(lead_id=4, description="Share flat options near metro", scheduled_at=datetime.utcnow() + timedelta(days=1)),
            FollowUp(lead_id=5, description="Schedule office space visit", scheduled_at=datetime.utcnow() - timedelta(hours=1)),
        ]
        db.session.add_all(followups)
        db.session.commit()
        print(f"Inserted {len(followups)} sample follow-ups.")

        print("\nDone! Your CRM is ready with sample data.")
    else:
        print(f"Database already has {Lead.query.count()} leads. Skipping seed.")
