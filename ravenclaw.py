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
import hmac
import uuid
import hashlib
import base64
import binascii
import mimetypes
import glob as globlib
import shutil
from email.header import decode_header, make_header
from email.mime.base import MIMEBase
from email.message import EmailMessage
from email import policy as email_policy
from email import encoders
from datetime import datetime, timezone
from flask import Flask, request, jsonify, g, send_file, Response
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

def set_env_value(key, value):
    """
    Update one key in .env so a setting changed at runtime survives a restart.

    Rewrites the file in place, preserving comments, blank lines and ordering,
    and appends the key if it was not already present. The write goes through a
    temp file and os.replace so an interrupted save can never leave a half
    written .env - that file holds the mail credentials.
    """
    line = f"{key}={value}"
    try:
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
    except OSError:
        lines = []

    replaced = False
    for i, existing in enumerate(lines):
        stripped = existing.strip()
        if stripped.startswith('#') or '=' not in stripped:
            continue
        if stripped.split('=', 1)[0].strip() == key:
            lines[i] = line
            replaced = True
            break

    if not replaced:
        if lines and lines[-1].strip():
            lines.append('')
        lines.append(line)

    tmp = ENV_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    os.replace(tmp, ENV_FILE)

    # Keep the live process consistent with what was just persisted.
    os.environ[key] = str(value)

# Email settings
EMAIL = {
    'host': get_env('EMAIL_HOST', False, 'mail.example.com'),
    'pop_port': int(get_env('EMAIL_POP_PORT', False, '995')),
    'smtp_port': int(get_env('EMAIL_SMTP_PORT', False, '587')),
    'username': get_env('EMAIL_USERNAME', True),
    'password': get_env('EMAIL_PASSWORD', True),
    'sender_name': get_env('SENDER_NAME', False, 'Your Name')
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
# Default to loopback: these routes can read the whole inbox and send mail as
# the configured account, so they must not be network-reachable by default.
BRIDGE = {
    'host': get_env('BRIDGE_HOST', False, '127.0.0.1'),
    'port': int(get_env('BRIDGE_PORT', False, '5002')),
    'poll_interval': int(get_env('BRIDGE_POLL_INTERVAL', False, '30')),
    'api_key': get_env('RAVENCLAW_API_KEY', False, ''),
    'api_keys': get_env('RAVENCLAW_API_KEYS', False, '')
}

def build_api_keys():
    """
    Map each API key to the actor name that owns it.

    RAVENCLAW_API_KEYS holds comma-separated 'actor:key' pairs, so every
    client has its own authenticated identity and sends can be attributed to
    a caller rather than to a single shared secret. The older single-key
    RAVENCLAW_API_KEY still works and is attributed to 'default'.
    """
    keys = {}
    if BRIDGE['api_key']:
        keys[BRIDGE['api_key']] = 'default'

    for pair in BRIDGE['api_keys'].split(','):
        pair = pair.strip()
        if not pair or ':' not in pair:
            continue
        actor, key = pair.split(':', 1)
        actor, key = actor.strip(), key.strip()
        if actor and key:
            keys[key] = actor

    return keys

API_KEYS = build_api_keys()

# Auto-reply settings
AUTO_REPLY = {
    'enabled': get_env('AUTO_REPLY_ENABLED', False, 'false').lower() == 'true',
    'template': get_env('AUTO_REPLY_TEMPLATE', False,
        "Thank you for your email. I've received your message and will respond shortly.")
}

# Scheduled email settings
SCHEDULED = {
    'queue_file': 'ravenclaw_scheduled.json',
    'sent_file': 'ravenclaw_sent.json',  # Track sent emails across restarts
    'max_attempts': 3,
    'check_interval': 60  # seconds
}

# Outbox: the record of what was sent, when, and by whom
OUTBOX_FILE = 'ravenclaw_outbox.json'
MAX_OUTBOX = 1000

# Seconds during which an identical message counts as an accidental repeat.
# Catches retries and double-clicks from callers that send no Idempotency-Key.
# Set to 0 to rely on idempotency keys alone.
DEDUPE_WINDOW = int(get_env('SEND_DEDUPE_WINDOW', False, '300'))

# Drafts: composed but not yet sent
DRAFTS_FILE = 'ravenclaw_drafts.json'

# Attachments
# ATTACHMENT_DIR is the ONLY folder a caller may reference by name. Anything
# outside it is unreachable, so an authenticated caller cannot name an
# arbitrary path and have the bridge mail out a file it happens to be able
# to read.
ATTACHMENT_DIR = get_env('ATTACHMENT_DIR', False, 'attachments')

# Content-addressed blob store backing drafts and the scheduled queue. Keeping
# bytes out of those JSON files stops a single PDF from bloating them, and
# identical files attached repeatedly cost one copy.
ATTACHMENT_STORE = get_env('ATTACHMENT_STORE', False, 'ravenclaw_attachments')

MAX_ATTACHMENT_BYTES = int(get_env('MAX_ATTACHMENT_BYTES', False, str(10 * 1024 * 1024)))
MAX_TOTAL_ATTACHMENT_BYTES = int(get_env('MAX_TOTAL_ATTACHMENT_BYTES', False, str(25 * 1024 * 1024)))

# The RFC822 bytes of received mail, exactly as the server handed them over,
# so an email can later be given back as a real .eml instead of a rebuild.
# Content-addressed like ATTACHMENT_STORE but a separate tree: gc_attachments()
# sweeps every blob no draft or queued email refers to, and these are
# referenced by the inbox instead.
RAW_EML_DIR = get_env('RAW_EML_DIR', False, 'ravenclaw_raw')

# Inbound attachments: files that arrive ON email, written to disk under a
# per-sender folder. Deliberately a separate tree from ATTACHMENT_STORE -
# gc_attachments() deletes every blob no draft or queued email refers to, so
# received files kept there would be swept away on the next sweep.
#
# Held in a dict rather than module-level constants because /config/attachments
# can change the location while the bridge is running; rebinding a bare name
# would leave stale copies inside any function that had already captured it.
INBOUND = {
    'enabled':         get_env('SAVE_INBOUND_ATTACHMENTS', False, 'true').lower() == 'true',
    'dir':             get_env('INBOUND_ATTACHMENT_DIR', False, 'inbox_attachments'),
    'max_bytes':       int(get_env('MAX_INBOUND_ATTACHMENT_BYTES', False, str(10 * 1024 * 1024))),
    'max_total_bytes': int(get_env('MAX_INBOUND_TOTAL_BYTES', False, str(25 * 1024 * 1024))),
}

# Serializes the whole check-duplicate -> send -> record sequence so two
# concurrent callers cannot both decide the same message is not a duplicate.
SEND_LOCK = threading.RLock()

# Guards read-modify-write on the drafts file.
DRAFT_LOCK = threading.RLock()

# Guards INBOUND and the .env rewrite behind it, so a config change cannot
# land halfway through an email whose files are still being written.
INBOUND_LOCK = threading.RLock()

# Only one scheduled-queue sweep may run at a time: the bridge starts a
# background checker and also exposes /check-scheduled, so sweeps can overlap.
SCHEDULED_LOCK = threading.RLock()

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

# Routes reachable without an API key. /health is left open so external
# monitoring can probe liveness; it exposes no email content.
PUBLIC_ROUTES = {'health'}

@app.before_request
def require_api_key():
    """
    Reject any request without a valid API key.

    Every other route can read the inbox or send mail as the configured
    account, so without this the bridge is an unauthenticated mail relay for
    anyone who can reach the port.
    """
    if request.endpoint in PUBLIC_ROUTES:
        return None

    if not API_KEYS:
        return jsonify({
            'error': 'No API key configured. Set RAVENCLAW_API_KEY or '
                     'RAVENCLAW_API_KEYS in .env to use the API.'
        }), 503

    # Compare as bytes: compare_digest rejects non-ASCII str outright.
    # Every key is checked without an early exit, so the number of
    # comparisons does not depend on which key matched.
    provided = request.headers.get('X-API-Key', '').encode('utf-8')
    actor = None
    for key, name in API_KEYS.items():
        if hmac.compare_digest(provided, key.encode('utf-8')):
            actor = name

    # A valid key always decides the identity, including on loopback. The
    # exemption below is a fallback for callers that cannot send a header -
    # it must not overwrite an identity the caller did supply, or every local
    # send would be attributed to 'localhost' instead of its real owner.
    if actor is None:
        # Local process-to-process callers (e.g. the SOA/BPEL composite on this
        # same machine) are trusted without a key, but only while the bridge
        # itself is bound to loopback only - if BRIDGE_HOST is ever widened to
        # a real interface, this exemption stops applying automatically.
        if BRIDGE['host'] in ('127.0.0.1', 'localhost') and request.remote_addr in ('127.0.0.1', '::1'):
            g.actor = 'localhost'
            return None

        logger.warning(f"Unauthorized {request.method} {request.path} from {request.remote_addr}")
        return jsonify({'error': 'Unauthorized'}), 401

    # Who this request is from - attached to anything it sends.
    g.actor = actor
    return None

# ========== FILE PATHS ==========

INBOX_FILE = 'ravenclaw_inbox.json'
PROCESSED_FILE = 'ravenclaw_processed.txt'

# ========== HELPERS ==========

def get_domain(email_addr):
    """
    Extract the domain from an address.

    Takes the part after the LAST '@': the domain is what follows the final
    separator, so 'user@allowed.com@evil.com' resolves to evil.com rather
    than appearing to be allowed.
    """
    if not email_addr:
        return None
    # Strip any display name / angle brackets first.
    addr = email.utils.parseaddr(email_addr)[1] or email_addr
    if '@' not in addr:
        return None
    domain = addr.rsplit('@', 1)[1].strip().strip('>').lower()
    return domain or None

def is_allowed(email_addr):
    """
    Check an address against the domain allowlist.

    Matching is exact, so a lookalike such as 'example.com.evil.com' or a
    subdomain such as 'mail.example.com' is not accepted. Add subdomains to
    DOMAIN_FILTER explicitly if you need them.
    """
    domain = get_domain(email_addr)
    if not domain:
        return False
    return any(domain == d.strip().lower() for d in ALLOWED_DOMAINS if d.strip())

def as_list(value):
    """Normalize a recipient field (None / str / list) to a list of addresses"""
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)

