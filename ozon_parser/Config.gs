// OZON_Config.gs
const OZON_CONFIG = {
  COLUMN_KEYWORDS: {
    NUMBER: ['№', 'номер', 'number', 'n'],
    ARTICLE: ['артикул', 'article', 'код', 'code'],
    TITLE: ['наименование', 'name', 'название', 'title', 'товар'],
    CARD_PRICE: ['cpp', 'с учетом спп ozon', 'cardprice', 'цена с учетом спп ozon кошелька (cpp)'],
    PRICE: ['без ozon', 'без озон', 'всех скидок', 'price'],
    ORIGINAL_PRICE: ['первоначальная цена (original)', 'первоначальная', 'original', 'оригинальная'],
    AVAILABLE: ['доступность', 'available', 'в наличии', 'наличие'],
    API_URL: ['api url', 'api ссылка', 'ссылка api', 'url api', 'ngrok url', 'api endpoint']
  },
  // Настройки API
  API_URL_CELL: 'B1', // Ячейка для настройки API URL (ОБЯЗАТЕЛЬНО)
  BATCH_SIZE: 50,
  REQUEST_DELAY: 2000,
  MAX_RETRIES: 3,
  HEADER_ROW: 2,
  DATA_START_ROW: 3,
  MESSAGES: {
    NO_PRICE_DATA: 'Цена не найдена',
    NO_DATA: 'Не найдено',
    PROCESSING: 'Обработка...',
    ERROR: 'Ошибка',
    NOT_AVAILABLE: 'Нет в наличии',
    COLUMN_NOT_FOUND: 'Столбец не найден',
    API_URL_NOT_SET: 'API URL не настроен',
    INVALID_API_URL: 'Неверный формат API URL'
  }
};