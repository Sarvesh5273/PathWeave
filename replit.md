# Running PathWeave on Replit

Keep the imported Python 3.12 / FastAPI structure and existing FalkorDB backend.

## Development

Use the **PathWeave** Run workflow:

```sh
python -m uvicorn app.main:app --host 0.0.0.0 --port 5000
```

Dependencies are pinned in `requirements.txt` and `pyproject.toml`; install them
using Replit's package management. Do not use the README's local `.venv` or
Docker Compose instructions inside Replit.

## Required services

- A reachable FalkorDB server. Configure `FALKORDB_HOST`, `FALKORDB_PORT`,
  `FALKORDB_SSL` (`true` for a TLS endpoint), and optionally `FALKORDB_GRAPH`
  as environment variables. Put its password in the `FALKORDB_PASSWORD` Secret.
  The default local Docker database at `127.0.0.1:16379` is not running here.
- `GROQ_API_KEY` and `TINYFISH_API_KEY` in Replit Secrets for provider features.
  Keep all credentials server-side; do not paste them into source or chat.

The web interface can start without these services, but that does not mean the
application is fully functional. `/api/health` reports graph availability and
provider-key presence (not provider authentication validity).

TinyFish Agent, recurring refresh, and demo tools remain disabled by default.
Do not enable paid/background work merely to test the imported setup.

## Data and verification

Hunts and usage live in ignored `data/runtime/scout.sqlite3`; graph plans live in
the configured FalkorDB server. Do not delete either to fix startup problems.
The repository's original Docker volume and ignored credentials were not imported.
Use synthetic profiles for verification.

Run `python -m pytest -q` for tests. Graph-backed tests need a reachable FalkorDB
instance; use `REQUIRE_FALKORDB=1` to require those tests rather than skip them.
Provider proof scripts make real API calls and should not be run automatically.
