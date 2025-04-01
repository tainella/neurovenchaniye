from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import Message
from aiogram.types import BufferedInputFile 
from aiogram.filters import Command
from aiogram.enums.parse_mode import ParseMode
import base64
import aiohttp
import asyncio
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import json
import os
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv, set_key, find_dotenv

#from googleapiclient.discovery import build

from app.sql_database.User import UserDatabase

load_dotenv(override=True)

LOG_DIR = "./data/bot_logs"

# SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
# SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE") 

# credentials = ServiceAccountCredentials.from_service_account_file(
#     SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# service_sheets = build("sheets", "v4", credentials=credentials)

# GOOGLE_SHEET = os.getenv("GOOGLE_SHEET")
# RANGE_NAME = "ОС пользователей!A2:I"

db_user = UserDatabase()

router = Router()
storage = MemoryStorage()
dispatcher = Dispatcher(storage=storage)

def update_env_variable(key, value):
    dotenv_path = find_dotenv()
    cleaned_value = value.replace(""", "").replace(""", "")  
    set_key(dotenv_path, key, cleaned_value, quote_mode="never")

class ConfigStates(StatesGroup):
    numerology = State()
    palmistry = State()
    combination = State()

@router.message(Command(commands=["id"]))
async def get_user_id(message: Message):
    user_id = message.from_user.id
    await message.answer(f"Ваш Telegram User ID: {user_id}")

def get_welcome_message(user_name):
    if not user_name:
        user_name = "коллега"
    with open("app/bot_messages/welcome.txt", encoding="utf-8") as f:
        welcome = f.read()
    return welcome.format(user_name=user_name)

functionality = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Сеанс нумерологии")],
        [KeyboardButton(text="Сеанс хиромантии")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

connected_sessions = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Да, сеанс хиромантии")],
        [KeyboardButton(text="Нет, в главное меню")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# логирование
def log_user_action(user_id, action, details=None, error=None):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "action": action,
        "details": details,
        "error": str(error) if error else None,
    }
    user_log_file = os.path.join(LOG_DIR, f"user_{user_id}.log")
    with open(user_log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

user_state = {}

# ============ START ===============
@router.message(Command(commands=["start"]))
async def start_command(message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or ""
    
    if not db_user.exists(user_id):
        await message.answer(
            "Вы не зарегистрированы в системе. Используйте команду /auth, чтобы зарегистрироваться."
        )
        return
    # else:
    #     if not db_user.is_approved(user_id):
    #         await message.answer(
    #             "Вы зарегистрированы, но не одобрены администратором. Ожидайте подтверждения."
    #         )
    #         return
        # все ок
        # log_user_action(user_id, "start", {"user_name": user_name})
    await message.answer(get_welcome_message(user_name),
                         parse_mode=ParseMode.MARKDOWN,
                         reply_markup=functionality)
    
@router.message(Command(commands=["end"]))
async def cmd_end(message: Message, state: FSMContext):
    """
    сбрасывает текущее состояние
    """
    await state.clear()
    await message.answer("Вы вышли из текущего режима ввода.")

# ============ ГЛАВНОЕ МЕНЮ ===================
@router.message(F.text.in_(["Нет, в главное меню", "Главное меню"]))
async def choose_structure(message: Message):
    user_name = message.from_user.first_name or ""
    await message.answer(get_welcome_message(user_name),
                         parse_mode=ParseMode.MARKDOWN,
                         reply_markup=functionality)

# ============ СЕАНС НУМЕРОЛОГИИ ===================
@router.message(F.text == "Сеанс нумерологии")
async def choose_structure(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_state[user_id] = "structure"
    log_user_action(user_id, "start_numerology")
    with open("app/bot_messages/start_numerology.txt") as f:
        start_numerology = f.read()
    
    excel_path = "app/temp/questionnaire.xlsx"
    with open(excel_path, "rb") as excel_file:
        await message.answer_document(
            document=types.BufferedInputFile(
                excel_file.read(),
                filename="Опрос_нумерология.xlsx"
            ),
            caption=start_numerology,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=types.ReplyKeyboardRemove()
        )
    await state.set_state(ConfigStates.numerology)

def fill_mapping(user_info: pd.DataFrame):
     json_data = {
        "base": {},
        "base_optional": {},
        "desire": "",
        "desire_optional": {},
        "optional": {}
    }
     with open("./data/numerology/field_mapping.json") as f:
        field_mapping = json.load(f)
        for i, row in user_info.iterrows():
            if len(row) < 2:  # Пропускаем строки без значений
                continue
            
            field_name = row[0]
            field_value = row[1]
            
            if field_name in field_mapping:
                section, key = field_mapping[field_name]
                # Обработка особых случаев
                if field_name == "Дата рождения" or field_name == "Дата консультирования":
                    # Преобразуем дату в ISO формат
                    try:
                        # Если дата в формате DD.MM.YYYY
                        if isinstance(field_value, str) and '.' in field_value:
                            day, month, year = field_value.split('.')
                            field_value = f"{year}-{month}-{day}"
                        # Если дата уже как объект datetime
                        elif isinstance(field_value, datetime):
                            field_value = field_value.strftime("%Y-%m-%d")
                    except Exception:
                        # Если не удалось преобразовать, оставляем как есть
                        pass
                if key == "None":  # Для поля "desire", которое не вложенный объект
                    json_data[section] = field_value
                else:
                    json_data[section][key] = field_value
        return json_data

@router.message(ConfigStates.numerology)
async def get_questionnaire(message: Message, bot: Bot, state: FSMContext):
    user_id = message.from_user.id
    log_user_action(user_id, "got_num_questionnaire")
    await bot.download(message.document.file_id, destination="app/temp/questionnaire.xlsx")
    questionnaire = pd.read_excel("app/temp/questionnaire.xlsx")
    user_info = fill_mapping(questionnaire)
    with open("./data/numerology/user_info.json", 'w') as f:
        json.dump(user_info, f, ensure_ascii=False, indent=4)

    await message.answer("Спасибо, анкета в обработке")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url=f"http://0.0.0.0:{os.getenv('BACKEND_PORT')}/numerology/user/",
            json=user_info) as num_answer:
            if num_answer.status != 200:  # or any other success code like 201
                error_text = await num_answer.text()
                await message.answer("Ошибка! " + error_text[:1000],
                                reply_markup=functionality)
            else:
                num_answer = await num_answer.json()
                user_id = message.from_user.id
                caption=f"""Хотите запустить связанный сеанс?"""
                if user_id in db_user.get_admins_id():
                    caption = f"<a href='{num_answer['link']}'>Гугл таблица</a>\n\n" + caption
                print('GOT ANSWER')
                pdf_binary = base64.b64decode(num_answer['pdf'])
                document = BufferedInputFile(
                    file=pdf_binary,
                    filename="Результат нумерология.pdf"
                )
                await asyncio.wait_for(message.answer_document(
                    document=document,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=connected_sessions),
                    timeout=50000)
                await state.clear()

# ============ СЕАНС ХИРОМАНТИИ ===================

@router.message(F.text.in_(["Сеанс хиромантии", "Да, сеанс хиромантии"]))
async def palmistry_session(message: Message):
    user_name = message.from_user.first_name or ""
    await message.answer(get_welcome_message(user_name),
                         parse_mode=ParseMode.MARKDOWN,
                         reply_markup=functionality)