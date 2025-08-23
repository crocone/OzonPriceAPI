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

  getSelectedArticlesFromSheet() {
    try {
      this.validateColumns();
      
      // Получаем выделенный диапазон
      const selection = this.sheet.getSelection();
      const activeRange = selection.getActiveRange();
      
      if (!activeRange) {
        throw new Error('Нет выделенного диапазона. Выделите ячейки с артикулами для парсинга.');
      }
      
      const articleCol = this.getColumnNumber('ARTICLE');
      const articles = [];
      
      // Получаем все выделенные диапазоны
      const ranges = selection.getActiveRangeList() ? selection.getActiveRangeList().getRanges() : [activeRange];
      
      Logger.log(`Найдено ${ranges.length} выделенных диапазонов`);
      
      ranges.forEach((range, rangeIndex) => {
        const startRow = range.getRow();
        const endRow = range.getLastRow();
        const startCol = range.getColumn();
        const endCol = range.getLastColumn();
        
        Logger.log(`Диапазон ${rangeIndex + 1}: строки ${startRow}-${endRow}, колонки ${startCol}-${endCol}`);
        
        // Проверяем, пересекается ли выделение с колонкой артикулов
        if (startCol <= articleCol && endCol >= articleCol) {
          // Выделение включает колонку артикулов
          for (let row = Math.max(startRow, OZON_CONFIG.DATA_START_ROW); row <= endRow; row++) {
            try {
              const cellValue = this.sheet.getRange(row, articleCol).getValue();
              const article = String(cellValue).trim();
              
              if (article && /^\d{3,15}$/.test(article)) {
                articles.push({ 
                  article: parseInt(article), 
                  rowIndex: row 
                });
                Logger.log(`Добавлен артикул: ${article} из строки ${row}`);
              } else if (article) {
                Logger.log(`Невалидный артикул в строке ${row}: ${article}`);
              }
            } catch (error) {
              Logger.log(`Ошибка чтения ячейки в строке ${row}: ${error.message}`);
            }
          }
        }
      });
      
      // Удаляем дубликаты и сортируем по rowIndex
      const uniqueArticles = [];
      const seenArticles = new Set();
      
      articles.forEach(item => {
        const key = `${item.article}_${item.rowIndex}`;
        if (!seenArticles.has(key)) {
          seenArticles.add(key);
          uniqueArticles.push(item);
        }
      });
      
      uniqueArticles.sort((a, b) => a.rowIndex - b.rowIndex);
      
      Logger.log(`Найдено ${uniqueArticles.length} уникальных выделенных артикулов`);
      
      if (uniqueArticles.length === 0) {
        throw new Error('В выделенном диапазоне не найдено валидных артикулов. Убедитесь, что выделили ячейки с артикулами (числа от 3 до 15 цифр).');
      }
      
      return uniqueArticles;
      
    } catch (error) {
      Logger.log(`Ошибка получения выделенных артикулов: ${error.message}`);
      throw error;
    }
  }

  saveResultsToSheet(results) {
    try {
      if (results.length === 0) {
        Logger.log('Нет результатов для сохранения');
        return;
      }
      
      Logger.log(`Начинаем сохранение ${results.length} результатов`);
      
      // Сортируем результаты по индексу строки
      results.sort((a, b) => a.rowIndex - b.rowIndex);
      
      const keyMap = {
        TITLE: 'title',
        SELLER: 'seller', 
        CARD_PRICE: 'cardPrice',
        PRICE: 'price',
        ORIGINAL_PRICE: 'originalPrice',
        AVAILABLE: 'isAvailable'
      };

      // Обрабатываем каждый тип колонки отдельно
      Object.keys(keyMap).forEach(columnType => {
        try {
          if (!this.columnMapping[columnType]) {
            Logger.log(`Колонка ${columnType} не найдена, пропускаем`);
            return;
          }
          
          const col = this.getColumnNumber(columnType);
          const key = keyMap[columnType];
          
          Logger.log(`Сохраняем данные в колонку ${columnType} (${col})`);
          
          // Подготавливаем значения для записи
          let values;
          if (columnType === 'AVAILABLE') {
            // Для доступности преобразуем boolean в текст
            values = results.map(result => [result[key] ? 'Да' : 'Нет']);
          } else {
            // Для остальных колонок используем значения как есть
            values = results.map(result => [result[key] ?? '']);
          }
          
          // Записываем данные по строкам (для надежности)
          results.forEach((result, index) => {
            try {
              const range = this.sheet.getRange(result.rowIndex, col, 1, 1);
              range.setValue(values[index][0]);
              
              // Применяем форматирование для цен
              if (['CARD_PRICE', 'PRICE', 'ORIGINAL_PRICE'].includes(columnType)) {
                if (typeof values[index][0] === 'number' && values[index][0] > 0) {
                  range.setNumberFormat('#,##0" ₽"');
                }
              }
            } catch (cellError) {
              Logger.log(`Ошибка записи в ячейку ${result.rowIndex}:${col}: ${cellError.message}`);
            }
          });
          
          Logger.log(`✅ Колонка ${columnType} сохранена успешно`);
          
        } catch (columnError) {
          Logger.log(`❌ Ошибка сохранения колонки ${columnType}: ${columnError.message}`);
        }
      });

      // Принудительно сохраняем изменения
      if (OZON_CONFIG.FORCE_FLUSH) {
        SpreadsheetApp.flush();
      }
      
      Logger.log(`✅ Успешно сохранено ${results.length} результатов в таблицу`);
      
    } catch (error) {
      Logger.log(`❌ Критическая ошибка сохранения результатов: ${error.message}`);
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