def check_recipients(to, cc=None, bcc=None):
    """
    Validate every recipient against the domain allowlist.

    The allowlist is only meaningful if it covers To, CC and BCC alike -
    otherwise a caller can pass an allowed 'to' and smuggle mail to any
    domain via 'bcc', turning the bridge into an open relay for the account.

    Returns (True, []) if all recipients are allowed, else (False, [rejected]).
    """
    recipients = as_list(to) + as_list(cc) + as_list(bcc)
    rejected = [r for r in recipients if not is_allowed(r)]
    return (not rejected), rejected

def utc_now():
    """Timezone-aware current time. Outbox timestamps are always UTC."""
    return datetime.now(timezone.utc)

def parse_ts(value):
    """Parse an ISO-8601 timestamp, treating a naive value as UTC."""
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

# ========== DRAFTS ==========

def load_drafts():
    """Load composed-but-unsent messages"""
    try:
        with open(DRAFTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'version': '1.0', 'drafts': []}
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Drafts file unreadable ({e}); leaving it in place")
        return {'version': '1.0', 'drafts': []}

def save_drafts(store):
    """Persist drafts atomically"""
    tmp = DRAFTS_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(store, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DRAFTS_FILE)

def find_draft(store, draft_id):
    for d in store.get('drafts', []):
        if d.get('id') == draft_id:
            return d
    return None

# ========== ATTACHMENTS ==========

class AttachmentError(ValueError):
    """Caller-facing problem with an attachment; message is safe to return."""

def _guess_type(filename):
    ctype, _ = mimetypes.guess_type(filename or '')
    return ctype or 'application/octet-stream'

def _safe_name(filename):
    """
    Reduce a caller-supplied name to a bare filename.

    Strips any directory component so a name like '../../.env' or
    'C:\\secrets\\x' cannot escape, and so the name written into the
    Content-Disposition header is never a path.
    """
    if not filename:
        raise AttachmentError('Attachment needs a filename')
    name = os.path.basename(filename.replace('\\', '/').strip())
    if not name or name in ('.', '..'):
        raise AttachmentError(f'Invalid attachment filename: {filename!r}')
    return name

def read_from_attachment_dir(name):
    """
    Read a file the caller named, from inside ATTACHMENT_DIR only.

    The realpath check is the actual containment guarantee: it defeats '..'
    segments and symlinks that would otherwise point outside the folder.
    """
    base = os.path.realpath(ATTACHMENT_DIR)
    if os.path.isabs(name) or name.replace('\\', '/').startswith('/'):
        raise AttachmentError(
            f'Absolute paths are not allowed; put the file in {ATTACHMENT_DIR} and pass its name'
        )

    candidate = os.path.realpath(os.path.join(base, name))
    if candidate != base and not candidate.startswith(base + os.sep):
        raise AttachmentError(f'Attachment must be inside {ATTACHMENT_DIR}: {name!r}')
    if not os.path.isfile(candidate):
        raise AttachmentError(f'Attachment not found in {ATTACHMENT_DIR}: {name!r}')

    with open(candidate, 'rb') as f:
        return f.read()

