# Blood Donation Network - Architecture Explainer

This is a living document. It explains what the system does, how each piece works, and why each
technology and design decision was made, including the alternatives that were considered and the
reasons they were rejected. It is updated in the same commit as the change it describes.

Last updated: 2026-08-07 (Phase 0)

---

## 1. What the system does

The system connects people who need blood with people who can give it.

A **patient** records a blood request: which blood group, which hospital, how many units, by
when. An **admin** reviews the request and broadcasts it, which selects every donor who is
medically eligible to give right now and sends each of them a notification. **Donors** see those
notifications and respond. As units actually arrive, the admin records each donation against the
request.

The central piece of domain logic is that **one request is normally filled by several different
donors**. A single donor gives roughly one unit; a request for four units needs four people. So a
request is not a binary filled-or-not flag. It accumulates donations and moves through `open`,
`partially_fulfilled`, and finally `fulfilled` only once the cumulative units received meet or
exceed the units required.

The second piece is **eligibility**. A donor who gave blood three weeks ago cannot give again.
Broadcasting to them wastes the notification and, worse, invites a medically unsafe donation.
Eligibility is computed by the server from the donor's record and is never accepted from the
client.

On top of this sits a network summary: how many donations have been arranged, how many requests
were fulfilled against how many are still open, what proportion of notified donors actually
responded, and how many registered donors are eligible to give at this moment.

---

## 2. Actors and permissions

Three roles. An earlier draft had four, including a `coordinator` and a hospital organisation
account; that was rejected because the real actors here are the person giving blood, the person
needing it, and the staff running the network. A hospital is a property of a request, not an
account holder, so it stays a text field on the request rather than becoming a tenant.

| Capability | admin | donor | patient |
| --- | --- | --- | --- |
| Register a donor profile | any donor | self, at sign-up | no |
| Donor directory with identities and contact details | yes | no | no |
| Aggregate eligible-donor counts by group and place | yes | yes | yes |
| Change availability status | any donor | own only | no |
| Create a blood request | yes | no | yes |
| View blood requests | all | only those they were notified about | own only |
| Broadcast a request to eligible donors | yes, exclusively | no | no |
| Record a donation against a request | yes, exclusively | no | no |
| Notification inbox and responding | on a donor's behalf | own | no |
| Network summary | global | no | progress on own requests |
| Manage user accounts | yes | no | no |

**Why broadcast and donation recording are admin-only.** Both were considered as patient
self-service. Broadcasting sends real messages to real people, so letting an unreviewed account
trigger it turns the donor list into a spam surface. Recording donations writes the numbers that
the entire fulfilment state machine and every analytics figure derive from, so letting the
beneficiary of a request write them lets a patient inflate their own progress. Keeping both under
staff control costs one review step and removes both problems.

**Why the donor directory is admin-only.** This follows from admin-only broadcast. Once patients
cannot contact donors directly, they have no workflow reason to see donor names, phone numbers,
or home locations. An earlier design gave patients a partially masked donor list; that was
rejected as unnecessary complexity guarding data they should not receive at all. Patients instead
get an aggregate availability view - counts of eligible donors by blood group and place - which
answers "is there any point filing this request" without identifying anybody.

**Why sign-up is public for donors and patients but never for admins.** A donation network that
requires staff intervention to accept a new donor will not grow. But an admin account can read
every donor's contact details and medical unavailability reason, so it is created only by the
`seed-admin` CLI command from environment variables, or by an existing admin.

---

## 3. Technology decisions

The three stack choices below were fixed by the brief and are recorded for completeness rather
than justified as open decisions.

- **Frontend: React with Vite.**
- **Backend: Python with Flask, serving a REST API.**
- **Database: PostgreSQL.**

Everything from here was an open decision.

### 3.1 ORM: SQLAlchemy 2.0

**Chosen** for its typed declarative models, its explicit unit-of-work transaction handling, and
the fact that it does not hide SQL when the query gets interesting. The fulfilment recomputation
needs a `SELECT ... FOR UPDATE` row lock and the eligibility filter needs a composable SQL
expression reused in three places; SQLAlchemy expresses both naturally.

**Rejected: raw psycopg.** No identity map, no unit of work, and every row-to-object conversion
written by hand. The performance argument does not apply at this scale, and the maintenance cost
is real.

**Rejected: Peewee.** Lighter and pleasant, but weaker PostgreSQL-specific support, no comparable
typing story, and a much smaller migration ecosystem.

**Rejected: the Django ORM.** Genuinely excellent, but it is not separable from Django, and the
brief fixes the backend framework as Flask.

### 3.2 Migrations: Alembic, driven through Flask-Migrate

