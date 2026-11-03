# Final Polish & Deployment — Design Doc

Date: 2026-11-03
Topic: Feature 8 — Final Polish & Deployment

## Intent and the why

Brew & Bite has all seven customer/admin features implemented and tested (82 tests passing). Before a final review and deployment, the application needs a focused pass on quality, security, configuration, documentation, and deployment readiness. No new product features will be added; every existing feature and its behavior must be preserved.

## Findings from the review

Routes, links, and navigation
- Every `url_for` target in templates resolves to an existing route. No broken links, form actions, or navigation targets found.
- Auth, cart, orders, admin, and customer blueprints are all correctly mounted and guarded.
- Minor redundancy: `/customer` (customer_home) and `/account` (customer.dashboard) both render customer dashboards. Existing behavior; leave as-is (no unrelated refactor).

Page states
- Empty states exist for cart, menu, orders list, and order history.
- Flash messages use the agreed categories (success, error, warning, info).
- No custom 404/500 pages: Flask defaults are used. With debug on, stack traces are exposed to the browser; with debug off, Flask's default plain errors are shown.

Styling and responsiveness
- Media queries exist for the top nav, menu, cart, and admin sidebar.
- Admin sidebar mobile toggle sets `aria-expanded`; the add-to-cart modal uses `aria-hidden`, `role="dialog"`, `aria-modal`, Escape-close, and overlay-click close. Focus-visible styles are present on buttons.
- Contrast and type scale follow the established coffee-brown palette; no gradients/shadows at rest; sentence case; square buttons — consistent with the house style.

Input validation and safe rendering
- Registration, checkout, and cart are validated server-side (email, phone, PIN, password strength/match, required fields, CSRF).
- Order prices/totals are computed on the backend, never trusted from the frontend.
- Jinja auto-escapes output; flash messages and order data are rendered escaped.
- CSRF token `csrf_token` is validated on every state-changing route; login `next` parameter is checked for open redirects.
- Registration can only create customers; admin accounts are created out-of-band via `flask create-admin`.

Uploads
- `secure_filename`, extension allowlist {jpg, jpeg, png, webp}, 16 MB request cap, dedupe file names, and old-image cleanup only when no other product references it.
- No MIME-type or virus scanning; document as a limitation.

Configuration and production readiness (concrete gaps)
- `SECRET_KEY` has a hardcoded default (`"dev-secret-change-in-production"`) in source — a secret-ish value checked into the repo.
- `SESSION_COOKIE_SECURE` defaults to `false`; fine for local HTTP, but production over HTTPS must opt in via env var.
- `app.run(debug=True)` is hardcoded; the dev-server entry point would run with debug enabled if used in production.
- No production WSGI server in `requirements.txt`.
- No migration framework: schema is initialized with `db.create_all()` plus raw `ALTER TABLE` auto-migrations for `users.phone` and `cart_items.notes`.
- Database is SQLite at `instance/cafe.db` (gitignored); uploads live in `app/static/uploads` (gitignored).
- No deployment documentation and no `.env.example`.

## Goals

- Remove hardcoded secret defaults from source; secrets come from environment variables.
- Secure session/cookie defaults: local development keeps working over HTTP; production over HTTPS gets secure cookies.
- Debug mode off by default for any non-dev entry point; dev server behavior unchanged locally.
- Custom 404 and 500 error pages that never expose stack traces or sensitive details.
- Add a production WSGI server to dependencies and document the start command.
- Add deployment documentation (`DEPLOYMENT.md`) and a placeholder-only `.env.example`.
- No schema changes; no new product features; existing behavior preserved.
- All existing tests keep passing; add tests for any config/error-handling changes.

## Non-goals

- Online payment processing (orders remain Cash on Delivery).
- Email/SMS notifications, password reset, user profile editing.
- A migration framework (Flask-Migrate) or schema changes.
- Multi-instance / horizontally scaled deployment architecture.
- Object storage for uploads (local filesystem with persistent volume).
- Assuming or configuring a specific hosting provider.

