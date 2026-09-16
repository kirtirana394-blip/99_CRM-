# 99Acres Lead CRM

Production-oriented Flask CRM for managing commercial real-estate leads received from 99Acres.

## Features
- Session login with hashed passwords and admin/user roles
- PostgreSQL production database with SQLite local fallback
- Persistent leads, follow-ups, notes, tasks, meetings, proposals, deals, notifications and stage history
- Dashboard KPIs and live database calculations
- Duplicate detection using normalized phone, email and 99Acres reference
- CSV/XLS/XLSX import with cleaning and import history
- Excel export
- Responsive SaaS-style UI
- Reports using real database data
- APScheduler reminders that are optional; core CRM remains usable without it
- Render deployment files
- Automated tests

## Windows PowerShell setup

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Open `http://127.0.0.1:5000/login`.

Default local credentials:
- Username: `admin`
- Password: `ChangeMe123!`

Change these immediately by setting `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` before first startup, or create a new admin and disable the default account.

## PostgreSQL

Set `DATABASE_URL` in `.env`, for example:

`postgresql://USER:PASSWORD@HOST:5432/DATABASE`

The application converts legacy `postgres://` URLs and uses psycopg automatically.

## Importing 99Acres data

Go to **Import 99Acres**, upload `.xlsx`, `.xls`, or `.csv`, then review the import summary. Common columns are mapped automatically. Client name plus at least one of phone/email/reference is required. Duplicate records are skipped based on normalized phone, email or source reference.

## Deployment to Render

1. Push this project to GitHub.
2. Create a Render Web Service using the repository.
3. The included `render.yaml` defines a web service and PostgreSQL database.
4. Set `SECRET_KEY` and `DATABASE_URL` as environment variables if not using the blueprint.
5. Build command: `pip install -r requirements.txt`
6. Start command: `gunicorn app:app`

## Tests

```powershell
.\.venv\Scripts\Activate.ps1
pytest -q
```

## Design decisions

- Qualification is never inferred merely from populated data. Users explicitly change status/stage.
- Disqualified leads require a reason.
- Overdue follow-ups are displayed as overdue; they do not silently change lead stage.
- `Unknown` is not automatically treated as disqualified because the source field may not represent a business rejection.
- Background reminders are supplemental. Dashboard and CRM functions do not depend on the scheduler.
