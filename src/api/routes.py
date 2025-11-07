"""Main API routes registration."""

from flask import Blueprint, render_template, send_from_directory
from .accounts import accounts_bp
from .queue import queue_bp
from .uploads import uploads_bp
from .script_control import script_bp
from .status import status_bp


def register_routes(app):
    """Register all API routes with Flask app."""
    # Register blueprints
    app.register_blueprint(accounts_bp)
    app.register_blueprint(queue_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(script_bp)
    app.register_blueprint(status_bp)
    
    # Main route
    @app.route('/')
    def index():
        return render_template('index.html')
    
    # Static files route is handled by Flask automatically via static_folder

