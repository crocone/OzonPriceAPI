// OZON_Parser.gs
class OZON_OzonParser {
  constructor(sheet) {
    this.sheet = sheet;
    this.sheetService = new OZON_SheetService(sheet);
    this.httpService = new OZON_HttpService(sheet);
    this.dataProcessor = new OZON_DataProcessor();
  }

  parseAllArticles() {
    try {
      const articlesData = this.sheetService.getArticlesFromSheet();
      if (articlesData.length === 0) {
        OZON_showProgressToast('Нет артикулов для обработки');
        return;
      }
      this.processBatchesWithSaving(articlesData, 'всех', OZON_CONFIG.BATCH_SIZE);
    } catch (error) {
      Logger.log(`Ошибка парсинга: ${error.message}`);
      throw error;
    }
  }

  parseSelectedArticles() {
    try {
      const selectedArticlesData = this.sheetService.getSelectedArticlesFromSheet();
      if (selectedArticlesData.length === 0) {
        OZON_showProgressToast('Нет выделенных артикулов для обработки');
        return;
      }
      
      Logger.log(`Найдено ${selectedArticlesData.length} выделенных артикулов для парсинга`);
      
      // Используем меньший размер батча для выделенных артикулов
      this.processBatchesWithSaving(selectedArticlesData, 'выделенных', OZON_CONFIG.SELECTION_BATCH_SIZE);
    } catch (error) {
      Logger.log(`Ошибка парсинга выделенных артикулов: ${error.message}`);
      throw error;
    }
  }

  processBatchesWithSaving(articlesData, type, customBatchSize = null) {
    try {
      const batchSize = customBatchSize || OZON_CONFIG.BATCH_SIZE;
      const batches = this.createBatches(articlesData, batchSize);
      const allResults = [];
      
      Logger.log(`Начинаем обработку ${articlesData.length} ${type} артикулов в ${batches.length} батчах (размер батча: ${batchSize})`);
      
      for (let i = 0; i < batches.length; i++) {
        const batch = batches[i];
        const batchNumber = i + 1;
        const totalBatches = batches.length;
        
        OZON_showProgressToast(`Обрабатываем батч ${batchNumber} из ${totalBatches} (${batch.length} артикулов)...`);
        Logger.log(`Обрабатываем батч ${batchNumber}/${totalBatches} (${batch.length} артикулов)`);
        
        try {
          // Обрабатываем батч
          const batchResults = this.processBatch(batch);
          allResults.push(...batchResults);
          
          // ВАЖНО: Сохраняем результаты батча сразу после обработки
          Logger.log(`🔄 Сохраняем результаты батча ${batchNumber} (${batchResults.length} результатов)...`);
          
          this.sheetService.saveResultsToSheet(batchResults);
          
          // Принудительно сохраняем изменения в Google Sheets
          SpreadsheetApp.flush();
          
          Logger.log(`✅ Батч ${batchNumber} обработан и сохранен (${batchResults.length} результатов)`);
          
          // Показываем прогресс с индикацией сохранения
          const processedCount = allResults.length;
          const totalCount = articlesData.length;
          const progressPercent = Math.round((processedCount / totalCount) * 100);
          
          OZON_showProgressToast(`✅ Батч ${batchNumber}/${totalBatches} сохранен! Прогресс: ${processedCount}/${totalCount} (${progressPercent}%)`);
          
          // Дополнительная пауза после сохранения для стабильности
          if (OZON_CONFIG.SAVE_DELAY > 0) {
            Utilities.sleep(OZON_CONFIG.SAVE_DELAY);
          }
          
          // Пауза между батчами (кроме последнего)
          if (i < batches.length - 1) {
            Logger.log(`Ожидание ${OZON_CONFIG.REQUEST_DELAY}мс перед следующим батчем...`);
            Utilities.sleep(OZON_CONFIG.REQUEST_DELAY);
          }
          
        } catch (error) {
          Logger.log(`❌ Ошибка обработки батча ${batchNumber}: ${error.message}`);
          
          // Создаем результаты с ошибками для текущего батча
          const errorResults = batch.map(item => ({
            rowIndex: item.rowIndex,
            article: String(item.article),
            title: OZON_CONFIG.MESSAGES.ERROR,
            seller: OZON_CONFIG.MESSAGES.ERROR,
            cardPrice: OZON_CONFIG.MESSAGES.ERROR,
            price: OZON_CONFIG.MESSAGES.ERROR,
            originalPrice: OZON_CONFIG.MESSAGES.ERROR,
            isAvailable: false
          }));
          
          // Сохраняем результаты с ошибками
          Logger.log(`🔄 Сохраняем результаты с ошибками для батча ${batchNumber}...`);
          
          this.sheetService.saveResultsToSheet(errorResults);
          allResults.push(...errorResults);
          
          // Принудительно сохраняем изменения
          SpreadsheetApp.flush();
          
          Logger.log(`⚠️ Батч ${batchNumber} обработан с ошибками и сохранен`);
          
          // Дополнительная пауза после сохранения
          if (OZON_CONFIG.SAVE_DELAY > 0) {
            Utilities.sleep(OZON_CONFIG.SAVE_DELAY);
          }
        }
      }
      
      Logger.log(`🎉 Обработка завершена! Всего обработано ${allResults.length} ${type} артикулов`);
      OZON_showProgressToast(`Обработка завершена! ${allResults.length} ${type} артикулов обработано`);
      
    } catch (error) {
      Logger.log(`Критическая ошибка обработки батчей: ${error.message}`);
      throw error;
    }
  }

  processBatch(batch) {
    try {
      const articles = batch.map(item => item.article);
      const apiResponse = this.httpService.fetchOzonData(articles);
      const processedData = this.dataProcessor.processOzonResponse(apiResponse);
      return this.matchResultsWithOriginal(batch, processedData);
    } catch (error) {
      Logger.log(`Ошибка обработки батча: ${error.message}`);
      throw error;
    }
  }

  createBatches(articles, batchSize) {
    const batches = [];
    for (let i = 0; i < articles.length; i += batchSize) batches.push(articles.slice(i, i + batchSize));
    return batches;
  }

  matchResultsWithOriginal(originalBatch, processedData) {
    const results = [];
    const resultsMap = new Map();
    processedData.forEach(item => resultsMap.set(item.article, item));
    console.log(originalBatch , 'originalBatch')
    originalBatch.forEach(originalItem => {
      const result = resultsMap.get(String(originalItem.article));
      results.push({
        rowIndex: originalItem.rowIndex,
        article: String(originalItem.article),
        title: result?.title || OZON_CONFIG.MESSAGES.NO_DATA,
        seller: result?.seller || OZON_CONFIG.MESSAGES.NO_DATA,
        cardPrice: result?.cardPrice || OZON_CONFIG.MESSAGES.NO_PRICE_DATA,
        price: result?.price || OZON_CONFIG.MESSAGES.NO_PRICE_DATA,
        originalPrice: result?.originalPrice || OZON_CONFIG.MESSAGES.NO_PRICE_DATA,
        isAvailable: result?.isAvailable || false
      });
    });
    return results;
  }

  clearResults() {
    this.sheetService.clearResults();
  }
}