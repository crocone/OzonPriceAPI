# utils/image_utils.py
import cv2
import numpy as np


def enhance_captcha_image(image):
    """Улучшает изображение капчи для лучшего распознавания"""
    # Конвертируем в оттенки серого
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # Увеличиваем контраст
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Убираем шум
    denoised = cv2.medianBlur(enhanced, 3)

    return denoised


def find_best_match_template(background, template):
    """Находит лучшее совпадение шаблона на изображении"""
    methods = [
        ('TM_CCOEFF_NORMED', cv2.TM_CCOEFF_NORMED),
        ('TM_CCORR_NORMED', cv2.TM_CCORR_NORMED),
        ('TM_SQDIFF_NORMED', cv2.TM_SQDIFF_NORMED)
    ]

    best_score = -1
    best_location = None
    best_method = None

    for method_name, method in methods:
        result = cv2.matchTemplate(background, template, method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            score = 1 - min_val
            location = min_loc
        else:
            score = max_val
            location = max_loc

        if score > best_score:
            best_score = score
            best_location = location
            best_method = method_name

    return best_location, best_score, best_method