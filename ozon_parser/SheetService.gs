// OZON_SheetService.gs
class OZON_SheetService {
  constructor(sheet) {
    this.sheet = sheet;
    this.columnMapping = this.detectColumns();
  }

  detectColumns() {
    try {
      const headerRange = this.sheet.getRange(OZON_CONFIG.HEADER_ROW, 1, 1, this.sheet.getLastColumn());
      const headers = headerRange.getValues()[0];
      const mapping = {};
      headers.forEach((header, index) => {
        if (!header) return;
        const headerText = String(header).toLowerCase().trim();
        Object.keys(OZON_CONFIG.COLUMN_KEYWORDS).forEach(columnType => {
          const keywords = OZON_CONFIG.COLUMN_KEYWORDS[columnType];
          if (keywords.some(keyword => headerText.includes(keyword.toLowerCase()))) {
            mapping[columnType] = index + 1;
          }
        });
      });
      Logger.log('OZON detected columns:');
      Logger.log(JSON.stringify(mapping, null, 2));
      return mapping;
    } catch (error) {
      Logger.log(`Ошибка определения колонок: ${error.message}`);
      throw error;
    }
  }

  getColumnNumber(columnType) {
    if (!this.columnMapping[columnType]) {
      throw new Error(`${OZON_CONFIG.MESSAGES.COLUMN_NOT_FOUND}: ${columnType}`);
    }
    return this.columnMapping[columnType];
  }

  validateColumns() {
    const requiredColumns = ['ARTICLE'];
    const missingColumns = [];
    requiredColumns.forEach(columnType => {
      if (!this.columnMapping[columnType]) missingColumns.push(columnType);
    });
    if (missingColumns.length > 0) throw new Error(`Отсутствуют необходимые колонки: ${missingColumns.join(', ')}`);
    return true;
  }

  getArticlesFromSheet() {
    try {
      this.validateColumns();
      const lastRow = this.sheet.getLastRow();
      if (lastRow < OZON_CONFIG.DATA_START_ROW) return [];
      const articleCol = this.getColumnNumber('ARTICLE');
      const range = this.sheet.getRange(OZON_CONFIG.DATA_START_ROW, articleCol, lastRow - OZON_CONFIG.DATA_START_ROW + 1, 1);
      const values = range.getValues();
      const articles = [];
      values.forEach((row, index) => {
        const article = String(row[0]).trim();
        if (article && /^\d{3,15}$/.test(article)) {
          articles.push({ article: parseInt(article), rowIndex: OZON_CONFIG.DATA_START_ROW + index });
        } else { Logger.log(`Невалидный артикул в строке ${OZON_CONFIG.DATA_START_ROW + index}: ${article}`); }
      });
      return articles;
    } catch (error) {
      Logger.log(`Ошибка получения артикулов: ${error.message}`);
      throw error;
    }
  }

  saveResultsToSheet(results) {
    try {
      if (results.length === 0) return;
      results.sort((a, b) => a.rowIndex - b.rowIndex);
      const startRow = results[0].rowIndex;
      const numRows = results.length;

      const keyMap = {
        TITLE: 'title',
        SELLER: 'seller',
        CARD_PRICE: 'cardPrice',
        PRICE: 'price',
        ORIGINAL_PRICE: 'originalPrice',
        AVAILABLE: 'isAvailable'
      };

      Object.keys(keyMap).forEach(columnType => {
        if (!this.columnMapping[columnType]) return;
        const col = this.getColumnNumber(columnType);
        const range = this.sheet.getRange(startRow, col, numRows, 1);
        const key = keyMap[columnType];
        const values = results.map(result => [result[key] ?? '']);
        range.setValues(values);

        if (['CARD_PRICE', 'PRICE', 'ORIGINAL_PRICE'].includes(columnType)) {
          range.setNumberFormat('#,##0" ₽"');
        }
        if (columnType === 'AVAILABLE') {
          range.setValues(results.map(result => [result[key] ? 'Да' : 'Нет']));
        }
      });

      Logger.log(`Сохранено ${results.length} результатов`);
    } catch (error) {
      Logger.log(`Ошибка сохранения результатов: ${error.message}`);
      throw error;
    }
  }

  clearResults() {
    try {
      const lastRow = this.sheet.getLastRow();
      if (lastRow < OZON_CONFIG.DATA_START_ROW) return;
      const numRows = lastRow - OZON_CONFIG.DATA_START_ROW + 1;
      ['TITLE', 'SELLER', 'CARD_PRICE', 'PRICE', 'ORIGINAL_PRICE', 'AVAILABLE'].forEach(columnType => {
        if (this.columnMapping[columnType]) {
          this.sheet.getRange(OZON_CONFIG.DATA_START_ROW, this.getColumnNumber(columnType), numRows, 1).clearContent();
        }
      });
      Logger.log('Результаты очищены');
    } catch (error) {
      Logger.log(`Ошибка очистки результатов: ${error.message}`);
      throw error;
    }
  }

  showColumnInfo() {
    let message = 'Найденные колонки:\n';
    Object.keys(this.columnMapping).forEach(columnType => {
      const columnNumber = this.columnMapping[columnType];
      const columnLetter = this.numberToColumn(columnNumber);
      message += `${columnType}: ${columnLetter}${columnNumber}\n`;
    });
    const allTypes = Object.keys(OZON_CONFIG.COLUMN_KEYWORDS);
    const missingTypes = allTypes.filter(type => !this.columnMapping[type]);
    if (missingTypes.length > 0) {
      message += '\nОтсутствующие колонки:\n';
      missingTypes.forEach(type => {
        const keywords = OZON_CONFIG.COLUMN_KEYWORDS[type].join(', ');
        message += `${type} (ключевые слова: ${keywords})\n`;
      });
    }
    Logger.log(message);
    SpreadsheetApp.getActiveSpreadsheet().toast(message, 'Информация о колонках', 10);
  }

  numberToColumn(num) {
    let result = '';
    while (num > 0) {
      num--;
      result = String.fromCharCode(65 + (num % 26)) + result;
      num = Math.floor(num / 26);
    }
    return result || 'A';
  }
}