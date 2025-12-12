# captcha_solver.py
import cv2
import numpy as np
import io
import time
import random
from selenium.webdriver.common.action_chains import ActionChains
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class SliderCaptchaSolver:
    """Решатель слайдер-капч типа 'Slide the puzzle piece'"""

    def __init__(self, driver):
        self.driver = driver

    def is_slider_captcha_present(self):
        """Проверяет, присутствует ли слайдер-капча на странице"""
        try:
            captcha_indicators = [
                "Confirm that you're not a bot",
                "Slide the",
                "puzzle piece",
                "slider",
                "Slide to fit"
            ]

            page_source = self.driver.page_source
            page_text = self.driver.find_element_by_tag_name('body').text

            for indicator in captcha_indicators:
                if indicator.lower() in page_source.lower() or indicator.lower() in page_text.lower():
                    return True

            # Проверяем наличие слайдера
            slider_elements = self.driver.find_elements_by_xpath(
                "//*[contains(@class, 'slider') or contains(@class, 'captcha') or contains(@class, 'puzzle')]"
            )
            return len(slider_elements) > 0

        except Exception as e:
            logger.debug(f"Error checking captcha: {e}")
            return False

    def find_slider_element(self):
        """Находит элемент слайдера на странице"""
        try:
            # Пробуем разные селекторы
            selectors = [
                "div[class*='slider']",
                "div[class*='captcha'] button",
                "button[class*='slider']",
                ".slider-container button",
                "div[role='slider']",
                "#slider",
                ".slider"
            ]

            for selector in selectors:
                elements = self.driver.find_elements_by_css_selector(selector)
                if elements:
                    return elements[0]

            # Ищем по атрибутам
            elements = self.driver.find_elements_by_xpath(
                "//*[@draggable='true' or @aria-valuenow or contains(@style, 'cursor: grab')]"
            )
            if elements:
                return elements[0]

        except Exception as e:
            logger.debug(f"Error finding slider: {e}")

        return None

    def get_captcha_images(self):
        """Извлекает изображения капчи (фон и пазл)"""
        try:
            # Пытаемся найти элементы изображений
            images = self.driver.find_elements_by_tag_name('img')
            captcha_images = []

            for img in images:
                src = img.get_attribute('src') or ''
                alt = img.get_attribute('alt') or ''
                class_name = img.get_attribute('class') or ''

                # Ищем изображения капчи
                if any(keyword in src.lower() or keyword in alt.lower() or keyword in class_name.lower()
                       for keyword in ['captcha', 'puzzle', 'slider', 'challenge']):
                    captcha_images.append(img)

            # Если нашли 2 изображения (фон и пазл)
            if len(captcha_images) >= 2:
                return captcha_images[:2]

            # Ищем canvas элементы
            canvas_elements = self.driver.find_elements_by_tag_name('canvas')
            if canvas_elements:
                return canvas_elements

        except Exception as e:
            logger.debug(f"Error getting captcha images: {e}")

        return []

    def calculate_slider_offset(self, background_img, puzzle_img):
        """Вычисляет необходимое смещение слайдера"""
        try:
            # Конвертируем изображения в numpy массивы
            if isinstance(background_img, Image.Image):
                bg_np = np.array(background_img)
            else:
                bg_np = background_img

            if isinstance(puzzle_img, Image.Image):
                puzzle_np = np.array(puzzle_img)
            else:
                puzzle_np = puzzle_img

            # Конвертируем в оттенки серого
            bg_gray = cv2.cvtColor(bg_np, cv2.COLOR_RGB2GRAY)
            puzzle_gray = cv2.cvtColor(puzzle_np, cv2.COLOR_RGB2GRAY)

            # Для слайдер-капчи обычно пазл нужно найти на фоне
            # Используем template matching
            result = cv2.matchTemplate(bg_gray, puzzle_gray, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # max_loc содержит координаты наилучшего совпадения
            # Это и есть целевая позиция пазла
            target_x = max_loc[0]

            # Текущая позиция пазла обычно в начале (0 или смещение контейнера)
            # Вычисляем необходимое смещение
            offset = target_x

            # Добавляем небольшую поправку (обычно нужно сместить немного дальше)
            offset = int(offset * 1.02)  # +2% компенсация

            logger.info(f"Calculated slider offset: {offset}px (target_x: {target_x})")
            return offset

        except Exception as e:
            logger.error(f"Error calculating offset: {e}")
            return None

    def simulate_human_drag(self, slider, offset):
        """Имитирует человеческое перетаскивание слайдера"""
        try:
            actions = ActionChains(self.driver)

            # Нажимаем на слайдер
            actions.click_and_hold(slider)
            actions.pause(random.uniform(0.1, 0.3))

            # Разбиваем перемещение на несколько этапов с разной скоростью
            current_x = 0
            steps = []

            # Ускорение в начале
            for i in range(3):
                step = offset * 0.1
                steps.append(step)
                current_x += step

            # Равномерное движение
            remaining = offset - current_x
            uniform_steps = 5
            for i in range(uniform_steps):
                step = remaining / (uniform_steps - i) if i < uniform_steps - 1 else remaining
                steps.append(step)
                current_x += step

            # Добавляем небольшие случайные отклонения
            steps = [s + random.uniform(-2, 2) for s in steps]

            # Выполняем перемещение
            for step in steps:
                actions.move_by_offset(step, random.uniform(-1, 1))
                actions.pause(random.uniform(0.05, 0.15))

            # Небольшая задержка перед отпусканием
            actions.pause(random.uniform(0.1, 0.3))
            actions.release()
            actions.pause(random.uniform(0.2, 0.5))

            # Выполняем все действия
            actions.perform()

            logger.info(f"Simulated human drag for {offset}px")
            return True

        except Exception as e:
            logger.error(f"Error simulating drag: {e}")
            return False

    def solve_slider_captcha(self):
        """Основной метод решения слайдер-капчи"""
        try:
            logger.info("Attempting to solve slider captcha...")

            # 1. Проверяем наличие капчи
            if not self.is_slider_captcha_present():
                logger.info("No slider captcha detected")
                return False

            # 2. Делаем скриншот всей страницы
            screenshot = self.driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(screenshot))

            # 3. Находим слайдер
            slider = self.find_slider_element()
            if not slider:
                logger.warning("Slider element not found")
                return False

            # 4. Пытаемся получить изображения капчи
            captcha_elements = self.get_captcha_images()

            if len(captcha_elements) >= 2:
                # Скачиваем оба изображения
                bg_src = captcha_elements[0].get_attribute('src')
                puzzle_src = captcha_elements[1].get_attribute('src')

                # Здесь можно добавить загрузку изображений по URL
                # Но для простоты будем использовать скриншот
                pass

            # 5. Для простоты используем фиксированное смещение
            # В реальном приложении нужно вычислить точное смещение
            # Но так как у нас нет реальных изображений, используем эвристику

            # Получаем размер слайдера
            slider_size = slider.size
            container_width = 300  # Примерная ширина контейнера капчи

            # Пробуем разные смещения
            for offset in [container_width * 0.7, container_width * 0.8, container_width * 0.9, container_width]:
                logger.info(f"Trying offset: {offset}px")

                if self.simulate_human_drag(slider, offset):
                    # Ждем реакции страницы
                    time.sleep(2)

                    # Проверяем, исчезла ли капча
                    if not self.is_slider_captcha_present():
                        logger.info("Captcha solved successfully!")
                        return True

            logger.warning("Failed to solve captcha with any offset")
            return False

        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            return False

    def solve_with_retry(self, max_retries=3):
        """Пытается решить капчу несколько раз"""
        for attempt in range(max_retries):
            logger.info(f"Captcha solving attempt {attempt + 1}/{max_retries}")

            if self.solve_slider_captcha():
                return True

            # Ждем перед следующей попыткой
            time.sleep(random.uniform(2, 4))

        return False