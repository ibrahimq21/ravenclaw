# Ravenclaw Makefile
# Usage: make <target>
#
# Targets:
#   all           - Start all components (bridge, bot, scheduler, sync)
#   bridge        - Start email bridge only
#   bot           - Start Discord bot only
#   scheduler     - Start scheduler only
#   sync          - Start JSON file watcher (syncs new emails to Discord)
#   check         - Trigger manual email check
#   inbox         - View all received emails (JSON)
#   unread        - View unread emails
#   email <id>    - View specific email by ID
#   status        - Check bridge status
#   stats         - View statistics
#   send          - Send an email (usage: make send TO=x SUBJECT=y BODY=z)
#   clean         - Clean log files
#   install       - Install dependencies
#   help          - Show this help
#
# Environment Variables (.env):
#   DOMAIN_FILTER       - Comma-separated list of allowed domains
#   BRIDGE_POLL_INTERVAL - Minutes between email checks (default: 30)

.PHONY: all bridge bot scheduler sync check inbox unread email status stats send clean install help

# Default target
all: bridge bot scheduler sync

# Start email bridge
bridge:
	@echo "[RAVENCLAW] Starting email bridge..."
	@python ravenclaw.py

# Start Discord bot
bot:
	@echo "[RAVENCLAW] Starting Discord bot..."
	@python ravenclaw-bot.py

# Start scheduler
scheduler:
	@echo "[RAVENCLAW] Starting scheduler..."
	@python ravenclaw-scheduler.py

# Start sync watcher
sync:
	@echo "[RAVENCLAW] Starting sync watcher..."
	@python ravenclaw_sync.py

# Trigger email check
check:
	@echo "[RAVENCLAW] Checking emails..."
	@curl -s -X POST http://localhost:5002/check || echo "Bridge not running"

# View inbox (all emails)
inbox:
	@echo "[RAVENCLAW] All received emails:"
	@curl -s http://localhost:5002/inbox | python -m json.tool 2>/dev/null || echo "Bridge not running"

# View unread emails
unread:
	@echo "[RAVENCLAW] Unread emails:"
	@curl -s http://localhost:5002/unread | python -m json.tool 2>/dev/null || echo "Bridge not running"

# View specific email
email:
	@echo "[RAVENCLAW] Email details:"
	@curl -s http://localhost:5002/inbox/$(id) | python -m json.tool 2>/dev/null || echo "Email not found"

# Check bridge status
status:
	@echo "[RAVENCLAW] Bridge status:"
	@curl -s http://localhost:5002/health 2>/dev/null | python -m json.tool || echo "Bridge offline"

# View statistics
stats:
	@echo "[RAVENCLAW] Statistics:"
	@curl -s http://localhost:5002/stats 2>/dev/null | python -m json.tool || echo "Bridge offline"

# Send an email
# Usage: make send TO=x SUBJECT=y BODY=z
send:
	@echo "[RAVENCLAW] Sending email to $(TO)..."
	@curl -s -X POST http://localhost:5002/send \
		-H "Content-Type: application/json" \
		-d '{"to":"$(TO)","subject":"$(SUBJECT)","body":"$(BODY)"}' || echo "Failed"

# Clean log files
clean:
	@echo "[RAVENCLAW] Cleaning logs..."
	@-del /Q *.log 2>nul
	@-del /Q ravenclaw_*.log 2>nul
	@echo "[RAVENCLAW] Logs cleaned"

# Install dependencies
install:
	@echo "[RAVENCLAW] Installing dependencies..."
	@pip install -q requests flask discord.py
	@echo "[RAVENCLAW] Dependencies installed"

# Show help
help:
	@echo "=================================================="
	@echo "  RAVENCLAW EMAIL BRIDGE - Makefile"
	@echo "=================================================="
	@echo ""
	@echo "USAGE:"
	@echo "  make <target> [VAR=value]"
	@echo ""
	@echo "TARGETS:"
	@echo "  all           Start all components"
	@echo "  bridge        Start email bridge"
	@echo "  bot           Start Discord bot"
	@echo "  scheduler     Start scheduler"
	@echo "  sync          Start JSON file watcher (syncs new emails to Discord)"
	@echo "  check         Trigger email check"
	@echo "  inbox         View all received emails"
	@echo "  unread        View unread emails"
	@echo "  email id=xxx  View specific email"
	@echo "  status        Check bridge status"
	@echo "  stats         View statistics"
	@echo "  send          Send email"
	@echo "  clean         Clean logs"
	@echo "  install       Install dependencies"
	@echo "  help          Show this help"
	@echo ""
	@echo "ENVIRONMENT VARIABLES (.env):"
	@echo "  DOMAIN_FILTER        - Allowed domains (comma-separated)"
	@echo "  BRIDGE_POLL_INTERVAL - Minutes between checks (default: 30)"
	@echo ""
	@echo "FILES:"
	@echo "  ravenclaw_inbox.json      - Received emails storage"
	@echo "  ravenclaw_sync_state.json - Sync tracking state"
	@echo "  ravenclaw.log             - Bridge logs"
	@echo ""
	@echo "EXAMPLES:"
	@echo "  make all"
	@echo "  make sync"
	@echo "  make check"
	@echo "  make inbox"
	@echo "  make unread"
	@echo "  make status"
	@echo "  make stats"
	@echo "  make send TO=user@domain.com SUBJECT=Hello BODY=Test"
	@echo ""
	@echo "=================================================="
