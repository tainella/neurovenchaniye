import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))
from app.handlers.handlers import router
from app.handlers.login_handlers import router as login_router
from app.handlers.admin_handlers import router as admin_router
from dotenv import load_dotenv
# from src.numerology import api as num_api

load_dotenv(override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")

LOG_DIR = "./data/bot_logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "bot.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(console_handler)

async def set_commands(bot: Bot):
    # Определяем список команд с описаниями
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="auth", description="Регистрация"),
        BotCommand(command="admin", description="Административное меню"),
        BotCommand(command="id", description="Получение своего id"),
        BotCommand(command="show_db", description="Показать всех пользователей"),
        BotCommand(command="end", description="Сброс состояния"),
    ]
    # Устанавливаем команды для бота
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

async def main():
    logging.info("Bot is starting...")
    try:
        if not BOT_TOKEN:
            logging.error("BOT_TOKEN is empty or not set!")
            return
            
        logging.info(f"Using token: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]}")
        bot = Bot(token=BOT_TOKEN)
        
        # Verify connection to Telegram
        try:
            me = await bot.get_me()
            logging.info(f"Successfully connected as @{me.username}")
        except Exception as e:
            logging.error(f"Failed to connect to Telegram: {e}")
            return
            
        dp = Dispatcher()
        dp.include_router(router)
        dp.include_router(login_router)
        dp.include_router(admin_router)
        await set_commands(bot)
        logging.info("Starting polling...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, timeout=5)
    except Exception as e:
        logging.error(f"Error in main bot function: {e}", exc_info=True)
    finally:
        logging.info("Bot is shutting down...")
        if 'bot' in locals():
            await bot.session.close()

async def start_services():
    logging.info("Starting bot service...")
    task1 = asyncio.create_task(main())
    logging.info("Starting numerology API service...")
    # task2 = asyncio.create_task(num_api.main())
    await asyncio.gather(task1)#, task2)

if __name__ == "__main__":
    try:
         asyncio.run(start_services())
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
