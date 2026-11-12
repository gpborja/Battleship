# Banco Ejemplo — sample banking app

A small full-stack banking demo: a **FastAPI** REST API backed by **SQLite** (via SQLAlchemy 2.0), a single-page **vanilla JS dashboard**, a **pytest** suite and a seed script with demo data. The dashboard reuses the look of [`../battleship.html`](../battleship.html) (flag colours, papel picado, Talavera background).

## Features

- Open accounts (optionally with an initial deposit), list them, and view a single account.
- Deposit, withdraw, and transfer money between accounts.
- Per-account transaction history, newest first, including incoming transfers.
- Business rules:
  - **No overdrafts** — a withdrawal or transfer larger than the balance is rejected with `409`. The check and debit happen in one conditional `UPDATE`, and a `CHECK (balance_cents >= 0)` constraint backs it up at the database level.
  - **No zero or negative amounts**, and no more than 2 decimal places (`422`).
  - **Atomic transfers** — debit, credit and ledger entry are written in one database transaction; any failure rolls back everything.
  - Transfers to the same account or to an unknown account are rejected.
- Money is stored as integer **cents**, so there is no floating-point drift. The API accepts and returns plain decimal numbers (`19.99`).
- Interactive API docs (Swagger UI) at `/docs`.

## Setup

Requires Python 3.10+. From this `banking/` directory:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m app.seed                 # optional: demo accounts + ~30 days of sample transactions
uvicorn app.main:app --reload      # http://127.0.0.1:8000
```

Open <http://127.0.0.1:8000/> for the dashboard and <http://127.0.0.1:8000/docs> for the API docs.

- `python -m app.seed --reset` wipes the database and reseeds it. Without `--reset` it does nothing if accounts already exist.
- The database is `./banking.db` by default. Set `BANKING_DATABASE_URL` (e.g. `sqlite:////tmp/bank.db`) to use another file.

## Running the tests

```bash
pytest            # from banking/
```

Each test gets its own temporary SQLite database. The suite covers account creation, deposits and withdrawals, amount validation, overdraft rejection, transfer atomicity (failures are injected after the debit and while writing the ledger entry), transaction history ordering, and the seed script.

## API reference

All endpoints are under `/api` and use JSON. Amounts are decimal numbers with at most 2 decimal places. Errors return `{"detail": ...}`.

| Method | Path | Body | Success | Errors |
| --- | --- | --- | --- | --- |
| `POST` | `/api/accounts` | `{"owner_name": "Ada", "initial_deposit": 100.00}` (`initial_deposit` optional, default 0) | `201` account | `400` blank name, `422` invalid input |
| `GET` | `/api/accounts` | — | `200` list of accounts, by id | — |
| `GET` | `/api/accounts/{id}` | — | `200` account | `404` |
| `POST` | `/api/accounts/{id}/deposit` | `{"amount": 50.00}` | `200` `{transaction, account}` | `404`, `422` |
| `POST` | `/api/accounts/{id}/withdraw` | `{"amount": 20.00}` | `200` `{transaction, account}` | `404`, `409` insufficient funds, `422` |
| `POST` | `/api/transfers` | `{"from_account_id": 1, "to_account_id": 2, "amount": 75.00}` | `200` `{transaction, from_account, to_account}` | `400` same account, `404`, `409`, `422` |
| `GET` | `/api/accounts/{id}/transactions?limit=N` | — | `200` list of transactions, newest first | `404` |

Account:

```json
{"id": 1, "owner_name": "Frida Kahlo", "balance": 7704.49, "created_at": "2026-10-13T02:35:02.548021+00:00"}
```

Transaction:

```json
{"id": 21, "account_id": 5, "type": "transfer", "amount": 10.0, "timestamp": "2026-11-12T02:35:04.783587+00:00",
 "related_account_id": 1, "direction": "out"}
```

- `type` is `deposit`, `withdrawal` or `transfer`.
- A transfer is stored as **one** row: `account_id` is the sender and `related_account_id` the receiver. It appears in the history of both accounts.
- `direction` (`in` / `out`) is computed for the account whose history (or operation) you requested, so the same transfer is `out` for the sender and `in` for the receiver.

Example:

```bash
curl -X POST localhost:8000/api/transfers -H 'Content-Type: application/json' \
     -d '{"from_account_id": 1, "to_account_id": 2, "amount": 75}'
```

## Project layout

```
banking/
├── app/
│   ├── main.py        # FastAPI app, routes, error handling; serves the dashboard at /
│   ├── services.py    # business rules (overdraft checks, atomic transfers, history)
│   ├── models.py      # SQLAlchemy models: Account, Transaction
│   ├── schemas.py     # Pydantic request/response models, cents <-> decimal conversion
│   ├── database.py    # engine/session setup (SQLite with foreign keys on)
│   └── seed.py        # demo data: python -m app.seed [--reset]
├── static/index.html  # single-page dashboard (vanilla JS)
├── tests/             # pytest suite
├── requirements.txt
└── pytest.ini
```
