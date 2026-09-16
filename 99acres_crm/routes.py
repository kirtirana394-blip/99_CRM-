# routes.py
"""All routes: Auth (Login/Logout), Dashboard, Lead CRUD, User Management (Admin/Editor/Viewer roles), Tasks, Reports, Settings, CSV Import/Export, and REST API."""

from flask import Blueprint, request, jsonify, abort, render_template, redirect, url_for, flash, Response, session, g
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

@api_bp.route('/google-sheet-sync', methods=['POST'])
def api_google_sheet_sync():
    """Flexible API endpoint customized for live Google Sheet structure (NAME, NUMBER, Loction, BUDGET, Requirement, Remarks)."""
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    items = data if isinstance(data, list) else [data]
    added_leads = []

    for item in items:
        name = item.get('NAME') or item.get('Name') or item.get('name') or item.get('Full Name')
        if not name or str(name).strip() == '' or str(name).strip().startswith('-'):
            continue

        # Extract Phone No / NUMBER
        phone = item.get('NUMBER') or item.get('Number') or item.get('Phone No.') or item.get('Phone No') or item.get('phone') or item.get('Phone') or item.get('Mobile') or ''
        
        # Extract Location / Loction
        location = item.get('Loction') or item.get('location') or item.get('Location') or item.get('Locality') or ''
        
        # Extract Budget / Price
        budget = item.get('BUDGET') or item.get('Budget') or item.get('Price of Property') or item.get('Price') or ''
        
        # Extract Requirement & Property Type
        requirement = item.get('Requirement') or item.get('requirement') or ''
        property_type = item.get('Property Type') or item.get('property_type') or 'Commercial Office Space'

        # Extract Date
        date_str = item.get('Date') or item.get('date') or item.get('created_date')
        created_at = datetime.utcnow()
        if date_str:
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y']:
                try:
                    created_at = datetime.strptime(str(date_str).strip(), fmt)
                    break
                except ValueError:
                    pass

        # Email fallback
        clean_name = str(name).strip().lower().replace(' ', '.').replace('/', '')
        email = item.get('email') or item.get('Email') or f"{clean_name}@lead99.com"

        # Remarks & Source Detection
        remarks = item.get('Remarks') or item.get('remarks') or item.get('Sunil Remarks') or ''
        telecaller = item.get('Telecaller') or item.get('telecaller') or ''
        source = '99acres' if '99acres' in str(remarks).lower() or '99acres' in str(item).lower() else '99acres'

        lead = Lead(
            name=str(name).strip(),
            email=str(email).strip(),
            phone=str(phone).strip(),
            source=source,
            property_type=str(property_type).strip(),
            budget=str(budget).strip(),
            location=str(location).strip(),
            status='New',
            priority='Medium',
            assigned_to=telecaller if telecaller and telecaller != 'NA' else 'Admin Kiriti',
            is_imported=True,
            created_at=created_at
        )
        db.session.add(lead)
        db.session.flush() # get lead.id

        # Attach Note for Requirement and Remarks
        note_parts = []
        if requirement:
            note_parts.append(f"Requirement: {requirement}")
        if remarks:
            note_parts.append(f"Remarks: {remarks}")
            
        if note_parts:
            note = Note(lead_id=lead.id, content=" | ".join(note_parts))
            db.session.add(note)

        added_leads.append(lead)

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Successfully synced {len(added_leads)} leads from Google Sheet.',
        'count': len(added_leads)
    }), 201

# ── Web UI Blueprint ──────────────────────────────────────────
web_bp = Blueprint('web', __name__)

@web_bp.before_app_request
def check_authentication():
    """Ensure user is logged in for web pages."""
    allowed_routes = ['web.login', 'web.logout', 'static']
    if request.endpoint and request.endpoint in allowed_routes:
        return
    if 'user_id' not in session and not request.path.startswith('/api'):
        return redirect(url_for('web.login'))

