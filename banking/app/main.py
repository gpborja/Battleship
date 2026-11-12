from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app import services
from app.database import DEFAULT_DATABASE_URL, init_db, make_engine, make_session_factory
from app.schemas import (
    AccountCreate,
    AccountOut,
    AmountRequest,
    TransactionOut,
    TransactionResult,
    TransferRequest,
    TransferResult,
    to_cents,
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def get_db(request: Request) -> Iterator[Session]:
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


router = APIRouter(prefix="/api")


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(body: AccountCreate, db: Session = Depends(get_db)):
    account = services.create_account(db, body.owner_name, to_cents(body.initial_deposit))
    return AccountOut.from_model(account)


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return [AccountOut.from_model(a) for a in services.list_accounts(db)]


@router.get("/accounts/{account_id}", response_model=AccountOut)
def get_account(account_id: int, db: Session = Depends(get_db)):
    return AccountOut.from_model(services.get_account(db, account_id))


@router.post("/accounts/{account_id}/deposit", response_model=TransactionResult)
def deposit(account_id: int, body: AmountRequest, db: Session = Depends(get_db)):
    txn = services.deposit(db, account_id, to_cents(body.amount))
    return TransactionResult(
        transaction=TransactionOut.from_model(txn, account_id),
        account=AccountOut.from_model(services.get_account(db, account_id)),
    )


@router.post("/accounts/{account_id}/withdraw", response_model=TransactionResult)
def withdraw(account_id: int, body: AmountRequest, db: Session = Depends(get_db)):
    txn = services.withdraw(db, account_id, to_cents(body.amount))
    return TransactionResult(
        transaction=TransactionOut.from_model(txn, account_id),
        account=AccountOut.from_model(services.get_account(db, account_id)),
    )


@router.post("/transfers", response_model=TransferResult)
def transfer(body: TransferRequest, db: Session = Depends(get_db)):
    txn = services.transfer(db, body.from_account_id, body.to_account_id, to_cents(body.amount))
    return TransferResult(
        transaction=TransactionOut.from_model(txn, body.from_account_id),
        from_account=AccountOut.from_model(services.get_account(db, body.from_account_id)),
        to_account=AccountOut.from_model(services.get_account(db, body.to_account_id)),
    )


@router.get("/accounts/{account_id}/transactions", response_model=list[TransactionOut])
def transaction_history(
    account_id: int,
    limit: int | None = Query(default=None, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    txns = services.transaction_history(db, account_id, limit)
    return [TransactionOut.from_model(t, account_id) for t in txns]


def create_app(database_url: str = DEFAULT_DATABASE_URL) -> FastAPI:
    app = FastAPI(title="Sample Bank API", version="1.0.0")
    engine = make_engine(database_url)
    init_db(engine)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)

    @app.exception_handler(services.BankingError)
    def _banking_error(_request: Request, exc: services.BankingError):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
