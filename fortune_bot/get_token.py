"""
get_token.py - 認証コードからtoken.jsonを生成する（1回限り）
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

CLIENT_ID     = os.getenv("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
AUTH_CODE     = input("認証コードを貼り付けてEnter: ")

flow = InstalledAppFlow.from_client_config(
    {"installed": {
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
    }},
    scopes=["https://www.googleapis.com/auth/youtube.upload"],
    redirect_uri="urn:ietf:wg:oauth:2.0:oob",
)

flow.fetch_token(code=AUTH_CODE)
creds = flow.credentials

token_data = {
    "token":         creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri":     creds.token_uri,
    "client_id":     creds.client_id,
    "client_secret": creds.client_secret,
    "scopes":        list(creds.scopes),
}

token_path = os.path.join(os.path.dirname(__file__), "token.json")
with open(token_path, "w") as f:
    json.dump(token_data, f, indent=2)

print(f"✅ token.json を生成しました: {token_path}")
print(f"   refresh_token: {creds.refresh_token[:20]}...")
