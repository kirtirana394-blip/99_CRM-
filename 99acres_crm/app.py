import os
from flask import Flask, redirect, url_for
from dotenv import load_dotenv
from config import Config
from models import db
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.leads import leads_bp
from routes.crm import crm_bp
from routes.import_export import import_export_bp
from routes.reports import reports_bp
from services.scheduler import start_scheduler

load_dotenv()

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(leads_bp)
    app.register_blueprint(crm_bp)
    app.register_blueprint(import_export_bp)
    app.register_blueprint(reports_bp)

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.index"))

    @app.errorhandler(404)
    def not_found(e):
        return ("Page not found", 404)

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server error")
        return ("Something went wrong. Please try again.", 500)

    with app.app_context():
        db.create_all()
        from services.seed import seed_local_admin
        seed_local_admin()

    if not app.testing:
        start_scheduler(app)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG","0")=="1")
