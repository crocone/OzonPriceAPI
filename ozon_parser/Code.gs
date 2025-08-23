// OZON_Code.gs
function OZON_addMenu() {
  SpreadsheetApp.getUi()
    .createMenu('🟣 OZON Парсер')
    .addItem('Парсить все артикулы', 'OZON_parseArticles')
    .addItem('Парсить выделенные артикулы', 'OZON_parseSelectedArticles')
    .addItem('Очистить результаты', 'OZON_clearResults')
    .addItem('Показать информацию о колонках', 'OZON_showColumnInfo')
    .addToUi();
}

function OZON_parseArticles() {
  try {
    Logger.log('=== НАЧАЛО ПАРСИНГА ВСЕХ АРТИКУЛОВ OZON ===');
    const sheet = SpreadsheetApp.getActiveSheet();
    const parser = new OZON_OzonParser(sheet);
    OZON_showProgressToast('Начинаем парсинг всех артикулов...');
    parser.parseAllArticles();
    Logger.log('=== ПАРСИНГ ЗАВЕРШЕН ===');
    OZON_showProgressToast('Парсинг завершен успешно!');
  } catch (error) {
    Logger.log(`Критическая ошибка: ${error.message}`);
    OZON_showErrorToast(`Ошибка: ${error.message}`);
  }
}

function OZON_parseSelectedArticles() {
  try {
    Logger.log('=== НАЧАЛО ПАРСИНГА ВЫДЕЛЕННЫХ АРТИКУЛОВ OZON ===');
    const sheet = SpreadsheetApp.getActiveSheet();
    const parser = new OZON_OzonParser(sheet);
    OZON_showProgressToast('Начинаем парсинг выделенных артикулов...');
    parser.parseSelectedArticles();
    Logger.log('=== ПАРСИНГ ВЫДЕЛЕННЫХ АРТИКУЛОВ ЗАВЕРШЕН ===');
    OZON_showProgressToast('Парсинг выделенных артикулов завершен успешно!');
  } catch (error) {
    Logger.log(`Критическая ошибка: ${error.message}`);
    OZON_showErrorToast(`Ошибка: ${error.message}`);
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
