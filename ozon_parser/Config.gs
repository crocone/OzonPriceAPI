// OZON_Config.gs
const OZON_CONFIG = {
  COLUMN_KEYWORDS: {
    NUMBER: ['№', 'номер', 'number', 'n'],
    ARTICLE: ['артикул', 'article', 'код', 'code'],
    TITLE: ['наименование', 'name', 'название', 'title', 'товар'],
    SELLER: ['продавец', 'seller', 'компания', 'магазин', 'поставщик'],
    CARD_PRICE: ['cpp', 'с учетом спп ozon', 'cardprice', 'цена с учетом спп ozon кошелька (cpp)'],
    PRICE: ['без ozon', 'без озон', 'всех скидок', 'price'],
    ORIGINAL_PRICE: ['первоначальная цена (original)', 'первоначальная', 'original', 'оригинальная'],
    AVAILABLE: ['доступность', 'available', 'в наличии', 'наличие'],
    API_URL: ['api url', 'api ссылка', 'ссылка api', 'url api', 'ngrok url', 'api endpoint']
  },
  // Настройки API
  API_URL_CELL: 'B1', // Ячейка для настройки API URL (ОБЯЗАТЕЛЬНО)
  BATCH_SIZE: 130,
  REQUEST_DELAY: 2000, // Задержка между батчами в миллисекундах
  MAX_RETRIES: 3,
  HEADER_ROW: 2,
  DATA_START_ROW: 3,
  
  // Настройки для выделенных артикулов
  SELECTION_BATCH_SIZE: 1, // Меньший размер батча для выделенных артикулов
  
  // Настройки сохранения
  SAVE_DELAY: 500, // Задержка после сохранения в миллисекундах
  FORCE_FLUSH: true, // Принудительное сохранение изменений
  MESSAGES: {
    NO_PRICE_DATA: 'Цена не найдена',
    NO_DATA: 'Не найдено',
    PROCESSING: 'Обработка...',
    ERROR: 'Ошибка',
    NOT_AVAILABLE: 'Нет в наличии',
    COLUMN_NOT_FOUND: 'Столбец не найден',
    API_URL_NOT_SET: 'API URL не настроен',
    INVALID_API_URL: 'Неверный формат API URL',
    NO_SELECTION: 'Нет выделенного диапазона',
    NO_VALID_ARTICLES_IN_SELECTION: 'В выделенном диапазоне нет валидных артикулов'
  }
};