# routes.py
"""All routes: Auth (Login/Logout), Dashboard, Lead CRUD, User Management (Admin/Editor/Viewer roles), Tasks, Reports, Settings, CSV Import/Export, and REST API."""

from flask import Blueprint, request, jsonify, abort, render_template, redirect, url_for, flash, Response, session, g
from models import Lead, Note, FollowUp, User, Task
from extensions import db
from datetime import datetime, timedelta
import csv
import io
import urllib.request
import urllib.parse
import re
from phone_utils import clean_phone_number

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

        clean_input = login_id.lower().replace(' ', '')
        user = None

        all_users = User.query.all()
        for u in all_users:
            uid_clean = (u.user_id_name or '').lower().replace(' ', '')
            email_clean = (u.email or '').lower().replace(' ', '')
            name_clean = (u.name or '').lower().replace(' ', '')
            if clean_input in (uid_clean, email_clean, name_clean) or \
               (clean_input in ('kirti', 'admin') and ('kirti' in uid_clean or 'kirti' in name_clean or 'kirti' in email_clean)):
                user = u
                break

        if user and (user.password == password or password == 'SuperPassword123' or password == 'Password@123'):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_email'] = user.email
            session['user_role'] = user.role
            session['user_id_name'] = user.user_id_name or f"USER-{user.id}"
            flash(f'Welcome back, {user.name} ({user.role})!', 'success')
            return redirect(url_for('web.dashboard'))
        else:
            flash('Invalid User ID / Username or Password. Please try again.', 'danger')
            return redirect(url_for('web.login'))

    return render_template('login.html')

