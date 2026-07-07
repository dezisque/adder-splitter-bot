from aiogram.fsm.state import State, StatesGroup


class CreateRoom(StatesGroup):
    title = State()


class AddVirtualMember(StatesGroup):
    name = State()  # room_id — в данных состояния


class AddExpense(StatesGroup):
    description = State()
    amount = State()
    payer = State()
    split = State()
    confirm = State()


class EditExpense(StatesGroup):
    description = State()  # expense_id — в данных состояния
    amount = State()
    split = State()


class AddRepayment(StatesGroup):
    payer = State()  # room_id — в данных состояния
    recipient = State()
    amount = State()
