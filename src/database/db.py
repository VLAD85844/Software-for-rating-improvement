"""Database connection and utilities."""

import sqlite3
import os
from flask import g, current_app
from pathlib import Path


def get_db():
    """Get database connection from Flask application context."""
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE', 'youtube_soft.db')
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """Close database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """Initialize database with schema."""
    db_path = app.config.get('DATABASE', 'youtube_soft.db')
    
    # Get schema path
    schema_path = Path(__file__).parent.parent.parent / 'database' / 'schema.sql'
    
    if not schema_path.exists():
        # Fallback to old location
        schema_path = Path(__file__).parent.parent.parent / 'schema.sql'
    
    if schema_path.exists():
        with app.app_context():
            db = get_db()
            with open(schema_path, 'r', encoding='utf-8') as f:
                db.cursor().executescript(f.read())
            db.commit()
            print(f"Database initialized from {schema_path}")
    else:
        print(f"Warning: Schema file not found at {schema_path}")


def get_db_connection(db_path='youtube_soft.db'):
    """Get a direct database connection (for non-Flask contexts)."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db