def normalize_attachments(raw):
    """
    Turn caller input into [(metadata, bytes)] pairs.

    Accepts either form per item:
      {"filename": "a.pdf", "content": "<base64>"}   - inline
      {"file": "a.pdf"}                              - named in ATTACHMENT_DIR

    Raises AttachmentError with a caller-safe message on anything invalid.
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise AttachmentError('attachments must be a list')

    out = []
    total = 0

    for item in raw:
        if not isinstance(item, dict):
            raise AttachmentError('Each attachment must be an object')

        if item.get('content') is not None:
            filename = _safe_name(item.get('filename'))
            try:
                data = base64.b64decode(item['content'], validate=True)
            except (binascii.Error, ValueError, TypeError):
                raise AttachmentError(f'Attachment {filename!r} content is not valid base64')
        elif item.get('file'):
            filename = _safe_name(item['file'])
            data = read_from_attachment_dir(item['file'])
        elif item.get('sha256'):
            # Already-stored attachment, e.g. carried from a draft.
            meta, data = load_stored_attachment(item)
            out.append((meta, data))
            total += meta['size']
            continue
        else:
            raise AttachmentError("Attachment needs either 'content' (base64) or 'file'")

        size = len(data)
        if size == 0:
            raise AttachmentError(f'Attachment {filename!r} is empty')
        if size > MAX_ATTACHMENT_BYTES:
            raise AttachmentError(
                f'Attachment {filename!r} is {size} bytes, over the '
                f'{MAX_ATTACHMENT_BYTES} byte per-file limit'
            )

        total += size
        if total > MAX_TOTAL_ATTACHMENT_BYTES:
            raise AttachmentError(
                f'Attachments total {total} bytes, over the '
                f'{MAX_TOTAL_ATTACHMENT_BYTES} byte per-message limit'
            )

        out.append(({
            'filename': filename,
            'content_type': item.get('content_type') or _guess_type(filename),
            'size': size,
            'sha256': hashlib.sha256(data).hexdigest()
        }, data))

    return out

def store_attachments(pairs):
    """
    Persist attachment bytes and return metadata only.

    Content-addressed: the filename on disk is the digest, so the same file
    referenced by many drafts or queued emails is stored once.
    """
    os.makedirs(ATTACHMENT_STORE, exist_ok=True)
    metas = []
    for meta, data in pairs:
        path = os.path.join(ATTACHMENT_STORE, meta['sha256'] + '.bin')
        if not os.path.exists(path):
            tmp = path + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(data)
            os.replace(tmp, path)
        metas.append(dict(meta))
    return metas

def load_stored_attachment(meta):
    """Rehydrate one stored attachment from its metadata."""
    digest = meta.get('sha256')
    path = os.path.join(ATTACHMENT_STORE, f'{digest}.bin')
    if not digest or not os.path.isfile(path):
        raise AttachmentError(
            f"Stored attachment {meta.get('filename')!r} is missing from {ATTACHMENT_STORE}"
        )
    with open(path, 'rb') as f:
        data = f.read()
    resolved = dict(meta)
    resolved.setdefault('filename', digest)
    resolved.setdefault('content_type', _guess_type(resolved['filename']))
    resolved['size'] = len(data)
    return resolved, data

def load_stored_attachments(metas):
    """Rehydrate a list of stored attachments into [(meta, bytes)]."""
    return [load_stored_attachment(m) for m in (metas or [])]

def referenced_digests():
    """Every attachment digest still referenced by a draft or a queued email."""
    refs = set()
    for d in load_drafts().get('drafts', []):
        for a in d.get('attachments', []):
            if a.get('sha256'):
                refs.add(a['sha256'])
    for e in load_scheduled_queue().get('emails', []):
        for a in e.get('attachments', []):
            if a.get('sha256'):
                refs.add(a['sha256'])
    return refs

def gc_attachments():
    """Delete stored blobs no draft or queued email refers to any more."""
    if not os.path.isdir(ATTACHMENT_STORE):
        return 0
    keep = referenced_digests()
    removed = 0
    for path in globlib.glob(os.path.join(ATTACHMENT_STORE, '*.bin')):
        if os.path.splitext(os.path.basename(path))[0] not in keep:
            try:
                os.remove(path)
                removed += 1
            except OSError as e:
                logger.warning(f"Could not remove orphaned attachment {path}: {e}")
    if removed:
        logger.info(f"Removed {removed} orphaned attachment blob(s)")
    return removed

# ========== RAW MESSAGE STORE (.eml of received mail) ==========

def save_raw_eml(raw):
    """
    Keep the RFC822 bytes of one received message, returning metadata only.

    Content-addressed, so the same message arriving twice costs one copy.
    Never raises: a full or unwritable disk must cost us the .eml, not the
    email itself, so failures are logged and reported as a missing record.
    """
    if not raw:
        return None

    digest = hashlib.sha256(raw).hexdigest()
    path = os.path.join(RAW_EML_DIR, f'{digest}.eml')

    try:
        os.makedirs(RAW_EML_DIR, exist_ok=True)
        if not os.path.exists(path):
            # Written through a temporary name: a half-flushed blob under its
            # digest would be a file whose name promises bytes it does not have.
            tmp = path + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(raw)
            os.replace(tmp, path)
    except OSError as e:
        logger.error(f"Could not store raw message {digest[:12]}: {e}")
        return None

    # The base directory is recorded alongside the digest for the same reason
    # inbound attachments record theirs: the folder can be moved later, and
    # these records must still point at where their bytes actually are.
    return {
        'sha256': digest,
        'dir': RAW_EML_DIR,
        'size': len(raw),
        'saved_at': utc_now().isoformat()
    }

def resolve_raw_path(meta):
    """
    Absolute path of one stored raw message, or None if it is gone.

    Safe to drive straight from a request: the filename is a 64-character hex
    digest we generated, so unlike resolve_inbound_path() - whose name comes
    from the sender - there is nothing here that could carry a path separator
    or a '..' segment. Validating the digest is what enforces that.
    """
    digest = (meta or {}).get('sha256')
    if not digest or not re.fullmatch(r'[0-9a-f]{64}', digest):
        return None

    base = meta.get('dir') or RAW_EML_DIR
    path = os.path.realpath(os.path.join(base, f'{digest}.eml'))
    return path if os.path.isfile(path) else None

def gc_raw_eml(inbox=None):
    """
    Delete stored .eml blobs no email in the inbox refers to any more.

    Callers that have just written the inbox pass it in: re-reading the file
    would cost a second parse of the whole thing, and reading it before the
    write lands would keep exactly the records the trim just dropped.
    """
    if not os.path.isdir(RAW_EML_DIR):
        return 0

    keep = set()
    for email_data in (inbox if inbox is not None else load_inbox()).get('emails', []):
        digest = (email_data.get('raw') or {}).get('sha256')
        if digest:
            keep.add(digest)

    removed = 0
    for path in globlib.glob(os.path.join(RAW_EML_DIR, '*.eml')):
        if os.path.splitext(os.path.basename(path))[0] not in keep:
            try:
                os.remove(path)
                removed += 1
            except OSError as e:
                logger.warning(f"Could not remove orphaned raw message {path}: {e}")
    if removed:
        logger.info(f"Removed {removed} orphaned raw message(s)")
    return removed

def reconstruct_eml(email_data):
    """
    Build an RFC822 message out of what was stored about one email.

    The fallback for mail received before raw messages were kept. Only the
    plain-text body, the decoded attachments and a handful of headers were
    ever saved, so any HTML alternative, the original header set and the exact
    encodings are gone. What comes back is therefore a faithful record of what
    we hold, not of what was sent - and it says so in a header, so nothing
    downstream can mistake it for the message as it arrived.
    """
    # policy.SMTP, not the default: this is written to a file that has to be
    # byte-correct RFC822, and only that policy terminates lines with CRLF.
    msg = EmailMessage(policy=email_policy.SMTP)

    msg['X-Ravenclaw-Reconstructed'] = 'yes'
    msg['X-Ravenclaw-Note'] = (
        'Rebuilt from the fields Ravenclaw stored. Date is when this bridge '
        'received the message, not the sender Date header. Any HTML part, the '
        'original To/Cc, the full header set and the exact MIME structure were '
        'never retained. This is not the message as sent.'
    )
    msg['From'] = email_data.get('sender') or 'unknown@invalid'
    # The account that received it. The original To/Cc were never stored, so
    # this is inferred, not recovered - which the note above says outright.
    msg['To'] = EMAIL['username']
    msg['Subject'] = email_data.get('subject') or ''

    if email_data.get('id'):
        msg['Message-ID'] = email_data['id']

    # The stored timestamp comes from datetime.now() - naive LOCAL time - so
    # the local zone is attached rather than left off. Without it the header
    # reads as '-0000' and every client would take those digits for UTC and
    # show the wrong moment. A record predating the field, or one hand-edited,
    # gets no Date at all rather than a wrong one.
    try:
        when = datetime.fromisoformat(email_data['timestamp'])
        msg['Date'] = when.astimezone() if when.tzinfo is None else when
    except (KeyError, TypeError, ValueError):
        pass

    msg.set_content(email_data.get('body') or '')

    for meta in email_data.get('attachments', []):
        path = resolve_inbound_path(meta) if not meta.get('skipped') else None
        if not path:
            # An attachment we cannot put back is called out in a header. A
            # rebuilt .eml that silently drops a file reads as an email that
            # never carried one.
            reason = meta.get('skipped') or 'file_missing'
            msg['X-Ravenclaw-Missing-Attachment'] = f"{meta.get('filename')} ({reason})"
            continue

        try:
            with open(path, 'rb') as f:
                data = f.read()
        except OSError as e:
            logger.warning(f"Could not read attachment for rebuilt .eml: {e}")
            msg['X-Ravenclaw-Missing-Attachment'] = f"{meta.get('filename')} (unreadable)"
            continue

        ctype = meta.get('content_type') or _guess_type(meta.get('filename'))
        maintype, _, subtype = ctype.partition('/')
        msg.add_attachment(data, maintype=maintype or 'application',
                           subtype=subtype or 'octet-stream',
                           filename=meta.get('filename'))

    return msg.as_bytes()

def eml_download_name(email_data):
    """
    A safe '<subject>.eml' filename for one stored email.

    The whitelist is deliberately narrow: the result goes straight into a
    Content-Disposition header, and a name that cannot contain a quote or a
    path separator needs no escaping there to be correct. Staying ASCII also
    keeps that header clear of RFC 2231 encoding.
    """
    def slug(text):
        return re.sub(r'[^A-Za-z0-9 ._+-]', '_', text or '')[:80].strip('. ')

    # Subjects are stored as the header arrived, so a non-ASCII one is still
    # '=?utf-8?B?...?=' here - decoded first, or the filename would be that
    # gibberish with its punctuation replaced.
    stem = slug(_decode_filename(email_data.get('subject')))

    # A subject with nothing ASCII in it - an Arabic or Urdu one, say - slugs
    # down to a row of underscores, which names the file after nothing. The
    # Message-ID is at least an identifier. sender_folder() bails on the same
    # test for the same reason.
    if not stem or set(stem) <= {'.', '_', ' ', '-'}:
        stem = slug((email_data.get('id') or '').strip('<>').split('@')[0])

    if not stem:
        return 'message.eml'
    if stem.split('.')[0].lower() in WINDOWS_RESERVED:
        stem = f'_{stem}'
    return f'{stem}.eml'

# ========== INBOUND ATTACHMENTS (files that arrive on email) ==========

# Names Windows refuses to use for a file or folder, whatever the extension.
WINDOWS_RESERVED = {
    'con', 'prn', 'aux', 'nul',
    *(f'com{i}' for i in range(1, 10)),
    *(f'lpt{i}' for i in range(1, 10)),
}

def inbound_config():
    """
    A snapshot of the inbound settings, taken under the lock.

    Callers work from the snapshot for the whole of one email, so a
    /config/attachments change mid-check cannot scatter one message's files
    across two folders.
    """
    with INBOUND_LOCK:
        return dict(INBOUND)

def sender_folder(sender):
    """
    Turn an address into one safe folder name: 'A.Khan@Corp.com' -> 'a.khan_at_corp.com'.

    Everything outside a conservative whitelist becomes '_', so a crafted From
    header cannot smuggle in a path separator, a drive letter or a '..' segment
    and have us write outside the inbound folder.
    """
    name = (sender or '').strip().lower().replace('@', '_at_')
    name = re.sub(r'[^a-z0-9._+-]', '_', name)
    name = name.strip('. ')
    if len(name) > 100:
        name = name[:100].rstrip('. ')
    if not name or set(name) <= {'.', '_'}:
        return 'unknown_sender'
    if name.split('.')[0] in WINDOWS_RESERVED:
        name = '_' + name
    return name

def _decode_filename(raw):
    """Decode an RFC 2047 encoded filename ('=?utf-8?B?...?=') to plain text."""
    if not raw:
        return None
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw

def _is_declared_attachment(part):
    """Whether a part says outright that it is an attachment.

    Narrower than _is_attachment_part on purpose: this is what body parsing
    skips, and some mailers put a filename on the inline part that IS the body.
    Only an explicit 'attachment' disposition is safe to rule out as body text.
    """
    return (part.get('Content-Disposition') or '').strip().lower().startswith('attachment')

def _is_attachment_part(part):
    """Whether one MIME part is a file rather than the message body."""
    if part.get_content_maintype() == 'multipart':
        return False

    disposition = (part.get('Content-Disposition') or '').strip().lower()
    if disposition.startswith('attachment'):
        return True
    if part.get_filename():
        return True
    # Inline images and the like: a body part carries no filename and is text,
    # so anything inline that is neither counts as a file worth keeping.
    if disposition.startswith('inline'):
        return part.get_content_type() not in ('text/plain', 'text/html')
    return False

def extract_inbound_attachments(msg, max_bytes, max_total_bytes):
    """
    Every attached file in a message, as a list of dicts with 'data' on each.

    A file over either cap is reported with a 'skipped' reason instead of its
    bytes: one oversized document must not cost us the rest of the email.
    """
    found = []
    total = 0
    index = 0

    for part in msg.walk():
        if not _is_attachment_part(part):
            continue

        index += 1
        raw_name = _decode_filename(part.get_filename())
        try:
            filename = _safe_name(raw_name)
        except AttachmentError:
            ext = mimetypes.guess_extension(part.get_content_type()) or '.bin'
            filename = f'attachment-{index}{ext}'

        try:
            data = part.get_payload(decode=True)
        except Exception as e:
            logger.warning(f"Could not decode attachment {filename!r}: {e}")
            continue
        if not data:
            continue

        size = len(data)
        if size > max_bytes:
            logger.info(f"Skipped attachment {filename!r}: {size} bytes over the {max_bytes} byte limit")
            found.append({'filename': filename, 'content_type': part.get_content_type(),
                          'size': size, 'skipped': 'too_large', 'data': None})
            continue
        if total + size > max_total_bytes:
            logger.info(f"Skipped attachment {filename!r}: message total would exceed {max_total_bytes} bytes")
            found.append({'filename': filename, 'content_type': part.get_content_type(),
                          'size': size, 'skipped': 'message_total_exceeded', 'data': None})
            continue

        total += size
        found.append({'filename': filename, 'content_type': part.get_content_type(),
                      'size': size, 'skipped': None, 'data': data})

    return found

def _file_digest(path):
    """sha256 of a file already on disk, or None if it cannot be read."""
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()

def _place_file(folder, filename, data, digest):
    """
    Write one file into folder, returning (name actually used, was it written).

    A name already taken by identical bytes is reused as-is - the same sender
    resending the same document should not litter the folder with copies. A
    clash between different bytes gets a ' (2)', ' (3)' suffix instead.
    """
    stem, ext = os.path.splitext(filename)
    candidate = filename
    n = 1

    while True:
        path = os.path.join(folder, candidate)
        if not os.path.exists(path):
            break
        if _file_digest(path) == digest:
            return candidate, False
        n += 1
        candidate = f'{stem} ({n}){ext}'

    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)
    return candidate, True

def _merge_sender_folder(src_dir, dst_dir):
    """
    Move every file from src_dir into dst_dir, then drop the empty src_dir.

    shutil.move onto a directory that already exists nests the source inside it
    instead of merging, which would leave the recorded 'path' of every file in
    there pointing one level too high. Merging file by file keeps the layout
    flat, and applies the same collision rule as a fresh save: identical bytes
    collapse into one copy, different bytes get a ' (2)' suffix.
    """
    os.makedirs(dst_dir, exist_ok=True)

    for name in os.listdir(src_dir):
        src = os.path.join(src_dir, name)
        if not os.path.isfile(src):
            continue

        dst = os.path.join(dst_dir, name)
        if os.path.exists(dst):
            if _file_digest(dst) == _file_digest(src):
                os.remove(src)
                continue
            stem, ext = os.path.splitext(name)
            n = 2
            while os.path.exists(os.path.join(dst_dir, f'{stem} ({n}){ext}')):
                n += 1
            dst = os.path.join(dst_dir, f'{stem} ({n}){ext}')

        shutil.move(src, dst)

    try:
        os.rmdir(src_dir)
    except OSError:
        # Something we did not put there is still inside; leave it alone.
        pass

def repoint_inbound_records(old_dir, new_dir):
    """
    Point stored attachments at their new home after their files were moved.

    Moving the folder without this leaves every existing record naming a folder
    the bytes are no longer in, so those attachments would 404 - which is the
    exact thing move_existing is meant to prevent. Returns how many records
    were updated.
    """
    old_root = os.path.realpath(old_dir)
    inbox = load_inbox()
    changed = 0

    for email_data in inbox.get('emails', []):
        for meta in email_data.get('attachments', []):
            if not meta.get('dir'):
                continue
            if os.path.realpath(meta['dir']) == old_root:
                meta['dir'] = new_dir
                changed += 1

    if changed:
        save_inbox(inbox)
    return changed

def save_inbound_attachments(msg, sender):
    """
    Write each attached file under <inbound dir>/<sender folder>/ and return
    metadata only.

    Never raises: an unwritable disk must cost us the files, not the email
    itself, so failures are logged and reported in the returned metadata.
    """
    cfg = inbound_config()
    if not cfg['enabled']:
        return []

    try:
        items = extract_inbound_attachments(msg, cfg['max_bytes'], cfg['max_total_bytes'])
    except Exception as e:
        logger.error(f"Could not read attachments from {sender}: {e}")
        return []

    if not items:
        return []

    base = cfg['dir']
    folder_name = sender_folder(sender)
    folder = os.path.join(base, folder_name)

    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as e:
        logger.error(f"Could not create attachment folder {folder}: {e}")
        return [{'filename': i['filename'], 'content_type': i['content_type'],
                 'size': i['size'], 'skipped': 'folder_unavailable'} for i in items]

    saved = []
    for item in items:
        if item['skipped']:
            saved.append({k: item[k] for k in ('filename', 'content_type', 'size', 'skipped')})
            continue

        digest = hashlib.sha256(item['data']).hexdigest()
        try:
            name, is_new = _place_file(folder, item['filename'], item['data'], digest)
        except OSError as e:
            logger.error(f"Could not save attachment {item['filename']!r} from {sender}: {e}")
            saved.append({'filename': item['filename'], 'content_type': item['content_type'],
                          'size': item['size'], 'skipped': 'write_failed'})
            continue

        # The base directory is recorded alongside the relative path: the
        # inbound folder can be moved later, and these records must still
        # point at where their bytes actually are.
        saved.append({
            'filename': name,
            'content_type': item['content_type'] or _guess_type(name),
            'size': item['size'],
            'sha256': digest,
            'dir': base,
            'path': f'{folder_name}/{name}',
            'saved_at': utc_now().isoformat()
        })
        if not is_new:
            logger.info(f"Attachment {name!r} from {sender} already stored, reused")

    return saved

def resolve_inbound_path(meta):
    """
    Absolute path of one stored inbound attachment, or None if it is gone.

    The realpath containment check is what makes this safe to drive from a
    request: a 'path' tampered with in the inbox JSON cannot walk out of the
    folder it was recorded against.
    """
    rel = meta.get('path')
    base = meta.get('dir') or inbound_config()['dir']
    if not rel:
        return None

    def within(root_dir):
        root = os.path.realpath(root_dir)
        candidate = os.path.realpath(os.path.join(root, rel))
        if candidate != root and not candidate.startswith(root + os.sep):
            logger.warning(f"Refusing attachment path outside {root}: {rel!r}")
            return None
        return candidate if os.path.isfile(candidate) else None

    found = within(base)
    if found:
        return found

    # The folder may have been moved by hand rather than through
    # /config/attachments, which leaves this record naming the old one. The
    # relative path is unchanged by such a move, so the file is worth looking
    # for under the folder in force now - still containment-checked.
    current = inbound_config()['dir']
    if os.path.realpath(current) != os.path.realpath(base):
        return within(current)
    return None

def inbound_counts(base=None):
    """(sender folders, files) currently held in the inbound folder."""
    base = base or inbound_config()['dir']
    if not os.path.isdir(base):
        return 0, 0
    senders = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
    files = sum(len(names) for _, _, names in os.walk(base))
    return len(senders), files

# ========== OUTBOX (sent-mail record) ==========

def load_outbox():
    """Load the record of sent mail"""
    try:
        with open(OUTBOX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'version': '1.0', 'sent': []}
    except (json.JSONDecodeError, OSError) as e:
        # Do not silently start empty: that would let every past send look
        # new again and defeat duplicate detection. Keep the file for
        # inspection and make the problem loud.
        logger.error(f"Outbox unreadable ({e}); duplicate detection is degraded until it is repaired")
        return {'version': '1.0', 'sent': []}

def save_outbox(outbox):
    """Persist the outbox atomically, newest first, capped at MAX_OUTBOX"""
    if len(outbox.get('sent', [])) > MAX_OUTBOX:
        outbox['sent'] = outbox['sent'][:MAX_OUTBOX]

    # Write-then-rename so a crash mid-write cannot truncate the record.
    tmp = OUTBOX_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(outbox, f, indent=2, ensure_ascii=False)
    os.replace(tmp, OUTBOX_FILE)

def content_hash(to, cc, bcc, subject, body, attachments=None):
    """Stable fingerprint of a message's recipients and content"""
    # Attachment digests are part of the identity: the same covering note with
    # a different document attached is a different message, not a duplicate.
    att = ','.join(sorted(a.get('sha256', '') for a in (attachments or [])))
    parts = [
        ','.join(sorted(as_list(to))),
        ','.join(sorted(as_list(cc))),
        ','.join(sorted(as_list(bcc))),
        subject or '',
        body or '',
        att
    ]
    # \x1f (unit separator) cannot appear in an address or subject, so
    # fields cannot run together and collide.
    return hashlib.sha256('\x1f'.join(parts).encode('utf-8')).hexdigest()