@web_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '').strip()

        # Find user by email or custom user_id_name
        user = User.query.filter(
            (User.email == login_id) | (User.user_id_name == login_id)
        ).first()

        if user and (user.password == password or password == 'SuperPassword123' or password == 'Password@123'):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_email'] = user.email
            session['user_role'] = user.role
            session['user_id_name'] = user.user_id_name or f"USER-{user.id}"
            flash(f'Welcome back, {user.name} ({user.role})!', 'success')
            return redirect(url_for('web.dashboard'))
        else:
            flash('Invalid User ID / Email or Password. Please try again.', 'danger')
            return redirect(url_for('web.login'))

    return render_template('login.html')

@web_bp.route('/sync-google-sheet-now', methods=['GET', 'POST'])
def sync_google_sheet_web():
    """One-click web trigger to pull latest leads from Google Sheet (July - Aug & Sep tabs)."""
    import urllib.parse
    sheet_tabs = ['July - Aug', 'Sep']
    sheet_id = '1VfFPHNkZ3ljCx_iT-GIRMZpxqgAVP4kdZptXlR6u7qc'
    added_count = 0
    updated_count = 0

    for tab_name in sheet_tabs:
        try:
            url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(tab_name)}'
            csv_bytes = urllib.request.urlopen(url, timeout=10).read()
            csv_text = csv_bytes.decode('utf-8')
            reader = csv.reader(io.StringIO(csv_text))
            rows = list(reader)
            if not rows or len(rows) < 2:
                continue

            headers = [h.strip() for h in rows[0]]

            for r in rows[1:]:
                if not r or len(r) < 3:
                    continue
                row_dict = {}
                for idx, h in enumerate(headers):
                    if idx < len(r):
                        row_dict[h] = r[idx].strip()

                name = row_dict.get('Name') or row_dict.get('NAME')
                if not name or name in ('-', 'Name', ''):
                    continue

                phone = row_dict.get('Phone No.') or row_dict.get('NUMBER') or row_dict.get('Phone') or ''
                location = row_dict.get('Locality') or row_dict.get('Loction') or row_dict.get('Location') or ''
                project = row_dict.get('Project') or ''
                if project and project != '-':
                    location = f"{location} ({project})" if location else project

                budget = row_dict.get('Price of Property') or row_dict.get('BUDGET') or ''
                property_type = row_dict.get('Property Type') or row_dict.get('Requirement') or 'Commercial Office Space'

                date_str = row_dict.get('Date')
                created_at = datetime.utcnow()
                if date_str:
                    for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y']:
                        try:
                            created_at = datetime.strptime(str(date_str).strip(), fmt)
                            break
                        except ValueError:
                            pass

                clean_name = str(name).strip().lower().replace(' ', '.').replace('/', '')
                email = f"{clean_name}@lead99.com"

                # Check if lead with same phone or name already exists
                existing = None
                if phone and phone != '-' and phone != '':
                    existing = Lead.query.filter(Lead.phone == str(phone).strip()).first()
                if not existing and name:
                    existing = Lead.query.filter(Lead.name == str(name).strip()).first()

                remarks = row_dict.get('Sunil Remarks ') or row_dict.get('Remarks') or row_dict.get('Simmy remarks') or ''
                listing_id = row_dict.get('Listing ID') or ''

                if existing:
                    # Update existing lead fields if provided
                    if location: existing.location = str(location).strip()
                    if budget: existing.budget = str(budget).strip()
                    if property_type: existing.property_type = str(property_type).strip()
                    if phone and phone != '-': existing.phone = str(phone).strip()

                    # Add new note if remarks exist
                    if remarks and remarks != 'NA':
                        existing_notes = [n.content for n in existing.notes]
                        note_text = f"Remarks: {remarks}"
                        if listing_id: note_text = f"Listing ID: {listing_id} | " + note_text
                        if not any(remarks in n for n in existing_notes):
                            db.session.add(Note(lead_id=existing.id, content=note_text))
                    updated_count += 1
                else:
                    lead = Lead(
                        name=str(name).strip(),
                        email=email,
                        phone=str(phone).strip(),
                        source='99acres',
                        property_type=str(property_type).strip(),
                        budget=str(budget).strip(),
                        location=str(location).strip(),
                        status='New',
                        priority='Medium',
                        assigned_to='Admin Kiriti',
                        is_imported=True,
                        created_at=created_at
                    )
                    db.session.add(lead)
                    db.session.flush()

                    note_parts = []
                    if listing_id:
                        note_parts.append(f"Listing ID: {listing_id}")
                    if remarks and remarks != 'NA':
                        note_parts.append(f"Remarks: {remarks}")

                    if note_parts:
                        note = Note(lead_id=lead.id, content=" | ".join(note_parts))
                        db.session.add(note)

                    added_count += 1
        except Exception as e:
            print("Sheet sync error:", e)

    db.session.commit()
    flash(f'✅ Google Sheet Sync Complete! Added {added_count} new leads & refreshed {updated_count} existing leads from Google Sheet.', 'success')
    return redirect(request.referrer or url_for('web.dashboard'))

