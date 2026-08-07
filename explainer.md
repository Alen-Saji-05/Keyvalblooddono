# Blood Donation Network - Architecture Explainer

This is a living document. It explains what the system does, how each piece works, and why each
technology and design decision was made, including the alternatives that were considered and the
reasons they were rejected. It is updated in the same commit as the change it describes.

Last updated: 2026-08-07 (Phase 3)

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

### 3.14 Session management: Flask-SQLAlchemy over a hand-rolled scoped session

**Chosen.** Flask-SQLAlchemy supplies a request-scoped session and binds engine options to
application config. The declarative base is the project's own `Base`, passed in via
`model_class`, so the models remain plain SQLAlchemy 2.0 classes that import and unit test
without an application context.

**Rejected: managing a `scoped_session` directly.** Entirely doable, and it means writing teardown
handlers that must never be forgotten. A leaked session holds a pooled connection and, worse, an
open transaction, and the symptom shows up much later as unexplained lock contention.

### 3.15 Testing: pytest against a real PostgreSQL database

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

## 5. Data model

Six tables. The four from the brief, plus `users` for authentication and `token_blocklist` for
logout. Every enumerated column is a native PostgreSQL enum type rather than free text, so the
database rejects an invalid value instead of storing it and letting it surface later as a filter
that silently matches nothing.

### 5.1 Refinements to the starting schema, and why

**`donors` gains `sex`, `date_of_birth`, and `weight_kg`.** The brief asks for "any fields needed
to compute medical eligibility". Those three are what the standard whole blood criteria are
actually expressed in: the inter-donation interval differs by sex, donors must be between 18 and
65, and there is a minimum body weight. Without them the system could check availability and
nothing else, and would happily broadcast to someone medically barred from donating.

These are eligibility inputs, not registration barriers. An underweight or over-age person can
still be registered and simply computes as ineligible. Rejecting the registration would throw away
a record that may become eligible later.

**`weight_kg` is `Numeric`, not `float`.** It sits directly in a comparison against a threshold,
and binary floating point can make a value entered as 45.0 compare below 45.

**`donors` gains `status_note`.** The reason for unavailability is encoded in the status itself,
as the brief specifies. This is the free-text detail a human wants alongside it, such as an
expected return date from travel.

**The unavailability reason lives in the status, not a separate column.** `unavailable_moved`,
`unavailable_traveling`, and `unavailable_medical` are distinct status values rather than
`available = false` plus a nullable `reason`. That makes the two invalid combinations -
unavailable with no reason, available with one - unrepresentable rather than merely discouraged.

**`blood_requests` gains `contact_phone`.** A request with no way to reach the requester is not
actionable; a donor who wants to help has to be able to call somebody.

**`blood_requests` gains `created_by_user_id`, nullable, `SET NULL` on delete.** This is what
patient scoping keys off. Matching on the `hospital` text column instead would mean two people
typing "St. Johns" and "St. John's" see different sets, and two unrelated patients at the same
hospital see each other's requests. Nullable because an admin can file a request for someone with
no account; `SET NULL` because deleting a user account must not erase the record that the request
happened.

**`donations` gains `recorded_by_user_id`.** Only an admin can record a donation, and these rows
drive every fulfilment figure and every analytic, so it is worth knowing which account wrote each.

**`notifications` gains `channel` and `delivery_error`.** The channel is recorded per row rather
than read from configuration at display time, so changing the configured driver later does not
rewrite how past broadcasts appear to have been delivered. `delivery_error` records a driver
failure without discarding the notification: the outreach still happened and still counts.

**`notifications` gains a unique constraint on `(donor_id, request_id)`.** Re-broadcasting a
request that is still short of units is a normal thing to do. Without the constraint the second
broadcast creates a second row for the same donor, which both sends a duplicate message and
inflates the denominator of the response-rate figure. The broadcast service therefore skips donors
already notified about that request.

### 5.2 Constraints that hold the invariants

Two invariants are enforced in the database, not only in application code.

**`ck_blood_requests_status_matches_units`** requires that `open` implies zero units received,
`partially_fulfilled` implies a total strictly between zero and the requirement, and `fulfilled`
implies the total meets or exceeds it. One service function writes these columns, but the
constraint means that if any other path ever touches them, the database refuses the write rather
than letting the request list quietly lie about which requests still need donors.

