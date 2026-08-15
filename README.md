# Investment Observatory

A private, self-hosted investment journal for a calm daily review of holdings and watchlist movement. It is monitoring software, not a brokerage, accounting system, or source of financial advice.

## Local development

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

The default development configuration uses PostgreSQL. For the supported deployment path:

```bash
cp .env.example .env
# replace every placeholder before exposing the service

docker compose up -d --build
docker compose exec web alembic upgrade head
```

Open http://localhost:8000. The first run intentionally contains no fabricated sample data; add a real security through the search action.

## Data sources

The initial adapter uses Yahoo's public chart/search endpoints for personal, low-frequency use and Google News RSS for linked headlines. Both are isolated behind provider interfaces and can be replaced. See `docs/data-sources.md` for limitations, rate protection, and the requirements for validating current terms before wider use.

## Operations

- `GET /health/live` checks process liveness.
- `GET /health/ready` checks database readiness.
- The worker runs hourly market sync and periodic RSS sync.
- Back up PostgreSQL before upgrades; see `docs/backup.md`.

Never commit `.env`, provider credentials, dumps, or personal holdings.

## Security

This repository is public by design, but deployments are intended for a trusted LAN or a reverse proxy with authentication. The Compose file refuses to start without explicit database credentials; the production deployment script generates those credentials on the server and stores them in a mode-600 `.env` file outside Git.

The application is a monitoring tool, not a brokerage or account aggregator. Do not add brokerage credentials, transaction exports, or personal holdings data to this repository. See `SECURITY.md` for reporting a vulnerability.