**Chosen** because Alembic is SQLAlchemy's own migration tool, it autogenerates revisions by
diffing models against the live schema, and every revision has a downgrade path. Flask-Migrate is
a thin wrapper that wires Alembic to the application factory and exposes `flask db` commands, so
migrations run with the same configuration as the app.

**Rejected: hand-written SQL migration files.** No autogeneration, no dependency ordering, and
downgrades exist only if somebody remembers to write them.

**Rejected: `db.create_all()`.** Fine for the first five minutes and unusable after that. It
cannot alter an existing table, so the first schema change loses data or requires a manual
rebuild.

### 3.3 Validation and serialisation: Pydantic v2

**Chosen** to validate every request body and query string at the HTTP boundary and to shape every
response. Pydantic v2's core is compiled Rust, its type coercion rules are predictable, and model
definitions read as ordinary typed Python. Separate input and output models also make it
straightforward to keep fields such as `password_hash` structurally incapable of reaching a
response.

**Rejected: Marshmallow.** Mature and well integrated with SQLAlchemy, but more boilerplate per
schema and materially slower, with a less direct relationship between a schema and a Python type.

**Rejected: hand-rolled dictionary validation.** Every endpoint reinvents type coercion, missing
field handling, and error formatting, and the results diverge.

### 3.4 Application structure: application factory, blueprints, service layer

**Chosen.** `create_app(config)` builds the application, blueprints group the HTTP routes by
resource, and a service layer holds the domain logic - eligibility, fulfilment, broadcast,
summary. Routes parse and authorise; services decide and persist.

This matters specifically because the fulfilment rule and the eligibility rule each have more
than one caller. Eligibility is needed by the donor search filter, by the broadcast selector, and
by the summary count. If that predicate lived inside a route handler it would be copied twice and
the three would drift, which is exactly the kind of divergence that makes an analytics number
quietly wrong.

**Rejected: a single `app.py`.** No configuration isolation, so tests run against the development
database, and no seam at which to test domain logic without an HTTP request.

**Rejected: Flask-RESTful or Flask-Smorest.** They add a resource-class abstraction and their own
serialisation opinions on top of a small, well understood endpoint surface, for little return once
Pydantic is already handling schemas.

### 3.5 Authentication: JWT via Flask-JWT-Extended

**Chosen.** Provides access and refresh token pairs, the `@jwt_required` decorator, identity and
claims loaders, token revocation hooks, and cookie handling, all of which would otherwise be
written by hand.

**Rejected: raw PyJWT.** Signing a token is the easy part. Refresh rotation, expiry handling,
revocation, and the decorator plumbing are the parts that get subtly wrong, and PyJWT provides
none of them.

**Rejected: Authlib.** A full OAuth2 and OIDC server. Appropriate when third parties need to
obtain tokens; far more machinery than a single first-party SPA requires.

**Rejected: server-side session cookies.** Workable, but the brief calls for JWT, and the SPA is
served from a different origin than the API in development.

### 3.6 Password hashing: Argon2id via argon2-cffi

**Chosen.** Argon2id is the current OWASP recommendation. It is memory-hard, which is what
actually degrades large-scale GPU cracking, and argon2-cffi is the reference binding.

**Rejected: bcrypt.** Silently truncates input at 72 bytes, which turns a long passphrase into a
shorter secret than the user believes, and it is not memory-hard.

**Rejected: Werkzeug's default PBKDF2.** Already available and acceptable, but strictly weaker
than Argon2id for no saving beyond one dependency.

### 3.7 Token transport: access token in memory, refresh token in an httpOnly cookie

This is the decision with the largest security consequence, so it is spelled out.

**Chosen.** The access token is short-lived (15 minutes), returned in the login response body, and
held only in React memory - never in `localStorage`, never in `sessionStorage`. The refresh token
is long-lived (7 days) and set as an `httpOnly`, `Secure`, `SameSite=Strict` cookie scoped to the
refresh path. A fetch interceptor catches a 401, silently calls the refresh endpoint, and retries
the original request once.

**Rejected: tokens in `localStorage`.** This is the common pattern and it is readable by any
injected script. This database holds donor phone numbers, home locations, and medical reasons for
unavailability. Token theft here is a concrete harm to identifiable people, not an abstract one,
so the convenience of surviving a page refresh does not justify it. Silent refresh restores that
convenience anyway.

**Rejected: both tokens in httpOnly cookies.** Genuinely secure and supported by the library, but
it makes every mutating request a CSRF target, requiring a double-submit token scheme for no gain
over the chosen split.

### 3.8 Token revocation: a `token_blocklist` table

**Chosen.** Logout inserts the refresh token's JTI into a blocklist table so the session actually
ends. Access tokens are not blocklisted; at a 15-minute lifetime, checking every request against a
table costs a query per request to shorten a worst-case window that is already short.

