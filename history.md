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

### Phase 1 - Defects found while verifying the migration against a live database

Four problems surfaced once the migration actually ran. All are recorded here rather than
quietly amended, because three of them are the kind that stay invisible until much later.

- **`alembic.ini` was in the wrong directory.** Flask-Migrate looks for it inside the migrations
  directory, not the backend root. With no config file found, `fileConfig` parsed nothing and then
  failed with a bare `KeyError: 'formatters'`, which names a logging section rather than the actual
  problem. Moved the file and added an existence check in `env.py` so a future recurrence fails
  with something diagnosable.
- **`compare_type` was passed twice to `context.configure`.** Flask-Migrate already supplies it in
  `configure_args`. The two are now merged, with anything set on the `Migrate` object winning, so a
  project-level override is still respected.
- **Check constraint names were doubled in the database**, producing
  `ck_donors_ck_donors_weight_positive`. The metadata naming convention for check constraints
  contains `%(constraint_name)s`, which means SQLAlchemy applies it to constraints that already
  have a name, using the given name as the token. The migration was passing fully-qualified names
  and having the convention expand them a second time. It now passes the same short names the
  models use.
- **`token_blocklist.jti` had both a unique constraint and a separate index.** PostgreSQL
  implements a unique constraint with a unique index, so the second was a duplicate of the same
  structure. Removed `index=True` from the model and the redundant `create_index` from the
  migration.
- **`.env` was not loaded when the package was imported directly.** `config.py` reads `os.environ`
  when its classes are defined, not when they are instantiated, and the `load_dotenv` call sat
  below the config import. The `flask` CLI hid this completely, because Flask loads `.env` itself
  before importing the application, so every setting silently fell back to its hardcoded default
  under any other entry point - a script, pytest, or a production WSGI server. The load now runs at
  the very top of the package `__init__`, before any submodule import.

### Phase 1 - Verification against a live PostgreSQL 17 database

- Created `bloodnet` and `bloodnet_test`, applied the migration, and confirmed a clean
  downgrade-to-base and upgrade roundtrip, including the enum type drops.
- Ran `flask db migrate` as a drift check: **no schema changes detected**, so the hand-written
  revision matches the models exactly.
- Seeded the demonstration dataset and confirmed the fulfilment service derives the right state
  for all three cases: an untouched request stays `open`, a request with one of four units becomes
  `partially_fulfilled`, and a request meeting its requirement from two different donors becomes
  `fulfilled`.
- Confirmed the SQL eligibility predicate and the Python evaluation agree on all fifteen seeded
  donors, with zero disagreements, across every exclusion reason: cooldown, travel, medical
  unavailability, underweight, and over age.
- Negative-tested the constraints. All eight attempts were rejected by the database: a status that
  contradicts its unit arithmetic in both directions, a response flag without a timestamp, an admin
  account linked to a donor record, a donor account without one, a duplicate notification for the
  same donor and request, a negative donation, and an invalid blood group.

### Phase 2 - JWT authentication and role-based authorisation

- **Added the authentication endpoints**: register, login, refresh, logout, current user, and
  password change, under `/api/auth`. Added administrator account management under `/api/users`.
  The latter deviates from the planned `/api/auth/users`: accounts are a resource administrators
  manage, whereas `/api/auth` is reserved for operations on the caller's own session, and keeping
  them apart lets the refresh cookie's path scope cover exactly the session operations.
- **Access token in memory, refresh token in an httpOnly cookie.** The access token is returned in
  the response body with a fifteen minute life; the refresh token is set as an httpOnly,
  SameSite=Strict cookie and never appears in a response body. A test asserts the body contains no
  refresh token, so the split cannot be undone by accident.
- **Refresh tokens rotate on every use.** The presented token is blocklisted and a new one issued,
  which limits a stolen refresh token to a single use and makes a theft surface as a rejected
  replay rather than two parties refreshing indefinitely.
- **The account row is loaded from the database on every authenticated request**, so deactivating
  an account takes effect immediately rather than when its access token happens to expire. Access
  tokens are deliberately not blocklist-checked, since at a fifteen minute life that would add a
  query per request to shorten an already short window.
- **Password policy is length-only**, twelve characters minimum, no composition rules and no
  rotation, following NIST SP 800-63B. Passwords containing the account's own email local part are
  refused, as is a small list of very common choices. The absence of a real breach corpus is
  recorded as a known gap in `explainer.md` section 7.3.
- **Login does not disclose whether an account exists.** Unknown address, wrong password, and
  deactivated account return identical responses, and the unknown-address path verifies against a
  throwaway hash so Argon2's cost does not make absence measurably faster than a wrong password.
- **Authorisation is declared as decorators on routes**, with the decorator applying
  `@jwt_required` itself so an endpoint cannot be written with only a role check and then fail open
  against an unauthenticated context. Ownership checks live in the service layer, where the row is
  available.
- **Added a route audit test** that walks the whole URL map and fails if any endpoint has neither a
  role requirement nor an entry in an explicit list of intentionally public paths. Adding an
  unprotected endpoint now has to be a deliberate edit to that list.
- **Added administrator self-protection**: an admin cannot deactivate or demote their own account,
  so the last administrator cannot remove the only account able to create another one and leave the
  network unable to broadcast. Donor accounts cannot change role in either direction, because the
  role is tied to a donor record.
- **Added a single error envelope** covering Flask's own HTTP errors, Pydantic validation, JWT
  rejections, integrity errors, and unhandled exceptions. Validation failures are keyed by field so
  a form can attach each message to its input. Token expiry has its own code so the client knows to
  refresh silently rather than redirect to login.
- **Added the pytest suite**: 44 tests over registration, login, the token lifecycle, password
  changes, role enforcement, administrator self-protection, and the error envelope. The schema is
  built by running the real Alembic migration at session start, so a revision that has drifted from
  the models fails the suite.

### Phase 2 - Defects found and fixed during the phase

- **Logout could never succeed.** The refresh cookie was scoped to `/api/auth/refresh`, so it was
  never sent to `/api/auth/logout`, and logout returned 401 every time. The cookie path is now
  `/api/auth`, which is still narrow enough that donor, request, and summary traffic never carries
  the credential. Caught by the logout test.
- **Validation errors were keyed by union variant, not by field.** The registration body used a
  Pydantic discriminated union, which prefixes every error location with the variant tag, so a
  missing name arrived as `patient.full_name` and no form could map it to an input. Replaced with
  an explicit role-to-schema lookup, which also keeps the administrator role structurally
  unreachable from the public endpoint. A test now asserts that no error key contains a dot.
- **The test isolation fixture leaked identity-mapped objects.** Truncating with RESTART IDENTITY
  hands the same primary keys back out, so the previous test's cached objects collided with the
  next test's fixtures. The session is now discarded along with its identity map.
- **Alembic warned about path separator handling**, falling back to splitting paths on spaces,
  commas, and colons, which breaks on a Windows drive letter. `path_separator = os` is now stated
  explicitly.
