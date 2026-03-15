import sys

with open('app/page.tsx', 'r') as f:
    content = f.read()

replacement = '''        const response = await fetch("http://127.0.0.1:5000/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ steps: compiledSteps, workspace_id: selectedWorkspace?.id || "temp", profile_id: "1", global_state, user_id: currentUserId })
        });'''

target = '''        const response = await fetch("http://127.0.0.1:5000/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ steps: compiledSteps, workspace_id: selectedWorkspace?.id || "temp", profile_id: "1", global_state })
        });'''

content = content.replace(target, replacement)

with open('app/page.tsx', 'w') as f:
    f.write(content)