**`ck_notifications_response_at_matches_responded`** requires a response timestamp exactly when
`responded` is true. Otherwise the response rate could be computed from one column while the
timestamps say something different.

**`ck_users_donor_role_requires_donor_link`** requires `donor_id` to be set for the donor role and
null for every other role, so no path can produce a donor account with nothing to manage or an
admin account that owns somebody's donation history.

Foreign key delete behaviour is chosen per relationship rather than uniformly. `donations.donor_id`
is `RESTRICT`, because a donation is a medical record and removing a donor must not silently delete
the history of blood they gave or retroactively change the fulfilment total of a request that was
met. `notifications` and `donations` cascade from their request, because neither means anything
without it.

### 5.3 Indexes

The composite index on `donors (blood_group, status, last_donation_date)` is ordered to match the
eligibility predicate, which filters on exactly those three columns in that order, so one
structure serves the whole broadcast selector and the eligible-donor count.

Place is matched case-insensitively, so the index is on `lower(place)`. An index on the raw column
would simply not be consulted by the query that exists.

Donor email is unique through a partial index over the rows that have one, since the column is
optional.

---

## 6. Domain logic

### 6.1 Eligibility

Expressed once, in `services/eligibility.py`, and rendered two ways from the same thresholds: a
SQL predicate so the database can filter and count without loading rows, and a Python evaluation
that returns the reasons a given donor failed so a person can be told why rather than just
excluded. An eligible-donor count that disagreed with the broadcast selector would be a silently
wrong number on the dashboard, which is exactly what having one definition prevents.

A donor is eligible when they are marked available, are between the configured minimum and maximum
ages, meet the minimum weight, and either have never donated or last donated outside the cooldown
window for their sex.

**The cooldown is sex-dependent, and `other` takes the longer interval.** Erring towards a longer
wait is the safe direction: the cost is a deferred donation, whereas the cost of the opposite error
is a donation that should not have happened.

**Thresholds are configuration, not constants.** The safe inter-donation interval is medical policy
and varies by jurisdiction; the defaults here are 90 days for male donors and 120 for female, ages
18 to 65, and a 45 kg minimum.

**All calendar arithmetic happens in Python before the predicate reaches SQL.** Comparing a column
against a bound date keeps the predicate sargable, so the composite index is used. Wrapping the
column in a date function instead would force the planner to evaluate an expression per row.

**The null branch is load-bearing.** A donor who has never donated has no cooldown to have elapsed.
Without `last_donation_date IS NULL OR ...`, SQL three-valued logic would silently exclude every
first-time donor from every broadcast - a bug that produces no error and simply makes the network
smaller than it is.

### 6.2 Fulfilment

One function, `services/fulfilment.recompute_request_fulfilment`, is the only thing in the codebase
that writes `units_fulfilled` or `status`.

**The total is recomputed with `SUM`, never incremented.** Incrementing compounds any error that
ever gets in, and is simply wrong the moment a donation is corrected or removed. Recomputing makes
the donations table the sole authority and `units_fulfilled` a cache that cannot drift from it.

**The request row is locked with `SELECT ... FOR UPDATE` before the total is read.** Two
administrators recording donations against the same request at the same moment would otherwise both
read the pre-existing total and both write a value that omits the other's donation - a lost update
that leaves a request looking short of blood it actually received. The lock serialises them so the
second transaction sees the first's committed row.

**`fulfilled` is `>=`, not `==`.** A final donation can overshoot the requirement, and an
over-supplied request is fulfilled, not stuck in partial forever.

---

## 7. Authentication and authorisation as built

### 7.1 Endpoints

```
POST   /api/auth/register        public: create a donor or patient account
POST   /api/auth/login           public, rate limited
POST   /api/auth/refresh         refresh cookie; rotates the refresh token
POST   /api/auth/logout          refresh cookie; revokes it
GET    /api/auth/me              any signed-in account
PATCH  /api/auth/me/password     any signed-in account

GET    /api/users                admin
POST   /api/users                admin
GET    /api/users/:id            admin
PATCH  /api/users/:id            admin
```

**Deviation from the planned surface: account management is `/api/users`, not
`/api/auth/users`.** Accounts are a resource that administrators manage; `/api/auth` is reserved
for operations on the caller's own session. Keeping the two apart means the refresh cookie's path
scope covers exactly the session operations and nothing else.

### 7.2 Registration is public, and admin is unreachable from it

