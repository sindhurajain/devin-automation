import hashlib
import hmac
import logging
from typing import Any

import requests
from automation.config import settings

logger = logging.getLogger("automation.github")


GITHUB_API_BASE = "https://api.github.com"


def verify_github_signature(secret: str, signature: str, body: bytes) -> bool:
    if not signature or not signature.startswith("sha256="):
        logger.warning("GitHub signature missing or malformed")
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    valid = hmac.compare_digest(digest, signature.split("=", 1)[1])
    if not valid:
        logger.warning("GitHub webhook signature verification failed")
    return valid


def comment_on_issue(issue_number: int, message: str) -> None:
    url = f"{GITHUB_API_BASE}/repos/{settings.github_repo}/issues/{issue_number}/comments"
    logger.info("Posting GitHub comment to issue #%s", issue_number)
    response = requests.post(
        url,
        json={"body": message},
        headers={
            "Authorization": f"token {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "devin-automation",
        },
        timeout=30,
    )
    response.raise_for_status()
    logger.info("Posted GitHub comment to issue #%s", issue_number)
