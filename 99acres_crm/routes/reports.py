from flask import Blueprint, render_template, session, redirect
from sqlalchemy import func
from models import db, Lead, Deal, User

reports_bp=Blueprint("reports",__name__)

@reports_bp.get("/reports")
def reports():
    if not session.get("user_id"): return redirect("/login")
    by_status=db.session.query(Lead.lead_status,func.count(Lead.id)).group_by(Lead.lead_status).all()
    by_property=db.session.query(Lead.property_name,func.count(Lead.id)).filter(Lead.property_name.isnot(None)).group_by(Lead.property_name).order_by(func.count(Lead.id).desc()).limit(10).all()
    by_location=db.session.query(Lead.location,func.count(Lead.id)).filter(Lead.location.isnot(None)).group_by(Lead.location).order_by(func.count(Lead.id).desc()).limit(10).all()
    users=db.session.query(User.username,func.count(Lead.id)).outerjoin(Lead,Lead.assigned_to==User.id).group_by(User.id).all()
    return render_template("reports.html",by_status=by_status,by_property=by_property,by_location=by_location,users=users)
