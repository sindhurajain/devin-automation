# Devin Automation Service

This repository contains an event-driven automation service for GitHub issues. It listens for issue webhook events, queues tasks in PostgreSQL, and triggers Devin sessions to generate fixes. The project also includes CI configuration and Docker support for local and remote deployment.

## Repository structure

- `automation/` - main FastAPI application and service modules
- `.github/workflows/ci.yml` - GitHub Actions pipeline
- `Dockerfile` - builds the service container
- `docker-compose.yml` - local Docker Compose environment with Postgres
- `.env.example` - environment variable template
- `requirements.txt` - Python dependencies

## Requirements

- Python 3.12
- Docker (for local container builds)
- Docker Compose (optional for local stack)
- GitHub repository access for webhook configuration
- GitHub personal access token for issue commenting and API access
- Devin account/API credentials for session creation and polling
- A GitHub repo or fork (e.g. your Superset fork) for the service to target
- Webhook configured for issue events pointing to the service endpoint
- Railway account or another container deployment platform (for deployments only; local development uses Docker/Docker Compose)

The GitHub token, Devin credentials, target repo/fork, and webhook setup must be configured before using the service for live issue automation.

## Environment variables

Copy `.env.example` to `.env` and adjust values for your environment. Do not commit `.env`.

Required values:

- `GITHUB_TOKEN` - GitHub access token for issue comments
- `GITHUB_REPO` - repository slug, e.g. `owner/repo`
- `GITHUB_WEBHOOK_SECRET` - webhook signature secret
- `DEVIN_API_KEY` - Devin API key
- `DEVIN_ORG_ID` - Devin organization ID
- `DEVIN_REPO_URLS` - comma-separated repository URLs used by Devin
- `DATABASE_URL` - SQLAlchemy database connection URL
- `POSTGRES_PASSWORD` - local Postgres password for Docker Compose
- `LOG_FILE` - path for service logs

## API endpoints

- `GET /health`
- `GET /status`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `GET /metrics`

## Deployed service

The deployed Railway service exposes the Swagger UI and API endpoints at:

- Swagger docs and endpoints: `https://devin-automation-production.up.railway.app/docs`
- Raw task response example: `https://devin-automation-production.up.railway.app/tasks/1`
- Raw tasks response list: `https://devin-automation-production.up.railway.app/tasks`

The current Railway deployment already uses an existing `.env` configuration, so no local `.env` setup is required to access the deployed service (note that deployment is limited by Devin usage capacity).

- Deployed updates are handled by Railway automatically when you merge a PR into `master`.

## Local development with Docker

1. Create `.env` from the example:

```bash
cp .env.example .env
```

2. Copy `.env.example` to `.env` and fill in your own values.

    Follow the format in `.env.example` exactly.

3. Start local services with Docker Compose:

```bash
docker compose up --build
```

4. The FastAPI service will be available at `http://localhost:8080`.

    The service uses PostgreSQL for task persistence. When running with Docker Compose using the provided `.env.example`, Postgres is started automatically and `DATABASE_URL` should already be set correctly. Change it only if you customize the database host, port, or credentials.

    If you want real GitHub webhook events from the Superset fork to reach your local service, start a tunnel after the service is running and then configure the GitHub webhook URL accordingly. If you only need to access the service locally in your browser, a tunnel is not required.

    Example tunnel commands:

    - `ngrok http 8080`
    - `npx localtunnel --port 8080`

    Then configure GitHub with a webhook URL like:

    - `https://<your-tunnel-id>.ngrok.io/webhook`
    - `https://<your-tunnel-id>.loca.lt/webhook`

    Make sure the tunnel URL is the one registered in GitHub and that `GITHUB_WEBHOOK_SECRET` matches the webhook secret configured on the Superset fork.

## Docker build

Build the container image:

```bash
docker build . -t devin-automation
```

Run the image:

```bash
docker run --env-file .env -p 8080:8000 devin-automation
```

## Notes

- Keep `.env` local only.
- `docker-compose.yml` is intended for local development and testing.