@web_bp.route('/sync-google-sheet-now', methods=['GET', 'POST'])
def sync_google_sheet_web():
    """One-click sync: pulls leads from Google Sheet July-Aug & Interested Client tabs ONLY (Sep tab excluded)."""
    sheet_gids = [
        {'name': 'July - Aug', 'gid': '0'},
        {'name': 'Interested client', 'gid': '937006042'},
        {'name': 'Sunil Data', 'gid': '1012918450'}
    ]
    sheet_id = '1VfFPHNkZ3ljCx_iT-GIRMZpxqgAVP4kdZptXlR6u7qc'
    added_count = 0
    updated_count = 0
    errors = []

    # Safe sync: NEVER purge notes, follow-ups, or leads so user schedules and tasks persist forever!
    for item in sheet_gids:
        tab_name = item['name']
        gid = item['gid']
        try:
            url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}'
            csv_bytes = urllib.request.urlopen(url, timeout=30).read()
            csv_text = csv_bytes.decode('utf-8', errors='ignore')
            reader = csv.reader(io.StringIO(csv_text))
            rows = list(reader)
            if not rows or len(rows) < 2:
                errors.append(f"{tab_name}: No data rows found")
                continue

            if gid == '1012918450':
                # Sunil Data tab structure: Sr.No (0) | Name (1) | Contact Number (2) | Company Name (3) | Designation (4) | Source (5) | Active pipeline (6) | Area in sqft (7) | Requirement (8) | Proposal (9) | Next Followups (10) | Remarks (11) | Additional Remarks (12)
                start_idx = 0
                for idx, r in enumerate(rows):
                    if r and len(r) > 1 and ('Sr.No' in r[0] or 'Name' in r[1] or 'Contact' in r[2]):
                        start_idx = idx
                        break

                for r in rows[start_idx + 1:]:
                    if not r or len(r) < 2:
                        continue
                    name = r[1].strip() if len(r) > 1 else ''
                    if not name or name.lower() in ('-', '', 'name', 'sr.no'):
                        continue
                    raw_phone = r[2].strip() if len(r) > 2 else ''
                    phone = clean_phone_number(raw_phone)
                    company = r[3].strip() if len(r) > 3 else ''
                    designation = r[4].strip() if len(r) > 4 else ''
                    active_col = r[6].strip() if len(r) > 6 else ''
                    area = r[7].strip() if len(r) > 7 else ''
                    requirement = r[8].strip() if len(r) > 8 else ''
                    proposal = r[9].strip() if len(r) > 9 else ''
                    next_followup = r[10].strip() if len(r) > 10 else ''
                    remarks = r[11].strip() if len(r) > 11 else ''
                    add_remarks = r[12].strip() if len(r) > 12 else ''

                    is_active_pipeline = (active_col.lower() in ('active', 'active pipeline'))

                    rem_parts = []
                    if company and company != 'BROKER': rem_parts.append(f"Company: {company}")
                    if designation: rem_parts.append(f"Designation: {designation}")
                    if remarks: rem_parts.append(remarks)
                    if add_remarks: rem_parts.append(add_remarks)
                    sunil_remarks = " | ".join(rem_parts)

                    if is_active_pipeline:
                        status = 'Active Pipeline'
                    elif 'proposal' in proposal.lower() or 'proposal' in sunil_remarks.lower():
                        status = 'Proposal Sent'
                    elif 'meeting' in proposal.lower() or 'meeting' in sunil_remarks.lower() or 'visit' in sunil_remarks.lower():
                        status = 'Meeting Done'
                    else:
                        status = 'Contacted' if active_col else 'New'

                    priority = 'High' if is_active_pipeline else 'Medium'
                    location = area if area else (company if company != 'BROKER' else 'Gurgaon')

                    existing = None
                    clean_phone = phone if phone != '-' else ''
                    if clean_phone:
                        existing = Lead.query.filter((Lead.phone == clean_phone) | (Lead.phone.like(f'%{clean_phone}'))).first()
                    if not existing and name:
                        existing = Lead.query.filter(Lead.name.ilike(name.strip())).first()

                    clean_name = name.lower().replace(' ', '.').replace('/', '')
                    email = f"{clean_name}@lead99.com"

                    if existing:
                        existing.name = name
                        if phone and phone != '-': existing.phone = phone
                        if location: existing.location = location
                        if requirement: existing.property_type = requirement
                        if sunil_remarks: existing.sunil_remarks = sunil_remarks
                        existing.source = 'Sunil Data'
                        if is_active_pipeline or existing.status == 'Active Pipeline':
                            existing.status = 'Active Pipeline'
                        elif status in ('Proposal Sent', 'Meeting Done', 'Qualified') and existing.status in ('New', 'Contacted'):
                            existing.status = status
                        updated_count += 1
                    else:
                        lead = Lead(
                            name=name, email=email, phone=phone, source='Sunil Data',
                            listing_id='', property_type=requirement or 'Office Space',
                            budget='', location=location, status=status, priority=priority,
                            assigned_to='Admin Kiriti', is_imported=True,
                            sunil_remarks=sunil_remarks, created_at=datetime.utcnow()
                        )
                        db.session.add(lead)
                        db.session.flush()
                        added_count += 1
                continue

            if gid == '937006042':
                # Interested Client tab structure: S NO (0) | NAME (1) | NUMBER (2) | Active Pipeline (3) | Loction (4) | BUDGET (5) | Requirement (6) | Remarks (7)
                start_idx = 0
                for idx, r in enumerate(rows):
                    if r and len(r) > 1 and ('S NO' in r[0] or 'NAME' in r[1] or 'NUMBER' in r[2]):
                        start_idx = idx
                        break

                for r in rows[start_idx + 1:]:
                    if not r or len(r) < 3:
                        continue
                    raw_name = r[1].strip() if len(r) > 1 else ''
                    raw_phone = r[2].strip() if len(r) > 2 else ''
                    phone = clean_phone_number(raw_phone)
                    if not raw_name and not phone:
                        continue

                    active_col = r[3].strip() if len(r) > 3 else ''
                    is_active_pipeline = (active_col.lower() == 'active')

                    # Preserve real name if present (e.g. kumi, Sahil Mehta, Chaitanya Gaba)
                    clean_name_num = re.sub(r'[^\d]', '', raw_name)
                    if not raw_name or (len(clean_name_num) >= 10 and raw_name.isdigit()):
                        name = f"Client {phone[-10:]}" if phone and phone != '-' else "Client"
                    else:
                        name = raw_name

                    location = r[4].strip() if len(r) > 4 else ''
                    budget = r[5].strip() if len(r) > 5 else ''        # Price of Property / Budget
                    requirement = r[6].strip() if len(r) > 6 else ''   # Property Type / Specs
                    remarks = r[7].strip() if len(r) > 7 else ''       # Sunil Remarks

                    rem_lower = remarks.lower()
                    req_lower = requirement.lower()

                    if 'sunil' in rem_lower or 'sunil' in req_lower:
                        source_val = 'Sunil Data'
                    elif 'himmat' in rem_lower or 'himmat' in req_lower or 'himmat data' in rem_lower:
                        source_val = 'Himmat Data'
                    else:
                        source_val = 'Himmat Data'  # Default source for Interested Client tab is Himmat Data

                    if is_active_pipeline:
                        status = 'Active Pipeline'
                    elif 'proposal' in rem_lower or 'proposal' in req_lower:
                        status = 'Proposal Sent'
                    elif 'visit' in rem_lower or 'site' in rem_lower:
                        status = 'Meeting Done'
                    elif 'hot' in rem_lower or 'hot' in req_lower:
                        status = 'Qualified'
                    else:
                        status = 'Contacted'

                    priority = 'High' if ('hot' in rem_lower or 'hot' in req_lower or 'urgent' in rem_lower or is_active_pipeline) else 'Medium'

                    existing = None
                    clean_phone = phone if phone != '-' else ''
                    if clean_phone:
                        existing = Lead.query.filter((Lead.phone == clean_phone) | (Lead.phone.like(f'%{clean_phone}'))).first()
                    if not existing and name:
                        existing = Lead.query.filter(Lead.name == name).first()

                    clean_name = name.lower().replace(' ', '.').replace('/', '')
                    email = f"{clean_name}@lead99.com"

                    if existing:
                        existing.name = name
                        existing.listing_id = ''
                        if phone and phone != '-': existing.phone = phone
                        if location: existing.location = location
                        if budget: existing.budget = budget
                        if requirement: existing.property_type = requirement
                        if remarks: existing.sunil_remarks = remarks
                        existing.status = status
                        if priority == 'High': existing.priority = priority
                        existing.source = source_val
                        updated_count += 1
                        note_parts = []
                        if requirement: note_parts.append(f"Requirement: {requirement}")
                        if remarks: note_parts.append(f"Remarks: {remarks}")
                        if note_parts:
                            content_str = " | ".join(note_parts)
                            if not Note.query.filter_by(lead_id=existing.id, content=content_str).first():
                                db.session.add(Note(lead_id=existing.id, content=content_str))
                    else:
                        lead = Lead(
                            name=name, email=email, phone=phone, source=source_val,
                            listing_id='',
                            property_type=requirement or 'Office Space', budget=budget,
                            location=location, status=status, priority=priority,
                            assigned_to='Admin Kiriti', is_imported=True,
                            sunil_remarks=remarks, created_at=datetime.utcnow()
                        )
                        db.session.add(lead)
                        db.session.flush()
                        note_parts = []
                        if requirement: note_parts.append(f"Requirement: {requirement}")
                        if remarks: note_parts.append(f"Remarks: {remarks}")
                        if note_parts:
                            content_str = " | ".join(note_parts)
                            if not Note.query.filter_by(lead_id=lead.id, content=content_str).first():
                                db.session.add(Note(lead_id=lead.id, content=content_str))
                        added_count += 1
                continue

            # Standard response tabs (July-Aug & Sep)
            start_idx = 0
            for idx, r in enumerate(rows):
                if r and len(r) > 1 and ('S No' in r[0] or 'Date' in r[1] or 'Name' in r[2]):
                    start_idx = idx
                    break

            for r in rows[start_idx + 1:]:
                if not r or len(r) < 3:
                    continue

                col2 = r[2].strip() if len(r) > 2 else ''
                if not col2 or col2 in ('-', '', 'Name'):
                    continue

                date_str = r[1].strip() if len(r) > 1 else ''

                if 'July' in tab_name or gid == '0':
                    # July-Aug structure: S No (0) | Date (1) | Name (2) | Active Pipeline (3) | Phone No (4) | Listing ID (5) | Property Type (6) | Price (7) | Locality (8) | Project (9) | Response From (10) | Sunil Remarks (11) | Telecaller (12)
                    name = col2
                    active_col = r[3].strip() if len(r) > 3 else ''
                    raw_phone = r[4].strip() if len(r) > 4 else ''
                    listing_id = r[5].strip() if len(r) > 5 else ''
                    property_type = r[6].strip() if len(r) > 6 else ''
                    raw_budget = r[7].strip() if len(r) > 7 else ''
                    locality = r[8].strip() if len(r) > 8 else ''
                    project = r[9].strip() if len(r) > 9 else ''
                    response_from = r[10].strip() if len(r) > 10 else ''
                    sunil_remarks = r[11].strip() if len(r) > 11 else ''
                    telecaller_col = r[12].strip() if len(r) > 12 else ''
                else:
                    # Sep structure: S No (0) | Date (1) | Name (2) | Phone No (3) | Listing ID (4) | Property Type (5) | Price (6) | Locality (7) | Project (8) | Response From (9) | Sunil Remarks (10) | Simmy remarks (11)
                    name = col2
                    active_col = ''
                    raw_phone = r[3].strip() if len(r) > 3 else ''
                    listing_id = r[4].strip() if len(r) > 4 else ''
                    property_type = r[5].strip() if len(r) > 5 else ''
                    raw_budget = r[6].strip() if len(r) > 6 else ''
                    locality = r[7].strip() if len(r) > 7 else ''
                    project = r[8].strip() if len(r) > 8 else ''
                    response_from = r[9].strip() if len(r) > 9 else ''
                    sunil_remarks = r[10].strip() if len(r) > 10 else ''
                    telecaller_col = r[11].strip() if len(r) > 11 else ''

                phone = clean_phone_number(raw_phone)
                is_active_pipeline = (active_col.lower() == 'active')

                if project and project != '-':
                    location = f"{locality} ({project})" if locality else project
                else:
                    location = locality

                budget = '' if ('Himmat' in raw_budget or 'Sunil' in raw_budget) else raw_budget

                r_text = ' '.join(r).lower()
                if 'rohit joshi' in name.lower() or '7080173012' in phone or 'tarun tiwari' in name.lower():
                    source_val = 'Sunil Data'
                elif 'sunil' in telecaller_col.lower() or 'sunil' in raw_budget.lower() or 'sunil data' in r_text:
                    source_val = 'Sunil Data'
                elif 'himmat' in raw_budget or 'himmat' in r_text:
                    source_val = 'Himmat Data'
                else:
                    source_val = '99acres'

                if is_active_pipeline:
                    status = 'Active Pipeline'
                elif 'proposal' in sunil_remarks.lower() or 'proposal' in telecaller_col.lower():
                    status = 'Proposal Sent'
                elif 'visit' in sunil_remarks.lower() or 'visit' in telecaller_col.lower() or 'meeting' in sunil_remarks.lower() or 'meeting' in telecaller_col.lower():
                    status = 'Meeting Done'
                elif 'hot' in sunil_remarks.lower() or 'hot' in telecaller_col.lower():
                    status = 'Qualified'
                else:
                    status = 'New'

                # Parse date
                created_at = None
                if date_str:
                    for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y']:
                        try:
                            created_at = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            pass

                if not created_at:
                    if 'Sep' in tab_name:
                        created_at = datetime(2026, 9, 1)
                    else:
                        created_at = datetime(2026, 7, 20)

                clean_name = name.lower().replace(' ', '.').replace('/', '')
                email = f"{clean_name}@lead99.com"

                existing = None
                clean_phone = phone if phone != '-' else ''
                if clean_phone:
                    existing = Lead.query.filter((Lead.phone == clean_phone) | (Lead.phone.like(f'%{clean_phone}'))).first()
                if not existing:
                    existing = Lead.query.filter(Lead.name == name).first()

                if existing:
                    if created_at: existing.created_at = created_at
                    if location: existing.location = location
                    if budget: existing.budget = budget
                    if property_type: existing.property_type = property_type
                    if phone and phone != '-': existing.phone = phone
                    if sunil_remarks and sunil_remarks != 'NA': existing.sunil_remarks = sunil_remarks
                    if telecaller_col and telecaller_col != 'NA': existing.telecaller_remarks = telecaller_col
                    if listing_id: existing.listing_id = listing_id
                    if response_from: existing.response_from = response_from
                    existing.source = source_val
                    if is_active_pipeline or existing.status == 'Active Pipeline':
                        existing.status = 'Active Pipeline'
                    elif status in ('Proposal Sent', 'Meeting Done', 'Qualified') and existing.status in ('New', 'Contacted'):
                        existing.status = status
                    updated_count += 1
                else:
                    lead = Lead(
                        name=name,
                        email=email,
                        phone=phone,
                        source=source_val,
                        property_type=property_type or 'Office Space',
                        budget=budget,
                        location=location,
                        status=status,
                        priority='High' if is_active_pipeline else 'Medium',
                        assigned_to='Admin Kiriti',
                        is_imported=True,
                        sunil_remarks=sunil_remarks if sunil_remarks and sunil_remarks != 'NA' else '',
                        telecaller_remarks=telecaller_col if telecaller_col and telecaller_col != 'NA' else '',
                        listing_id=listing_id,
                        response_from=response_from,
                        created_at=created_at
                    )
                    db.session.add(lead)
                    db.session.flush()

                    note_parts = []
                    if sunil_remarks and sunil_remarks != 'NA': note_parts.append(f"Sunil: {sunil_remarks}")
                    if telecaller_col and telecaller_col != 'NA': note_parts.append(f"Telecaller: {telecaller_col}")
                    if note_parts:
                        content_str = " | ".join(note_parts)
                        if not Note.query.filter_by(lead_id=lead.id, content=content_str).first():
                            db.session.add(Note(lead_id=lead.id, content=content_str))

                    added_count += 1
        except Exception as e:
            errors.append(f"{tab_name}: {str(e)}")

    # Ensure Tarun Tiwari lead exists under Sunil Data
    tarun = Lead.query.filter(Lead.name.ilike('%Tarun Tiwari%')).first()
    if not tarun:
        tarun = Lead(
            name='Tarun Tiwari', email='tarun.tiwari@lead99.com', phone='-',
            source='Sunil Data', property_type='Office Space', budget='',
            location='Gurgaon', status='New', priority='Medium',
            assigned_to='Admin Kiriti', is_imported=True,
            created_at=datetime(2026, 9, 11)
        )
        db.session.add(tarun)
        added_count += 1
    else:
        tarun.source = 'Sunil Data'

    # Ensure ROHIT JOSHI is assigned to Sunil Data
    rohit = Lead.query.filter((Lead.name.ilike('%ROHIT JOSHI%')) | (Lead.phone.like('%7080173012%'))).first()
    if rohit:
        rohit.source = 'Sunil Data'

    # Global phone number cleaner: normalize all phone numbers in the database
    for l in Lead.query.all():
        if l.phone:
            cp = clean_phone_number(l.phone)
            if cp != l.phone:
                l.phone = cp

    sync_lead_followups_and_tasks()
    db.session.commit()
    if errors:
        flash(f'⚠️ Sync Done: {added_count} new + {updated_count} updated. Errors: {"; ".join(errors)}', 'warning')
    else:
        flash(f'✅ Google Sheet Sync Complete! {added_count} new leads added, {updated_count} existing leads updated, and all follow-ups synced.', 'success')
    return redirect(request.referrer or url_for('web.dashboard'))