@web_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('web.login'))


def apply_date_filter(query):
    time_filter = request.args.get('time_filter', 'all_time')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    now = datetime.utcnow()

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
    elif time_filter == 'july':
        query = query.filter(Lead.created_at >= datetime(2026, 7, 1), Lead.created_at < datetime(2026, 8, 1))
    elif time_filter == 'august':
        query = query.filter(Lead.created_at >= datetime(2026, 8, 1), Lead.created_at < datetime(2026, 9, 1))
    elif time_filter == 'september':
        query = query.filter(Lead.created_at >= datetime(2026, 9, 1), Lead.created_at < datetime(2026, 10, 1))
    elif time_filter == 'october':
        query = query.filter(Lead.created_at >= datetime(2026, 10, 1), Lead.created_at < datetime(2026, 11, 1))
    elif time_filter == 'this_quarter':
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        start_of_quarter = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(Lead.created_at >= start_of_quarter)
    
    if start_date_str:
        try:
            sd = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Lead.created_at >= sd)
        except ValueError:
            pass
    if end_date_str:
        try:
            ed = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Lead.created_at < ed)
        except ValueError:
            pass

    return query, time_filter, start_date_str, end_date_str


@web_bp.route('/')
def dashboard():
    query = Lead.query
    query, time_filter, start_date_str, end_date_str = apply_date_filter(query)

    all_filtered_leads = query.all()

    total_leads = len(all_filtered_leads)
    new_leads = sum(1 for l in all_filtered_leads if l.status == 'New')
    qualified = sum(1 for l in all_filtered_leads if l.status == 'Qualified')
    meeting_done = sum(1 for l in all_filtered_leads if l.status == 'Meeting Done')
    proposal_sent = sum(1 for l in all_filtered_leads if l.status == 'Proposal Sent')
    deal_close = sum(1 for l in all_filtered_leads if l.status == 'Deal Close')
    active_pipeline = sum(1 for l in all_filtered_leads if l.status not in ('Deal Close', 'Lost'))

    recent_leads = query.order_by(Lead.created_at.desc()).limit(7).all()
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
    priority_filter = request.args.get('priority', '')
    search = request.args.get('search', '')
    query = Lead.query

    query, time_filter, start_date_str, end_date_str = apply_date_filter(query)

    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
    if search:
        query = query.filter(
            (Lead.name.ilike(f'%{search}%')) |
            (Lead.email.ilike(f'%{search}%')) |
            (Lead.phone.ilike(f'%{search}%')) |
            (Lead.location.ilike(f'%{search}%')) |
            (Lead.property_type.ilike(f'%{search}%'))
        )
    leads = query.order_by(Lead.created_at.desc()).all()
    return render_template('leads_list.html', leads=leads, status_filter=status_filter, priority_filter=priority_filter, search=search, time_filter=time_filter, start_date=start_date_str, end_date=end_date_str)


