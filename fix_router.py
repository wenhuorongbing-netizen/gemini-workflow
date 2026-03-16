import re

with open('app.py', 'r') as f:
    content = f.read()

# Let's see the rest of the router logic
match = re.search(r'elif step_type == \'router\':.*?elif step_type == \'webhook\':', content, re.DOTALL)
if match:
    print(match.group(0))
