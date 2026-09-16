# config.py
"""Configuration supporting Render cloud (SQLite/Postgres) and local MySQL."""

import os

class Config:
    DATABASE_URL = os.getenv('DATABASE_URL', '')
    IS_RENDER = os.getenv('RENDER', False)

    if DATABASE_URL:
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    elif IS_RENDER:
        # On Render cloud, use zero-config SQLite file if no DATABASE_URL is set
        BASE_DIR = os.path.abspath(os.path.dirname(__file__))
        SQLITE_PATH = os.path.join(BASE_DIR, 'crm.sqlite')
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{SQLITE_PATH}"
    else:
        # Local development with MySQL
        MYSQL_USER = os.getenv('MYSQL_USER', 'root')
        MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'Rana1530#')
        MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
        MYSQL_PORT = os.getenv('MYSQL_PORT', '3306')
        MYSQL_DB = os.getenv('MYSQL_DB', 'crm')
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'yayath-99acres-crm-secret-2026')
