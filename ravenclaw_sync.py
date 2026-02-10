"""
Ravenclaw Sync - JSON File Watcher
Watches inbox JSON for new emails and syncs to Discord
"""

import json
import os
import time
import requests
from datetime import datetime

# Config
INBOX_FILE = 'ravenclaw_inbox.json'
SYNC_STATE_FILE = 'ravenclaw_sync_state.json'
POLL_INTERVAL = 5  # seconds
def load_state():
    try:
        with open(SYNC_STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'last_synced_msg_nums': []}

def save_state(state):
    with open(SYNC_STATE_FILE, 'w') as f:
        json.dump(state, f)

def get_env(key, default=''):
    return os.environ.get(key, default)

DISCORD_WEBHOOK_URL = get_env('DISCORD_WEBHOOK_URL', '')

def send_to_discord(sender, subject, body, msg_id):
    """Send email to Discord via webhook"""
    content = f"""**New Email (Sync)**

From: {sender}
Subject: {subject}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
ID: {msg_id}

---
{body}"""

    if not DISCORD_WEBHOOK_URL:
        print(f"[SKIP] No webhook URL configured")
        return False

    try:
        requests.post(DISCORD_WEBHOOK_URL, json={'content': content}, timeout=10)
        print(f"[DISCORD] {sender} - {subject}")
        return True
    except Exception as e:
        print(f"[ERROR] Discord: {e}")
        return False

def sync_new_emails():
    """Check for new emails and sync them"""
    if not os.path.exists(INBOX_FILE):
        return

    try:
        with open(INBOX_FILE, 'r', encoding='utf-8') as f:
            inbox = json.load(f)
    except Exception as e:
        print(f"[ERROR] Read inbox: {e}")
        return

    state = load_state()
    last_synced = set(state['last_synced_msg_nums'])

    new_count = 0
    for email in inbox.get('emails', []):
        msg_num = email.get('msg_num')
        if msg_num and msg_num not in last_synced:
            # New email found!
            print(f"[NEW] {email.get('sender')} - {email.get('subject')}")
            send_to_discord(
                email.get('sender'),
                email.get('subject'),
                email.get('body'),
                email.get('id', msg_num)
            )
            last_synced.add(msg_num)
            new_count += 1

    if new_count > 0:
        state['last_synced_msg_nums'] = list(last_synced)
        save_state(state)
        print(f"[SYNC] Complete - {new_count} new emails synced")

def main():
    print("=" * 50)
    print("RAVENCLAW SYNC - JSON File Watcher")
    print(f"Watching: {INBOX_FILE}")
    print(f"Poll interval: {POLL_INTERVAL}s")
    print("=" * 50)

    while True:
        sync_new_emails()
        time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    main()
