# ravenclaw.py
"""
Ravenclaw - Secure Email Bridge for Discord
============================================
Features:
- POP3 email fetching with domain filtering
- Discord webhook integration
- SMTP email sending
- Scheduled emails with JSON queue
- Scheduled checks every 30 minutes
- Secure credential management via .env
- Auto-reply capabilities
- Conversation threading
- Inbox storage in JSON file
- Memory leak prevention (max emails, log rotation)
"""

import poplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import time
import json
import re
import threading
import logging
import sys
import os
from datetime import datetime
from flask import Flask, request, jsonify
import signal
import atexit
from logging.handlers import RotatingFileHandler

# ========== CONFIG ==========

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

def load_env():
    """Load environment variables from .env"""
    if not os.path.exists(ENV_FILE):
        print(f"[WARN] {ENV_FILE} not found!")
        return
    
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

def get_env(key, required=False, default=None):
    val = os.environ.get(key, default)
    if required and not val:
        raise ValueError(f"Required env var {key} not set!")
    return val

# Email settings
EMAIL = {
    'host': get_env('EMAIL_HOST', False, 'mail.example.com'),
    'pop_port': int(get_env('EMAIL_POP_PORT', False, '995')),
    'smtp_port': int(get_env('EMAIL_SMTP_PORT', False, '587')),
    'username': get_env('EMAIL_USERNAME', True),
    'password': get_env('EMAIL_PASSWORD', True)
}

# Domain filter
DOMAIN_FILTER = get_env('DOMAIN_FILTER', False, 'example.com')
ALLOWED_DOMAINS = [d.strip() for d in DOMAIN_FILTER.split(',')]

# Discord settings
DISCORD = {
    'webhook_url': get_env('DISCORD_WEBHOOK_URL', False, ''),
    'use_webhook': get_env('DISCORD_USE_WEBHOOK', False, 'false').lower() == 'true',
    'openclaw_url': get_env('OPENCLAW_URL', False, 'http://localhost:3000/api/message')
}

# Bridge settings
BRIDGE = {
    'host': get_env('BRIDGE_HOST', False, '0.0.0.0'),
    'port': int(get_env('BRIDGE_PORT', False, '5002')),
    'poll_interval': int(get_env('BRIDGE_POLL_INTERVAL', False, '30'))
}

# Auto-reply settings
AUTO_REPLY = {
    'enabled': get_env('AUTO_REPLY_ENABLED', False, 'false').lower() == 'true',
    'template': get_env('AUTO_REPLY_TEMPLATE', False, 
        "Thank you for your email. I've received your message and will respond shortly.\n\n- Enoth")
}

# Scheduled email settings
SCHEDULED = {
    'queue_file': 'ravenclaw_scheduled.json',
    'sent_file': 'ravenclaw_sent.json',  # Track sent emails across restarts
    'max_attempts': 3,
    'check_interval': 60  # seconds
}

# Memory leak prevention
MAX_EMAILS = 1000  # Keep last 1000 emails max
MAX_LOG_SIZE = 1024 * 1024  # 1MB
MAX_LOG_BACKUPS = 5

# Global shutdown flag
shutdown_requested = False

# Logging with rotation
logger = logging.getLogger('ravenclaw')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [RAVENCLAW] %(message)s')

