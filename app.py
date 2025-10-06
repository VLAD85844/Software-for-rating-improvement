import os
import json
import sqlite3
import threading
import asyncio
import time
import signal
import sys
from flask import Flask, render_template, request, jsonify, send_from_directory
from pathlib import Path
from gologin_auth import GoLoginAuth
from datetime import datetime
from flask import g

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['DATABASE'] = 'youtube_soft.db'

script_thread = None
is_running = False
script_instance = None


def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


def get_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db


def close_db(e=None):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/start_script', methods=['POST'])
def start_script():
    global script_thread, is_running, script_instance

    if is_running:
        return jsonify({'status': 'error', 'message': 'Скрипт уже запущен'})

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

    with open('config.json', 'w') as f:
        json.dump(config, f)

    try:
        db = get_db()
        accounts = db.execute(
            'SELECT id, email, password FROM accounts WHERE id IN ({})'
            .format(','.join(['?'] * len(account_ids))),
            account_ids
        ).fetchall()

        if not accounts:
            return jsonify({'status': 'error', 'message': 'Не выбрано ни одного аккаунта'})

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

        return jsonify({'status': 'success',
                        'message': f'Скрипт запущен для {len(accounts)} аккаунтов (потоков: {threads_count})'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Ошибка запуска: {str(e)}'})


@app.route('/clear_profiles', methods=['POST'])
def clear_profiles():
    try:
        db = get_db()
        db.execute('DELETE FROM account_profiles')
        db.commit()
        return jsonify({'status': 'success', 'message': 'All profile associations cleared'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/stop_script', methods=['POST'])
def stop_script():
    global is_running, script_instance, script_thread

    if not is_running:
        return jsonify({'status': 'error', 'message': 'Скрипт не запущен'})

    try:
        is_running = False
        if script_instance:
            script_instance.stop()
            time.sleep(2)

        if script_thread and script_thread.is_alive():
            script_thread.join(timeout=10)
            if script_thread.is_alive():
                try:
                    print("Принудительное завершение потока")
                except:
                    pass

        try:
            from omnilogin_manager import OmniloginManager
            browser_manager = OmniloginManager()
            async def strict_close_browsers():
                await browser_manager.strict_kill_browser()
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(strict_close_browsers())
                print("Строгое закрытие браузеров выполнено")
            finally:
                loop.close()
        except Exception as e:
            print(f"Ошибка строгого закрытия браузеров: {str(e)}")

        return jsonify({'status': 'success', 'message': 'Скрипт остановлен и браузеры закрыты'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Ошибка остановки: {str(e)}'})


@app.route('/accounts', methods=['GET', 'POST', 'DELETE'])
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
                'message': f'Ошибка загрузки аккаунтов: {str(e)}'
            })

    elif request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'Файл не найден'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'Файл не выбран'})

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
                    'message': f'Добавлено {len(accounts)} аккаунтов'
                })

            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': f'Ошибка обработки файла: {str(e)}'
                })

    elif request.method == 'DELETE':
        data = request.json
        account_ids = data.get('account_ids', [])

        if not account_ids:
            return jsonify({'status': 'error', 'message': 'Не выбрано ни одного аккаунта'})

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
                'message': f'Удалено {db.total_changes} аккаунтов'
            })

        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Ошибка удаления: {str(e)}'
            })


