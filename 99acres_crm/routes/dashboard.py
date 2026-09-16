from flask import Blueprint, render_template, session
from datetime import datetime, timedelta
from sqlalchemy import func
from models import db, Lead, FollowUp, Meeting, Proposal, Deal, Task, Notification

dashboard_bp=Blueprint("dashboard",__name__)

@dashboard_bp.get("/dashboard")
def index():
    if not session.get("user_id"): return __import__("flask").redirect("/login")
    now=datetime.now(); today=now.date()
    start_week=now-timedelta(days=now.weekday()); start_month=now.replace(day=1)
    statuses=["New Lead","Contacted","Qualified Lead","Meeting Done","Proposal Sent","Active","Deal Closed","Disqualified Lead"]
    counts={s:Lead.query.filter_by(lead_status=s).count() for s in statuses}
    total=Lead.query.count()
    closed=counts["Deal Closed"]
    revenue=db.session.query(func.coalesce(func.sum(Deal.deal_value),0)).scalar() or 0
    conversion=(closed/total*100) if total else 0
    due_today=FollowUp.query.filter(FollowUp.status=="Pending",func.date(FollowUp.followup_at)==today).count()
    overdue=FollowUp.query.filter(FollowUp.status=="Pending",FollowUp.followup_at<now).count()
    upcoming=FollowUp.query.filter(FollowUp.status=="Pending",FollowUp.followup_at>now).count()
    meetings=Meeting.query.filter(Meeting.status=="Scheduled",Meeting.meeting_at>=now).count()
    proposals=Proposal.query.filter(Proposal.proposal_status.in_(["Sent","Under Discussion"])).count()
    leads_today=Lead.query.filter(Lead.created_at>=datetime.combine(today,datetime.min.time())).count()
    leads_week=Lead.query.filter(Lead.created_at>=start_week).count()
    leads_month=Lead.query.filter(Lead.created_at>=start_month).count()
    tasks=Task.query.filter(Task.status!="Completed").count()
    notes=Notification.query.filter_by(user_id=session["user_id"],read=False).order_by(Notification.created_at.desc()).limit(5).all()
    return render_template("dashboard.html",counts=counts,total=total,closed=closed,revenue=revenue,conversion=conversion,
        due_today=due_today,overdue=overdue,upcoming=upcoming,meetings=meetings,proposals=proposals,
        leads_today=leads_today,leads_week=leads_week,leads_month=leads_month,tasks=tasks,notifications=notes)
