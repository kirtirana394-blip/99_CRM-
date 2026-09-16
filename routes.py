# routes.py
"""All routes: Dashboard, Lead CRUD, User Management, Tasks, CSV Import/Export, and REST API."""

from flask import Blueprint, request, jsonify, abort, render_template, redirect, url_for, flash, Response
from models import Lead, Note, FollowUp, User, Task
from extensions import db
from datetime import datetime, timedelta
import csv
import io

# ── API Blueprint ──────────────────────────────────────────────
api_bp = Blueprint('api', __name__)

@api_bp.route('/leads', methods=['POST'])
def api_create_lead():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('email'):
        abort(400, description='name and email are required')
    created_at = datetime.strptime(data['created_date'], '%Y-%m-%d') if data.get('created_date') else datetime.utcnow()
    lead = Lead(
        name=data['name'], email=data['email'],
        phone=data.get('phone', ''), source=data.get('source', '99acres'),
        property_type=data.get('property_type', ''),
        budget=data.get('budget', ''), location=data.get('location', ''),
        status=data.get('status', 'New'), priority=data.get('priority', 'Medium'),
        assigned_to=data.get('assigned_to', ''),
        created_at=created_at
    )
    db.session.add(lead)
    db.session.commit()
    return jsonify(lead.to_dict()), 201

@api_bp.route('/leads', methods=['GET'])
def api_list_leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    return jsonify([l.to_dict() for l in leads])

# ── Web UI Blueprint ──────────────────────────────────────────
web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def dashboard():
    time_filter = request.args.get('time_filter', 'this_week')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')

    now = datetime.utcnow()
    query = Lead.query

    # Apply date range filtering
    if time_filter == 'today':
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(Lead.created_at >= start_of_day)
    elif time_filter == 'this_week':
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(Lead.created_at >= start_of_week)
    elif time_filter == 'this_month':
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(Lead.created_at >= start_of_month)
    elif time_filter == 'this_quarter':
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        start_of_quarter = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(Lead.created_at >= start_of_quarter)
    elif time_filter == 'custom' and start_date_str and end_date_str:
        try:
            sd = datetime.strptime(start_date_str, '%Y-%m-%d')
            ed = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Lead.created_at >= sd, Lead.created_at < ed)
        except ValueError:
            pass

    all_filtered_leads = query.all()

    # Calculate metric card counts
    total_leads = len(all_filtered_leads)
    new_leads = sum(1 for l in all_filtered_leads if l.status == 'New')
    qualified = sum(1 for l in all_filtered_leads if l.status == 'Qualified')
    meeting_done = sum(1 for l in all_filtered_leads if l.status == 'Meeting Done')
    proposal_sent = sum(1 for l in all_filtered_leads if l.status == 'Proposal Sent')
    deal_close = sum(1 for l in all_filtered_leads if l.status == 'Deal Close')
    active_pipeline = sum(1 for l in all_filtered_leads if l.status not in ('Deal Close', 'Lost'))

    recent_leads = Lead.query.order_by(Lead.created_at.desc()).limit(7).all()
    today_followups = FollowUp.query.filter(FollowUp.completed == False).order_by(FollowUp.scheduled_at.asc()).limit(5).all()

    users_list = User.query.filter_by(status='Active').all()

    return render_template('dashboard.html',
        total_leads=total_leads, new_leads=new_leads, qualified=qualified,
        meeting_done=meeting_done, proposal_sent=proposal_sent,
        active_pipeline=active_pipeline, deal_close=deal_close,
        recent_leads=recent_leads, today_followups=today_followups,
        time_filter=time_filter, start_date=start_date_str, end_date=end_date_str,
        users_list=users_list)


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
            (Lead.location.ilike(f'%{search}%')) |
            (Lead.property_type.ilike(f'%{search}%'))
        )
    leads = query.order_by(Lead.created_at.desc()).all()
    return render_template('leads_list.html', leads=leads, status_filter=status_filter, search=search)


@web_bp.route('/leads/add', methods=['GET', 'POST'])
def add_lead():
    users = User.query.filter_by(status='Active').all()
    if request.method == 'POST':
        created_at_str = request.form.get('created_date', '')
        created_at = datetime.strptime(created_at_str, '%Y-%m-%d') if created_at_str else datetime.utcnow()

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
            created_at=created_at
        )
        db.session.add(lead)
        db.session.commit()
        flash('Lead added successfully!', 'success')
        return redirect(url_for('web.leads_list'))
    return render_template('lead_form.html', lead=None, action='Add', users=users)


@web_bp.route('/leads/<int:lid>')
def lead_detail(lid):
    lead = Lead.query.get_or_404(lid)
    users = User.query.filter_by(status='Active').all()
    return render_template('lead_detail.html', lead=lead, users=users)


@web_bp.route('/leads/<int:lid>/edit', methods=['GET', 'POST'])
def edit_lead(lid):
    lead = Lead.query.get_or_404(lid)
    users = User.query.filter_by(status='Active').all()
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
        
        created_at_str = request.form.get('created_date', '')
        if created_at_str:
            try:
                lead.created_at = datetime.strptime(created_at_str, '%Y-%m-%d')
            except ValueError:
                pass
                
        db.session.commit()
        flash('Lead updated successfully!', 'success')
        return redirect(url_for('web.lead_detail', lid=lead.id))
    return render_template('lead_form.html', lead=lead, action='Edit', users=users)


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
        try:
            fu = FollowUp(lead_id=lead.id, description=desc,
                          scheduled_at=datetime.strptime(sched, '%Y-%m-%dT%H:%M'))
            db.session.add(fu)
            db.session.commit()
            flash('Follow-up scheduled.', 'success')
        except ValueError:
            flash('Invalid date/time format.', 'danger')
    return redirect(url_for('web.lead_detail', lid=lid))


