# utils/ozon_captcha_solver.py
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


class OzonCaptchaSolverV2:
    """Продвинутый решатель капчи Ozon с точным вычислением смещения"""

    def __init__(self, driver):
        self.driver = driver
        self.scale = 1.0

    def get_scale_factor(self):
        """Получает масштаб из стиля капчи"""
        try:
            captcha_element = self.driver.find_element(By.ID, "captcha")
            style = captcha_element.get_attribute("style")

            # Ищем --scale в стиле
            import re
            scale_match = re.search(r'--scale:\s*([\d.]+)', style)
            if scale_match:
                self.scale = float(scale_match.group(1))
                logger.info(f"Found scale factor: {self.scale}")
            else:
                # Пытаемся вычислить по размерам изображения
                bg_img = self.driver.find_element(By.ID, "image")
                natural_width = bg_img.get_attribute("naturalWidth")
                client_width = bg_img.size['width']
                if natural_width and client_width:
                    self.scale = float(client_width) / float(natural_width)
                    logger.info(f"Computed scale factor: {self.scale}")

        except Exception as e:
            logger.warning(f"Could not determine scale factor: {e}")
            self.scale = 1.28  # Значение по умолчанию для Ozon

        return self.scale

    def download_captcha_images(self):
        """Скачивает изображения капчи для анализа"""
        try:
            # Получаем элементы изображений
            bg_element = self.driver.find_element(By.ID, "image")
            puzzle_element = self.driver.find_element(By.ID, "puzzle")

            # Получаем URL изображений
            bg_url = bg_element.get_attribute("src")
            puzzle_url = puzzle_element.get_attribute("src")

            logger.info(f"Background URL: {bg_url[:100]}...")
            logger.info(f"Puzzle URL: {puzzle_url[:100]}...")

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

            logger.info(f"Background shape: {bg_np.shape}")
            logger.info(f"Puzzle shape: {puzzle_np.shape}")

            return bg_np, puzzle_np

        except Exception as e:
            logger.error(f"Error downloading captcha images: {e}")

            # Fallback: делаем скриншот и пытаемся вырезать изображения
            try:
                return self.extract_images_from_screenshot()
            except Exception as e2:
                logger.error(f"Failed to extract from screenshot: {e2}")
                return None, None

    def extract_images_from_screenshot(self):
        """Извлекает изображения капчи из скриншота"""
        try:
            # Делаем скриншот всей страницы
            screenshot = self.driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(screenshot))
            img_np = np.array(img)

            # Находим координаты капчи на странице
            captcha_element = self.driver.find_element(By.ID, "captcha-container")
            location = captcha_element.location
            size = captcha_element.size

            # Вырезаем область капчи
            x, y = int(location['x']), int(location['y'])
            w, h = int(size['width']), int(size['height'])

            captcha_area = img_np[y:y + h, x:x + w]

            # Пытаемся найти изображения внутри области капчи
            # Это сложная задача, требующая анализа DOM и CSS

            logger.warning("Using screenshot extraction - less accurate")
            return captcha_area, captcha_area  # Заглушка

        except Exception as e:
            logger.error(f"Failed to extract images: {e}")
            return None, None

    def calculate_precise_offset(self, bg_image, puzzle_image):
        """Точно вычисляет необходимое смещение слайдера"""
        try:
            # Конвертируем в оттенки серого
            bg_gray = cv2.cvtColor(bg_image, cv2.COLOR_RGB2GRAY)
            puzzle_gray = cv2.cvtColor(puzzle_image, cv2.COLOR_RGB2GRAY)

            # Улучшаем контраст для лучшего распознавания
            bg_gray = cv2.equalizeHist(bg_gray)
            puzzle_gray = cv2.equalizeHist(puzzle_gray)

            # Применяем Gaussian blur для удаления шума
            bg_gray = cv2.GaussianBlur(bg_gray, (3, 3), 0)
            puzzle_gray = cv2.GaussianBlur(puzzle_gray, (3, 3), 0)

            # Используем template matching с несколькими методами
            methods = [cv2.TM_CCOEFF_NORMED, cv2.TM_CCORR_NORMED, cv2.TM_SQDIFF_NORMED]
            best_match = None
            best_score = -1

            for method in methods:
                result = cv2.matchTemplate(bg_gray, puzzle_gray, method)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                    score = 1 - min_val
                    location = min_loc
                else:
                    score = max_val
                    location = max_loc

                if score > best_score:
                    best_score = score
                    best_match = location

            if best_match:
                target_x = best_match[0]

                # Получаем текущее положение пазла из DOM
                puzzle_element = self.driver.find_element(By.ID, "puzzle")
                style = puzzle_element.get_attribute("style")

                # Извлекаем left из стиля
                import re
                left_match = re.search(r'left:\s*(\d+)px', style)
                current_left = int(left_match.group(1)) if left_match else 11

                # Конвертируем в координаты изображения с учетом масштаба
                current_x_image = current_left / self.scale

                # Вычисляем необходимое смещение
                offset_px = target_x - current_x_image

                # Конвертируем смещение в пиксели слайдера
                slider_container = self.driver.find_element(By.ID, "slider-container")
                container_width = slider_container.size['width']

                # Вычисляем максимальное возможное смещение пазла
                bg_width = bg_image.shape[1]
                puzzle_width = puzzle_image.shape[1]
                max_puzzle_offset = bg_width - puzzle_width

                # Линейное преобразование
                slider_offset = (offset_px / max_puzzle_offset) * container_width

                logger.info(f"Precise calculation: target_x={target_x}, "
                            f"current_x={current_x_image}, offset_px={offset_px:.1f}, "
                            f"slider_offset={slider_offset:.1f}px")

                return int(slider_offset)

            return None

        except Exception as e:
            logger.error(f"Error in precise offset calculation: {e}")
            return None

    def get_puzzle_initial_position(self):
        """Получает начальное положение пазла"""
        try:
            puzzle_element = self.driver.find_element(By.ID, "puzzle")
            style = puzzle_element.get_attribute("style")

            import re
            left_match = re.search(r'left:\s*(\d+)px', style)
            top_match = re.search(r'top:\s*(\d+)px', style)

            left = int(left_match.group(1)) if left_match else 11
            top = int(top_match.group(1)) if top_match else 83

            return left, top

        except Exception as e:
            logger.error(f"Error getting puzzle position: {e}")
            return 11, 83

    def simulate_human_slide(self, slider, offset):
        """Имитирует человеческое движение слайдера"""
        try:
            actions = ActionChains(self.driver)

            # Нажимаем на слайдер
            actions.click_and_hold(slider).pause(random.uniform(0.1, 0.3))

            # Разбиваем движение на части
            total_steps = random.randint(8, 12)
            remaining = offset

            # Немного сдвигаем назад для имитации дрожи
            actions.move_by_offset(-random.uniform(2, 5), 0)
            actions.pause(random.uniform(0.05, 0.1))

            # Основное движение
            for i in range(total_steps):
                if remaining <= 0:
                    break

                # Нелинейное движение
                if i < 3:  # Начало - медленно
                    step = remaining * 0.1 + random.uniform(-1, 1)
                elif i > total_steps - 3:  # Конец - медленно
                    step = remaining * 0.15 + random.uniform(-0.5, 0.5)
                else:  # Середина - быстрее
                    step = remaining / (total_steps - i) * random.uniform(0.8, 1.2)

                step = max(1, min(step, remaining))

                # Добавляем небольшое вертикальное движение
                actions.move_by_offset(step, random.uniform(-0.3, 0.3))
                actions.pause(random.uniform(0.02, 0.08))

                remaining -= step

            # Небольшое движение назад (как при отпускании)
            actions.move_by_offset(-random.uniform(3, 8), 0)
            actions.pause(random.uniform(0.1, 0.2))

            # Отпускаем
            actions.release()
            actions.perform()

            logger.info(f"Simulated human slide for {offset}px")
            return True

        except Exception as e:
            logger.error(f"Error simulating slide: {e}")
            return False

    def solve_with_precision(self):
        """Решает капчу с точным вычислением"""
        try:
            logger.info("Starting precision solution for Ozon captcha")

            # 1. Получаем масштаб
            self.get_scale_factor()

            # 2. Скачиваем изображения
            bg_image, puzzle_image = self.download_captcha_images()
            if bg_image is None or puzzle_image is None:
                logger.error("Failed to get captcha images")
                return False

            # 3. Вычисляем точное смещение
            slider_offset = self.calculate_precise_offset(bg_image, puzzle_image)
            if slider_offset is None:
                logger.error("Failed to calculate offset")
                return False

            # 4. Находим слайдер
            slider = self.driver.find_element(By.ID, "slider")
            if not slider:
                logger.error("Slider not found")
                return False

            # 5. Добавляем небольшую поправку (обычно нужно немного не довезти)
            adjustment = random.uniform(-5, 5)
            final_offset = max(10, slider_offset + adjustment)

            logger.info(f"Final slider offset: {final_offset:.1f}px")

            # 6. Перемещаем слайдер
            self.simulate_human_slide(slider, final_offset)

            # 7. Ждем результата
            time.sleep(random.uniform(1.5, 2.5))

            # 8. Проверяем успешность
            return self.check_success()

        except Exception as e:
            logger.error(f"Error in precision solution: {e}")
            return False

    def solve_with_heuristic(self):
        """Эвристическое решение (fallback)"""
        try:
            logger.info("Using heuristic method")

            # Находим слайдер
            slider = self.driver.find_element(By.ID, "slider")
            if not slider:
                return False

            # Получаем размеры контейнера слайдера
            container = self.driver.find_element(By.ID, "slider-container")
            container_width = container.size['width']

            # Ozon обычно требует ~80-90% от ширины контейнера
            test_offsets = [
                int(container_width * 0.75),
                int(container_width * 0.80),
                int(container_width * 0.85),
                int(container_width * 0.88),
                int(container_width * 0.90),
                int(container_width * 0.92)
            ]

            for offset in test_offsets:
                logger.info(f"Trying heuristic offset: {offset}px")

                self.simulate_human_slide(slider, offset)
                time.sleep(2)

                if self.check_success():
                    logger.info(f"Success with heuristic offset {offset}px")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error in heuristic method: {e}")
            return False

    def check_success(self):
        """Проверяет, успешно ли решена капча"""
        try:
            # Проверяем, исчезли ли элементы капчи
            captcha_elements = self.driver.find_elements(By.ID, "captcha-container")
            if not captcha_elements:
                return True

            # Проверяем, изменился ли текст
            hint_element = self.driver.find_element(By.ID, "hint")
            hint_text = hint_element.text.lower() if hint_element else ""

            if "доступ" in hint_text or "доступно" in hint_text:
                return True

            # Проверяем URL
            current_url = self.driver.current_url
            if "antibot" not in current_url and "__rr" not in current_url:
                return True

            return False

        except Exception as e:
            logger.debug(f"Error checking success: {e}")
            return False

    def solve(self):
        """Основной метод решения"""
        try:
            # Сначала пробуем точный метод
            if self.solve_with_precision():
                logger.info("Captcha solved with precision method")
                return True

            logger.warning("Precision method failed, trying heuristic")

            # Если не получилось, пробуем эвристический
            if self.solve_with_heuristic():
                logger.info("Captcha solved with heuristic method")
                return True

            logger.error("All methods failed")
            return False

        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            return False