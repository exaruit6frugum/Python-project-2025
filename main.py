# main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
import database as db
import utils

# Настройка логирования (чтобы видеть ошибки в консоли)
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()


# --- FSM: Машина состояний для добавления подписки ---
class AddSubState(StatesGroup):
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_category = State()
    waiting_for_importance = State()


# --- Клавиатуры (UI) ---
def get_main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="➕ Добавить ежемесячный платёж")
    kb.button(text="📋 Список платежей")
    kb.button(text="📊 Аналитика")
    kb.button(text="💡 Советы по оптимизации")
    kb.button(text="🗑 Удалить платёж")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


def get_categories_kb():
    kb = ReplyKeyboardBuilder()
    for cat in config.CATEGORIES:
        kb.button(text=cat)
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=True)


# --- Обработчики команд ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Приветствие"""
    db.init_db()  # Гарантируем, что БД создана
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n"
        "Я помогу управлять регулярными платежами.\n"
        "Выбери действие в меню:",
        reply_markup=get_main_kb()
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "<b>Как работает этот бот:</b>\n\n"
        "1️⃣ <b>Добавление:</b> Нажми '➕ Добавить ежемесячный платёж'. Бот спросит название, цену, "
        "категорию и твою личную оценку полезности (от 1 до 10).\n\n"
        "2️⃣ <b>Аналитика:</b> Я построю график расходов по категориям и посчитаю, сколько ты тратишь в месяц и в год.\n\n"
        "3️⃣ <b>Оптимизация:</b> На основе твоих оценок я вычислю 'стоимость единицы удовольствия'. "
        "Если сервис дорогой, но ты оценил его полезность низко — я предложу его отключить.\n\n"
    )
    await message.answer(help_text, parse_mode="HTML")


# --- Логика добавления подписки (FSM) ---

@dp.message(F.text == "➕ Добавить ежемесячный платёж")
async def start_add_sub(message: types.Message, state: FSMContext):
    await message.answer("Введите название сервиса (например, Netflix):")
    await state.set_state(AddSubState.waiting_for_name)


@dp.message(AddSubState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько вы платите в месяц (в рублях)?")
    await state.set_state(AddSubState.waiting_for_price)


@dp.message(AddSubState.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    # Проверка на число
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число.")
        return

    await state.update_data(price=float(message.text))
    await message.answer("Выберите категорию:", reply_markup=get_categories_kb())
    await state.set_state(AddSubState.waiting_for_category)


@dp.message(AddSubState.waiting_for_category)
async def process_category(message: types.Message, state: FSMContext):
    if message.text not in config.CATEGORIES:
        await message.answer("Пожалуйста, выберите категорию из кнопок.")
        return

    await state.update_data(category=message.text)
    await message.answer(
        "Оцените полезность этой подписки от 1 до 10\n(где 1 - вообще не пользуюсь, 10 - жить без неё не могу):"
    )
    await state.set_state(AddSubState.waiting_for_importance)


@dp.message(AddSubState.waiting_for_importance)
async def process_importance(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or not (1 <= int(message.text) <= 10):
        await message.answer("Введите число от 1 до 10.")
        return

    data = await state.get_data()
    # Сохраняем в БД
    db.add_subscription(
        user_id=message.from_user.id,
        name=data['name'],
        price=data['price'],
        category=data['category'],
        importance=int(message.text)
    )

    await message.answer("✅ Подписка успешно сохранена!", reply_markup=get_main_kb())
    await state.clear()


# --- Просмотр списка ---

@dp.message(F.text == "📋 Список платежей")
async def show_list(message: types.Message):
    subs = db.get_all_subs(message.from_user.id)
    if not subs:
        await message.answer("Список пуст.")
        return

    response = "<b>Ваши подписки:</b>\n\n"
    for sub in subs:
        # sub = (name, price, category, importance)
        response += f"🔹 <b>{sub[0]}</b> | {sub[1]}₽\n   Категория: {sub[2]} | Важность: {sub[3]}/10\n\n"

    await message.answer(response, parse_mode="HTML")


# --- Графики и Статистика ---

@dp.message(F.text == "📊 Аналитика")
async def show_stats(message: types.Message):
    user_id = message.from_user.id

    # Текстовый отчет
    subs = db.get_all_subs(user_id)
    if not subs:
        await message.answer("Сначала добавьте данные.")
        return

    monthly, yearly = utils.calculate_monthly_forecast(subs)
    text = (f"💰 <b>Финансовая сводка:</b>\n"
            f"В месяц: {monthly} руб.\n"
            f"В год: {yearly} руб.\n\n"
            f"Генерирую график...")
    await message.answer(text, parse_mode="HTML")

    # 1. Первый график (Круговой)
    chart_data = db.get_stats_by_category(user_id)
    pie_buf = utils.generate_pie_chart(chart_data)

    # 2. Второй график (Столбчатый)
    bar_buf = utils.generate_bar_chart(subs)
    await message.answer("📊 Ваша финансовая статистика:")

    if pie_buf:
        await message.answer_photo(BufferedInputFile(pie_buf.read(), filename="pie.png"),
                                   caption="Расходы по категориям")
    if bar_buf:
        await message.answer_photo(BufferedInputFile(bar_buf.read(), filename="bar.png"),
                                   caption="Сравнение Цены и Полезности")


# --- Рекомендации (Оптимизация) ---

@dp.message(F.text == "💡 Советы по оптимизации")
async def show_advice(message: types.Message):
    subs = db.get_all_subs(message.from_user.id)
    if not subs:
        await message.answer("Нет данных для анализа.")
        return

    advice_text, wasted_money = utils.analyze_efficiency(subs)

    header = "🤖 <b>Анализ эффективности:</b>\n\n"
    footer = f"\n\n💸 Потенциальная экономия: <b>{wasted_money} руб./мес</b>" if wasted_money > 0 else ""

    await message.answer(header + advice_text + footer, parse_mode="HTML")


@dp.message(F.text == "🗑 Удалить платёж")
async def select_sub_to_delete(message: types.Message):
    subs = db.get_all_subs_with_ids(message.from_user.id)
    if not subs:
        await message.answer("У вас пока нет активных подписок.")
        return

    # Создаем инлайн-кнопки для каждой подписки
    builder = InlineKeyboardBuilder()
    for sub_id, name, price in subs:
        builder.button(text=f"❌ {name} ({price}₽)", callback_data=f"del_{sub_id}")

    builder.adjust(1)
    await message.answer("Выберите подписку для удаления:", reply_markup=builder.as_markup())


# Обработка нажатия на инлайн-кнопку
@dp.callback_query(F.data.startswith("del_"))
async def confirm_delete(callback: types.callback_query):
    sub_id = int(callback.data.split("_")[1])
    db.delete_sub_by_id(sub_id)
    await callback.answer("Удалено!")  # Всплывающее уведомление
    await callback.message.edit_text("✅ Платёж успешно удален из базы.")


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())