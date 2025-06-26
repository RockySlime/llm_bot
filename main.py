import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
import httpx
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Получаем токен бота и ключ OpenRouter API из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Проверка, что токены загружены
if not TELEGRAM_BOT_TOKEN:
    logging.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения.")
    exit("Ошибка: Токен Telegram-бота не установлен. Пожалуйста, добавьте его в .env файл.")
if not OPENROUTER_API_KEY:
    logging.error("OPENROUTER_API_KEY не найден в переменных окружения.")
    exit("Ошибка: Ключ OpenRouter API не установлен. Пожалуйста, добавьте его в .env файл.")

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Функция для получения ответа от LLM через OpenRouter
async def get_llm_response(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        # Явное указание модели DeepSeek Qwen3 8B
        # !!! ПРОВЕРЬТЕ ТОЧНЫЙ ID МОДЕЛИ НА САЙТЕ OPENROUTER, ЕСЛИ БУДУТ ОШИБКИ !!!
        "model": "deepseek/deepseek-r1-0528-qwen3-8b:free", # Наиболее вероятный ID для "DeepSeek: Deepseek R1 0528 Qwen3 8B (free)"
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            logging.info(f"Отправка запроса в OpenRouter для LLM. Prompt: '{prompt[:50]}...'")
            response = await client.post(f"{OPENROUTER_BASE_URL}/chat/completions", headers=headers, json=data, timeout=60.0)
            response.raise_for_status() # Вызывает исключение для статусов 4xx/5xx

            json_response = response.json()
            if 'choices' in json_response and len(json_response['choices']) > 0:
                content = json_response['choices'][0]['message']['content']
                logging.info(f"Получен ответ от LLM. Длина: {len(content)} символов.")
                return content
            else:
                logging.warning(f"Неожиданный формат ответа от OpenRouter: {json_response}")
                return "Не удалось получить осмысленный ответ от LLM."

    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        return f"Произошла ошибка при обращении к LLM: {e.response.status_code}. Пожалуйста, попробуйте еще раз позже. Детали: {e.response.text}"
    except httpx.RequestError as e:
        logging.error(f"An error occurred while requesting LLM: {e}")
        return "Произошла ошибка сети при обращении к LLM. Пожалуйста, проверьте подключение и повторите попытку."
    except Exception as e:
        logging.error(f"An unexpected error occurred in LLM response: {e}")
        return "Произошла непредвиденная ошибка при получении ответа от LLM."

# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    logging.info(f"Получена команда /start от пользователя {message.from_user.id}")
    await message.reply("Привет! Я Telegram-бот, который общается с помощью LLM через OpenRouter. Отправь мне сообщение, и я постараюсь ответить.")

# Обработчик команды /help
@dp.message_handler(commands=['help'])
async def send_help(message: types.Message):
    logging.info(f"Получена команда /help от пользователя {message.from_user.id}")
    await message.reply("Просто отправь мне любое текстовое сообщение, и я передам его LLM. Я отвечу тебе результатом.")

# Обработчик всех текстовых сообщений
@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle_text_message(message: types.Message):
    logging.info(f"Получено текстовое сообщение от пользователя {message.from_user.id}: '{message.text[:50]}...'")
    await message.reply("Думаю над ответом...") # Сообщаем пользователю, что запрос обрабатывается

    llm_response = await get_llm_response(message.text)
    await message.reply(llm_response)

# Главная функция для запуска бота
if __name__ == '__main__':
    logging.info("Запуск бота...")
    executor.start_polling(dp, skip_updates=True)