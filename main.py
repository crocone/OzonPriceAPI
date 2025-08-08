#!/usr/bin/env python3
"""
Главный файл запуска GUI для Ozon Parser API
"""

import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from gui.gui_manager import main
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"❌ Ошибка импорта GUI: {e}")
    print("Убедитесь, что установлен tkinter (обычно идет с Python)")
    print("Если проблема не решается, запустите API напрямую:")
    print("python app.py")
    input("Нажмите Enter для выхода...")
except Exception as e:
    print(f"❌ Ошибка запуска GUI: {e}")
    input("Нажмите Enter для выхода...")