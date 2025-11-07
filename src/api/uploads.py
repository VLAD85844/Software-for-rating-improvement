"""File upload endpoints."""

from flask import Blueprint, request, jsonify
from src.database.db import get_db
from src.utils.helpers import allowed_file

uploads_bp = Blueprint('uploads', __name__)


@uploads_bp.route('/proxies', methods=['POST'])
def upload_proxies():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'File not found'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'})
    
    if file and allowed_file(file.filename):
        try:
            content = file.read().decode('utf-8')
            proxies = [line.strip() for line in content.splitlines() if line.strip()]
            
            db = get_db()
            db.execute('DELETE FROM proxies')
            for proxy in proxies:
                db.execute(
                    'INSERT INTO proxies (proxy) VALUES (?)',
                    (proxy,)
                )
            db.commit()
            
            return jsonify({'status': 'success', 'message': f'Uploaded {len(proxies)} proxies to DB'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Error processing file: {str(e)}'})


@uploads_bp.route('/urls', methods=['POST'])
def upload_urls():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'File not found'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'})
    
    if file and allowed_file(file.filename):
        try:
            content = file.read().decode('utf-8')
            urls = [line.strip() for line in content.splitlines() if line.strip()]
            
            db = get_db()
            db.execute('DELETE FROM video_urls')
            for url in urls:
                db.execute(
                    'INSERT INTO video_urls (url) VALUES (?)',
                    (url,)
                )
            db.commit()
            
            return jsonify({'status': 'success', 'message': f'Uploaded {len(urls)} URLs to DB'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Error processing file: {str(e)}'})


@uploads_bp.route('/titles', methods=['POST'])
def upload_titles():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'File not found'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'})
    
    if file and allowed_file(file.filename):
        try:
            content = file.read().decode('utf-8')
            titles = [line.strip() for line in content.splitlines() if line.strip()]
            
            db = get_db()
            db.execute('DELETE FROM video_titles')
            for title in titles:
                db.execute(
                    'INSERT INTO video_titles (title) VALUES (?)',
                    (title,)
                )
            db.commit()
            
            return jsonify({
                'status': 'success',
                'message': f'Uploaded {len(titles)} video titles to DB'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error processing file: {str(e)}'
            })


@uploads_bp.route('/tags', methods=['POST'])
def upload_tags():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'File not found'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'})
    
    if file and allowed_file(file.filename):
        try:
            content = file.read().decode('utf-8')
            tags = [line.strip() for line in content.splitlines() if line.strip()]
            
            db = get_db()
            db.execute('DELETE FROM video_tags')
            for tag in tags:
                db.execute(
                    'INSERT INTO video_tags (tag) VALUES (?)',
                    (tag,)
                )
            db.commit()
            
            print(f"Uploaded {len(tags)} tags to DB")
            
            return jsonify({
                'status': 'success',
                'message': f'Uploaded {len(tags)} tags to DB'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error processing file: {str(e)}'
            })

