"""Google Calendar (read events) and Gmail (send mail) access.

The CRM data itself lives in PostgreSQL. Google is only used for the admin menu.

One-time setup:
1. Google Cloud Console: create a project, enable "Google Calendar API" and "Gmail API".
2. OAuth consent screen: fill in the app name and add your Google account as a test user.
3. Credentials > Create credentials > OAuth client ID > Desktop app. Download the JSON file.
4. Save it as credentials/credentials.json inside the project folder.

The first call opens a browser for sign-in and creates credentials/token.json.
Google libraries are imported only when needed, so the rest of the app works without them.
"""
import base64
import os
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from paths import app_dir

CREDENTIALS_DIR = os.environ.get("CRM_CREDENTIALS_DIR", os.path.join(app_dir(), "credentials"))
CLIENT_FILE = os.path.join(CREDENTIALS_DIR, "credentials.json")
TOKEN_FILE = os.path.join(CREDENTIALS_DIR, "token.json")
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


class GoogleSetupError(Exception):
    """Raised when Google libraries, credentials or sign-in are not ready."""


def _credentials():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as error:
        raise GoogleSetupError("Google libraries are missing. Run: pip install -r requirements.txt") from error

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds and not set(SCOPES).issubset(set(creds.scopes or [])):
        creds = None  # token was created before a scope was added: sign in again
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not os.path.exists(CLIENT_FILE):
            raise GoogleSetupError(f"credentials.json was not found at {CLIENT_FILE}")
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

    os.makedirs(CREDENTIALS_DIR, exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as handle:
        handle.write(creds.to_json())
    return creds


def format_start(value):
    """Turn Google's ISO start time into dd.mm.yyyy HH:MM (date-only events stay as they are)."""
    if not value:
        return ""
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return value
    return moment.strftime("%d.%m.%Y %H:%M")


def calendar_id():
    """Calendar to read. Set it in credentials/calendar_id.txt (one line), so code updates do not reset it.

    Without that file the main calendar ("primary") is used.
    """
    path = os.path.join(CREDENTIALS_DIR, "calendar_id.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            value = handle.read().strip()
        if value:
            return value
    return "primary"


def fetch_events(days_back=30, days_ahead=60, max_results=100):
    """Return a list of dicts: name, start, participants (list of e-mails), organizer."""
    from googleapiclient.discovery import build

    service = build("calendar", "v3", credentials=_credentials(), cache_discovery=False)
    now = datetime.now(timezone.utc)
    result = service.events().list(
        calendarId=calendar_id(),
        timeMin=(now - timedelta(days=days_back)).isoformat(),
        timeMax=(now + timedelta(days=days_ahead)).isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=max_results,
    ).execute()

    events = []
    for item in result.get("items", []):
        start = item.get("start", {})
        attendees = [a["email"] for a in item.get("attendees", []) if a.get("email")]
        events.append({
            "name": item.get("summary", "(no title)"),
            "start": format_start(start.get("dateTime") or start.get("date", "")),
            "participants": attendees,
            "organizer": item.get("organizer", {}).get("email", ""),
        })
    return events


def send_email(recipients, subject, body):
    """Send a plain-text e-mail from the signed-in Gmail account."""
    from googleapiclient.discovery import build

    service = build("gmail", "v1", credentials=_credentials(), cache_discovery=False)
    message = EmailMessage()
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