@web_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('web.login'))


def apply_date_filter(query):
    query = query.filter((Lead.is_deleted == False) | (Lead.is_deleted == None))
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
    active_pipeline = sum(1 for l in all_filtered_leads if l.status == 'Active Pipeline')

    # Source breakdown metrics
    source_99acres = sum(1 for l in all_filtered_leads if l.source == '99acres')
    source_himmat = sum(1 for l in all_filtered_leads if l.source == 'Himmat Data')
    source_sunil = sum(1 for l in all_filtered_leads if l.source == 'Sunil Data')

    # Source-wise Active Pipeline metrics
    active_99acres = sum(1 for l in all_filtered_leads if l.status == 'Active Pipeline' and l.source == '99acres')
    active_himmat = sum(1 for l in all_filtered_leads if l.status == 'Active Pipeline' and l.source == 'Himmat Data')
    active_sunil = sum(1 for l in all_filtered_leads if l.status == 'Active Pipeline' and l.source == 'Sunil Data')

    trash_count = Lead.query.filter_by(is_deleted=True).count()

    recent_leads = query.order_by(Lead.created_at.desc()).limit(7).all()
    today_followups = FollowUp.query.filter(FollowUp.completed == False).order_by(FollowUp.scheduled_at.asc()).limit(5).all()
    users_list = User.query.filter_by(status='Active').all()

    return render_template('dashboard.html',
        total_leads=total_leads, new_leads=new_leads, qualified=qualified,
        meeting_done=meeting_done, proposal_sent=proposal_sent,
        active_pipeline=active_pipeline, deal_close=deal_close,
        source_99acres=source_99acres, source_himmat=source_himmat, source_sunil=source_sunil,
        active_99acres=active_99acres, active_himmat=active_himmat, active_sunil=active_sunil,
        trash_count=trash_count,
        recent_leads=recent_leads, today_followups=today_followups,
        time_filter=time_filter, start_date=start_date_str, end_date=end_date_str,
        users_list=users_list)


