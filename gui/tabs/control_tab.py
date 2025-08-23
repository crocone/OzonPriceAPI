#!/usr/bin/env python3
"""
Вкладка управления API
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import subprocess
import sys
import os
import re
import time
import socket
from typing import Optional, Callable


class ControlTab:
    def __init__(self, parent_frame, log_callback: Callable[[str, str], None]):
        self.parent_frame = parent_frame
        self.log_callback = log_callback
        
        # Переменные состояния
        self.api_process = None
        self.api_thread = None  # Для встроенного режима
        self.is_running = False
        self.ngrok_url = None
        
        # Создание интерфейса
        self.create_widgets()
    

    
    def create_widgets(self):
        """Создание виджетов вкладки управления"""
        # Заголовок
        title_label = tk.Label(
            self.parent_frame, 
            text="Ozon Parser API с ngrok", 
            font=('Arial', 16, 'bold'),
            bg='#f0f0f0'
        )
        title_label.pack(pady=20)
        

        
        # Статус
        self.status_frame = tk.Frame(self.parent_frame, bg='#f0f0f0')
        self.status_frame.pack(pady=10)
        
        tk.Label(self.status_frame, text="Статус:", font=('Arial', 12), bg='#f0f0f0').pack(side='left')
        self.status_label = tk.Label(
            self.status_frame, 
            text="Остановлен", 
            font=('Arial', 12, 'bold'),
            fg='red',
            bg='#f0f0f0'
        )
        self.status_label.pack(side='left', padx=10)
        
        # Кнопки управления
        self.buttons_frame = tk.Frame(self.parent_frame, bg='#f0f0f0')
        self.buttons_frame.pack(pady=20)
        
        self.start_button = tk.Button(
            self.buttons_frame,
            text="🚀 Запустить API",
            command=self.start_api,
            font=('Arial', 12),
            bg='#4CAF50',
            fg='white',
            padx=20,
            pady=10,
            cursor='hand2'
        )
        self.start_button.pack(side='left', padx=10)
        
        self.stop_button = tk.Button(
            self.buttons_frame,
            text="🛑 Остановить API",
            command=self.stop_api,
            font=('Arial', 12),
            bg='#f44336',
            fg='white',
            padx=20,
            pady=10,
            cursor='hand2',
            state='disabled'
        )
        self.stop_button.pack(side='left', padx=10)
        
        self.cleanup_button = tk.Button(
            self.buttons_frame,
            text="🧹 Очистить процессы",
            command=self.force_cleanup,
            font=('Arial', 10),
            bg='#FF9800',
            fg='white',
            padx=15,
            pady=8,
            cursor='hand2'
        )
        self.cleanup_button.pack(side='left', padx=10)
        
        # ngrok URL
        self.url_frame = tk.Frame(self.parent_frame, bg='#f0f0f0')
        self.url_frame.pack(pady=20, padx=20, fill='x')
        
        tk.Label(self.url_frame, text="ngrok URL:", font=('Arial', 12), bg='#f0f0f0').pack(anchor='w')
        
        self.url_text_frame = tk.Frame(self.url_frame, bg='#f0f0f0')
        self.url_text_frame.pack(fill='x', pady=5)
        
        self.url_entry = tk.Entry(
            self.url_text_frame,
            font=('Arial', 11),
            state='readonly',
            bg='white'
        )
        self.url_entry.pack(side='left', fill='x', expand=True)
        
        self.copy_button = tk.Button(
            self.url_text_frame,
            text="📋 Копировать",
            command=self.copy_url,
            font=('Arial', 10),
            bg='#2196F3',
            fg='white',
            padx=10,
            cursor='hand2',
            state='disabled'
        )
        self.copy_button.pack(side='right', padx=(10, 0))
        
        # Информация
        self.info_frame = tk.LabelFrame(
            self.parent_frame, 
            text="Информация", 
            font=('Arial', 11),
            bg='#f0f0f0'
        )
        self.info_frame.pack(pady=20, padx=20, fill='both', expand=True)
        
        info_text = """
