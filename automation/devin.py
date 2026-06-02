import logging
import time
from typing import Any
import requests
from requests.exceptions import RequestException
from automation.config import settings


logger = logging.getLogger("automation.devin")
DEVIN_BASE_URL = "https://api.devin.ai/v3"


def create_devin_session(issue_number: int, issue_title: str, issue_body: str, repo_url: str) -> dict[str, Any]:
    prompt = (
        f"You are Devin, an autonomous code remediation agent. "
        f"The task is issue #{issue_number} in repository {repo_url}. "
        f"Issue title: {issue_title}\n\nIssue body:\n{issue_body}\n\n"
        "Please fix this issue in the repository by making the minimal patch required, adding tests when appropriate, and creating a pull request. "
        "If you create a PR, return the PR metadata in the session response. "
        "If you need more information, fail with a clear error message instead of guessing."
    )
    configured_repos = [repo.strip() for repo in settings.devin_repo_urls.split(",") if repo.strip()]
    repos = configured_repos or [repo_url]
    payload: dict[str, Any] = {
        "prompt": prompt,
        "title": f"Devin remediation: issue #{issue_number} - {issue_title}",
        "bypass_approval": True,
        "tags": ["devin-fix", "automation", "superset"],
        "repos": repos,
        "devin_mode": settings.devin_mode,
        "structured_output_required": False,
    }
    if settings.devin_create_as_user_id:
        payload["create_as_user_id"] = settings.devin_create_as_user_id

    url = f"{DEVIN_BASE_URL}/organizations/{settings.devin_org_id}/sessions"
    response = requests.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {settings.devin_api_key}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def get_devin_session(session_id: str) -> dict[str, Any]:
    url = f"{DEVIN_BASE_URL}/organizations/{settings.devin_org_id}/sessions/{session_id}"
    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {settings.devin_api_key}",
            "Accept": "application/json",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def cancel_devin_session(session_id: str) -> None:
    if not session_id.startswith("devin-"):
        session_id = f"devin-{session_id}"

    url = f"{DEVIN_BASE_URL}/organizations/{settings.devin_org_id}/sessions/{session_id}"
    try:
        response = requests.delete(
            url,
            headers={
                "Authorization": f"Bearer {settings.devin_api_key}",
                "Accept": "application/json",
            },
            params={"archive": "true"},
            timeout=30,
        )
        if response.status_code == 404:
            logger.info("Devin session terminate endpoint returned 404 for session %s", session_id)
            return
        response.raise_for_status()
        logger.info("Terminated Devin session %s and archived it", session_id)
    except RequestException as exc:
        logger.warning("Failed to terminate Devin session %s: %s", session_id, exc)


def _has_open_pr(session: dict[str, Any]) -> bool:
    pulls = session.get("pull_requests", []) or []
    return any(
        pull.get("pr_state") == "open" and pull.get("pr_url")
        for pull in pulls
    )


def _is_terminal_session(session: dict[str, Any]) -> bool:
    status = session.get("status")
    status_detail = session.get("status_detail")

    if status in {"exit", "error", "suspended"}:
        return True

    if status == "running" and status_detail == "finished":
        return True

    if _has_open_pr(session):
        return True

    return False


def wait_for_session_completion(session_id: str, timeout_seconds: int = 3600, poll_interval: int = 15) -> tuple[dict[str, Any], bool]:
    deadline = time.time() + timeout_seconds
    last_session: dict[str, Any] = {"session_id": session_id, "status": "unknown"}
    while time.time() < deadline:
        try:
            session = get_devin_session(session_id)
            last_session = session
        except RequestException as exc:
            logger.warning(
                "Transient Devin polling error for session %s: %s. Retrying in %s seconds.",
                session_id,
                exc,
                poll_interval,
            )
            time.sleep(poll_interval)
            continue

        if _is_terminal_session(session):
            return session, False

        logger.debug(
            "Session %s still active: status=%s status_detail=%s pull_requests=%s",
            session_id,
            session.get("status"),
            session.get("status_detail"),
            session.get("pull_requests"),
        )
        time.sleep(poll_interval)

    logger.warning(
        "Timed out waiting for Devin session %s after %s seconds; last observed status=%s status_detail=%s. Leaving task in running state for later recovery.",
        session_id,
        timeout_seconds,
        last_session.get("status"),
        last_session.get("status_detail"),
    )
    return last_session, True