## Anti-goals (a failure even if it technically works)

- A real secret or credential committed to source control.
- Production running with `debug=True` or stack traces exposed to users.
- Local development broken by secure-cookie defaults (cookies must be sendable over HTTP in dev).
- Existing tests failing or existing feature behavior changing.
- Uploaded images or the database being lost on a routine redeploy.

## Constraints (from AGENTS.md / existing conventions)

- Prices formatted as `&#8377;{{ "%.2f"|format(price) }}`.
- CSRF token named `csrf_token`, validated via each blueprint's `_csrf_valid()`.
- Flash categories: `success`, `error`, `warning`, `info`.
- Orders blueprint has no `url_prefix`; admin blueprint mounted at `/admin`.
- Delivery fee read from `current_app.config["DELIVERY_FEE"]`.
- Order status transitions enforced by `Order.ALLOWED_TRANSITIONS` / `transition_to()`.
- `db.create_all()` on startup + auto-migrations for `users.phone` and `cart_items.notes`; do not duplicate them.
- House style: flat square-cornered buttons, no gradients/shadows at rest, no eyebrows, sentence case, no index numbers.

## Approaches considered

Production detection
   - `APP_ENV` (values: `development` or `production`) is the single reliable production setting. `FLASK_ENV` is deprecated in current Flask and is deliberately not used. `APP_ENV` defaults to `development`, so local development keeps its convenient behavior; an operator deploying to production sets `APP_ENV=production`.

1. SECRET_KEY
   - (a) Keep hardcoded dev default — rejected: places a secret-ish value in source.
   - (b) `os.environ.get("SECRET_KEY") or os.urandom(24)` — chosen for local dev and tests. Works without env; sessions invalidate on restart when using the random fallback, which is acceptable and clearly a dev fallback.
   - (c) Require `SECRET_KEY` and fail fast in production — chosen in addition to (b): when `APP_ENV=production` and `SECRET_KEY` is missing, the app raises `RuntimeError` at startup instead of silently falling back. A misconfigured deployment therefore fails loudly rather than invalidating sessions on every restart.

