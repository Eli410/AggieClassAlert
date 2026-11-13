# AggieClassAlert

AggieClassAlert is a Discord bot for Texas A&M course monitoring.  
Users can watch specific class sections (by term + CRN) and get notified when seats open.

Invite: https://discord.gg/mwpYwbbnhV

## Features

- Search sections by course and optionally instructor, then add one or many alerts from interactive menus.
- Look up a section directly by CRN and add it to your watchlist.
- View, delete, or reactivate alerts from an interactive `/my_alerts` flow.
- Configure whether notifications are sent by DM or in the server alert channel.
- Automatic background polling checks section availability every 60 seconds.

## Slash Commands

### User Commands

- `/search term course [professor]`
  - Main command for finding sections and creating alerts.
  - Includes autocomplete for term, course, and professor.
- `/search_by_crn`
  - Opens a modal to search by term + CRN and add an alert for that section.
- `/my_alerts [user]`
  - Shows alerts (active + completed) with options to edit, delete, delete all, or reactivate.
- `/setting`
  - User preferences, including DM notification toggle.
- `/status`
  - Shows bot latency and current alert stats.
- `/all_alerts` 
  - view aggregate ranking of most watched alerts.

### Owner/Admin Commands

- `/sync` - sync slash commands for the current server.
- `/restart` - restart the bot process.
- `/say` - send a message to a target channel.

## How It Works

1. User creates alerts via `/search` or `/search_by_crn`.
2. Alerts are stored locally in `tasks.json`.
3. A background task refreshes class availability every minute.
4. When watched sections open, users are notified:
   - DM first if enabled in `/setting`
   - fallback to the configured server alert channel if DM fails/disabled
5. Triggered alerts are marked completed (can be reactivated in `/my_alerts`).

## Setup

### 1) Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Create `.env`

```env
DISCORD_TOKEN=your_discord_bot_token
WEB_LINK_TOKEN=optional_token_for_website_sync
WEB_LINK_URL=optional_callback_url_for_website_sync
```

Only `DISCORD_TOKEN` is required for normal bot operation.  
`WEB_LINK_TOKEN` and `WEB_LINK_URL` are used by the message-link sync flow.

## Run

```bash
python main.py
```

Run in development mode (disables background availability polling):

```bash
python main.py --dev
```

## Notes

- `.env` and runtime JSON state files are gitignored.
- Sample API payloads live under `format_example/`.
