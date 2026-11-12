"""Business logic. Every public function runs in a single DB transaction:
it commits on success and rolls back everything on any error."""

from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models import Account, Transaction, TransactionType, utcnow


class BankingError(Exception):
    status_code = 400


class AccountNotFound(BankingError):
    status_code = 404

    def __init__(self, account_id: int):
        super().__init__(f"Account {account_id} not found")
        self.account_id = account_id


class InsufficientFunds(BankingError):
    status_code = 409

    def __init__(self, account_id: int):
        super().__init__(f"Insufficient funds in account {account_id}")
        self.account_id = account_id


class InvalidAmount(BankingError):
    status_code = 422


class InvalidTransfer(BankingError):
    status_code = 400


def _check_amount(amount_cents: int) -> None:
    if not isinstance(amount_cents, int) or amount_cents <= 0:
        raise InvalidAmount("Amount must be greater than zero")


def _get_or_404(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise AccountNotFound(account_id)
    return account


def _debit(db: Session, account_id: int, amount_cents: int) -> None:
    # Conditional UPDATE: the balance check and the debit happen in one statement,
    # so two concurrent withdrawals can never overdraw the account.
    result = db.execute(
        update(Account)
        .where(Account.id == account_id, Account.balance_cents >= amount_cents)
        .values(balance_cents=Account.balance_cents - amount_cents)
    )
    if result.rowcount != 1:
        _get_or_404(db, account_id)
        raise InsufficientFunds(account_id)


def _credit(db: Session, account_id: int, amount_cents: int) -> None:
    result = db.execute(
        update(Account)
        .where(Account.id == account_id)
        .values(balance_cents=Account.balance_cents + amount_cents)
    )
    if result.rowcount != 1:
        raise AccountNotFound(account_id)


def _record(db: Session, **fields) -> Transaction:
    txn = Transaction(**fields)
    if txn.timestamp is None:
        txn.timestamp = utcnow()
    db.add(txn)
    return txn


def _commit(db: Session, *objs) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    for obj in objs:
        db.refresh(obj)


def create_account(
    db: Session, owner_name: str, initial_deposit_cents: int = 0, at: datetime | None = None
) -> Account:
    owner_name = owner_name.strip()
    if not owner_name:
        raise BankingError("Owner name must not be empty")
    if initial_deposit_cents < 0:
        raise InvalidAmount("Initial deposit must not be negative")
    try:
        account = Account(owner_name=owner_name, balance_cents=initial_deposit_cents, created_at=at or utcnow())
        db.add(account)
        db.flush()
        if initial_deposit_cents:
            _record(
                db,
                account_id=account.id,
                type=TransactionType.deposit,
                amount_cents=initial_deposit_cents,
                timestamp=at,
            )
    except Exception:
        db.rollback()
        raise
    _commit(db, account)
    return account


def get_account(db: Session, account_id: int) -> Account:
    return _get_or_404(db, account_id)


def list_accounts(db: Session) -> list[Account]:
    return list(db.scalars(select(Account).order_by(Account.id)))


def deposit(db: Session, account_id: int, amount_cents: int, at: datetime | None = None) -> Transaction:
    _check_amount(amount_cents)
    try:
        _credit(db, account_id, amount_cents)
        txn = _record(db, account_id=account_id, type=TransactionType.deposit, amount_cents=amount_cents, timestamp=at)
        db.flush()
    except Exception:
        db.rollback()
        raise
    _commit(db, txn)
    return txn


def withdraw(db: Session, account_id: int, amount_cents: int, at: datetime | None = None) -> Transaction:
    _check_amount(amount_cents)
    try:
        _debit(db, account_id, amount_cents)
        txn = _record(
            db, account_id=account_id, type=TransactionType.withdrawal, amount_cents=amount_cents, timestamp=at
        )
        db.flush()
    except Exception:
        db.rollback()
        raise
    _commit(db, txn)
    return txn


def transfer(
    db: Session, from_account_id: int, to_account_id: int, amount_cents: int, at: datetime | None = None
) -> Transaction:
    """Move money between accounts atomically: both sides are applied or neither is."""
    _check_amount(amount_cents)
    if from_account_id == to_account_id:
        raise InvalidTransfer("Cannot transfer to the same account")
    try:
        _get_or_404(db, to_account_id)
        _debit(db, from_account_id, amount_cents)
        _credit(db, to_account_id, amount_cents)
        txn = _record(
            db,
            account_id=from_account_id,
            type=TransactionType.transfer,
            amount_cents=amount_cents,
            related_account_id=to_account_id,
            timestamp=at,
        )
        db.flush()
    except Exception:
        db.rollback()
        raise
    _commit(db, txn)
    return txn


def transaction_history(db: Session, account_id: int, limit: int | None = None) -> list[Transaction]:
    """All transactions touching the account (including incoming transfers), newest first."""
    _get_or_404(db, account_id)
    stmt = (
        select(Transaction)
        .where(or_(Transaction.account_id == account_id, Transaction.related_account_id == account_id))
        .order_by(Transaction.timestamp.desc(), Transaction.id.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))