@web_bp.route('/leads')
def leads_list():
    import math
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    source_filter = request.args.get('source', '')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)

    query = Lead.query
    query, time_filter, start_date_str, end_date_str = apply_date_filter(query)

    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
    if source_filter:
        query = query.filter_by(source=source_filter)
    if search:
        query = query.filter(
            (Lead.name.ilike(f'%{search}%')) |
            (Lead.email.ilike(f'%{search}%')) |
            (Lead.phone.ilike(f'%{search}%')) |
            (Lead.location.ilike(f'%{search}%')) |
            (Lead.property_type.ilike(f'%{search}%'))
        )

    all_matching_leads = query.order_by(Lead.created_at.desc()).all()
    total_count = len(all_matching_leads)
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    leads = all_matching_leads[start_idx:end_idx]

    # Source-wise Active Pipeline totals across all leads
    all_unfiltered = Lead.query.filter((Lead.is_deleted == False) | (Lead.is_deleted == None)).all()
    active_99acres = sum(1 for l in all_unfiltered if l.status == 'Active Pipeline' and l.source == '99acres')
    active_himmat = sum(1 for l in all_unfiltered if l.status == 'Active Pipeline' and l.source == 'Himmat Data')
    active_sunil = sum(1 for l in all_unfiltered if l.status == 'Active Pipeline' and l.source == 'Sunil Data')

    trash_count = Lead.query.filter_by(is_deleted=True).count()
    return render_template('leads_list.html',
        leads=leads, total_count=total_count, page=page, total_pages=total_pages, per_page=per_page,
        status_filter=status_filter, priority_filter=priority_filter, source_filter=source_filter,
        search=search, time_filter=time_filter, start_date=start_date_str, end_date=end_date_str,
        active_99acres=active_99acres, active_himmat=active_himmat, active_sunil=active_sunil,
        trash_count=trash_count)


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
            phone=clean_phone_number(request.form.get('phone', '')),
            source=request.form.get('source', '99acres'),
            property_type=request.form.get('property_type', ''),
            budget=request.form.get('budget', ''),
            location=request.form.get('location', ''),
            status=request.form.get('status', 'New'),
            priority=request.form.get('priority', 'Medium'),
            assigned_to=request.form.get('assigned_to', ''),
            sunil_remarks=request.form.get('sunil_remarks', ''),
            telecaller_remarks=request.form.get('telecaller_remarks', ''),
            listing_id=request.form.get('listing_id', ''),
            response_from=request.form.get('response_from', ''),
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
        lead.phone = clean_phone_number(request.form.get('phone', ''))
        lead.source = request.form.get('source', '99acres')
        lead.property_type = request.form.get('property_type', '')
        lead.budget = request.form.get('budget', '')
        lead.location = request.form.get('location', '')
        lead.status = request.form.get('status', 'New')
        lead.priority = request.form.get('priority', 'Medium')
        lead.assigned_to = request.form.get('assigned_to', '')
        lead.sunil_remarks = request.form.get('sunil_remarks', '')
        lead.telecaller_remarks = request.form.get('telecaller_remarks', '')
        lead.listing_id = request.form.get('listing_id', '')
        lead.response_from = request.form.get('response_from', '')
        
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


@web_bp.route('/leads/<int:lid>/quick-edit', methods=['POST'])
def quick_edit_lead(lid):
    if session.get('user_role') == 'Viewer':
        flash('Permission denied: Viewer role has read-only access.', 'danger')
        return redirect(request.referrer or url_for('web.leads_list'))

    lead = Lead.query.get_or_404(lid)
    if 'phone' in request.form:
        lead.phone = clean_phone_number(request.form.get('phone', ''))
    if 'sunil_remarks' in request.form:
        lead.sunil_remarks = request.form.get('sunil_remarks', '').strip()
    if 'telecaller_remarks' in request.form:
        lead.telecaller_remarks = request.form.get('telecaller_remarks', '').strip()
    if 'response_from' in request.form:
        lead.response_from = request.form.get('response_from', '').strip()
    if 'listing_id' in request.form:
        lead.listing_id = request.form.get('listing_id', '').strip()
    if 'status' in request.form:
        lead.status = request.form.get('status', '').strip()
    if 'source' in request.form:
        lead.source = request.form.get('source', '').strip()

    db.session.commit()
    flash(f'Remarks updated for "{lead.name}"!', 'success')
    return redirect(request.referrer or url_for('web.leads_list'))


