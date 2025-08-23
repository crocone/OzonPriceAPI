// OZON_HttpService.gs
class OZON_HttpService {
  constructor(sheet) {
    this.sheet = sheet;
    this.apiUrl = this.getApiUrl();
  }

  getApiUrl() {
    try {
      // Получаем URL из ячейки B1
      const apiUrlCell = this.sheet.getRange(OZON_CONFIG.API_URL_CELL);
      const cellValue = apiUrlCell.getValue();

      if (cellValue && typeof cellValue === "string" && cellValue.trim()) {
        let url = cellValue.trim();

        // Проверяем базовый формат URL
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
          Logger.log(
            `Неверный формат URL в ячейке ${OZON_CONFIG.API_URL_CELL}: ${url}`
          );
          throw new Error(
            `${OZON_CONFIG.MESSAGES.INVALID_API_URL}: ${url}\n\nURL должен начинаться с http:// или https://\nПример: https://abc123.ngrok-free.app`
          );
        }

        // Автоматически добавляем endpoint если его нет
        if (!url.includes("/api/v1/get_price")) {
          if (url.endsWith("/")) {
            url = url + "api/v1/get_price";
          } else {
            url = url + "/api/v1/get_price";
          }

          // Обновляем ячейку с полным URL
          apiUrlCell.setValue(url);
          Logger.log(
            `Автоматически добавлен endpoint. Обновленный URL: ${url}`
          );
        }

        Logger.log(
          `Используем API URL из ячейки ${OZON_CONFIG.API_URL_CELL}: ${url}`
        );
        return url;
      } else {
        // Ячейка пустая - ОШИБКА!
        Logger.log(`API URL не найден в ячейке ${OZON_CONFIG.API_URL_CELL}`);
        apiUrlCell.setNote(
          "ОБЯЗАТЕЛЬНО! Введите здесь ваш ngrok URL (например: https://abc123.ngrok.io)"
        );
        throw new Error(
          `${OZON_CONFIG.MESSAGES.API_URL_NOT_SET}. Введите URL в ячейку ${OZON_CONFIG.API_URL_CELL}`
        );
      }
    } catch (error) {
      Logger.log(`Ошибка получения API URL: ${error.message}`);
      throw error;
    }
  }

  isValidApiUrl(url) {
    try {
      // Проверяем что URL не пустой
      if (!url || typeof url !== "string" || !url.trim()) {
        return false;
      }

      url = url.trim();

      // Проверяем базовый формат URL
      if (!url.startsWith("http://") && !url.startsWith("https://")) {
        return false;
      }

      // Проверяем минимальную длину
      if (url.length < 10) {
        return false;
      }

      // Базовая проверка структуры URL
      try {
        new URL(url);
        return true;
      } catch (e) {
        Logger.log(`URL validation failed: ${e.message}`);
        return false;
      }
    } catch (error) {
      Logger.log(`isValidApiUrl error: ${error.message}`);
      return false;
    }
  }

  fetchOzonData(articles) {
    try {
      Logger.log(`Запрос к Ozon API: ${this.apiUrl}`);
      Logger.log(`Артикулов для обработки: ${articles.length}`);

      const options = {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true", // Для обхода предупреждения ngrok
        },
        payload: JSON.stringify({ articles }),
        muteHttpExceptions: true,
      };

      const response = UrlFetchApp.fetch(this.apiUrl, options);
      const responseCode = response.getResponseCode();
      const responseText = response.getContentText();

      Logger.log(`Ответ сервера: ${responseCode}`);

      if (responseCode !== 200) {
        throw new Error(`HTTP Error: ${responseCode} - ${responseText}`);
      }

      const data = JSON.parse(responseText);
      Logger.log(
        `Получен ответ: success=${data.success}, parsed=${data.parsed_articles}/${data.total_articles}`
      );

      return data;
    } catch (error) {
      Logger.log(`Ошибка HTTP запроса: ${error.message}`);
      throw error;
    }
  }

  testConnection(testArticles = [2360879218]) {
    try {
      Logger.log(`Тестирование подключения к API: ${this.apiUrl}`);
      const response = this.fetchOzonData(testArticles);
      Logger.log("Тест подключения успешен");
      return { success: true, data: response };
    } catch (error) {
      Logger.log(`Тест подключения неудачен: ${error.message}`);
      return { success: false, error: error.message };
    }
  }

  updateApiUrl(newUrl) {
    try {
      if (!this.isValidApiUrl(newUrl)) {
        throw new Error(`${OZON_CONFIG.MESSAGES.INVALID_API_URL}: ${newUrl}`);
      }

      // Автоматически добавляем endpoint если его нет
      let finalUrl = newUrl;
      if (!newUrl.includes("/api/v1/get_price")) {
        if (newUrl.endsWith("/")) {
          finalUrl = newUrl + "api/v1/get_price";
        } else {
          finalUrl = newUrl + "/api/v1/get_price";
        }
      }

      const apiUrlCell = this.sheet.getRange(OZON_CONFIG.API_URL_CELL);
      apiUrlCell.setValue(finalUrl);
      this.apiUrl = finalUrl;

      Logger.log(`API URL обновлен: ${finalUrl}`);
      return true;
    } catch (error) {
      Logger.log(`Ошибка обновления API URL: ${error.message}`);
      throw error;
    }
  }
}
