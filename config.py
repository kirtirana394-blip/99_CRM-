# config.py
"""Configuration - supports Render (PostgreSQL), Cloud MySQL, or Local MySQL."""

import os

class Config:
    # Render sets DATABASE_URL automatically for its free PostgreSQL
    # If DATABASE_URL is set, use it directly (cloud deployment)
    # Otherwise fall back to MySQL config (local development)
    DATABASE_URL = os.getenv('DATABASE_URL', '')

    if DATABASE_URL:
        # Render uses postgres:// but SQLAlchemy needs postgresql://
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Local MySQL fallback
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