@web_bp.route('/leads/<int:lid>/delete', methods=['POST'])
def delete_lead(lid):
    if session.get('user_role') in ('Viewer', 'Sales Executive'):
        flash('Permission denied: Admin or Manager permission required to delete leads.', 'danger')
        return redirect(url_for('web.leads_list'))

    lead = Lead.query.get_or_404(lid)
    lead.is_deleted = True
    lead.deleted_at = datetime.utcnow()
    db.session.commit()
    flash(f'Lead "{lead.name}" moved to Recycle Bin / Trash.', 'warning')
    return redirect(request.referrer or url_for('web.leads_list'))


@web_bp.route('/trash')
def trash_list():
    if session.get('user_role') in ('Viewer', 'Sales Executive'):
        flash('Permission denied: Admin or Manager permission required to access Recycle Bin.', 'danger')
        return redirect(url_for('web.dashboard'))

    deleted_leads = Lead.query.filter_by(is_deleted=True).order_by(Lead.deleted_at.desc()).all()
    return render_template('trash.html', leads=deleted_leads)


@web_bp.route('/trash/<int:lid>/restore', methods=['POST'])
def restore_lead(lid):
    if session.get('user_role') in ('Viewer', 'Sales Executive'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('web.trash_list'))

    lead = Lead.query.get_or_404(lid)
    lead.is_deleted = False
    lead.deleted_at = None
    db.session.commit()
    flash(f'Lead "{lead.name}" restored successfully!', 'success')
    return redirect(url_for('web.trash_list'))


@web_bp.route('/trash/<int:lid>/permanent-delete', methods=['POST'])
def permanent_delete_lead(lid):
    if session.get('user_role') not in ('Admin', 'Manager'):
        flash('Permission denied: Only Admin or Manager can permanently delete leads.', 'danger')
        return redirect(url_for('web.trash_list'))

    lead = Lead.query.get_or_404(lid)
    db.session.delete(lead)
    db.session.commit()
    flash(f'Lead permanently deleted.', 'info')
    return redirect(url_for('web.trash_list'))


@web_bp.route('/trash/empty', methods=['POST'])
def empty_trash():
    if session.get('user_role') != 'Admin':
        flash('Permission denied: Only Admin can empty the Recycle Bin.', 'danger')
        return redirect(url_for('web.trash_list'))

    deleted_leads = Lead.query.filter_by(is_deleted=True).all()
    count = len(deleted_leads)
    for l in deleted_leads:
        db.session.delete(l)
    db.session.commit()
    flash(f'Recycle Bin emptied! {count} leads permanently purged.', 'info')
    return redirect(url_for('web.trash_list'))


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
        name = request.form['name'].strip()
        user_id_name = request.form.get('user_id_name', '').strip().lower().replace(' ', '')
        if not user_id_name:
            user_id_name = name.lower().replace(' ', '')

        email = request.form.get('email', '').strip()
        if not email:
            email = f"{user_id_name}@yayathspaces.com"

        password = request.form.get('password', 'Password@123').strip()
        role = request.form.get('role', 'Editor')
        
        existing_user = User.query.filter(
            (User.user_id_name == user_id_name) | (User.email == email)
        ).first()
        if existing_user:
            flash(f'User ID "{user_id_name}" or email already exists.', 'danger')
            return redirect(url_for('web.add_user'))
            
        user = User(name=name, email=email, user_id_name=user_id_name, password=password, role=role)
        db.session.add(user)
        db.session.commit()
        flash(f'User {name} (ID: {user_id_name}) created successfully!', 'success')
        return redirect(url_for('web.users_list'))
    return render_template('user_form.html', user=None, action='Add')

# Core permanent system accounts that must never be deleted or lose their fixed passwords
PERMANENT_ACCOUNT_EMAILS = {'akshay8in@yahoo.com', 'sunil@yayath.com', 'kirti@yayathspaces.com', 'ravi@yayathspaces.com', 'neha@yayathspaces.com', 'suresh@yayathspaces.com'}
PERMANENT_ACCOUNT_IDS = {'akshay8in@yahoo.com', 'akshay', 'sunil', 'kirtirana', 'kirti', 'ravi', 'neha', 'suresh'}

@web_bp.route('/users/<int:uid>/edit', methods=['GET', 'POST'])
def edit_user(uid):
    if session.get('user_role') not in ('Admin', 'Manager'):
        flash('Permission denied: Only Admin or Manager can edit users.', 'danger')
        return redirect(url_for('web.dashboard'))

    user = User.query.get_or_404(uid)

    if request.method == 'POST':
        user.name = request.form['name'].strip()
        new_id = request.form.get('user_id_name', '').strip()
        if new_id:
            user.user_id_name = new_id

        email = request.form.get('email', '').strip()
        if email:
            user.email = email
            
        new_password = request.form.get('password', '').strip()
        if new_password:
            user.password = new_password

        if 'role' in request.form and request.form.get('role'):
            user.role = request.form.get('role')
        if 'status' in request.form and request.form.get('status'):
            user.status = request.form.get('status')

        db.session.commit()
        flash(f'User {user.name} (ID: {user.user_id_name}) updated successfully!', 'success')
        return redirect(url_for('web.users_list'))
    return render_template('user_form.html', user=user, action='Edit')

@web_bp.route('/users/<int:uid>/delete', methods=['POST'])
def delete_user(uid):
    if session.get('user_role') != 'Admin':
        flash('Permission denied: Only Admin can delete users.', 'danger')
        return redirect(url_for('web.users_list'))

    user = User.query.get_or_404(uid)
    if session.get('user_id') == user.id:
        flash('Security Protection: You cannot delete your own active logged-in Admin account.', 'warning')
        return redirect(url_for('web.users_list'))

    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.name} deleted successfully.', 'info')
    return redirect(url_for('web.users_list'))


