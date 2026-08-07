# Change History

A running, dated changelog of every change made to this project, newest entries appended at
the bottom of each date section. Each entry records what changed and why.

---

## 2026-08-07

### Phase 0 - Repository and documentation bootstrap

- **Initialised the git repository** on branch `main` and wired the `origin` remote to
  `https://github.com/Alen-Saji-05/Keyvalblooddono.git`. The remote was empty, so no existing
  history was disturbed.
- **Added `.gitignore`** covering Python bytecode and virtual environments, Node modules and
  Vite build output, editor directories, OS metadata, and environment files. `.env` is ignored
  while `.env.example` is explicitly re-included, so the shape of the configuration is version
  controlled but the secrets are not.
- **Added `README.md`** with prerequisites, database setup, backend and frontend run
  instructions, and the project layout.
- **Added `explainer.md`** as the living architecture document, seeded with the decisions taken
  during planning: the fixed stack, ORM, migration tool, validation library, application
  structure, authentication approach, notification strategy, frontend data layer, routing,
  styling approach, and testing strategy. Each decision records the alternatives considered and
  why they were rejected.
- **Added `history.md`** (this file).

**Why this ordering:** documentation and version control are established before any code so that
every subsequent change has somewhere to be recorded and can be committed as it is made, rather
than reconstructed afterwards.

### Planning decisions captured before Phase 1

- **Role model settled at three roles: `admin`, `donor`, `patient`.** An earlier draft proposed a
  four-role model including a `coordinator` and a hospital organisation account. This was
  rejected in review: the actors in this system are the person donating blood, the person
  requesting it, and the staff operating the network. The hospital is a property of a request,
  not an account holder.
- **Broadcast and donation recording restricted to `admin`.** Considered allowing patients to
  broadcast their own requests and confirm receipt of units. Rejected so that outbound
  notifications to donors and the fulfilment figures both stay under staff control, and a
  patient cannot inflate their own request's progress or send unreviewed messages to donors.
- **Public self-registration for `donor` and `patient` roles; `admin` accounts are never public.**
  The first admin is created by a CLI command from environment variables, and further admins are
  created by an existing admin.
- **Donor directory is admin-only.** A consequence of admin-only broadcast: patients have no
  workflow reason to see donor identities or contact details. Patients instead get an aggregate
  availability view returning eligible donor counts by blood group and place, which carries no
  personally identifying information. This replaced an earlier, more complex design that showed
  patients a partially masked donor list.

### Phase 1 - Data model, migrations, and the two domain invariants

- **Added the SQLAlchemy models** for the six tables: `donors`, `users`, `blood_requests`,
  `donations`, `notifications`, and `token_blocklist`. Enumerations are native PostgreSQL enum
  types storing their wire values, so the table is readable in a SQL client and the database
  rejects invalid values rather than storing them.
- **Refined the starting schema.** `donors` gained `sex`, `date_of_birth`, and `weight_kg` because
  the brief requires the fields needed to compute medical eligibility and those are what the whole
  blood criteria are expressed in, plus `status_note` for free-text detail alongside an
  unavailable status. `blood_requests` gained `contact_phone`, without which a request is not
  actionable, and `created_by_user_id` for patient scoping. `donations` gained
  `recorded_by_user_id`. `notifications` gained `channel` and `delivery_error`, and a unique
  constraint on `(donor_id, request_id)` so that re-broadcasting does not duplicate messages or
  inflate the response-rate denominator. Each refinement is justified in `explainer.md` section 5.
- **Enforced two invariants as database check constraints** rather than in application code alone:
  a request's status must agree with its unit arithmetic, and a notification's response timestamp
  must agree with its responded flag. A third constraint ties the donor role to a donor record.
- **Chose foreign key delete behaviour per relationship.** `donations.donor_id` is `RESTRICT`
  because a donation is a medical record; notifications and donations cascade from their request
  because neither means anything without it; `blood_requests.created_by_user_id` is `SET NULL` so
  removing an account does not erase the record that the request happened.
- **Added `services/eligibility.py`**, which owns the eligibility rule and renders it two ways from
  one set of thresholds: a sargable SQL predicate for filtering and counting, and a Python
  evaluation returning the reasons a donor is ineligible. Written this way specifically so the
  dashboard's eligible-donor count and the broadcast selector cannot disagree.
- **Added `services/fulfilment.py`**, the only code that writes `units_fulfilled` or `status`. It
  recomputes the total with `SUM` rather than incrementing, and takes a `SELECT ... FOR UPDATE`
  lock on the request row first so that two administrators recording donations concurrently cannot
  lose one another's update.
- **Added the hand-written initial Alembic revision.** Written by hand rather than autogenerated
  because Alembic does not diff check constraints, and because autogeneration would have created
  each enum type implicitly at the first table referencing it, which fails for the enums used by
  two tables.
- **Added the application factory, configuration classes, extensions module, health endpoint,
  Argon2id password hashing, and the CLI commands** `seed-admin`, `seed-demo`, and
  `purge-expired-tokens`. The demo dataset is built relative to the current date so that the
  eligibility rules always produce a meaningful spread, rather than every donor becoming eligible
  once fixed fixture dates age.
- **Chose Flask-SQLAlchemy** for request-scoped session handling over a hand-managed
  `scoped_session`, recorded in `explainer.md` section 3.14.
