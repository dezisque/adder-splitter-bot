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
    exact_pick = State()  # «Свои суммы»: кому задать сумму
    exact_amount = State()  # ввод суммы выбранному участнику
    confirm = State()


class EditExpense(StatesGroup):
    description = State()  # expense_id — в данных состояния
    amount = State()
    split = State()


class QuickAdd(StatesGroup):
    room = State()  # черновик «Мясо 2450» ждёт выбора комнаты


class AddRepayment(StatesGroup):
    payer = State()  # room_id — в данных состояния
    recipient = State()
    amount = State()
