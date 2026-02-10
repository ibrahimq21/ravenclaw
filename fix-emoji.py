# Remove emojis from ravenclaw.py
import os

filepath = 'C:\\Users\\ibrahim.q.scs\\.openclaw\\workspace\\email-bridge\\ravenclaw.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace emojis with text
replacements = {
    '[RAVENCLAW]': '[RAVENCLAW]',
    '✅': '[OK]',
    '❌': '[ERROR]'
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print('Removed emojis')
