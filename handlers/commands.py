# handlers/commands.py
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

import database as db
import keyboards
from services.survey import send_weekly_usage_survey

# Глобальная переменная для бота (будет установлена в main.py)
_bot: Bot = None


def set_bot(bot: Bot):
    """Установить экземпляр бота для использования в handlers"""
    global _bot
    _bot = bot


def register_commands_handlers(dp: Dispatcher):
    """Регистрация обработчиков команд"""
    
    @dp.message(Command("start"))
    async def cmd_start(message: Message):
        """Приветствие"""
        db.init_db()  # Гарантируем, что БД создана
        await message.answer(
            f"Привет, {message.from_user.first_name}!\n"
            "Я помогу управлять регулярными платежами.\n"
            "Выбери действие в меню:",
            reply_markup=keyboards.get_main_kb()
        )

    @dp.message(Command("help"))
    async def cmd_help(message: Message):
        help_text = (
            "<b>Как работает этот бот:</b>\n\n"
            "1️⃣ <b>Добавление:</b> Нажми '➕ Добавить ежемесячный платёж'. Бот спросит название, цену, "
            "категорию и твою личную оценку полезности (от 1 до 10).\n\n"
            "2️⃣ <b>Аналитика:</b> Я построю график расходов по категориям и посчитаю, сколько ты тратишь в месяц и в год.\n\n"
            "3️⃣ <b>Оптимизация:</b> На основе твоих оценок я вычислю 'стоимость единицы удовольствия'. "
            "Если сервис дорогой, но ты оценил его полезность низко — я предложу его отключить.\n\n"
            "4️⃣ <b>Еженедельные опросы:</b> Каждую неделю бот будет спрашивать, как часто вы использовали каждую подписку.\n\n"
            "5️⃣ <b>Команда /survey:</b> Вызовите опрос вручную в любое время.\n\n"
        )
        await message.answer(help_text, parse_mode="HTML")

    @dp.message(Command("survey"))
    async def cmd_survey(message: Message):
        """Ручной вызов еженедельного опроса"""
        if _bot:
            await send_weekly_usage_survey(_bot, message.from_user.id)

