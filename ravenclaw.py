# ravenclaw.py
"""
Ravenclaw - Secure Email Bridge for Discord
============================================
Features:
- POP3 email fetching with domain filtering
- Discord webhook integration
- SMTP email sending
- Scheduled checks every 30 minutes
- Secure credential management via .env
- Auto-reply capabilities
- Conversation threading
- Inbox storage in JSON file
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
    'host': get_env('EMAIL_HOST', False, 'mail.sapphire.co'),
    'pop_port': int(get_env('EMAIL_POP_PORT', False, '995')),
    'smtp_port': int(get_env('EMAIL_SMTP_PORT', False, '587')),
    'username': get_env('EMAIL_USERNAME', True),
    'password': get_env('EMAIL_PASSWORD', True)
}

# Domain filter
DOMAIN_FILTER = get_env('DOMAIN_FILTER', False, 'sapphire.co')
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

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [RAVENCLAW] %(message)s',
    handlers=[
        logging.FileHandler('ravenclaw.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

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
    """Save inbox to JSON file"""
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

def send_smtp(to, subject, body, in_reply_to=None):
    """Send email via SMTP"""
    msg = MIMEMultipart()
    msg['Subject'] = f"Re: {subject}"
    msg['From'] = f"Enoth <{EMAIL['username']}>"
    msg['To'] = to
    msg['In-Reply-To'] = in_reply_to if in_reply_to else ""
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    try:
        with smtplib.SMTP(EMAIL['host'], EMAIL['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL['username'], EMAIL['password'])
            server.send_message(msg)
        logger.info(f"Sent: {to}")
        return True
    except Exception as e:
        logger.error(f"SMTP error: {e}")
        return False

# ========== EMAIL PROCESSING ==========

def check_inbox():
    """Main email check function - reads emails and saves to JSON"""
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
        
        # Save updated inbox
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

@app.route('/check', methods=['POST'])
def trigger_check():
    """Trigger manual email check"""
    threading.Thread(target=check_inbox).start()
    return jsonify({'status': 'checking'})

@app.route('/stats')
def stats():
    """Get processing stats"""
    inbox = load_inbox()
    emails = inbox.get('emails', [])
    unread = len([e for e in emails if not e.get('read', False)])
    return jsonify({
        'total': len(emails),
        'unread': unread,
        'domains': ALLOWED_DOMAINS
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

def run_scheduler():
    """Background scheduler"""
    while True:
        check_inbox()
        time.sleep(BRIDGE['poll_interval'] * 60)

if __name__ == '__main__':
    print("=" * 50)
    print("RAVENCLAW EMAIL BRIDGE")
    print("=" * 50)
    print(f"Account: {EMAIL['username'][:5]}***")
    print(f"Domains: {', '.join(ALLOWED_DOMAINS)}")
    print(f"Check every: {BRIDGE['poll_interval']} minutes")
    print(f"Inbox file: {INBOX_FILE}")
    print("=" * 50)
    
    # Start Flask in background
    def run_flask():
        app.run(host=BRIDGE['host'], port=BRIDGE['port'], debug=False, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Main scheduler
    run_scheduler()
