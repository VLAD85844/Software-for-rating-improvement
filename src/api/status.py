"""Status and statistics endpoints."""

import os
import json
from flask import Blueprint, jsonify
from src.database.db import get_db
from src.utils.helpers import count_lines
from .script_control import get_script_state

status_bp = Blueprint('status', __name__)


@status_bp.route('/status')
def get_status():
    """Get application status."""
    try:
        script_state = get_script_state()
        db = get_db()
        accounts_count = db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0]
        proxies_count = count_lines('proxies.txt') if os.path.exists('proxies.txt') else 0
        urls_count = count_lines('video_urls.txt') if os.path.exists('video_urls.txt') else 0
        
        return jsonify({
            'is_running': script_state['is_running'],
            'accounts_count': accounts_count,
            'proxies_count': proxies_count,
            'urls_count': urls_count
        })
    except Exception as e:
        return jsonify({
            'is_running': False,
            'error': str(e),
            'accounts_count': 0,
            'proxies_count': 0,
            'urls_count': 0
        })


@status_bp.route('/stats')
def get_stats():
    """Get execution statistics."""
    try:
        with open('report.json', 'r') as f:
            report = json.load(f)
        return jsonify({
            'status': 'success',
            'stats': {
                'total_accounts': report.get('total_accounts', 0),
                'active_accounts': report.get('active_accounts', 0),
                'success_actions': report.get('success_actions', 0),
                'failed_actions': report.get('failed_actions', 0)
            }
        })
    except:
        return jsonify({
            'status': 'error',
            'stats': {
                'total_accounts': 0,
                'active_accounts': 0,
                'success_actions': 0,
                'failed_actions': 0
            }
        })

