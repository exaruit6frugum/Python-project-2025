from aiogram.utils.keyboard import ReplyKeyboardBuilder
import config


def get_main_kb():
    """Главная клавиатура бота"""
    kb = ReplyKeyboardBuilder()
    kb.button(text="➕ Добавить ежемесячный платёж")
    kb.button(text="✏️ Изменить важность платежа")
    kb.button(text="📋 Список платежей")
    kb.button(text="📊 Аналитика")
    kb.button(text="💡 Советы по оптимизации")
    kb.button(text="🗑 Удалить платёж")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


def get_categories_kb():
    """Клавиатура выбора категории"""
    kb = ReplyKeyboardBuilder()
    for cat in config.CATEGORIES:
        kb.button(text=cat)
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_usage_rating_kb():
    """Клавиатура для оценки использования (1-10)"""
    kb = ReplyKeyboardBuilder()
    for i in range(1, 11):
        kb.button(text=str(i))
    kb.adjust(5)  # 5 кнопок в ряд
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=True)

