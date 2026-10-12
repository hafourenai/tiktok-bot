"""Instagram OAuth flow management."""

import secrets
import base64
import hashlib
import httpx
import logging
from instagram_db import save_oauth_state, get_oauth_state, save_connection, get_connection, delete_connection

logger = logging.getLogger(__name__)


def generate_pkce():
    """Generate PKCE code_verifier dan code_challenge."""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge


def get_auth_url(telegram_user_id: int) -> str:
    """Generate Instagram OAuth authorization URL."""
    try:
        from config import INSTAGRAM_APP_ID, INSTAGRAM_REDIRECT_URI
        
        state = secrets.token_urlsafe(32)
        code_verifier, code_challenge = generate_pkce()
        
        # Simpan state dan PKCE verifier
        save_oauth_state(state, telegram_user_id, code_verifier)
        
        params = {
            "client_id": INSTAGRAM_APP_ID,
            "redirect_uri": INSTAGRAM_REDIRECT_URI,
            "scope": "user_profile,instagram_business_basic_access",
            "response_type": "code",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        
        auth_url = "https://api.instagram.com/oauth/authorize?" + "&".join(
            f"{k}={v}" for k, v in params.items()
        )
        logger.info(f"Generated auth URL for user {telegram_user_id}")
        return auth_url
    except Exception as e:
        logger.error(f"Failed to generate auth URL: {e}")
        raise


async def exchange_code_for_token(code: str, state: str) -> dict:
    """Tukar authorization code menjadi access token."""
    try:
        from config import INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET, INSTAGRAM_REDIRECT_URI
        
        state_data = get_oauth_state(state)
        if not state_data:
            raise ValueError("State tidak valid atau sudah expired")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://graph.instagram.com/v18.0/access_token",
                data={
                    "client_id": INSTAGRAM_APP_ID,
                    "client_secret": INSTAGRAM_APP_SECRET,
                    "grant_type": "authorization_code",
                    "redirect_uri": INSTAGRAM_REDIRECT_URI,
                    "code": code,
                    "code_verifier": state_data["code_verifier"],
                }
            )
            response.raise_for_status()
            data = response.json()
        
        # Dapatkan user info
        async with httpx.AsyncClient() as client:
            user_response = await client.get(
                f"https://graph.instagram.com/me?fields=id,username&access_token={data['access_token']}"
            )
            user_response.raise_for_status()
            user_data = user_response.json()
        
        # Simpan ke database
        save_connection(
            telegram_user_id=state_data["telegram_user_id"],
            instagram_user_id=user_data["id"],
            instagram_username=user_data["username"],
            access_token=data["access_token"],
            expires_in=data.get("expires_in", 5184000)
        )
        
        logger.info(f"Successfully authenticated user {state_data['telegram_user_id']}: @{user_data['username']}")
        
        return {
            "telegram_user_id": state_data["telegram_user_id"],
            "instagram_username": user_data["username"],
        }
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        raise