A donation network that needs staff intervention to accept a new donor will not grow, so donor and
patient sign-up is open. The admin role cannot be reached through it: the submitted role selects
which Pydantic schema validates the body, and there is no schema registered for admin, so an
escalated value never selects a model and never reaches the service layer. The first admin comes
from the `seed-admin` CLI command; every later one is created by an existing admin.

**Rejected: a Pydantic discriminated union for the registration body.** It was implemented first
and then removed. Pydantic prefixes every error location with the variant tag, so a missing name
came back keyed as `patient.full_name` rather than `full_name`, and the registration form could not
attach a message to its field without knowing to strip a prefix. An explicit role-to-schema lookup
costs four lines and keeps error keys equal to field names. A test asserts that no error key
contains a dot, so the regression cannot return unnoticed.

**Rejected: one schema with optional donor fields.** A patient could then post a blood group and
have it silently ignored, and a donor could omit a required one and only discover it at the
database.

### 7.3 Password policy

Minimum twelve characters, no composition rules, no forced rotation, for every role including
admin. This follows NIST SP 800-63B, which found that mandatory character-class rules and periodic
rotation push people towards predictable substitutions and reuse, while length is what actually
resists guessing. A password is also refused if it contains the local part of the account's own
email address, since such a password is disclosed by the username, and if it appears in a small
built-in list of the most common choices.

**Known gap:** that list is a token gesture, not a breach corpus. A production deployment should
check candidates against a real compromised-password set.

### 7.4 Login does not disclose whether an account exists

Unknown address, wrong password, and deactivated account all return the same 401 with the same
message. A test asserts the two responses are byte-identical. For a medical service, confirming
that a particular person is registered with a blood network is itself a disclosure.

Timing is equalised as well: Argon2 verification is deliberately slow, so returning early on an
unknown address would make "no such account" measurably faster than "wrong password" and turn the
endpoint into an enumeration oracle. The unknown-address path verifies against a throwaway hash so
both paths do the same work.

Registration does disclose that an address is taken, which is unavoidable - a sign-up form that
silently accepted a duplicate would be unusable. The endpoint where enumeration actually matters is
login, and that one does not.

### 7.5 Refresh token rotation

Every refresh revokes the presented token and issues a new one, rather than one token being reused
for its whole seven-day life. Rotation limits a stolen refresh token to a single use, and because
the superseded token is blocklisted, the thief and the legitimate user cannot both keep refreshing:
whichever presents the old token second is rejected, which surfaces the theft rather than hiding
it.

### 7.6 The refresh cookie's path scope

Scoped to `/api/auth`, not to `/api/auth/refresh`.

The narrower scope was implemented first and was wrong: logout has to revoke the refresh token, so
it has to receive it, and a cookie scoped to the refresh path alone is simply never sent to the
logout endpoint. The result was a logout that always returned 401. `/api/auth` is still narrow
enough that donor, request, donation, and summary traffic never carries the credential.

### 7.7 The account is loaded from the database on every authenticated request

Role and donor link travel in the token as claims, so an ordinary authorisation decision needs no
query. But the account row itself is fetched on each request, and that is deliberate: without it,
deactivating an administrator would take effect only when their current access token expired,
leaving up to fifteen minutes in which a disabled account can still read every donor's contact
details and medical unavailability reason. One indexed primary-key lookup in exchange for immediate
deactivation is the right side of that trade. A test asserts that a still-valid access token stops
working the moment the account is deactivated.

Access tokens are not checked against the revocation blocklist for the mirror-image reason: at a
fifteen-minute lifetime that would add a second query per request to shorten a window that is
already short.

### 7.8 Authorisation is declared on the route, and ownership is checked on the row

Role requirements are decorators, so the permission for an endpoint is visible on the line above
it and an endpoint with no decorator is conspicuously public rather than accidentally so. The
decorator applies `@jwt_required` itself, so an endpoint cannot be written with only a role check
and then read from an unauthenticated context and fail open.

A test walks the entire route table and fails if any endpoint has neither a role requirement nor an
entry in an explicit allow-list of intentionally public paths. Adding an unprotected endpoint is
therefore a conscious act recorded in the test file, not something that happens by forgetting a
decorator.

Role is only ever the first filter. Ownership - a patient reading their own request, a donor
answering their own notification - cannot be decided from a token and is enforced in the service
layer where the row is available.

### 7.9 Administrators cannot lock the network out of itself

