from dotenv import load_dotenv
from aiogram import Dispatcher, Router, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from app.sql_database.User import UserDatabase

load_dotenv(override=True)

class AuthStates(StatesGroup):
    waiting_for_tgname = State()

LOG_DIR = "./data/bot_logs"

db_user = UserDatabase()

router = Router()
storage = MemoryStorage()
dispatcher = Dispatcher(storage=storage)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Стать дежурным админом"),
         KeyboardButton(text="Добавить админа")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

@router.message(Command(commands=["admin"]))
async def admin_command(message: Message):
    user_id = message.from_user.id
    if user_id in db_user.get_admins_id():
        await message.answer("Административное меню:", 
                             reply_markup=admin_keyboard)
    else:
        await message.answer("У вас нет доступа к этой команде.")

@router.message(F.text == "👤 Стать дежурным админом")
async def update_vector_database(message: Message):
    user_id = message.from_user.id
    if not db_user.exists(user_id):
        await message.answer("Вы не зарегистрированы.")
        return

    if user_id not in db_user.get_admins_id():
        await message.answer("Эта команда доступна только ADMIN-пользователю.")
        return
    
    db_user.set_access_rights(user_id, "duty_admin")
    await message.answer("Теперь вы дежурный админ. Все запросы будут поступать вам.")

@router.message(F.text == "Добавить админа")
async def add_admin(message: Message, state: FSMContext):
    await message.answer("Введите @telegram_name нового админа")
    await state.set_state(AuthStates.waiting_for_tgname)

@router.message(AuthStates.waiting_for_tgname)
async def handle_new_admin(message: Message, state: FSMContext):
    tg_name = message.text.strip()
    user_id = db_user.get_user_id_by_tgname(tg_name.replace('@', ''))
    if user_id:
        db_user.set_access_rights(user_id, 'admin')
        await message.answer("Новый админ подтвержден")
    else:
        await message.answer("Нет такого пользователя")

@router.message(Command(commands=["show_duty_admin"]))
async def cmd_show_duty_admin(message: Message):
    duty_id = db_user.get_duty_admin_id()
    if duty_id == 0:
        await message.answer("Дежурный админ не назначен.")
        return
    
    d_data = db_user.get_user(duty_id)
    tg_link = db_user.get_user_telegram_link(duty_id)
    text = (
        f"👨‍💼 Текущий дежурный администратор:\n\n"
        f'👤 Имя: {d_data["username"]}\n'
        f'📱 Telegram: {tg_link}\n'
    )
    await message.answer(text)