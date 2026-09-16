from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file
from models import db, Lead, ImportHistory
from utils.helpers import normalize_phone, normalize_email, parse_dt
import pandas as pd, io, os

bp=Blueprint("import_export",__name__)

COLUMN_MAP={
"lead_id":"lead_id","lead id":"lead_id","client name":"client_name","name":"client_name",
"company":"company_name","company name":"company_name","phone":"phone","mobile":"phone",
"email":"email","property":"property_name","property name":"property_name","property type":"property_type",
"location":"location","requirement":"requirement","budget":"budget","area":"area_required",
"area required":"area_required","source reference":"source_reference","99acres lead id":"source_reference",
"status":"lead_status","priority":"priority","assigned to":"assigned_to","lead date":"lead_date",
}

def clean_col(x): return str(x).strip().lower().replace("_"," ").replace("-"," ")

@bp.route("/import",methods=["GET","POST"])
def import_page():
    if not session.get("user_id"): return redirect("/login")
    if request.method=="POST":
        f=request.files.get("file")
        if not f or not f.filename.lower().endswith((".xlsx",".xls",".csv")):
            flash("Upload .xlsx, .xls or .csv only.","danger"); return redirect(url_for("import_export.import_page"))
        try:
            if f.filename.lower().endswith(".csv"): df=pd.read_csv(f)
            else: df=pd.read_excel(f)
        except Exception as e:
            flash(f"Could not read file: {e}","danger"); return redirect(url_for("import_export.import_page"))
        mapped={c:COLUMN_MAP.get(clean_col(c)) for c in df.columns}
        usable=[c for c,v in mapped.items() if v]
        if "client_name" not in [mapped[c] for c in usable]:
            flash("Missing required column: Client Name.","danger"); return redirect(url_for("import_export.import_page"))
        imported=dupes=invalid=0
        for _,row in df.iterrows():
            data={mapped[c]: (None if pd.isna(row[c]) else row[c]) for c in usable}
            phone=normalize_phone(data.get("phone")); email=normalize_email(data.get("email")); ref=str(data.get("source_reference") or "").strip() or None
            if not data.get("client_name") or not (phone or email or ref):
                invalid+=1; continue
            dup=Lead.query.filter(
                (Lead.phone==phone if phone else False) |
                (Lead.email==email if email else False) |
                (Lead.source_reference==ref if ref else False)
            ).first()
            if dup: dupes+=1; continue
            l=Lead(lead_id=str(data.get("lead_id") or f"99A-{__import__('uuid').uuid4().hex[:10].upper()}"),
                   client_name=str(data["client_name"]).strip(),company_name=str(data.get("company_name") or "") or None,
                   phone=phone,email=email,property_name=str(data.get("property_name") or "") or None,
                   property_type=str(data.get("property_type") or "") or None,location=str(data.get("location") or "") or None,
                   requirement=str(data.get("requirement") or "") or None,budget=str(data.get("budget") or "") or None,
                   area_required=str(data.get("area_required") or "") or None,source="99Acres",source_reference=ref,
                   lead_status=str(data.get("lead_status") or "New Lead"),lead_stage=str(data.get("lead_status") or "New Lead"),
                   priority=str(data.get("priority") or "Medium"),lead_date=parse_dt(data.get("lead_date")))
            if not l.lead_date: l.lead_date=__import__("datetime").datetime.now()
            db.session.add(l); imported+=1
        ih=ImportHistory(file_name=f.filename,uploaded_by=session["user_id"],total_records=len(df),
                         imported_records=imported,duplicate_records=dupes,invalid_records=invalid)
        db.session.add(ih); db.session.commit()
        flash(f"Import complete — {imported} imported, {dupes} duplicates, {invalid} invalid.","success")
    history=ImportHistory.query.order_by(ImportHistory.upload_date.desc()).limit(20).all()
    return render_template("import.html",history=history)

@bp.get("/export/leads")
def export_leads():
    if not session.get("user_id"): return redirect("/login")
    q=Lead.query
    status=request.args.get("status")
    if status: q=q.filter_by(lead_status=status)
    rows=[]
    for l in q.order_by(Lead.created_at.desc()).all():
        rows.append({"Lead ID":l.lead_id,"Client Name":l.client_name,"Company":l.company_name,"Phone":l.phone,"Email":l.email,
                     "Location":l.location,"Requirement":l.requirement,"Budget":l.budget,"Area Required":l.area_required,
                     "Source":l.source,"Status":l.lead_status,"Priority":l.priority,"Assigned To":l.assignee.username if l.assignee else "",
                     "Next Follow-up":l.next_followup_date,"Created Date":l.created_at})
    df=pd.DataFrame(rows)
    out=io.BytesIO()
    with pd.ExcelWriter(out,engine="openpyxl") as writer: df.to_excel(writer,index=False,sheet_name="Leads")
    out.seek(0); return send_file(out,as_attachment=True,download_name="99Acres_Leads.xlsx",mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