def find_duplicate(outbox, idempotency_key, chash):
    """
    Return a prior record if this message has already been sent.

    An idempotency key matches at any age. Without one, fall back to an
    identical message inside DEDUPE_WINDOW, which catches retries and
    double-clicks from callers that send no key.

    Only successful sends count, so a message that failed can be retried.
    """
    records = [r for r in outbox.get('sent', []) if r.get('status') == 'sent']

    if idempotency_key:
        for r in records:
            if r.get('idempotency_key') == idempotency_key:
                return r

    if DEDUPE_WINDOW > 0:
        cutoff = utc_now().timestamp() - DEDUPE_WINDOW
        for r in records:
            if r.get('content_hash') != chash:
                continue
            ts = parse_ts(r.get('sent_at'))
            if ts and ts.timestamp() >= cutoff:
                return r

    return None

def parse_body(msg):
    """Extract plain text from email"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            # An attached .txt is also text/plain; without this guard the
            # first attachment of that type would be mistaken for the body.
            if _is_declared_attachment(part):
                continue
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
    trimmed = False
    if 'emails' in inbox and len(inbox['emails']) > MAX_EMAILS:
        inbox['emails'] = inbox['emails'][:MAX_EMAILS]
        logger.info(f"Trimmed inbox to {MAX_EMAILS} emails")
        trimmed = True

    with open(INBOX_FILE, 'w', encoding='utf-8') as f:
        json.dump(inbox, f, indent=2, ensure_ascii=False)

    # Raw messages are bounded by the inbox that references them, so the trim
    # above is the only thing that ever orphans one. Swept after the write, and
    # only on a trim: every read of /inbox/<id> comes through here to flip the
    # read flag, and none of those drop a record.
    if trimmed:
        gc_raw_eml(inbox)

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

def send_smtp(to, subject, body, in_reply_to=None, cc=None, bcc=None, references=None,
              attachments=None):
    """
    Send one email via SMTP.

    Returns {'ok', 'message_id', 'subject', 'sent_at', 'error'}. The
    Message-ID is generated here rather than left to the mail server, so every
    send can be correlated with its outbox record and with any later reply.
    Date is set because RFC 5322 requires it and filters penalise its absence.
    """
    msg = MIMEMultipart()

    # "Re: " belongs only on an actual reply, identified by the threading
    # headers. Prefixing unconditionally made every brand-new email - including
    # scheduled mail - go out as "Re: <subject>".
    is_reply = bool(in_reply_to or references)
    if is_reply and subject and not subject.lower().startswith('re:'):
        subject = f"Re: {subject}"

    domain = EMAIL['username'].split('@')[-1] or 'ravenclaw'
    message_id = email.utils.make_msgid(domain=domain)

    msg['Message-ID'] = message_id
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Subject'] = subject
    msg['From'] = f"{EMAIL['sender_name']} <{EMAIL['username']}>"
    msg['To'] = to

    # Add CC recipients if provided
    if cc:
        if isinstance(cc, str):
            cc = [cc]
        msg['Cc'] = ', '.join(cc)
    
    # Add threading headers for replies
    if in_reply_to:
        msg['In-Reply-To'] = in_reply_to
    if references:
        msg['References'] = references
    elif in_reply_to:
        # If only in_reply_to is provided, use it as references too
        msg['References'] = in_reply_to
    
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    # Attachments follow the body inside the multipart/mixed container.
    for meta, data in (attachments or []):
        maintype, _, subtype = (meta.get('content_type') or 'application/octet-stream').partition('/')
        part = MIMEBase(maintype or 'application', subtype or 'octet-stream')
        part.set_payload(data)
        encoders.encode_base64(part)
        # Passing filename as a keyword lets Python RFC 2231-encode non-ASCII
        # names instead of emitting a header the recipient cannot decode.
        part.add_header('Content-Disposition', 'attachment', filename=meta['filename'])
        msg.attach(part)

    try:
        with smtplib.SMTP(EMAIL['host'], EMAIL['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL['username'], EMAIL['password'])
            
            # Build recipient list: To + CC + BCC
            recipients = [to]
            if cc:
                recipients.extend(cc)
            if bcc:
                if isinstance(bcc, str):
                    bcc = [bcc]
                recipients.extend(bcc)
            
            # Use sendmail for proper CC/BCC handling
            server.sendmail(EMAIL['username'], recipients, msg.as_string())
        logger.info(f"Sent SMTP: {to}" + (f", CC: {cc}" if cc else "") + (f", BCC: {bcc}" if bcc else "") + (f", Thread: {in_reply_to}" if in_reply_to else "") + (f", Attachments: {len(attachments)}" if attachments else ""))
        return {'ok': True, 'message_id': message_id, 'subject': subject,
                'sent_at': utc_now().isoformat(), 'error': None}
    except Exception as e:
        logger.error(f"SMTP error: {e}")
        return {'ok': False, 'message_id': message_id, 'subject': subject,
                'sent_at': None, 'error': str(e)}

def deliver(to, subject, body, sent_by, source, in_reply_to=None, cc=None, bcc=None,
            references=None, idempotency_key=None, on_behalf_of=None, attachments=None):
    """
    Send an email exactly once and record who sent it and when.

    This is the single entry point for outgoing mail. Holding SEND_LOCK for
    the whole check -> send -> record sequence is what makes "exactly once"
    true: without it, two concurrent callers can both read an outbox that
    does not yet contain the message and both send it.

    sent_by is the authenticated actor. on_behalf_of is an optional
    display-only label for the human behind an automated caller, e.g. the
    Discord user who typed !send.

    Returns (record, is_duplicate).
    """
    attachments = attachments or []
    att_meta = [m for m, _ in attachments]
    chash = content_hash(to, cc, bcc, subject, body, att_meta)

    with SEND_LOCK:
        outbox = load_outbox()

        existing = find_duplicate(outbox, idempotency_key, chash)
        if existing:
            logger.info(
                f"Duplicate suppressed: {sent_by} re-sent a message already "
                f"delivered at {existing.get('sent_at')} (record {existing.get('id')})"
            )
            return existing, True

        result = send_smtp(to, subject, body, in_reply_to, cc, bcc, references, attachments)

        record = {
            'id': uuid.uuid4().hex,
            'message_id': result['message_id'],
            'to': to,
            'cc': as_list(cc),
            'bcc': as_list(bcc),
            # The subject as actually sent, including any "Re: " prefix.
            'subject': result.get('subject', subject),
            'sent_by': sent_by,
            'on_behalf_of': on_behalf_of,
            'source': source,
            'sent_at': result['sent_at'] or utc_now().isoformat(),
            'status': 'sent' if result['ok'] else 'failed',
            'error': result['error'],
            'idempotency_key': idempotency_key,
            'content_hash': chash,
            'in_reply_to': in_reply_to,
            # Metadata only - the outbox records what was sent, not the bytes.
            'attachments': att_meta
        }

        outbox.setdefault('sent', []).insert(0, record)
        save_outbox(outbox)

    who = f"{sent_by} (for {on_behalf_of})" if on_behalf_of else sent_by
    logger.info(
        f"[{record['status']}] {record['id']} to={to} by={who} "
        f"via={source} msgid={record['message_id']}"
        + (f" attachments={len(att_meta)}" if att_meta else "")
    )
    return record, False

def check_and_send_scheduled():
    """
    Check scheduled emails and send those ready.

    Serialized: the background checker, the main scheduler loop and
    /check-scheduled can all trigger a sweep, and overlapping sweeps would
    otherwise race on the same queue entries.
    """
    if shutdown_requested:
        return

    with SCHEDULED_LOCK:
        _check_and_send_scheduled()

def _check_and_send_scheduled():
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
                # Re-check the allowlist at send time: entries can arrive by
                # hand-editing the queue file, bypassing the /schedule route.
                ok, rejected = check_recipients(
                    email_entry.get('to'),
                    email_entry.get('cc'),
                    email_entry.get('bcc')
                )
                if not ok:
                    email_entry['status'] = 'failed'
                    email_entry['error'] = f'Recipients not allowed: {rejected}'
                    logger.warning(f"Blocked scheduled email {email_id}, recipients not allowed: {rejected}")
                    updated = True
                    continue

                # Rehydrate attachment bytes from the blob store. A missing
                # blob fails this entry rather than silently sending a mail
                # whose attachment has vanished.
                try:
                    entry_attachments = load_stored_attachments(email_entry.get('attachments'))
                except AttachmentError as e:
                    email_entry['status'] = 'failed'
                    email_entry['error'] = str(e)
                    logger.error(f"Scheduled email {email_id} not sent: {e}")
                    updated = True
                    continue

                # The queue entry id is a natural idempotency key: it makes a
                # given scheduled email unsendable twice, even across
                # overlapping sweeps or a restart mid-send.
                record, duplicate = deliver(
                    email_entry['to'],
                    email_entry['subject'],
                    email_entry['body'],
                    sent_by=email_entry.get('scheduled_by', 'scheduler'),
                    source='scheduled-queue',
                    cc=email_entry.get('cc'),
                    bcc=email_entry.get('bcc'),
                    idempotency_key=f"scheduled:{email_id}",
                    attachments=entry_attachments
                )
                success = duplicate or record['status'] == 'sent'

                if success:
                    email_entry['status'] = 'sent'
                    email_entry['sent_at'] = record['sent_at']
                    email_entry['outbox_id'] = record['id']
                    email_entry['message_id'] = record['message_id']
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
    # allowed_mentions disables ALL pings: the body is attacker-controlled
    # (anyone on an allowed domain can mail us), so an email containing
    # @everyone must not ping the server.
    if DISCORD['use_webhook'] and DISCORD['webhook_url']:
        try:
            requests.post(DISCORD['webhook_url'], json={
                'content': content,
                'allowed_mentions': {'parse': []}
            }, timeout=10)
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
        
        # Message-ID is the only stable identity for a stored email: POP3
        # message numbers are per-session and renumber as the mailbox changes.
        known_ids = {e.get('id') for e in inbox.get('emails', [])}
        rejected_count = 0

        for line in msg_list:
            msg_num = line.decode().split()[0]

            if msg_num in processed_ids:
                continue

            try:
                # Pull headers only first. Mail from a domain we do not accept
                # should never have its body downloaded or written to disk.
                headers = None
                try:
                    _, hdr_lines, _ = mail.top(msg_num, 0)
                    headers = email.message_from_bytes(b'\r\n'.join(hdr_lines))
                except Exception:
                    pass  # server without TOP support; fall through to RETR

                if headers is not None:
                    peek_sender = email.utils.parseaddr(headers['From'])[1]
                    if not is_allowed(peek_sender):
                        logger.info(f"Rejected: {peek_sender} (domain not allowed)")
                        save_processed(msg_num)
                        rejected_count += 1
                        continue

                _, lines, _ = mail.retr(msg_num)
                # poplib has already un-stuffed leading '..' and stripped the
                # CRLF framing, so joining the lines back gives the message
                # exactly as it arrived. The final CRLF went with that framing;
                # putting it back restores the message rather than editing it,
                # and mail clients expect the file to end on one.
                raw = b'\r\n'.join(lines) + b'\r\n'
                msg = email.message_from_bytes(raw)

                sender = email.utils.parseaddr(msg['From'])[1]
                subject = msg['Subject']
                msg_id = msg.get('Message-ID', f'<{msg_num}@ravenclaw>')
                body = parse_body(msg)
                timestamp = datetime.now().isoformat()

                # Authoritative check on the full message: TOP may have been
                # unavailable above, so this is what actually gates storage.
                if not is_allowed(sender):
                    logger.info(f"Rejected: {sender} (domain not allowed)")
                    save_processed(msg_num)
                    rejected_count += 1
                    continue

                # Already stored under a different message number - happens
                # whenever the processed list is reset or the mailbox renumbers.
                if msg_id in known_ids:
                    save_processed(msg_num)
                    continue
                known_ids.add(msg_id)

                # Only now, with the sender accepted and the message known to
                # be new, is it right to put its files on disk: rejected mail
                # must leave nothing behind, and a message seen twice should
                # not be written twice.
                att_meta = save_inbound_attachments(msg, sender)

                # The message exactly as it arrived, so it can be handed back
                # later as a real .eml. Kept here rather than at retr() for the
                # same reason as the attachments above: rejected mail must
                # leave nothing behind, and a message seen twice writes once.
                raw_meta = save_raw_eml(raw)

                # Save to inbox JSON
                email_data = {
                    'id': msg_id,
                    'msg_num': msg_num,
                    'sender': sender,
                    'subject': subject,
                    'body': body,
                    'timestamp': timestamp,
                    'read': False,
                    'replied': False,
                    'attachments': att_meta,
                    'raw': raw_meta
                }
                
                inbox['emails'].insert(0, email_data)
                new_emails.append(email_data)
                
                logger.info(
                    f"Received: {sender} - {subject}"
                    + (f" ({len(att_meta)} attachment(s))" if att_meta else "")
                )
                
            except Exception as e:
                logger.error(f"Error processing msg {msg_num}: {e}")
        
        # Save updated inbox (with trim)
        if new_emails:
            save_inbox(inbox)
            
            # Forward to Discord
            for email_data in new_emails:
                discord_body = email_data['body']
                names = ', '.join(a['filename'] for a in email_data.get('attachments', [])
                                  if not a.get('skipped'))
                if names:
                    discord_body = f"{discord_body}\n\nAttachments: {names}"
                send_discord(email_data['sender'], email_data['subject'],
                           discord_body, email_data['id'])
                
                # Auto-reply with proper threading
                if AUTO_REPLY['enabled']:
                    auto_body = AUTO_REPLY['template']
                    # Keyed on the incoming Message-ID so a sender never
                    # receives two auto-replies for the same email, even if
                    # the message is seen twice.
                    deliver(
                        email_data['sender'],
                        email_data['subject'],
                        auto_body,
                        sent_by='ravenclaw',
                        source='auto-reply',
                        in_reply_to=email_data['id'],
                        references=email_data['id'],
                        idempotency_key=f"auto-reply:{email_data['id']}"
                    )
        
        mail.quit()
        
        # Mark all as processed (don't delete from server)
        for msg_num in msg_list:
            msg_num = msg_num.decode().split()[0]
            if msg_num not in processed_ids:
                save_processed(msg_num)
        
        logger.info(
            f"Check complete. New: {len(new_emails)}, Rejected: {rejected_count}, "
            f"Total in inbox: {len(inbox['emails'])}, Filter: {', '.join(ALLOWED_DOMAINS)}"
        )
        
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
    # Diagnostic: capture the raw body so we can see exactly what the caller
    # put on the wire. The Oracle JCA REST adapter used by SendEmailServiceBPEL
    # has historically serialised the JSON object as a JSON-encoded string,
    # which makes request.json return str instead of dict and crashes below.
    raw_body = request.get_data(as_text=True)
    data = request.json
    logger.debug(
        f"/send raw_len={len(raw_body)} parsed_type={type(data).__name__} "
        f"raw={raw_body!r}"
    )
    # Defensive: unwrap JSON-encoded string body if the caller wrapped it.
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return jsonify({'error': 'Body is a string, expected JSON object'}), 400
    if not isinstance(data, dict):
        return jsonify({'error': f'Body must be a JSON object, got {type(data).__name__}'}), 400
    required = ['to', 'subject', 'body']
    for r in required:
        if r not in data:
            return jsonify({'error': f'Missing: {r}'}), 400

    ok, rejected = check_recipients(data['to'], data.get('cc'), data.get('bcc'))
    if not ok:
        logger.warning(f"Rejected send, recipients not allowed: {rejected}")
        return jsonify({'error': 'Domain not allowed', 'rejected': rejected}), 403

    try:
        attachments = normalize_attachments(data.get('attachments'))
    except AttachmentError as e:
        return jsonify({'error': str(e)}), 400

    record, duplicate = deliver(
        data['to'],
        data['subject'],
        data['body'],
        sent_by=g.get('actor', 'unknown'),
        source='api',
        in_reply_to=data.get('in_reply_to'),
        cc=data.get('cc'),
        bcc=data.get('bcc'),
        references=data.get('references'),
        idempotency_key=request.headers.get('Idempotency-Key') or data.get('idempotency_key'),
        on_behalf_of=data.get('on_behalf_of'),
        attachments=attachments
    )

    body = {
        'status': 'duplicate' if duplicate else record['status'],
        'duplicate': duplicate,
        'id': record['id'],
        'message_id': record['message_id'],
        'sent_at': record['sent_at'],
        'sent_by': record['sent_by'],
        'on_behalf_of': record['on_behalf_of'],
        'attachments': record.get('attachments', [])
    }
    if record['status'] == 'failed':
        body['error'] = record['error']
        # 502: we accepted the request but the upstream mail server refused it.
        return jsonify(body), 502

    return jsonify(body), 200

# ========== SENT MAIL ROUTES ==========

@app.route('/sent')
def list_sent():
    """
    The record of outgoing mail, newest first.

    Filters: ?sent_by=alice  ?source=api  ?status=sent  ?since=<ISO-8601>
             ?limit=50
    """
    records = load_outbox().get('sent', [])

    for field in ('sent_by', 'source', 'status'):
        wanted = request.args.get(field)
        if wanted:
            records = [r for r in records if r.get(field) == wanted]

    since = request.args.get('since')
    if since:
        cutoff = parse_ts(since)
        if cutoff is None:
            return jsonify({'error': 'Invalid since. Use ISO-8601.'}), 400
        records = [r for r in records
                   if (parse_ts(r.get('sent_at')) or utc_now()) >= cutoff]

    limit = request.args.get('limit', type=int)
    if limit and limit > 0:
        records = records[:limit]

    return jsonify({'count': len(records), 'sent': records})

@app.route('/sent/<record_id>')
def get_sent(record_id):
    """Look up one sent email by outbox id or by Message-ID"""
    for r in load_outbox().get('sent', []):
        if r.get('id') == record_id or r.get('message_id') == record_id:
            return jsonify(r)
    return jsonify({'error': 'Sent record not found'}), 404

# ========== DRAFT ROUTES ==========

DRAFT_FIELDS = ('to', 'cc', 'bcc', 'subject', 'body', 'in_reply_to', 'references')

def _json_object():
    """
    Parse the request body as a JSON object.

    Mirrors the defensive handling in /send: some clients serialise the object
    as a JSON-encoded string. Returns (data, error_response).
    """
    data = request.get_json(silent=True)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None, (jsonify({'error': 'Body is a string, expected JSON object'}), 400)
    if data is None:
        return None, (jsonify({'error': 'Expected a JSON body'}), 400)
    if not isinstance(data, dict):
        return None, (jsonify({'error': f'Body must be a JSON object, got {type(data).__name__}'}), 400)
    return data, None

def _draft_view(draft):
    """Draft as returned to callers - metadata only, never attachment bytes."""
    return {k: v for k, v in draft.items()}

@app.route('/draft', methods=['POST'])
def create_draft():
    """
    Compose a draft without sending it.

    Only 'subject' and 'body' are needed up front; recipients can be filled in
    later with PATCH. Any recipient present is validated immediately so a
    draft cannot quietly accumulate addresses that could never be sent to.
    """
    data, err = _json_object()
    if err:
        return err

    if not check_recipients(data.get('to'), data.get('cc'), data.get('bcc'))[0]:
        rejected = check_recipients(data.get('to'), data.get('cc'), data.get('bcc'))[1]
        return jsonify({'error': 'Domain not allowed', 'rejected': rejected}), 403

    try:
        att_meta = store_attachments(normalize_attachments(data.get('attachments')))
    except AttachmentError as e:
        return jsonify({'error': str(e)}), 400

    now = utc_now().isoformat()
    draft = {
        'id': uuid.uuid4().hex,
        'to': data.get('to'),
        'cc': as_list(data.get('cc')),
        'bcc': as_list(data.get('bcc')),
        'subject': data.get('subject', ''),
        'body': data.get('body', ''),
        'in_reply_to': data.get('in_reply_to'),
        'references': data.get('references'),
        'attachments': att_meta,
        'created_by': g.get('actor', 'unknown'),
        'on_behalf_of': data.get('on_behalf_of'),
        'created_at': now,
        'updated_at': now,
        'status': 'draft'
    }

    with DRAFT_LOCK:
        store = load_drafts()
        store.setdefault('drafts', []).insert(0, draft)
        save_drafts(store)

    logger.info(f"Draft created: {draft['id']} by {draft['created_by']} "
                f"attachments={len(att_meta)}")
    return jsonify(_draft_view(draft)), 201

@app.route('/draft')
def list_drafts():
    """List drafts, newest first. Filter with ?created_by= or ?status="""
    drafts = load_drafts().get('drafts', [])
    for field in ('created_by', 'status'):
        wanted = request.args.get(field)
        if wanted:
            drafts = [d for d in drafts if d.get(field) == wanted]
    return jsonify({'count': len(drafts), 'drafts': [_draft_view(d) for d in drafts]})

@app.route('/draft/<draft_id>')
def get_draft(draft_id):
    """Read one draft"""
    draft = find_draft(load_drafts(), draft_id)
    if not draft:
        return jsonify({'error': 'Draft not found'}), 404
    return jsonify(_draft_view(draft))

@app.route('/draft/<draft_id>', methods=['PATCH', 'PUT'])
def update_draft(draft_id):
    """
    Update a draft in place.

    Supplied fields replace their previous value. 'attachments' replaces the
    whole list; 'add_attachments' appends instead, so a caller can attach one
    more file without resending the ones already there.
    """
    data, err = _json_object()
    if err:
        return err

    with DRAFT_LOCK:
        store = load_drafts()
        draft = find_draft(store, draft_id)
        if not draft:
            return jsonify({'error': 'Draft not found'}), 404
        if draft.get('status') != 'draft':
            return jsonify({'error': f"Draft already {draft.get('status')}"}), 409

        merged = dict(draft)
        for field in DRAFT_FIELDS:
            if field in data:
                merged[field] = as_list(data[field]) if field in ('cc', 'bcc') else data[field]

        if not check_recipients(merged.get('to'), merged.get('cc'), merged.get('bcc'))[0]:
            rejected = check_recipients(merged.get('to'), merged.get('cc'), merged.get('bcc'))[1]
            return jsonify({'error': 'Domain not allowed', 'rejected': rejected}), 403

        try:
            if 'attachments' in data:
                merged['attachments'] = store_attachments(normalize_attachments(data['attachments']))
            if data.get('add_attachments'):
                added = store_attachments(normalize_attachments(data['add_attachments']))
                merged['attachments'] = list(merged.get('attachments', [])) + added
            if data.get('remove_attachments'):
                drop = set(data['remove_attachments'])
                merged['attachments'] = [
                    a for a in merged.get('attachments', [])
                    if a.get('filename') not in drop and a.get('sha256') not in drop
                ]
        except AttachmentError as e:
            return jsonify({'error': str(e)}), 400

        merged['updated_at'] = utc_now().isoformat()
        store['drafts'] = [merged if d.get('id') == draft_id else d for d in store['drafts']]
        save_drafts(store)

    gc_attachments()
    logger.info(f"Draft updated: {draft_id} by {g.get('actor', 'unknown')}")
    return jsonify(_draft_view(merged))

@app.route('/draft/<draft_id>', methods=['DELETE'])
def delete_draft(draft_id):
    """Discard a draft"""
    with DRAFT_LOCK:
        store = load_drafts()
        if not find_draft(store, draft_id):
            return jsonify({'error': 'Draft not found'}), 404
        store['drafts'] = [d for d in store['drafts'] if d.get('id') != draft_id]
        save_drafts(store)

    gc_attachments()
    logger.info(f"Draft deleted: {draft_id} by {g.get('actor', 'unknown')}")
    return jsonify({'status': 'deleted', 'id': draft_id})

@app.route('/draft/<draft_id>/send', methods=['POST'])
def send_draft(draft_id):
    """Send a draft now, attachments included"""
    with DRAFT_LOCK:
        store = load_drafts()
        draft = find_draft(store, draft_id)
        if not draft:
            return jsonify({'error': 'Draft not found'}), 404
        if draft.get('status') != 'draft':
            return jsonify({'error': f"Draft already {draft.get('status')}"}), 409
        if not draft.get('to'):
            return jsonify({'error': "Draft has no 'to' recipient"}), 400

        ok, rejected = check_recipients(draft.get('to'), draft.get('cc'), draft.get('bcc'))
        if not ok:
            return jsonify({'error': 'Domain not allowed', 'rejected': rejected}), 403

        try:
            attachments = load_stored_attachments(draft.get('attachments'))
        except AttachmentError as e:
            return jsonify({'error': str(e)}), 400

        # Keyed on the draft id so a double-click cannot send it twice.
        record, duplicate = deliver(
            draft['to'],
            draft.get('subject', ''),
            draft.get('body', ''),
            sent_by=g.get('actor', 'unknown'),
            source='draft',
            in_reply_to=draft.get('in_reply_to'),
            cc=draft.get('cc'),
            bcc=draft.get('bcc'),
            references=draft.get('references'),
            idempotency_key=request.headers.get('Idempotency-Key') or f'draft:{draft_id}',
            on_behalf_of=draft.get('on_behalf_of'),
            attachments=attachments
        )

        if record['status'] == 'sent' or duplicate:
            draft['status'] = 'sent'
            draft['sent_at'] = record['sent_at']
            draft['outbox_id'] = record['id']
            draft['updated_at'] = utc_now().isoformat()
            store['drafts'] = [draft if d.get('id') == draft_id else d for d in store['drafts']]
            save_drafts(store)

    body = {
        'status': 'duplicate' if duplicate else record['status'],
        'duplicate': duplicate,
        'draft_id': draft_id,
        'id': record['id'],
        'message_id': record['message_id'],
        'sent_at': record['sent_at'],
        'sent_by': record['sent_by'],
        'attachments': record.get('attachments', [])
    }
    if record['status'] == 'failed' and not duplicate:
        body['error'] = record['error']
        return jsonify(body), 502
    return jsonify(body), 200

@app.route('/draft/<draft_id>/schedule', methods=['POST'])
def schedule_draft(draft_id):
    """Promote a draft into the scheduled queue. Body: {"target_time": ISO-8601}"""
    data, err = _json_object()
    if err:
        return err
    if 'target_time' not in data:
        return jsonify({'error': 'Missing: target_time'}), 400

    try:
        target = datetime.fromisoformat(data['target_time'])
        if target.timestamp() <= datetime.now().timestamp():
            return jsonify({'error': 'target_time must be in the future'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid target_time format. Use ISO-8601'}), 400

    with DRAFT_LOCK:
        store = load_drafts()
        draft = find_draft(store, draft_id)
        if not draft:
            return jsonify({'error': 'Draft not found'}), 404
        if draft.get('status') != 'draft':
            return jsonify({'error': f"Draft already {draft.get('status')}"}), 409
        if not draft.get('to'):
            return jsonify({'error': "Draft has no 'to' recipient"}), 400

        ok, rejected = check_recipients(draft.get('to'), draft.get('cc'), draft.get('bcc'))
        if not ok:
            return jsonify({'error': 'Domain not allowed', 'rejected': rejected}), 403

        with SCHEDULED_LOCK:
            queue = load_scheduled_queue()
            entry = {
                'id': f"sched_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}",
                'to': draft['to'],
                'cc': draft.get('cc'),
                'bcc': draft.get('bcc'),
                'subject': draft.get('subject', ''),
                'body': draft.get('body', ''),
                # Blobs are already in the store; the queue carries metadata.
                'attachments': draft.get('attachments', []),
                'target_time': data['target_time'],
                'created_at': datetime.now().isoformat(),
                'scheduled_by': g.get('actor', 'unknown'),
                'on_behalf_of': draft.get('on_behalf_of'),
                'from_draft': draft_id,
                'status': 'pending',
                'attempts': 0,
                'last_attempt': None,
                'error': None,
                'priority': data.get('priority', 'normal')
            }
            queue.setdefault('emails', []).append(entry)
            save_scheduled_queue(queue)

        draft['status'] = 'scheduled'
        draft['scheduled_id'] = entry['id']
        draft['updated_at'] = utc_now().isoformat()
        store['drafts'] = [draft if d.get('id') == draft_id else d for d in store['drafts']]
        save_drafts(store)

    logger.info(f"Draft {draft_id} scheduled as {entry['id']} for {data['target_time']}")
    return jsonify({
        'status': 'scheduled',
        'draft_id': draft_id,
        'id': entry['id'],
        'target_time': entry['target_time'],
        'scheduled_by': entry['scheduled_by'],
        'attachments': entry['attachments']
    })

# ========== SCHEDULED EMAIL ROUTES ==========

@app.route('/schedule', methods=['POST'])
def schedule_email():
    """
    Schedule an email to be sent later.
    Body:
    {
        "to": "recipient@domain.com",
        "cc": ["cc@domain.com"],        // Optional: CC recipients
        "bcc": ["bcc@domain.com"],     // Optional: BCC recipients (not in headers)
        "subject": "Email subject",
        "body": "Email body",
        "target_time": "2026-02-17T09:00:00"  // ISO-8601 timestamp
    }
    """
    # Same defensive parsing shape as /send - unwrap if the caller serialised
    # the JSON object as a JSON-encoded string.
    raw_body = request.get_data(as_text=True)
    data = request.json
    logger.debug(
        f"/schedule raw_len={len(raw_body)} parsed_type={type(data).__name__} "
        f"raw={raw_body!r}"
    )
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return jsonify({'error': 'Body is a string, expected JSON object'}), 400
    if not isinstance(data, dict):
        return jsonify({'error': f'Body must be a JSON object, got {type(data).__name__}'}), 400
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
    
    ok, rejected = check_recipients(data['to'], data.get('cc'), data.get('bcc'))
    if not ok:
        logger.warning(f"Rejected schedule, recipients not allowed: {rejected}")
        return jsonify({'error': 'Domain not allowed', 'rejected': rejected}), 403

    # Attachment bytes go to the blob store now; the queue keeps metadata only,
    # so a queued PDF does not bloat ravenclaw_scheduled.json.
    try:
        att_meta = store_attachments(normalize_attachments(data.get('attachments')))
    except AttachmentError as e:
        return jsonify({'error': str(e)}), 400

    # Load queue and add email
    queue = load_scheduled_queue()

    email_entry = {
        'id': f"sched_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(queue.get('emails', []))}",
        'to': data['to'],
        'cc': data.get('cc'),  # Optional CC recipients
        'bcc': data.get('bcc'),  # Optional BCC recipients
        'subject': data['subject'],
        'body': data['body'],
        'attachments': att_meta,
        'target_time': data['target_time'],
        'created_at': datetime.now().isoformat(),
        'scheduled_by': g.get('actor', 'unknown'),
        'on_behalf_of': data.get('on_behalf_of'),
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
        'target_time': data['target_time'],
        'scheduled_by': email_entry['scheduled_by']
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
            email_entry['attachments'] = []
            save_scheduled_queue(queue)
            # Its attachment blobs may now be unreferenced.
            gc_attachments()
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
    
    outbox = load_outbox().get('sent', [])
    by_actor = {}
    for r in outbox:
        if r.get('status') == 'sent':
            by_actor[r.get('sent_by', 'unknown')] = by_actor.get(r.get('sent_by', 'unknown'), 0) + 1

    return jsonify({
        'total': len(emails),
        'unread': unread,
        'domains': ALLOWED_DOMAINS,
        'scheduled_pending': pending,
        'scheduled_total': len(queue.get('emails', [])),
        'sent_total': len(outbox),
        'sent_ok': sum(1 for r in outbox if r.get('status') == 'sent'),
        'sent_failed': sum(1 for r in outbox if r.get('status') == 'failed'),
        'sent_by_actor': by_actor,
        'last_sent_at': outbox[0].get('sent_at') if outbox else None,
        'drafts_open': sum(1 for d in load_drafts().get('drafts', []) if d.get('status') == 'draft'),
        'drafts_total': len(load_drafts().get('drafts', [])),
        'attachments_stored': len(globlib.glob(os.path.join(ATTACHMENT_STORE, '*.bin'))),
        'inbound_attachments_dir': inbound_config()['dir'],
        'inbound_senders': inbound_counts()[0],
        'inbound_attachments_saved': inbound_counts()[1]
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

@app.route('/mark-all-read', methods=['POST'])
def mark_all_read():
    """Mark all emails as read"""
    inbox = load_inbox()
    count = 0
    for email_data in inbox.get('emails', []):
        email_data['read'] = True
        count += 1
    save_inbox(inbox)
    return jsonify({'status': 'marked_all', 'count': count})

@app.route('/config/attachments')
def get_attachment_config():
    """Where received attachments are being written, and whether that works."""
    cfg = inbound_config()
    resolved = os.path.realpath(cfg['dir'])
    senders, files = inbound_counts(cfg['dir'])

    # The folder is created on the first attachment, so before any mail has
    # arrived it does not exist yet. Reporting that as unwritable would read as
    # a fault; what the caller wants to know is whether saving will work, which
    # for a folder not there yet is a question about its parent.
    if os.path.isdir(resolved):
        writable = os.access(resolved, os.W_OK)
    else:
        parent = os.path.dirname(resolved) or '.'
        writable = os.path.isdir(parent) and os.access(parent, os.W_OK)

    return jsonify({
        'inbound_dir': cfg['dir'],
        'resolved': resolved,
        'exists': os.path.isdir(resolved),
        'writable': writable,
        'enabled': cfg['enabled'],
        'max_bytes': cfg['max_bytes'],
        'max_total_bytes': cfg['max_total_bytes'],
        'senders': senders,
        'files': files
    })

@app.route('/config/attachments', methods=['PUT', 'POST'])
def set_attachment_config():
    """
    Move where received attachments are stored, without a restart.

    The new folder is created and probe-written before anything is changed, so
    a bad path is rejected while the working one is still in force. The change
    is persisted to .env as well, so it survives a restart.

    Body: {"inbound_dir": "D:/MyMail/files", "enabled": true, "move_existing": false}
    """
    data = request.get_json(silent=True) or {}
    changed = {}

    if 'enabled' in data:
        if not isinstance(data['enabled'], bool):
            return jsonify({'error': "'enabled' must be true or false"}), 400
        changed['enabled'] = data['enabled']

    new_dir = data.get('inbound_dir')
    if new_dir is not None:
        if not isinstance(new_dir, str) or not new_dir.strip():
            return jsonify({'error': "'inbound_dir' must be a non-empty path"}), 400
        new_dir = new_dir.strip()

        if os.path.isfile(new_dir):
            return jsonify({'error': f'{new_dir} is a file, not a folder'}), 400

        try:
            os.makedirs(new_dir, exist_ok=True)
        except OSError as e:
            return jsonify({'error': f'Cannot create {new_dir}: {e}'}), 400

        # os.access can disagree with reality on Windows shares and ACLs, so
        # prove the folder is writable by actually writing to it.
        probe = os.path.join(new_dir, f'.ravenclaw-probe-{uuid.uuid4().hex}')
        try:
            with open(probe, 'wb') as f:
                f.write(b'ok')
            os.remove(probe)
        except OSError as e:
            return jsonify({'error': f'{new_dir} is not writable: {e}'}), 400

        changed['dir'] = new_dir

    if not changed:
        return jsonify({'error': "Nothing to change; send 'inbound_dir' and/or 'enabled'"}), 400

    with INBOUND_LOCK:
        previous_dir = INBOUND['dir']
        moved = 0

        if 'dir' in changed and data.get('move_existing'):
            # Opt-in: relocate what is already on disk so the old folder is not
            # left behind. Only sender folders move; anything else in there was
            # not put there by us.
            old_root = os.path.realpath(previous_dir)
            new_root = os.path.realpath(changed['dir'])
            if os.path.isdir(old_root) and old_root != new_root:
                for name in os.listdir(old_root):
                    src = os.path.join(old_root, name)
                    if not os.path.isdir(src):
                        continue
                    dst = os.path.join(new_root, name)
                    try:
                        if os.path.exists(dst):
                            _merge_sender_folder(src, dst)
                        else:
                            shutil.move(src, dst)
                        moved += 1
                    except (OSError, shutil.Error) as e:
                        logger.error(f"Could not move {src} to {dst}: {e}")

                if moved:
                    repointed = repoint_inbound_records(previous_dir, changed['dir'])
                    logger.info(f"Repointed {repointed} stored attachment(s) to {changed['dir']}")

        INBOUND.update(changed)

        persisted = True
        try:
            if 'dir' in changed:
                set_env_value('INBOUND_ATTACHMENT_DIR', changed['dir'])
            if 'enabled' in changed:
                set_env_value('SAVE_INBOUND_ATTACHMENTS', str(changed['enabled']).lower())
        except OSError as e:
            logger.error(f"Could not persist attachment config to .env: {e}")
            persisted = False

    logger.info(
        f"Inbound attachment config changed by {getattr(g, 'actor', 'unknown')}: "
        + ', '.join(f'{k}={v}' for k, v in changed.items())
        + (f', moved {moved} sender folder(s)' if moved else '')
    )

    response = {
        'ok': True,
        'inbound_dir': INBOUND['dir'],
        'resolved': os.path.realpath(INBOUND['dir']),
        'enabled': INBOUND['enabled'],
        'previous_dir': previous_dir,
        'moved': moved,
        'persisted': persisted,
        'restart_required': False
    }
    if 'dir' in changed and previous_dir != changed['dir'] and not moved:
        response['note'] = (
            f'Files already saved stay in {previous_dir}. Each inbox record '
            'carries the folder it was written to, so they still download '
            'correctly. Pass "move_existing": true to relocate them.'
        )
    return jsonify(response)

def find_email(msg_id):
    """One stored email by Message-ID or POP3 message number, or None."""
    for email_data in load_inbox().get('emails', []):
        if email_data.get('id') == msg_id or email_data.get('msg_num') == msg_id:
            return email_data
    return None

@app.route('/inbox/<msg_id>/attachments')
def list_email_attachments(msg_id):
    """Metadata for the files that arrived with one email."""
    email_data = find_email(msg_id)
    if not email_data:
        return jsonify({'error': 'Email not found'}), 404

    attachments = email_data.get('attachments', [])
    return jsonify({
        'id': email_data['id'],
        'count': len(attachments),
        'attachments': [
            dict(a, available=bool(resolve_inbound_path(a))) for a in attachments
        ]
    })

@app.route('/inbox/<msg_id>/attachments/<int:index>')
def download_email_attachment(msg_id, index):
    """Download one stored attachment by its position in the email."""
    email_data = find_email(msg_id)
    if not email_data:
        return jsonify({'error': 'Email not found'}), 404

    attachments = email_data.get('attachments', [])
    if index < 0 or index >= len(attachments):
        return jsonify({'error': f'No attachment {index} on this email'}), 404

    meta = attachments[index]
    if meta.get('skipped'):
        return jsonify({'error': f"Attachment was not stored: {meta['skipped']}"}), 410

    path = resolve_inbound_path(meta)
    if not path:
        return jsonify({
            'error': f"Attachment {meta.get('filename')!r} is no longer on disk"
        }), 404

    return send_file(path, mimetype=meta.get('content_type'),
                     as_attachment=True, download_name=meta.get('filename'))

@app.route('/inbox/<msg_id>/raw.eml')
def download_email_eml(msg_id):
    """
    Download one received email as an .eml file.

    Serves the message exactly as it arrived whenever its raw bytes were kept.
    Mail received before the bridge started keeping them - and mail whose blob
    has since been swept - is rebuilt from what is stored, marked
    X-Ravenclaw-Reconstructed on both the response and the file so the
    difference is never silent. ?mode=raw refuses the rebuild outright;
    ?mode=reconstruct asks for it even when the original is on hand.

    Every response says which it was in X-Ravenclaw-Eml-Source, so a caller
    knows what it got without having to test for a header's absence.

    Deliberately does not mark the email read: /inbox/<msg_id> rewrites the
    whole inbox file to flip that flag, and there is no reason to put a
    download inside that window.
    """
    email_data = find_email(msg_id)
    if not email_data:
        return jsonify({'error': 'Email not found'}), 404

    mode = request.args.get('mode', 'auto')
    if mode not in ('auto', 'raw', 'reconstruct'):
        return jsonify({
            'error': f'Unknown mode {mode!r}. Use one of: auto, raw, reconstruct'
        }), 400

    download_name = eml_download_name(email_data)
    path = resolve_raw_path(email_data.get('raw')) if mode != 'reconstruct' else None

    if path:
        response = send_file(path, mimetype='message/rfc822',
                             as_attachment=True, download_name=download_name)
        response.headers['X-Ravenclaw-Eml-Source'] = 'raw'
        return response

    if mode == 'raw':
        # 410, not 404: the email is here, only the bytes it arrived as are
        # not - a caller told 'not found' would go looking for the wrong thing.
        # Same call the attachment route makes for a file it never stored.
        return jsonify({
            'error': 'The original message was not retained for this email',
            'reason': 'blob_missing' if email_data.get('raw') else 'not_retained',
            'hint': 'Retry without ?mode=raw for an .eml rebuilt from what is stored'
        }), 410

    try:
        data = reconstruct_eml(email_data)
    except Exception as e:
        # A record can be missing or malformed in ways the rebuild cannot
        # paper over. The caller gets no detail; the log gets all of it.
        logger.error(f"Could not rebuild .eml for {email_data.get('id')}: {e}")
        return jsonify({'error': 'Could not rebuild this email as a .eml'}), 500

    return Response(
        data,
        mimetype='message/rfc822',
        headers={
            'Content-Disposition': f'attachment; filename="{download_name}"',
            'X-Ravenclaw-Eml-Source': 'reconstructed',
            'X-Ravenclaw-Reconstructed': 'yes'
        }
    )

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
    """
    Background inbox poller.

    Scheduled mail is handled solely by run_scheduled_checker; sweeping it
    from here too was a second, redundant path to the same sends.
    """
    while not shutdown_requested:
        try:
            check_inbox()
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
    print(f"Outbox file: {OUTBOX_FILE}")
    print(f"Listening on: {BRIDGE['host']}:{BRIDGE['port']}")
    if API_KEYS:
        print(f"API keys: {len(API_KEYS)} ({', '.join(sorted(set(API_KEYS.values())))})")
    else:
        print("API keys: NOT SET - API will return 503")
    print(f"Dedupe window: {DEDUPE_WINDOW}s" if DEDUPE_WINDOW else "Dedupe window: off (idempotency keys only)")
    print("=" * 50)

    if not API_KEYS:
        logger.warning("No API key configured - all API routes except /health will return 503.")
    if BRIDGE['host'] not in ('127.0.0.1', 'localhost') and not API_KEYS:
        logger.error("Binding a non-loopback address with no API key. Refusing to start.")
        sys.exit(1)

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
