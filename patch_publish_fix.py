import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Fix the URL used in fetch for publishing - it needs the workflow ID, not workspace ID.
old_publish_fetch = "fetch(`/api/workflows/${selectedWorkspace.id}/publish`"
new_publish_fetch = "fetch(`/api/workflows/${selectedWorkspace.workflows && selectedWorkspace.workflows.length > 0 ? selectedWorkspace.workflows[0].id : ''}/publish`"

if old_publish_fetch in content:
    content = content.replace(old_publish_fetch, new_publish_fetch)

with open('app/page.tsx', 'w') as f:
    f.write(content)
