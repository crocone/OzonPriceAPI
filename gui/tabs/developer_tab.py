#!/usr/bin/env python3
"""
Вкладка с информацией о разработчике
"""

import tkinter as tk
from tkinter import ttk
import webbrowser


class DeveloperTab:
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.create_widgets()
    
    def create_widgets(self):
        """Создание виджетов вкладки разработчика"""
        # Основной контейнер
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill='both', expand=True, padx=40, pady=40)
        
        # Заголовок
        title_label = tk.Label(
            main_frame,
            text="👨‍💻 РАЗРАБОТЧИК OZON ПАРСЕРА",
            font=('Arial', 20, 'bold'),
            fg='#2c3e50'
        )
        title_label.pack(pady=(0, 40))
        
        # Контейнер для контактов
        contacts_frame = ttk.LabelFrame(main_frame, text="Контактная информация", padding=40)
        contacts_frame.pack(fill='x')
        
        # Telegram
        telegram_frame = ttk.Frame(contacts_frame)
        telegram_frame.pack(fill='x', pady=20)
        
        tk.Label(
            telegram_frame,
            text="📱 Telegram:",
            font=('Arial', 16, 'bold')
        ).pack(anchor='w')
        
        telegram_btn = tk.Button(
            telegram_frame,
            text="@NurjahonErgashevMe",
            font=('Arial', 16),
            fg='#0088cc',
            relief='flat',
            cursor='hand2',
            command=lambda: webbrowser.open('https://t.me/NurjahonErgashevMe')
        )
        telegram_btn.pack(anchor='w', pady=(10, 0))
        
        # Kwork
        kwork_frame = ttk.Frame(contacts_frame)
        kwork_frame.pack(fill='x', pady=20)
        
        tk.Label(
            kwork_frame,
            text="💼 Kwork:",
            font=('Arial', 16, 'bold')
        ).pack(anchor='w')
        
        kwork_btn = tk.Button(
            kwork_frame,
            text="kwork.ru/user/nurjahonergashevme",
            font=('Arial', 16),
            fg='#0088cc',
            relief='flat',
            cursor='hand2',
            command=lambda: webbrowser.open('https://kwork.ru/user/nurjahonergashevme')
        )
        kwork_btn.pack(anchor='w', pady=(10, 0))