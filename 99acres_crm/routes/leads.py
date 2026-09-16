from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from sqlalchemy import or_
from models import db, Lead, User, StageHistory
from utils.helpers import normalize_phone, normalize_email, parse_dt

leads_bp=Blueprint("leads",__name__)
STAGES=["New Lead","Contacted","Qualified Lead","Meeting Done","Proposal Sent","Active","Deal Closed","Disqualified Lead"]

def duplicate_for(phone,email,ref,exclude_id=None):
    q=Lead.query
    clauses=[]
    if phone: clauses.append(Lead.phone==phone)
    if email: clauses.append(Lead.email==email)
    if ref: clauses.append(Lead.source_reference==ref)
    if not clauses: return None
    q=q.filter(or_(*clauses))
    if exclude_id: q=q.filter(Lead.id!=exclude_id)
    return q.first()

@leads_bp.get("/leads")
def list_leads():
    if not session.get("user_id"): return redirect("/login")
    q=Lead.query
    search=request.args.get("q","").strip()
    status=request.args.get("status","")
    assigned=request.args.get("assigned","")
    priority=request.args.get("priority","")
    if search:
        like=f"%{search}%"
        q=q.filter(or_(Lead.client_name.ilike(like),Lead.phone.ilike(like),Lead.email.ilike(like),
                       Lead.company_name.ilike(like),Lead.location.ilike(like),Lead.lead_id.ilike(like)))
    if status: q=q.filter_by(lead_status=status)
    if assigned:
        q=q.filter_by(assigned_to=int(assigned))
    if priority: q=q.filter_by(priority=priority)
    page=max(int(request.args.get("page",1)),1); per=25
    pagination=q.order_by(Lead.created_at.desc()).paginate(page=page,per_page=per,error_out=False)
    return render_template("leads.html",pagination=pagination,leads=pagination.items,users=User.query.filter_by(active=True).all(),stages=STAGES)

@leads_bp.route("/leads/new",methods=["GET","POST"])
def new_lead():
    if not session.get("user_id"): return redirect("/login")
    users=User.query.filter_by(active=True).all()
    if request.method=="POST":
        phone=normalize_phone(request.form.get("phone")); email=normalize_email(request.form.get("email"))
        ref=request.form.get("source_reference","").strip() or None
        dup=duplicate_for(phone,email,ref)
        if dup:
            flash(f"Duplicate found: {dup.lead_id}. Existing lead opened instead.","warning")
            return redirect(url_for("leads.detail",lead_id=dup.id))
        lead=Lead(
            lead_id=request.form.get("lead_id").strip() or f"99A-{__import__('uuid').uuid4().hex[:10].upper()}",
            client_name=request.form["client_name"].strip(), company_name=request.form.get("company_name"),
            phone=phone,alternate_phone=normalize_phone(request.form.get("alternate_phone")),email=email,
            property_name=request.form.get("property_name"),property_type=request.form.get("property_type"),
            location=request.form.get("location"),requirement=request.form.get("requirement"),
            budget=request.form.get("budget"),area_required=request.form.get("area_required"),
            source="99Acres",source_reference=ref,lead_status=request.form.get("lead_status","New Lead"),
            lead_stage=request.form.get("lead_stage","New Lead"),priority=request.form.get("priority","Medium"),
            assigned_to=int(request.form["assigned_to"]) if request.form.get("assigned_to") else None,
            lead_date=parse_dt(request.form.get("lead_date")) or __import__("datetime").datetime.now(),
            next_followup_date=parse_dt(request.form.get("next_followup_date")),notes=request.form.get("notes"))
        if lead.lead_status=="Disqualified Lead" and not request.form.get("lost_reason"):
            flash("Disqualification reason is required.","danger"); return render_template("lead_form.html",lead=lead,users=users,stages=STAGES)
        lead.lost_reason=request.form.get("lost_reason")
        db.session.add(lead); db.session.flush()
        db.session.add(StageHistory(lead_id=lead.id,new_stage=lead.lead_stage,changed_by=session["user_id"]))
        db.session.commit()
        flash("Lead created successfully.","success")
        return redirect(url_for("leads.detail",lead_id=lead.id))
    return render_template("lead_form.html",lead=None,users=users,stages=STAGES)

@leads_bp.route("/leads/<int:lead_id>",methods=["GET","POST"])
def detail(lead_id):
    if not session.get("user_id"): return redirect("/login")
    lead=Lead.query.get_or_404(lead_id); users=User.query.filter_by(active=True).all()
    if request.method=="POST":
        old=lead.lead_stage
        phone=normalize_phone(request.form.get("phone")); email=normalize_email(request.form.get("email"))
        dup=duplicate_for(phone,email,request.form.get("source_reference"),lead.id)
        if dup:
            flash(f"Another lead already uses that contact/reference: {dup.lead_id}","danger")
            return render_template("lead_detail.html",lead=lead,users=users,stages=STAGES)
        for f in ["client_name","company_name","alternate_phone","property_name","property_type","location","requirement","budget","area_required","priority","notes","lost_reason"]:
            if f in request.form: setattr(lead,f,request.form.get(f))
        lead.phone=phone; lead.email=email
        lead.assigned_to=int(request.form["assigned_to"]) if request.form.get("assigned_to") else None
        lead.lead_status=request.form.get("lead_status",lead.lead_status)
        lead.lead_stage=request.form.get("lead_stage",lead.lead_stage)
        lead.next_followup_date=parse_dt(request.form.get("next_followup_date"))
        lead.deal_value=float(request.form.get("deal_value") or 0)
        if lead.lead_status=="Disqualified Lead" and not lead.lost_reason:
            flash("Disqualification reason is required.","danger")
            return render_template("lead_detail.html",lead=lead,users=users,stages=STAGES)
        if old!=lead.lead_stage:
            db.session.add(StageHistory(lead_id=lead.id,old_stage=old,new_stage=lead.lead_stage,changed_by=session["user_id"]))
        db.session.commit(); flash("Lead updated.","success")
        return redirect(url_for("leads.detail",lead_id=lead.id))
    return render_template("lead_detail.html",lead=lead,users=users,stages=STAGES)

@leads_bp.post("/leads/<int:lead_id>/delete")
def delete(lead_id):
    if session.get("role")!="admin": return {"error":"Admin access required"},403
    lead=Lead.query.get_or_404(lead_id); db.session.delete(lead); db.session.commit()
    return {"ok":True}

@leads_bp.post("/api/leads/bulk")
def bulk():
    if not session.get("user_id"): return {"error":"Unauthorized"},401
    data=request.get_json() or {}; ids=data.get("ids",[])
    leads=Lead.query.filter(Lead.id.in_(ids)).all()
    if data.get("status"):
        for l in leads: l.lead_status=l.lead_stage=data["status"]
    if data.get("assigned_to") is not None:
        for l in leads: l.assigned_to=int(data["assigned_to"]) if data["assigned_to"] else None
    db.session.commit()
    return jsonify({"ok":True,"updated":len(leads)})