@web_bp.route('/followups/<int:fid>/complete', methods=['POST'])
def complete_followup(fid):
    fu = FollowUp.query.get_or_404(fid)
    fu.completed = True
    db.session.commit()
    flash('Follow-up marked complete.', 'success')
    return redirect(request.referrer or url_for('web.dashboard'))

# ── User Management (Admin Tab) ──────────────────────────────────
@web_bp.route('/users')
def users_list():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('users.html', users=users)

@web_bp.route('/users/add', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        role = request.form.get('role', 'Sales Executive')
        
        if User.query.filter_by(email=email).first():
            flash('User with this email already exists.', 'danger')
            return redirect(url_for('web.add_user'))
            
        user = User(name=name, email=email, role=role)
        db.session.add(user)
        db.session.commit()
        flash(f'User {name} ({role}) created successfully!', 'success')
        return redirect(url_for('web.users_list'))
    return render_template('user_form.html', user=None, action='Add')

@web_bp.route('/users/<int:uid>/edit', methods=['GET', 'POST'])
def edit_user(uid):
    user = User.query.get_or_404(uid)
    if request.method == 'POST':
        user.name = request.form['name']
        user.email = request.form['email']
        user.role = request.form.get('role', 'Sales Executive')
        user.status = request.form.get('status', 'Active')
        db.session.commit()
        flash('User updated successfully!', 'success')
        return redirect(url_for('web.users_list'))
    return render_template('user_form.html', user=user, action='Edit')

@web_bp.route('/users/<int:uid>/delete', methods=['POST'])
def delete_user(uid):
    user = User.query.get_or_404(uid)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted.', 'info')
    return redirect(url_for('web.users_list'))

# ── Tasks & Follow-ups Tab ──────────────────────────────────────
@web_bp.route('/tasks')
def tasks_list():
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    followups = FollowUp.query.order_by(FollowUp.scheduled_at.asc()).all()
    leads = Lead.query.all()
    users = User.query.filter_by(status='Active').all()
    return render_template('tasks.html', tasks=tasks, followups=followups, leads=leads, users=users)

@web_bp.route('/tasks/add', methods=['POST'])
def add_task():
    title = request.form.get('title', '').strip()
    desc = request.form.get('description', '').strip()
    lead_id = request.form.get('lead_id')
    assigned_to = request.form.get('assigned_to', '')
    due_date_str = request.form.get('due_date', '')
    priority = request.form.get('priority', 'Medium')

    if title:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
        task = Task(title=title, description=desc, lead_id=lead_id if lead_id else None,
                    assigned_to=assigned_to, due_date=due_date, priority=priority)
        db.session.add(task)
        db.session.commit()
        flash('Task added successfully!', 'success')
    return redirect(url_for('web.tasks_list'))

@web_bp.route('/tasks/<int:tid>/complete', methods=['POST'])
def complete_task(tid):
    task = Task.query.get_or_404(tid)
    task.completed = True
    db.session.commit()
    flash('Task completed!', 'success')
    return redirect(url_for('web.tasks_list'))

@web_bp.route('/tasks/<int:tid>/delete', methods=['POST'])
def delete_task(tid):
    task = Task.query.get_or_404(tid)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'info')
    return redirect(url_for('web.tasks_list'))

# ── Import & Export Data ──────────────────────────────────────
@web_bp.route('/import', methods=['GET', 'POST'])
def import_csv():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename.endswith('.csv'):
            flash('Please upload a valid .csv file.', 'danger')
            return redirect(url_for('web.import_csv'))

        stream = io.StringIO(file.stream.read().decode("utf-8"), newline=None)
        csv_reader = csv.DictReader(stream)
        count = 0
        for row in csv_reader:
            name = row.get('Name') or row.get('name')
            email = row.get('Email') or row.get('email')
            if not name or not email:
                continue

            created_date_str = row.get('Created Date') or row.get('created_date')
            created_at = datetime.utcnow()
            if created_date_str:
                try:
                    created_at = datetime.strptime(created_date_str.strip(), '%Y-%m-%d')
                except ValueError:
                    pass

            lead = Lead(
                name=name.strip(),
                email=email.strip(),
                phone=(row.get('Phone') or row.get('phone') or '').strip(),
                source=(row.get('Source') or row.get('source') or '99acres').strip(),
                property_type=(row.get('Property Type') or row.get('property_type') or '').strip(),
                budget=(row.get('Budget') or row.get('budget') or '').strip(),
                location=(row.get('Location') or row.get('location') or '').strip(),
                status=(row.get('Status') or row.get('status') or 'New').strip(),
                priority=(row.get('Priority') or row.get('priority') or 'Medium').strip(),
                assigned_to=(row.get('Assigned To') or row.get('assigned_to') or '').strip(),
                created_at=created_at
            )
            db.session.add(lead)
            count += 1
        
        db.session.commit()
        flash(f'Successfully imported {count} leads! They are now updated in your Dashboard.', 'success')
        return redirect(url_for('web.dashboard'))

    return render_template('import.html')


@web_bp.route('/export')
def export_csv():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['ID', 'Name', 'Email', 'Phone', 'Source', 'Property Type', 'Budget', 'Location', 'Status', 'Priority', 'Assigned To', 'Created Date'])
    for l in leads:
        writer.writerow([l.id, l.name, l.email, l.phone, l.source, l.property_type, l.budget, l.location, l.status, l.priority, l.assigned_to, l.created_at.strftime('%Y-%m-%d')])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=leads_export.csv"}
    )