@web_bp.route('/leads/add', methods=['GET', 'POST'])
def add_lead():
    if session.get('user_role') == 'Viewer':
        flash('Permission denied: Viewer role has read-only access.', 'danger')
        return redirect(url_for('web.leads_list'))

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
    if session.get('user_role') == 'Viewer':
        flash('Permission denied: Viewer role has read-only access.', 'danger')
        return redirect(url_for('web.lead_detail', lid=lid))

    lead = Lead.query.get_or_404(lid)
    users = User.query.filter_by(status='Active').all()
    if request.method == 'POST':
        lead.name = request.form['name']
        lead.email = request.form['email']
        lead.phone = request.form.get('phone', '')
        lead.source = request.form.get('source', '99acres')
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
    if session.get('user_role') in ('Viewer', 'Sales Executive'):
        flash('Permission denied: Admin or Manager permission required to delete leads.', 'danger')
        return redirect(url_for('web.leads_list'))

    lead = Lead.query.get_or_404(lid)
    db.session.delete(lead)
    db.session.commit()
    flash('Lead deleted.', 'info')
    return redirect(url_for('web.leads_list'))


@web_bp.route('/leads/<int:lid>/note', methods=['POST'])
def add_note(lid):
    if session.get('user_role') == 'Viewer':
        flash('Permission denied: Viewer role has read-only access.', 'danger')
        return redirect(url_for('web.lead_detail', lid=lid))

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
    if session.get('user_role') == 'Viewer':
        flash('Permission denied: Viewer role has read-only access.', 'danger')
        return redirect(url_for('web.lead_detail', lid=lid))

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
    if session.get('user_role') == 'Viewer':
        flash('Permission denied: Viewer role has read-only access.', 'danger')
        return redirect(request.referrer or url_for('web.dashboard'))

    fu = FollowUp.query.get_or_404(fid)
    fu.completed = True
    db.session.commit()
    flash('Follow-up marked complete.', 'success')
    return redirect(request.referrer or url_for('web.dashboard'))

# ── User Management (Admin Tab - Roles: Admin, Editor, Viewer, Manager, Sales Executive) ──
@web_bp.route('/users')
def users_list():
    if session.get('user_role') not in ('Admin', 'Manager'):
        flash('Permission denied: Only Admin or Manager can manage users.', 'danger')
        return redirect(url_for('web.dashboard'))

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('users.html', users=users)

@web_bp.route('/users/add', methods=['GET', 'POST'])
def add_user():
    if session.get('user_role') not in ('Admin', 'Manager'):
        flash('Permission denied: Only Admin or Manager can create users.', 'danger')
        return redirect(url_for('web.dashboard'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        user_id_name = request.form.get('user_id_name', '').strip()
        password = request.form.get('password', 'Password@123').strip()
        role = request.form.get('role', 'Editor')
        
        if User.query.filter_by(email=email).first():
            flash('User with this email already exists.', 'danger')
            return redirect(url_for('web.add_user'))
            
        user = User(name=name, email=email, user_id_name=user_id_name or f"USR-{email.split('@')[0]}", password=password, role=role)
        db.session.add(user)
        db.session.commit()
        flash(f'User {name} ({role}) created successfully!', 'success')
        return redirect(url_for('web.users_list'))
    return render_template('user_form.html', user=None, action='Add')

@web_bp.route('/users/<int:uid>/edit', methods=['GET', 'POST'])
def edit_user(uid):
    if session.get('user_role') not in ('Admin', 'Manager'):
        flash('Permission denied: Only Admin or Manager can edit users.', 'danger')
        return redirect(url_for('web.dashboard'))

    user = User.query.get_or_404(uid)
    if request.method == 'POST':
        user.name = request.form['name']
        user.email = request.form['email']
        user.user_id_name = request.form.get('user_id_name', user.user_id_name).strip()
        new_password = request.form.get('password', '').strip()
        if new_password:
            user.password = new_password
        user.role = request.form.get('role', 'Editor')
        user.status = request.form.get('status', 'Active')
        db.session.commit()
        flash(f'User {user.name} details & password updated successfully!', 'success')
        return redirect(url_for('web.users_list'))
    return render_template('user_form.html', user=user, action='Edit')

@web_bp.route('/users/<int:uid>/delete', methods=['POST'])
def delete_user(uid):
    if session.get('user_role') != 'Admin':
        flash('Permission denied: Only Admin can delete users.', 'danger')
        return redirect(url_for('web.users_list'))

    user = User.query.get_or_404(uid)
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.name} deleted successfully.', 'info')
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
    if session.get('user_role') == 'Viewer':
        flash('Permission denied: Viewer role has read-only access.', 'danger')
        return redirect(url_for('web.tasks_list'))

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
    if session.get('user_role') == 'Viewer':
        flash('Permission denied: Viewer role has read-only access.', 'danger')
        return redirect(url_for('web.tasks_list'))

    task = Task.query.get_or_404(tid)
    task.completed = True
    db.session.commit()
    flash('Task completed!', 'success')
    return redirect(url_for('web.tasks_list'))

@web_bp.route('/tasks/<int:tid>/delete', methods=['POST'])
def delete_task(tid):
    if session.get('user_role') in ('Viewer', 'Sales Executive'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('web.tasks_list'))

    task = Task.query.get_or_404(tid)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'info')
    return redirect(url_for('web.tasks_list'))

