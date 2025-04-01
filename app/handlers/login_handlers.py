from dotenv import load_dotenv, set_key, find_dotenv
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import Message
import logging

from app.sql_database.User import UserDatabase

load_dotenv(override=True)

LOG_DIR = "./data/bot_logs"

db_user = UserDatabase()

router = Router()
storage = MemoryStorage()
dispatcher = Dispatcher(storage=storage)

class AuthStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_auth_ok = State()

@router.message(Command(commands=["auth"]))
async def auth(message: Message, state: FSMContext):
    """"
    Запрашиваем у пользователя ФИО, если он не зарегистрирован
    """
    user_id = message.from_user.id
    print(user_id)
    if db_user.exists(user_id):
        # if db_user.is_approved(user_id):
        await message.answer("Вы уже зарегистрированы и одобрены администратором. Можете пользоваться ботом.")
    # else:
    #     await message.answer("Вы зарегистрированы, но ваша учетная запись ожидает одобрения администратором. Пожалуйста, подождите.")
        return
    else:
        await message.answer("Для регистрации введите, пожалуйста, ваше ФИО:")
        await state.set_state(AuthStates.waiting_for_username)

@router.message(AuthStates.waiting_for_username)
async def handle_user(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # if user_id in db_user.get_admins_id():
        # user_data = db_user.get_user(user_id)
        # if user_data.get("access_rights") == "duty_admin":
        #     await message.answer(
        #         "Вы зарегистрированы как администратор системы!\n"
        #         "Вам автоматически присвоены права дежурного администратора."
        #     )
        # else:
        #     await message.answer(
        #         "Вы зарегистрированы как администратор системы!"
        #     )
        
    
    username = message.text.strip()
    tg_link = message.from_user.username
    db_user.insert(user_id=user_id, 
                    username=username,
                    telegram_username=tg_link)
    await message.answer(
            "Спасибо! Ваши данные записаны."
            # "Ожидайте, пока дежурный администратор одобрит вашу регистрацию."
            )

    # ========== Отправка уведомления деж админу =============
    # duty_admin_id = db_user.get_duty_admin_id()
    # admin_list = [duty_admin_id] if duty_admin_id else db_user.get_admins_id()
    # admin_text = (
    # f"📨 Запрос на доступ\n\n"
    # f"👤 Пользователь: {username}\n"
    # f"📱 Telegram: @{tg_link}\n"
    # f"🆔 ID: {user_id}\n\n"
    # " Пользователь запросил доступ. Для одобрения используйте команду:\n"
    # "👉 `/approve <ID>`"
    # )

    # for admin_id in admin_list:
    #     try:
    #         await message.bot.send_message(admin_id, admin_text)
    #     except Exception as e:
    #         logging.error(f"Ошибка при отправке уведомления админу {admin_id}: {e}")
    # await state.clear()

@router.message(Command(commands=["approve"]))
async def cmd_approve(message: Message):
    user_id = message.from_user.id

    if not db_user.exists(user_id):
        await message.answer("Пользователь не найден. Вас нет в системе")
        return
    
    # user_data = db_user.get_user(user_id)
    # if user_data.get("access_rights") not in ("duty_admin", "admin") and user_id not in ADMINS:
    #     await message.answer("У вас нет прав на выполнение этой команды.")
    #     return

    parts = message.text.split()
    # if len(parts) < 2:
    #     await message.answer("Используйте: /approve <ID>")
    #     return

    target_user_id = parts[1]
    if not target_user_id.isdigit():
        await message.answer("user_id должен быть числом")
        return

    target_user_id = int(target_user_id)
    if not db_user.exists(target_user_id):
        await message.answer(f"Пользователя с id={target_user_id} нет в Базе данных")
        return

    db_user.approve_user(target_user_id)
    target_user_data = db_user.get_user(target_user_id)
    tg_link = db_user.get_user_telegram_link(target_user_id)

    # await message.answer(
    # f"""
    # ✅ Пользователь успешно одобрен!\n\n
    
    # 👤 ФИО: {target_user_data["username"]}\n
    # 📱 Telegram: {tg_link}\n
    # 🆔 ID: {target_user_id}
    # """
    # )
    # ========== Уведомление пользователя, что он одобрен ===========
    # try:
    #     await message.bot.send_message(
    #         target_user_id,
    #         "🎉 *Поздравляем!* Ваш доступ был успешно одобрен дежурным администратором. Теперь вы можете пользоваться ботом!"
    #     )
    # except Exception as e:
    #     logging.error(f"Ошибка при отправке уведомления пользователю: {e}")

@router.message(Command(commands=["delete_user"]))
async def cmd_delete_user(message: Message):
    user_id = message.from_user.id

    user_data = db_user.get_user(user_id)
    # if not db_user.exists(user_id) or user_data.get("access_rights") != "duty_admin":
        # await message.answer("У вас нет прав на выполнение этой команды.")
    return   
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Некорректная команда. Используйте: /delete_user <ID1> <ID2> ...")
        return
    
    target_user_ids = []
    for user_id_str in parts[1:]:
        if user_id_str.isdigit():
            target_user_ids.append(int(user_id_str))
        else:
            await message.answer(f"Некорректный ID: {user_id_str}")

    invalid_ids = []
    deleted_ids = []

    for target_user_id in target_user_ids:
        if not db_user.exists(target_user_id):
            invalid_ids.append(target_user_id)
        else:
            try:
                db_user.delete(target_user_id)
                deleted_ids.append(target_user_id)
            except Exception as e:
                logging.error(f"Ошибка при удалении пользователя {target_user_id}: {e}")
                invalid_ids.append(target_user_id)

    response = ""
    if deleted_ids:
        response += f'✅ Пользователи с ID {", ".join(map(str, deleted_ids))} успешно удалены.\n'
    if invalid_ids:
        response += f'❌ Не удалось удалить пользователей с ID {", ".join(map(str, invalid_ids))}. Проверьте их корректность или наличие в базе данных.'

    await message.answer(response)
    
@router.message(Command(commands=["show_db"]))
async def cmd_show_db(message: Message):
    # user_id = message.from_user.id
    # if user_id not in db_user.get_admins_id():
    #     await message.answer("У вас нет прав на выполнение этой команды.")
    # return
    
    try:
        rows = db_user.get_all_users()

        if not rows:
            await message.answer("База данных пуста.")
            return

        text = "📊 *Содержимое базы данных:*\n\n"
        for row in rows:
            text += (
                f"👤 Пользователь:\n"
                f'🆔 ID: {row["user_id"]}\n'
                f'👨‍💻 Имя (ФИО): {row["username"]}\n'
                f'📱 Telegram-ник: @{row["telegram_username"] or "не указан"}\n'
                # f'📋 Статус: {"✅ Одобрен" if row["approved"] else "⏳ Ожидает одобрения"}\n'
                # f'🔑 Права доступа: {row["access_rights"]}\n'
                # f'{"=" * 20}\n'
            )
        max_length = 4096
        for i in range(0, len(text), max_length):
            chunk = text[i:i + max_length]
            await message.answer(chunk)

    except Exception as e:
        logging.error(f"Ошибка при получении данных из БД {e}")
        await message.answer("Произошла ошибка при получении данных из БД.")
