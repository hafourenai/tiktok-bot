"""FastAPI callback service untuk Instagram OAuth."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
import asyncio
import logging
from instagram_oauth import exchange_code_for_token

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/auth/instagram/callback", response_class=HTMLResponse)
async def instagram_callback(code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    """Handle Instagram OAuth callback."""
    
    if error:
        logger.error(f"OAuth error: {error}")
        return f"""
        <html>
        <head><title>Instagram OAuth Error</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>❌ OAuth Error</h1>
            <p>Error: <code>{error}</code></p>
            <p><a href="https://t.me/YOUR_BOT_USERNAME">← Kembali ke Bot Telegram</a></p>
        </body>
        </html>
        """
    
    if not code or not state:
        logger.error("Missing code or state")
        raise HTTPException(status_code=400, detail="Missing code or state")
    
    try:
        result = await exchange_code_for_token(code, state)
        logger.info(f"Successfully authenticated: {result['instagram_username']}")
        
        return f"""
        <html>
        <head><title>Instagram Terhubung</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>✅ Instagram Terhubung!</h1>
            <p>Akun <strong>@{result['instagram_username']}</strong> berhasil terhubung.</p>
            <p>Anda boleh menutup halaman ini dan kembali ke Telegram.</p>
            <p style="color: #666; margin-top: 30px; font-size: 12px;">
                User ID: {result['telegram_user_id']}
            </p>
        </body>
        </html>
        """
    
    except ValueError as e:
        logger.error(f"State validation failed: {e}")
        return f"""
        <html>
        <head><title>Session Expired</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>❌ Session Expired</h1>
            <p>State token sudah expired atau invalid.</p>
            <p>Coba <code>/instagram_connect</code> lagi di Telegram.</p>
        </body>
        </html>
        """
    
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return f"""
        <html>
        <head><title>Login Gagal</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>❌ Login Gagal</h1>
            <p>Error: <code>{str(e)[:100]}</code></p>
            <p>Coba lagi atau hubungi developer.</p>
        </body>
        </html>
        """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")
