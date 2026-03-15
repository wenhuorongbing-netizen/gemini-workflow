import sys
import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# 1. Add currentUserId state
replacement_state = '''  const [accountProfileStr, setAccountProfileStr] = useState("1");
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [currentUserId, setCurrentUserId] = useState<string>("user1");

  useEffect(() => {
    const savedUserId = localStorage.getItem('current_userId');
    if (savedUserId) setCurrentUserId(savedUserId);
  }, []);

  useEffect(() => {
    localStorage.setItem('current_userId', currentUserId);
    fetchWorkspaces();
  }, [currentUserId]);'''

target_state = '''  const [accountProfileStr, setAccountProfileStr] = useState("1");
  const [isLoggingIn, setIsLoggingIn] = useState(false);'''

content = content.replace(target_state, replacement_state)


# 2. Patch fetches to include headers

content = re.sub(r'await fetch\("/api/workspaces"\)', r'await fetch("/api/workspaces", { headers: { "x-user-id": currentUserId } })', content)

content = re.sub(
    r'await fetch\("/api/workspaces", \{\s*method: "POST",\s*headers: \{ "Content-Type": "application/json" \},\s*body: JSON\.stringify\(\{ name \}\),\s*\}\);',
    r'await fetch("/api/workspaces", { method: "POST", headers: { "Content-Type": "application/json", "x-user-id": currentUserId }, body: JSON.stringify({ name }) });',
    content
)

content = re.sub(r'await fetch\(`/api/workflows/\$\{selectedWorkspace.id\}`,\s*\{\s*method: \'POST\',\s*headers:\s*\{\s*\'Content-Type\':\s*\'application/json\'\s*\},',
                 r'await fetch(`/api/workflows/${selectedWorkspace.id}`, { method: "POST", headers: { "Content-Type": "application/json", "x-user-id": currentUserId },',
                 content)

content = re.sub(r'fetch\(`/api/workflows/save`,\s*\{\s*method:\s*\'POST\',\s*headers:\s*\{\s*\'Content-Type\':\s*\'application/json\'\s*\},',
                 r'fetch(`/api/workflows/save`, { method: "POST", headers: { "Content-Type": "application/json", "x-user-id": currentUserId },',
                 content)

content = re.sub(r'await fetch\(`/api/workflows/\$\{workspaceId\}`\)',
                 r'await fetch(`/api/workflows/${workspaceId}`, { headers: { "x-user-id": currentUserId } })',
                 content)

content = re.sub(r'await fetch\(`/api/runs/\$\{workspaceId\}`\)',
                 r'await fetch(`/api/runs/${workspaceId}`, { headers: { "x-user-id": currentUserId } })',
                 content)

content = re.sub(r'await fetch\(`/api/workflows/\$\{\(selectedWorkspace as any\).workflows && \(selectedWorkspace as any\).workflows.length > 0 \? \(selectedWorkspace as any\).workflows\[0\].id : \'\'\}/publish`,\s*\{\s*method: \'POST\',\s*headers: \{ \'Content-Type\': \'application/json\' \},',
                 r'await fetch(`/api/workflows/${(selectedWorkspace as any).workflows && (selectedWorkspace as any).workflows.length > 0 ? (selectedWorkspace as any).workflows[0].id : \'\'}/publish`, { method: "POST", headers: { "Content-Type": "application/json", "x-user-id": currentUserId },',
                 content)

content = re.sub(r'await fetch\(`/api/runs/\$\{selectedWorkspace\?.id\}`,\s*\{\s*method:\s*\'POST\',\s*headers:\s*\{\s*\'Content-Type\':\s*\'application/json\'\s*\},',
                 r'await fetch(`/api/runs/${selectedWorkspace?.id}`, { method: "POST", headers: { "Content-Type": "application/json", "x-user-id": currentUserId },',
                 content)

with open('app/page.tsx', 'w') as f:
    f.write(content)
