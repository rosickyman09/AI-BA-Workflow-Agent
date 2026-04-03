"""
One-time script to get Google OAuth2 refresh token for Drive uploads.
Auto-writes the token to infra/.env and tests the Drive connection.

Run from project root:
  python backend/scripts/get_google_refresh_token.py

A browser window will open. Sign in with the Google account that OWNS
the AI-BA-Agent Documents Drive folder.
"""

import os
import sys
import pathlib
import re

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("ERROR: Run:  pip install google-auth-oauthlib")
    sys.exit(1)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Read from .env so script works without manual editing
env_path = pathlib.Path(__file__).parent.parent.parent / "infra" / ".env"

def read_env(key: str) -> str:
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key, "")

CLIENT_ID     = read_env("GOOGLE_CLIENT_ID")
CLIENT_SECRET = read_env("GOOGLE_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in infra/.env")
    sys.exit(1)

print(f"Using Client ID: {CLIENT_ID[:30]}...")
print("Starting OAuth2 flow — browser will open...")

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

refresh_token = creds.refresh_token
if not refresh_token:
    print("ERROR: No refresh token returned. Make sure 'prompt=consent' and 'access_type=offline'.")
    sys.exit(1)

print("\n" + "=" * 60)
print("Token obtained!")
print(f"GOOGLE_REFRESH_TOKEN={refresh_token}")
print("=" * 60)

# --- Auto-write to infra/.env ---
if env_path.exists():
    content = env_path.read_text(encoding="utf-8")
    if re.search(r"^GOOGLE_REFRESH_TOKEN=", content, re.MULTILINE):
        content = re.sub(
            r"^GOOGLE_REFRESH_TOKEN=.*$",
            f"GOOGLE_REFRESH_TOKEN={refresh_token}",
            content,
            flags=re.MULTILINE,
        )
    else:
        content += f"\nGOOGLE_REFRESH_TOKEN={refresh_token}\n"
    env_path.write_text(content, encoding="utf-8")
    print(f"Written to: {env_path}")
else:
    print(f"WARNING: Could not find {env_path} — copy token manually.")

# --- Test Drive connection ---
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    test_creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    test_creds.refresh(Request())
    svc = build("drive", "v3", credentials=test_creds)
    about = svc.about().get(fields="user,storageQuota").execute()
    email = about["user"]["emailAddress"]
    quota = about.get("storageQuota", {})
    used_mb = int(quota.get("usage", 0)) // 1024 // 1024
    total_mb = int(quota.get("limit", 0)) // 1024 // 1024
    print(f"\nDrive connection OK!")
    print(f"  Logged in as: {email}")
    print(f"  Storage: {used_mb} MB used / {total_mb} MB total")
    print(f"\nNext step:")
    print(f"  cd infra && docker compose up -d backend")
except Exception as exc:
    print(f"\nWARNING: Drive test failed: {exc}")
    print("Token is written to .env — restart backend manually.")

