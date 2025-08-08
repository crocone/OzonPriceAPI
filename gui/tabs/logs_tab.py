#!/usr/bin/env python3
"""
Вкладка логов
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import time
import queue
import logging
from typing import Optional


class LogHandler(logging.Handler):
    """Кастомный обработчик логов для GUI"""
    
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        self.log_queue.put(record)


class LogsTab:
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        
        # Очередь для логов
        self.log_queue = queue.Queue()
        
        # Создание интерфейса
        self.create_widgets()
        
        # Настройка логирования
        self.setup_logging()
        
        # Запуск обработки логов
        self.process_logs()
    
    def create_widgets(self):
        """Создание виджетов вкладки логов"""
        # Заголовок
        logs_title = tk.Label(
            self.parent_frame, 
            text="Логи системы", 
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0'
        )
        logs_title.pack(pady=10)
        
        # Кнопки управления логами
        logs_controls = tk.Frame(self.parent_frame, bg='#f0f0f0')
        logs_controls.pack(pady=5)
        
        clear_button = tk.Button(
            logs_controls,
            text="🗑️ Очистить логи",
            command=self.clear_logs,
            font=('Arial', 10),
            bg='#FF9800',
            fg='white',
            padx=15,
            cursor='hand2'
        )
        clear_button.pack(side='left', padx=5)
        
        # Область логов
        self.logs_text = scrolledtext.ScrolledText(
            self.parent_frame,
            wrap=tk.WORD,
            font=('Consolas', 9),
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='white'
        )
        self.logs_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Настройка цветов для разных уровней логов
        self.logs_text.tag_configure('INFO', foreground='#00ff00')      # Зеленый
        self.logs_text.tag_configure('WARNING', foreground='#ffff00')   # Желтый
        self.logs_text.tag_configure('ERROR', foreground='#ff0000')     # Красный
        self.logs_text.tag_configure('DEBUG', foreground='#888888')     # Серый
        self.logs_text.tag_configure('CRITICAL', foreground='#ff00ff')  # Пурпурный
    
    def setup_logging(self):
        """Настройка системы логирования"""
        # Создаем обработчик для GUI
        self.log_handler = LogHandler(self.log_queue)
        self.log_handler.setLevel(logging.INFO)
        
        # Форматтер для логов
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        
        # Добавляем обработчик к root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        root_logger.setLevel(logging.INFO)
    
    def clear_logs(self):
        """Очистка логов"""
        self.logs_text.delete(1.0, tk.END)
        self.log_message("🗑️ Логи очищены", "INFO")
    
    def log_message(self, message: str, level: str = "INFO"):
        """Добавление сообщения в логи"""
        timestamp = time.strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        
        # Добавляем в очередь логов
        record = logging.LogRecord(
            name="GUI",
            level=getattr(logging, level),
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        self.log_queue.put(record)
    
    def process_logs(self):
        """Обработка очереди логов"""
        try:
            while True:
                record = self.log_queue.get_nowait()
                
                # Форматируем сообщение
                timestamp = time.strftime("%H:%M:%S", time.localtime(record.created))
                message = f"[{timestamp}] {record.getMessage()}\n"
                
                # Определяем цвет по уровню
                level_name = record.levelname
                
                # Добавляем в текстовое поле
                self.logs_text.insert(tk.END, message, level_name)
                self.logs_text.see(tk.END)
                
        except queue.Empty:
            pass
        
        # Планируем следующую обработку
        self.parent_frame.after(100, self.process_logs)