@app.route('/accounts/<int:account_id>/tag', methods=['POST'])
def update_account_tag(account_id):
    db = get_db()
    data = request.json
    tag_name = data.get('tag_name')
    tag_color = data.get('tag_color')

    try:
        account = db.execute('SELECT id FROM accounts WHERE id = ?', (account_id,)).fetchone()
        if not account:
            return jsonify({'status': 'error', 'message': 'Аккаунт не найден'})
        db.execute('DELETE FROM account_tags WHERE account_id = ?', (account_id,))
        if tag_name and tag_color:
            db.execute(
                'INSERT INTO account_tags (account_id, name, color) VALUES (?, ?, ?)',
                (account_id, tag_name, tag_color)
            )

        db.commit()
        return jsonify({'status': 'success', 'message': 'Метка обновлена'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Ошибка обновления метки: {str(e)}'})


@app.route('/tags', methods=['POST'])
def upload_tags():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Файл не найден'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'Файл не выбран'})

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

            print(f"Загружено {len(tags)} тегов в БД")

            return jsonify({
                'status': 'success',
                'message': f'Загружено {len(tags)} тегов в БД'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Ошибка обработки файла: {str(e)}'
            })


@app.route('/proxies', methods=['POST'])
def upload_proxies():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Файл не найден'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'Файл не выбран'})

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

            return jsonify({'status': 'success', 'message': f'Загружено {len(proxies)} прокси в БД'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Ошибка обработки файла: {str(e)}'})


@app.route('/accounts/<int:account_id>/proxy', methods=['POST'])
def update_account_proxy(account_id):
    db = get_db()
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


@app.route('/accounts/<int:account_id>/proxy', methods=['GET'])
def get_account_proxy(account_id):
    db = get_db()
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


@app.route('/urls', methods=['POST'])
def upload_urls():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Файл не найден'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'Файл не выбран'})

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

            return jsonify({'status': 'success', 'message': f'Загружено {len(urls)} URL в БД'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Ошибка обработки файла: {str(e)}'})


@app.route('/titles', methods=['POST'])
def upload_titles():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Файл не найден'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'Файл не выбран'})

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
                'message': f'Загружено {len(titles)} названий видео в БД'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Ошибка обработки файла: {str(e)}'
            })


@app.route('/status')
def get_status():
    global is_running

    try:
        db = get_db()
        accounts_count = db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0]
        proxies_count = count_lines('proxies.txt') if os.path.exists('proxies.txt') else 0
        urls_count = count_lines('video_urls.txt') if os.path.exists('video_urls.txt') else 0

        return jsonify({
            'is_running': is_running,
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


@app.route('/stats')
def get_stats():
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


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/queue', methods=['GET', 'POST', 'DELETE'])
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
                'message': f'Ошибка загрузки очереди: {str(e)}'
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
                'message': 'Тег и название видео обязательны'
            })

        try:
            db.execute(
                'INSERT INTO video_queue (tag, title, filter_strategy, priority, status) VALUES (?, ?, ?, ?, ?)',
                (tag, title, filter_strategy, priority, 'pending')
            )
            db.commit()

            return jsonify({
                'status': 'success',
                'message': 'Видео добавлено в очередь'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Ошибка добавления в очередь: {str(e)}'
            })

    elif request.method == 'DELETE':
        data = request.json
        item_ids = data.get('item_ids', [])

        if not item_ids:
            return jsonify({
                'status': 'error',
                'message': 'Не выбрано ни одного элемента'
            })

        try:
            db.execute(
                'DELETE FROM video_queue WHERE id IN ({})'.format(','.join(['?'] * len(item_ids))),
                item_ids
            )
            db.commit()

            return jsonify({
                'status': 'success',
                'message': f'Удалено {len(item_ids)} элементов из очереди'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Ошибка удаления: {str(e)}'
            })


@app.route('/queue/<int:item_id>', methods=['PUT', 'DELETE'])
def manage_queue_item(item_id):
    db = get_db()

    if request.method == 'PUT':
        data = request.json
        status = data.get('status')

        if status not in ['pending', 'processing', 'completed', 'failed']:
            return jsonify({
                'status': 'error',
                'message': 'Неверный статус'
            })

        try:
            db.execute(
                'UPDATE video_queue SET status = ? WHERE id = ?',
                (status, item_id)
            )
            db.commit()

            return jsonify({
                'status': 'success',
                'message': 'Статус обновлен'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Ошибка обновления: {str(e)}'
            })

    elif request.method == 'DELETE':
        try:
            db.execute('DELETE FROM video_queue WHERE id = ?', (item_id,))
            db.commit()

            return jsonify({
                'status': 'success',
                'message': 'Элемент удален из очереди'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Ошибка удаления: {str(e)}'
            })


@app.route('/queue/stats')
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


@app.route('/stop/<profile_id>', methods=['GET'])
def stop_profile(profile_id):
    """Закрывает браузер по profile_id"""
    try:
        from omnilogin_manager import OmniloginManager

        browser_manager = OmniloginManager()
        async def close_profile():
            await browser_manager.close_profile(profile_id)
        import asyncio
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


@app.route('/queue/refresh', methods=['POST'])
def refresh_queue():
    """Принудительно обновляет очередь видео"""
    try:
        db = get_db()

        total = db.execute('SELECT COUNT(*) FROM video_queue').fetchone()[0]
        pending = db.execute('SELECT COUNT(*) FROM video_queue WHERE status = "pending"').fetchone()[0]
        processing = db.execute('SELECT COUNT(*) FROM video_queue WHERE status = "processing"').fetchone()[0]
        completed = db.execute('SELECT COUNT(*) FROM video_queue WHERE status = "completed"').fetchone()[0]

        return jsonify({
            'status': 'success',
            'message': 'Очередь обновлена',
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


def run_script_in_thread(script):
    """Запуск скрипта в отдельном потоке с обработкой асинхронного кода"""
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(script.run())
    except Exception as e:
        try:
            print(f"Ошибка в потоке скрипта: {str(e)}")
        except:
            pass
    finally:
        try:
            if loop and not loop.is_closed():
                loop.close()
        except:
            pass


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['txt']


def count_lines(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
            return len(lines)
    except:
        return 0


def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    try:
        print("\nПолучен сигнал завершения, останавливаем приложение...")

        global is_running, script_instance, script_thread
        if is_running and script_instance:
            is_running = False
            script_instance.stop()

        if script_thread and script_thread.is_alive():
            script_thread.join(timeout=5)

        print("Приложение корректно завершено")
        sys.exit(0)
    except Exception as e:
        try:
            print(f"Ошибка при завершении: {str(e)}")
        except:
            pass
        sys.exit(1)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not os.path.exists(app.config['DATABASE']):
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)