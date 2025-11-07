"""Account management endpoints."""

from flask import Blueprint, request, jsonify
from datetime import datetime
from src.database.db import get_db

accounts_bp = Blueprint('accounts', __name__)


@accounts_bp.route('/accounts', methods=['GET', 'POST', 'DELETE'])
def manage_accounts():
    db = get_db()
    
    if request.method == 'GET':
        try:
            accounts = db.execute('''
                SELECT a.id, a.email, a.password, a.status, a.created_at, t.name as tag, t.color as tag_color
                FROM accounts a
                LEFT JOIN account_tags t ON a.id = t.account_id
                ORDER BY a.id
            ''').fetchall()
            
            accounts_list = []
            for account in accounts:
                account_data = {
                    'id': account['id'],
                    'email': account['email'],
                    'password': account['password'],
                    'status': account['status'],
                    'created_at': account['created_at']
                }
                
                if account['tag']:
                    account_data['tag'] = {
                        'name': account['tag'],
                        'color': account['tag_color']
                    }
                
                accounts_list.append(account_data)
            
            return jsonify({
                'status': 'success',
                'accounts': accounts_list
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error loading accounts: {str(e)}'
            })
    
    elif request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'File not found'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'No file selected'})
        
        from src.utils.helpers import allowed_file
        if file and allowed_file(file.filename):
            try:
                content = file.read().decode('utf-8')
                accounts = []
                for line in content.splitlines():
                    parts = line.strip().split(':', 2)
                    if len(parts) >= 2:
                        email = parts[0]
                        password = parts[1]
                        recovery_email = parts[2] if len(parts) >= 3 else None
                        accounts.append((email, password, recovery_email))
                
                for email, password, recovery_email in accounts:
                    db.execute(
                        'INSERT OR IGNORE INTO accounts (email, password, recovery_email, status, created_at) VALUES (?, ?, ?, ?, ?)',
                        (email, password, recovery_email, 'active', datetime.now())
                    )
                db.commit()
                
                return jsonify({
                    'status': 'success',
                    'message': f'Added {len(accounts)} accounts'
                })
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': f'Error processing file: {str(e)}'
                })
    
    elif request.method == 'DELETE':
        data = request.json
        account_ids = data.get('account_ids', [])
        
        if not account_ids:
            return jsonify({'status': 'error', 'message': 'No accounts selected'})
        
        try:
            db.execute(
                'DELETE FROM account_tags WHERE account_id IN ({})'.format(','.join(['?'] * len(account_ids))),
                account_ids
            )
            
            db.execute(
                'DELETE FROM accounts WHERE id IN ({})'.format(','.join(['?'] * len(account_ids))),
                account_ids
            )
            
            db.commit()
            return jsonify({
                'status': 'success',
                'message': f'Deleted {db.total_changes} accounts'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error deleting accounts: {str(e)}'
            })


@accounts_bp.route('/accounts/<int:account_id>/tag', methods=['POST'])
def update_account_tag(account_id):
    db = get_db()
    data = request.json
    tag_name = data.get('tag_name')
    tag_color = data.get('tag_color')
    
    try:
        account = db.execute('SELECT id FROM accounts WHERE id = ?', (account_id,)).fetchone()
        if not account:
            return jsonify({'status': 'error', 'message': 'Account not found'})
        db.execute('DELETE FROM account_tags WHERE account_id = ?', (account_id,))
        if tag_name and tag_color:
            db.execute(
                'INSERT INTO account_tags (account_id, name, color) VALUES (?, ?, ?)',
                (account_id, tag_name, tag_color)
            )
        
        db.commit()
        return jsonify({'status': 'success', 'message': 'Tag updated'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error updating tag: {str(e)}'})


@accounts_bp.route('/accounts/<int:account_id>/proxy', methods=['POST', 'GET'])
def manage_account_proxy(account_id):
    db = get_db()
    
    if request.method == 'POST':
        data = request.json
        proxy_id = data.get('proxy_id')
        
        try:
            db.execute(
                'INSERT OR REPLACE INTO account_proxies (account_id, proxy_id) VALUES (?, ?)',
                (account_id, proxy_id)
            )
            db.commit()
            return jsonify({'status': 'success', 'message': 'Proxy updated'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    
    elif request.method == 'GET':
        try:
            proxy = db.execute('''
                SELECT p.proxy 
                FROM proxies p
                JOIN account_proxies ap ON p.id = ap.proxy_id
                WHERE ap.account_id = ?
            ''', (account_id,)).fetchone()
            
            if proxy:
                return jsonify({'status': 'success', 'proxy': proxy['proxy']})
            return jsonify({'status': 'error', 'message': 'Proxy not found'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})

