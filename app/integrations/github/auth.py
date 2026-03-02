"""
GitHub App authentication utilities.
"""

import time

import jwt

from app.core.config import settings
from app.core.http_client import http_client


async def get_access_token(installation_id: int) -> str:
    """Exchanges Private Key + Installation ID for a temporary Token"""
    # Create the JWT (The "ID Badge" for the App)
    payload = {
        "iat": int(time.time()) - 60,
        "exp": int(time.time()) + (10 * 60),
        "iss": settings.GITHUB_APP_ID,
    }
    jwt_token = jwt.encode(payload, settings.GITHUB_APP_PRIVATE_KEY, algorithm="RS256")

    # Request the Token from GitHub
    resp = await http_client.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        },
    )
    resp.raise_for_status()
    return resp.json()["token"]
