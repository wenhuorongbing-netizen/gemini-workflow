import re

with open('app.py', 'r') as f:
    content = f.read()

# Replace `for node in nodes:` with `for step in steps:`
# and `node['id']` with `step['id']`
content = content.replace("for node in nodes:", "for s in steps:")
content = content.replace("tag = f\"{{{{{node['id']}}}}}\"", "tag = f\"{{{{{s.get('id', '')}}}}}\"")
content = content.replace("node['id'] in results", "s.get('id', '') in results")
content = content.replace("results[node['id']]", "results[s.get('id', '')]")

with open('app.py', 'w') as f:
    f.write(content)