🔹 Нажмите "Запустить API" для старта сервера
🔹 После запуска скопируйте ngrok URL
🔹 Используйте URL для доступа к API
🔹 Документация доступна по адресу: {URL}/docs
🔹 Для остановки нажмите "Остановить API"
        """
        
        self.info_label = tk.Label(
            self.info_frame,
            text=info_text,
            font=('Arial', 10),
            justify='left',
            bg='#f0f0f0'
        )
        self.info_label.pack(padx=10, pady=10, anchor='w')
    
    def start_api(self):
        """Запуск API в отдельном потоке"""
        if self.is_running:
            return
        
        self.log_callback("🚀 Запуск API сервера...", "INFO")
        
        # Обновляем интерфейс
        self.is_running = True
        self.status_label.config(text="Запускается...", fg='orange')
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        
        # Запускаем API в отдельном потоке
        api_thread = threading.Thread(target=self.run_api_process, daemon=True)
        api_thread.start()
    
    def run_api_process(self):
        """Запуск процесса API"""
        try:
            # Проверяем, не занят ли порт 8000 и освобождаем его
            self.cleanup_port_8000()
            
            # Проверяем наличие venv
            if os.name == 'nt':  # Windows
                python_path = os.path.join('venv', 'Scripts', 'python.exe')
            else:  # Linux/Mac
                python_path = os.path.join('venv', 'bin', 'python')
            
            if not os.path.exists(python_path):
                python_path = sys.executable
                self.log_callback("⚠️ venv не найден, используем системный Python", "WARNING")
            
            # Проверяем, запускаемся ли мы из .exe файла
            if hasattr(sys, '_MEIPASS'):
                # Запуск из .exe - используем встроенные функции
                self.log_callback("🔧 Запуск API из .exe файла (встроенный режим)", "INFO")
                self.run_api_embedded()
                return
            else:
                # Запуск из исходного кода - используем subprocess
                cmd = [python_path, 'app.py']
                self.log_callback(f"🔧 Команда запуска: {' '.join(cmd)}", "DEBUG")
                
                self.api_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                )
                
                self.log_callback("✅ API процесс запущен", "INFO")
                
                # Обновляем статус в главном потоке
                self.parent_frame.after(0, lambda: self.status_label.config(text="Запущен", fg='green'))
                
                # Читаем вывод процесса
                ngrok_url_found = False
                startup_timeout = 30  # 30 секунд на запуск
                start_time = time.time()
                
                for line in iter(self.api_process.stdout.readline, ''):
                    if not self.is_running:  # Проверяем, не остановили ли мы процесс
                        break
                        
                    if line:
                        line = line.strip()
                        
                        # Ищем ngrok URL в выводе
                        ngrok_match = re.search(r'https://[a-zA-Z0-9-]+\.ngrok(?:-free)?\.app', line)
                        if ngrok_match and not ngrok_url_found:
                            self.ngrok_url = ngrok_match.group(0)
                            ngrok_url_found = True
                            self.parent_frame.after(0, self.update_ngrok_url)
                        
                        # Определяем уровень лога по содержимому
                        if 'ERROR' in line or 'error' in line.lower():
                            level = 'ERROR'
                        elif 'WARNING' in line or 'warning' in line.lower():
                            level = 'WARNING'
                        elif 'DEBUG' in line:
                            level = 'DEBUG'
                        else:
                            level = 'INFO'
                        
                        self.log_callback(line, level)
                    
                    # Проверяем, не завершился ли процесс
                    if self.api_process.poll() is not None:
                        break
                    
                    # Проверяем таймаут запуска
                    if not ngrok_url_found and (time.time() - start_time) > startup_timeout:
                        self.log_callback("⚠️ Таймаут запуска - ngrok URL не получен", "WARNING")
                        break
                
                # Процесс завершился
                if self.is_running:  # Только если мы не остановили его сами
                    self.log_callback("🛑 API процесс завершен", "WARNING")
                    self.parent_frame.after(0, self.on_api_stopped)
            
        except Exception as e:
            self.log_callback(f"❌ Ошибка запуска API: {e}", "ERROR")
            self.parent_frame.after(0, self.on_api_stopped)
    
    def stop_api(self):
        """Остановка API"""
        if not self.is_running:
            return
        
        self.log_callback("🛑 Остановка API сервера...", "INFO")
        
        try:
            # Проверяем режим запуска
            if hasattr(sys, '_MEIPASS'):
                # Встроенный режим - останавливаем ngrok и помечаем как остановленный
                self.log_callback("🔧 Остановка встроенного API...", "INFO")
                try:
                    from pyngrok import ngrok
                    # Правильный способ отключения всех туннелей
                    tunnels = ngrok.get_tunnels()
                    for tunnel in tunnels:
                        ngrok.disconnect(tunnel.public_url)
                    self.log_callback("🔌 ngrok туннели отключены", "INFO")
                except Exception as e:
                    self.log_callback(f"⚠️ Ошибка отключения ngrok: {e}", "WARNING")
                
                # Помечаем как остановленный (сервер остановится сам при завершении приложения)
                self.log_callback("✅ API остановлен (встроенный режим)", "INFO")
                
            elif self.api_process:
                # Режим subprocess - завершаем процесс
                # Сначала пытаемся мягко завершить
                self.api_process.terminate()
                
                # Ждем завершения
                try:
                    self.api_process.wait(timeout=3)
                    self.log_callback("✅ Процесс завершен корректно", "INFO")
                except subprocess.TimeoutExpired:
                    # Принудительное завершение
                    self.log_callback("⚠️ Принудительное завершение процесса...", "WARNING")
                    self.api_process.kill()
                    try:
                        self.api_process.wait(timeout=2)
                        self.log_callback("✅ Процесс принудительно завершен", "INFO")
                    except subprocess.TimeoutExpired:
                        self.log_callback("❌ Не удалось завершить процесс", "ERROR")
            
            # Дополнительная очистка ngrok процессов (Windows)
            if os.name == 'nt':
                try:
                    subprocess.run(['taskkill', '/f', '/im', 'ngrok.exe'], 
                                 capture_output=True, timeout=5)
                    self.log_callback("🔧 Очистка ngrok процессов", "INFO")
                except:
                    pass  # Игнорируем ошибки очистки
            
            self.log_callback("✅ API остановлен", "INFO")
            
        except Exception as e:
            self.log_callback(f"❌ Ошибка остановки API: {e}", "ERROR")
        
        # Небольшая задержка перед сбросом состояния
        import time
        time.sleep(0.5)
        
        self.on_api_stopped()
    
    def on_api_stopped(self):
        """Обработка остановки API"""
        # Сбрасываем состояние
        self.is_running = False
        self.api_process = None
        self.ngrok_url = None
        
        # Обновляем интерфейс
        self.status_label.config(text="Остановлен", fg='red')
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.copy_button.config(state='disabled')
        
        # Очищаем URL
        self.url_entry.config(state='normal')
        self.url_entry.delete(0, tk.END)
        self.url_entry.config(state='readonly')
        
        # Логируем готовность к новому запуску
        self.log_callback("🔄 Готов к новому запуску", "INFO")
    
    def update_ngrok_url(self):
        """Обновление ngrok URL в интерфейсе"""
        if self.ngrok_url:
            self.url_entry.config(state='normal')
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, self.ngrok_url)
            self.url_entry.config(state='readonly')
            self.copy_button.config(state='normal')
            
            self.log_callback(f"🌐 ngrok URL получен: {self.ngrok_url}", "INFO")
    
    def copy_url(self):
        """Копирование URL в буфер обмена"""
        if self.ngrok_url:
            self.parent_frame.clipboard_clear()
            self.parent_frame.clipboard_append(self.ngrok_url)
            self.parent_frame.update()
            
            self.log_callback("📋 URL скопирован в буфер обмена", "INFO")
            messagebox.showinfo("Успех", "URL скопирован в буфер обмена!")
    
    def cleanup_port_8000(self):
        """Очистка порта 8000 от занимающих процессов"""
        try:
            # Проверяем, не занят ли порт 8000
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', 8000))
            sock.close()
            
            if result == 0:
                self.log_callback("⚠️ Порт 8000 занят, освобождаем...", "WARNING")
                
                if os.name == 'nt':  # Windows
                    # Находим и убиваем процессы на порту 8000
                    result = subprocess.run(['netstat', '-ano'], 
                                          capture_output=True, text=True, timeout=5)
                    for line in result.stdout.split('\n'):
                        if ':8000' in line and 'LISTENING' in line:
                            parts = line.split()
                            if len(parts) > 4:
                                pid = parts[-1]
                                try:
                                    subprocess.run(['taskkill', '/f', '/pid', pid], 
                                                 capture_output=True, timeout=3)
                                    self.log_callback(f"🔧 Завершен процесс PID {pid} на порту 8000", "INFO")
                                except:
                                    pass
                else:  # Linux/Mac
                    # Убиваем процессы на порту 8000
                    subprocess.run(['lsof', '-ti:8000', '|', 'xargs', 'kill', '-9'], 
                                 shell=True, capture_output=True, timeout=5)
                    self.log_callback("🔧 Процессы на порту 8000 завершены", "INFO")
                
                # Ждем немного, чтобы порт освободился
                time.sleep(1)
        except:
            pass  # Игнорируем ошибки проверки порта
    
    def cleanup_ngrok_processes(self):
        """Принудительная очистка ngrok процессов"""
        try:
            if os.name == 'nt':  # Windows
                # Убиваем все процессы ngrok
                subprocess.run(['taskkill', '/f', '/im', 'ngrok.exe'], 
                             capture_output=True, timeout=5)
                self.log_callback("🔧 ngrok процессы завершены", "INFO")
            else:  # Linux/Mac
                # Убиваем процессы ngrok
                subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True, timeout=5)
                self.log_callback("🔧 ngrok процессы завершены", "INFO")
        except:
            pass  # Игнорируем ошибки очистки
    
    def run_api_embedded(self):
        """Запуск API встроенно в .exe файле"""
        try:
            # Очищаем порт 8000 перед запуском
            self.cleanup_port_8000()
            
            # Импортируем функции из app.py
            from app import app
            import uvicorn
            
            self.log_callback("✅ API модули импортированы", "INFO")
            
            # Запускаем ngrok туннель с обработкой ошибок
            self.log_callback("🌐 Запуск ngrok туннеля...", "INFO")
            try:
                # Пытаемся запустить ngrok напрямую
                from pyngrok import ngrok
                tunnel = ngrok.connect(8000)
                if tunnel:
                    # Извлекаем только URL из объекта NgrokTunnel
                    self.ngrok_url = tunnel.public_url
                    self.parent_frame.after(0, self.update_ngrok_url)
                    self.log_callback(f"✅ ngrok туннель запущен: {self.ngrok_url}", "INFO")
            except Exception as e:
                self.log_callback(f"⚠️ Ошибка ngrok: {e}", "WARNING")
                self.log_callback("🔧 Работаем только с локальным сервером", "INFO")
            
            self.log_callback("🌐 Локальный сервер: http://localhost:8000", "INFO")
            
            # Обновляем статус
            self.parent_frame.after(0, lambda: self.status_label.config(text="Запущен", fg='green'))
            
            # Запускаем FastAPI сервер в отдельном потоке
            def run_server():
                try:
                    self.log_callback("🔥 Запуск FastAPI сервера...", "INFO")
                    
                    # Запускаем сервер с минимальной конфигурацией для .exe
                    uvicorn.run(
                        app,
                        host="0.0.0.0",
                        port=8000,
                        reload=False,
                        log_level="error",  # Минимальный уровень логов
                        access_log=False,   # Отключаем access log
                        use_colors=False,   # Отключаем цвета
                        log_config=None     # Отключаем кастомную конфигурацию логов
                    )
                except Exception as e:
                    self.log_callback(f"❌ Ошибка сервера: {e}", "ERROR")
                    self.parent_frame.after(0, self.on_api_stopped)
            
            # Запускаем сервер в отдельном потоке
            self.api_thread = threading.Thread(target=run_server, daemon=True)
            self.api_thread.start()
            
            self.log_callback("✅ API запущен в встроенном режиме", "INFO")
            
        except Exception as e:
            self.log_callback(f"❌ Ошибка запуска встроенного API: {e}", "ERROR")
            self.parent_frame.after(0, self.on_api_stopped)
    
    def force_cleanup(self):
        """Принудительная очистка всех процессов"""
        self.log_callback("🧹 Принудительная очистка процессов...", "INFO")
        
        # Останавливаем API если запущен
        if self.is_running:
            self.stop_api()
        
        # Ждем немного
        time.sleep(1)
        
        # Принудительная очистка
        self.cleanup_ngrok_processes()
        self.cleanup_port_8000()
        
        # Сбрасываем состояние
        self.on_api_stopped()
        
        self.log_callback("✅ Принудительная очистка завершена", "INFO")
        messagebox.showinfo("Очистка", "Все процессы очищены. Можно запускать заново.")
    
    def cleanup(self):
        """Очистка ресурсов при закрытии"""
        if self.is_running:
            self.stop_api()
        
        # Принудительная очистка
        self.cleanup_ngrok_processes()