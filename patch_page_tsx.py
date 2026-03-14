import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Replace the onChange handler to use an object wrapper like the others do
content = content.replace(
    "onChange={(e) => updateNodeData(node.id, 'triggerType', e.target.value)}",
    "onChange={(e) => updateNodeData(node.id, { triggerType: e.target.value })}"
)
content = content.replace(
    "onChange={(e) => updateNodeData(node.id, 'cron', e.target.value)}",
    "onChange={(e) => updateNodeData(node.id, { cron: e.target.value })}"
)

with open('app/page.tsx', 'w') as f:
    f.write(content)
