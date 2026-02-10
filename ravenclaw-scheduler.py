# ravenclaw-scheduler.py
"""
Ravenclaw Email Scheduler
Checks emails every 30 minutes automatically
"""

import os
import sys
import time
import logging
import requests

# Load env
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(ENV_FILE):
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

BRIDGE_URL = os.environ.get('BRIDGE_URL', 'http://localhost:5002')
INTERVAL = int(os.environ.get('BRIDGE_POLL_INTERVAL', '30'))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [RAVENCLAW-SCHEDULER] %(message)s',
    handlers=[
        logging.FileHandler('ravenclaw-scheduler.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check():
    """Check emails"""
    try:
        logger.info("Checking emails...")
        r = requests.post(f'{BRIDGE_URL}/check', timeout=30)
        if r.status_code == 200:
            logger.info("Check completed successfully")
        else:
            logger.warning(f"Check returned: {r.status_code}")
    except Exception as e:
        logger.error(f"Check failed: {e}")

def status():
    """Check bridge status"""
    try:
        r = requests.get(f'{BRIDGE_URL}/health', timeout=10)
        if r.status_code == 200:
            data = r.json()
            logger.info(f"Bridge: {data.get('status', '?')} | Emails: {data.get('emails_count', 0)}")
    except:
        logger.warning("Bridge offline")

if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("Ravenclaw Scheduler Started")
    logger.info(f"Interval: {INTERVAL} minutes")
    logger.info("=" * 50)
    
    # Initial check
    check()
    
    # Schedule
    import schedule
    schedule.every(INTERVAL).minutes.do(check)
    schedule.every().hour.do(status)
    
    while True:
        schedule.run_pending()
        time.sleep(1)
