# fsm/states.py
from aiogram.fsm.state import StatesGroup, State

class AddTask(StatesGroup):
    waiting_for_content = State()
    waiting_for_due_date = State()
