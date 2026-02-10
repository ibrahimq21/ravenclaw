# Fix ENV_FILE path in ravenclaw.py
import os

filepath = 'C:\\Users\\ibrahim.q.scs\\.openclaw\\workspace\\email-bridge\\ravenclaw.py'
with open(filepath, 'r') as f:
    content = f.read()

old = "ENV_FILE = '.env'"
new = "ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')"

content = content.replace(old, new)

with open(filepath, 'w') as f:
    f.write(content)

print('Updated ENV_FILE path')
