# utils/ozon_captcha_solver_v3.py
import cv2
import numpy as np
import io
import time
import random
import logging
import requests
from PIL import Image
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import base64

logger = logging.getLogger(__name__)


class OzonCaptchaSolverV3:
    """Продвинутый решатель капчи Ozon с одним непрерывным движением"""

    def __init__(self, driver):
        self.driver = driver
        self.scale = 1.0
        self.container_width = 0

    def get_scale_factor(self):
        """Получает масштаб из стиля капчи"""
        try:
            captcha_element = self.driver.find_element(By.ID, "captcha")
            style = captcha_element.get_attribute("style")

            import re
            scale_match = re.search(r'--scale:\s*([\d.]+)', style)
            if scale_match:
                self.scale = float(scale_match.group(1))
                logger.info(f"Found scale factor: {self.scale}")
            else:
                self.scale = 1.28  # Значение по умолчанию для Ozon

        except Exception as e:
            logger.warning(f"Could not determine scale factor: {e}")
            self.scale = 1.28

        return self.scale

    def get_container_width(self):
        """Получает ширину контейнера слайдера"""
        try:
            container = self.driver.find_element(By.ID, "slider-container")
            self.container_width = container.size['width']
            logger.info(f"Container width: {self.container_width}px")
            return self.container_width
        except Exception as e:
            logger.error(f"Error getting container width: {e}")
            return 480  # Значение по умолчанию

    def download_captcha_images(self):
        """Скачивает изображения капчи для анализа"""
        try:
            # Получаем элементы изображений
            bg_element = self.driver.find_element(By.ID, "image")
            puzzle_element = self.driver.find_element(By.ID, "puzzle")

            # Получаем URL изображений
            bg_url = bg_element.get_attribute("src")
            puzzle_url = puzzle_element.get_attribute("src")

            logger.info(f"Downloading captcha images...")

            # Скачиваем изображения
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            # Скачиваем фон
            bg_response = requests.get(bg_url, headers=headers, timeout=10)
            bg_image = Image.open(io.BytesIO(bg_response.content))
            bg_np = np.array(bg_image)

            # Скачиваем пазл
            puzzle_response = requests.get(puzzle_url, headers=headers, timeout=10)
            puzzle_image = Image.open(io.BytesIO(puzzle_response.content))
            puzzle_np = np.array(puzzle_image)

            # Конвертируем в RGB если нужно
            if len(bg_np.shape) == 2:
                bg_np = cv2.cvtColor(bg_np, cv2.COLOR_GRAY2RGB)
            if len(puzzle_np.shape) == 2:
                puzzle_np = cv2.cvtColor(puzzle_np, cv2.COLOR_GRAY2RGB)

            logger.info(f"Background: {bg_np.shape}, Puzzle: {puzzle_np.shape}")
            return bg_np, puzzle_np

        except Exception as e:
            logger.error(f"Error downloading images: {e}")
            return None, None

    def calculate_precise_offset(self, bg_image, puzzle_image):
        """Точно вычисляет необходимое смещение слайдера"""
        try:
            # Конвертируем в оттенки серого
            bg_gray = cv2.cvtColor(bg_image, cv2.COLOR_RGB2GRAY)
            puzzle_gray = cv2.cvtColor(puzzle_image, cv2.COLOR_RGB2GRAY)

            # Улучшаем контраст
            bg_gray = cv2.equalizeHist(bg_gray)
            puzzle_gray = cv2.equalizeHist(puzzle_gray)

            # Применяем Gaussian blur для удаления шума
            bg_gray = cv2.GaussianBlur(bg_gray, (3, 3), 0)
            puzzle_gray = cv2.GaussianBlur(puzzle_gray, (3, 3), 0)

            # Используем template matching
            result = cv2.matchTemplate(bg_gray, puzzle_gray, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            target_x = max_loc[0]

            # Получаем текущее положение пазла из DOM
            puzzle_element = self.driver.find_element(By.ID, "puzzle")
            style = puzzle_element.get_attribute("style")

            import re
            left_match = re.search(r'left:\s*(\d+)px', style)
            current_left = int(left_match.group(1)) if left_match else 11

            # Конвертируем в координаты изображения с учетом масштаба
            current_x_image = current_left / self.scale

            # Вычисляем необходимое смещение в пикселях изображения
            offset_px = target_x - current_x_image

            # Вычисляем максимальное возможное смещение пазла
            bg_width = bg_image.shape[1]
            puzzle_width = puzzle_image.shape[1]
            max_puzzle_offset = bg_width - puzzle_width

            if max_puzzle_offset <= 0:
                logger.error("Invalid image dimensions")
                return None

            # Конвертируем смещение в пиксели слайдера
            slider_offset = (offset_px / max_puzzle_offset) * self.container_width

            logger.info(f"Calculation: target_x={target_x}, current_x={current_x_image}, "
                        f"offset_px={offset_px:.1f}, slider_offset={slider_offset:.1f}px")

            return slider_offset

        except Exception as e:
            logger.error(f"Error calculating offset: {e}")
            return None

    def get_slider_element(self):
        """Находит и возвращает элемент слайдера"""
        try:
            # Ждем появления слайдера
            wait = WebDriverWait(self.driver, 10)
            slider = wait.until(
                EC.presence_of_element_located((By.ID, "slider"))
            )
            return slider
        except Exception as e:
            logger.error(f"Error finding slider: {e}")
            return None

    def simulate_single_drag(self, slider, offset):
        """Имитирует одно непрерывное перетаскивание"""
        try:
            actions = ActionChains(self.driver)

            # Начинаем с небольшого движения назад для имитации дрожи
            actions.click_and_hold(slider).pause(random.uniform(0.1, 0.2))
            actions.move_by_offset(-random.uniform(2, 5), random.uniform(-1, 1))
            actions.pause(random.uniform(0.05, 0.1))

            # Разбиваем основное движение на этапы для реалистичности
            total_steps = random.randint(15, 20)
            remaining = offset
            segments = []

            # Генерируем сегменты движения
            for i in range(total_steps):
                if i < total_steps // 3:  # Начало - медленно
                    segment = remaining * random.uniform(0.05, 0.08)
                elif i > total_steps * 2 // 3:  # Конец - медленно
                    segment = remaining * random.uniform(0.06, 0.09)
                else:  # Середина - быстрее
                    segment = remaining * random.uniform(0.09, 0.12)

                segment = max(1, min(segment, remaining))
                segments.append(segment)
                remaining -= segment

                if remaining <= 0:
                    break

            # Выполняем движение по сегментам
            for i, segment in enumerate(segments):
                # Добавляем небольшое вертикальное движение
                vertical_offset = random.uniform(-0.5, 0.5) if i % 3 == 0 else 0

                actions.move_by_offset(
                    segment + random.uniform(-0.5, 0.5),
                    vertical_offset
                )

                # Случайные паузы между движениями
                if i < len(segments) - 1:
                    pause = random.uniform(0.02, 0.06)
                    actions.pause(pause)

            # Небольшое движение назад в конце (имитация дрожи при отпускании)
            actions.move_by_offset(-random.uniform(2, 4), 0)
            actions.pause(random.uniform(0.1, 0.2))

            # Отпускаем
            actions.release()

            # Выполняем все действия одним perform()
            actions.perform()

            logger.info(f"Completed single drag for {offset:.1f}px")
            return True

        except Exception as e:
            logger.error(f"Error in single drag: {e}")
            return False

    def solve_with_intelligent_offsets(self):
        """Интеллектуальное решение с диапазоном смещений"""
        try:
            logger.info("Starting intelligent solution")

            # 1. Получаем параметры
            self.get_scale_factor()
            self.get_container_width()

            # 2. Скачиваем изображения
            bg_image, puzzle_image = self.download_captcha_images()
            if bg_image is None or puzzle_image is None:
                logger.error("Failed to download images")
                return False

            # 3. Вычисляем базовое смещение
            base_offset = self.calculate_precise_offset(bg_image, puzzle_image)
            if base_offset is None:
                logger.error("Failed to calculate base offset")
                return False

            # 4. Генерируем диапазон смещений вокруг базового
            offsets_to_try = []

            # Основное смещение
            offsets_to_try.append(base_offset)

            # Смещения на ±10, ±20 пикселей
            for delta in [-20, -15, -10, -5, 5, 10, 15, 20]:
                offset = base_offset + delta
                if 10 < offset < self.container_width - 50:
                    offsets_to_try.append(offset)

            # Добавляем эвристические смещения (проценты от ширины)
            for percent in [0.7, 0.75, 0.8, 0.85, 0.88, 0.9, 0.92]:
                offset = self.container_width * percent
                offsets_to_try.append(offset)

            # Убираем дубликаты и сортируем
            offsets_to_try = sorted(list(set([int(o) for o in offsets_to_try])))
            logger.info(f"Offsets to try: {offsets_to_try}")

            # 5. Пробуем смещения
            for offset in offsets_to_try:
                logger.info(f"Trying offset: {offset}px")

                # Получаем свежий элемент слайдера для каждой попытки
                slider = self.get_slider_element()
                if not slider:
                    logger.error("Slider not found for new attempt")
                    continue

                # Проверяем, не решилась ли уже капча
                if self.check_success():
                    logger.info("Captcha already solved")
                    return True

                # Перемещаем слайдер
                if self.simulate_single_drag(slider, offset):
                    # Ждем реакции
                    time.sleep(random.uniform(1.5, 2))

                    # Проверяем успех
                    if self.check_success():
                        logger.info(f"Success with offset {offset}px")
                        return True

                    # Если не сработало, ждем немного перед следующей попыткой
                    time.sleep(0.5)

            logger.warning("All offsets failed")
            return False

        except Exception as e:
            logger.error(f"Error in intelligent solution: {e}")
            return False

    def solve_with_rapid_fire(self):
        """Быстрое решение с несколькими попытками на одной странице"""
        try:
            logger.info("Starting rapid fire solution")

            self.get_container_width()

            # Быстрые эвристические смещения
            quick_offsets = [
                int(self.container_width * 0.8),
                int(self.container_width * 0.85),
                int(self.container_width * 0.88),
                int(self.container_width * 0.9),
                int(self.container_width * 0.92),
                int(self.container_width * 0.94)
            ]

            for offset in quick_offsets:
                logger.info(f"Rapid fire trying: {offset}px")

                slider = self.get_slider_element()
                if not slider:
                    continue

                # Быстрое движение
                actions = ActionChains(self.driver)
                actions.click_and_hold(slider)

                # Быстрое перемещение с небольшими паузами
                for i in range(3):
                    segment = offset / 3
                    actions.move_by_offset(segment, random.uniform(-1, 1))
                    actions.pause(0.05)

                actions.release()
                actions.perform()

                time.sleep(1)

                if self.check_success():
                    logger.info(f"Rapid fire success with {offset}px")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error in rapid fire: {e}")
            return False

    def check_success(self):
        """Проверяет, успешно ли решена капча"""
        try:
            # Проверяем несколько индикаторов

            # 1. Проверяем URL
            current_url = self.driver.current_url
            if "antibot" not in current_url.lower() and "__rr" not in current_url:
                logger.info("Success: URL changed")
                return True

            # 2. Проверяем наличие капчи
            try:
                captcha_container = self.driver.find_element(By.ID, "captcha-container")
                if not captcha_container.is_displayed():
                    logger.info("Success: Captcha container hidden")
                    return True
            except:
                logger.info("Success: No captcha container found")
                return True

            # 3. Проверяем текст подсказки
            try:
                hint = self.driver.find_element(By.ID, "hint")
                hint_text = hint.text.lower() if hint.text else ""
                if "доступ" in hint_text or "success" in hint_text:
                    logger.info("Success: Hint text changed")
                    return True
            except:
                pass

            # 4. Проверяем, не перенаправило ли нас
            time.sleep(0.5)  # Даем время для перенаправления
            new_url = self.driver.current_url
            if new_url != current_url and "antibot" not in new_url.lower():
                logger.info("Success: Page redirected")
                return True

            return False

        except Exception as e:
            logger.debug(f"Error in success check: {e}")
            return False

    def solve(self):
        """Основной метод решения"""
        max_attempts = 2

        for attempt in range(1, max_attempts + 1):
            logger.info(f"=== Captcha solving attempt {attempt}/{max_attempts} ===")

            # Пробуем интеллектуальный метод
            if self.solve_with_intelligent_offsets():
                return True

            # Если не сработало, пробуем быстрый метод
            logger.info("Intelligent method failed, trying rapid fire")
            if self.solve_with_rapid_fire():
                return True

            if attempt < max_attempts:
                logger.info(f"Waiting before next attempt...")
                time.sleep(random.uniform(2, 3))

        logger.error(f"Failed to solve captcha after {max_attempts} attempts")
        return False