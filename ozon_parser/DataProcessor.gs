// OZON_DataProcessor.gs
class OZON_DataProcessor {
  processOzonResponse(apiResponse) {
    const results = [];
    apiResponse.results.forEach(result => {
      try {
        const processedProduct = this.processProduct(result);
        results.push(processedProduct);
      } catch (error) {
        Logger.log(`Ошибка обработки продукта ${result.article}: ${error.message}`);
        results.push({
          article: String(result.article),
          title: OZON_CONFIG.MESSAGES.ERROR,
          cardPrice: OZON_CONFIG.MESSAGES.ERROR,
          price: OZON_CONFIG.MESSAGES.ERROR,
          originalPrice: OZON_CONFIG.MESSAGES.ERROR,
          isAvailable: false
        });
      }
    });
    Logger.log(`Обработано ${results.length} продуктов`);
    return results;
  }

  processProduct(result) {
    const article = String(result.article);
    let title = OZON_CONFIG.MESSAGES.NO_DATA;
    let cardPrice = OZON_CONFIG.MESSAGES.NO_PRICE_DATA;
    let price = OZON_CONFIG.MESSAGES.NO_PRICE_DATA;
    let originalPrice = OZON_CONFIG.MESSAGES.NO_PRICE_DATA;
    let isAvailable = false;

    if (result.success && result.price_info) {
      const pi = result.price_info;
      title = result.title || title;
      cardPrice = pi.cardPrice || cardPrice;
      price = pi.price || price;
      originalPrice = pi.originalPrice || originalPrice;
      isAvailable = pi.isAvailable || false;
    }
    return { article, title, cardPrice, price, originalPrice, isAvailable };
  }
}