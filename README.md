# Property Revenue Dashboard

Debugging fixes for the existing PropertyFlow assignment. The original FastAPI,
React, PostgreSQL, and Redis structure is retained.

## Run

```sh
docker compose up --build -d
```

- Dashboard: http://localhost:3000
- API documentation: http://localhost:8000/docs
- Logs: `docker compose logs --tail 100 backend`

Use the two client accounts in [ASSIGNMENT.md](ASSIGNMENT.md). The dashboard defaults
to March 2024 because that is the month used by the supplied reservation fixtures.

## Test

Run the backend suite, including PostgreSQL integration tests:

```sh
docker compose exec -T -e RUN_DATABASE_TESTS=1 backend python -m unittest discover -s tests -v
```

The database tests insert their own fixtures inside transactions and roll them back.
They do not change the supplied sample data.

For browser checks using an installed Microsoft Edge and `uv`:

```sh
uv run --no-project --with playwright python scripts/check_dashboard.py --channel msedge
```

Alternatively, install Playwright's Chromium and omit `--channel`:

```sh
uv run --no-project --with playwright playwright install chromium
uv run --no-project --with playwright python scripts/check_dashboard.py
```
