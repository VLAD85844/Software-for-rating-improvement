"""Script control endpoints."""

import threading
import asyncio
import time
import json
from flask import Blueprint, request, jsonify
from src.core.automation import GoLoginAuth
from src.managers.omnilogin_manager import OmniloginManager
from src.utils.config import ConfigManager
from src.database.db import get_db

script_bp = Blueprint('script', __name__)

# Global state
script_thread = None
is_running = False
script_instance = None


def run_script_in_thread(script):
    """Run script in separate thread with async code handling."""
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(script.run())
    except Exception as e:
        try:
            print(f"Error in script thread: {str(e)}")
        except:
            pass
    finally:
        try:
            if loop and not loop.is_closed():
                loop.close()
        except:
            pass


@script_bp.route('/start_script', methods=['POST'])
def start_script():
    global script_thread, is_running, script_instance
    
    if is_running:
        return jsonify({'status': 'error', 'message': 'Script is already running'})
    
    data = request.json
    account_ids = data.get('account_ids', [])
    threads_count = int(data.get('threads_count', 5))
    
    config = {
        'watch_duration': data.get('watch_duration', '30'),
        'max_actions_per_account': data.get('max_actions_per_account', 3),
        'human_behavior': data.get('human_behavior', True),
        'enable_likes': data.get('enable_likes', True),
        'enable_subscriptions': data.get('enable_subscriptions', False),
        'enable_referral': data.get('enable_referral', True),
        'urls_strategy': data.get('urls_strategy', 'random'),
        'create_channel': data.get('create_channel', False),
        'enable_title_search': data.get('enable_title_search', False),
        'filter_strategy': data.get('filter_strategy', 'none')
    }
    
    # Save config
    config_manager = ConfigManager()
    config_manager.save(config)
    
    try:
        db = get_db()
        accounts = db.execute(
            'SELECT id, email, password FROM accounts WHERE id IN ({})'
            .format(','.join(['?'] * len(account_ids))),
            account_ids
        ).fetchall()
        
        if not accounts:
            return jsonify({'status': 'error', 'message': 'No accounts selected'})
        
        script_instance = GoLoginAuth(
            threads=threads_count,
            account_ids=account_ids,
            enable_title_search=data.get('enable_title_search', False)
        )
        script_thread = threading.Thread(
            target=run_script_in_thread,
            args=(script_instance,),
            daemon=False
        )
        script_thread.start()
        is_running = True
        
        return jsonify({
            'status': 'success',
            'message': f'Script started for {len(accounts)} accounts (threads: {threads_count})'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Start error: {str(e)}'})


@script_bp.route('/stop_script', methods=['POST'])
def stop_script():
    global is_running, script_instance, script_thread
    
    if not is_running:
        return jsonify({'status': 'error', 'message': 'Script is not running'})
    
    try:
        is_running = False
        if script_instance:
            script_instance.stop()
            time.sleep(2)
        
        if script_thread and script_thread.is_alive():
            script_thread.join(timeout=10)
            if script_thread.is_alive():
                try:
                    print("Force thread termination")
                except:
                    pass
        
        try:
            browser_manager = OmniloginManager()
            async def strict_close_browsers():
                await browser_manager.strict_kill_browser()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(strict_close_browsers())
                print("Strict browser closure executed")
            finally:
                loop.close()
        except Exception as e:
            print(f"Error during strict browser closure: {str(e)}")
        
        return jsonify({'status': 'success', 'message': 'Script stopped and browsers closed'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Stop error: {str(e)}'})


@script_bp.route('/stop/<profile_id>', methods=['GET'])
def stop_profile(profile_id):
    """Close browser by profile_id"""
    try:
        browser_manager = OmniloginManager()
        async def close_profile():
            await browser_manager.close_profile(profile_id)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(close_profile())
            return jsonify({'closed': True})
        finally:
            loop.close()
    except Exception as e:
        return jsonify({
            'closed': False,
            'error': str(e)
        })


@script_bp.route('/clear_profiles', methods=['POST'])
def clear_profiles():
    try:
        db = get_db()
        db.execute('DELETE FROM account_profiles')
        db.commit()
        return jsonify({'status': 'success', 'message': 'All profile associations cleared'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


def get_script_state():
    """Get current script state for other modules."""
    return {
        'is_running': is_running,
        'script_instance': script_instance
    }