**Rejected: pure statelessness.** Logout would clear the client and leave a valid refresh token in
existence for seven days, which makes the logout button a lie.

**Rejected: a Redis blocklist.** The right answer at scale. Here it means running another service
to store a handful of rows that PostgreSQL is already positioned to hold.

### 3.9 Login rate limiting: Flask-Limiter

**Chosen** on the login endpoint. An unthrottled login route on a public sign-up system is a
credential-stuffing target. In-memory storage in development, with the storage backend
configurable for deployment.

### 3.10 Notifications: a persisted record plus a pluggable driver

**Chosen.** The `notifications` table is the source of truth: a broadcast writes one row per
selected donor, and that row is what the donor's inbox reads and what the response-rate analytic
counts. Actual delivery goes through a `Notifier` interface with swappable drivers - a console
driver by default, and an SMTP driver enabled by environment variables.

Separating the record from the delivery means the response-rate figure is well defined even when
no mail server is configured, and the broadcast endpoint does not fail because an external service
is down.

**Rejected: SMS through Twilio or similar.** The realistic channel for this problem, and the
correct choice for a real deployment. It requires paid credentials that cannot be exercised or
verified here, so it is left as a driver-shaped hole rather than an untested integration.

**Rejected: calling `smtp.send` inline in the request handler.** Blocks the response on network
I/O, fails the whole broadcast if one address is bad, and leaves no delivery record.

### 3.11 Frontend server state: TanStack Query

**Chosen.** Nearly all state in this application is server state: donor lists, request lists,
notifications, summary figures. TanStack Query handles caching, background refetching, and
invalidation after mutations, which is precisely the problem. Recording a donation invalidates the
request detail, the request list, and the summary, and that is expressed declaratively.

**Rejected: Redux Toolkit.** A large amount of machinery for an application whose client-side
state is little more than the current filter selection and the in-memory access token.

**Rejected: Zustand or plain Context as the data cache.** Perfectly good for UI state, but using
them for server data means hand-writing loading flags, error states, request deduplication, and
cache invalidation. That is reimplementing the library badly.

### 3.12 Routing: React Router

**Chosen** for nested routes and route-level guards, which map directly onto three role-scoped
areas of the application sharing one shell.

**Rejected: a file-system-routed meta-framework such as Next.js or Remix.** Each would replace
Vite, which the brief fixes.

### 3.13 Styling: CSS custom-property design tokens with CSS Modules

**Chosen.** A single token layer defines colour, type scale, spacing, radius, and elevation; each
component has a scoped `.module.css` file consuming those tokens. The brief requires a distinct
original visual identity and high information density, and a token layer is exactly the mechanism
that keeps a dense interface coherent.

**Rejected: Tailwind.** Fast to write, but it pushes the design decisions into class strings
spread across the markup, which makes an original identity harder to define in one place and
harder to change globally. The token layer is the part actually needed here.

**Rejected: Material UI, Chakra, or another component library.** Each arrives with a strong
existing visual identity. The brief asks for a distinct one, so adopting a library would mean
fighting its defaults to look unlike itself.

### 3.14 Testing: pytest against a real PostgreSQL database

**Chosen.** A dedicated `bloodnet_test` database, with each test running inside a transaction that
is rolled back afterwards. The logic worth testing here - the fulfilment recomputation under a row
lock, the eligibility predicate, the cumulative units arithmetic - is expressed in SQL. Testing it
against anything other than PostgreSQL tests the wrong thing.

**Rejected: SQLite as the test database.** Faster and needs no service, but it differs from
PostgreSQL on enums, on `FOR UPDATE`, and on date handling, which are the exact features under
test.

**Rejected: mocking the repository layer.** Would verify that the code calls the functions it
calls, while the SQL that fulfilment correctness depends on goes unexercised.

---

## 4. Design constraints held throughout

- **No emojis** in code, comments, commit messages, user-facing copy, or documentation.
- **No government emblems, insignia, tricolour, or official symbols.** The eRaktKosh portal was
  used as a reference for which screens a blood network needs and how densely they present
  information. None of its branding, imagery, or visual identity is reproduced.
- **Every non-obvious decision is recorded here** in the same commit that makes it.

---

## 5. Sections to be written as their phases land

- Data model: tables, columns, constraints, indexes, and the reasoning behind each refinement to
  the starting schema.
- Domain logic: the eligibility predicate, the fulfilment state machine, and broadcast selection.
- API surface: endpoints, authorisation rules, and any deviation from the suggested surface.
- Frontend architecture: the visual identity, component structure, and the three role-scoped
  areas.
- Deployment and operational notes.
