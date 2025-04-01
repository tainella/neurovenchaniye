from aiogram import Bot, Dispatcher, types
from aiogram.types import FSInputFile
from aiogram.utils import executor
import asyncio

API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['send_circle'])
async def send_video_circle(message: types.Message):
    try:
        # Укажите путь к файлу кружка
        file_path = 'path/to/your/video.mp4'
        video_file = FSInputFile(file_path)

        # Отправляем кружок
        await bot.send_video_note(chat_id=message.chat.id, video_note=video_file)

        await message.reply("Кружок отправлен!")
    except Exception as e:
        await message.reply(f"Ошибка отправки кружка: {str(e)}")

if __name__ == '__main__':
    # Запускаем бота
    executor.start_polling(dp, skip_updates=True)
