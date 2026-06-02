import hashlib
import hmac
from typing import Any

import requests
from automation.config import settings


GITHUB_API_BASE = "https://api.github.com"


def verify_github_signature(secret: str, signature: str, body: bytes) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature.split("=", 1)[1])


def comment_on_issue(issue_number: int, message: str) -> None:
    url = f"{GITHUB_API_BASE}/repos/{settings.github_repo}/issues/{issue_number}/comments"
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
