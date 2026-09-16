from models import db, Lead
def login(c):
    return c.post("/login",data={"identity":"admin","password":"pass"},follow_redirects=True)
def test_login_and_dashboard(client):
    r=login(client); assert r.status_code==200; assert b"Total Leads" in r.data
def test_lead_persistence(client,app):
    login(client)
    r=client.post("/leads/new",data={"client_name":"Test User","phone":"919876543210","email":"T@EXAMPLE.COM","lead_status":"New Lead","lead_stage":"New Lead"},follow_redirects=True)
    assert r.status_code==200
    with app.app_context():
        l=Lead.query.filter_by(client_name="Test User").first()
        assert l.phone=="9876543210" and l.email=="t@example.com"
def test_duplicate(client,app):
    login(client)
    client.post("/leads/new",data={"client_name":"A","phone":"9876543210","email":"a@x.com","lead_status":"New Lead","lead_stage":"New Lead"})
    r=client.post("/leads/new",data={"client_name":"B","phone":"09876543210","email":"b@x.com","lead_status":"New Lead","lead_stage":"New Lead"},follow_redirects=True)
    assert b"Duplicate" in r.data
def test_delete_requires_admin(client,app):
    login(client)
    client.post("/leads/new",data={"client_name":"Delete Me","phone":"9000000000"})
    with app.app_context(): lid=Lead.query.filter_by(client_name="Delete Me").first().id
    r=client.post(f"/leads/{lid}/delete"); assert r.status_code==200
