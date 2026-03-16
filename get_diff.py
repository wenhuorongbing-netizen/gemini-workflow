import re

with open('bot.py', 'r') as f:
    content = f.read()

print("get_last_response" in content)
