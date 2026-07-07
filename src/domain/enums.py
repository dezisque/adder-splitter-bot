from enum import StrEnum


class ExpenseKind(StrEnum):
    EXPENSE = "expense"
    REPAYMENT = "repayment"


class SplitType(StrEnum):
    EQUAL = "equal"
