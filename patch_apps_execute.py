import sys

with open('app/apps/[workflowId]/page.tsx', 'r') as f:
    content = f.read()

replacement = '''    const [currentUserId, setCurrentUserId] = useState<string>("user1");

    useEffect(() => {
        const savedUserId = localStorage.getItem('current_userId');
        if (savedUserId) setCurrentUserId(savedUserId);
    }, []);

    useEffect(() => {
        if (!workflowId) return;

        const fetchWf = async () => {
            try {
                // We reuse the workspace fetch by just filtering the workspace's workflows.
                // In a true prod app we'd have a specific GET /api/workflows/[id]
                const res = await fetch('/api/workspaces', { headers: { 'x-user-id': currentUserId } });'''

target = '''    useEffect(() => {
        if (!workflowId) return;

        const fetchWf = async () => {
            try {
                // We reuse the workspace fetch by just filtering the workspace's workflows.
                // In a true prod app we'd have a specific GET /api/workflows/[id]
                const res = await fetch('/api/workspaces');'''

content = content.replace(target, replacement)

replacement_run = '''        const fetchRecentRuns = async (wid: string) => {
            try {
                const rRes = await fetch(`/api/runs/app/${wid}`, { headers: { 'x-user-id': currentUserId } });'''

target_run = '''        const fetchRecentRuns = async (wid: string) => {
            try {
                const rRes = await fetch(`/api/runs/app/${wid}`);'''

content = content.replace(target_run, replacement_run)

replacement_exec = '''            const response = await fetch("http://127.0.0.1:5000/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ steps: compiledData.steps, nodeOrder: compiledData.nodeOrder, user_id: currentUserId }),
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || "Failed to start execution");
            }

            const data = await response.json();
            const taskId = data.task_id;

            const eventSource = new EventSource(`http://127.0.0.1:5000/api/logs/${taskId}`);'''

target_exec = '''            const response = await fetch("http://127.0.0.1:8000/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ steps: compiledData.steps, nodeOrder: compiledData.nodeOrder }),
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || "Failed to start execution");
            }

            const data = await response.json();
            const taskId = data.task_id;

            const eventSource = new EventSource(`http://127.0.0.1:8000/api/logs/${taskId}`);'''

content = content.replace(target_exec, replacement_exec)


with open('app/apps/[workflowId]/page.tsx', 'w') as f:
    f.write(content)