2. SESSION_COOKIE_SECURE
   - (a) Keep env default `false` — rejected: production over HTTPS is insecure if the operator forgets to set it.
   - (b) Default `true` always — rejected: breaks local development over HTTP (secure cookies aren't sent).
   - (c) Default `true` when `APP_ENV=production`, else `false` — chosen. Local dev works over HTTP; production gets secure cookies unless explicitly overridden.

3. Debug mode / dev server entry point
   - (a) Keep `debug=True` hardcoded — rejected: production must not run debug.
   - (b) `debug` driven by `FLASK_DEBUG` with an `APP_ENV`-aware default — chosen: `FLASK_DEBUG` is honored when explicitly set; otherwise debug is `true` for local development (`APP_ENV=development`) and `false` in production (`APP_ENV=production`). Production uses gunicorn (WSGI) and never touches `app.run`.

4. Error pages
   - (a) Leave Flask defaults — rejected: stack traces exposed in debug; generic plain errors in production.
   - (b) Custom `404` and `500` handlers rendering `templates/errors/404.html` and `templates/errors/500.html` — chosen: consistent UI, no stack traces or sensitive details exposed.

5. Production WSGI server
   - (a) `gunicorn` — chosen: widely used, simple `gunicorn app:app` entry point; add to `requirements.txt`.
   - (b) `waitress` — rejected: fewer community docs, adds an alternative without benefit here.
   - (c) None — rejected: no documented production start command.

6. Database schema
   - (a) Keep `db.create_all()` + auto-migrations — chosen: matches existing conventions, no new dependencies or migration files.
   - (b) Add Flask-Migrate — rejected: scope creep; adds dependency, migration directory, and commands for an app that currently has none.

7. Persistent file storage
   - (a) Local filesystem (`instance/` + `app/static/uploads`) with a persistent volume in production — chosen; document backup/volume requirements.
   - (b) Object storage (S3 etc.) — rejected: scope beyond Feature 8.

## How it gets built (decisions made)

`app/__init__.py`
- Add module-level `_is_production()` returning `True` when `APP_ENV=production` (else `False`; defaults to development).
- `SECRET_KEY = os.environ.get("SECRET_KEY")`; when missing:
  - local/dev/tests: fall back to `os.urandom(24)` (sessions invalidate on restart — clearly a dev fallback).
  - production (`APP_ENV=production`): raise `RuntimeError("SECRET_KEY must be set in production")` at startup — fail fast, no silent fallback.
- `SESSION_COOKIE_SECURE` defaults to `true` when `APP_ENV=production`, else `false`. `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"` unchanged.
- Add `@app.errorhandler(404)` and `@app.errorhandler(500)` rendering `errors/404.html` and `errors/500.html`; no stack traces or request data exposed.
- Keep `db.create_all()`, auto-migrations, and category seeding unchanged.

`app.py`
- `app.run(debug=..., host=..., port=...)` driven by env: `FLASK_DEBUG` honored when explicitly set; otherwise `true` for local development (`APP_ENV=development`) and `false` in production (`APP_ENV=production`). `HOST` (default `127.0.0.1`), `PORT` (default `5000`). Dev-server behavior locally unchanged; production uses gunicorn and never touches `app.run`.

`requirements.txt`
- Add `gunicorn` (production WSGI server). Document `gunicorn app:app` as the production start command.

Templates
- New `app/templates/errors/404.html` and `app/templates/errors/500.html`, both extending `base.html`, with plain copy and a "Back to menu/home" action. No stack traces, no request data.

Documentation (new files)
- `DEPLOYMENT.md`: Python version, dependencies, environment variables (placeholder-only example), local setup and test commands, production start command, DB init/migration steps, static/uploads handling, HTTPS, secret management, backups, operational limitations.
- `.env.example`: placeholder values only, no real credentials or secrets.

Tests
- Add tests for custom error pages (404 renders, 500 renders without stack trace) and session-cookie secure default behavior. Add to the existing test files or a small new test module; keep the full suite green.

Database and persistent-file handling
- No schema changes, no new tables, no column changes. Do not delete, reset, or replace existing data.
- `instance/cafe.db` and `app/static/uploads` are gitignored; in production these must live on persistent storage (volume mount) and be backed up. Uploaded product images survive only if the uploads directory persists across redeploys.

Known risks and limitations
- SQLite is single-instance; not suitable for multi-replica or horizontally scaled deployment. Consider PostgreSQL for that.
- Uploads stored on the local filesystem; ephemeral filesystems (some PaaS) lose images on redeploy unless a persistent volume is mounted.
- The `SECRET_KEY` random fallback invalidates sessions on restart; production must set `SECRET_KEY`.
- Custom error handlers do not catch errors raised before Flask is fully initialized (e.g., import errors); those are deployment/configuration errors.
- No MIME-type or virus scanning of uploaded images.
- Debug error pages still expose stack traces if `FLASK_DEBUG=true` is set in production; documented as something operators must avoid.
- This design does not configure a hosting provider; provider-specific steps (domain, TLS certificate, process manager, object storage) remain for the operator.

## What's left to the builder

- Exact wording and any styling tweaks for `errors/404.html` and `errors/500.html` (keep them consistent with `base.html`).
- Whether `gunicorn` is added to `requirements.txt` as a committed dependency or only documented (recommended: add it, since a production start command should be runnable without manual installs).
- Confirmation that keeping `/customer` and `/account` as separate dashboard routes is acceptable (no consolidation planned).
- The hosting provider and its provider-specific steps (TLS, process manager, persistent volume, backups) are left to the operator and documented as remaining work.

---

This design is ready for your approval. Once you approve it, I'll implement only the approved Feature 8 scope and preserve all existing features. If anything above is wrong or missing, tell me and I'll revise before building.

One question that could change what gets built: should I add `gunicorn` to `requirements.txt` as a committed dependency (so `gunicorn app:app` works out of the box), or only document it and leave installation to the operator?
