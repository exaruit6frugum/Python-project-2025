import asyncio
import logging
from aiogram import Bot, Dispatcher

import config
import database as db
from handlers import register_commands_handlers, register_messages_handlers, register_callbacks_handlers
from handlers.commands import set_bot as set_bot_commands
from handlers.messages import set_bot as set_bot_messages
from handlers.callbacks import set_bot as set_bot_callbacks
from services.survey import weekly_survey_scheduler

# Настройка логирования (чтобы видеть ошибки в консоли)
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()


async def main():
    """Главная функция запуска бота"""
    print("Бот запущен")
    
    # Инициализация БД
    db.init_db()
    
    # Устанавливаем бота в handlers для использования в функциях
    set_bot_commands(bot)
    set_bot_messages(bot)
    set_bot_callbacks(bot)
    
    # Регистрация всех обработчиков
    register_commands_handlers(dp)
    register_messages_handlers(dp)
    register_callbacks_handlers(dp)
    
    # Запускаем планировщик еженедельных опросов в фоне
    asyncio.create_task(weekly_survey_scheduler(bot))
    
    # Запуск бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
