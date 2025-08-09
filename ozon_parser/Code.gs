// OZON_Code.gs
function OZON_addMenu() {
  SpreadsheetApp.getUi()
    .createMenu('🟣 OZON Парсер')
    .addItem('Парсить артикулы', 'OZON_parseArticles')
    .addSeparator()
    .addItem('Настроить API URL', 'OZON_setupApiUrl')
    .addItem('Тест подключения', 'OZON_testConnection')
    .addSeparator()
    .addItem('Очистить результаты', 'OZON_clearResults')
    .addItem('Показать информацию о колонках', 'OZON_showColumnInfo')
    .addToUi();
}

function OZON_parseArticles() {
  try {
    Logger.log('=== НАЧАЛО ПАРСИНГА АРТИКУЛОВ OZON ===');
    const sheet = SpreadsheetApp.getActiveSheet();
    const parser = new OZON_OzonParser(sheet);
    OZON_showProgressToast('Начинаем парсинг артикулов...');
    parser.parseAllArticles();
    Logger.log('=== ПАРСИНГ ЗАВЕРШЕН ===');
    OZON_showProgressToast('Парсинг завершен успешно!');
  } catch (error) {
    Logger.log(`Критическая ошибка: ${error.message}`);
    OZON_showErrorToast(`Ошибка: ${error.message}`);
  }
}

function OZON_setupApiUrl() {
  try {
    const ui = SpreadsheetApp.getUi();
    const sheet = SpreadsheetApp.getActiveSheet();
    
    // Получаем текущий URL из ячейки B1
    const apiUrlCell = sheet.getRange(OZON_CONFIG.API_URL_CELL);
    const currentUrl = apiUrlCell.getValue() || '[НЕ НАСТРОЕН]';
    
    const result = ui.prompt(
      'Настройка API URL',
      `Текущий API URL: ${currentUrl}\n\nВведите ваш ngrok URL (например: https://abc123.ngrok.io/api/v1/get_price):`,
      ui.ButtonSet.OK_CANCEL
    );
    
    if (result.getSelectedButton() === ui.Button.OK) {
      const newUrl = result.getResponseText().trim();
      
      if (!newUrl) {
        OZON_showErrorToast('URL не может быть пустым');
        return;
      }
      
      // Автоматически добавляем endpoint если его нет
      let finalUrl = newUrl;
      if (!newUrl.includes('/api/v1/get_price')) {
        if (newUrl.endsWith('/')) {
          finalUrl = newUrl + 'api/v1/get_price';
        } else {
          finalUrl = newUrl + '/api/v1/get_price';
        }
      }
      
      // Обновляем URL напрямую в ячейке
      apiUrlCell.setValue(finalUrl);
      OZON_showProgressToast(`API URL обновлен: ${finalUrl}`);
      
      // Предлагаем протестировать подключение
      const testResult = ui.alert(
        'URL обновлен',
        'API URL успешно обновлен. Хотите протестировать подключение?',
        ui.ButtonSet.YES_NO
      );
      
      if (testResult === ui.Button.YES) {
        OZON_testConnection();
      }
    }
  } catch (error) {
    Logger.log(`Ошибка настройки API URL: ${error.message}`);
    OZON_showErrorToast(`Ошибка настройки: ${error.message}`);
  }
}

function OZON_testConnection() {
  try {
    const sheet = SpreadsheetApp.getActiveSheet();
    const httpService = new OZON_HttpService(sheet);
    
    OZON_showProgressToast('Тестируем подключение к API...');
    
    const testResult = httpService.testConnection([2360879218]);
    
    if (testResult.success) {
      const data = testResult.data;
      const message = `✅ Подключение успешно!\n\nAPI URL: ${httpService.apiUrl}\nОбработано артикулов: ${data.parsed_articles}/${data.total_articles}\nСтатус: ${data.success ? 'Успех' : 'Ошибка'}`;
      
      SpreadsheetApp.getUi().alert('Тест подключения', message, SpreadsheetApp.getUi().ButtonSet.OK);
      OZON_showProgressToast('Подключение к API работает!');
    } else {
      const message = `❌ Ошибка подключения!\n\nAPI URL: ${httpService.apiUrl}\nОшибка: ${testResult.error}`;
      
      SpreadsheetApp.getUi().alert('Тест подключения', message, SpreadsheetApp.getUi().ButtonSet.OK);
      OZON_showErrorToast('Ошибка подключения к API');
    }
  } catch (error) {
    Logger.log(`Ошибка тестирования: ${error.message}`);
    OZON_showErrorToast(`Ошибка тестирования: ${error.message}`);
  }
}

function OZON_clearResults() {
  try {
    const sheet = SpreadsheetApp.getActiveSheet();
    // Создаем только SheetService для очистки, без HTTP сервиса
    const sheetService = new OZON_SheetService(sheet);
    sheetService.clearResults();
    OZON_showProgressToast('Результаты очищены');
  } catch (error) {
    Logger.log(`Ошибка очистки: ${error.message}`);
    OZON_showErrorToast(`Ошибка очистки: ${error.message}`);
  }
}

function OZON_showColumnInfo() {
  try {
    const sheet = SpreadsheetApp.getActiveSheet();
    const sheetService = new OZON_SheetService(sheet);
    sheetService.showColumnInfo();
  } catch (error) {
    Logger.log(`Ошибка показа информации о колонках: ${error.message}`);
    OZON_showErrorToast(`Ошибка: ${error.message}`);
  }
}