# File handler with rotation
file_handler = RotatingFileHandler('ravenclaw.log', maxBytes=MAX_LOG_SIZE, backupCount=MAX_LOG_BACKUPS, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ========== FLASK APP ==========

app = Flask(__name__)

# ========== FILE PATHS ==========

INBOX_FILE = 'ravenclaw_inbox.json'
PROCESSED_FILE = 'ravenclaw_processed.txt'

# ========== HELPERS ==========

def get_domain(email_addr):
    """Extract domain from email"""
    m = re.search(r'@([a-zA-Z0-9.-]+)', email_addr)
    return m.group(1).lower() if m else None

def is_allowed(email_addr):
    """Check if email domain is allowed"""
    domain = get_domain(email_addr)
    return domain and any(domain == d.lower() for d in ALLOWED_DOMAINS)

def parse_body(msg):
    """Extract plain text from email"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    body = part.get_payload(decode=True).decode('latin-1')
                break
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='replace')
        except:
            body = msg.get_payload(decode=True).decode('latin-1')
    return body

def load_inbox():
    """Load inbox from JSON file"""
    try:
        with open(INBOX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {'emails': []}

def save_inbox(inbox):
    """Save inbox to JSON file with max emails limit"""
    # Trim to max emails to prevent memory leak
    if 'emails' in inbox and len(inbox['emails']) > MAX_EMAILS:
        inbox['emails'] = inbox['emails'][:MAX_EMAILS]
        logger.info(f"Trimmed inbox to {MAX_EMAILS} emails")
    
    with open(INBOX_FILE, 'w', encoding='utf-8') as f:
        json.dump(inbox, f, indent=2, ensure_ascii=False)

def load_processed():
    """Load processed message IDs"""
    try:
        with open(PROCESSED_FILE, 'r') as f:
            return set(line.strip() for line in f)
    except:
        return set()

def save_processed(msg_id):
    """Save processed message ID"""
    with open(PROCESSED_FILE, 'a') as f:
        f.write(msg_id + '\n')

# ========== SCHEDULED EMAIL FUNCTIONS ==========

def load_scheduled_queue():
    """Load scheduled email queue from JSON file"""
    try:
        with open(SCHEDULED['queue_file'], 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Sync with persistent sent IDs to ensure no re-sending
            sent_ids = load_sent_ids()
            for email_entry in data.get('emails', []):
                if email_entry.get('id') in sent_ids:
                    email_entry['status'] = 'sent'
                    if not email_entry.get('sent_at'):
                        email_entry['sent_at'] = datetime.now().isoformat()
            
            # Filter out old sent emails (older than 7 days)
            cutoff = datetime.now().timestamp() - (7 * 24 * 60 * 60)
            data['emails'] = [e for e in data.get('emails', []) 
                             if e.get('status') != 'sent' or 
                             (e.get('status') == 'sent' and 
                              datetime.fromisoformat(e.get('sent_at', '2000-01-01')).timestamp() > cutoff)]
            return data
    except:
        return {'version': '1.0', 'emails': []}

def save_scheduled_queue(queue):
    """Save scheduled email queue to JSON file"""
    with open(SCHEDULED['queue_file'], 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)

def load_sent_ids():
    """Load IDs of already-sent emails"""
    try:
        with open(SCHEDULED['sent_file'], 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get('sent_ids', []))
    except:
        return set()

def save_sent_ids(sent_ids):
    """Save sent email IDs to persistent file"""
    with open(SCHEDULED['sent_file'], 'w', encoding='utf-8') as f:
        json.dump({'sent_ids': list(sent_ids)}, f, indent=2)

def send_smtp(to, subject, body, in_reply_to=None):
    """Send email via SMTP"""
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = f"Enoth <{EMAIL['username']}>"
    msg['To'] = to
    if in_reply_to:
        msg['In-Reply-To'] = in_reply_to
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    try:
        with smtplib.SMTP(EMAIL['host'], EMAIL['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL['username'], EMAIL['password'])
            server.send_message(msg)
        logger.info(f"Sent SMTP: {to}")
        return True
    except Exception as e:
        logger.error(f"SMTP error: {e}")
        return False

def check_and_send_scheduled():
    """Check scheduled emails and send those ready"""
    if shutdown_requested:
        return
    
    queue = load_scheduled_queue()
    now = datetime.now().isoformat()
    now_ts = datetime.now().timestamp()
    
    # Load persistent sent IDs to prevent re-sending across restarts
    sent_ids = load_sent_ids()
    
    updated = False
    
    for email_entry in queue.get('emails', []):
        email_id = email_entry.get('id')
        
        # Skip if already sent (persistent check)
        if email_id in sent_ids:
            continue
        
        if email_entry.get('status') == 'sent':
            continue
        
        # Check if it's time to send
        try:
            target_time = datetime.fromisoformat(email_entry.get('target_time'))
            if target_time.timestamp() <= now_ts:
                # Try to send
                success = send_smtp(
                    email_entry['to'],
                    email_entry['subject'],
                    email_entry['body']
                )
                
                if success:
                    email_entry['status'] = 'sent'
                    email_entry['sent_at'] = now
                    sent_ids.add(email_id)  # Track persistently
                    save_sent_ids(sent_ids)  # Save immediately
                    logger.info(f"Scheduled email sent: {email_entry['to']} ({email_id})")
                else:
                    email_entry['attempts'] = email_entry.get('attempts', 0) + 1
                    email_entry['last_attempt'] = now
                    
                    if email_entry['attempts'] >= SCHEDULED['max_attempts']:
                        email_entry['status'] = 'failed'
                        email_entry['error'] = 'Max attempts reached'
                        logger.error(f"Scheduled email failed: {email_entry['to']}")
                
                updated = True
                
        except Exception as e:
            logger.error(f"Error processing scheduled email: {e}")
    
    if updated:
        save_scheduled_queue(queue)

# ========== DISCORD/EMAIL FUNCTIONS ==========

def send_discord(sender, subject, body, msg_id):
    """Forward email to Discord"""
    content = f"""**New Email**

From: {sender}
Subject: {subject}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
ID: {msg_id}

---
{body}"""

    # Discord webhook
    if DISCORD['use_webhook'] and DISCORD['webhook_url']:
        try:
            requests.post(DISCORD['webhook_url'], json={'content': content}, timeout=10)
            logger.info(f"Discord: {sender}")
            return True
        except Exception as e:
            logger.error(f"Webhook error: {e}")
    
    # OpenClaw fallback
    try:
        requests.post(DISCORD['openclaw_url'], json={
            'channel': 'discord',
            'message': content,
            'metadata': {'reply_to': sender, 'message_id': msg_id, 'type': 'email'}
        }, timeout=10)
        logger.info(f"OpenClaw: {sender}")
        return True
    except:
        return False

# ========== EMAIL PROCESSING ==========

def check_inbox():
    """Main email check function - reads emails and saves to JSON"""
    if shutdown_requested:
        logger.info("Shutdown requested, skipping inbox check")
        return
    
    logger.info("Checking inbox...")
    
    processed_ids = load_processed()
    inbox = load_inbox()
    
    new_emails = []
    
    try:
        mail = poplib.POP3_SSL(EMAIL['host'], EMAIL['pop_port'])
        mail.user(EMAIL['username'])
        mail.pass_(EMAIL['password'])
        
        _, msg_list, _ = mail.list()
        
        if not msg_list:
            mail.quit()
            logger.info("No emails found")
            return
        
        for line in msg_list:
            msg_num = line.decode().split()[0]
            
            if msg_num in processed_ids:
                continue
            
            try:
                _, lines, _ = mail.retr(msg_num)
                msg = email.message_from_bytes(b'\r\n'.join(lines))
                
                sender = email.utils.parseaddr(msg['From'])[1]
                subject = msg['Subject']
                msg_id = msg.get('Message-ID', f'<{msg_num}@ravenclaw>')
                body = parse_body(msg)
                timestamp = datetime.now().isoformat()
                
                # Check domain filter
                if not is_allowed(sender):
                    logger.info(f"Rejected: {sender} (domain not allowed)")
                    save_processed(msg_num)
                    continue
                
                # Save to inbox JSON
                email_data = {
                    'id': msg_id,
                    'msg_num': msg_num,
                    'sender': sender,
                    'subject': subject,
                    'body': body,
                    'timestamp': timestamp,
                    'read': False,
                    'replied': False
                }
                
                inbox['emails'].insert(0, email_data)
                new_emails.append(email_data)
                
                logger.info(f"Received: {sender} - {subject}")
                
            except Exception as e:
                logger.error(f"Error processing msg {msg_num}: {e}")
        
        # Save updated inbox (with trim)
        if new_emails:
            save_inbox(inbox)
            
            # Forward to Discord
            for email_data in new_emails:
                send_discord(email_data['sender'], email_data['subject'], 
                           email_data['body'], email_data['id'])
                
                # Auto-reply
                if AUTO_REPLY['enabled']:
                    auto_body = AUTO_REPLY['template']
                    send_smtp(email_data['sender'], email_data['subject'], 
                             auto_body, email_data['id'])
        
        mail.quit()
        
        # Mark all as processed (don't delete from server)
        for msg_num in msg_list:
            msg_num = msg_num.decode().split()[0]
            if msg_num not in processed_ids:
                save_processed(msg_num)
        
        logger.info(f"Check complete. New: {len(new_emails)}, Total in inbox: {len(inbox['emails'])}")
        
    except Exception as e:
        logger.error(f"Inbox check failed: {e}")

# ========== ROUTES ==========

@app.route('/')
def index():
    return f"""<h1>Ravenclaw Email Bridge</h1>
<p>Status: Running</p>
<p>Account: {EMAIL['username'][:5]}***</p>
<p>Domains: {', '.join(ALLOWED_DOMAINS)}</p>
<p>Emails in inbox: {len(load_inbox().get('emails', []))}</p>
<p>Auto-reply: {'Enabled' if AUTO_REPLY['enabled'] else 'Disabled'}</p>"""

@app.route('/health')
def health():
    return jsonify({
        'status': 'running',
        'account': EMAIL['username'][:5] + '***',
        'domains': ALLOWED_DOMAINS,
        'emails_count': len(load_inbox().get('emails', [])),
        'auto_reply': AUTO_REPLY['enabled']
    })

@app.route('/inbox')
def get_inbox():
    """Get all emails from inbox JSON"""
    inbox = load_inbox()
    return jsonify(inbox)

@app.route('/inbox/<msg_id>')
def get_email(msg_id):
    """Get specific email by ID"""
    inbox = load_inbox()
    for email_data in inbox.get('emails', []):
        if email_data['id'] == msg_id or email_data['msg_num'] == msg_id:
            email_data['read'] = True
            save_inbox(inbox)
            return jsonify(email_data)
    return jsonify({'error': 'Email not found'}), 404

@app.route('/unread')
def get_unread():
    """Get unread emails"""
    inbox = load_inbox()
    unread = [e for e in inbox.get('emails', []) if not e.get('read', False)]
    return jsonify({'unread': unread, 'count': len(unread)})

@app.route('/send', methods=['POST'])
def send_email():
    """Send email reply"""
    data = request.json
    required = ['to', 'subject', 'body']
    for r in required:
        if r not in data:
            return jsonify({'error': f'Missing: {r}'}), 400
    
    if not is_allowed(data['to']):
        return jsonify({'error': 'Domain not allowed'}), 403
    
    success = send_smtp(data['to'], data['subject'], data['body'], data.get('in_reply_to'))
    return jsonify({'status': 'sent' if success else 'failed'})

# ========== SCHEDULED EMAIL ROUTES ==========

@app.route('/schedule', methods=['POST'])
def schedule_email():
    """
    Schedule an email to be sent later.
    Body:
    {
        "to": "recipient@domain.com",
        "subject": "Email subject",
        "body": "Email body",
        "target_time": "2026-02-17T09:00:00"  # ISO-8601 timestamp
    }
    """
    data = request.json
    required = ['to', 'subject', 'body', 'target_time']
    for r in required:
        if r not in data:
            return jsonify({'error': f'Missing: {r}'}), 400
    
    # Validate target_time format
    try:
        target = datetime.fromisoformat(data['target_time'])
        if target.timestamp() <= datetime.now().timestamp():
            return jsonify({'error': 'target_time must be in the future'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid target_time format. Use ISO-8601 (e.g., 2026-02-17T09:00:00)'}), 400
    
    if not is_allowed(data['to']):
        return jsonify({'error': 'Domain not allowed'}), 403
    
    # Load queue and add email
    queue = load_scheduled_queue()
    
    email_entry = {
        'id': f"sched_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(queue.get('emails', []))}",
        'to': data['to'],
        'subject': data['subject'],
        'body': data['body'],
        'target_time': data['target_time'],
        'created_at': datetime.now().isoformat(),
        'status': 'pending',
        'attempts': 0,
        'last_attempt': None,
        'error': None,
        'priority': data.get('priority', 'normal')
    }
    
    queue['emails'].append(email_entry)
    save_scheduled_queue(queue)
    
    logger.info(f"Scheduled email: {data['to']} for {data['target_time']}")
    
    return jsonify({
        'status': 'scheduled',
        'id': email_entry['id'],
        'target_time': data['target_time']
    })

@app.route('/schedule/list')
def list_scheduled():
    """List all scheduled emails"""
    queue = load_scheduled_queue()
    pending = [e for e in queue.get('emails', []) if e.get('status') == 'pending']
    return jsonify({
        'total': len(queue.get('emails', [])),
        'pending': len(pending),
        'emails': pending
    })

@app.route('/schedule/cancel/<email_id>', methods=['POST'])
def cancel_scheduled(email_id):
    """Cancel a scheduled email"""
    queue = load_scheduled_queue()
    
    for email_entry in queue.get('emails', []):
        if email_entry.get('id') == email_id and email_entry.get('status') == 'pending':
            email_entry['status'] = 'cancelled'
            save_scheduled_queue(queue)
            return jsonify({'status': 'cancelled', 'id': email_id})
    
    return jsonify({'error': 'Scheduled email not found or already sent'}), 404

@app.route('/check', methods=['POST'])
def trigger_check():
    """Trigger manual email check"""
    threading.Thread(target=check_inbox).start()
    return jsonify({'status': 'checking'})

@app.route('/check-scheduled', methods=['POST'])
def trigger_scheduled_check():
    """Trigger manual check of scheduled emails"""
    threading.Thread(target=check_and_send_scheduled).start()
    return jsonify({'status': 'checking'})

@app.route('/stats')
def stats():
    """Get processing stats"""
    inbox = load_inbox()
    emails = inbox.get('emails', [])
    unread = len([e for e in emails if not e.get('read', False)])
    
    queue = load_scheduled_queue()
    pending = len([e for e in queue.get('emails', []) if e.get('status') == 'pending'])
    
    return jsonify({
        'total': len(emails),
        'unread': unread,
        'domains': ALLOWED_DOMAINS,
        'scheduled_pending': pending,
        'scheduled_total': len(queue.get('emails', []))
    })

@app.route('/mark-read/<msg_id>', methods=['POST'])
def mark_read(msg_id):
    """Mark email as read"""
    inbox = load_inbox()
    for email_data in inbox.get('emails', []):
        if email_data['id'] == msg_id or email_data['msg_num'] == msg_id:
            email_data['read'] = True
            save_inbox(inbox)
            return jsonify({'status': 'marked', 'id': msg_id})
    return jsonify({'error': 'Email not found'}), 404

# ========== MAIN ==========

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_requested = True

def cleanup():
    """Cleanup on exit"""
    logger.info("Ravenclaw shutting down...")

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(cleanup)

def run_scheduler():
    """Background scheduler with shutdown support"""
    while not shutdown_requested:
        try:
            check_inbox()
            check_and_send_scheduled()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        
        if not shutdown_requested:
            time.sleep(BRIDGE['poll_interval'] * 60)

def run_scheduled_checker():
    """Background checker for scheduled emails (more frequent)"""
    while not shutdown_requested:
        try:
            check_and_send_scheduled()
        except Exception as e:
            logger.error(f"Scheduled checker error: {e}")
        
        if not shutdown_requested:
            time.sleep(SCHEDULED['check_interval'])

if __name__ == '__main__':
    print("=" * 50)
    print("RAVENCLAW EMAIL BRIDGE")
    print("=" * 50)
    print(f"Account: {EMAIL['username'][:5]}***")
    print(f"Domains: {', '.join(ALLOWED_DOMAINS)}")
    print(f"Check every: {BRIDGE['poll_interval']} minutes")
    print(f"Inbox file: {INBOX_FILE}")
    print(f"Max emails: {MAX_EMAILS}")
    print(f"Scheduled emails: {SCHEDULED['queue_file']}")
    print("=" * 50)
    
    # Start Flask in background
    def run_flask():
        app.run(host=BRIDGE['host'], port=BRIDGE['port'], debug=False, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Start scheduled email checker in background
    scheduled_thread = threading.Thread(target=run_scheduled_checker, daemon=True)
    scheduled_thread.start()
    
    # Main scheduler for inbox
    run_scheduler()
    logger.info("Ravenclaw stopped gracefully")
