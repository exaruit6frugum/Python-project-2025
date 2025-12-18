# handlers/__init__.py
from .commands import register_commands_handlers
from .messages import register_messages_handlers
from .callbacks import register_callbacks_handlers

__all__ = ['register_commands_handlers', 'register_messages_handlers', 'register_callbacks_handlers']

