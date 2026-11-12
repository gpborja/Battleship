from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# Positive amount with at most 2 decimal places, e.g. 25 or 19.99.
Amount = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2, examples=[100.00])]


def to_cents(amount: Decimal) -> int:
    return int(amount * 100)


def from_cents(cents: int) -> float:
    return cents / 100


def _as_utc(value: datetime) -> datetime:
    # SQLite drops tzinfo; values are always stored in UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class AccountCreate(BaseModel):
    owner_name: str = Field(min_length=1, max_length=100, examples=["Ada Lovelace"])
    initial_deposit: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)] = Decimal("0")


class AmountRequest(BaseModel):
    amount: Amount


class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: Amount


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_name: str
    balance: float
    created_at: datetime

    @field_serializer("created_at")
    def _ser_created_at(self, value: datetime) -> str:
        return _as_utc(value).isoformat()

    @classmethod
    def from_model(cls, account) -> "AccountOut":
        return cls(
            id=account.id,
            owner_name=account.owner_name,
            balance=from_cents(account.balance_cents),
            created_at=account.created_at,
        )


class TransactionOut(BaseModel):
    id: int
    account_id: int
    type: Literal["deposit", "withdrawal", "transfer"]
    amount: float
    timestamp: datetime
    related_account_id: int | None
    # Relative to the account whose history is requested: "in" adds money, "out" removes it.
    direction: Literal["in", "out"] | None = None

    @field_serializer("timestamp")
    def _ser_timestamp(self, value: datetime) -> str:
        return _as_utc(value).isoformat()

    @classmethod
    def from_model(cls, txn, perspective_account_id: int | None = None) -> "TransactionOut":
        txn_type = txn.type.value
        direction = None
        if perspective_account_id is not None:
            if txn_type == "deposit":
                direction = "in"
            elif txn_type == "withdrawal":
                direction = "out"
            else:
                direction = "out" if txn.account_id == perspective_account_id else "in"
        return cls(
            id=txn.id,
            account_id=txn.account_id,
            type=txn_type,
            amount=from_cents(txn.amount_cents),
            timestamp=txn.timestamp,
            related_account_id=txn.related_account_id,
            direction=direction,
        )


class TransactionResult(BaseModel):
    transaction: TransactionOut
    account: AccountOut


class TransferResult(BaseModel):
    transaction: TransactionOut
    from_account: AccountOut
    to_account: AccountOut
