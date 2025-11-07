"""Main Flask application entry point."""

import os
import signal
import sys
from pathlib import Path
from flask import Flask

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database.db import init_db, close_db
from src.api.routes import register_routes

app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['DATABASE'] = 'youtube_soft.db'

# Register routes
register_routes(app)

# Register database teardown
app.teardown_appcontext(close_db)


def signal_handler(signum, frame):
    """Signal handler for graceful shutdown"""
    try:
        print("\nReceived termination signal, stopping application...")
        
        # Stop script if running
        from src.api.script_control import get_script_state
        script_state = get_script_state()
        if script_state['is_running'] and script_state['script_instance']:
            script_state['script_instance'].stop()
        
        print("Application gracefully terminated")
        sys.exit(0)
    except Exception as e:
        try:
            print(f"Error during termination: {str(e)}")
        except:
            pass
        sys.exit(1)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize database if it doesn't exist
    if not os.path.exists(app.config['DATABASE']):
        init_db(app)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
