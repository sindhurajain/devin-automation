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
- Railway account or another container deployment platform

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

## Local development

1. Create `.env` from the example:

```bash
cp .env.example .env
```

2. Start local services with Docker Compose:

```bash
docker compose up --build
```

3. The FastAPI service will be available at `http://localhost:8000`.

4. Health and status endpoints:

- `GET /health`
- `GET /status`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `GET /metrics`

## Run locally without Docker

Install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run the app:

```bash
uvicorn automation.main:app --host 0.0.0.0 --port 8000
```

## Docker build

Build the container image:

```bash
docker build . -t devin-automation
```

Run the image:

```bash
docker run --env-file .env -p 8000:8000 devin-automation
```

## GitHub Actions CI

The workflow is defined in `.github/workflows/ci.yml` and includes:

- dependency installation
- Python syntax validation
- Docker build verification

The workflow is configured to run on all pushes and pull requests.

## Railway deployment

To deploy on Railway:

1. Ensure your repository is pushed to GitHub.
2. Create or link a Railway project.
3. Configure the deployment branch in Railway.
4. Add required environment variables in Railway settings.
5. Deploy the Docker container.

If you want Railway to deploy only after CI passes, use GitHub branch protection or status check rules.

## Notes

- Keep `.env` local only.
- `docker-compose.yml` is intended for local development and testing.
- The service uses PostgreSQL for task persistence, so make sure `DATABASE_URL` points to a valid database.
