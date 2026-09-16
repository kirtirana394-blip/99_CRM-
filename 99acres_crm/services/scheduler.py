from datetime import datetime, timedelta
from models import db, FollowUp, Notification, Task, Meeting
_started=False

def run_automation(app):
    with app.app_context():
        now=datetime.now()
        pending=FollowUp.query.filter_by(status="Pending",reminder=True).all()
        for f in pending:
            for hours, label in ((24,"24-hour reminder"),(1,"1-hour reminder")):
                target=f.followup_at-timedelta(hours=hours)
                if target <= now < target+timedelta(minutes=10):
                    msg=f"{label}: {f.activity_type} for {f.lead.client_name} at {f.followup_at.strftime('%d/%m/%Y %I:%M %p')}"
                    exists=Notification.query.filter_by(user_id=f.assigned_user_id,message=msg).first()
                    if not exists: db.session.add(Notification(user_id=f.assigned_user_id,message=msg))
        overdue=FollowUp.query.filter_by(status="Pending").filter(FollowUp.followup_at<now).all()
        for f in overdue:
            msg=f"Overdue follow-up for {f.lead.client_name}"
            if not Notification.query.filter_by(user_id=f.assigned_user_id,message=msg).first():
                db.session.add(Notification(user_id=f.assigned_user_id,message=msg))
        db.session.commit()

def start_scheduler(app):
    global _started
    if _started: return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler=BackgroundScheduler(daemon=True)
        scheduler.add_job(lambda: run_automation(app),"interval",minutes=10,id="crm_automation",replace_existing=True)
        scheduler.start()
        _started=True
    except Exception:
        app.logger.warning("Background scheduler unavailable; CRM remains fully usable.")
