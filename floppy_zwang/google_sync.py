import os
import pickle
import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from db import get_gc_event_id, map_task_to_gc

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS_DIR = os.path.join(BASE_DIR, "..", "secrets")

CREDENTIALS_FILE = os.path.join(SECRETS_DIR, "credentials.json")
TOKEN_PICKLE = os.path.join(SECRETS_DIR, "token.pickle")


def google_get_service():
    creds = None
    if os.path.exists(TOKEN_PICKLE):
        with open(TOKEN_PICKLE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PICKLE, "wb") as f:
            pickle.dump(creds, f)

    return build("calendar", "v3", credentials=creds)


def task_to_event_body(task):
    tid, title, desc, due, priority, tags, completed = task

    if due:
        dt = datetime.datetime.strptime(due, "%Y-%m-%d").date()
        return {
            "summary": f"[Task] {title}",
            "description": (desc or "") + f"\n\nTags: {tags or ''}",
            "start": {"date": dt.isoformat()},
            "end": {"date": (dt + datetime.timedelta(days=1)).isoformat()},
        }
    else:
        now = datetime.datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
        return {
            "summary": f"[Task] {title}",
            "description": (desc or "") + f"\n\nTags: {tags or ''}",
            "start": {"dateTime": now.isoformat()},
            "end": {"dateTime": (now + datetime.timedelta(hours=1)).isoformat()},
        }


def push_task_to_google(task):
    service = google_get_service()
    event_body = task_to_event_body(task)
    existing_id = get_gc_event_id(task[0])

    if existing_id:
        try:
            updated = service.events().patch(
                calendarId="primary", eventId=existing_id, body=event_body
            ).execute()
            return updated["id"]
        except Exception:
            pass

    created = service.events().insert(calendarId="primary", body=event_body).execute()
    return created["id"]
