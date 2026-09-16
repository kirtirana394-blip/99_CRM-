from flask import Blueprint, request, redirect, url_for, session, flash, jsonify, render_template
from datetime import datetime
from models import db, Lead, FollowUp, Note, Task, Meeting, Proposal, Deal, Notification
from utils.helpers import parse_dt

crm_bp=Blueprint("crm",__name__)

@crm_bp.post("/leads/<int:lead_id>/followups")
def add_followup(lead_id):
    if not session.get("user_id"): return {"error":"Unauthorized"},401
    lead=Lead.query.get_or_404(lead_id)
    f=FollowUp(lead_id=lead.id,assigned_user_id=int(request.form["assigned_user_id"]) if request.form.get("assigned_user_id") else session["user_id"],
               followup_at=parse_dt(request.form["followup_at"]),activity_type=request.form.get("activity_type","Follow-up"),
               notes=request.form.get("notes"),reminder=bool(request.form.get("reminder")),created_by=session["user_id"])
    if not f.followup_at: flash("Valid follow-up date/time required.","danger"); return redirect(url_for("leads.detail",lead_id=lead.id))
    db.session.add(f); lead.next_followup_date=f.followup_at; db.session.commit()
    flash("Follow-up scheduled.","success"); return redirect(url_for("leads.detail",lead_id=lead.id))

@crm_bp.post("/followups/<int:fid>/complete")
def complete_followup(fid):
    f=FollowUp.query.get_or_404(fid); f.status="Completed"; f.completed_at=datetime.now(); db.session.commit()
    return {"ok":True}

@crm_bp.post("/leads/<int:lead_id>/notes")
def add_note(lead_id):
    lead=Lead.query.get_or_404(lead_id)
    text=request.form.get("note_text","").strip()
    if text: db.session.add(Note(lead_id=lead.id,note_text=text,created_by=session["user_id"])); db.session.commit()
    return redirect(url_for("leads.detail",lead_id=lead.id))

@crm_bp.post("/tasks")
def add_task():
    t=Task(title=request.form["title"],lead_id=int(request.form["lead_id"]) if request.form.get("lead_id") else None,
           assigned_user_id=int(request.form["assigned_user_id"]) if request.form.get("assigned_user_id") else session["user_id"],
           due_date=parse_dt(request.form.get("due_date")),priority=request.form.get("priority","Medium"),
           description=request.form.get("description"))
    db.session.add(t); db.session.commit(); flash("Task created.","success"); return redirect(request.referrer or url_for("dashboard.index"))

@crm_bp.post("/tasks/<int:tid>/status")
def task_status(tid):
    t=Task.query.get_or_404(tid); t.status=request.form["status"]; db.session.commit(); return {"ok":True}

@crm_bp.post("/leads/<int:lead_id>/meetings")
def add_meeting(lead_id):
    m=Meeting(lead_id=lead_id,meeting_at=parse_dt(request.form["meeting_at"]),meeting_type=request.form.get("meeting_type","Meeting"),
              location=request.form.get("location"),participants=request.form.get("participants"),notes=request.form.get("notes"))
    db.session.add(m); db.session.commit(); flash("Meeting scheduled.","success"); return redirect(url_for("leads.detail",lead_id=lead_id))

@crm_bp.post("/meetings/<int:mid>/status")
def meeting_status(mid):
    m=Meeting.query.get_or_404(mid); m.status=request.form["status"]
    if m.status=="Completed": m.lead.lead_status=m.lead.lead_stage="Meeting Done"
    db.session.commit(); return {"ok":True}

@crm_bp.post("/leads/<int:lead_id>/proposals")
def add_proposal(lead_id):
    p=Proposal(lead_id=lead_id,proposal_date=parse_dt(request.form.get("proposal_date")) or datetime.now(),
               proposal_value=float(request.form.get("proposal_value") or 0),proposal_status=request.form.get("proposal_status","Draft"),
               followup_date=parse_dt(request.form.get("followup_date")),notes=request.form.get("notes"))
    db.session.add(p)
    if p.proposal_status in ("Sent","Under Discussion"): p.lead.lead_status=p.lead.lead_stage="Proposal Sent"
    db.session.commit(); flash("Proposal saved.","success"); return redirect(url_for("leads.detail",lead_id=lead_id))

@crm_bp.post("/leads/<int:lead_id>/deals")
def close_deal(lead_id):
    lead=Lead.query.get_or_404(lead_id)
    value=float(request.form.get("deal_value") or 0); date=parse_dt(request.form.get("deal_date")) or datetime.now()
    if value<=0: flash("Deal value must be greater than zero.","danger"); return redirect(url_for("leads.detail",lead_id=lead_id))
    d=Deal(lead_id=lead.id,deal_date=date,deal_value=value,property_name=request.form.get("property_name") or lead.property_name,
           client_name=lead.client_name,salesperson_id=lead.assigned_to or session["user_id"])
    db.session.add(d); lead.deal_date=date; lead.deal_value=value; lead.lead_status=lead.lead_stage="Deal Closed"
    db.session.commit(); flash("Deal closed and revenue recorded.","success"); return redirect(url_for("leads.detail",lead_id=lead_id))

@crm_bp.get("/followups")
def followups():
    if not session.get("user_id"): return redirect("/login")
    now=datetime.now()
    items=FollowUp.query.filter_by(status="Pending").order_by(FollowUp.followup_at).all()
    return render_template("followups.html",items=items,now=now)

@crm_bp.get("/tasks")
def tasks():
    if not session.get("user_id"): return redirect("/login")
    return render_template("tasks.html",tasks=Task.query.order_by(Task.due_date.asc()).all(),leads=Lead.query.order_by(Lead.client_name).all())
