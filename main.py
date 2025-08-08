import logging
import uvicorn
import webbrowser
import threading
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routes.parser_routes import router as parser_router
from config.settings import settings
from pyngrok import ngrok
import time


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Ozon Price Parser API",
    description="API for parsing product prices from Ozon",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    logger.info(f"Request: {request.method} {request.url}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} - {process_time:.2f}s")
    
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(parser_router, prefix="/api/v1", tags=["parser"])


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Ozon Price Parser API",
        "version": "1.0.0",
        "docs": "/docs"
    }


def start_ngrok_tunnel():
    """
    Запускает ngrok туннель и возвращает публичную ссылку
    """
    try:
        # Создаем туннель на порт 8000
        public_url = ngrok.connect(8000)
        logger.info("="*60)
        logger.info("� NGPROK ТУННЕЛЬ УСПЕШНО ЗАПУЩЕН!")
        logger.info("="*60)
        logger.info(f"🌐 Публичный URL: {public_url}")
        logger.info(f"📖 API документация: {public_url}/docs")
        logger.info(f"🔧 Swagger UI: {public_url}/docs")
        logger.info(f"📚 ReDoc: {public_url}/redoc")
        logger.info("="*60)
        logger.info("📋 Примеры curl запросов:")
        logger.info(f"   curl -X GET \"{public_url}/\"")
        logger.info(f"   curl -X GET \"{public_url}/api/v1/health\"")
        logger.info(f"   curl -X POST \"{public_url}/api/v1/get_price\" -H \"Content-Type: application/json\" -d '{{\"articles\": [158761892]}}'")
        logger.info("="*60)
        
        # Автоматически открываем документацию в браузере
        try:
            webbrowser.open(f"{public_url}/docs")
            logger.info("🌐 Документация API открыта в браузере")
        except Exception as browser_error:
            logger.warning(f"Не удалось открыть браузер: {browser_error}")
        
        return public_url
    except Exception as e:
        logger.error(f"❌ Ошибка запуска ngrok: {e}")
        logger.error("Убедитесь, что:")
        logger.error("1. ngrok установлен и доступен в PATH")
        logger.error("2. authtoken настроен: ngrok config add-authtoken <your_token>")
        logger.error("3. Порт 8000 не занят другим процессом")
        return None


# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Ozon Price Parser API...")
    logger.info(f"Settings: Headless={settings.HEADLESS}, Max articles={settings.MAX_ARTICLES_PER_REQUEST}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Ozon Price Parser API...")
    
    # Отключаем ngrok туннель
    try:
        ngrok.disconnect_all()
        logger.info("ngrok туннель отключен")
    except Exception as e:
        logger.warning(f"Ошибка отключения ngrok: {e}")
    
    # Clean up parser instance
    from routes.parser_routes import parser_instance
    if parser_instance:
        parser_instance.close()


if __name__ == "__main__":
    logger.info("🚀 Запуск Ozon Parser API с ngrok интеграцией...")
    
    # Запускаем ngrok туннель
    public_url = start_ngrok_tunnel()
    
    if not public_url:
        logger.error("❌ Не удалось запустить ngrok туннель. Запуск только локального сервера...")
        logger.info("🌐 Локальный сервер будет доступен по адресу: http://localhost:8000")
    
    # Небольшая задержка для инициализации ngrok
    time.sleep(2)
    
    try:
        # Запускаем FastAPI сервер на порту 8000
        logger.info("🔥 Запуск FastAPI сервера...")
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,  # Отключаем reload для стабильности с ngrok
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска сервера: {e}")
    finally:
        # Отключаем ngrok при завершении
        try:
            ngrok.disconnect_all()
            logger.info("🔌 ngrok туннель отключен")
        except Exception as e:
            logger.warning(f"⚠️  Ошибка отключения ngrok: {e}")
        
        logger.info("👋 Сервер остановлен")