import logging
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import database as db


async def send_weekly_usage_survey(bot: Bot, user_id: int, chat_id=None, message_id=None):
    """Отправить или обновить еженедельный опрос о частоте использования подписок"""
    try:
        # Получаем все подписки пользователя (кроме ЖКХ)
        subs = db.get_all_subs(user_id, include_id=True, exclude_zkh=True, include_usage=False)
        
        if not subs:
            if chat_id and message_id:
                try:
                    await bot.edit_message_text(
                        "У вас нет подписок для оценки.",
                        chat_id=chat_id,
                        message_id=message_id
                    )
                except:
                    pass
            return  # У пользователя нет подписок для опроса
        
        # Определяем начало текущей недели (понедельник)
        today = datetime.now().date()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        week_start_str = week_start.strftime("%Y-%m-%d")
        
        # Получаем список уже оцененных подписок для отображения
        rated_sub_ids = db.get_rated_subscriptions_for_week(user_id, week_start)
        
        message_text = (
            "📊 <b>Еженедельный опрос о частоте использования подписок</b>\n\n"
            "Оцените, насколько активно вы пользовались каждой подпиской на этой неделе "
            f"(с {week_start.strftime('%d.%m')}):\n\n"
            "Шкала от 1 до 10:\n"
            "1-2 - почти не пользовался\n"
            "3-4 - редко пользовался\n"
            "5-6 - пользовался умеренно\n"
            "7-8 - пользовался часто\n"
            "9-10 - пользовался очень активно\n\n"
            "Выберите подписку для оценки:"
        )
        
        # Создаем инлайн-кнопки для каждой подписки
        builder = InlineKeyboardBuilder()
        for sub_id, name, price, category, importance in subs:
            if sub_id in rated_sub_ids:
                # Получаем оценку для отображения
                rating = db.check_subscription_rated(sub_id, week_start)
                builder.button(
                    text=f"✅ {name} ({price}₽) - {rating}/10",
                    callback_data=f"rate_{sub_id}_{week_start_str}"
                )
            else:
                builder.button(
                    text=f"{name} ({price}₽)",
                    callback_data=f"rate_{sub_id}_{week_start_str}"
                )
        
        # Всегда добавляем кнопку "Завершить опрос"
        builder.button(
            text="✅ Завершить опрос",
            callback_data=f"finish_survey_{week_start_str}"
        )
        
        builder.adjust(1)
        
        if chat_id and message_id:
            # Обновляем существующее сообщение
            try:
                await bot.edit_message_text(
                    message_text,
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode="HTML",
                    reply_markup=builder.as_markup()
                )
            except Exception as e:
                logging.error(f"Не удалось обновить сообщение: {e}")
                # Если не удалось обновить, отправляем новое
                await bot.send_message(
                    user_id,
                    message_text,
                    parse_mode="HTML",
                    reply_markup=builder.as_markup()
                )
        else:
            # Отправляем новое сообщение
            await bot.send_message(
                user_id,
                message_text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
    except Exception as e:
        logging.error(f"Ошибка при отправке опроса пользователю {user_id}: {e}")


async def check_unused_subscriptions(bot: Bot):
    """Проверка подписок, неиспользуемых более 3 недель, и отправка уведомлений"""
    try:
        # Получаем всех пользователей с подписками
        conn = db.create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT user_id FROM subscriptions')
        user_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        for user_id in user_ids:
            unused_subs = db.get_unused_subscriptions(user_id, weeks_threshold=3)
            
            if unused_subs:
                message_text = (
                    "⚠️ <b>Уведомление о неиспользуемых подписках</b>\n\n"
                    "Следующие подписки не использовались более 3 недель:\n\n"
                )
                
                for sub in unused_subs:
                    sub_id, name, price, last_week, weeks_unused = sub
                    weeks_unused = int(weeks_unused) if weeks_unused else 0
                    
                    if last_week:
                        message_text += (
                            f"❌ <b>{name}</b> ({price}₽)\n"
                            f"   Последнее использование: {weeks_unused} недель назад\n\n"
                        )
                    else:
                        message_text += (
                            f"❌ <b>{name}</b> ({price}₽)\n"
                            f"   Никогда не использовалась ({weeks_unused} недель с момента добавления)\n\n"
                        )
                
                message_text += "💡 Рекомендуем отменить эти подписки для экономии средств."
                
                try:
                    await bot.send_message(user_id, message_text, parse_mode="HTML")
                except Exception as e:
                    logging.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
        
    except Exception as e:
        logging.error(f"Ошибка при проверке неиспользуемых подписок: {e}")


async def weekly_survey_scheduler(bot: Bot):
    """Планировщик еженедельных опросов и проверки неиспользуемых подписок"""
    import asyncio
    
    while True:
        try:
            # Проверяем каждый день в 10:00
            now = datetime.now()
            if now.hour == 10 and now.minute < 5:  # Окно в 5 минут
                # Определяем, понедельник ли сегодня
                if now.weekday() == 0:  # 0 = понедельник
                    # Получаем всех пользователей с подписками
                    conn = db.create_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT DISTINCT user_id FROM subscriptions')
                    user_ids = [row[0] for row in cursor.fetchall()]
                    conn.close()
                    
                    # Отправляем опрос каждому пользователю
                    for user_id in user_ids:
                        await send_weekly_usage_survey(bot, user_id)
                        await asyncio.sleep(1)  # Небольшая задержка между отправками
                    
                    logging.info(f"Отправлены еженедельные опросы {len(user_ids)} пользователям")
                    
                    # Проверяем неиспользуемые подписки
                    await check_unused_subscriptions(bot)
                    logging.info("Проверка неиспользуемых подписок завершена")
            
            # Проверяем каждую минуту
            await asyncio.sleep(60)
        except Exception as e:
            logging.error(f"Ошибка в планировщике опросов: {e}")
            await asyncio.sleep(60)

