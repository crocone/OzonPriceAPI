// OZON_Utils.gs
function OZON_showProgressToast(message) {
  SpreadsheetApp.getActiveSpreadsheet().toast(message, 'Ozon Парсер', 3);
}

function OZON_showErrorToast(message) {
  SpreadsheetApp.getActiveSpreadsheet().toast(message, 'Ошибка', 10);
}

function OZON_showColumnInfo() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const service = new OZON_SheetService(sheet);
  service.showColumnInfo();
}