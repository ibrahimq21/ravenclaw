"""
Ravenclaw Sync - JSON File Watcher
Watches inbox JSON for new emails and syncs to Discord
Features:
- Memory leak prevention (max state size)
- In-memory state caching
- Graceful shutdown
"""

import json
import os
import time
import requests
from datetime import datetime
import signal

# Config
INBOX_FILE = 'ravenclaw_inbox.json'
SYNC_STATE_FILE = 'ravenclaw_sync_state.json'
POLL_INTERVAL = 5  # seconds
MAX_SYNC_STATE = 500  # Max msg_nums to track (prevent memory leak)
STATE_CACHE_TTL = 60  # Refresh state from disk every 60 seconds

# Global state
shutdown_requested = False
state_cache = {
    'last_synced_msg_nums': [],
    'last_refresh': 0
}

def load_state():
    """Load state from file"""
    try:
        with open(SYNC_STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'last_synced_msg_nums': []}

def save_state(state):
    """Save state to file with size limit"""
    # Limit state size to prevent memory leak
    if 'last_synced_msg_nums' in state:
        state['last_synced_msg_nums'] = state['last_synced_msg_nums'][-MAX_SYNC_STATE:]
    
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
    """Check for new emails and sync them with state caching"""
    global state_cache
    
    if shutdown_requested:
        return
    
    if not os.path.exists(INBOX_FILE):
        return

    # Refresh state cache periodically
    current_time = time.time()
    if current_time - state_cache['last_refresh'] > STATE_CACHE_TTL:
        fresh_state = load_state()
        state_cache['last_synced_msg_nums'] = fresh_state.get('last_synced_msg_nums', [])
        state_cache['last_refresh'] = current_time
    
    try:
        with open(INBOX_FILE, 'r', encoding='utf-8') as f:
            inbox = json.load(f)
    except Exception as e:
        print(f"[ERROR] Read inbox: {e}")
        return

    last_synced = set(state_cache['last_synced_msg_nums'])
    new_synced = []

    new_count = 0
    for email in inbox.get('emails', []):
        msg_num = email.get('msg_num')
        if msg_num and msg_num not in last_synced:
            # New email found!
            print(f"[NEW] {email.get('sender')} - {email.get('subject')}")
            success = send_to_discord(
                email.get('sender'),
                email.get('subject'),
                email.get('body'),
                email.get('id', msg_num)
            )
            if success:
                new_synced.append(msg_num)
                last_synced.add(msg_num)
                new_count += 1

    # Update state if new emails synced
    if new_synced:
        state_cache['last_synced_msg_nums'] = list(last_synced)[:MAX_SYNC_STATE]
        save_state(state_cache)
        print(f"[SYNC] Complete - {new_count} new emails synced")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    print(f"\n[INFO] Received signal {signum}, shutting down...")
    shutdown_requested = True

def main():
    print("=" * 50)
    print("RAVENCLAW SYNC - JSON File Watcher")
    print("=" * 50)
    print(f"Watching: {INBOX_FILE}")
    print(f"Poll interval: {POLL_INTERVAL}s")
    print(f"Max sync state: {MAX_SYNC_STATE}")
    print(f"State cache TTL: {STATE_CACHE_TTL}s")
    print("=" * 50)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize state cache
    state_cache['last_synced_msg_nums'] = load_state().get('last_synced_msg_nums', [])
    state_cache['last_refresh'] = time.time()
    
    try:
        while not shutdown_requested:
            sync_new_emails()
            if not shutdown_requested:
                time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        pass
    
    print("[INFO] Ravenclaw Sync stopped gracefully")

if __name__ == '__main__':
    main()
