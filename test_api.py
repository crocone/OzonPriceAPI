#!/usr/bin/env python3
"""
Тестовый файл для проверки API парсера Ozon
Тестирует реальные артикулы: 2360879218, 859220077, 2430448285, 2392842054, 
1774818716, 1649767704, 2433082108, 1372069683
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
        
        print("\n2️⃣  Парсинг одного артикула:")
        print(f"curl -X POST \"{self.base_url}/api/v1/get_price\" \\")
        print("     -H \"Content-Type: application/json\" \\")
        print("     -d '{\"articles\": [2360879218]}'")
        
        print("\n3️⃣  Парсинг нескольких артикулов:")
        print(f"curl -X POST \"{self.base_url}/api/v1/get_price\" \\")
        print("     -H \"Content-Type: application/json\" \\")
        print("     -d '{\"articles\": [2360879218, 859220077, 2430448285]}'")
        
        print("\n4️⃣  Парсинг всех тестовых артикулов:")
        print(f"curl -X POST \"{self.base_url}/api/v1/get_price\" \\")
        print("     -H \"Content-Type: application/json\" \\")
        print("     -d '{\"articles\": [2360879218,859220077,2430448285,2392842054,1774818716,1649767704,2433082108,1372069683]}'")
        
        print("\n5️⃣  Получение документации API:")
        print(f"curl -X GET \"{self.base_url}/docs\"")
        
        print("\n6️⃣  Проверка здоровья API:")
        print(f"curl -X GET \"{self.base_url}/api/v1/health\"")
        
        print("\n7️⃣  Получение OpenAPI схемы:")
        print(f"curl -X GET \"{self.base_url}/openapi.json\"")
        
        print("\n" + "="*60)
    
    def run_full_test(self):
        """
        Запуск полного набора тестов с реальными артикулами
        """
        print("🚀 ЗАПУСК ТЕСТИРОВАНИЯ API С РЕАЛЬНЫМИ АРТИКУЛАМИ")
        print("="*60)
        
        # Реальные тестовые артикулы
        test_articles = [
            2360879218, 859220077, 2430448285, 2392842054, 
            1774818716, 1649767704, 2433082108, 1372069683,
            2360879218,859220077,2430448285,2392842054,1774818716,1649767704,2433082108,1372069683,1769433039,1837510918,2384249751,2384245580,2328688150,2328688150,2246018851,2274804444,2229057548,1707200180,1563574023,1922781846,550798603,1640239319,2246017617,2042778498,1972531799,1891423572,1590382207,1644248201,1922781204,1044578885,1761947652,1871396205,2403251730,2403251749,1972531451,1998259730,2293789309,1787544241,1691820698
        ]
        
        print(f"📦 Тестируем {len(test_articles)} артикулов:")
        for i, article in enumerate(test_articles, 1):
            print(f"  {i}. {article}")
        
        # 1. Проверка доступности API
        print("\n" + "="*50)
        print("🔍 ПРОВЕРКА ДОСТУПНОСТИ API")
        print("="*50)
        
        if not self.test_health_check():
            print("❌ API недоступен. Тестирование прервано.")
            return False
        
        # 2. Тестирование множественного парсинга (основной тест)
        print("\n" + "="*50)
        print("🔍 ТЕСТИРОВАНИЕ МНОЖЕСТВЕННОГО ПАРСИНГА")
        print("="*50)
        
        multiple_result = self.test_multiple_articles(test_articles)
        
        # 3. Детальный анализ результатов
        print("\n" + "="*50)
        print("📊 ДЕТАЛЬНЫЙ АНАЛИЗ РЕЗУЛЬТАТОВ")
        print("="*50)
        
        if not multiple_result.get('error') and 'results' in multiple_result:
            results = multiple_result['results']
            
            print(f"📈 Общая статистика:")
            print(f"  • Всего артикулов: {len(test_articles)}")
            print(f"  • Получено результатов: {len(results)}")
            print(f"  • Успешно обработано: {multiple_result.get('parsed_articles', 0)}")
            print(f"  • Неудачных попыток: {len(test_articles) - multiple_result.get('parsed_articles', 0)}")
            
            # Анализ по каждому артикулу
            print(f"\n📋 Результаты по артикулам:")
            for i, result in enumerate(results, 1):
                article = result.get('article', 'Unknown')
                success = result.get('success', False)
                available = result.get('isAvailable', False)
                
                status_icon = "✅" if success else "❌"
                avail_icon = "📦" if available else "📭"
                
                print(f"  {i}. {article} {status_icon} {avail_icon}")
                
                if success and result.get('price_info'):
                    price_info = result['price_info']
                    if price_info.get('cardPrice'):
                        print(f"     💰 Цена по карте: {price_info['cardPrice']} руб.")
                    if price_info.get('price'):
                        print(f"     💵 Обычная цена: {price_info['price']} руб.")
                
                if result.get('title'):
                    title = result['title'][:60] + "..." if len(result['title']) > 60 else result['title']
                    print(f"     🏷️  {title}")
                
                if result.get('error'):
                    print(f"     ⚠️  Ошибка: {result['error']}")
                
                print()  # Пустая строка для разделения
        
        # 4. Генерация примеров curl
        self.generate_curl_examples()
        
        # 5. Итоговая статистика
        print("\n" + "="*50)
        print("🎯 ИТОГОВАЯ СТАТИСТИКА")
        print("="*50)
        
        if not multiple_result.get('error'):
            success_rate = (multiple_result.get('parsed_articles', 0) / len(test_articles)) * 100
            print(f"✅ Тест завершен успешно")
            print(f"📊 Процент успеха: {success_rate:.1f}%")
            print(f"⏱️  Среднее время на артикул: ~{120/len(test_articles):.1f} сек")
            
            if success_rate >= 80:
                print("🎉 Отличный результат! API работает стабильно")
            elif success_rate >= 60:
                print("👍 Хороший результат, есть место для улучшений")
            else:
                print("⚠️  Низкий процент успеха, требуется оптимизация")
        else:
            print("❌ Тест завершен с ошибками")
            print(f"🔍 Ошибка: {multiple_result.get('error', 'Unknown')}")
        
        return not multiple_result.get('error', True)


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