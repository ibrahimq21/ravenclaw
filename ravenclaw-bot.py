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

if not DISCORD_BOT_TOKEN:
    print("[ERROR] DISCORD_BOT_TOKEN not found in .env!")
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
        requests.post(f'{BRIDGE_URL}/check', timeout=10)
        await ctx.send('[OK] Email check triggered!')
    except Exception as e:
        await ctx.send(f'[ERROR] {e}')

@bot.command(name='send', help='Send email: !send <to> <subject> <message>')
async def send(ctx, to: str, subject: str, *, message: str):
    try:
        r = requests.post(f'{BRIDGE_URL}/send', json={
            'to': to, 'subject': subject, 'body': message
        }, timeout=10)
        if r.status_code == 200:
            await ctx.send(f'[OK] Sent to {to}')
        else:
            await ctx.send(f'[ERROR] Failed')
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
        r = requests.get(f'{BRIDGE_URL}/stats', timeout=5)
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
        requests.post(f'{BRIDGE_URL}/check', timeout=10)
        await interaction.response.send_message('[OK] Checked!')
    except:
        await interaction.response.send_message('[ERROR] Bridge offline')

@bot.tree.command(name='send', description='Send an email')
async def send_slash(interaction, to: str, subject: str, message: str):
    try:
        r = requests.post(f'{BRIDGE_URL}/send', json={'to': to, 'subject': subject, 'body': message}, timeout=10)
        await interaction.response.send_message(f'[OK] Sent to {to}')
    except:
        await interaction.response.send_message('[ERROR] Failed')

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
