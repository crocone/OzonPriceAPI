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
      const batches = this.createBatches(articlesData, OZON_CONFIG.BATCH_SIZE);
      const allResults = [];
      for (let i = 0; i < batches.length; i++) {
        const batch = batches[i];
        OZON_showProgressToast(`Обрабатываем батч ${i + 1} из ${batches.length}...`);
        Logger.log(`Обрабатываем батч ${i + 1}/${batches.length} (${batch.length} артикулов)`);
        try {
          const batchResults = this.processBatch(batch);
          allResults.push(...batchResults);
          this.sheetService.saveResultsToSheet(batchResults);
          if (i < batches.length - 1) {
            Logger.log(`Ожидание ${OZON_CONFIG.REQUEST_DELAY}мс...`);
            Utilities.sleep(OZON_CONFIG.REQUEST_DELAY);
          }
        } catch (error) {
          Logger.log(`Ошибка обработки батча ${i + 1}: ${error.message}`);
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
          this.sheetService.saveResultsToSheet(errorResults);
          allResults.push(...errorResults);
        }
      }
      Logger.log(`Обработано ${allResults.length} артикулов`);
    } catch (error) {
      Logger.log(`Ошибка парсинга: ${error.message}`);
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