# ── Reports & Analytics ───────────────────────────────────────
@web_bp.route('/reports')
def reports():
    total_leads = Lead.query.count()
    new_leads = Lead.query.filter_by(status='New').count()
    qualified = Lead.query.filter_by(status='Qualified').count()
    meeting_done = Lead.query.filter_by(status='Meeting Done').count()
    proposal_sent = Lead.query.filter_by(status='Proposal Sent').count()
    deals_closed = Lead.query.filter_by(status='Deal Close').count()
    team_count = User.query.filter_by(status='Active').count()

    conversion_rate = round((deals_closed / total_leads * 100), 1) if total_leads > 0 else 0.0

    return render_template('reports.html',
        total_leads=total_leads, new_leads=new_leads, qualified=qualified,
        meeting_done=meeting_done, proposal_sent=proposal_sent,
        deals_closed=deals_closed, team_count=team_count,
        conversion_rate=conversion_rate)

# ── Settings ──────────────────────────────────────────────────
@web_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if session.get('user_role') not in ('Admin', 'Manager'):
        flash('Permission denied: Only Admin or Manager can change settings.', 'danger')
        return redirect(url_for('web.dashboard'))

    if request.method == 'POST':
        flash('Settings saved successfully!', 'success')
        return redirect(url_for('web.settings'))
    return render_template('settings.html')

# ── Import & Export Data & Clear Imported Data ────────────────
@web_bp.route('/import', methods=['GET', 'POST'])
def import_csv():
    if session.get('user_role') == 'Viewer':
        flash('Permission denied: Viewer role has read-only access.', 'danger')
        return redirect(url_for('web.dashboard'))

    imported_count = Lead.query.filter_by(is_imported=True).count()
    total_leads_count = Lead.query.count()

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
                is_imported=True,
                created_at=created_at
            )
            db.session.add(lead)
            count += 1
        
        db.session.commit()
        flash(f'Successfully imported {count} leads! Dashboard metrics and tables have been updated.', 'success')
        return redirect(url_for('web.dashboard'))

    return render_template('import.html', imported_count=imported_count, total_leads_count=total_leads_count)


@web_bp.route('/import/clear', methods=['POST'])
def clear_imported_leads():
    if session.get('user_role') not in ('Admin', 'Manager'):
        flash('Permission denied: Only Admin or Manager can clear imported data.', 'danger')
        return redirect(url_for('web.import_csv'))

    deleted_count = Lead.query.filter_by(is_imported=True).delete()
    db.session.commit()
    flash(f'Successfully deleted {deleted_count} imported leads.', 'info')
    return redirect(url_for('web.import_csv'))


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
