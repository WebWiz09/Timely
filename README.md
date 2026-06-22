# Timely

Highlight any text on the web  a message, an email, an article and Timely reads it, understands the intent, and schedules it directly to your Google Calendar, Tasks, or Gmail. No app switching, no retyping. You stay in the conversation you're already in.

Built for the USAII Global AI Hackathon 2026 — Undergraduate Track, "Productivity: Build the Second Brain for Real Life."

## How it works

1. Highlight text anywhere on the web
2. Click the Timely icon that appears
3. Gemini reads the text and classifies the intent — calendar event, task, or email
4. Timely shows you exactly what it's about to do
5. You confirm — only then does anything touch your real Google account

Nothing executes automatically. Every action is previewed before it's created.

## Architecture

```
Highlighted text
   → Gemini 2.5 Flash + custom system prompt (intent classification, entity extraction)
   → /analyze previews the action
   → user confirms
   → /confirm executes via the relevant Google API
```

## Tech stack

- **Backend:** Flask (Python), deployed on Railway
- **AI:** Gemini 2.5 Flash with a custom structured-output system prompt
- **Frontend:** Chrome Extension (Manifest V3, React + Vite)
- **Integrations:** Google Calendar API, Google Tasks API, Gmail API
- **Auth:** Google OAuth 2.0

## API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/auth/status` | GET | Check if Google is connected |
| `/analyze` | POST | Send highlighted text, get a preview of detected actions |
| `/confirm` | POST | Execute a previously previewed action |

## Running locally

```bash
pip install -r requirements.txt
```

Create a `.env` file with:
```
GEMINI_API_KEY=your_key_here
```

Add your own `client_secrets.json` from Google Cloud Console (OAuth credentials), then run:
```bash
python tm.py
```

## Installing the Chrome extension

1. Go to the [Releases](../../releases) tab of this repo
2. Download the latest `timely-extension.zip`
3. Unzip it
4. Open Chrome → `chrome://extensions`
5. Turn on **Developer Mode** (top right)
6. Click **Load unpacked** → select the unzipped folder
7. Highlight any text on any page to try it

## Team

- **Henry Nnamene** — Backend, AI integration
- **Baqee** — Frontend, Chrome extension
- **Rita** — AI system prompt design and testing

## Responsible AI

Timely never monitors tabs or messages passively it only ever reads a conversation the moment a user explicitly highlights it and clicks. Every action is staged and shown to the user before execution; nothing is created, sent, or modified on a real Google account without explicit confirmation.
