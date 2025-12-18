from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import database as db
import utils
import keyboards
from states import AddSubState, UsageRatingState, ChangeImportanceState
from services.survey import send_weekly_usage_survey
from aiogram import Bot

# Глобальная переменная для бота (будет установлена в main.py)
_bot: Bot = None


def set_bot(bot: Bot):
    """Установка экземпляра бота для использования в handlers"""
    global _bot
    _bot = bot


def register_messages_handlers(dp: Dispatcher):
    """Регистрация обработчиков сообщений"""
    
    # --- Логика добавления подписки (FSM) ---
    
    @dp.message(F.text == "➕ Добавить ежемесячный платёж")
    async def start_add_sub(message: Message, state: FSMContext):
        await message.answer("Введите название сервиса (например, Netflix):")
        await state.set_state(AddSubState.waiting_for_name)

    @dp.message(AddSubState.waiting_for_name)
    async def process_name(message: Message, state: FSMContext):
        await state.update_data(name=message.text)
        await message.answer("Сколько вы платите в месяц (в рублях)?")
        await state.set_state(AddSubState.waiting_for_price)

    @dp.message(AddSubState.waiting_for_price)
    async def process_price(message: Message, state: FSMContext):
        # Проверка на число
        if not message.text.isdigit():
            await message.answer("Пожалуйста, введите число.")
            return

        await state.update_data(price=float(message.text))
        await message.answer("Выберите категорию:", reply_markup=keyboards.get_categories_kb())
        await state.set_state(AddSubState.waiting_for_category)

    @dp.message(AddSubState.waiting_for_category)
    async def process_category(message: Message, state: FSMContext):
        if message.text not in config.CATEGORIES:
            await message.answer("Пожалуйста, выберите категорию из кнопок.")
            return

        await state.update_data(category=message.text)
        await message.answer(
            "Оцените важность этой подписки от 1 до 10\n(где 1 - почти не нужна, 10 - жить без неё не могу):"
        )
        await state.set_state(AddSubState.waiting_for_importance)

    @dp.message(AddSubState.waiting_for_importance)
    async def process_importance(message: Message, state: FSMContext):
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

        await message.answer("✅ Подписка успешно сохранена!", reply_markup=keyboards.get_main_kb())
        await state.clear()

    @dp.message(ChangeImportanceState.waiting_for_importance)
    async def process_change_importance(message: Message, state: FSMContext):
        """Обработка изменения важности"""
        if not message.text.isdigit() or not (1 <= int(message.text) <= 10):
            await message.answer("Пожалуйста, введите число от 1 до 10.", reply_markup=keyboards.get_usage_rating_kb())
            return
        
        new_importance = int(message.text)
        data = await state.get_data()
        sub_id = data['sub_id']
        
        # Обновляем важность в БД
        conn = db.create_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE subscriptions SET importance = ? WHERE id = ?',
            (new_importance, sub_id)
        )
        cursor.execute('SELECT service_name FROM subscriptions WHERE id = ?', (sub_id,))
        service_name = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        
        await message.answer(
            f"✅ Важность подписки <b>{service_name}</b> изменена на {new_importance}/10",
            parse_mode="HTML",
            reply_markup=keyboards.get_main_kb()
        )
        await state.clear()

    # --- Просмотр списка ---

    @dp.message(F.text == "📋 Список платежей")
    async def show_list(message: Message):
        subs = db.get_all_subs(message.from_user.id, include_id=False, exclude_zkh=False, include_usage=False)
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
    async def show_stats(message: Message):
        user_id = message.from_user.id

        # Текстовый отчет
        subs = db.get_all_subs(user_id, include_id=False, exclude_zkh=False, include_usage=False)
        if not subs:
            await message.answer("Сначала добавьте данные.")
            return

        monthly, yearly = utils.calculate_monthly_forecast(subs)
        text = (f"💰 <b>Финансовая сводка:</b>\n"
                f"В месяц: {monthly} руб.\n"
                f"В год: {yearly} руб.\n")
        await message.answer(text, parse_mode="HTML")

        # Первый график (Круговой)
        chart_data = db.get_stats_by_category(user_id)
        pie_buf = utils.generate_pie_chart(chart_data)

        # Второй график (Столбчатый) - стоимость за единицу удовольствия
        subs_with_usage = db.get_all_subs(user_id, include_id=True, exclude_zkh=False, include_usage=True)
        bar_buf = utils.generate_bar_chart(subs_with_usage)
        await message.answer("📊 Ваша финансовая статистика:")

        if pie_buf:
            await message.answer_photo(BufferedInputFile(pie_buf.read(), filename="pie.png"),
                                       caption="Расходы по категориям")
        if bar_buf:
            await message.answer_photo(BufferedInputFile(bar_buf.read(), filename="bar.png"),
                                       caption="Стоимость за единицу удовольствия")

    # --- Рекомендации (Оптимизация) ---

    @dp.message(F.text == "💡 Советы по оптимизации")
    async def show_advice(message: Message):
        subs_with_usage = db.get_all_subs(message.from_user.id, include_id=True, exclude_zkh=False, include_usage=True)
        if not subs_with_usage:
            await message.answer("Нет данных для анализа.")
            return

        advice_text, wasted_money = utils.analyze_efficiency(subs_with_usage)

        header = "<b>Анализ эффективности:</b>\n\n"
        footer = f"\n\n💸 Потенциальная экономия: <b>{wasted_money:.0f} руб./мес</b>" if wasted_money > 0 else ""

        await message.answer(header + advice_text + footer, parse_mode="HTML")

    # --- Изменение важности подписки ---

    @dp.message(F.text == "✏️ Изменить важность платежа")
    async def select_sub_to_change_importance(message: Message):
        subs = db.get_all_subs(message.from_user.id, include_id=True, exclude_zkh=False, include_usage=False)
        if not subs:
            await message.answer("У вас пока нет активных подписок.")
            return

        # Создаем инлайн-кнопки для каждой подписки
        builder = InlineKeyboardBuilder()
        for sub in subs:
            # sub = (id, name, price, category, importance)
            sub_id, name, price, category, importance = sub[0], sub[1], sub[2], sub[3], sub[4]
            builder.button(text=f"{name} ({price}₽) - важность: {importance}/10", callback_data=f"change_imp_{sub_id}")

        builder.adjust(1)
        await message.answer("Выберите подписку для изменения важности:", reply_markup=builder.as_markup())

    # --- Удаление подписки ---

    @dp.message(F.text == "🗑 Удалить платёж")
    async def select_sub_to_delete(message: Message):
        subs = db.get_all_subs(message.from_user.id, include_id=True, exclude_zkh=False, include_usage=False)
        if not subs:
            await message.answer("У вас пока нет активных подписок.")
            return

        # Создаем инлайн-кнопки для каждой подписки
        builder = InlineKeyboardBuilder()
        for sub in subs:
            # sub = (id, name, price, category, importance)
            sub_id, name, price = sub[0], sub[1], sub[2]
            builder.button(text=f"❌ {name} ({price}₽)", callback_data=f"del_{sub_id}")

        builder.adjust(1)
        await message.answer("Выберите подписку для удаления:", reply_markup=builder.as_markup())

    # --- Обработка оценки использования ---

    @dp.message(UsageRatingState.waiting_for_rating)
    async def process_usage_rating(message: Message, state: FSMContext):
        """Обработка оценки использования"""
        from datetime import datetime
        
        if not message.text.isdigit() or not (1 <= int(message.text) <= 10):
            await message.answer("Пожалуйста, введите число от 1 до 10.", reply_markup=keyboards.get_usage_rating_kb())
            return
        
        rating = int(message.text)
        data = await state.get_data()
        sub_id = data['sub_id']
        week_start_str = data['week_start']
        survey_chat_id = data.get('survey_chat_id')
        survey_message_id = data.get('survey_message_id')
        
        # Сохраняем оценку
        week_start_date = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        db.save_usage_score(sub_id, message.from_user.id, week_start_date, rating)
        
        # Получаем название сервиса для подтверждения
        conn = db.create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT service_name FROM subscriptions WHERE id = ?', (sub_id,))
        service_name = cursor.fetchone()[0]
        conn.close()
        
        # Показываем подтверждение
        await message.answer(
            f"✅ Оценка для <b>{service_name}</b> сохранена: {rating}/10",
            parse_mode="HTML"
        )
        
        # Обновляем сообщение с опросом, если оно было сохранено
        if survey_chat_id and survey_message_id and _bot:
            await send_weekly_usage_survey(
                _bot,
                message.from_user.id,
                chat_id=survey_chat_id,
                message_id=survey_message_id
            )
        
        await state.clear()

    @dp.message(ChangeImportanceState.waiting_for_importance)
    async def process_change_importance(message: Message, state: FSMContext):
        """Обработка изменения важности"""
        if not message.text.isdigit() or not (1 <= int(message.text) <= 10):
            await message.answer("Пожалуйста, введите число от 1 до 10.", reply_markup=keyboards.get_usage_rating_kb())
            return
        
        new_importance = int(message.text)
        data = await state.get_data()
        sub_id = data['sub_id']
        
        # Обновляем важность в БД
        conn = db.create_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE subscriptions SET importance = ? WHERE id = ?',
            (new_importance, sub_id)
        )
        cursor.execute('SELECT service_name FROM subscriptions WHERE id = ?', (sub_id,))
        service_name = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        
        await message.answer(
            f"✅ Важность подписки <b>{service_name}</b> изменена на {new_importance}/10",
            parse_mode="HTML",
            reply_markup=keyboards.get_main_kb()
        )
        await state.clear()