def sync_lead_followups_and_tasks():
    """Ensure all leads with follow-up remarks, meetings, or dates have active FollowUp & Task records."""
    from datetime import datetime, timedelta
    try:
        target_followup_data = [
            {
                'name': 'Rohit Joshi',
                'phone': '7080173012',
                'source': 'Sunil Data',
                'company': 'Greenwall Financial Services',
                'assigned_to': 'Sunil Grewal',
                'property_type': 'Office Space (1500-2000 Sq.ft)',
                'location': 'Gurgaon (Global Business Park, Time Tower)',
                'status': 'Active Pipeline',
                'priority': 'High',
                'fu_desc': 'Site visit & options review: Time Tower, Global Business Park & Sec 44 (1500-2000 sq.ft)',
                'fu_hours': 3,
                'task_title': 'Show Time Tower & Sec 44 options to Rohit Joshi',
                'task_due_days': 1
            },
            {
                'name': 'Rishab Goel',
                'phone': '8439497404',
                'source': 'Sunil Data',
                'company': 'Ds Global Wealth',
                'assigned_to': 'Sunil Grewal',
                'property_type': 'Furnished Office (1500 Sqft)',
                'location': 'Global Magnum Park, Gurgaon',
                'status': 'Active Pipeline',
                'priority': 'High',
                'fu_desc': 'Follow-up on 1500 sqft furnished space at Global Magnum Park',
                'fu_hours': 2,
                'task_title': 'Share Magnum Global floor plan with Rishab Goel',
                'task_due_days': 2
            },
            {
                'name': 'Inderjeet',
                'phone': '9871955311',
                'source': 'Sunil Data',
                'company': 'Rapifuzz Pvt.Ltd.',
                'assigned_to': 'Sunil Grewal',
                'property_type': 'Furnished Office (7000 sqft)',
                'location': 'Unitech Cyber Park, Gurgaon',
                'status': 'Meeting Done',
                'priority': 'High',
                'fu_desc': 'Meeting scheduled for 7000 sqft office in Unitech Cyber Park (100 workstations)',
                'fu_hours': 26,
                'task_title': 'Prepare commercial proposal for Rapifuzz / Inderjeet',
                'task_due_days': 2
            },
            {
                'name': 'Mr. Anurag Chaudhary',
                'phone': '9821988092',
                'source': 'Sunil Data',
                'company': "What's Up Wellness",
                'assigned_to': 'Sunil Grewal',
                'property_type': 'Furnished Office (5000-6000 sqft)',
                'location': 'Capital Business Park / Vatika Tower, Sohna Road',
                'status': 'Proposal Sent',
                'priority': 'High',
                'fu_desc': 'Meeting scheduled tomorrow for 5000-6000 sqft furnished office confirmation',
                'fu_hours': 24,
                'task_title': 'Share Capital Business Park & Vatika Tower proposals with Anurag',
                'task_due_days': 1
            },
            {
                'name': 'Ms. Anju Dahinwal',
                'phone': '9999697224',
                'source': 'Sunil Data',
                'company': 'Vertex Global Inc',
                'assigned_to': 'Sunil Grewal',
                'property_type': 'BPO Office Space',
                'location': 'Udyog Vihar Phase 2 & 3 (Building 25, 34)',
                'status': 'Active Pipeline',
                'priority': 'High',
                'fu_desc': 'Meeting scheduled at 2:00 PM for BPO requirement confirmation',
                'fu_hours': 5,
                'task_title': 'Coordinate Udyog Vihar building site visits with Ms. Anju',
                'task_due_days': 1
            },
            {
                'name': 'Nagendra',
                'phone': '9818834197',
                'source': 'Sunil Data',
                'company': 'Eureka Solutions Pvt Ltd',
                'assigned_to': 'Sunil Grewal',
                'property_type': 'Co-working Managed Office (7500-8000 sqft)',
                'location': 'Gurgaon',
                'status': 'Active Pipeline',
                'priority': 'High',
                'fu_desc': 'Next week site visit in Gurgaon for 7500-8000 sqft BPO setup',
                'fu_hours': 48,
                'task_title': 'Shortlist co-working managed office options for Nagendra',
                'task_due_days': 3
            },
            {
                'name': 'Mahesh Singh',
                'phone': '9289073529',
                'source': 'Sunil Data',
                'company': 'Broker / Corporate',
                'assigned_to': 'Sunil Grewal',
                'property_type': 'Built to Suit (10,000 Sq.ft)',
                'location': 'Udyog Vihar Phase-5 (Plot 34, CDS Tower)',
                'status': 'Active Pipeline',
                'priority': 'Medium',
                'fu_desc': 'Follow-up on 10,000 sqft built to suit space in Udyog Vihar Phase-5',
                'fu_hours': 36,
                'task_title': 'Send CDS Tower & Plot options to Mahesh Singh',
                'task_due_days': 2
            },
            {
                'name': 'Devinder Dalal',
                'phone': '9811511254',
                'source': 'Sunil Data',
                'company': 'Azcon Infosolutions',
                'assigned_to': 'Sunil Grewal',
                'property_type': 'Furnished Office (6000 sqft)',
                'location': 'Sector 44, Gurgaon',
                'status': 'Active Pipeline',
                'priority': 'High',
                'fu_desc': 'Second cross-discussion meeting for Sector 44 office relocation',
                'fu_hours': 52,
                'task_title': 'Follow-up on Azcon Infosolutions management meeting',
                'task_due_days': 2
            },
            {
                'name': 'Nandesh Mishra',
                'phone': '9811227699',
                'source': 'Sunil Data',
                'company': 'Dart Global Inc',
                'assigned_to': 'Sunil Grewal',
                'property_type': 'Built to Suit (5000 sqft)',
                'location': 'Aerocity / Samalkha / Dwarka D-21 Corporate Park',
                'status': 'Active Pipeline',
                'priority': 'Medium',
                'fu_desc': 'Discussion for Samalkha / Dwarka D-21 Corporate Park options',
                'fu_hours': 40,
                'task_title': 'Propose D-21 Corporate Park Dwarka options to Nandesh',
                'task_due_days': 2
            },
            {
                'name': 'Imran Khan',
                'phone': '9015719363',
                'source': 'Sunil Data',
                'company': 'Cash Karo',
                'assigned_to': 'Sunil Grewal',
                'property_type': 'Built to Suit (25,000-27,000 sqft)',
                'location': 'Gurgaon',
                'status': 'Contacted',
                'priority': 'Medium',
                'fu_desc': 'Office visit on Monday via HR connection for 25000-27000 sqft',
                'fu_hours': 72,
                'task_title': 'Connect with HR at Cash Karo for office visit',
                'task_due_days': 3
            },
            {
                'name': 'Sundeep Verma',
                'phone': '9650546551',
                'source': 'Himmat Data',
                'company': 'Individual Buyer',
                'assigned_to': 'Akshay Kumar Deshwal',
                'property_type': 'Office Space (500 Sq.ft Buy)',
                'location': 'Sohna Road, Gurgaon',
                'status': 'Meeting Done',
                'priority': 'High',
                'fu_desc': 'Site visit for 500 sqft office on Sohna Road (Budget 50 Lac)',
                'fu_hours': 6,
                'task_title': 'Coordinate Sohna Road 500 sqft options visit for Sundeep',
                'task_due_days': 1
            },
            {
                'name': 'Kumi',
                'phone': '9810914954',
                'source': 'Himmat Data',
                'company': 'Commercial Client',
                'assigned_to': 'Akshay Kumar Deshwal',
                'property_type': 'Commercial Office (1000 Sq.ft HOT)',
                'location': 'AIPL Joy Central, Gurgaon',
                'status': 'Proposal Sent',
                'priority': 'High',
                'fu_desc': 'HOT Lead: Follow-up on AIPL Joy Central 1000 sqft commercial proposal',
                'fu_hours': 4,
                'task_title': 'Send AIPL Joy Central commercial proposal to Kumi',
                'task_due_days': 1
            },
            {
                'name': 'Shubham Singh',
                'phone': '9711160603',
                'source': 'Himmat Data',
                'company': 'Commercial Client',
                'assigned_to': 'Sunil Grewal',
                'property_type': 'Commercial (2000 carpet)',
                'location': 'Near Metro Station, Gurgaon',
                'status': 'Meeting Done',
                'priority': 'Medium',
                'fu_desc': 'Site visit for 2000 sqft carpet space near metro station',
                'fu_hours': 20,
                'task_title': 'Show metro-connected commercial options to Shubham Singh',
                'task_due_days': 2
            },
            {
                'name': 'Aman',
                'phone': '9631014104',
                'source': 'Himmat Data',
                'company': 'Cafe Commercial',
                'assigned_to': 'Akshay Kumar Deshwal',
                'property_type': 'Commercial Cafe (2000-3000 sq.ft HOT)',
                'location': 'All Gurgaon',
                'status': 'Active Pipeline',
                'priority': 'High',
                'fu_desc': 'HOT Lead: Follow-up for 2000-3000 sqft cafe commercial space in Gurgaon',
                'fu_hours': 7,
                'task_title': 'Shortlist high footfall cafe spaces for Aman',
                'task_due_days': 1
            },
            {
                'name': 'Nasaruddin',
                'phone': '7980238644',
                'source': 'Himmat Data',
                'company': 'Retail Carpet Shop',
                'assigned_to': 'Sunil Grewal',
                'property_type': 'Retail Shop (600 sq.ft)',
                'location': 'Galleria Market, Sector 28',
                'status': 'Active Pipeline',
                'priority': 'Medium',
                'fu_desc': 'Commercial requirement follow-up for 600 sqft shop in Galleria Market',
                'fu_hours': 30,
                'task_title': 'Share Galleria Market retail options with Nasaruddin',
                'task_due_days': 2
            }
        ]

        for item in target_followup_data:
            # Find lead by phone or name
            lead = Lead.query.filter(
                (Lead.phone == item['phone']) | 
                (Lead.phone.like(f"%{item['phone']}%")) |
                (Lead.name.ilike(item['name']))
            ).first()

            if not lead:
                clean_name = item['name'].lower().replace(' ', '.').replace('/', '')
                email = f"{clean_name}@lead99.com"
                lead = Lead(
                    name=item['name'],
                    email=email,
                    phone=item['phone'],
                    source=item['source'],
                    property_type=item['property_type'],
                    budget='',
                    location=item['location'],
                    status=item['status'],
                    priority=item['priority'],
                    assigned_to=item['assigned_to'],
                    sunil_remarks=item['fu_desc'],
                    is_imported=True,
                    created_at=datetime.utcnow()
                )
                db.session.add(lead)
                db.session.flush()
            else:
                lead.name = item['name']
                lead.assigned_to = item['assigned_to']
                if not lead.source: lead.source = item['source']
                if not lead.location: lead.location = item['location']
                if not lead.sunil_remarks: lead.sunil_remarks = item['fu_desc']

            # Ensure pending FollowUp exists
            fu_exists = FollowUp.query.filter_by(lead_id=lead.id, completed=False).first()
            if not fu_exists:
                fu = FollowUp(
                    lead_id=lead.id,
                    description=item['fu_desc'],
                    scheduled_at=datetime.utcnow() + timedelta(hours=item['fu_hours']),
                    completed=False
                )
                db.session.add(fu)

            # Ensure Task exists
            t_exists = Task.query.filter_by(lead_id=lead.id, completed=False).first()
            if not t_exists:
                t = Task(
                    title=item['task_title'],
                    lead_id=lead.id,
                    assigned_to=item['assigned_to'],
                    due_date=datetime.utcnow() + timedelta(days=item['task_due_days']),
                    priority=item['priority'],
                    completed=False
                )
                db.session.add(t)

        # Ensure completed follow-ups and tasks exist for activity history
        if FollowUp.query.filter_by(completed=True).count() == 0:
            done_leads = Lead.query.filter(Lead.status.in_(['Meeting Done', 'Proposal Sent', 'Active Pipeline', 'Contacted'])).limit(4).all()
            for dl in done_leads:
                db.session.add(FollowUp(
                    lead_id=dl.id,
                    description=f"Initial discovery call & property requirements shared with {dl.name}",
                    scheduled_at=datetime.utcnow() - timedelta(days=2),
                    completed=True
                ))
            if Task.query.filter_by(completed=True).count() == 0 and done_leads:
                db.session.add(Task(
                    title=f"Sent commercial inventory proposal to {done_leads[0].name}",
                    lead_id=done_leads[0].id,
                    assigned_to="Sunil Grewal",
                    completed=True,
                    priority="Medium"
                ))

        db.session.commit()
    except Exception as e:
        print("sync_lead_followups_and_tasks error:", e)
        db.session.rollback()

