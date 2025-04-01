import asyncio
import logging
import os
import sys
import random
import json
import time
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Any
from datetime import datetime
from pathlib import Path
import base64
import aiohttp

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import BotCommand, BotCommandScopeDefault, Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import BufferedInputFile
from aiogram.filters import Command
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv, set_key, find_dotenv
import pandas as pd
import random

# Путь к файлу
file_path = './app/auf.txt'

def get_random_name():
    # Чтение файла и преобразование в массив строк
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = [line.strip() for line in file.readlines() if line.strip()]

    # Выбор случайной строки
    return random.choice(lines)
# Load environment variables
load_dotenv(override=True)

# Bot token from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Directory setup
LOG_DIR = "./data/bot_logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Data storage directory for JSON files
DATA_DIR = "./data/storage"
os.makedirs(DATA_DIR, exist_ok=True)
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")

# Directory for saving dialogues
DIALOGUES_DIR = "./data/dialogues"
os.makedirs(DIALOGUES_DIR, exist_ok=True)

# Create necessary app directories
os.makedirs("app/bot_messages", exist_ok=True)
os.makedirs("app/temp", exist_ok=True)
os.makedirs("data/numerology", exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "bot.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(console_handler)

# Create routers
router = Router()
login_router = Router()
admin_router = Router()
matchmaking_router = Router()

# Define FSM states
class ConfigStates(StatesGroup):
    numerology = State()
    palmistry = State()
    combination = State()

# Define user roles and states for matchmaking
class UserRole(str, Enum):
    HERO = "hero"
    PRETENDER = "pretender"
    HOST = "host"

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"

class RoomState(str, Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    QUESTION = "question"
    VOTING = "voting"
    FINISHED = "finished"

# Data structures for matchmaking
waiting_users: Dict[int, Gender] = {}  # user_id -> gender
active_rooms: Dict[str, Dict] = {}  # room_id -> room_data
user_to_room: Dict[int, str] = {}  # user_id -> room_id
user_state = {}  # For tracking user state in handlers

# Sample questions for the game
QUESTIONS = [
    "Что для вас самое важное в отношениях?",
    "Как вы проводите свободное время?",
    "Какую книгу вы прочитали последней?",
    "Что бы вы хотели изменить в своей жизни?",
    "Какое ваше любимое место для путешествий?",
    "Опишите свой идеальный день",
    "Какое качество вы цените в людях больше всего?",
    "Какая ваша самая заветная мечта?"
]

# Setup storage
storage = MemoryStorage()

# ============================
# JSON STORAGE FUNCTIONS
# ============================

def init_json_storage():
    """Initialize JSON files if they don't exist"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        
        if not os.path.exists(USERS_FILE):
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f)
        
        if not os.path.exists(ADMINS_FILE):
            with open(ADMINS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
                
        # Ensure welcome message exists
        welcome_path = "app/bot_messages/welcome.txt"
        if not os.path.exists(welcome_path):
            os.makedirs(os.path.dirname(welcome_path), exist_ok=True)
            with open(welcome_path, "w", encoding="utf-8") as f:
                f.write("Привет, {user_name}! Добро пожаловать.")
        
        # Ensure numerology message exists
        numerology_path = "app/bot_messages/start_numerology.txt"
        if not os.path.exists(numerology_path):
            os.makedirs(os.path.dirname(numerology_path), exist_ok=True)
            with open(numerology_path, "w", encoding="utf-8") as f:
                f.write("Заполните анкету для сеанса нумерологии.")
        
        # Create field_mapping.json if it doesn't exist
        mapping_file = os.path.join("data/numerology", "field_mapping.json")
        if not os.path.exists(mapping_file):
            os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
            with open(mapping_file, "w", encoding="utf-8") as f:
                json.dump({
                    "Дата рождения": ["base", "birth_date"],
                    "Имя": ["base", "name"]
                }, f, indent=2, ensure_ascii=False)
                
        # Check for dummy questionnaire
        questionnaire_path = "app/temp/questionnaire.xlsx"
        if not os.path.exists(questionnaire_path):
            try:
                # Create a very basic Excel file as placeholder
                os.makedirs(os.path.dirname(questionnaire_path), exist_ok=True)
                df = pd.DataFrame([
                    ["Дата рождения", ""],
                    ["Имя", ""]
                ])
                df.to_excel(questionnaire_path, index=False, header=False)
            except Exception as e:
                logging.error(f"Could not create placeholder questionnaire: {e}")
                
        logging.info("JSON storage initialized successfully")
    except Exception as e:
        logging.error(f"Error initializing JSON storage: {e}")
        # Continue execution despite error - we'll handle individual file errors elsewhere

def user_exists(user_id: int) -> bool:
    """Check if user exists in the database"""
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        return str(user_id) in users
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error checking if user exists: {e}")
        # If we can't check, assume user doesn't exist
        return False
    except Exception as e:
        logging.error(f"Unexpected error checking if user exists: {e}")
        return False

def add_user(user_id: int, name: str, gender: str = None) -> None:
    """Add a new user to the database"""
    try:
        # First check if the file exists, if not create it
        if not os.path.exists(USERS_FILE):
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f)
        
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        
        users[str(user_id)] = {
            "name": name,
            "gender": gender,
            "registration_date": datetime.now().isoformat(),
            "approved": False  # By default, users aren't approved
        }
        
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error adding user: {e}")

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user data from the database"""
    try:
        if not os.path.exists(USERS_FILE):
            return None
            
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        
        return users.get(str(user_id))
    except Exception as e:
        logging.error(f"Error getting user: {e}")
        return None

def approve_user(user_id: int) -> bool:
    """Approve a user in the database"""
    try:
        if not os.path.exists(USERS_FILE):
            return False
            
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        
        if str(user_id) in users:
            users[str(user_id)]["approved"] = True
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=2, ensure_ascii=False)
            return True
        return False
    except Exception as e:
        logging.error(f"Error approving user: {e}")
        return False

def is_approved(user_id: int) -> bool:
    """Check if a user is approved"""
    try:
        user_data = get_user(user_id)
        return user_data and user_data.get("approved", False)
    except Exception as e:
        logging.error(f"Error checking if user is approved: {e}")
        return False

def get_all_users() -> Dict[str, Any]:
    """Get all users from the database"""
    try:
        if not os.path.exists(USERS_FILE):
            return {}
            
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        return users
    except Exception as e:
        logging.error(f"Error getting all users: {e}")
        return {}

def get_admins_id() -> List[int]:
    """Get list of admin user IDs"""
    try:
        if not os.path.exists(ADMINS_FILE):
            with open(ADMINS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
                
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            admins = json.load(f)
        
        return [int(admin_id) for admin_id in admins]
    except (FileNotFoundError, json.JSONDecodeError):
        # If file doesn't exist or is empty, return empty list
        return []
    except Exception as e:
        logging.error(f"Error getting admin IDs: {e}")
        return []

def add_admin(user_id: int) -> None:
    """Add a user to admins list"""
    try:
        if not os.path.exists(ADMINS_FILE):
            with open(ADMINS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
                
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            admins = json.load(f)
        
        if str(user_id) not in admins:
            admins.append(str(user_id))
        
        with open(ADMINS_FILE, "w", encoding="utf-8") as f:
            json.dump(admins, f, indent=2)
    except Exception as e:
        logging.error(f"Error adding admin: {e}")

def remove_admin(user_id: int) -> bool:
    """Remove a user from admins list"""
    try:
        if not os.path.exists(ADMINS_FILE):
            return False
            
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            admins = json.load(f)
        
        if str(user_id) in admins:
            admins.remove(str(user_id))
            with open(ADMINS_FILE, "w", encoding="utf-8") as f:
                json.dump(admins, f, indent=2)
            return True
        return False
    except Exception as e:
        logging.error(f"Error removing admin: {e}")
        return False

# ============================
# HELPER FUNCTIONS
# ============================

def update_env_variable(key, value):
    try:
        dotenv_path = find_dotenv()
        if dotenv_path:  # Check if .env file exists
            cleaned_value = value.replace(""", "").replace(""", "")  
            set_key(dotenv_path, key, cleaned_value, quote_mode="never")
    except Exception as e:
        logging.error(f"Error updating env variable: {e}")

def log_user_action(user_id, action, details=None, error=None):
    """Log user actions to individual log files"""
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "details": details,
            "error": str(error) if error else None,
        }
        
        log_dir = "./data/bot_logs"
        os.makedirs(log_dir, exist_ok=True)
        user_log_file = os.path.join(log_dir, f"user_{user_id}.log")
        
        with open(user_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        # Just log to console but don't crash
        logging.error(f"Error logging user action: {e}")

def get_welcome_message(user_name):
    """Generate welcome message for a user"""
    try:
        if not user_name:
            user_name = "Ламповая няша"
        
        welcome_path = "app/bot_messages/welcome.txt"
        # Check if file exists
        if not os.path.exists(welcome_path):
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(welcome_path), exist_ok=True)
            # Create default welcome message
            with open(welcome_path, "w", encoding="utf-8") as f:
                f.write("Добро пожаловать, {user_name}!")
            
        with open(welcome_path, encoding="utf-8") as f:
            welcome = f.read()
        return welcome.format(user_name=user_name)
    except Exception as e:
        logging.error(f"Error getting welcome message: {e}")
        # Fallback message in case of error
        return f"Добро пожаловать, {user_name}!"

# Define keyboards
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

def fill_mapping(user_info: pd.DataFrame):
    """Process user questionnaire data"""
    try:
        json_data = {
            "base": {},
            "base_optional": {},
            "desire": "",
            "desire_optional": {},
            "optional": {}
        }
        
        mapping_path = "./data/numerology/field_mapping.json"
        if not os.path.exists(mapping_path):
            # Create a default mapping if none exists
            os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
            field_mapping = {
                "Дата рождения": ["base", "birth_date"],
                "Имя": ["base", "name"]
            }
            with open(mapping_path, "w", encoding="utf-8") as f:
                json.dump(field_mapping, f, indent=2, ensure_ascii=False)
        else:
            with open(mapping_path) as f:
                field_mapping = json.load(f)
                
        for i, row in user_info.iterrows():
            if len(row) < 2:  # Skip rows without values
                continue
            
            field_name = row[0]
            field_value = row[1]
            
            if field_name in field_mapping:
                section, key = field_mapping[field_name]
                # Handle special cases
                if field_name == "Дата рождения" or field_name == "Дата консультирования":
                    # Convert date to ISO format
                    try:
                        # If date is in DD.MM.YYYY format
                        if isinstance(field_value, str) and '.' in field_value:
                            day, month, year = field_value.split('.')
                            field_value = f"{year}-{month}-{day}"
                        # If date is already a datetime object
                        elif isinstance(field_value, datetime):
                            field_value = field_value.strftime("%Y-%m-%d")
                    except Exception:
                        # If conversion fails, leave as is
                        pass
                if key == "None":  # For "desire" field, which is not a nested object
                    json_data[section] = field_value
                else:
                    json_data[section][key] = field_value
        return json_data
    except Exception as e:
        logging.error(f"Error filling mapping: {e}")
        # Return a basic structure in case of error
        return {
            "base": {},
            "base_optional": {},
            "desire": "",
            "desire_optional": {},
            "optional": {}
        }

# ============================
# COMMAND HANDLERS
# ============================

@router.message(Command(commands=["id"]))
async def get_user_id(message: Message):
    """Get user's Telegram ID"""
    try:
        user_id = message.from_user.id
        await message.answer(f"Ваш Telegram User ID: {user_id}")
    except Exception as e:
        logging.error(f"Error getting user ID: {e}")
        await message.answer("Произошла ошибка при получении ID.")

@router.message(Command(commands=["start"]))
async def start_command(message: Message):
    """Start bot interaction"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name or ""
        
        if not user_exists(user_id):
            await message.answer(
                "Вы не зарегистрированы в системе. Используйте команду /auth, чтобы зарегистрироваться."
            )
            return
        
        await message.answer(get_welcome_message(user_name),
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=functionality)
        log_user_action(user_id, "start", {"user_name": user_name})
    except Exception as e:
        logging.error(f"Error in start command: {e}")
        # Try to respond with a basic message if possible
        try:
            await message.answer("Произошла ошибка при запуске бота. Пожалуйста, попробуйте позже.")
        except:
            pass  # If even this fails, just move on

@router.message(Command(commands=["end"]))
async def cmd_end(message: Message, state: FSMContext):
    """Reset current state"""
    try:
        await state.clear()
        await message.answer("Вы вышли из текущего режима ввода.")
    except Exception as e:
        logging.error(f"Error ending state: {e}")
        await message.answer("Произошла ошибка при выходе из режима.")

@router.message(F.text.in_(["Нет, в главное меню", "Главное меню"]))
async def choose_structure(message: Message):
    """Return to main menu"""
    try:
        user_name = message.from_user.first_name or ""
        await message.answer(get_welcome_message(user_name),
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=functionality)
    except Exception as e:
        logging.error(f"Error returning to main menu: {e}")
        await message.answer("Произошла ошибка при возврате в главное меню.")

# ============================
# NUMEROLOGY SESSION
# ============================

@router.message(F.text == "Сеанс нумерологии")
async def choose_structure(message: Message, state: FSMContext):
    """Start numerology session"""
    try:
        user_id = message.from_user.id
        user_state[user_id] = "structure"
        log_user_action(user_id, "start_numerology")
        
        # Check if file exists
        numerology_path = "app/bot_messages/start_numerology.txt"
        if not os.path.exists(numerology_path):
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(numerology_path), exist_ok=True)
            # Create default message
            with open(numerology_path, "w", encoding="utf-8") as f:
                f.write("Заполните анкету для сеанса нумерологии.")
                
        with open(numerology_path) as f:
            start_numerology = f.read()
        
        excel_path = "app/temp/questionnaire.xlsx"
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        
        if os.path.exists(excel_path):
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
        else:
            # Create a basic questionnaire if it doesn't exist
            df = pd.DataFrame([
                ["Дата рождения", ""],
                ["Имя", ""]
            ])
            df.to_excel(excel_path, index=False, header=False)
            
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
    except Exception as e:
        logging.error(f"Error starting numerology session: {e}")
        try:
            await message.answer(
                "Произошла ошибка при запуске сеанса нумерологии. Пожалуйста, попробуйте позже.",
                reply_markup=functionality
            )
        except:
            pass  # If even this fails, just move on

@router.message(ConfigStates.numerology, F.document)
async def get_questionnaire(message: Message, bot: Bot, state: FSMContext):
    """Process numerology questionnaire"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "got_num_questionnaire")
        
        # Create the temp directory if it doesn't exist
        os.makedirs("app/temp", exist_ok=True)
        
        # Download the document
        file_path = "app/temp/questionnaire.xlsx"
        await bot.download(message.document, destination=file_path)
        
        # Ensure the file was downloaded successfully
        if not os.path.exists(file_path):
            await message.answer("Не удалось загрузить файл. Пожалуйста, попробуйте еще раз.")
            return
            
        # Read and process the questionnaire
        questionnaire = pd.read_excel(file_path)
        user_info = fill_mapping(questionnaire)
        
        # Ensure the directory exists
        os.makedirs("./data/numerology", exist_ok=True)
        
        with open("./data/numerology/user_info.json", 'w', encoding="utf-8") as f:
            json.dump(user_info, f, ensure_ascii=False, indent=4)

        await message.answer("Спасибо, анкета в обработке")
        
        backend_port = os.getenv('BACKEND_PORT', '8000')
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    url=f"http://0.0.0.0:{backend_port}/numerology/user/",
                    json=user_info) as num_answer:
                    if num_answer.status != 200:  # or any other success code like 201
                        error_text = await num_answer.text()
                        await message.answer("Ошибка! " + error_text[:1000],
                                        reply_markup=functionality)
                    else:
                        num_answer = await num_answer.json()
                        caption=f"""Хотите запустить связанный сеанс?"""
                        if user_id in get_admins_id():
                            caption = f"<a href='{num_answer['link']}'>Гугл таблица</a>\n\n" + caption
                        logging.info('GOT ANSWER')
                        
                        try:
                            if 'pdf' in num_answer:
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
                            else:
                                await message.answer(
                                    "Обработка завершена, но PDF результат не был получен.",
                                    reply_markup=connected_sessions
                                )
                        except Exception as e:
                            logging.error(f"Error sending document: {e}")
                            await message.answer(
                                "Не удалось отправить результат. Пожалуйста, попробуйте позже.",
                                reply_markup=functionality
                            )
                        
                        await state.clear()
            except Exception as e:
                logging.error(f"Error communicating with backend: {e}")
                await message.answer(
                    "Ошибка при обработке анкеты. Пожалуйста, попробуйте позже.",
                    reply_markup=functionality
                )
    except Exception as e:
        logging.error(f"Error processing questionnaire: {e}")
        await message.answer(
            "Произошла ошибка при обработке анкеты. Пожалуйста, попробуйте позже.",
            reply_markup=functionality
        )
        await state.clear()

# ============================
# PALMISTRY SESSION
# ============================

@router.message(F.text.in_(["Сеанс хиромантии", "Да, сеанс хиромантии"]))
async def palmistry_session(message: Message):
    """Start palmistry session"""
    try:
        user_name = message.from_user.first_name or ""
        await message.answer(get_welcome_message(user_name),
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=functionality)
    except Exception as e:
        logging.error(f"Error starting palmistry session: {e}")
        try:
            await message.answer(
                "Произошла ошибка при запуске сеанса хиромантии. Пожалуйста, попробуйте позже.",
                reply_markup=functionality
            )
        except:
            pass

# ============================
# LOGIN HANDLERS
# ============================

@login_router.message(Command(commands=["auth"]))
async def auth_command(message: Message):
    """User registration command"""
    try:
        logging.info(f"Handling auth command from user {message.from_user.id}")
        user_id = message.from_user.id
        user_name = message.from_user.first_name or ""
        
        # Here you would typically collect more user information
        # For simplicity, let's assume gender is provided in the command
        args = message.text.split()
        if len(args) < 2 or args[1].lower() not in ["male", "female"]:
            await message.answer(
                "Пожалуйста, укажите ваш пол: /auth male или /auth female"
            )
            return
        
        gender = Gender.MALE if args[1].lower() == "male" else Gender.FEMALE
        
        # Register the user in JSON storage
        if not user_exists(user_id):
            add_user(user_id, get_random_name(), gender.value)
            add_admin(user_id)
            
            # Add user to waiting lobby
            waiting_users[user_id] = gender
            
            await message.answer(
                "Вы успешно зарегистрированы! Попали в зал ожидания.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            log_user_action(user_id, "registration", {"gender": gender.value})
        else:
            # User already exists, still add to waiting lobby
            waiting_users[user_id] = gender
            await message.answer(
                "Вы уже зарегистрированы. Попали в зал ожидания.",
                reply_markup=types.ReplyKeyboardRemove()
            )
    except Exception as e:
        logging.error(f"Error in auth command: {e}")
        await message.answer("Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.")

# ============================
# ADMIN HANDLERS
# ============================

@admin_router.message(Command(commands=["admin"]))
async def admin_command(message: Message):
    """Admin panel command"""
    try:
        user_id = message.from_user.id
        
        # Check if the user is an admin
        if user_id not in get_admins_id():
            await message.answer("У вас нет доступа к административной панели.")
            return
        
        # Create admin keyboard
        admin_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Показать всех пользователей")],
                [KeyboardButton(text="Добавить админа")],
                [KeyboardButton(text="Удалить админа")],
                [KeyboardButton(text="Главное меню")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            "Административная панель. Выберите действие:",
            reply_markup=admin_keyboard
        )
    except Exception as e:
        logging.error(f"Error in admin command: {e}")
        await message.answer("Произошла ошибка при доступе к административной панели.")

@admin_router.message(F.text == "Показать всех пользователей")
@admin_router.message(Command(commands=["show_db"]))
async def show_db_command(message: Message):
    """Show all users command"""
    try:
        user_id = message.from_user.id
        
        # Check if the user is an admin
        if user_id not in get_admins_id():
            await message.answer("У вас нет доступа к этой команде.")
            return
        
        users = get_all_users()
        
        if not users:
            await message.answer("База данных пуста.")
            return
        
        # Format user data
        user_list = "Список пользователей:\n\n"
        for uid, user_data in users.items():
            approved_status = "Одобрен" if user_data.get("approved", False) else "Не одобрен"
            user_list += f"ID: {uid}\nИмя: {get_random_name()}\n"
            user_list += f"Пол: {user_data.get('gender', 'Не указан')}\n"
            user_list += f"Статус: {approved_status}\n"
            user_list += f"Дата регистрации: {user_data.get('registration_date', 'Неизвестно')}\n\n"
        
        # Send as a document if the list is too long
        if len(user_list) > 4000:
            with open("temp_users.txt", "w", encoding="utf-8") as f:
                f.write(user_list)
            
            with open("temp_users.txt", "rb") as f:
                await message.answer_document(
                    document=types.BufferedInputFile(
                        f.read(),
                        filename="users_list.txt"
                    ),
                    caption="Список пользователей (полный)"
                )
            
            # Clean up temp file
            if os.path.exists("temp_users.txt"):
                os.remove("temp_users.txt")
        else:
            await message.answer(user_list)
    except Exception as e:
        logging.error(f"Error showing database: {e}")
        await message.answer("Произошла ошибка при отображении базы данных.")

@admin_router.message(F.text == "Добавить админа")
async def add_admin_prompt(message: Message, state: FSMContext):
    """Prompt for adding an admin"""
    try:
        user_id = message.from_user.id
        
        if user_id not in get_admins_id():
            await message.answer("У вас нет доступа к этой функции.")
            return
        
        await message.answer(
            "Введите ID пользователя, которого нужно сделать администратором:"
        )
        # Could set state here for admin operations
    except Exception as e:
        logging.error(f"Error in add admin prompt: {e}")
        await message.answer("Произошла ошибка.")

@admin_router.message(F.text == "Удалить админа")
async def remove_admin_prompt(message: Message, state: FSMContext):
    """Prompt for removing an admin"""
    try:
        user_id = message.from_user.id
        
        if user_id not in get_admins_id():
            await message.answer("У вас нет доступа к этой функции.")
            return
        
        admins = get_admins_id()
        admin_list = "Список администраторов:\n\n"
        
        for admin_id in admins:
            admin_list += f"ID: {admin_id}\n"
        
        await message.answer(
            admin_list + "\nВведите ID администратора, которого нужно удалить:"
        )
        # Could set state here for admin operations
    except Exception as e:
        logging.error(f"Error in remove admin prompt: {e}")
        await message.answer("Произошла ошибка.")

@admin_router.message(Command(commands=["setup_admin"]))
async def setup_admin_command(message: Message):
    """Set up the first admin of the system"""
    try:
        user_id = message.from_user.id
        
        # Get current admins
        admins = get_admins_id()
        
        # If no admins yet or user is already an admin
        if not admins or user_id in admins:
            add_admin(user_id)
            await message.answer("Вы добавлены как администратор системы.")
        else:
            await message.answer("Администраторы уже настроены. Только существующий администратор может добавить новых.")
    except Exception as e:
        logging.error(f"Error setting up admin: {e}")
        await message.answer("Произошла ошибка при настройке администратора.")

# ============================
# MATCHMAKING HANDLERS AND FUNCTIONS
# ============================

async def get_user_profile(user_id: int) -> str:
    """Get user profile information from JSON storage"""
    try:
        user_data = get_user(user_id)
        if not user_data:
            return "Информация о пользователе недоступна"
        
        return f"Имя: {user_data.get('name', 'Не указано')}\nПол: {user_data.get('gender', 'Не указан')}"
    except Exception as e:
        logging.error(f"Error getting user profile: {e}")
        return "Ошибка при получении профиля пользователя"

@matchmaking_router.message(Command(commands=["lobby"]))
async def lobby_command(message: Message):
    """Check lobby status command"""
    try:
        logging.info(f"Handling lobby command from user {message.from_user.id}")
        user_id = message.from_user.id
        
        # Only admins can check lobby status
        if user_id not in get_admins_id():
            await message.answer("Эта команда доступна только администраторам.")
            return
        
        male_count = len([uid for uid, gender in waiting_users.items() if gender == Gender.MALE])
        female_count = len([uid for uid, gender in waiting_users.items() if gender == Gender.FEMALE])
        
        await message.answer(
            f"Статус зала ожидания:\n"
            f"Мужчин: {male_count}\n"
            f"Женщин: {female_count}\n"
            f"Всего: {len(waiting_users)}\n\n"
            f"Активных комнат: {len(active_rooms)}"
        )
    except Exception as e:
        logging.error(f"Error checking lobby status: {e}")
        await message.answer("Произошла ошибка при проверке статуса зала ожидания.")

@matchmaking_router.message(Command(commands=["next_round"]))
async def start_matchmaking(message: Message, bot: Bot):
    """Start matchmaking round command"""
    try:
        logging.info(f"Handling next_round command from user {message.from_user.id}")
        user_id = message.from_user.id
        
        # Check if the user is an admin
        if user_id not in get_admins_id():
            await message.answer("Эта команда доступна только администраторам.")
            return
        
        # Count users by gender
        males = [uid for uid, gender in waiting_users.items() if gender == Gender.MALE]
        females = [uid for uid, gender in waiting_users.items() if gender == Gender.FEMALE]
        
        male_count = len(males)
        female_count = len(females)
        
        # Calculate how many rooms we can create (with 1:3 ratio)
        female_hero_rooms = min(female_count, male_count // 3)
        male_hero_rooms = min(male_count, female_count // 3)
        
        total_rooms = female_hero_rooms + male_hero_rooms
        
        if total_rooms == 0:
            await message.answer(
                f"Недостаточно участников для создания комнат. "
                f"Текущее соотношение М:Ж = {male_count}:{female_count}. "
                f"Нужно соотношение 3:1 или 1:3."
            )
            return
        
        # Create rooms
        created_rooms = []
        
        # Create rooms with female heroes
        for i in range(female_hero_rooms):
            # Take one female as hero
            hero_id = females.pop(0)
            # Take three males as pretenders
            pretender_ids = [males.pop(0) for _ in range(3)]
            
            room_id = f"room_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}"
            room = {
                "id": room_id,
                "state": RoomState.WAITING,
                "hero": {"id": hero_id, "gender": Gender.FEMALE},
                "pretenders": [{"id": pid, "gender": Gender.MALE, "index": idx+1} for idx, pid in enumerate(pretender_ids)],
                "admin_id": user_id,  # Admin who initiated the room
                "messages": [],
                "current_question": None,
                "current_target": None,
                "questions_asked": 0,
                "selected_pretender": None
            }
            
            active_rooms[room_id] = room
            
            # Map users to their rooms
            user_to_room[hero_id] = room_id
            for pid in pretender_ids:
                user_to_room[pid] = room_id
                
            # Remove users from waiting list
            waiting_users.pop(hero_id)
            for pid in pretender_ids:
                waiting_users.pop(pid)
                
            created_rooms.append(room)
        
        # Create rooms with male heroes (similar logic)
        for i in range(male_hero_rooms):
            hero_id = males.pop(0)
            pretender_ids = [females.pop(0) for _ in range(3)]
            
            room_id = f"room_{datetime.now().strftime('%Y%m%d%H%M%S')}_{female_hero_rooms + i}"
            room = {
                "id": room_id,
                "state": RoomState.WAITING,
                "hero": {"id": hero_id, "gender": Gender.MALE},
                "pretenders": [{"id": pid, "gender": Gender.FEMALE, "index": idx+1} for idx, pid in enumerate(pretender_ids)],
                "admin_id": user_id,  # Admin who initiated the room
                "messages": [],
                "current_question": None,
                "current_target": None,
                "questions_asked": 0,
                "selected_pretender": None
            }
            
            active_rooms[room_id] = room
            
            user_to_room[hero_id] = room_id
            for pid in pretender_ids:
                user_to_room[pid] = room_id
                
            waiting_users.pop(hero_id)
            for pid in pretender_ids:
                waiting_users.pop(pid)
                
            created_rooms.append(room)
        
        # Notify admin
        await message.answer(
            f"Создано {len(created_rooms)} комнат. "
            f"Осталось в зале ожидания: {len(waiting_users)} пользователей."
        )
        
        # Notify all users about their roles and rooms and automatically start rooms
        for room in created_rooms:
            hero_id = room["hero"]["id"]
            await bot.send_message(
                hero_id,
                f"Вы выбраны героем в комнате {room['id']}! Бот будет задавать вопросы вам и претендентам."
            )
            
            for pretender in room["pretenders"]:
                pretender_id = pretender["id"]
                await bot.send_message(
                    pretender_id,
                    f"Вы претендент №{pretender['index']} в комнате {room['id']}! Бот будет задавать вопросы."
                )
            
            # Automatically start the room
            await start_room(bot, room)
    except Exception as e:
        logging.error(f"Error in matchmaking: {e}")
        await message.answer("Произошла ошибка при создании комнат.")

async def start_room(bot: Bot, room: Dict):
    """Start a room session with the bot as the host"""
    try:
        room["state"] = RoomState.ACTIVE
        
        # Send introduction messages to all participants
        hero_id = room["hero"]["id"]
        hero_info = await get_user_profile(hero_id)
        
        # Send hero info to pretenders
        for pretender in room["pretenders"]:
            pretender_id = pretender["id"]
            await bot.send_message(
                pretender_id,
                f"Начинаем игру!\n\nИнформация о герое:\n{hero_info}"
            )
        
        # Send pretender info to hero
        pretender_info = ""
        for pretender in room["pretenders"]:
            pretender_id = pretender["id"]
            profile = await get_user_profile(pretender_id)
            pretender_info += f"Претендент {pretender['index']}:\n{profile}\n\n"
        
        await bot.send_message(
            hero_id,
            f"Начинаем игру!\n\nИнформация о претендентах:\n{pretender_info}"
        )
        
        # Bot automatically asks the first question to the hero
        await ask_next_question(bot, room)
    except Exception as e:
        logging.error(f"Error starting room: {e}")
        # Try to notify participants about the error
        try:
            all_ids = [room["hero"]["id"]] + [p["id"] for p in room["pretenders"]]
            for user_id in all_ids:
                await bot.send_message(user_id, "Произошла ошибка при запуске комнаты.")
        except:
            pass

async def ask_next_question(bot: Bot, room: Dict):
    """Bot automatically selects next question and target"""
    try:
        if room["state"] != RoomState.ACTIVE:
            return
        
        # Determine who should receive the next question based on turn order
        # First question goes to hero, then alternates between pretenders and hero
        question_count = room["questions_asked"]
        
        if question_count == 0 or question_count % 4 == 0:
            # Ask hero first, then every 4th question
            target = "hero"
            target_id = room["hero"]["id"]
            target_name = "Герою"
        else:
            # Ask pretenders in order
            pretender_idx = (question_count % 4)
            if pretender_idx > 3:  # Safety check
                pretender_idx = 1
                
            target = f"pretender_{pretender_idx}"
            target_id = next(p["id"] for p in room["pretenders"] if p["index"] == pretender_idx)
            target_name = f"Претенденту {pretender_idx}"
        
        room["current_target"] = target
        
        # Select a question from the pool
        used_questions = [msg["text"] for msg in room["messages"] if msg["type"] == "question"]
        available_questions = [q for q in QUESTIONS if q not in used_questions]
        
        if not available_questions:
            # If we've used all questions, repeat some or end the round
            if len(used_questions) >= 8:  # After 8 questions (2 rounds), move to voting
                await start_voting(bot, room)
                return
            else:
                # Reset the question pool for another round
                available_questions = QUESTIONS
        
        question_text = random.choice(available_questions)
        room["current_question"] = question_text
        
        # Send question to the target
        await bot.send_message(
            target_id,
            f"Вопрос для вас: {question_text}\n\nПожалуйста, ответьте на вопрос."
        )
        
        # Notify all other participants about the question
        participants = [room["hero"]["id"]] + [p["id"] for p in room["pretenders"]]
        for participant_id in participants:
            if participant_id != target_id:
                await bot.send_message(
                    participant_id,
                    f"{target_name} задан вопрос: {question_text}\n\nОжидайте ответ."
                )
        
        # Record question in room history
        room["messages"].append({
            "type": "question",
            "from": "host",
            "to": target,
            "text": question_text,
            "timestamp": datetime.now().isoformat()
        })
        
        room["questions_asked"] += 1
    except Exception as e:
        logging.error(f"Error asking next question: {e}")
        # Try to recover and continue
        try:
            if "current_target" in room and room["current_target"]:
                target_id = (room["hero"]["id"] if room["current_target"] == "hero" 
                            else next(p["id"] for p in room["pretenders"] 
                                    if p["index"] == int(room["current_target"].split("_")[1])))
                await bot.send_message(
                    target_id,
                    "Произошла ошибка при задании вопроса. Пожалуйста, напишите любой ответ, чтобы продолжить."
                )
        except:
            # If recovery fails, try to move to voting
            try:
                await start_voting(bot, room)
            except:
                pass

@matchmaking_router.message(Command(commands=["end_room"]))
async def end_room_command(message: Message, bot: Bot):
    """Force end a room command"""
    try:
        logging.info(f"Handling end_room command from user {message.from_user.id}")
        user_id = message.from_user.id
        
        # Only admins can force end rooms
        if user_id not in get_admins_id():
            await message.answer("Эта команда доступна только администраторам.")
            return
        
        # Get room ID from command arguments
        args = message.text.split()
        if len(args) < 2:
            await message.answer("Укажите ID комнаты: /end_room [room_id]")
            return
        
        room_id = args[1]
        if room_id not in active_rooms:
            await message.answer(f"Комната {room_id} не найдена.")
            return
        
        room = active_rooms[room_id]
        
        await start_voting(bot, room)
        await message.answer(f"Комната {room_id} переведена на этап голосования.")
    except Exception as e:
        logging.error(f"Error ending room: {e}")
        await message.answer("Произошла ошибка при завершении комнаты.")

# Handler for participant answers
@matchmaking_router.message(lambda message: message.from_user.id in user_to_room)
async def handle_answer(message: Message, bot: Bot):
    try:
        user_id = message.from_user.id
        room_id = user_to_room.get(user_id)
        
        if not room_id or room_id not in active_rooms:
            return
        
        room = active_rooms[room_id]
        
        if room["state"] != RoomState.ACTIVE:
            return
        
        # Determine user role
        user_role = None
        user_name = None
        
        if room["hero"]["id"] == user_id:
            user_role = "hero"
            user_name = "Герой"
        else:
            for pretender in room["pretenders"]:
                if pretender["id"] == user_id:
                    user_role = f"pretender_{pretender['index']}"
                    user_name = f"Претендент {pretender['index']}"
                    break
        
        if not user_role or user_role != room["current_target"]:
            await message.answer("Сейчас не ваша очередь отвечать на вопрос.")
            return
        
        answer_text = message.text
        
        # Record the answer
        room["messages"].append({
            "type": "answer",
            "from": user_role,
            "text": answer_text,
            "question": room["current_question"],
            "timestamp": datetime.now().isoformat()
        })
        
        # Broadcast the answer to all participants
        participants = [room["hero"]["id"]] + [p["id"] for p in room["pretenders"]]
        for participant_id in participants:
            if participant_id != user_id:
                await bot.send_message(
                    participant_id,
                    f"{user_name} ответил: {answer_text}"
                )
        
        # Notify the user that their answer was recorded
        await message.answer("Ваш ответ записан.")
        
        # Check if it's time to move to voting (after a certain number of questions)
        if room["questions_asked"] >= 8:  # 2 questions per person (hero + 3 pretenders)
            await start_voting(bot, room)
        else:
            # Bot automatically asks the next question
            await asyncio.sleep(2)  # Small delay before next question for readability
            await ask_next_question(bot, room)
    except Exception as e:
        logging.error(f"Error handling answer: {e}")
        # Try to continue to the next question
        try:
            room_id = user_to_room.get(message.from_user.id)
            if room_id and room_id in active_rooms:
                room = active_rooms[room_id]
                await ask_next_question(bot, room)
        except:
            pass

async def start_voting(bot: Bot, room: Dict):
    """Start the voting phase where hero selects a pretender"""
    try:
        room["state"] = RoomState.VOTING
        
        # Create voting keyboard for the hero
        voting_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=f"Выбрать претендента 1")],
                [KeyboardButton(text=f"Выбрать претендента 2")],
                [KeyboardButton(text=f"Выбрать претендента 3")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        # Notify hero to vote
        await bot.send_message(
            room["hero"]["id"],
            "Пожалуйста, выберите одного претендента:",
            reply_markup=voting_keyboard
        )
        
        # Notify other participants
        for pretender in room["pretenders"]:
            await bot.send_message(
                pretender["id"],
                "Раунд вопросов завершен. Герой выбирает претендента."
            )
        
        # Notify admin if one initiated the room
        if room.get("admin_id"):
            await bot.send_message(
                room["admin_id"],
                "Раунд вопросов завершен. Герой выбирает претендента."
            )
    except Exception as e:
        logging.error(f"Error starting voting: {e}")
        # Try to end the room anyway
        try:
            await end_room(bot, room)
        except:
            pass

# Handler for hero's vote
@matchmaking_router.message(lambda message: message.from_user.id in user_to_room)
async def handle_vote(message: Message, bot: Bot):
    try:
        user_id = message.from_user.id
        room_id = user_to_room.get(user_id)
        
        if not room_id or room_id not in active_rooms:
            return
        
        room = active_rooms[room_id]
        
        if room["state"] != RoomState.VOTING or room["hero"]["id"] != user_id:
            return
        
        # Get selected pretender number
        try:
            pretender_num = int(message.text.split()[-1])
            if pretender_num < 1 or pretender_num > len(room["pretenders"]):
                raise ValueError("Invalid pretender number")
            
            selected_pretender = next(p for p in room["pretenders"] if p["index"] == pretender_num)
        except (ValueError, StopIteration):
            await message.answer("Некорректный номер претендента.")
            return
        
        room["selected_pretender"] = selected_pretender
        
        # Notify all participants about the choice
        participants = [room["hero"]["id"]] + [p["id"] for p in room["pretenders"]]
        for participant_id in participants:
            if participant_id == user_id:
                await bot.send_message(
                    participant_id,
                    f"Вы выбрали претендента {pretender_num}.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
            elif participant_id == selected_pretender["id"]:
                await bot.send_message(
                    participant_id,
                    f"Поздравляем! Герой выбрал вас.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
            else:
                await bot.send_message(
                    participant_id,
                    f"Герой выбрал претендента {pretender_num}.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
        
        # End the room
        await end_room(bot, room)
    except Exception as e:
        logging.error(f"Error handling vote: {e}")
        # Try to end the room anyway
        try:
            room_id = user_to_room.get(message.from_user.id)
            if room_id and room_id in active_rooms:
                room = active_rooms[room_id]
                await end_room(bot, room)
        except:
            pass

async def end_room(bot: Bot, room: Dict):
    """End a room and generate the dialogue file"""
    try:
        room["state"] = RoomState.FINISHED
        
        # Generate dialogue file
        dialogue = generate_dialogue(room)
        
        # Save dialogue to file
        os.makedirs(DIALOGUES_DIR, exist_ok=True)
        file_path = os.path.join(DIALOGUES_DIR, f"dialogue_{room['id']}.txt")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(dialogue)
        
        # Send dialogue file to admin if one initiated the room
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                file_data = f.read()
                if room.get("admin_id"):
                    await bot.send_document(
                        room["admin_id"],
                        types.BufferedInputFile(
                            file_data,
                            filename=f"dialogue_{room['id']}.txt"
                        ),
                        caption=f"Диалог комнаты {room['id']}"
                    )
        
        # Get all participants
        all_participants = [room["hero"]["id"]] + [p["id"] for p in room["pretenders"]]
        
        # Remove users from room mapping
        user_to_room.pop(room["hero"]["id"], None)
        for pretender in room["pretenders"]:
            user_to_room.pop(pretender["id"], None)
        
        # Add users back to waiting lobby
        waiting_users[room["hero"]["id"]] = Gender(room["hero"]["gender"])
        for pretender in room["pretenders"]:
            waiting_users[pretender["id"]] = Gender(pretender["gender"])
        
        # Remove room
        active_rooms.pop(room["id"])
        
        # Notify admin that all users are back in the lobby
        if room.get("admin_id"):
            await bot.send_message(
                room["admin_id"],
                f"Комната {room['id']} завершена. Все участники возвращены в зал ожидания."
            )
            
        # Return all participants to main menu
        for participant_id in all_participants:
            try:
                user_name = message.from_user.first_name if 'message' in locals() else ""
                if not user_name:
                    user_data = get_user(participant_id)
                    user_name = user_data.get("name", "") if user_data else ""
                
                await bot.send_message(
                    participant_id,
                    f"Игра завершена! Возвращаемся в главное меню.",
                    reply_markup=functionality
                )
            except Exception as e:
                logging.error(f"Error returning user {participant_id} to main menu: {e}")
                
    except Exception as e:
        logging.error(f"Error ending room: {e}")
        # Try to clean up as much as possible
        try:
            # Get all participants before cleanup
            all_participants = []
            if "hero" in room and "id" in room["hero"]:
                all_participants.append(room["hero"]["id"])
            if "pretenders" in room:
                for pretender in room["pretenders"]:
                    if "id" in pretender:
                        all_participants.append(pretender["id"])
            
            # Remove users from room mapping
            if "hero" in room and "id" in room["hero"]:
                user_to_room.pop(room["hero"]["id"], None)
            if "pretenders" in room:
                for pretender in room["pretenders"]:
                    if "id" in pretender:
                        user_to_room.pop(pretender["id"], None)
            
            # Add users back to waiting lobby if possible
            if "hero" in room and "id" in room["hero"] and "gender" in room["hero"]:
                waiting_users[room["hero"]["id"]] = Gender(room["hero"]["gender"])
            if "pretenders" in room:
                for pretender in room["pretenders"]:
                    if "id" in pretender and "gender" in pretender:
                        waiting_users[pretender["id"]] = Gender(pretender["gender"])
            
            # Remove room
            if "id" in room:
                active_rooms.pop(room["id"], None)
                
            # Return all participants to main menu
            for participant_id in all_participants:
                try:
                    await bot.send_message(
                        participant_id,
                        "Произошла ошибка при завершении игры. Возвращаемся в главное меню.",
                        reply_markup=functionality
                    )
                except Exception:
                    pass
        except Exception as ex:
            logging.error(f"Error during room cleanup: {ex}")

def generate_dialogue(room: Dict) -> str:
    """Generate a text dialogue from room messages"""
    try:
        dialogue = f"Диалог комнаты {room['id']}\n"
        dialogue += f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        dialogue += f"Герой: Пользователь {room['hero']['id']}\n"
        
        for pretender in room["pretenders"]:
            dialogue += f"Претендент {pretender['index']}: Пользователь {pretender['id']}\n"
        
        dialogue += f"Ведущий: Бот\n\n"
        
        if room["selected_pretender"]:
            dialogue += f"РЕЗУЛЬТАТ: Герой выбрал претендента {room['selected_pretender']['index']}\n"
        else:
            dialogue += f"РЕЗУЛЬТАТ: Выбор не был сделан\n"
        
        dialogue += "=" * 50 + "\n\n"
        
        # Sort messages by timestamp
        sorted_messages = sorted(room["messages"], key=lambda msg: msg["timestamp"])
        
        # Group messages by question
        current_question = None
        for msg in sorted_messages:
            if msg["type"] == "question":
                current_question = msg
                if msg["to"] == "hero":
                    dialogue += f"Вопрос герою: {msg['text']}\n\n"
                else:
                    pretender_num = msg["to"].split("_")[1]
                    dialogue += f"Вопрос претенденту {pretender_num}: {msg['text']}\n\n"
            elif msg["type"] == "answer" and current_question:
                if msg["from"] == "hero":
                    dialogue += f"Ответ героя: {msg['text']}\n\n"
                else:
                    pretender_num = msg["from"].split("_")[1]
                    dialogue += f"Ответ претендента {pretender_num}: {msg['text']}\n\n"
                    dialogue += "-" * 30 + "\n\n"
        
        return dialogue
    except Exception as e:
        logging.error(f"Error generating dialogue: {e}")
        return f"Ошибка при генерации диалога комнаты {room['id']}"

# ============================
# BOT SETUP AND STARTUP FUNCTIONS
# ============================

async def set_commands(bot: Bot):
    """Set up bot commands with descriptions"""
    try:
        commands = [
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="auth", description="Регистрация"),
            BotCommand(command="admin", description="Административное меню"),
            BotCommand(command="id", description="Получение своего id"),
            BotCommand(command="show_db", description="Показать всех пользователей"),
            BotCommand(command="end", description="Сброс состояния"),
            # Добавляем команды для матчмейкинга
            BotCommand(command="next_round", description="Запуск раунда матчмейкинга"),
            BotCommand(command="lobby", description="Статус зала ожидания"),
            BotCommand(command="end_room", description="Завершить комнату"),
            BotCommand(command="setup_admin", description="Настроить первого администратора")
        ]
        # Устанавливаем команды для бота
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    except Exception as e:
        logging.error(f"Error setting commands: {e}")

async def main():
    """Main function to start the bot"""
    try:
        # Initialize JSON storage
        init_json_storage()
        
        # Create all necessary directories
        os.makedirs(LOG_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(DIALOGUES_DIR, exist_ok=True)
        os.makedirs("app/temp", exist_ok=True)
        os.makedirs("data/numerology", exist_ok=True)
        os.makedirs("app/bot_messages", exist_ok=True)
        
        logging.info("Bot is starting...")
        
        # Check for bot token
        if not BOT_TOKEN:
            logging.error("BOT_TOKEN is empty or not set!")
            logging.warning("Bot will continue running but won't be able to connect to Telegram.")
            # Keep running for debugging purposes
            while True:
                await asyncio.sleep(60)  # Sleep to prevent CPU usage
                logging.info("Bot is still running despite missing token.")
        
        logging.info(f"Using token: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:] if len(BOT_TOKEN) > 10 else '***'}")
        bot = Bot(token=BOT_TOKEN)
        
        # Verify connection to Telegram
        try:
            me = await bot.get_me()
            logging.info(f"Successfully connected as @{me.username}")
        except Exception as e:
            logging.error(f"Failed to connect to Telegram: {e}")
            logging.warning("Bot will continue running but won't be able to respond to messages.")
            while True:
                await asyncio.sleep(60)  # Sleep to prevent CPU usage
                logging.info("Bot is still running despite connection failure.")
        
        # Setup dispatcher and routers
        dp = Dispatcher(storage=storage)
        dp.include_router(matchmaking_router)
        dp.include_router(router)
        dp.include_router(login_router)
        dp.include_router(admin_router)
        
        # Set up commands
        try:
            await set_commands(bot)
        except Exception as e:
            logging.error(f"Failed to set commands: {e}")
            # Continue anyway
        
        # Start polling
        logging.info("Starting polling...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, timeout=5)
    except Exception as e:
        logging.error(f"Error in main function: {e}", exc_info=True)
        # Keep the process running
        while True:
            await asyncio.sleep(60)
            logging.info("Bot is still running despite error in main function.")

if __name__ == "__main__":
    # Using while True loop to ensure the container never exits
    while True:
        try:
            # Run the main function
            asyncio.run(main())
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt, but container will continue running")
        except Exception as e:
            logging.error(f"Critical error in main loop: {e}", exc_info=True)
        
        # If we get here, there was an error, wait before restarting
        logging.info("Bot crashed, restarting in 5 seconds...")
        time.sleep(5)