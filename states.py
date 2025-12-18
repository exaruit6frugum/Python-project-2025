from aiogram.fsm.state import State, StatesGroup


class AddSubState(StatesGroup):
    """Машина состояний для добавления подписки"""
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_category = State()
    waiting_for_importance = State()


class UsageRatingState(StatesGroup):
    """Машина состояний для оценки использования"""
    waiting_for_rating = State()


class ChangeImportanceState(StatesGroup):
    """Машина состояний для изменения важности подписки"""
    waiting_for_importance = State()

