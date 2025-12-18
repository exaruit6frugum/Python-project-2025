from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import database as db
import keyboards
from services.survey import send_weekly_usage_survey
from aiogram import Bot

# Глобальная переменная для бота (будет установлена в main.py)
_bot: Bot = None


def set_bot(bot: Bot):
    """Установить экземпляр бота для использования в handlers"""
    global _bot
    _bot = bot
from states import UsageRatingState, ChangeImportanceState


def register_callbacks_handlers(dp: Dispatcher):
    """Регистрация обработчиков callback-запросов"""
    
    @dp.callback_query(F.data.startswith("del_"))
    async def confirm_delete(callback: CallbackQuery):
        """Удаление подписки"""
        sub_id = int(callback.data.split("_")[1])
        db.delete_sub_by_id(sub_id)
        await callback.answer("Удалено!")  # Всплывающее уведомление
        await callback.message.edit_text("✅ Платёж успешно удален из базы.")

    @dp.callback_query(F.data.startswith("rate_"))
    async def start_rating_usage(callback: CallbackQuery, state: FSMContext):
        """Начало процесса оценки использования"""
        parts = callback.data.split("_")
        sub_id = int(parts[1])
        week_start_str = parts[2]
        
        # Получаем информацию о подписке
        conn = db.create_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT service_name FROM subscriptions WHERE id = ?',
            (sub_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await callback.answer("Подписка не найдена", show_alert=True)
            return
        
        service_name = result[0]
        
        # Сохраняем данные исходного сообщения с опросом для обновления
        await state.update_data(
            sub_id=sub_id, 
            week_start=week_start_str,
            survey_chat_id=callback.message.chat.id,
            survey_message_id=callback.message.message_id
        )
        
        await callback.message.edit_text(
            f"Оцените использование <b>{service_name}</b> на этой неделе:\n\n"
            "Введите число от 1 до 10:",
            parse_mode="HTML"
        )
        await callback.message.answer(
            "Используйте клавиатуру ниже или введите число:",
            reply_markup=keyboards.get_usage_rating_kb()
        )
        await state.set_state(UsageRatingState.waiting_for_rating)
        await callback.answer()

    @dp.callback_query(F.data.startswith("finish_survey_"))
    async def finish_survey(callback: CallbackQuery):
        """Завершение опроса"""
        await callback.message.edit_text(
            "✅ <b>Опрос завершен!</b>\n\n"
            "Все ваши оценки сохранены. Вы можете проверить аналитику в разделе '💡 Советы по оптимизации'.",
            parse_mode="HTML"
        )
        await callback.answer("Опрос завершен!")

    @dp.callback_query(F.data.startswith("change_imp_"))
    async def start_change_importance(callback: CallbackQuery, state: FSMContext):
        """Начало процесса изменения важности"""
        sub_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о подписке
        conn = db.create_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT service_name, importance FROM subscriptions WHERE id = ?',
            (sub_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await callback.answer("Подписка не найдена", show_alert=True)
            return
        
        service_name, current_importance = result
        
        await state.update_data(sub_id=sub_id)
        await callback.message.edit_text(
            f"Текущая важность <b>{service_name}</b>: {current_importance}/10\n\n"
            "Введите новую важность от 1 до 10:",
            parse_mode="HTML"
        )
        await callback.message.answer(
            "Используйте клавиатуру ниже или введите число:",
            reply_markup=keyboards.get_usage_rating_kb()
        )
        await state.set_state(ChangeImportanceState.waiting_for_importance)
        await callback.answer()

