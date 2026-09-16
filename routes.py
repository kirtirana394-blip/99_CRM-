# routes.py
"""All routes: Web UI pages + REST API endpoints."""

from flask import Blueprint, request, jsonify, abort, render_template, redirect, url_for, flash
from models import Lead, Note, FollowUp
from extensions import db
from datetime import datetime

# ── API Blueprint ──────────────────────────────────────────────
api_bp = Blueprint('api', __name__)

@api_bp.route('/leads', methods=['POST'])
def api_create_lead():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('email'):
        abort(400, description='name and email are required')
    lead = Lead(
        name=data['name'], email=data['email'],
        phone=data.get('phone', ''), source=data.get('source', '99acres'),
        property_type=data.get('property_type', ''),
        budget=data.get('budget', ''), location=data.get('location', ''),
        status=data.get('status', 'New'), priority=data.get('priority', 'Medium'),
        assigned_to=data.get('assigned_to', ''),
    )
    db.session.add(lead)
    db.session.commit()
    return jsonify(lead.to_dict()), 201

@api_bp.route('/leads', methods=['GET'])
def api_list_leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    return jsonify([l.to_dict() for l in leads])

@api_bp.route('/leads/<int:lid>', methods=['GET'])
def api_get_lead(lid):
    lead = Lead.query.get_or_404(lid)
    return jsonify(lead.to_dict())

@api_bp.route('/leads/<int:lid>', methods=['PUT'])
def api_update_lead(lid):
    lead = Lead.query.get_or_404(lid)
    data = request.get_json()
    for f in ('name','email','phone','source','property_type','budget','location','status','priority','assigned_to'):
        if f in data:
            setattr(lead, f, data[f])
    db.session.commit()
    return jsonify(lead.to_dict())

@api_bp.route('/leads/<int:lid>', methods=['DELETE'])
def api_delete_lead(lid):
    lead = Lead.query.get_or_404(lid)
    db.session.delete(lead)
    db.session.commit()
    return '', 204

# ── Web UI Blueprint ──────────────────────────────────────────
web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def dashboard():
    total = Lead.query.count()
    new_count = Lead.query.filter_by(status='New').count()
    contacted = Lead.query.filter_by(status='Contacted').count()
    qualified = Lead.query.filter_by(status='Qualified').count()
    converted = Lead.query.filter_by(status='Converted').count()
    lost = Lead.query.filter_by(status='Lost').count()
    recent = Lead.query.order_by(Lead.created_at.desc()).limit(10).all()
    today_followups = FollowUp.query.filter(
        FollowUp.scheduled_at <= datetime.utcnow(),
        FollowUp.completed == False
    ).all()
    return render_template('dashboard.html',
        total=total, new_count=new_count, contacted=contacted,
        qualified=qualified, converted=converted, lost=lost,
        recent=recent, today_followups=today_followups)

@web_bp.route('/leads')
def leads_list():
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    query = Lead.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if search:
        query = query.filter(
            (Lead.name.ilike(f'%{search}%')) |
            (Lead.email.ilike(f'%{search}%')) |
            (Lead.phone.ilike(f'%{search}%')) |
            (Lead.location.ilike(f'%{search}%'))
        )
    leads = query.order_by(Lead.created_at.desc()).all()
    return render_template('leads_list.html', leads=leads,
        status_filter=status_filter, search=search)

@web_bp.route('/leads/add', methods=['GET', 'POST'])
def add_lead():
    if request.method == 'POST':
        lead = Lead(
            name=request.form['name'], email=request.form['email'],
            phone=request.form.get('phone', ''),
            source=request.form.get('source', '99acres'),
            property_type=request.form.get('property_type', ''),
            budget=request.form.get('budget', ''),
            location=request.form.get('location', ''),
            status=request.form.get('status', 'New'),
            priority=request.form.get('priority', 'Medium'),
            assigned_to=request.form.get('assigned_to', ''),
        )
        db.session.add(lead)
        db.session.commit()
        flash('Lead added successfully!', 'success')
        return redirect(url_for('web.leads_list'))
    return render_template('lead_form.html', lead=None, action='Add')

@web_bp.route('/leads/<int:lid>')
def lead_detail(lid):
    lead = Lead.query.get_or_404(lid)
    return render_template('lead_detail.html', lead=lead)

@web_bp.route('/leads/<int:lid>/edit', methods=['GET', 'POST'])
def edit_lead(lid):
    lead = Lead.query.get_or_404(lid)
    if request.method == 'POST':
        lead.name = request.form['name']
        lead.email = request.form['email']
        lead.phone = request.form.get('phone', '')
        lead.source = request.form.get('source', '')
        lead.property_type = request.form.get('property_type', '')
        lead.budget = request.form.get('budget', '')
        lead.location = request.form.get('location', '')
        lead.status = request.form.get('status', 'New')
        lead.priority = request.form.get('priority', 'Medium')
        lead.assigned_to = request.form.get('assigned_to', '')
        db.session.commit()
        flash('Lead updated!', 'success')
        return redirect(url_for('web.lead_detail', lid=lead.id))
    return render_template('lead_form.html', lead=lead, action='Edit')

@web_bp.route('/leads/<int:lid>/delete', methods=['POST'])
def delete_lead(lid):
    lead = Lead.query.get_or_404(lid)
    db.session.delete(lead)
    db.session.commit()
    flash('Lead deleted.', 'info')
    return redirect(url_for('web.leads_list'))

@web_bp.route('/leads/<int:lid>/note', methods=['POST'])
def add_note(lid):
    lead = Lead.query.get_or_404(lid)
    content = request.form.get('content', '').strip()
    if content:
        note = Note(lead_id=lead.id, content=content)
        db.session.add(note)
        db.session.commit()
        flash('Note added.', 'success')
    return redirect(url_for('web.lead_detail', lid=lid))

@web_bp.route('/leads/<int:lid>/followup', methods=['POST'])
def add_followup(lid):
    lead = Lead.query.get_or_404(lid)
    desc = request.form.get('description', '').strip()
    sched = request.form.get('scheduled_at', '')
    if sched:
        fu = FollowUp(lead_id=lead.id, description=desc,
                      scheduled_at=datetime.strptime(sched, '%Y-%m-%dT%H:%M'))
        db.session.add(fu)
        db.session.commit()
        flash('Follow-up scheduled.', 'success')
    return redirect(url_for('web.lead_detail', lid=lid))

@web_bp.route('/followups/<int:fid>/complete', methods=['POST'])
def complete_followup(fid):
    fu = FollowUp.query.get_or_404(fid)
    fu.completed = True
    db.session.commit()
    flash('Follow-up marked complete.', 'success')
    return redirect(url_for('web.lead_detail', lid=fu.lead_id))
