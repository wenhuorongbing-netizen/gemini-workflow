import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Make sure AlertCircle is imported properly
if "import { AlertCircle" not in content:
    content = content.replace("import { Home, FileText", "import { Home, FileText, AlertCircle")

# Add auto-scroll effect
auto_scroll_effect = """  // Auto-scroll logs
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);"""

if "// Auto-scroll logs" not in content:
    content = content.replace("  // Resume SSE stream on load", auto_scroll_effect + "\n\n  // Resume SSE stream on load")


# Update handleRun to save task_id to localStorage
old_handle_run_success = """      const data = await response.json();
      if (data.task_id) {
          connectSSE(data.task_id);
      }"""
new_handle_run_success = """      const data = await response.json();
      if (data.task_id) {
          localStorage.setItem('current_task_id', data.task_id);
          connectSSE(data.task_id);
      }"""
content = content.replace(old_handle_run_success, new_handle_run_success)

# Update connectSSE to remove task_id on complete
old_sse_complete = """        if (parsed.status === "Complete" || parsed.status === "Workflow Finished" || parsed.status === "Error" || parsed.status === "Jules Error") {
            setIsExecuting(false);
            eventSource.close();
            setLogs((prev) => [...prev, parsed]);

            // Optionally refetch runs to show the new one
            if (selectedWorkspace) {
                fetchRuns(selectedWorkspace.id);
            }
        }"""
new_sse_complete = """        if (parsed.status === "Complete" || parsed.status === "Workflow Finished" || parsed.status === "Error" || parsed.status === "Jules Error") {
            setIsExecuting(false);
            eventSource.close();
            localStorage.removeItem('current_task_id');
            setLogs((prev) => [...prev, parsed]);

            // Optionally refetch runs to show the new one
            if (selectedWorkspace) {
                fetchRuns(selectedWorkspace.id);
            }
        }"""
content = content.replace(old_sse_complete, new_sse_complete)

with open('app/page.tsx', 'w') as f:
    f.write(content)
