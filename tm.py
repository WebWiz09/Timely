from flask import Flask, request, jsonify, session
from flask_cors import CORS
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
from datetime import datetime
from google import genai
import os
import json
import pickle
import threading

load_dotenv()

app = Flask(__name__)
app.secret_key = "timely-secret-key-2026"
CORS(app, supports_credentials=True)

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Gemini setup
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Load Rita's system prompt
SYSTEM_PROMPT = open("system_prompt.txt").read()

# Google API scopes
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/gmail.modify"
]

TOKEN_FILE = "token.pickle"
pending_actions = {}

# ─── GOOGLE AUTH ─────────────────────────────────────────────

def get_google_credentials():
    """Load saved credentials, refresh if expired"""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return creds

@app.route("/auth/status")
def auth_status():
    """Extension calls this to check if Google is connected"""
    creds = get_google_credentials()
    if creds and creds.valid:
        return jsonify({"connected": True})
    return jsonify({"connected": False})

@app.route("/auth/connect")
def auth_connect():
    """Opens Google login in browser and saves token when done"""
    def run_flow():
        flow = InstalledAppFlow.from_client_secrets_file(
            "client_secrets.json", SCOPES
        )
        creds = flow.run_local_server(port=8080, open_browser=True)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    thread = threading.Thread(target=run_flow)
    thread.start()
    thread.join()

    return jsonify({"success": True, "message": "Google connected successfully!"})

##Calender 
def create_calendar_event(creds, details):
    service = build("calendar", "v3", credentials=creds)
    
    event = {
        "summary": details.get("event_title"),
        "location": details.get("location"),
        "description": details.get("description"),
        "start": {
            "dateTime": details.get("start"),
            "timeZone": "Africa/Lagos"
        },
        "end": {
            "dateTime": details.get("end"),
            "timeZone": "Africa/Lagos"
        },
        "attendees": [{"email": a} for a in details.get("attendees", []) if "@" in a],
    }
    
    if details.get("meet_link"):
        event["conferenceData"] = {
            "createRequest": {
                "requestId": "timely-meet",
                "conferenceSolutionKey": {"type": "hangoutsMeet"}
            }
        }
    
    created = service.events().insert(
        calendarId="primary",
        body=event,
        conferenceDataVersion=1
    ).execute()
    
    return created.get("htmlLink")

    ## Google Tasks 
def create_task(creds, details):
    service = build("tasks", "v1", credentials=creds)
    
    task = {
        "title": details.get("task"),
        "notes": details.get("notes"),
    }
    
    if details.get("due"):
        task["due"] = details.get("due") + "T00:00:00.000Z"
    
    created = service.tasks().insert(
        tasklist="@default",
        body=task
    ).execute()
    
    return created.get("id")

## Google Gmail
def send_email(creds, details):
    service = build("gmail", "v1", credentials=creds)
    
    message = MIMEText(details.get("body", ""))
    message["to"] = ", ".join(details.get("to", []))
    message["subject"] = details.get("subject", "")
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    if details.get("action") == "draft":
        result = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw}}
        ).execute()
        return result.get("id")
    else:
        result = service.users().messages().send(
            userId="me",
            body={"raw": raw}
        ).execute()
        return result.get("id")

# ─── ANALYZE ROUTE ───────────────────────────────────────────

@app.route("/analyze", methods=["POST"])
def analyze():
    creds = get_google_credentials()
    if not creds or not creds.valid:
        return jsonify({"success": False, "error": "google_not_connected"}), 401

    data = request.json
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    today = datetime.now().strftime("%A, %B %d, %Y")
    full_prompt = SYSTEM_PROMPT + f"\n\nToday's date is: {today}\n\nUser input: " + text

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=full_prompt
    )

    raw = response.text.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "Could not parse AI response"}), 500

    if isinstance(result, dict):
        result = [result]

    needs_confirmation = []
    needs_clarification = []

    for action in result:
        if action.get("status") == "clarification_needed":
            needs_clarification.append({
                "tool": action.get("tool"),
                "question": action.get("question")
            })
            continue

        # Generate a unique ID for this pending action
        import uuid
        action_id = str(uuid.uuid4())

        # Store the full action so /confirm can use it later
        pending_actions[action_id] = action

        needs_confirmation.append({
            "action_id": action_id,
            "tool": action.get("tool"),
            "title": action.get("title"),
            "details": action.get("details")
        })

    return jsonify({
        "success": True,
        "needs_confirmation": needs_confirmation,
        "needs_clarification": needs_clarification
    })



    ## Confirmation
@app.route("/confirm", methods=["POST"])
def confirm():
    creds = get_google_credentials()
    data = request.json
    action_id = data.get("action_id")

    action = pending_actions.get(action_id)
    if not action:
        return jsonify({"success": False, "error": "Action not found or expired"}), 404

    tool = action.get("tool")
    details = action.get("details", {})

    if tool == "google_calendar":
        link = create_calendar_event(creds, details)
        result = {"tool": "google_calendar", "link": link}

    elif tool == "google_tasks":
        task_id = create_task(creds, details)
        result = {"tool": "google_tasks", "id": task_id}

    elif tool == "gmail":
        email_id = send_email(creds, details)
        result = {"tool": "gmail", "id": email_id}

    else:
        return jsonify({"success": False, "error": "Unknown tool"}), 400

    # Remove from pending now that it's done
    del pending_actions[action_id]

    return jsonify({"success": True, "result": result})
# ─── RUN ─────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)