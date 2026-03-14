import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Add logic to auto-resume on mount
auto_resume = """
  useEffect(() => {
    const savedTaskId = localStorage.getItem('current_task_id');
    if (savedTaskId) {
      console.log("Resuming task:", savedTaskId);
      setIsExecuting(true);
      connectSSE(savedTaskId);
    }
  }, []);
"""

if "Resuming task" not in content:
    content = content.replace("export default function Page() {", "export default function Page() {" + auto_resume)

with open('app/page.tsx', 'w') as f:
    f.write(content)
