# Blood Donation Network

A system for connecting people who need blood with donors who are medically eligible to give.
Patients record blood requests, administrators broadcast those requests to eligible donors,
donors respond, and each donation is recorded against the request until the required units are
met.

For the architecture and the reasoning behind every technical decision, see
[explainer.md](explainer.md). For a dated log of changes, see [history.md](history.md).

---

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | React with Vite |
| Backend | Python with Flask, REST API |
| Database | PostgreSQL |

---

## Prerequisites

- Python 3.10 or newer
- Node.js 20 or newer
- PostgreSQL 14 or newer, running and reachable

---

## Database setup

Create the development and test databases:

```bash
createdb -U postgres bloodnet
```

```bash
createdb -U postgres bloodnet_test
```

---

## Backend

From the `backend` directory, create a virtual environment and install dependencies:

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `DATABASE_URL` to point at your local PostgreSQL instance,
along with the JWT secret and the initial administrator credentials. The `.env` file is ignored by
git and must never be committed.

Apply migrations:

```bash
flask db upgrade
```

Create the first administrator account from the values in `.env`:

```bash
flask seed-admin
```

Run the API:

```bash
flask run
```

---

## Frontend

From the `frontend` directory:

```bash
npm install
```

```bash
npm run dev
```

---

## Tests

From the `backend` directory:

```bash
pytest
```

---

## Project layout

```
backend/
  app/
    api/            HTTP routes grouped by resource
    models/         SQLAlchemy models and enums
    schemas/        Pydantic request and response models
    services/       Domain logic: eligibility, fulfilment, broadcast, summary
    notifications/  Notifier interface and drivers
  migrations/       Alembic revisions
  tests/
frontend/
  src/
    api/            Typed API client and query hooks
    components/     Shared UI primitives
    features/       Screens grouped by domain area
    styles/         Design tokens and base styles
```
