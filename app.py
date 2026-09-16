# app.py
"""Yayath 99Acres CRM - Flask Application."""

from flask import Flask
from config import Config
from extensions import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    from routes import api_bp, web_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(web_bp)

    with app.app_context():
        db.create_all()

    return app


# Gunicorn needs this
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
