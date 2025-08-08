#!/usr/bin/env python3
"""
Главный менеджер GUI для Ozon Parser API
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.tabs.control_tab import ControlTab
from gui.tabs.logs_tab import LogsTab


class OzonParserGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ozon Parser API - Управление")
        self.root.geometry("800x600")
        self.root.configure(bg='#f0f0f0')
        
        # Создание интерфейса
        self.create_widgets()
        
        # Настройка обработчика закрытия
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        """Создание основных виджетов"""
        # Создаем notebook для вкладок
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Создаем фреймы для вкладок
        self.control_frame = ttk.Frame(self.notebook)
        self.logs_frame = ttk.Frame(self.notebook)
        
        # Добавляем вкладки в notebook
        self.notebook.add(self.control_frame, text="Управление")
        self.notebook.add(self.logs_frame, text="Логи")
        
        # Создаем вкладку логов (сначала, чтобы логирование работало)
        self.logs_tab = LogsTab(self.logs_frame)
        
        # Создаем вкладку управления (передаем callback для логирования)
        self.control_tab = ControlTab(self.control_frame, self.logs_tab.log_message)
        
        # Логируем запуск GUI
        self.logs_tab.log_message("🖥️ GUI приложение запущено", "INFO")
    
    def on_closing(self):
        """Обработка закрытия приложения"""
        if hasattr(self.control_tab, 'is_running') and self.control_tab.is_running:
            if messagebox.askokcancel("Выход", "API все еще запущен. Остановить и выйти?"):
                self.control_tab.cleanup()
                self.root.after(1000, self.root.destroy)
        else:
            self.root.destroy()


def main():
    """Главная функция запуска GUI"""
    try:
        root = tk.Tk()
        app = OzonParserGUI(root)
        root.mainloop()
    except Exception as e:
        print(f"Ошибка запуска GUI: {e}")
        input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    main()