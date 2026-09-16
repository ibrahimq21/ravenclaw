# ravenclaw-bot.py
"""
Ravenclaw Discord Bot
Commands to control the email bridge from Discord
"""

import os
import sys

# Load env
ENV_FILE = '.env'
if os.path.exists(ENV_FILE):
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
BRIDGE_URL = os.environ.get('BRIDGE_URL', 'http://localhost:5002')
RAVENCLAW_API_KEY = os.environ.get('RAVENCLAW_API_KEY', '')

# Every bridge route except /health requires this header
AUTH_HEADERS = {'X-API-Key': RAVENCLAW_API_KEY}

if not DISCORD_BOT_TOKEN:
    print("[ERROR] DISCORD_BOT_TOKEN not found in .env!")
    sys.exit(1)

if not RAVENCLAW_API_KEY:
    print("[ERROR] RAVENCLAW_API_KEY not found in .env - bridge calls will fail!")
    sys.exit(1)

import discord
from discord.ext import commands
import requests

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"[OK] Ravenclaw Bot online: {bot.user}")
    print(f"[OK] Servers: {len(bot.guilds)}")

@bot.command(name='check', help='Check for new emails')
async def check(ctx):
    try:
        requests.post(f'{BRIDGE_URL}/check', headers=AUTH_HEADERS, timeout=10)
        await ctx.send('[OK] Email check triggered!')
    except Exception as e:
        await ctx.send(f'[ERROR] {e}')

@bot.command(name='send', help='Send email: !send <to> <subject> <message>')
async def send(ctx, to: str, subject: str, *, message: str):
    try:
        # on_behalf_of names the human who typed the command, so the outbox
        # shows more than "the bot sent it". The Discord message id is unique
        # per command invocation, so a retry cannot send the email twice.
        r = requests.post(f'{BRIDGE_URL}/send', json={
            'to': to, 'subject': subject, 'body': message,
            'on_behalf_of': str(ctx.author)
        }, headers={**AUTH_HEADERS, 'Idempotency-Key': f'discord:{ctx.message.id}'}, timeout=10)

        data = r.json() if r.content else {}
        if r.status_code == 200 and data.get('duplicate'):
            await ctx.send(f"[OK] Already sent to {to} at {data.get('sent_at')} - not sending again")
        elif r.status_code == 200:
            await ctx.send(f"[OK] Sent to {to} (id: {data.get('id', '?')[:8]})")
        else:
            await ctx.send(f"[ERROR] {data.get('error') or data.get('rejected') or r.status_code}")
    except Exception as e:
        await ctx.send(f'[ERROR] {e}')

@bot.command(name='status', help='Check bridge status')
async def status(ctx):
    try:
        r = requests.get(f'{BRIDGE_URL}/health', timeout=5)
        data = r.json()
        await ctx.send(f"**Ravenclaw Status**\nAccount: {data.get('account', '?')}\nAuto-reply: {data.get('auto_reply', '?')}")
    except:
        await ctx.send('[ERROR] Bridge offline!')

@bot.command(name='stats', help='View email stats')
async def stats(ctx):
    try:
        r = requests.get(f'{BRIDGE_URL}/stats', headers=AUTH_HEADERS, timeout=5)
        data = r.json()
        await ctx.send(f"**Email Stats**\nProcessed: {data.get('processed', 0)}\nRejected: {data.get('rejected', 0)}\nDomains: {', '.join(data.get('allowed_domains', []))}")
    except:
        await ctx.send('[ERROR] Could not fetch stats')

@bot.command(name='help', help='Show help')
async def help_cmd(ctx):
    await ctx.send("""**Ravenclaw Commands**

`!check` - Check emails
`!send <to> <subject> <message>` - Send email
`!status` - Bridge status
`!stats` - Email statistics

Slash commands also available: /check, /send, /status""")

@bot.tree.command(name='check', description='Check for new emails')
async def check_slash(interaction):
    try:
        requests.post(f'{BRIDGE_URL}/check', headers=AUTH_HEADERS, timeout=10)
        await interaction.response.send_message('[OK] Checked!')
    except:
        await interaction.response.send_message('[ERROR] Bridge offline')

@bot.tree.command(name='send', description='Send an email')
async def send_slash(interaction, to: str, subject: str, message: str):
    try:
        r = requests.post(f'{BRIDGE_URL}/send', json={
            'to': to, 'subject': subject, 'body': message,
            'on_behalf_of': str(interaction.user)
        }, headers={**AUTH_HEADERS, 'Idempotency-Key': f'discord:{interaction.id}'}, timeout=10)

        data = r.json() if r.content else {}
        if r.status_code == 200 and data.get('duplicate'):
            await interaction.response.send_message(f"[OK] Already sent to {to} at {data.get('sent_at')}")
        elif r.status_code == 200:
            await interaction.response.send_message(f'[OK] Sent to {to}')
        else:
            await interaction.response.send_message(f"[ERROR] {data.get('error') or r.status_code}")
    except Exception as e:
        await interaction.response.send_message(f'[ERROR] {e}')

@bot.tree.command(name='status', description='Check bridge status')
async def status_slash(interaction):
    try:
        r = requests.get(f'{BRIDGE_URL}/health', timeout=5)
        data = r.json()
        await interaction.response.send_message(f"**Status**: {data.get('status', '?')}")
    except:
        await interaction.response.send_message('[ERROR] Offline')

if __name__ == '__main__':
    print("=" * 40)
    print("Ravenclaw Discord Bot")
    print("=" * 40)
    bot.run(DISCORD_BOT_TOKEN)
