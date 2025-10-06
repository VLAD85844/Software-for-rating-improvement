import asyncio
import sqlite3
import requests
import random
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from concurrent.futures import ThreadPoolExecutor
import threading
import psutil
import platform
import subprocess
from omnilogin_manager import OmniloginManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


class GoLoginAuth:
    def __init__(self, threads=1, account_ids=None, enable_title_search=False):
        self.browser_manager = OmniloginManager()
        self.threads = threads
        self.accounts = []
        self.proxies = []
        self.user_agents = []
        self.video_urls = []
        self.accounts = []
        self.account_ids = account_ids or []
        self._stop_event = threading.Event()
        self._running = True
        self.referers = [
            "https://www.reddit.com/",
            "https://twitter.com/",
            "https://www.facebook.com/",
            "https://www.instagram.com/",
            "https://www.tumblr.com/",
            "https://www.pinterest.com/",
            "https://www.linkedin.com/",
            "https://www.quora.com/",
            "https://www.vk.com/",
            "https://www.tiktok.com/"
        ]
        self.config = {
            'watch_duration': '50%',
            'max_actions_per_account': 3,
            'human_behavior': True,
            'use_proxy': True,
            'enable_likes': True,
            'enable_subscriptions': False,
            'open_devtools': False,
            'urls_strategy': 'random',
            'enable_title_search': enable_title_search
        }
        self.db = sqlite3.connect('youtube_soft.db')
        self.db.row_factory = sqlite3.Row
        self.load_config()
        self.video_queue = []
        self.load_video_queue()

    def load_config(self):
        """Загрузка аккаунтов с recovery_email"""
        try:
            if self.account_ids:
                query = 'SELECT id, email, password, recovery_email FROM accounts WHERE id IN ({})'.format(
                    ','.join(['?'] * len(self.account_ids))
                )
                accounts = self.db.execute(query, self.account_ids).fetchall()
            else:
                accounts = self.db.execute('SELECT id, email, password, recovery_email FROM accounts').fetchall()

            self.accounts = [
                (acc['email'], acc['password'], acc['recovery_email'])
                for acc in accounts
            ]

            if not self.accounts:
                raise Exception("Не загружены аккаунты из базы данных")

            if self.config['use_proxy']:
                self.proxies = [row['proxy'] for row in
                                self.db.execute('SELECT proxy FROM proxies WHERE status = "active"').fetchall()]
                print(f"Загружено {len(self.proxies)} прокси из БД")

            if Path('user_agents.txt').exists():
                with open('user_agents.txt', 'r') as f:
                    self.user_agents = [line.strip() for line in f if line.strip()]
                print(f"Загружено {len(self.user_agents)} User-Agent")
            else:
                self.user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
                ]

            video_urls = self.db.execute('SELECT url FROM video_urls').fetchall()
            self.video_urls = [row['url'] for row in video_urls]

            print(f"Загружено {len(self.video_urls)} URL видео из БД")

            if not self.video_urls and not self.config.get('enable_title_search', False):
                print("Предупреждение: Не загружены видео URL (но это не критично при поиске по названию)")

            db = sqlite3.connect('youtube_soft.db')
            cursor = db.execute('SELECT tag FROM video_tags')
            self.video_tags = [row[0] for row in cursor.fetchall()]
            print(f"Загружено {len(self.video_tags)} тегов видео из БД")
            db.close()

            db = sqlite3.connect('youtube_soft.db')
            try:
                video_titles = db.execute('SELECT title FROM video_titles').fetchall()
                self.video_titles = [row['title'].strip() for row in video_titles if row['title'].strip()]
                print(f"Загружено {len(self.video_titles)} названий видео из БД")
            finally:
                db.close()

            if Path('config.json').exists():
                with open('config.json', 'r') as f:
                    config_data = json.load(f)
                    self.config.update({
                        'watch_duration': str(config_data.get('watch_duration', '30')),
                        'duration_mode': config_data.get('duration_mode', 'fixed'),
                        'min_watch_duration': config_data.get('min_watch_duration', 30),
                        'max_watch_duration': config_data.get('max_watch_duration', 180),
                        'max_actions_per_account': config_data.get('max_actions_per_account', 3),
                        'human_behavior': config_data.get('human_behavior', True),
                        'use_proxy': config_data.get('use_proxy', True),
                        'enable_likes': config_data.get('enable_likes', True),
                        'enable_subscriptions': config_data.get('enable_subscriptions', False),
                        'enable_referral': config_data.get('enable_referral', True),
                        'open_devtools': config_data.get('open_devtools', False),
                        'urls_strategy': config_data.get('urls_strategy', 'random'),
                        'create_channel': config_data.get('create_channel', False),
                        'enable_title_search': config_data.get('enable_title_search', False),
                        'filter_strategy': config_data.get('filter_strategy', 'none')
                    })

                if self.config['enable_title_search']:
                    db = sqlite3.connect('youtube_soft.db')
                    try:
                        video_titles = db.execute('SELECT title FROM video_titles').fetchall()
                        self.video_titles = [row['title'] for row in video_titles]
                        print(f"Загружено {len(self.video_titles)} названий видео из БД")
                    finally:
                        db.close()

        except Exception as e:
            raise Exception(f"Ошибка загрузки конфигурации: {str(e)}")
        finally:
            self.db.close()

    def load_video_queue(self):
        """Загрузка очереди видео из базы данных"""
        try:
            db = sqlite3.connect('youtube_soft.db')
            db.row_factory = sqlite3.Row

            queue_items = db.execute('''
                SELECT id, tag, title, filter_strategy, priority, status
                FROM video_queue
                WHERE status IN ('pending', 'processing')
                ORDER BY priority DESC, created_at ASC
            ''').fetchall()

            self.video_queue = [
                {
                    'id': item['id'],
                    'tag': item['tag'],
                    'title': item['title'],
                    'filter_strategy': item['filter_strategy'],
                    'priority': item['priority'],
                    'status': item['status']
                }
                for item in queue_items
            ]

            print(f"Загружено {len(self.video_queue)} элементов в очередь видео")
            db.close()
        except Exception as e:
            print(f"Ошибка загрузки очереди видео: {str(e)}")
            self.video_queue = []

    def get_next_queue_item(self):
        """Получает следующий элемент из очереди с обновлением из БД"""
        self.refresh_queue_from_db()

        if not self.video_queue:
            return None

        for i, item in enumerate(self.video_queue):
            if item['status'] in ['pending', 'processing']:
                item = self.video_queue.pop(i)
                self.video_queue.append(item)
                return item

        return None

    def get_account_queue_progress(self, account_id):
        """Получает прогресс аккаунта в очереди - какие элементы уже обработаны"""
        try:
            db = sqlite3.connect('youtube_soft.db')
            db.row_factory = sqlite3.Row

            all_items = db.execute('''
                SELECT id, tag, title, filter_strategy, priority, status
                FROM video_queue
                ORDER BY priority DESC, created_at ASC
            ''').fetchall()

            processed_items = db.execute('''
                SELECT queue_item_id
                FROM queue_progress
                WHERE account_id = ? AND status = 'completed'
            ''', (account_id,)).fetchall()

            processed_ids = {row[0] for row in processed_items}

            unprocessed_items = []
            for item in all_items:
                if item['id'] not in processed_ids:
                    unprocessed_items.append({
                        'id': item['id'],
                        'tag': item['tag'],
                        'title': item['title'],
                        'filter_strategy': item['filter_strategy'],
                        'priority': item['priority'],
                        'status': item['status']
                    })

            db.close()
            return unprocessed_items

        except Exception as e:
            print(f"Ошибка получения прогресса аккаунта {account_id}: {str(e)}")
            return []

    def get_next_queue_item_for_account(self, account_id):
        """Получает следующий элемент очереди для конкретного аккаунта"""
        self.refresh_queue_from_db()

        unprocessed_items = self.get_account_queue_progress(account_id)

        if not unprocessed_items:
            return None

        return unprocessed_items[0]

    def refresh_queue_from_db(self):
        """Обновляет очередь из базы данных для получения новых элементов"""
        try:
            db = sqlite3.connect('youtube_soft.db')
            db.row_factory = sqlite3.Row

            queue_items = db.execute('''
                SELECT id, tag, title, filter_strategy, priority, status
                FROM video_queue
                WHERE status IN ('pending', 'processing')
                ORDER BY priority DESC, created_at ASC
            ''').fetchall()

            new_queue = [
                {
                    'id': item['id'],
                    'tag': item['tag'],
                    'title': item['title'],
                    'filter_strategy': item['filter_strategy'],
                    'priority': item['priority'],
                    'status': item['status']
                }
                for item in queue_items
            ]

            current_ids = {item['id'] for item in self.video_queue}
            new_ids = {item['id'] for item in new_queue}

            if new_ids - current_ids:
                print(f"[Очередь] Обнаружены новые элементы: {new_ids - current_ids}")
                self.video_queue = new_queue

            db.close()
        except Exception as e:
            print(f"[Очередь] Ошибка обновления очереди: {str(e)}")

    def update_queue_item_status(self, item_id, status):
        """Обновляет статус элемента очереди"""
        try:
            db = sqlite3.connect('youtube_soft.db')
            db.execute('UPDATE video_queue SET status = ? WHERE id = ?', (status, item_id))
            db.commit()
            db.close()

            for item in self.video_queue:
                if item['id'] == item_id:
                    item['status'] = status
                    break
        except Exception as e:
            print(f"Ошибка обновления статуса очереди: {str(e)}")

    def record_queue_progress(self, item_id, account_id, status):
        """Записывает прогресс обработки элемента очереди аккаунтом"""
        try:
            db = sqlite3.connect('youtube_soft.db')

            if status == 'processing':
                db.execute('''
                    INSERT OR REPLACE INTO queue_progress (queue_item_id, account_id, status, started_at)
                    VALUES (?, ?, ?, ?)
                ''', (item_id, account_id, status, datetime.now()))
            elif status in ['completed', 'failed']:
                db.execute('''
                    UPDATE queue_progress 
                    SET status = ?, completed_at = ?
                    WHERE queue_item_id = ? AND account_id = ?
                ''', (status, datetime.now(), item_id, account_id))

                if db.total_changes == 0:
                    db.execute('''
                        INSERT INTO queue_progress (queue_item_id, account_id, status, started_at, completed_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (item_id, account_id, status, datetime.now(), datetime.now()))

            db.commit()
            db.close()
        except Exception as e:
            print(f"Ошибка записи прогресса очереди: {str(e)}")

    async def kill_browser_processes(self):
        """Закрывает все процессы браузера"""
        try:
            pass
        except Exception as e:
            print(f"[Kill] Ошибка закрытия процессов: {str(e)}")
            return set()

    async def get_existing_profile(self, account_id):
        db = sqlite3.connect('youtube_soft.db')
        try:
            cursor = db.execute('SELECT profile_id FROM account_profiles WHERE account_id = ?', (account_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            db.close()

    async def save_profile_for_account(self, account_id, profile_id):
        db = sqlite3.connect('youtube_soft.db')
        try:
            db.execute('INSERT OR REPLACE INTO account_profiles (account_id, profile_id) VALUES (?, ?)',
                       (account_id, profile_id))
            db.commit()
        finally:
            db.close()

    async def process_accounts_in_batches(self):
        """Обрабатывает аккаунты батчами по количеству потоков с поддержкой очереди"""
        original_total_accounts = len(self.accounts)
        total_accounts = original_total_accounts
        batch_size = self.threads
        current_batch_start = 0
        empty_queue_count = 0
        processed_all_accounts = False

        self._original_accounts = self.accounts.copy()
        if hasattr(self, 'account_ids') and self.account_ids:
            self._original_account_ids = self.account_ids.copy()
        if hasattr(self, 'user_agents') and self.user_agents:
            self._original_user_agents = self.user_agents.copy()

        while self._running:
            self.refresh_queue_from_db()

            batch_end = min(current_batch_start + batch_size, total_accounts)
            current_batch = list(range(current_batch_start, batch_end))

            print(f"\n=== Обработка аккаунтов {current_batch_start + 1}-{batch_end} из {total_accounts} ===")

            await self.run_batch(current_batch)

            current_batch_start = batch_end
            print(f"Переходим к следующему батчу: {current_batch_start}/{total_accounts}")

            if current_batch_start >= total_accounts:
                processed_all_accounts = True
                print("Все аккаунты обработаны, проверяем новые элементы в очереди")

                if self.config['enable_title_search']:
                    available_items = [item for item in self.video_queue if item['status'] in ['pending', 'processing']]

                    accounts_with_unprocessed_items = []
                    for account_idx in range(total_accounts):
                        account_id = self.account_ids[account_idx] if self.account_ids and account_idx < len(
                            self.account_ids) else account_idx + 1
                        unprocessed_items = self.get_account_queue_progress(account_id)
                        if unprocessed_items:
                            accounts_with_unprocessed_items.append(account_idx)

                    if not available_items and not accounts_with_unprocessed_items:
                        empty_queue_count += 1
                        print(
                            f"Очередь видео пуста и все аккаунты обработали все элементы (проверка {empty_queue_count}/3)")

                        if empty_queue_count >= 3:
                            print("Очередь видео пуста 3 раза подряд, завершаем работу")
                            break

                        await asyncio.sleep(10)
                        continue
                    else:
                        empty_queue_count = 0

                        if available_items:
                            print(f"Обнаружены новые элементы в очереди ({len(available_items)})")

                        if accounts_with_unprocessed_items:
                            print(
                                f"Аккаунты {accounts_with_unprocessed_items} не обработали все элементы, перезапускаем обработку")
                            self.accounts = [self.accounts[i] for i in accounts_with_unprocessed_items]
                            if hasattr(self, 'account_ids') and self.account_ids:
                                self.account_ids = [self.account_ids[i] for i in accounts_with_unprocessed_items]
                            if hasattr(self, 'user_agents') and self.user_agents:
                                self.user_agents = [self.user_agents[i] for i in accounts_with_unprocessed_items]

                            total_accounts = len(self.accounts)
                            current_batch_start = 0
                            print(
                                f"Запускаем обработку только для аккаунтов с необработанными элементами: {accounts_with_unprocessed_items}")
                        else:
                            current_batch_start = 0
                            if hasattr(self, '_original_accounts'):
                                self.accounts = self._original_accounts
                                if hasattr(self, '_original_account_ids'):
                                    self.account_ids = self._original_account_ids
                                if hasattr(self, '_original_user_agents'):
                                    self.user_agents = self._original_user_agents
                                total_accounts = original_total_accounts

                        processed_all_accounts = False
                else:
                    print("Поиск по названию отключен, завершаем работу")
                    break

            if self._running:
                await asyncio.sleep(5)

    async def run_batch(self, account_indices):
        """Обрабатывает указанные аккаунты в пуле потоков"""
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            loop = asyncio.get_event_loop()
            futures = []

            for idx in account_indices:
                if not self._running:
                    break
                future = loop.run_in_executor(
                    executor,
                    self.process_account_sync,
                    idx
                )
                futures.append(future)
            results = await asyncio.gather(*futures, return_exceptions=True)
            for i, result in zip(account_indices, results):
                if isinstance(result, Exception):
                    print(f"[Аккаунт {i}] Ошибка: {str(result)}")
                elif result is False:
                    print(f"[Аккаунт {i}] Завершено с ошибкой")
                else:
                    print(f"[Аккаунт {i}] Успешно завершено")

    def process_account_sync(self, account_idx):
        """Синхронная обертка для обработки аккаунта"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.process_account(account_idx))
        except Exception as e:
            print(f"[Аккаунт {account_idx}] Критическая ошибка: {str(e)}")
            return False
        finally:
            loop.close()

    async def run_script_in_thread(script):
        """Запуск скрипта в отдельном потоке с обработкой асинхронного кода"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            await script.run()
        except Exception as e:
            print(f"Ошибка в потоке скрипта: {str(e)}")
        finally:
            if loop:
                loop.close()

    async def search_video_by_tag(self, driver, tag, filter_strategy='none', target_title=None):
        """Поиск видео по тегу с применением фильтров (Selenium version)"""
        print(f"[Поиск] Начинаем поиск по тегу: {tag} с фильтром: {filter_strategy}")
        if target_title:
            print(f"[ОТЛАДКА] Ищем видео с названием: {target_title}")
        else:
            print(f"[ОТЛАДКА] Ищем среди {len(self.video_titles)} названий: {self.video_titles[:3]}...")

        try:
            driver.get("https://www.youtube.com")
            await self.human_like_movement(driver)

            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="search_query"]'))
            )
            search_box.clear()
            search_box.send_keys(tag)
            search_box.send_keys(Keys.RETURN)
            time.sleep(3)

            if filter_strategy != 'none':
                original_filter = self.config.get('filter_strategy', 'none')
                self.config['filter_strategy'] = filter_strategy
                await self.apply_search_filters(driver)
                self.config['filter_strategy'] = original_filter

            scroll_duration = 60
            scroll_step = 300
            scroll_delay = 0.5
            scroll_interval = 0.5
            total_steps = int(scroll_duration / scroll_interval)

            print(f"[Поиск] Начинаем плавную прокрутку в течение {scroll_duration} секунд")

            start_time = time.time()
            last_height = driver.execute_script("return document.documentElement.scrollHeight")

            for step in range(total_steps):
                if not self._running:
                    print("[Поиск] Поиск прерван (сигнал остановки)")
                    return False

                driver.execute_script(f"window.scrollBy(0, {scroll_step})")
                time.sleep(scroll_delay)

                new_height = driver.execute_script("return document.documentElement.scrollHeight")
                if new_height == last_height and step > 10:
                    break

                last_height = new_height

                videos = driver.find_elements(By.TAG_NAME, 'ytd-video-renderer')
                for video in videos:
                    try:
                        video_title = video.find_element(By.CSS_SELECTOR, '#video-title').text

                        if target_title:
                            clean_target_title = target_title.strip().lower()
                            clean_video_title = video_title.strip().lower()
                            if (clean_target_title in clean_video_title or
                                    clean_video_title in clean_target_title):
                                print(f"[Поиск] Найдено совпадение: {video_title}")

                                click_success = False

                                try:
                                    video_link = video.find_element(By.CSS_SELECTOR, 'a#video-title')
                                    if video_link:
                                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});",
                                                              video_link)
                                        time.sleep(1)
                                        video_link.click()
                                        print("[Поиск] Клик по ссылке видео выполнен")
                                        return True
                                except Exception as e:
                                    pass

                                if not click_success:
                                    try:
                                        thumbnail = video.find_element(By.CSS_SELECTOR, 'a#thumbnail')
                                        if thumbnail:
                                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});",
                                                                  thumbnail)
                                            time.sleep(1)
                                            thumbnail.click()
                                            print("[Поиск] Клик по миниатюре выполнен")
                                            return True
                                    except Exception as e:
                                        pass

                                if not click_success:
                                    try:
                                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", video)
                                        time.sleep(1)
                                        driver.execute_script("arguments[0].click();", video)
                                        print("[Поиск] Клик по элементу видео выполнен")
                                        return True
                                    except Exception as e:
                                        pass

                                if not click_success:
                                    try:
                                        links = video.find_elements(By.TAG_NAME, 'a')
                                        for link in links:
                                            try:
                                                if link.is_displayed() and link.is_enabled():
                                                    driver.execute_script(
                                                        "arguments[0].scrollIntoView({block: 'center'});", link)
                                                    time.sleep(1)
                                                    link.click()
                                                    print("[Поиск] Клик по найденной ссылке выполнен")
                                                    return True
                                            except:
                                                continue
                                    except Exception as e:
                                        pass
                        else:
                            for title in self.video_titles:
                                clean_title = title.strip().lower()
                                clean_video_title = video_title.strip().lower()
                                if clean_title in clean_video_title:
                                    print(f"[Поиск] Найдено совпадение: {video_title}")

                                    click_success = False

                                    try:
                                        video_link = video.find_element(By.CSS_SELECTOR, 'a#video-title')
                                        if video_link:
                                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});",
                                                                  video_link)
                                            time.sleep(1)
                                            video_link.click()
                                            print("[Поиск] Клик по ссылке видео выполнен")
                                            return True
                                    except Exception as e:
                                        pass

                                    if not click_success:
                                        try:
                                            thumbnail = video.find_element(By.CSS_SELECTOR, 'a#thumbnail')
                                            if thumbnail:
                                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});",
                                                                      thumbnail)
                                                time.sleep(1)
                                                thumbnail.click()
                                                print("[Поиск] Клик по миниатюре выполнен")
                                                return True
                                        except Exception as e:
                                            pass

                                    if not click_success:
                                        try:
                                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});",
                                                                  video)
                                            time.sleep(1)
                                            driver.execute_script("arguments[0].click();", video)
                                            print("[Поиск] Клик по элементу видео выполнен")
                                            return True
                                        except Exception as e:
                                            pass

                                    if not click_success:
                                        try:
                                            links = video.find_elements(By.TAG_NAME, 'a')
                                            for link in links:
                                                try:
                                                    if link.is_displayed() and link.is_enabled():
                                                        driver.execute_script(
                                                            "arguments[0].scrollIntoView({block: 'center'});", link)
                                                        time.sleep(1)
                                                        link.click()
                                                        print("[Поиск] Клик по найденной ссылке выполнен")
                                                        return True
                                                except:
                                                    continue
                                        except Exception as e:
                                            pass



                    except Exception as e:
                        print(f"[Поиск] Ошибка при обработке видео: {str(e)}")
                        continue

                if random.random() < 0.3:
                    await self.human_like_movement(driver)

                if (time.time() - start_time) > scroll_duration:
                    break

                time.sleep(scroll_interval)

            print("[Поиск] Совпадение не найдено")
            return False

        except Exception as e:
            print(f"[Поиск] Критическая ошибка: {str(e)}")
            driver.save_screenshot(f"search_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            return False

    async def search_video_by_title(self, driver, video_title, filter_strategy='none'):
        """Поиск видео по названию с применением фильтров"""
        print(f"[Поиск] Начинаем поиск по названию: {video_title} с фильтром: {filter_strategy}")
        print(f"[ОТЛАДКА] Ищем видео с названием: '{video_title}'")

        try:
            driver.get("https://www.youtube.com")
            await self.human_like_movement(driver)

            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="search_query"]'))
            )
            search_box.clear()
            search_box.send_keys(video_title)
            search_box.send_keys(Keys.RETURN)
            time.sleep(3)

            if filter_strategy != 'none':
                original_filter = self.config.get('filter_strategy', 'none')
                self.config['filter_strategy'] = filter_strategy
                await self.apply_search_filters(driver)
                self.config['filter_strategy'] = original_filter

            scroll_duration = 60
            scroll_step = 300
            scroll_delay = 0.5
            scroll_interval = 0.5
            total_steps = int(scroll_duration / scroll_interval)

            print(f"[Поиск] Начинаем плавную прокрутку в течение {scroll_duration} секунд")

            start_time = time.time()
            last_height = driver.execute_script("return document.documentElement.scrollHeight")

            for step in range(total_steps):
                if not self._running:
                    print("[Поиск] Поиск прерван (сигнал остановки)")
                    return False

                driver.execute_script(f"window.scrollBy(0, {scroll_step})")
                time.sleep(scroll_delay)

                new_height = driver.execute_script("return document.documentElement.scrollHeight")
                if new_height == last_height and step > 10:
                    break

                last_height = new_height

                videos = driver.find_elements(By.TAG_NAME, 'ytd-video-renderer')
                for video in videos:
                    try:
                        video_title_element = video.find_element(By.CSS_SELECTOR, '#video-title')
                        current_video_title = video_title_element.text

                        clean_search_title = video_title.strip().lower()
                        clean_current_title = current_video_title.strip().lower()
                        if (clean_search_title in clean_current_title or
                                clean_current_title in clean_search_title):
                            print(f"[Поиск] Найдено совпадение: {current_video_title}")

                            click_success = False

                            try:
                                video_link = video.find_element(By.CSS_SELECTOR, 'a#video-title')
                                if video_link:
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", video_link)
                                    time.sleep(1)
                                    video_link.click()
                                    print("[Поиск] Клик по ссылке видео выполнен")
                                    return True
                            except Exception as e:
                                pass

                            if not click_success:
                                try:
                                    thumbnail = video.find_element(By.CSS_SELECTOR, 'a#thumbnail')
                                    if thumbnail:
                                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});",
                                                              thumbnail)
                                        time.sleep(1)
                                        thumbnail.click()
                                        print("[Поиск] Клик по миниатюре выполнен")
                                        return True
                                except Exception as e:
                                    pass

                            if not click_success:
                                try:
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", video)
                                    time.sleep(1)
                                    driver.execute_script("arguments[0].click();", video)
                                    print("[Поиск] Клик по элементу видео выполнен")
                                    return True
                                except Exception as e:
                                    pass

                            if not click_success:
                                try:
                                    links = video.find_elements(By.TAG_NAME, 'a')
                                    for link in links:
                                        try:
                                            if link.is_displayed() and link.is_enabled():
                                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});",
                                                                      link)
                                                time.sleep(1)
                                                link.click()
                                                print("[Поиск] Клик по найденной ссылке выполнен")
                                                return True
                                        except:
                                            continue
                                except Exception as e:
                                    pass



                    except Exception as e:
                        print(f"[Поиск] Ошибка при обработке видео: {str(e)}")
                        continue

                if random.random() < 0.3:
                    await self.human_like_movement(driver)

                if (time.time() - start_time) > scroll_duration:
                    break

                time.sleep(scroll_interval)

            print("[Поиск] Совпадение не найдено")
            return False

        except Exception as e:
            print(f"[Поиск] Критическая ошибка: {str(e)}")
            driver.save_screenshot(f"search_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            return False

    async def apply_search_filters(self, driver):
        """Оптимизированное применение фильтров поиска"""
        try:
            filter_strategy = self.config.get('filter_strategy', 'none')
            if filter_strategy == 'none':
                return True

            filter_button = None
            try:
                filter_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR,
                                                'button[aria-label*="filter"], button[aria-label*="lọc"], button[aria-label*="фильтр"]'))
                )
            except TimeoutException:
                buttons = driver.find_elements(By.TAG_NAME, 'button')
                for btn in buttons:
                    if btn.is_displayed():
                        text = btn.text.lower()
                        if 'filter' in text or 'фильтр' in text or 'lọc' in text:
                            filter_button = btn
                            break

            if not filter_button:
                return False

            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", filter_button)
            driver.execute_script("arguments[0].click();", filter_button)
            time.sleep(0.5)

            if filter_strategy == 'last-hour':
                return await self._apply_time_filter(driver, "Last hour")
            elif filter_strategy == 'today':
                return await self._apply_time_filter(driver, "Today")
            elif filter_strategy == 'week':
                return await self._apply_time_filter(driver, "This week")
            elif filter_strategy == 'month':
                return await self._apply_time_filter(driver, "This month")

            return True

        except Exception as e:
            print(f"[Фильтры] Ошибка: {str(e)}")
            return False

    async def _apply_time_filter(self, driver, filter_name):
        """Применение временного фильтра с усиленной логикой"""
        try:
            print(f"[Фильтры] Пытаемся применить фильтр: {filter_name}")

            filter_text_variations = {
                "Last hour": ["Last hour", "Última hora", "Một giờ qua", "Последний час"],
                "Today": ["Today", "Hôm nay", "Сегодня", "Vandaag"],
                "This week": ["This week", "Tuần này", "Esta semana", "На этой неделе"],
                "This month": ["This month", "Tháng này", "Este mes", "В этом месяце"]
            }

            texts_to_search = filter_text_variations.get(filter_name, [filter_name])

            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'ytd-search-filter-group-renderer')))
            time.sleep(2)

            filter_elements = driver.find_elements(By.CSS_SELECTOR, 'ytd-search-filter-renderer')

            if not filter_elements:
                raise Exception("Не найдены элементы фильтров")

            print(f"[Фильтры] Найдено {len(filter_elements)} элементов фильтров")
            target_element = None

            for element in filter_elements:
                try:
                    element_text = element.text.strip().lower()
                    if not element_text:
                        continue

                    for variation in texts_to_search:
                        if variation.lower() in element_text:
                            print(f"[Фильтры] Найден элемент с текстом: {element.text.strip()} (искали: {variation})")
                            target_element = element
                            break

                    if target_element:
                        break
                except Exception as e:
                    print(f"[Фильтры] Ошибка проверки элемента: {str(e)}")
                    continue

            if not target_element:
                raise Exception(f"Не найден фильтр для: {filter_name} (искали варианты: {texts_to_search})")

            results_before = len(driver.find_elements(By.CSS_SELECTOR, 'ytd-video-renderer'))

            for attempt in range(3):
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                                          target_element)
                    time.sleep(1)

                    if filter_name == "Today":
                        clickable = target_element.find_element(By.CSS_SELECTOR, 'a#endpoint, div#label')
                        if clickable:
                            driver.execute_script("arguments[0].click();", clickable)
                            print("[Фильтры] Клик по внутреннему элементу для Hôm nay")
                        else:
                            driver.execute_script("arguments[0].click();", target_element)
                    else:
                        WebDriverWait(driver, 3).until(EC.element_to_be_clickable(target_element))
                        ActionChains(driver).move_to_element(target_element).pause(0.5).click().perform()

                    print(f"[Фильтры] Попытка {attempt + 1}: Клик по фильтру {target_element.text.strip()}")
                    time.sleep(2)

                    current_results = len(driver.find_elements(By.CSS_SELECTOR, 'ytd-video-renderer'))
                    if current_results != results_before:
                        print(
                            f"[Фильтры] Фильтр успешно применен (изменение результатов с {results_before} до {current_results})")
                        return True

                except Exception as e:
                    print(f"[Фильтры] Ошибка при клике (попытка {attempt + 1}): {str(e)}")
                    time.sleep(1)
                    continue

            print("[Фильтры] Стандартные клики не сработали, пробуем альтернативные методы")

            try:
                if filter_name == "Today":
                    location = target_element.location
                    size = target_element.size
                    x = location['x'] + size['width'] * 0.3
                    y = location['y'] + size['height'] * 0.7

                    ActionChains(driver).move_by_offset(x, y).click().perform()
                    print(f"[Фильтры] Клик по координатам ({x}, {y}) для Hôm nay")
                else:
                    driver.execute_script("arguments[0].click();", target_element)
                    print("[Фильтры] Клик через JavaScript")

                time.sleep(2)

                current_results = len(driver.find_elements(By.CSS_SELECTOR, 'ytd-video-renderer'))
                if current_results != results_before:
                    print(
                        f"[Фильтры] Фильтр применен после альтернативных методов (изменение результатов с {results_before} до {current_results})")
                    return True

                return False

            except Exception as e:
                print(f"[Фильтры] Критическая ошибка при альтернативных методах клика: {str(e)}")
                return False

        except Exception as e:
            print(f"[Фильтры] Ошибка при применении фильтра {filter_name}: {str(e)}")
            driver.save_screenshot(f"filter_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            return False

    async def create_profile(self, profile_name, account_idx, proxy_config=None):
        """Создает профиль в Omnilogin с уникальным фингерпринтом"""
        try:
            resolutions = ["1920x1080", "1366x768", "1440x900", "1600x900", "1280x720"]
            timezones = ["America/New_York", "Europe/Moscow", "Asia/Tokyo", "Europe/London", "Australia/Sydney"]
            languages = ["en-US,en", "en-GB,en", "en-CA,en"]

            resolution = random.choice(resolutions)
            timezone = random.choice(timezones)
            language = random.choice(languages)

            fingerprint = {
                'timezone': False,
                'tzValue': timezone,
                'web_rtc': 'automatic',
                'public_ip': None,
                'screen_resolution': resolution,
                'fonts': 'SystemDefault',
                'canvas': 'Noise',
                'web_gl_type': 'Custom',
                'web_gl_image_type': 'Noise',
                'audio_context': 'Noise',
                'client_rects': 'Noise',
                'lang': language,
                'omni_browser_version': '32',
                'browser_version': 'random',
                'operating_system': 'window'
            }

            profile_id = self.browser_manager.create_profile(
                name=profile_name,
                proxy_config=proxy_config,
                fingerprint=fingerprint
            )

            print(f"[Профиль {profile_name}] Создан с ID: {profile_id}")
            return profile_id

        except Exception as e:
            raise Exception(f"Ошибка создания профиля: {str(e)}")

    async def start_profile(self, profile_id: str):
        """Запускаем профиль через BitBrowser и возвращаем driver"""
        try:
            chrome_path = r"PATH"
            chromedriver_path = r"PATH"

            ws_url = self.browser_manager.start_profile(
                profile_id,
                chrome_path=chrome_path,
                chromedriver_path=chromedriver_path
            )
            await asyncio.sleep(5)

            chrome_options = Options()
            chrome_options.debugger_address = ws_url.replace('ws://', '').split('/')[0]

            service = Service(executable_path=chromedriver_path)
            driver = webdriver.Chrome(
                service=service,
                options=chrome_options
            )
            return driver

        except Exception as e:
            raise Exception(f"Ошибка запуска профиля: {str(e)}")

    async def connect_to_existing_profile(self, profile_id: str):
        """Подключаемся к уже открытому профилю"""
        try:
            chrome_path = r"C:/Users/Vlad/Desktop/chrome-win64/chrome.exe"
            chromedriver_path = r"C:/Users/Vlad/Desktop/chromedriver-win64/chromedriver.exe"

            ws_url = self.browser_manager.get_profile_ws_url(profile_id)
            if not ws_url:
                raise Exception("Не удалось получить WebSocket URL для профиля")

            chrome_options = Options()
            chrome_options.debugger_address = ws_url.replace('ws://', '').split('/')[0]

            service = Service(executable_path=chromedriver_path)
            driver = webdriver.Chrome(
                service=service,
                options=chrome_options
            )
            return driver

        except Exception as e:
            raise Exception(f"Ошибка подключения к существующему профилю: {str(e)}")

    async def human_like_movement(self, driver):
        """Улучшенная имитация человеческого поведения с проверкой границ"""
        if not self.config.get('human_behavior', True):
            return

        try:
            window_size = driver.execute_script("""
                return {
                    width: window.innerWidth || document.documentElement.clientWidth,
                    height: window.innerHeight || document.documentElement.clientHeight
                };
            """)
            width = window_size['width']
            height = window_size['height']
            min_x = int(width * 0.2)
            max_x = int(width * 0.8)
            min_y = int(height * 0.2)
            max_y = int(height * 0.8)
            actions = ActionChains(driver)
            actions.move_by_offset(0, 0).perform()
            time.sleep(0.5)
            for _ in range(random.randint(3, 7)):
                if not self._running:
                    return
                x = random.randint(min_x, max_x)
                y = random.randint(min_y, max_y)

                try:
                    driver.execute_script(f"""
                        const elem = document.elementFromPoint({x}, {y});
                        if (elem) {{
                            const rect = elem.getBoundingClientRect();
                            window.dispatchEvent(new MouseEvent('mousemove', {{
                                clientX: rect.left + rect.width/2,
                                clientY: rect.top + rect.height/2
                            }}));
                        }}
                    """)
                    time.sleep(random.uniform(0.2, 1.0))
                except Exception as e:
                    print(f"[Движение] Ошибка перемещения: {str(e)}")
                    continue
            try:
                scroll_amount = random.randint(200, 800)
                scroll_direction = 1 if random.random() > 0.5 else -1
                steps = random.randint(5, 15)
                step_size = scroll_amount * scroll_direction / steps

                for _ in range(steps):
                    if not self._running:
                        return
                    driver.execute_script(f"window.scrollBy({{top: {step_size}, behavior: 'smooth'}})")
                    time.sleep(random.uniform(0.1, 0.3))
            except Exception as e:
                print(f"[Движение] Ошибка скроллинга: {str(e)}")

        except Exception as e:
            print(f"Ошибка имитации поведения: {str(e)}")

    async def handle_recovery_email_verification(self, driver, recovery_email):
        """Обработка верификации через резервную почту с улучшенным поиском элементов"""
        try:
            print("[Recovery Email] Ожидаем появления элементов восстановления...")
            timeout = 20 if self.config.get('human_behavior', False) else 15
            recovery_selectors = [
                '//div[contains(., "Confirm your recovery email") and not(contains(., "Get a verification code"))]',
                '//div[contains(., "Подтвердите ваш резервный email")]',
                '//div[@jsname="fmcmS" and contains(., "Confirm your recovery email")]',
                '//div[@jsname="EBHGs" and contains(., "Confirm your recovery email")]',
                'div[jsname="fmcmS"]',
                'div[jsname="EBHGs"]',
                'div[role="button"][aria-label*="Confirm your recovery email"]',
                'div[role="button"][aria-label*="Подтвердите ваш резервный email"]'
            ]
            recovery_element = None
            for selector in recovery_selectors:
                try:
                    if selector.startswith('//'):
                        elements = WebDriverWait(driver, 3).until(
                            EC.presence_of_all_elements_located((By.XPATH, selector)))
                        visible_elements = [el for el in elements if el.is_displayed()]
                        if visible_elements:
                            recovery_element = visible_elements[0]
                            print(f"[Recovery] Найден элемент по XPath: {selector}")
                            break
                    else:
                        elements = WebDriverWait(driver, 3).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                        for el in elements:
                            if el.is_displayed():
                                text = el.text
                                if ('Confirm your recovery email' in text or
                                        'Подтвердите ваш резервный email' in text):
                                    recovery_element = el
                                    print(f"[Recovery] Найден элемент по CSS: {selector}")
                                    break
                        if recovery_element:
                            break
                except:
                    continue

            if not recovery_element:
                print("[Recovery] Элемент не найден по стандартным селекторам, пробуем расширенный поиск")
                all_divs = driver.find_elements(By.TAG_NAME, 'div')
                for div in all_divs:
                    try:
                        if div.is_displayed():
                            text = div.text
                            if ('Confirm your recovery email' in text and
                                    'Get a verification code' not in text):
                                recovery_element = div
                                print("[Recovery] Найден элемент через расширенный поиск")
                                break
                    except:
                        continue

            if not recovery_element:
                raise Exception("Не удалось найти элемент подтверждения recovery email")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", recovery_element)
            time.sleep(1)
            try:
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable(recovery_element))
                recovery_element.click()
                print("[Recovery] Клик по элементу подтверждения выполнен")
            except:
                driver.execute_script("arguments[0].click();", recovery_element)
                print("[Recovery] Клик выполнен через JavaScript")
            print("[Recovery] Ожидаем появления поля для ввода email...")
            email_input = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="email"], input[jsname="YPqjbf"]'))
            )
            if self.config.get('human_behavior', False):
                email_input.clear()
                for char in recovery_email:
                    email_input.send_keys(char)
                    time.sleep(random.uniform(0.1, 0.3))
                print("[Recovery] Recovery email введен (человекообразный ввод)")
            else:
                email_input.clear()
                email_input.send_keys(recovery_email)
                print("[Recovery] Recovery email введен (быстрый ввод)")
            next_selectors = [
                'button:has-text("Next")',
                'button:has-text("Далее")',
                'button:has-text("Подтвердить")',
                'div[role="button"]:has-text("Next")',
                'div.VfPpkd-RLmnJb',
                'span.VfPpkd-vQzf8d'
            ]

            next_button = None
            for selector in next_selectors:
                try:
                    next_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    break
                except:
                    continue

            if next_button:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", next_button)
                    print("[Recovery] Кнопка подтверждения нажата через JS")
                except Exception as e:
                    print(f"[Recovery] Ошибка клика через JS: {str(e)}, пробуем обычный клик")
                    next_button.click()
                    print("[Recovery] Кнопка подтверждения нажата обычным кликом")

                time.sleep(3)
            else:
                print("[Recovery] Кнопка не найдена, пробуем Enter")
                email_input.send_keys(Keys.RETURN)
            try:
                WebDriverWait(driver, timeout).until(
                    lambda d: "myaccount.google.com" in d.current_url.lower() or
                              "signin/challenge" not in d.current_url.lower())
                print("[Recovery] Верификация recovery email завершена успешно")
                return True
            except TimeoutException:
                print("[Recovery] Не удалось подтвердить успешное завершение")
                return True

        except Exception as e:
            print(f"[Recovery] Критическая ошибка: {str(e)}")
            driver.save_screenshot(f"recovery_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            if "stop_script" in str(e):
                self.stop()
            return False

    async def auth_google(self, driver, email, password, recovery_email=None):
        """Полная авторизация в Google с обработкой всех сценариев"""
        try:
            driver.set_page_load_timeout(60)

            driver.get("https://accounts.google.com/")
            if not self._running:
                return False

            await self.human_like_movement(driver)
            time.sleep(random.uniform(2, 4))

            try:
                email_field = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="email"]')))

                email_field.clear()
                for char in email:
                    email_field.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
                time.sleep(random.uniform(1, 2))
            except Exception as e:
                print(f"[Авторизация] Ошибка ввода email: {str(e)}")
                driver.save_screenshot(f"email_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                return False

            try:
                next_buttons = WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, '//button[contains(., "Далее") or contains(., "Next")]')))

                next_button = None
                for btn in next_buttons:
                    if btn.is_displayed():
                        next_button = btn
                        break

                if next_button:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", next_button)
                    print("[Авторизация] Кнопка 'Далее' нажата")
                else:
                    raise Exception("Не найдена видимая кнопка 'Далее'")

                time.sleep(random.uniform(3, 5))
            except Exception as e:
                print(f"[Авторизация] Ошибка нажатия кнопки 'Далее': {str(e)}")
                driver.save_screenshot(f"next_button_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                return False

            try:
                password_field = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="password"]')))

                WebDriverWait(driver, 10).until(
                    lambda d: password_field.is_displayed() and password_field.is_enabled())

                password_field.clear()
                for char in password:
                    password_field.send_keys(char)
                    time.sleep(random.uniform(0.1, 0.3))
                time.sleep(random.uniform(1, 2))
            except Exception as e:
                print(f"[Авторизация] Ошибка ввода пароля: {str(e)}")
                driver.save_screenshot(f"password_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                return False

            try:
                next_buttons = WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, '//button[contains(., "Далее") or contains(., "Next")]')))

                next_button = None
                for btn in next_buttons:
                    if btn.is_displayed():
                        next_button = btn
                        break

                if next_button:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", next_button)
                    print("[Авторизация] Кнопка 'Далее' после пароля нажата")
                else:
                    raise Exception("Не найдена видимая кнопка 'Далее' после пароля")

                time.sleep(random.uniform(5, 8))

            except Exception as e:
                print(f"[Авторизация] Ошибка нажатия кнопки 'Далее' после пароля: {str(e)}")
                driver.save_screenshot(f"password_next_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                return False

            recovery_success = True
            if recovery_email:
                try:
                    recovery_element = WebDriverWait(driver, 15).until(
                        EC.any_of(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[jsname="fmcmS"]')),
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[jsname="EBHGs"]')),
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[jsname="YPqjbf"]'))
                        )
                    )
                    print("[Recovery] Обнаружена страница восстановления")
                    recovery_success = await self.handle_recovery_email_verification(driver, recovery_email)
                    if not recovery_success:
                        raise Exception("Ошибка обработки recovery email")
                except TimeoutException:
                    print("[Recovery] Страница восстановления не обнаружена")

            try:
                not_now_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, '//span[contains(., "Not now") or contains(., "Не сейчас")]')))
                print("[Passkey] Обнаружено предложение passkey, нажимаем 'Not now'")
                not_now_button.click()
                time.sleep(2)
            except TimeoutException:
                print("[Passkey] Страница с предложением passkey не обнаружена")

            print("[Авторизация] Успешно завершена")
            return True

        except Exception as e:
            print(f"[Авторизация] Критическая ошибка: {str(e)}")
            driver.save_screenshot(f"auth_error_{email.split('@')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            return False

    async def create_youtube_channel(self, driver):
        """Оптимизированное создание YouTube канала с прямым переходом на страницу создания"""
        try:
            print("[Канал] Начинаем оптимизированный процесс создания канала")

            driver.get("https://www.youtube.com")
            await asyncio.sleep(random.uniform(5, 10))

            driver.get("https://www.youtube.com/create_channel")
            await asyncio.sleep(random.uniform(5, 10))

            print("[Канал] Ожидаем загрузки формы создания...")
            await asyncio.sleep(random.uniform(8, 12))

            final_button_clicked = False
            print("[Канал] Поиск финальной кнопки создания канала...")

            buttons = driver.find_elements(By.TAG_NAME, 'button')
            for button in buttons:
                try:
                    text = button.text.lower()
                    if 'tạo kênh' in text or 'create channel' in text:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                        await asyncio.sleep(random.uniform(1, 2))

                        driver.execute_script("arguments[0].click();", button)
                        print("[Канал] Финальная кнопка найдена и нажата по тексту")
                        final_button_clicked = True
                        break
                except Exception as e:
                    print(f"[Канал] Ошибка при обработке кнопки: {str(e)}")
                    continue

            if not final_button_clicked:
                print("[Канал] Кнопка не найдена по тексту, пробуем альтернативные методы")

                if buttons:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", buttons[0])
                        await asyncio.sleep(1)
                        driver.execute_script("arguments[0].click();", buttons[0])
                        print("[Канал] Клик по первой найденной кнопке")
                        final_button_clicked = True
                    except Exception as e:
                        print(f"[Канал] Ошибка клика по первой кнопке: {str(e)}")

            if not final_button_clicked:
                raise Exception("Не удалось найти и нажать кнопку создания канала")

            print("[Канал] Ожидаем завершения создания канала...")
            await asyncio.sleep(random.uniform(15, 20))

            current_url = driver.current_url.lower()
            if "channel" in current_url or "youtube.com" in current_url:
                print(f"[Канал] Канал успешно создан (URL: {current_url})")
                return True

            try:
                channel_elements = driver.find_elements(By.CSS_SELECTOR,
                                                        'yt-formatted-string#channel-name, ytd-channel-name')
                if channel_elements:
                    print(f"[Канал] Канал создан: {channel_elements[0].text}")
                    return True
            except:
                pass

            raise Exception("Не удалось подтвердить создание канала")

        except Exception as e:
            print(f"[Канал] Ошибка при создании канала: {str(e)}")
            try:
                driver.save_screenshot(f"channel_creation_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            except:
                print("[Канал] Не удалось сохранить скриншот ошибки")
            return False

    async def watch_video(self, driver, video_url=None, video_title=None, video_tag=None, filter_strategy='none'):
        """Универсальная функция просмотра видео с улучшенной имитацией поведения"""
        try:
            if video_tag:
                print(f"[Видео] Начинаем обработку по тегу: {video_tag} с фильтром: {filter_strategy}")
                found = await self.search_video_by_tag(driver, video_tag, filter_strategy, video_title)
                if not found:
                    return False
            elif video_title:
                found = await self.search_video_by_title(driver, video_title, filter_strategy)
                if not found:
                    return False
            else:
                if self.config.get('enable_referral', True):
                    referer = random.choice(self.referers)
                    print(f"[Видео] Используем реферальный переход с: {referer}")
                    driver.execute_script(f"window.location.href = '{video_url}';")

                time.sleep(3)

            try:
                video_element = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'video')))
                print("[Видео] Видеоплеер успешно загружен")
            except Exception as e:
                print(f"[Видео] Видеоплеер не загрузился: {str(e)}")
                driver.save_screenshot(f"video_load_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                return False

            await self.human_like_movement(driver)
            try:
                driver.execute_script("""
                    const video = document.querySelector('video');
                    if (video) {
                        video.scrollIntoView({behavior: 'smooth', block: 'center'});
                        video.play().catch(e => console.log('Play error:', e));
                    }
                """)
                time.sleep(3)
            except Exception as play_error:
                print(f"[Видео] Ошибка воспроизведения: {str(play_error)}")
                driver.save_screenshot(f"play_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                return False
            if self.config.get('duration_mode', 'fixed') == 'random':
                min_duration = int(self.config.get('min_watch_duration', 30))
                max_duration = int(self.config.get('max_watch_duration', 180))
                actual_watch_time = random.randint(min_duration, max_duration)
                print(
                    f"[Видео] Случайная длительность просмотра: {actual_watch_time} секунд (диапазон {min_duration}-{max_duration})")
            else:
                watch_duration = str(self.config.get('watch_duration', '30'))
                try:
                    actual_watch_time = float(watch_duration)
                    print(f"[Видео] Фиксированная длительность просмотра: {actual_watch_time} секунд")
                except ValueError:
                    print("[Видео] Некорректное значение watch_duration, используем 30 секунд")
                    actual_watch_time = 30

            print(f"[Видео] Фактическое время просмотра: {actual_watch_time} секунд")
            actions = [
                self._adjust_volume,
                self._seek_video,
                self._random_mouse_movement,
                self._random_scroll,
                self._press_hotkey
            ]
            action_weights = [3, 4, 3, 5, 4]

            start_time = time.time()
            last_action_time = start_time

            while (time.time() - start_time) < actual_watch_time:
                if not self._running:
                    print("[Видео] Получен сигнал остановки")
                    return False

                current_time = time.time()
                elapsed = current_time - last_action_time
                if elapsed > random.uniform(5, 15):
                    action = random.choices(actions, weights=action_weights, k=1)[0]
                    try:
                        await action(driver)
                        last_action_time = current_time
                    except Exception as e:
                        print(f"[Видео] Ошибка при выполнении действия: {str(e)}")

            if self._running:
                if self.config['enable_likes']:
                    like_success = await self.like_video(driver)
                    print(f"[Видео] {'Лайк успешно поставлен' if like_success else 'Не удалось поставить лайк'}")

                if self.config['enable_subscriptions']:
                    subscribe_success = await self.subscribe_to_channel(driver)
                    print(f"[Видео] {'Подписка успешно оформлена' if subscribe_success else 'Не удалось подписаться'}")

            print("[Видео] Просмотр видео завершен успешно")
            return True

        except Exception as e:
            print(f"[Видео] Критическая ошибка: {str(e)}")
            driver.save_screenshot(f"video_critical_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            return False

    async def _adjust_volume(self, driver):
        """Случайная регулировка громкости"""
        actions = [
            {"type": "mute", "probability": 0.3},
            {"type": "unmute", "probability": 0.2},
            {"type": "set", "value": random.randint(10, 100), "probability": 0.5}
        ]

        action = random.choices(actions, weights=[a["probability"] for a in actions], k=1)[0]

        try:
            mute_button = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'button.ytp-mute-button')))

            if action["type"] == "mute":
                is_muted = mute_button.get_attribute('data-title-no-tooltip') == 'Unmute'
                if not is_muted:
                    mute_button.click()
                    print("[Действие] Выключен звук")
                    time.sleep(random.uniform(0.5, 1.5))

            elif action["type"] == "unmute":
                is_muted = mute_button.get_attribute('data-title-no-tooltip') == 'Unmute'
                if is_muted:
                    mute_button.click()
                    print("[Действие] Включен звук")
                    time.sleep(random.uniform(0.5, 1.5))

            elif action["type"] == "set":
                mute_button.click()
                time.sleep(0.5)

                volume_slider = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.ytp-volume-slider')))
                slider_location = volume_slider.location
                slider_size = volume_slider.size
                target_volume = action["value"]
                x_offset = slider_size['width'] * (target_volume / 100)
                actions = ActionChains(driver)
                actions.move_to_element_with_offset(volume_slider, x_offset, slider_size['height'] / 2)
                actions.click()
                actions.perform()

                print(f"[Действие] Установлена громкость {target_volume}%")
                time.sleep(random.uniform(1, 3))

        except Exception as e:
            print(f"[Действие] Ошибка регулировки громкости: {str(e)}")

    async def _toggle_fullscreen(self, driver):
        """Пустая реализация - полноэкранный режим отключен"""
        pass

    async def _seek_video(self, driver):
        """Надежная перемотка видео только вперед"""
        try:
            duration = driver.execute_script('''
                const video = document.querySelector('video');
                return video ? Math.round(video.duration) : null;
            ''')

            if not duration or duration <= 0:
                print("[Перемотка] Не удалось получить длительность видео")
                return

            current_time = driver.execute_script('''
                const video = document.querySelector('video');
                return video ? Math.round(video.currentTime) : 0;
            ''')
            seek_amount = random.randint(5, 15)
            new_time = min(duration, current_time + seek_amount)

            print(f"[Перемотка] Переход с {current_time} на {new_time} сек (вперед)")
            try:
                progress_bar = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.ytp-progress-bar')))
                bar_size = progress_bar.size['width']
                target_pos = (new_time / duration) * bar_size

                actions = ActionChains(driver)
                actions.move_to_element(progress_bar)
                actions.move_by_offset(target_pos - bar_size / 2, 0)
                actions.click()
                actions.perform()

            except:
                try:
                    presses = max(1, seek_amount // 5)
                    for _ in range(presses):
                        ActionChains(driver).send_keys(Keys.ARROW_RIGHT).perform()
                        time.sleep(0.3)

                except Exception as e:
                    print(f"[Перемотка] Ошибка: {str(e)}")

        except Exception as e:
            print(f"[Перемотка] Критическая ошибка: {str(e)}")

    async def _random_mouse_movement(self, driver):
        """Случайные движения мышью с проверкой границ"""
        try:
            window_size = driver.get_window_size()
            width = window_size['width']
            height = window_size['height']

            min_x = int(width * 0.3)
            max_x = int(width * 0.7)
            min_y = int(height * 0.3)
            max_y = int(height * 0.7)

            moves = random.randint(3, 7)

            actions = ActionChains(driver)
            actions.move_by_offset(width // 2, height // 2).perform()
            time.sleep(0.5)

            for _ in range(moves):
                if not self._running:
                    return

                x = random.randint(min_x, max_x)
                y = random.randint(min_y, max_y)

                actions = ActionChains(driver)
                actions.move_by_offset(x - width // 2, y - height // 2).perform()
                time.sleep(random.uniform(0.2, 1.0))

            print("[Действие] Случайные движения мышью")
        except Exception as e:
            print(f"[Действие] Ошибка движения мышью: {str(e)}")

    async def _random_scroll(self, driver):
        """Плавный скроллинг страницы"""
        try:
            scroll_amount = random.randint(200, 800)
            scroll_direction = 1 if random.random() > 0.5 else -1

            steps = random.randint(5, 15)
            step_size = scroll_amount * scroll_direction / steps

            for _ in range(steps):
                if not self._running:
                    return

                driver.execute_script(f"window.scrollBy(0, {step_size})")
                time.sleep(random.uniform(0.1, 0.3))

            print(f"[Действие] Плавный скролл {'вниз' if scroll_direction > 0 else 'вверх'}")
            time.sleep(random.uniform(1, 3))
        except Exception as e:
            print(f"[Действие] Ошибка скроллинга: {str(e)}")

    async def _press_hotkey(self, driver):
        """Нажатие горячих клавиш"""
        try:
            hotkeys = [
                {'key': Keys.SPACE, 'action': 'Пауза/продолжение'},
                {'key': Keys.ARROW_RIGHT, 'action': 'Вперед 5 сек'},
                {'key': 'm', 'action': 'Вкл/выкл звук'}
            ]

            hotkey = random.choice(hotkeys)
            actions = ActionChains(driver)

            if hotkey['key'] == Keys.SPACE:
                is_paused = driver.execute_script("""
                    const video = document.querySelector('video');
                    return video ? video.paused : false;
                """)
                actions.send_keys(Keys.SPACE)
                actions.perform()
                print(f"[Действие] {'Возобновлено' if is_paused else 'Пауза'} видео")
                if not is_paused:
                    resume_time = random.uniform(5, 10)
                    print(f"[Действие] Автоматическое возобновление через {resume_time:.1f} сек")
                    await asyncio.sleep(resume_time)
                    actions.send_keys(Keys.SPACE)
                    actions.perform()
                    print("[Действие] Видео возобновлено")
            else:
                if isinstance(hotkey['key'], str):
                    actions.send_keys(hotkey['key'])
                else:
                    actions.key_down(hotkey['key'])
                actions.perform()
                print(f"[Действие] Нажата клавиша: {hotkey['action']}")

            time.sleep(random.uniform(1, 3))
        except Exception as e:
            print(f"[Действие] Ошибка нажатия горячей клавиши: {str(e)}")

    async def get_video_duration(self, driver):
        try:
            duration = driver.execute_script('''
                const video = document.querySelector('video');
                return video ? Math.round(video.duration * 1000) : null;
            ''')

            if duration and duration > 0:
                return duration

            duration_str = driver.execute_script('''
                const elem = document.querySelector('.ytp-time-duration');
                return elem ? elem.textContent.trim() : null;
            ''')

            if duration_str:
                try:
                    parts = list(map(int, duration_str.split(':')))
                    if len(parts) == 3:
                        return parts[0] * 3600000 + parts[1] * 60000 + parts[2] * 1000
                    elif len(parts) == 2:
                        return parts[0] * 60000 + parts[1] * 1000
                    elif len(parts) == 1:
                        return parts[0] * 1000
                except:
                    pass

            return None
        except Exception as e:
            print(f"Ошибка определения длительности: {str(e)}")
            return None

    async def like_video(self, driver):
        """Надежная постановка лайка с новыми селекторами"""
        if not self.config.get('enable_likes', True):
            return False

        try:
            print("[Лайк] Поиск кнопки лайка...")

            like_selectors = [
                'button[aria-label^="like this video"]',
                'button[aria-label^="Нравится"]',
                'button[title^="I like this"]',
                'button[title^="Мне нравится"]',
                'button.yt-spec-button-shape-next[aria-label*="like"]',
                'ytd-toggle-button-renderer[aria-label^="Like"]',
                'div#top-level-buttons ytd-toggle-button-renderer:first-child',
                'ytd-toggle-button-renderer.style-scope.ytd-menu-renderer.force-icon-button.style-text',
                'button[class*="like-button"]',
                'div.yt-spec-button-shape-next__icon',
                'yt-icon[class*="like"]',
                'button[aria-label*="like"] yt-icon',
                'button[aria-label*="like"] div.yt-spec-button-shape-next__icon'
            ]

            like_button = None
            for selector in like_selectors:
                try:
                    like_button = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if like_button:
                        if 'icon' in selector.lower():
                            like_button = like_button.find_element(By.XPATH, './ancestor::button')
                        break
                except:
                    continue

            if not like_button:
                raise Exception("Не найдена кнопка лайка")
            try:
                aria_pressed = like_button.get_attribute('aria-pressed')
                if aria_pressed == 'true':
                    print("[Лайк] Лайк уже поставлен")
                    return True
            except:
                pass
            for attempt in range(3):
                try:
                    driver.execute_script("""
                        arguments[0].scrollIntoView({
                            block: 'center',
                            behavior: 'smooth'
                        });
                    """, like_button)
                    WebDriverWait(driver, 5).until(EC.visibility_of(like_button))
                    driver.execute_script("""
                        arguments[0].click();
                        arguments[0].focus();
                    """, like_button)
                    time.sleep(2)
                    try:
                        aria_pressed = like_button.get_attribute('aria-pressed')
                        if aria_pressed == 'true':
                            print(f"[Лайк] Успешно поставлен (попытка {attempt + 1})")
                            return True
                    except:
                        pass

                except Exception as e:
                    print(f"[Лайк] Ошибка попытки {attempt + 1}: {str(e)}")
                    time.sleep(1)
            try:
                like_button.click()
                time.sleep(2)
                return True
            except:
                return False

        except Exception as e:
            print(f"[Лайк] Критическая ошибка: {str(e)}")
            return False

    async def subscribe_to_channel(self, driver):
        """Улучшенный метод для подписки на канал"""
        if not self.config.get('enable_subscriptions', False):
            return False

        try:
            print("[Подписка] Поиск кнопки подписки...")

            subscribe_selectors = [
                'button[aria-label^="Subscribe"]',
                'button[aria-label^="Подписаться"]',
                'button[title^="Subscribe"]',
                'button[title^="Подписаться"]',
                'ytd-subscribe-button-renderer',
                'paper-button[aria-label^="Subscribe"]',
                'paper-button[aria-label^="Подписаться"]',
                'yt-formatted-string:contains("Subscribe")',
                'yt-formatted-string:contains("Подписаться")',
                'div#subscribe-button',
                'button.yt-spec-button-shape-next:contains("Subscribe")',
                'button.yt-spec-button-shape-next:contains("Подписаться")'
            ]

            subscribe_button = None
            for selector in subscribe_selectors:
                try:
                    subscribe_button = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    if subscribe_button:
                        break
                except:
                    continue

            if not subscribe_button:
                print("[Подписка] Кнопка не найдена по селекторам, пробуем альтернативные методы")
                try:
                    buttons = driver.find_elements(By.TAG_NAME, 'button')
                    for button in buttons:
                        try:
                            text = button.text.lower()
                            if 'subscribe' in text or 'подписаться' in text:
                                subscribe_button = button
                                break
                        except:
                            continue

                    if not subscribe_button:
                        raise Exception("Не найдена кнопка подписки")
                except Exception as e:
                    print(f"[Подписка] Ошибка поиска кнопки: {str(e)}")
                    return False

            subscribed = False
            try:
                text = subscribe_button.text.lower()
                if 'subscribed' in text or 'подписки' in text:
                    subscribed = True
            except:
                pass

            if subscribed:
                print("[Подписка] Уже подписан")
                return True
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                                      subscribe_button)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", subscribe_button)
                print("[Подписка] Подписка выполнена (через JavaScript)")
                time.sleep(3)
                try:
                    new_text = subscribe_button.text.lower()
                    if 'subscribed' in new_text or 'подписки' in new_text:
                        print("[Подписка] Успешно подтверждено")
                        return True
                    else:
                        subscribe_button.click()
                        print("[Подписка] Подписка выполнена (обычный клик)")
                        time.sleep(3)
                        return True
                except:
                    return True
            except Exception as click_error:
                print(f"[Подписка] Ошибка клика: {str(click_error)}")
                return False

        except Exception as e:
            print(f"[Подписка] Критическая ошибка: {str(e)}")
            driver.save_screenshot(f"subscribe_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            return False

    def log_result(self, account_idx, action, success, error=""):
        """Логирование результатов в CSV"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        email = self.accounts[account_idx][0]
        proxy = self.proxies[account_idx % len(self.proxies)].split(':')[0] if self.proxies else "no_proxy"

        log_data = {
            'timestamp': timestamp,
            'email': email,
            'proxy': proxy,
            'action': action,
            'status': 'Success' if success else 'Failed',
            'error': error
        }

        file_exists = Path('results.csv').exists()
        with open('results.csv', 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=log_data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(log_data)

    async def check_google_auth(self, driver):
        """Проверяет, выполнен ли вход в аккаунт Google"""
        try:
            driver.get("https://myaccount.google.com/")
            await asyncio.sleep(5)

            page_source = driver.page_source

            if "Create an account" in page_source:
                print("[Проверка авторизации] Найдена строка 'Create an account' - аккаунт не авторизован")
                return False
            else:
                print("[Проверка авторизации] Строка 'Create an account' не найдена - аккаунт авторизован")
                return True

        except Exception as e:
            print(f"[Проверка авторизации] Ошибка: {str(e)}")
            return False

    async def process_account(self, account_idx):
        """Обработка одного аккаунта с привязкой прокси и поддержкой корректной остановки"""
        if not self._running:
            print(f"[Аккаунт {account_idx}] Пропуск - скрипт остановлен")
            return False

        profile_id = None
        driver = None
        account_id = self.account_ids[account_idx] if self.account_ids and account_idx < len(self.account_ids) else None
        skip_auth = False
        browser_reused = False

        try:
            email, password, recovery_email = self.accounts[account_idx]
            user_agent = self.user_agents[account_idx % len(self.user_agents)]

            proxy = None
            proxy_config = {}

            if self.config['use_proxy'] and self.proxies:
                db = sqlite3.connect('youtube_soft.db')
                try:
                    if account_id:
                        cursor = db.execute('''
                            SELECT p.proxy FROM proxies p
                            JOIN account_proxies ap ON p.id = ap.proxy_id
                            WHERE ap.account_id = ?
                        ''', (account_id,))
                        result = cursor.fetchone()
                        if result:
                            proxy = result[0]
                            print(f"[Аккаунт {account_idx}] Используется привязанный прокси: {proxy.split('@')[0]}...")

                    if not proxy:
                        cursor = db.execute('''
                            SELECT p.proxy FROM proxies p
                            JOIN account_proxies ap ON p.id = ap.proxy_id
                        ''')
                        used_proxies = [row[0] for row in cursor.fetchall()]

                        for p in self.proxies:
                            if p not in used_proxies:
                                proxy = p
                                break

                        if not proxy:
                            cursor = db.execute('''
                                SELECT p.proxy, COUNT(ap.account_id) as usage_count 
                                FROM proxies p
                                LEFT JOIN account_proxies ap ON p.id = ap.proxy_id
                                GROUP BY p.proxy
                                ORDER BY usage_count
                            ''')
                            proxy = cursor.fetchone()[0]
                            print(
                                f"[Аккаунт {account_idx}] Все прокси заняты, выбран наименее используемый: {proxy.split('@')[0]}...")
                        else:
                            print(f"[Аккаунт {account_idx}] Назначен свободный прокси: {proxy.split('@')[0]}...")

                        if account_id and proxy:
                            cursor = db.execute('SELECT id FROM proxies WHERE proxy = ?', (proxy,))
                            proxy_row = cursor.fetchone()

                            if proxy_row:
                                proxy_id = proxy_row[0]
                                db.execute('DELETE FROM account_proxies WHERE account_id = ?', (account_id,))
                                db.execute('''
                                    INSERT INTO account_proxies (account_id, proxy_id)
                                    VALUES (?, ?)
                                ''', (account_id, proxy_id))
                                db.commit()
                                print(f"[Аккаунт {account_idx}] Привязка прокси сохранена в БД")
                except Exception as e:
                    print(f"[Аккаунт {account_idx}] Ошибка работы с БД: {str(e)}")
                finally:
                    db.close()

                if proxy and ':' in proxy:
                    parts = proxy.split(':')
                    proxy_config = {
                        "mode": "http",
                        "host": parts[0],
                        "port": int(parts[1]),
                        "username": parts[2] if len(parts) > 2 else "",
                        "password": parts[3] if len(parts) > 3 else ""
                    }

            print(f"\n[Аккаунт {account_idx}] Начало обработки")
            print(f"Email: {email}")
            print(f"User-Agent: {user_agent[:50]}...")
            print(f"Proxy: {proxy.split('@')[0] if proxy else 'no proxy'}...")

            if account_id:
                db = sqlite3.connect('youtube_soft.db')
                try:
                    cursor = db.execute('SELECT profile_id FROM account_profiles WHERE account_id = ?', (account_id,))
                    result = cursor.fetchone()
                    if result:
                        profile_id = result[0]
                        print(f"[Аккаунт {account_idx}] Найден существующий профиль ID: {profile_id}")

                        try:
                            driver = await self.start_profile(profile_id)
                            is_authenticated = await self.check_google_auth(driver)

                            if is_authenticated:
                                skip_auth = True
                                browser_reused = True
                                print(
                                    f"[Аккаунт {account_idx}] Используется существующий профиль ID: {profile_id} - аккаунт уже авторизован")
                            else:
                                print(
                                    f"[Аккаунт {account_idx}] Профиль найден, но аккаунт не авторизован - требуется вход")
                                skip_auth = False
                        except Exception as e:
                            if "Browser have already openned" in str(e):
                                print(
                                    f"[Аккаунт {account_idx}] Браузер уже открыт, пробуем подключиться к существующему")
                                try:
                                    driver = await self.connect_to_existing_profile(profile_id)
                                    is_authenticated = await self.check_google_auth(driver)

                                    if is_authenticated:
                                        skip_auth = True
                                        browser_reused = True
                                        print(
                                            f"[Аккаунт {account_idx}] Подключились к существующему браузеру - аккаунт авторизован")
                                    else:
                                        print(
                                            f"[Аккаунт {account_idx}] Подключились к существующему браузеру - требуется вход")
                                        skip_auth = False
                                except Exception as connect_error:
                                    print(
                                        f"[Аккаунт {account_idx}] Ошибка подключения к существующему браузеру: {str(connect_error)}")
                                    skip_auth = False
                            else:
                                print(f"[Аккаунт {account_idx}] Ошибка запуска профиля: {str(e)}")
                                skip_auth = False
                except Exception as e:
                    print(f"[Аккаунт {account_idx}] Ошибка проверки профиля в БД: {str(e)}")
                finally:
                    db.close()

            if not profile_id:
                try:
                    profile_name = f"yt_{email.split('@')[0]}_{account_idx}"
                    if not self._running:
                        print(f"[Аккаунт {account_idx}] Прерывание - скрипт остановлен")
                        return False

                    profile_id = await self.create_profile(profile_name, account_idx, proxy_config)
                    print(f"[Аккаунт {account_idx}] Создан профиль ID: {profile_id}")

                    if account_id:
                        db = sqlite3.connect('youtube_soft.db')
                        try:
                            db.execute('INSERT OR REPLACE INTO account_profiles (account_id, profile_id) VALUES (?, ?)',
                                       (account_id, profile_id))
                            db.commit()
                            print(f"[Аккаунт {account_idx}] Профиль сохранен в БД")
                        except Exception as e:
                            print(f"[Аккаунт {account_idx}] Ошибка сохранения профиля: {str(e)}")
                        finally:
                            db.close()

                except Exception as e:
                    print(f"[Аккаунт {account_idx}] Ошибка создания профиля: {str(e)}")
                    return False

                self.current_profile_id = profile_id

                if not self._running:
                    print(f"[Аккаунт {account_idx}] Прерывание после создания профиля")
                    return False

            if not skip_auth:
                if not driver:
                    driver = await self.start_profile(profile_id)
                    print(f"[Аккаунт {account_idx}] Профиль запущен")

                if not self._running:
                    print(f"[Аккаунт {account_idx}] Прерывание после запуска профиля")
                    if driver:
                        try:
                            driver.quit()
                            print(f"[Аккаунт {account_idx}] WebDriver закрыт при прерывании")
                        except:
                            pass
                    return False

                try:
                    auth_success = await self.auth_google(
                        driver,
                        email,
                        password,
                        recovery_email
                    )
                    self.log_result(account_idx, 'Auth', auth_success)
                except Exception as auth_error:
                    print(f"[Аккаунт {account_idx}] Auth error: {str(auth_error)}")
                    if driver:
                        try:
                            driver.save_screenshot(f"auth_error_{account_idx}.png")
                        except:
                            pass
                    raise
            else:
                auth_success = True
                print(f"[Аккаунт {account_idx}] Пропускаем авторизацию (профиль уже авторизован)")

            if auth_success and self._running:
                if self.config.get('create_channel', False):
                    channel_success = await self.create_youtube_channel(driver)
                    self.log_result(account_idx, 'Create Channel', channel_success)
                    result = channel_success
                else:
                    if self.config['enable_title_search']:
                        processed_items = 0
                        max_items_per_session = 3

                        current_account_id = account_id if account_id else account_idx + 1

                        while processed_items < max_items_per_session and self._running:
                            queue_item = self.get_next_queue_item_for_account(current_account_id)
                            if not queue_item:
                                print(f"[Аккаунт {account_idx}] Нет новых элементов для обработки, завершаем")
                                break

                            print(
                                f"[Аккаунт {account_idx}] Обрабатываем элемент очереди {processed_items + 1}: {queue_item['tag']} - {queue_item['title']}")

                            self.update_queue_item_status(queue_item['id'], 'processing')

                            self.record_queue_progress(queue_item['id'], current_account_id, 'processing')

                            try:
                                video_success = await self.watch_video(
                                    driver,
                                    video_tag=queue_item['tag'],
                                    video_title=queue_item['title'],
                                    filter_strategy=queue_item['filter_strategy']
                                )

                                if video_success:
                                    self.update_queue_item_status(queue_item['id'], 'completed')
                                    self.record_queue_progress(queue_item['id'], current_account_id, 'completed')
                                    self.log_result(account_idx, f'Queue Video: {queue_item["title"]}', True)
                                    print(f"[Аккаунт {account_idx}] Элемент {queue_item['id']} успешно обработан")
                                else:
                                    self.update_queue_item_status(queue_item['id'], 'failed')
                                    self.record_queue_progress(queue_item['id'], current_account_id, 'failed')
                                    self.log_result(account_idx, f'Queue Video: {queue_item["title"]}', False)
                                    print(f"[Аккаунт {account_idx}] Элемент {queue_item['id']} обработан с ошибкой")

                                processed_items += 1

                                if processed_items < max_items_per_session:
                                    await asyncio.sleep(random.uniform(2, 5))

                            except Exception as e:
                                print(f"[Аккаунт {account_idx}] Ошибка обработки элемента {queue_item['id']}: {str(e)}")
                                self.update_queue_item_status(queue_item['id'], 'failed')
                                self.record_queue_progress(queue_item['id'], current_account_id, 'failed')
                                self.log_result(account_idx, f'Queue Video: {queue_item["title"]}', False, str(e))
                                processed_items += 1

                        if processed_items > 0:
                            result = True
                            print(f"[Аккаунт {account_idx}] Обработано {processed_items} элементов очереди")
                        else:
                            print(f"[Аккаунт {account_idx}] Очередь пуста, используем стандартную логику")

                            if hasattr(self, 'video_tags') and self.video_tags:
                                if self.config.get('urls_strategy') == 'single':
                                    tags_to_search = [self.video_tags[0]]
                                elif self.config.get('urls_strategy') == 'round-robin':
                                    tags_to_search = [self.video_tags[account_idx % len(self.video_tags)]]
                                elif self.config.get('urls_strategy') == 'sequential':
                                    tags_to_search = self.video_tags.copy()
                                else:
                                    tags_to_search = [random.choice(self.video_tags)]

                                print(f"Tags to search: {tags_to_search}")
                                tag_results = []
                                for tag_idx, tag in enumerate(tags_to_search):
                                    if not self._running:
                                        break

                                    print(
                                        f"[Аккаунт {account_idx}] Поиск по тегу {tag_idx + 1}/{len(tags_to_search)}: {tag}")
                                    tag_success = await self.watch_video(driver, video_tag=tag)
                                    self.log_result(account_idx, f'Search by Tag {tag_idx + 1}', tag_success)
                                    tag_results.append(tag_success)

                                    if tag_idx < len(tags_to_search) - 1:
                                        time.sleep(random.uniform(2, 5))

                                result = all(tag_results) if tag_results else False
                            elif hasattr(self, 'video_titles') and self.video_titles:
                                if self.config.get('urls_strategy') == 'single':
                                    titles_to_search = [self.video_titles[0]]
                                elif self.config.get('urls_strategy') == 'round-robin':
                                    titles_to_search = [self.video_titles[account_idx % len(self.video_titles)]]
                                elif self.config.get('urls_strategy') == 'sequential':
                                    titles_to_search = self.video_titles.copy()
                                else:
                                    titles_to_search = [random.choice(self.video_titles)]

                                print(f"Titles to search: {titles_to_search}")
                                title_results = []
                                for title_idx, title in enumerate(titles_to_search):
                                    if not self._running:
                                        break

                                    print(
                                        f"[Аккаунт {account_idx}] Поиск видео {title_idx + 1}/{len(titles_to_search)}: {title}")
                                    title_success = await self.watch_video(driver, video_title=title)
                                    self.log_result(account_idx, f'Search Video {title_idx + 1}', title_success)
                                    title_results.append(title_success)

                                    if title_idx < len(titles_to_search) - 1:
                                        time.sleep(random.uniform(2, 5))

                                result = all(title_results) if title_results else False
                            else:
                                result = False
                    else:
                        if not self.video_urls:
                            print(f"[Аккаунт {account_idx}] Нет доступных URL видео, пропускаем")
                            result = False
                            return result

                        if self.config.get('urls_strategy') == 'single':
                            videos_to_watch = [self.video_urls[0]]
                        elif self.config.get('urls_strategy') == 'round-robin':
                            videos_to_watch = [self.video_urls[account_idx % len(self.video_urls)]]
                        elif self.config.get('urls_strategy') == 'sequential':
                            videos_to_watch = self.video_urls.copy()
                        else:
                            videos_to_watch = [random.choice(self.video_urls)]

                        print(f"Video URLs: {videos_to_watch}")
                        video_results = []
                        for video_idx, video_url in enumerate(videos_to_watch):
                            if not self._running:
                                break

                            print(
                                f"[Аккаунт {account_idx}] Видео {video_idx + 1}/{len(videos_to_watch)}: {video_url}")
                            video_success = await self.watch_video(driver, video_url=video_url)
                            self.log_result(account_idx, f'Watch Video {video_idx + 1}', video_success)
                            video_results.append(video_success)

                            if video_idx < len(videos_to_watch) - 1:
                                time.sleep(random.uniform(2, 5))

                        result = all(video_results) if video_results else False
            else:
                print(f"[Аккаунт {account_idx}] Пропуск действий (остановка или ошибка авторизации)")
                result = False

            return result

        except Exception as e:
            if str(e) == "stop_script":
                print(f"[Аккаунт {account_idx}] Критическая ошибка - остановка скрипта")
                self.stop()
                raise
            error_msg = str(e)
            print(f"[Аккаунт {account_idx}] Ошибка: {error_msg}")
            self.log_result(account_idx, 'Error', False, error_msg)
            return False
        finally:
            if driver:
                try:
                    driver.quit()
                    print(f"[Аккаунт {account_idx}] WebDriver закрыт")
                except Exception as e:
                    print(f"[Аккаунт {account_idx}] Ошибка при закрытии WebDriver: {str(e)}")
                    try:
                        driver.execute_script("window.close();")
                        print(f"[Аккаунт {account_idx}] WebDriver закрыт через JavaScript")
                    except:
                        pass

            if profile_id:
                try:
                    await self.browser_manager.close_profile(profile_id)
                    print(f"[Аккаунт {account_idx}] Профиль {profile_id} закрыт в Omnilogin")

                    await self.browser_manager.strict_kill_browser(profile_id)
                    print(f"[Аккаунт {account_idx}] Браузер профиля {profile_id} принудительно закрыт через taskkill")

                except Exception as e:
                    print(f"[Аккаунт {account_idx}] Ошибка при закрытии профиля: {str(e)}")
            else:
                print(f"[Аккаунт {account_idx}] Нет профиля для закрытия")

    async def run(self):
        """Основной цикл обработки аккаунтов с батчами"""
        try:
            print(f"Запуск с {self.threads} потоками")
        except:
            pass

        try:
            self.load_video_queue()
            try:
                print(f"Загружено {len(self.video_queue)} элементов в очередь")
            except:
                pass

            await self.process_accounts_in_batches()
        except Exception as e:
            if str(e) == "stop_script":
                try:
                    print("Обнаружена критическая ошибка - остановка скрипта")
                except:
                    pass
                self.stop()
            else:
                try:
                    print(f"Критическая ошибка в основном цикле: {str(e)}")
                except:
                    pass
        finally:
            try:
                if hasattr(self, 'browser_manager') and self.browser_manager:
                    try:
                        print("Завершение работы скрипта")
                    except:
                        pass
                    await self.close_all_profiles()
            except Exception as e:
                try:
                    print(f"Ошибка при завершении: {str(e)}")
                except:
                    pass

    async def close_all_profiles(self):
        """Закрывает все открытые профили при завершении работы"""
        try:
            try:
                print("[Завершение] Закрываем все открытые профили...")
            except:
                pass

            db = sqlite3.connect('youtube_soft.db')
            try:
                cursor = db.execute('SELECT profile_id FROM account_profiles')
                profiles = cursor.fetchall()

                if not profiles:
                    try:
                        print("[Завершение] Нет профилей для закрытия")
                    except:
                        pass
                    return

                closed_count = 0
                for profile_row in profiles:
                    profile_id = str(profile_row[0])
                    try:
                        try:
                            print(f"[Завершение] Пытаемся закрыть профиль: '{profile_id}'")
                        except:
                            pass

                        is_running = await self.browser_manager.check_profile_exists(profile_id)
                        if is_running:
                            await self.browser_manager.close_profile(profile_id)
                            closed_count += 1
                            try:
                                print(f"[Завершение] Профиль {profile_id} закрыт")
                            except:
                                pass
                        else:
                            try:
                                print(f"[Завершение] Профиль {profile_id} не запущен, пропускаем")
                            except:
                                pass

                    except Exception as e:
                        try:
                            print(f"[Завершение] Ошибка закрытия профиля {profile_id}: {str(e)}")
                        except:
                            pass

                try:
                    print(f"[Завершение] Закрыто {closed_count} профилей из {len(profiles)}")

                    print("[Завершение] Выполняем строгое закрытие браузеров через taskkill...")
                    await self.browser_manager.strict_kill_browser()

                except:
                    pass

            finally:
                db.close()

        except Exception as e:
            try:
                print(f"[Завершение] Ошибка при закрытии профилей: {str(e)}")
            except:
                pass

    def stop(self):
        self._running = False
        self._stop_event.set()
        try:
            print("Получен сигнал остановки")
        except:
            pass

        try:
            loop = asyncio.get_event_loop()
            if loop and loop.is_running():
                asyncio.create_task(self.close_all_profiles())
            else:
                asyncio.run(self.close_all_profiles())
        except Exception as e:
            try:
                print(f"Ошибка при закрытии профилей при остановке: {str(e)}")
            except:
                pass

    async def clean_invalid_profiles(self):
        db = sqlite3.connect('youtube_soft.db')
        try:
            cursor = db.execute('SELECT account_id, profile_id FROM account_profiles')
            profiles = cursor.fetchall()

            for account_id, profile_id in profiles:
                if not await self.browser_manager.check_profile_exists(str(profile_id)):
                    db.execute('DELETE FROM account_profiles WHERE account_id = ?', (account_id,))
                    print(f"Удалена связь для несуществующего профиля {profile_id}")

            db.commit()
        finally:
            db.close()

    def generate_report(self):
        """Генерация итогового отчета с улучшенной обработкой данных"""
        try:
            report_data = {
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_accounts': len(self.accounts),
                'active_accounts': 0,
                'total_actions': 0,
                'success_actions': 0,
                'failed_actions': 0,
                'channel_creations': 0,
                'searched_videos': 0,
                'found_videos': 0
            }

            if Path('results.csv').exists():
                with open('results.csv', 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        report_data['total_actions'] += 1

                        if row['status'] == 'Success':
                            report_data['success_actions'] += 1
                            if 'Auth' in row['action']:
                                report_data['active_accounts'] += 1
                            elif 'Create Channel' in row['action']:
                                report_data['channel_creations'] += 1
                            elif 'Search Video' in row['action']:
                                report_data['searched_videos'] += 1
                                report_data['found_videos'] += 1
                        else:
                            report_data['failed_actions'] += 1
                            if 'Search Video' in row['action']:
                                report_data['searched_videos'] += 1

            with open('report.json', 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2)

            print("\nОтчет:")
            print(f"Аккаунтов: {report_data['total_accounts']} (рабочих: {report_data['active_accounts']})")
            print(f"Действий: {report_data['total_actions']}")
            print(f"Успешных: {report_data['success_actions']}")
            print(f"Неудачных: {report_data['failed_actions']}")
            print(f"Создано каналов: {report_data['channel_creations']}")
            if report_data['searched_videos'] > 0:
                print(f"Поиск видео: {report_data['found_videos']}/{report_data['searched_videos']} успешно")

            return report_data

        except Exception as e:
            print(f"Ошибка генерации отчета: {str(e)}")
            return None


if __name__ == "__main__":
    try:
        auth = GoLoginAuth()
        asyncio.run(auth.run())
    except Exception as e:
        print(f"Критическая ошибка: {str(e)}")