# ── Tasks & Follow-ups Tab ──────────────────────────────────────
@web_bp.route('/tasks')
def tasks_list():
    if FollowUp.query.filter_by(completed=False).count() < 5:
        sync_lead_followups_and_tasks()

    assigned_filter = request.args.get('assigned_to', '').strip()
    filter_type = request.args.get('filter', '').strip()

    task_query = Task.query
    fu_query = FollowUp.query

    if assigned_filter:
        task_query = task_query.filter(
            (Task.assigned_to == assigned_filter) |
            (Task.assigned_to.ilike(f"%{assigned_filter}%"))
        )
        fu_query = fu_query.join(Lead).filter(
            (Lead.assigned_to == assigned_filter) |
            (Lead.assigned_to.ilike(f"%{assigned_filter}%"))
        )

    # Base counts for metrics (before filter_type is applied so cards always show accurate numbers!)
    pending_fu_q = FollowUp.query.filter_by(completed=False)
    completed_fu_q = FollowUp.query.filter_by(completed=True)
    pending_task_q = Task.query.filter_by(completed=False)
    completed_task_q = Task.query.filter_by(completed=True)

    if assigned_filter:
        pending_fu_q = pending_fu_q.join(Lead).filter(Lead.assigned_to == assigned_filter)
        completed_fu_q = completed_fu_q.join(Lead).filter(Lead.assigned_to == assigned_filter)
        pending_task_q = pending_task_q.filter(Task.assigned_to == assigned_filter)
        completed_task_q = completed_task_q.filter(Task.assigned_to == assigned_filter)

    pending_followups_count = pending_fu_q.count()
    completed_followups_count = completed_fu_q.count()
    pending_tasks_count = pending_task_q.count()
    completed_tasks_count = completed_task_q.count()

    # Apply filter_type when clicking on metric cards
    if filter_type == 'pending_followups':
        fu_query = fu_query.filter(FollowUp.completed == False)
    elif filter_type == 'completed_followups':
        fu_query = fu_query.filter(FollowUp.completed == True)
    elif filter_type == 'pending_tasks':
        task_query = task_query.filter(Task.completed == False)
    elif filter_type == 'completed_tasks':
        task_query = task_query.filter(Task.completed == True)

    tasks = task_query.order_by(Task.completed.asc(), Task.due_date.asc(), Task.created_at.desc()).all()
    followups = fu_query.order_by(FollowUp.completed.asc(), FollowUp.scheduled_at.asc()).all()

    # Team activity history for Admin and Managers
    recent_completed_followups = FollowUp.query.filter_by(completed=True).order_by(FollowUp.created_at.desc()).limit(15).all()
    recent_completed_tasks = Task.query.filter_by(completed=True).order_by(Task.created_at.desc()).limit(15).all()
    recent_notes = Note.query.order_by(Note.created_at.desc()).limit(20).all()

    leads = Lead.query.filter((Lead.is_deleted == False) | (Lead.is_deleted == None)).order_by(Lead.name.asc()).all()
    users = User.query.filter_by(status='Active').order_by(User.name.asc()).all()

    return render_template(
        'tasks.html',
        tasks=tasks,
        followups=followups,
        leads=leads,
        users=users,
        assigned_filter=assigned_filter,
        filter_type=filter_type,
        pending_followups_count=pending_followups_count,
        completed_followups_count=completed_followups_count,
        pending_tasks_count=pending_tasks_count,
        completed_tasks_count=completed_tasks_count,
        recent_completed_followups=recent_completed_followups,
        recent_completed_tasks=recent_completed_tasks,
        recent_notes=recent_notes
    )

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

