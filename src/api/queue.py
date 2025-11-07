"""Video queue management endpoints."""

from flask import Blueprint, request, jsonify
from src.database.db import get_db

queue_bp = Blueprint('queue', __name__)


@queue_bp.route('/queue', methods=['GET', 'POST', 'DELETE'])
def manage_queue():
    db = get_db()
    
    if request.method == 'GET':
        try:
            queue_items = db.execute('''
                SELECT id, tag, title, filter_strategy, priority, status, created_at
                FROM video_queue
                ORDER BY priority DESC, created_at ASC
            ''').fetchall()
            
            queue_list = []
            for item in queue_items:
                queue_list.append({
                    'id': item['id'],
                    'tag': item['tag'],
                    'title': item['title'],
                    'filter_strategy': item['filter_strategy'],
                    'priority': item['priority'],
                    'status': item['status'],
                    'created_at': item['created_at']
                })
            
            return jsonify({
                'status': 'success',
                'queue': queue_list
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error loading queue: {str(e)}'
            })
    
    elif request.method == 'POST':
        data = request.json
        tag = data.get('tag', '').strip()
        title = data.get('title', '').strip()
        filter_strategy = data.get('filter_strategy', 'none')
        priority = int(data.get('priority', 0))
        
        if not tag or not title:
            return jsonify({
                'status': 'error',
                'message': 'Tag and video title are required'
            })
        
        try:
            db.execute(
                'INSERT INTO video_queue (tag, title, filter_strategy, priority, status) VALUES (?, ?, ?, ?, ?)',
                (tag, title, filter_strategy, priority, 'pending')
            )
            db.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Video added to queue'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error adding to queue: {str(e)}'
            })
    
    elif request.method == 'DELETE':
        data = request.json
        item_ids = data.get('item_ids', [])
        
        if not item_ids:
            return jsonify({
                'status': 'error',
                'message': 'No items selected'
            })
        
        try:
            db.execute(
                'DELETE FROM video_queue WHERE id IN ({})'.format(','.join(['?'] * len(item_ids))),
                item_ids
            )
            db.commit()
            
            return jsonify({
                'status': 'success',
                'message': f'Deleted {len(item_ids)} items from queue'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error deleting from queue: {str(e)}'
            })


@queue_bp.route('/queue/<int:item_id>', methods=['PUT', 'DELETE'])
def manage_queue_item(item_id):
    db = get_db()
    
    if request.method == 'PUT':
        data = request.json
        status = data.get('status')
        
        if status not in ['pending', 'processing', 'completed', 'failed']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid status'
            })
        
        try:
            db.execute(
                'UPDATE video_queue SET status = ? WHERE id = ?',
                (status, item_id)
            )
            db.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Status updated'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error updating status: {str(e)}'
            })
    
    elif request.method == 'DELETE':
        try:
            db.execute('DELETE FROM video_queue WHERE id = ?', (item_id,))
            db.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Item deleted from queue'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error deleting item: {str(e)}'
            })


@queue_bp.route('/queue/stats')
def get_queue_stats():
    try:
        db = get_db()
        
        total = db.execute('SELECT COUNT(*) FROM video_queue').fetchone()[0]
        processing = db.execute('SELECT COUNT(*) FROM video_queue WHERE status = "processing"').fetchone()[0]
        completed = db.execute('SELECT COUNT(*) FROM video_queue WHERE status = "completed"').fetchone()[0]
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total': total,
                'processing': processing,
                'completed': completed
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })


@queue_bp.route('/queue/refresh', methods=['POST'])
def refresh_queue():
    """Force refresh video queue"""
    try:
        db = get_db()
        
        total = db.execute('SELECT COUNT(*) FROM video_queue').fetchone()[0]
        pending = db.execute('SELECT COUNT(*) FROM video_queue WHERE status = "pending"').fetchone()[0]
        processing = db.execute('SELECT COUNT(*) FROM video_queue WHERE status = "processing"').fetchone()[0]
        completed = db.execute('SELECT COUNT(*) FROM video_queue WHERE status = "completed"').fetchone()[0]
        
        return jsonify({
            'status': 'success',
            'message': 'Queue refreshed',
            'stats': {
                'total': total,
                'pending': pending,
                'processing': processing,
                'completed': completed
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

