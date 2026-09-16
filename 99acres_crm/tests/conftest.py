import pytest
from app import create_app
from models import db
from services.auth import set_password
from models import User

@pytest.fixture()
def app(tmp_path):
    app=create_app({"TESTING":True,"SQLALCHEMY_DATABASE_URI":f"sqlite:///{tmp_path/'test.sqlite3'}","WTF_CSRF_ENABLED":False,"SECRET_KEY":"test"})
    with app.app_context():
        db.drop_all(); db.create_all()
        u=User(username="admin",email="admin@test.local",role="admin")
        set_password(u,"pass"); db.session.add(u); db.session.commit()
    yield app

@pytest.fixture()
def client(app):
    return app.test_client()