An admin may not deactivate their own account or change their own role. The concern is not
protecting them from a mistake but the last administrator removing the only account that can create
another one, which would leave the system unable to broadcast any request and no way back short of
the CLI.

A donor account's role can never be changed, in either direction. A donor account is tied to a
donor record: promoting one would orphan the record, and demoting some other account into a donor
would need a record that does not exist. Those cases are handled by creating the right account, not
by mutating one.

### 7.10 One error envelope

Every failure leaves the API as `{"error": {"code", "message", "details"}}`, including Flask's own
404 and 405, Pydantic validation failures, JWT rejections, and unhandled exceptions. Without this,
the client would parse a different shape per error source, and Flask would return HTML for a 404.

Validation errors carry a field-keyed map so a form can attach each message to its input.
Unexpected exceptions and database integrity errors are logged in full and reported generically,
because their messages carry table names, constraint names, connection strings, and row contents.

Token expiry has its own code, `token_expired`, distinct from other 401s, because it is the one
authentication failure the client should answer by silently refreshing rather than by sending the
user to the login screen.

---

## 8. The domain API

### 8.1 Surface

```
GET    /api/meta                          public: enumerations and eligibility thresholds
GET    /api/availability                  any role: eligible donor counts by group, no identities

POST   /api/donors                        admin
GET    /api/donors                        admin: search
GET    /api/donors/:id                    admin, or the donor themselves
PATCH  /api/donors/:id                    admin, or the donor themselves
PATCH  /api/donors/:id/status             admin, or the donor themselves

POST   /api/requests                      patient, admin
GET    /api/requests                      any role, scoped
GET    /api/requests/:id                  any role, scoped
POST   /api/requests/:id/broadcast        admin
POST   /api/requests/:id/donations        admin

POST   /api/notifications/:id/respond     donor (own), admin (on a donor's behalf)

GET    /api/me/donor                      donor
PATCH  /api/me/donor                      donor
PATCH  /api/me/donor/status               donor
GET    /api/me/notifications              donor
GET    /api/me/donations                  donor

GET    /api/summary                       admin (network), patient (own requests)
```

**Deviations from the suggested surface**, each additive:

- `GET /api/availability` and `GET /api/meta` are new. Availability is what replaces the donor
  directory for patients. Meta keeps enum labels on the server so the frontend cannot drift from
  them.
- `/api/me/*` exists because donor self-service endpoints take no donor id at all. There is no
  parameter to tamper with and no ownership check that can be forgotten - the only donor these
  routes can reach is the one on the token.
- `POST /api/notifications/:id/respond` is new. Without it the response rate would be measurable
  only through completed donations, and a donor who says "yes, I will come tomorrow" would be
  counted as having ignored the broadcast.
- `GET /api/requests/:id` returns donations inline, and notifications too for an administrator.

### 8.2 Everything is paginated, and the page size is capped

Including the endpoints that look small today. The donor directory is the case that matters: a real
network has tens of thousands of donors, and an unbounded list endpoint is both a slow query and a
one-request export of the entire contact database. Asking for more than 100 rows is **rejected**
rather than silently clamped, so a caller cannot request everything and be told it worked.

### 8.3 Scoping is a SQL filter, not a post-fetch check

Request visibility - admin sees all, patient sees their own, donor sees the ones they were notified
about - is applied as a `WHERE` clause. A request the caller may not see is never loaded, so it
cannot leak through a pagination total or a count even if a serialiser is later changed.

The default branch of that filter returns nothing rather than everything. If a fourth role is ever
added and this function is not updated, the failure mode is an empty list rather than a disclosure.

Fetching another patient's request returns **404, not 403**. A 403 would confirm the request exists,
which lets anyone enumerate the network's requests by probing ids.

### 8.4 Donor identities on a request are administrator-only

A patient viewing their own request sees the donation count, the units, and the dates - real
progress information - but donor names and ids come back as null, and the notification list is
absent entirely. Donors who gave never agreed to be identified to the patient. An administrator sees
everything, because contacting donors is their job. A test asserts the donor's name does not appear
anywhere in the patient's response body.

### 8.5 Broadcast

Selection is the shared eligibility predicate intersected with the acceptable blood groups, and
optionally narrowed by place. Using the shared predicate rather than an inline copy is what keeps
the broadcast in step with the eligible-donor count on the dashboard and the eligible filter in the
directory; a test asserts the two produce the same number.

