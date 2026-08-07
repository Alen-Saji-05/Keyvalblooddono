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
