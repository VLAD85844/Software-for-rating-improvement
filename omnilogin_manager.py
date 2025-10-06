import asyncio
import requests
import json
import time
import subprocess
import platform
import psutil
from typing import Optional, List, Dict, Union


class OmniloginManager:
    def __init__(self, base_url: str = "http://localhost:35353"):
        self.base_url = base_url
        self.headers = {
            'Content-Type': 'application/json'
        }

    def create_profile(self, name: str, proxy_config: Optional[Dict] = None,
                       fingerprint: Optional[Dict] = None) -> str:
        """Создает профиль в Omnilogin с указанными параметрами"""
        try:
            profile_data = {
                "name": name,
                "fingerprints": fingerprint or self._get_default_fingerprint()
            }

            response = requests.post(
                f"{self.base_url}/profiles",
                data=json.dumps(profile_data),
                headers=self.headers
            )

            if response.status_code != 200:
                raise Exception(f"Ошибка создания профиля: {response.text}")

            profile_info = response.json()
            profile_id = profile_info.get('id')

            if not profile_id:
                raise Exception("Не получен ID профиля из ответа")

            print(f"[Omnilogin] Профиль создан с ID: {profile_id} (тип: {type(profile_id)})")
            print(f"[Omnilogin] Полный ответ API: {profile_info}")

            if proxy_config:
                try:
                    success = self.bind_embedded_proxy(str(profile_id), proxy_config)
                    if success:
                        print(f"[Omnilogin] Встроенный прокси привязан к профилю {profile_id}")
                    else:
                        print(f"[Omnilogin] Не удалось привязать прокси к профилю {profile_id}")
                except Exception as proxy_error:
                    print(f"[Omnilogin] Ошибка привязки прокси: {str(proxy_error)}")

            return str(profile_id)

        except Exception as e:
            raise Exception(f"Ошибка создания профиля: {str(e)}")

    def _get_default_fingerprint(self) -> Dict:
        """Возвращает стандартный фингерпринт для Omnilogin"""
        return {
            "timezone": False,
            "tzValue": "Europe/Moscow",
            "web_rtc": "automatic",
            "public_ip": None,
            "screen_resolution": "1920x1080",
            "fonts": "SystemDefault",
            "canvas": "Noise",
            "web_gl_type": "Custom",
            "web_gl_image_type": "Noise",
            "audio_context": "Noise",
            "client_rects": "Noise",
            "lang": "en-US,en",
            "omni_browser_version": "32",
            "browser_version": "random",
            "operating_system": "window"
        }

    def start_profile(self, profile_id: str, chrome_path: str = None, chromedriver_path: str = None) -> str:
        """Запускает профиль и возвращает WebSocket URL для подключения"""
        try:
            params = {
                'profile_id': profile_id
            }

            if chrome_path:
                params['addition_args'] = [f'--chrome-path={chrome_path}']

            if chromedriver_path:
                params['addition_args'] = params.get('addition_args', []) + [f'--chromedriver-path={chromedriver_path}']

            response = requests.get(
                f"{self.base_url}/open",
                params=params,
                headers=self.headers
            )

            if response.status_code != 200:
                raise Exception(f"Ошибка запуска профиля: {response.text}")

            result = response.json()

            if not result.get('status'):
                raise Exception("Профиль не удалось запустить")

            ws_url = result.get('web_socket_debugger_url')
            if not ws_url:
                raise Exception("Не получен WebSocket URL из ответа")

            if not ws_url.startswith('ws://'):
                ws_url = 'ws://' + ws_url.lstrip('http://').lstrip('https://')

            print(f"[Omnilogin] Профиль {profile_id} запущен, WebSocket: {ws_url}")
            return ws_url

        except Exception as e:
            raise Exception(f"Ошибка запуска профиля: {str(e)}")

    async def close_profile(self, profile_id: str) -> None:
        """Закрывает конкретный профиль браузера через принудительное завершение процесса"""
        try:
            print(f"[Omnilogin] Пытаемся закрыть профиль {profile_id}")
            check_response = requests.get(
                f"{self.base_url}/profiles/{profile_id}",
                headers=self.headers,
                timeout=10
            )

            if check_response.status_code != 200:
                print(f"[Omnilogin] Профиль {profile_id} не найден или не запущен (HTTP {check_response.status_code})")
                return

            profile_info = check_response.json()
            if not profile_info.get('web_socket_debugger_url'):
                print(f"[Omnilogin] Профиль {profile_id} не запущен (нет WebSocket URL)")
                return
            print(f"[Omnilogin] Профиль {profile_id} найден и запущен, закрываем через kill...")
            await self._kill_browser_by_profile(profile_id)

        except Exception as e:
            print(f"[Omnilogin] Ошибка при закрытии профиля {profile_id}: {str(e)}")

    async def _kill_browser_by_profile(self, profile_id: str) -> None:
        """Закрывает браузер конкретного профиля через принудительное завершение процесса"""
        try:
            print(f"[Omnilogin] Закрываем браузер профиля {profile_id} через kill...")

            system = platform.system().lower()

            if system == "windows":
                try:
                    profile_response = requests.get(
                        f"{self.base_url}/profiles/{profile_id}",
                        headers=self.headers,
                        timeout=10
                    )

                    if profile_response.status_code == 200:
                        profile_info = profile_response.json()
                        ws_url = profile_info.get('web_socket_debugger_url', '')

                        if ws_url:
                            try:
                                port = ws_url.split(':')[-1].split('/')[0]
                                print(f"[Omnilogin] Найден порт профиля: {port}")
                                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                                    try:
                                        if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                                            cmdline = proc.info['cmdline']
                                            if cmdline and any(f':{port}' in arg for arg in cmdline):
                                                print(
                                                    f"[Omnilogin] Найден процесс Chrome с портом {port}: PID {proc.info['pid']}")
                                                proc.terminate()
                                                print(f"[Omnilogin] Процесс {proc.info['pid']} завершен")
                                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                                        continue
                                subprocess.run(["taskkill", "/f", "/im", "chrome.exe"],
                                               capture_output=True, check=False)
                                print(f"[Omnilogin] Все процессы Chrome закрыты")

                            except Exception as port_error:
                                print(f"[Omnilogin] Ошибка извлечения порта: {str(port_error)}")
                                subprocess.run(["taskkill", "/f", "/im", "chrome.exe"],
                                               capture_output=True, check=False)
                                print(f"[Omnilogin] Все процессы Chrome закрыты (fallback)")
                    else:
                        subprocess.run(["taskkill", "/f", "/im", "chrome.exe"],
                                       capture_output=True, check=False)
                        print(f"[Omnilogin] Все процессы Chrome закрыты (fallback)")

                except Exception as e:
                    print(f"[Omnilogin] Ошибка закрытия Chrome на Windows: {str(e)}")

            elif system == "linux":
                try:
                    subprocess.run(["pkill", "-f", "chrome.*--remote-debugging-port"],
                                   capture_output=True, check=False)
                    subprocess.run(["pkill", "-f", "chrome.*--user-data-dir"],
                                   capture_output=True, check=False)
                    print(f"[Omnilogin] Процессы Chrome с антидетект флагами закрыты на Linux")
                except Exception as e:
                    print(f"[Omnilogin] Ошибка закрытия Chrome на Linux: {str(e)}")

            elif system == "darwin":
                try:
                    subprocess.run(["pkill", "-f", "Google Chrome.*--remote-debugging-port"],
                                   capture_output=True, check=False)
                    subprocess.run(["pkill", "-f", "Google Chrome.*--user-data-dir"],
                                   capture_output=True, check=False)
                    print(f"[Omnilogin] Процессы Chrome с антидетект флагами закрыты на macOS")
                except Exception as e:
                    print(f"[Omnilogin] Ошибка закрытия Chrome на macOS: {str(e)}")

        except Exception as e:
            print(f"[Omnilogin] Ошибка принудительного закрытия браузера профиля {profile_id}: {str(e)}")

    async def force_close_all_browsers(self) -> None:
        """Принудительно закрывает все браузеры антидетекта через системные команды"""
        try:
            print("[Omnilogin] Принудительно закрываем все браузеры антидетекта...")

            system = platform.system().lower()

            if system == "windows":
                try:
                    antidetect_processes = []
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                                cmdline = proc.info['cmdline']
                                if cmdline and any('--remote-debugging-port' in arg for arg in cmdline):
                                    antidetect_processes.append(proc.info['pid'])
                                    print(f"[Omnilogin] Найден процесс антидетекта: PID {proc.info['pid']}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    for pid in antidetect_processes:
                        try:
                            subprocess.run(["taskkill", "/f", "/pid", str(pid)],
                                           capture_output=True, check=False)
                            print(f"[Omnilogin] Процесс {pid} закрыт")
                        except Exception as e:
                            print(f"[Omnilogin] Ошибка закрытия процесса {pid}: {str(e)}")

                    if not antidetect_processes:
                        print("[Omnilogin] Процессы антидетекта не найдены")

                except Exception as e:
                    print(f"[Omnilogin] Ошибка закрытия Chrome на Windows: {str(e)}")

            elif system == "linux":
                try:
                    subprocess.run(["pkill", "-f", "chrome.*--remote-debugging-port"],
                                   capture_output=True, check=False)
                    subprocess.run(["pkill", "-f", "chrome.*--user-data-dir"],
                                   capture_output=True, check=False)
                    print("[Omnilogin] Процессы Chrome с антидетект флагами закрыты на Linux")
                except Exception as e:
                    print(f"[Omnilogin] Ошибка закрытия Chrome на Linux: {str(e)}")

            elif system == "darwin":
                try:
                    subprocess.run(["pkill", "-f", "Google Chrome.*--remote-debugging-port"],
                                   capture_output=True, check=False)
                    subprocess.run(["pkill", "-f", "Google Chrome.*--user-data-dir"],
                                   capture_output=True, check=False)
                    print("[Omnilogin] Процессы Chrome с антидетект флагами закрыты на macOS")
                except Exception as e:
                    print(f"[Omnilogin] Ошибка закрытия Chrome на macOS: {str(e)}")

        except Exception as e:
            print(f"[Omnilogin] Ошибка принудительного закрытия браузеров: {str(e)}")

    async def strict_kill_browser(self, profile_id: str = None) -> None:
        """Строгое закрытие браузера через taskkill (только для Windows)"""
        try:
            system = platform.system().lower()

            if system == "windows":
                print("[Omnilogin] Выполняем строгое закрытие браузера через taskkill...")

                processes_to_kill = [
                    "chrome.exe",
                    "chromedriver.exe",
                    "bitbrowser.exe",
                    "bitbrowser-core.exe"
                ]

                killed_processes = []

                for process_name in processes_to_kill:
                    try:
                        result = subprocess.run(
                            ["taskkill", "/f", "/im", process_name],
                            capture_output=True,
                            text=True,
                            check=False
                        )

                        if result.returncode == 0:
                            print(f"[Omnilogin] Успешно закрыты процессы {process_name}")
                            killed_processes.append(process_name)
                        elif "не найдены процессы" in result.stderr.lower() or "no tasks" in result.stderr.lower() or "не удается найти процесс" in result.stderr.lower():
                            pass
                        else:
                            print(f"[Omnilogin] Ошибка закрытия {process_name}: {result.stderr}")

                    except Exception as e:
                        print(f"[Omnilogin] Исключение при закрытии {process_name}: {str(e)}")
                if profile_id:
                    try:
                        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                            try:
                                if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                                    cmdline = proc.info['cmdline']
                                    if cmdline and any('--remote-debugging-port' in arg for arg in cmdline):
                                        if any(profile_id in arg for arg in cmdline):
                                            print(
                                                f"[Omnilogin] Найден процесс профиля {profile_id}: PID {proc.info['pid']}")
                                            subprocess.run(["taskkill", "/f", "/pid", str(proc.info['pid'])],
                                                           capture_output=True, check=False)
                                            print(f"[Omnilogin] Процесс профиля {profile_id} закрыт")
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                continue
                    except Exception as e:
                        print(f"[Omnilogin] Ошибка поиска процессов профиля: {str(e)}")

                print(f"[Omnilogin] Строгое закрытие завершено. Закрыто процессов: {len(killed_processes)}")

            else:
                print(f"[Omnilogin] Строгое закрытие через taskkill доступно только на Windows. Текущая ОС: {system}")
                await self.force_close_all_browsers()

        except Exception as e:
            print(f"[Omnilogin] Ошибка строгого закрытия браузера: {str(e)}")

    def delete_profile(self, profile_id: str) -> None:
        """Удаляет профиль"""
        try:
            response = requests.delete(
                f"{self.base_url}/profiles/{profile_id}",
                headers=self.headers
            )

            if response.status_code != 200:
                raise Exception(f"Ошибка удаления профиля: {response.text}")

            print(f"[Omnilogin] Профиль {profile_id} удален")

        except Exception as e:
            raise Exception(f"Ошибка удаления профиля: {str(e)}")

    async def check_profile_exists(self, profile_id: str) -> bool:
        """Проверяет существование профиля"""
        try:
            response = requests.get(
                f"{self.base_url}/profiles/{profile_id}",
                headers=self.headers,
                timeout=10
            )

            return response.status_code == 200

        except Exception as e:
            print(f"[Omnilogin] Ошибка проверки профиля {profile_id}: {str(e)}")
            return False

    def get_profile_ws_url(self, profile_id: str) -> Optional[str]:
        """Получает WebSocket URL для уже открытого профиля"""
        try:
            response = requests.get(
                f"{self.base_url}/profiles/{profile_id}",
                headers=self.headers
            )

            if response.status_code != 200:
                return None

            profile_info = response.json()
            ws_url = profile_info.get('web_socket_debugger_url')

            if ws_url:
                if not ws_url.startswith('ws://'):
                    ws_url = 'ws://' + ws_url.lstrip('http://').lstrip('https://')
                return ws_url

            return None

        except Exception as e:
            print(f"[Omnilogin] Ошибка получения WebSocket URL для профиля {profile_id}: {str(e)}")
            return None

    async def kill_browser_processes(self) -> None:
        """Закрывает все процессы браузера антидетекта"""
        try:
            print(f"[Omnilogin] Закрываем все процессы браузера антидетекта...")

            await self.force_close_all_browsers()

        except Exception as e:
            print(f"[Omnilogin] Ошибка при закрытии процессов браузера: {str(e)}")

    def get_proxy_list(self) -> List[Dict]:
        """Получает список прокси из Omnilogin"""
        try:
            response = requests.get(
                f"{self.base_url}/proxies",
                headers=self.headers
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('docs', [])
            else:
                print(f"[Omnilogin] Ошибка получения списка прокси: {response.text}")
                return []

        except Exception as e:
            print(f"[Omnilogin] Ошибка при получении списка прокси: {str(e)}")
            return []

    def get_profiles_list(self) -> List[Dict]:
        """Получает список всех профилей из Omnilogin"""
        try:
            response = requests.get(
                f"{self.base_url}/profiles",
                headers=self.headers
            )

            if response.status_code == 200:
                result = response.json()
                profiles = result.get('docs', []) if isinstance(result, dict) else result
                print(f"[Omnilogin] Получено {len(profiles)} профилей из API")
                for profile in profiles:
                    if isinstance(profile, dict):
                        print(f"[Omnilogin] Профиль: {profile}")
                return profiles
            else:
                print(f"[Omnilogin] Ошибка получения списка профилей: {response.text}")
                return []

        except Exception as e:
            print(f"[Omnilogin] Ошибка при получении списка профилей: {str(e)}")
            return []

    def create_proxy(self, proxy_config: Dict) -> Optional[int]:
        """Создает прокси в Omnilogin"""
        try:
            proxy_data = {
                "name": proxy_config.get('name', f"proxy_{int(time.time())}"),
                "proxy_type": proxy_config.get('mode', 'HTTPS').upper(),
                "host": proxy_config.get('host', ''),
                "port": proxy_config.get('port', 0),
                "user_name": proxy_config.get('username', ''),
                "password": proxy_config.get('password', '')
            }

            print(f"[Omnilogin] Создаем прокси: {proxy_data['name']}")

            response = requests.post(
                f"{self.base_url}/proxies",
                data=json.dumps(proxy_data),
                headers=self.headers
            )

            if response.status_code == 200:
                result = response.json()
                print(f"[Omnilogin] Ответ создания прокси: {result}")

                if 'docs' in result and result['docs']:
                    proxy_id = result['docs'][0].get('id')
                    if proxy_id:
                        print(f"[Omnilogin] Прокси создан с ID: {proxy_id}")
                        return proxy_id
                elif 'id' in result:
                    proxy_id = result['id']
                    print(f"[Omnilogin] Прокси создан с ID: {proxy_id}")
                    return proxy_id
                else:
                    print(f"[Omnilogin] ID прокси не найден в ответе: {result}")
                    return None
            else:
                print(f"[Omnilogin] Ошибка создания прокси: {response.text}")
                return None

        except Exception as e:
            print(f"[Omnilogin] Ошибка при создании прокси: {str(e)}")
            return None

    def update_profile_fingerprint(self, profile_id: str, fingerprint: Dict) -> bool:
        """Обновляет фингерпринт профиля"""
        try:
            response = requests.put(
                f"{self.base_url}/profiles/{profile_id}/fingerprint",
                data=json.dumps(fingerprint),
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"[Omnilogin] Фингерпринт профиля {profile_id} обновлен")
                return True
            else:
                print(f"[Omnilogin] Ошибка обновления фингерпринта: {response.text}")
                return False

        except Exception as e:
            print(f"[Omnilogin] Ошибка при обновлении фингерпринта: {str(e)}")
            return False

    def bind_embedded_proxy(self, profile_id: str, proxy_config: Dict) -> bool:
        """Привязывает встроенный прокси к профилю через /profiles/embedded-proxy"""
        try:
            embedded_proxy_data = {
                "proxy": {
                    "name": proxy_config.get('name', f"embedded_proxy_{int(time.time())}"),
                    "proxy_type": proxy_config.get('mode', 'HTTPS').upper(),
                    "host": proxy_config.get('host', ''),
                    "port": proxy_config.get('port', 0),
                    "user_name": proxy_config.get('username', ''),
                    "password": proxy_config.get('password', '')
                },
                "profileIds": [profile_id]
            }

            print(f"[Omnilogin] Привязываем встроенный прокси к профилю {profile_id}")

            response = requests.put(
                f"{self.base_url}/profiles/embedded-proxy",
                data=json.dumps(embedded_proxy_data),
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"[Omnilogin] Встроенный прокси успешно привязан к профилю {profile_id}")
                return True
            else:
                print(f"[Omnilogin] Ошибка привязки встроенного прокси: {response.text}")
                return False

        except Exception as e:
            print(f"[Omnilogin] Ошибка при привязке встроенного прокси: {str(e)}")
            return False

    def update_profile_proxy(self, profile_id: str, proxy_id: int) -> bool:
        """Обновляет прокси профиля (устаревший метод)"""
        try:
            methods = [
                self._bind_proxy_method1,
                self._bind_proxy_method2,
                self._bind_proxy_method3
            ]

            for method in methods:
                try:
                    if method(profile_id, proxy_id):
                        return True
                except Exception as e:
                    print(f"[Omnilogin] Метод {method.__name__} не сработал: {str(e)}")
                    continue

            print(f"[Omnilogin] Все методы привязки прокси не сработали")
            return False

        except Exception as e:
            print(f"[Omnilogin] Ошибка при привязке прокси: {str(e)}")
            return False

    def _bind_proxy_method1(self, profile_id: str, proxy_id: int) -> bool:
        """Метод 1: Обновление профиля с proxy_id"""
        try:
            profile_update_data = {
                "proxy_id": proxy_id
            }

            response = requests.put(
                f"{self.base_url}/profiles/{profile_id}",
                data=json.dumps(profile_update_data),
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"[Omnilogin] Метод 1: Прокси {proxy_id} привязан к профилю {profile_id}")
                return True
            return False

        except Exception as e:
            print(f"[Omnilogin] Ошибка метода 1: {str(e)}")
            return False

    def _bind_proxy_method2(self, profile_id: str, proxy_id: int) -> bool:
        """Метод 2: Использование специального API для привязки прокси"""
        try:
            proxy_data = {
                "profile_ids": [profile_id],
                "proxy_id": proxy_id
            }

            response = requests.put(
                f"{self.base_url}/profiles/proxy",
                data=json.dumps(proxy_data),
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"[Omnilogin] Метод 2: Прокси {proxy_id} привязан к профилю {profile_id}")
                return True
            return False

        except Exception as e:
            print(f"[Omnilogin] Ошибка метода 2: {str(e)}")
            return False

    def _bind_proxy_method3(self, profile_id: str, proxy_id: int) -> bool:
        """Метод 3: Обновление прокси с указанием профиля"""
        try:
            proxy_update_data = {
                "profile_id": profile_id
            }

            response = requests.put(
                f"{self.base_url}/proxies/{proxy_id}",
                data=json.dumps(proxy_update_data),
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"[Omnilogin] Метод 3: Прокси {proxy_id} привязан к профилю {profile_id}")
                return True
            return False

        except Exception as e:
            print(f"[Omnilogin] Ошибка метода 3: {str(e)}")
            return False