**Donors already notified about this request are skipped.** Re-broadcasting a request still short of
units is a normal thing to do. Without the skip, a second broadcast sends a duplicate message and
adds a row that inflates the denominator of the response rate. The unique constraint would reject
the row anyway; the skip turns a would-be error into the intended behaviour.

**Broadcasting a fulfilled request is refused with a 409**, not accepted as a harmless no-op.
Sending donors to a hospital that no longer needs them wastes a donation that could have gone to an
open request, and costs the network credibility with the people it depends on. A partially fulfilled
request can still be broadcast, because it still needs blood.

**The result reports what was skipped, not only what succeeded.** An administrator who sees
"0 notified" needs to know whether there are no eligible donors of that group or whether everyone
eligible was already told, because those call for completely different next steps.

**Compatibility widening is opt-in.** `include_compatible=true` widens from an exact group match to
the transfusion compatibility matrix, so an O-negative donor can be called for any recipient. It is
off by default so the behaviour matches the brief exactly and an administrator opts into a wider
list knowingly.

### 8.6 Notification delivery is separate from the notification record

The `notifications` row is the source of truth. Delivery goes through a driver - console by default,
SMTP when configured. A driver failure records the reason against that one notification and the
broadcast continues; it does not abort outreach to two hundred other people, and it does not discard
the record, because the outreach still happened.

That separation is also what makes the response rate well defined with no mail server configured.

### 8.7 Recording a donation

One transaction, and the order is load-bearing. See section 8.8.

Three side effects beyond the donation row itself:

- **Fulfilment is recomputed**, so `units_fulfilled` and `status` follow from the donations table.
- **The donor's `last_donation_date` moves forward only.** Guarded with a comparison rather than
  assigned, because an administrator entering a backlog of paper records out of order would
  otherwise move the date backwards and make a donor look eligible months before they are.
- **Any matching notification is marked responded.** Somebody who turned up and gave has responded
  by any reasonable definition, so the response rate counts people who actually helped rather than
  only those who clicked a button.

A donation dated before the request was created is refused. It cannot have been given in response to
an appeal that did not exist, and it is almost always a mistyped year.

### 8.8 The deadlock, and the lock ordering that fixes it

This is the most consequential thing found in this phase, and it was found by a test rather than in
production.

Recording a donation originally inserted the donation row and *then* took the `FOR UPDATE` lock on
the request to recompute fulfilment. Under two concurrent writers that deadlocks, reliably:
inserting a row with a foreign key takes a `FOR KEY SHARE` lock on the referenced request, so each
transaction ends up holding a key-share lock that the other's exclusive lock must wait for.
PostgreSQL detects the cycle and kills one transaction.

The fix is to acquire the exclusive lock **first**, before inserting, so every writer takes locks in
the same order and the second simply waits for the first to commit. A test drives the real service
function from two threads on separate connections and asserts both that no error is raised and that
neither donation is lost.

The single-threaded tests all passed before the fix. Concurrency bugs of this shape do not appear
under sequential testing, which is why the test uses real connections rather than one session.

### 8.9 The summary

The four figures the brief asks for, plus the context needed to read them.

- **Donations arranged** is reported as both a count of events and a sum of units, because forty
  donations of one unit is not the same operational picture as twenty of two.
- **Fulfilled against unfulfilled** splits unfulfilled into open and partially fulfilled. A request
  at three of four units needs one more donor; a request at zero needs a broadcast. Averaging them
  into one number hides which is which.
- **Donor response rate** uses notifications sent as the denominator, not distinct donors, so a
  donor notified about three requests counts three times. That is the right denominator for
  measuring whether broadcasts work.
- **Donors eligible right now** uses the same predicate as the broadcast selector. This is the whole
  reason eligibility is defined once. It is deliberately distinct from both "registered" and
  "available": in the test scenario six donors are registered, five are marked available, and one is
  eligible, because three have just donated and one is underweight.

The same endpoint serves patients with `scope: "own_requests"`, counting only their own requests.
Donor counts stay network-wide because they are aggregate, carry no identities, and are exactly what
tells a patient whether their request has any prospect of being met.

Donors get no summary at all. Their view is their own inbox and donation history; how many requests
are going unmet across the network is not a figure to publish to the people the network depends on.

---

## 9. Sections to be written as their phases land

- Frontend architecture: visual identity, component structure, and the three role-scoped areas.
- Frontend architecture: the visual identity, component structure, and the three role-scoped
  areas.
- Deployment and operational notes.
