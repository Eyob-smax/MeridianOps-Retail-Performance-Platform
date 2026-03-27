from decimal import Decimal
from enum import StrEnum


class MemberTier(StrEnum):
    BASE = "base"
    SILVER = "silver"
    GOLD = "gold"


class CampaignType(StrEnum):
    PERCENT_OFF = "percent_off"
    FIXED_AMOUNT = "fixed_amount"
    FULL_REDUCTION = "full_reduction"


class IssuanceMethod(StrEnum):
    ACCOUNT_ASSIGNMENT = "account_assignment"
    PRINTABLE_QR = "printable_qr"


class RedemptionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class WalletEntryType(StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"


class InventoryDocumentType(StrEnum):
    RECEIVING = "receiving"
    TRANSFER = "transfer"
    COUNT = "count"


class InventoryLedgerEntryType(StrEnum):
    RECEIVE = "receive"
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN = "transfer_in"
    COUNT_ADJUST = "count_adjust"
    RESERVE = "reserve"
    RELEASE = "release"


class ReservationAction(StrEnum):
    CREATE = "create"
    RELEASE_CANCEL = "release_cancel"
    RELEASE_FULFILL = "release_fulfill"


class QuizDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AttemptResult(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"


def round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
