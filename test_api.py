#!/usr/bin/env python3
"""
Тестовый файл для проверки API парсера Ozon
Тестирует артикулы: 158761892 и 2278238527
"""

import requests
import json
import time
import sys
from typing import List, Dict, Any


class OzonAPITester:
    def __init__(self, base_url: str):
        """
        Инициализация тестера API
        
        Args:
            base_url: Базовый URL API (например, https://abc123.ngrok.io)
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'OzonAPITester/1.0'
        })
    
    def test_health_check(self) -> bool:
        """
        Проверка доступности API
        """
        try:
            print("🔍 Проверка доступности API...")
            response = self.session.get(f"{self.base_url}/")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ API доступен: {data.get('message', 'Unknown')}")
                print(f"📋 Версия: {data.get('version', 'Unknown')}")
                return True
            else:
                print(f"❌ API недоступен. Статус: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка подключения к API: {e}")
            return False
    
    def test_single_article(self, article: int) -> Dict[str, Any]:
        """
        Тестирование парсинга одного артикула
        
        Args:
            article: Номер артикула для тестирования
            
        Returns:
            Результат парсинга
        """
        try:
            print(f"\n🔍 Тестирование артикула: {article}")
            
            # Подготавливаем данные запроса
            payload = {
                "articles": [article]
            }
            
            # Отправляем запрос
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/api/v1/get_price",
                json=payload,
                timeout=60  # Увеличиваем таймаут для парсинга
            )
            end_time = time.time()
            
            # Анализируем ответ
            if response.status_code == 200:
                data = response.json()
                duration = end_time - start_time
                
                print(f"✅ Запрос выполнен успешно за {duration:.2f} секунд")
                
                # Проверяем результаты
                if 'results' in data and len(data['results']) > 0:
                    result = data['results'][0]
                    
                    print(f"📦 Артикул: {result.get('article')}")
                    print(f"🎯 Успешно: {result.get('success')}")
                    print(f"📋 Доступен: {result.get('isAvailable')}")
                    
                    if result.get('title'):
                        print(f"🏷️  Название: {result['title'][:80]}...")
                    
                    if result.get('price_info'):
                        price_info = result['price_info']
                        if price_info.get('cardPrice'):
                            print(f"💰 Цена по карте: {price_info['cardPrice']} руб.")
                        if price_info.get('price'):
                            print(f"💵 Обычная цена: {price_info['price']} руб.")
                        if price_info.get('originalPrice'):
                            print(f"🏷️  Первоначальная цена: {price_info['originalPrice']} руб.")
                    
                    if result.get('seller'):
                        print(f"🏪 Продавец: {result['seller'].get('name', 'Неизвестно')}")
                    
                    if result.get('error'):
                        print(f"⚠️  Ошибка: {result['error']}")
                
                return data
            else:
                print(f"❌ Ошибка запроса. Статус: {response.status_code}")
                print(f"📄 Ответ: {response.text}")
                return {"error": f"HTTP {response.status_code}", "response": response.text}
                
        except requests.exceptions.Timeout:
            print(f"⏰ Таймаут запроса для артикула {article}")
            return {"error": "Timeout"}
        except Exception as e:
            print(f"❌ Ошибка при тестировании артикула {article}: {e}")
            return {"error": str(e)}
    
    def test_multiple_articles(self, articles: List[int]) -> Dict[str, Any]:
        """
        Тестирование парсинга нескольких артикулов
        
        Args:
            articles: Список артикулов для тестирования
            
        Returns:
            Результат парсинга
        """
        try:
            print(f"\n🔍 Тестирование множественных артикулов: {articles}")
            
            # Подготавливаем данные запроса
            payload = {
                "articles": articles
            }
            
            # Отправляем запрос
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/api/v1/get_price",
                json=payload,
                timeout=120  # Увеличиваем таймаут для множественного парсинга
            )
            end_time = time.time()
            
            # Анализируем ответ
            if response.status_code == 200:
                data = response.json()
                duration = end_time - start_time
                
                print(f"✅ Запрос выполнен успешно за {duration:.2f} секунд")
                print(f"📊 Обработано артикулов: {len(data.get('results', []))}")
                
                # Статистика по результатам
                successful = sum(1 for r in data.get('results', []) if r.get('success'))
                available = sum(1 for r in data.get('results', []) if r.get('isAvailable'))
                
                print(f"✅ Успешно обработано: {successful}/{len(articles)}")
                print(f"📦 Доступно товаров: {available}/{len(articles)}")
                
                return data
            else:
                print(f"❌ Ошибка запроса. Статус: {response.status_code}")
                print(f"📄 Ответ: {response.text}")
                return {"error": f"HTTP {response.status_code}", "response": response.text}
                
        except requests.exceptions.Timeout:
            print(f"⏰ Таймаут запроса для артикулов {articles}")
            return {"error": "Timeout"}
        except Exception as e:
            print(f"❌ Ошибка при тестировании артикулов {articles}: {e}")
            return {"error": str(e)}
    
    def generate_curl_examples(self):
        """
        Генерирует примеры curl запросов
        """
        print("\n" + "="*60)
        print("📋 ПРИМЕРЫ CURL ЗАПРОСОВ")
        print("="*60)
        
        print("\n1️⃣  Проверка доступности API:")
        print(f"curl -X GET \"{self.base_url}/\"")
        
        print("\n2️⃣  Парсинг одного артикула (158761892):")
        print(f"curl -X POST \"{self.base_url}/api/v1/get_price\" \\")
        print("     -H \"Content-Type: application/json\" \\")
        print("     -d '{\"articles\": [158761892]}'")
        
        print("\n3️⃣  Парсинг двух артикулов (158761892 и 2278238527):")
        print(f"curl -X POST \"{self.base_url}/api/v1/get_price\" \\")
        print("     -H \"Content-Type: application/json\" \\")
        print("     -d '{\"articles\": [158761892, 2278238527]}'")
        
        print("\n4️⃣  Получение документации API:")
        print(f"curl -X GET \"{self.base_url}/docs\"")
        
        print("\n5️⃣  Получение OpenAPI схемы:")
        print(f"curl -X GET \"{self.base_url}/openapi.json\"")
        
        print("\n6️⃣  Проверка здоровья API:")
        print(f"curl -X GET \"{self.base_url}/api/v1/health\"")
        
        print("\n" + "="*60)
    
    def run_full_test(self):
        """
        Запуск полного набора тестов
        """
        print("🚀 ЗАПУСК ПОЛНОГО ТЕСТИРОВАНИЯ API")
        print("="*50)
        
        # Тестовые артикулы
        test_articles = [158761892, 2278238527]
        
        # 1. Проверка доступности
        if not self.test_health_check():
            print("❌ API недоступен. Тестирование прервано.")
            return False
        
        # 2. Тестирование отдельных артикулов
        print("\n" + "="*50)
        print("🔍 ТЕСТИРОВАНИЕ ОТДЕЛЬНЫХ АРТИКУЛОВ")
        print("="*50)
        
        individual_results = []
        for article in test_articles:
            result = self.test_single_article(article)
            individual_results.append(result)
            time.sleep(1)  # Небольшая пауза между запросами
        
        # 3. Тестирование множественного парсинга
        print("\n" + "="*50)
        print("🔍 ТЕСТИРОВАНИЕ МНОЖЕСТВЕННОГО ПАРСИНГА")
        print("="*50)
        
        multiple_result = self.test_multiple_articles(test_articles)
        
        # 4. Генерация примеров curl
        self.generate_curl_examples()
        
        # 5. Итоговая статистика
        print("\n" + "="*50)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("="*50)
        
        successful_individual = sum(1 for r in individual_results if not r.get('error'))
        print(f"✅ Успешных индивидуальных тестов: {successful_individual}/{len(test_articles)}")
        
        if not multiple_result.get('error'):
            print("✅ Множественный тест: Успешно")
        else:
            print("❌ Множественный тест: Неуспешно")
        
        return True


def main():
    """
    Главная функция для запуска тестов
    """
    # Проверяем аргументы командной строки
    if len(sys.argv) < 2:
        print("❌ Использование: python test_api.py <ngrok_url>")
        print("📝 Пример: python test_api.py https://abc123.ngrok.io")
        sys.exit(1)
    
    base_url = sys.argv[1]
    
    # Создаем тестер и запускаем тесты
    tester = OzonAPITester(base_url)
    tester.run_full_test()


if __name__ == "__main__":
    main()