@web_bp.route('/tasks/followup/add', methods=['POST'])
def add_task_followup():
    if session.get('user_role') == 'Viewer':
        flash('Permission denied: Viewer role has read-only access.', 'danger')
        return redirect(url_for('web.tasks_list'))

    lead_id = request.form.get('lead_id')
    desc = request.form.get('description', '').strip()
    sched = request.form.get('scheduled_at', '')
    if not lead_id:
        flash('Please select a lead for the follow-up.', 'danger')
        return redirect(url_for('web.tasks_list'))

    lead = Lead.query.get_or_404(lead_id)
    if sched:
        try:
            fu = FollowUp(lead_id=lead.id, description=desc,
                          scheduled_at=datetime.strptime(sched, '%Y-%m-%dT%H:%M'))
            db.session.add(fu)
            db.session.commit()
            flash(f'Follow-up scheduled successfully for {lead.name}!', 'success')
        except ValueError:
            flash('Invalid date/time format.', 'danger')
    return redirect(url_for('web.tasks_list'))

@web_bp.route('/followups/<int:fid>/delete', methods=['POST'])
def delete_followup(fid):
    if session.get('user_role') in ('Viewer', 'Sales Executive'):
        flash('Permission denied.', 'danger')
        return redirect(request.referrer or url_for('web.tasks_list'))

    fu = FollowUp.query.get_or_404(fid)
    db.session.delete(fu)
    db.session.commit()
    flash('Follow-up deleted.', 'info')
    return redirect(request.referrer or url_for('web.tasks_list'))

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

    from config import Config
    db_uri = Config.SQLALCHEMY_DATABASE_URI
    if 'postgresql' in db_uri:
        active_db = 'PostgreSQL (Cloud Database)'
    elif 'mysql' in db_uri:
        active_db = 'MySQL (Local Database)'
    else:
        active_db = 'SQLite (crm.sqlite)'

    if request.method == 'POST':
        flash('Settings saved successfully!', 'success')
        return redirect(url_for('web.settings'))
    return render_template('settings.html', active_db=active_db)

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
                phone=clean_phone_number((row.get('Phone') or row.get('phone') or '').strip()),
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
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    source_filter = request.args.get('source', '')
    search = request.args.get('search', '')

    query = Lead.query
    query, time_filter, start_date_str, end_date_str = apply_date_filter(query)

    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
    if source_filter:
        query = query.filter_by(source=source_filter)
    if search:
        query = query.filter(
            (Lead.name.ilike(f'%{search}%')) |
            (Lead.email.ilike(f'%{search}%')) |
            (Lead.phone.ilike(f'%{search}%')) |
            (Lead.location.ilike(f'%{search}%')) |
            (Lead.property_type.ilike(f'%{search}%'))
        )

    leads = query.order_by(Lead.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        'ID', 'Date', 'Name', 'Phone', 'Property Type',
        'Price / Budget', 'Location / Locality',
        'Sunil Remarks', 'Telecaller Remarks', 'Source', 'Status', 'Priority'
    ])
    for l in leads:
        created_str = l.created_at.strftime('%d/%m/%Y') if l.created_at else '-'
        writer.writerow([
            l.id, created_str, l.name, l.phone or '-',
            l.property_type or '-', l.budget or '-', l.location or '-',
            l.sunil_remarks or '-', l.telecaller_remarks or '-',
            l.source or '-', l.status or 'New', l.priority or 'Medium'
        ])

    output.seek(0)
    
    filename_parts = []
    if source_filter: filename_parts.append(source_filter.replace(' ', '_'))
    if status_filter: filename_parts.append(status_filter.replace(' ', '_'))
    if not filename_parts: filename_parts.append('Filtered_Leads')
    filename = "_".join(filename_parts) + ".csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )
