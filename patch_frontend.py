import re
with open("app/page.tsx", "r") as f:
    content = f.read()

start_idx = content.find('      try {\n        const response = await fetch("http://127.0.0.1:8000/execute"')

if start_idx != -1:
    end_pattern = re.compile(r'      \} catch \(error: any\) \{\n\s*alert\("Network Error: " \+ error\.message\);\n\s*\} finally \{\n\s*setIsExecuting\(false\);\n\s*\}')
    match = end_pattern.search(content, start_idx)
    if match:
        end_idx = match.end()
        print(f"Found block: {start_idx} to {end_idx}")

        new_fetch = """      try {
        const response = await fetch("http://127.0.0.1:8000/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ steps: compiledSteps, workspace_id: selectedWorkspace?.id || "temp", profile_id: "1", global_state })
        });

        if (!response.ok) {
           const err = await response.json();
           alert("Failed to queue workflow: " + (err.error || "Unknown error"));
           setIsExecuting(false);
           return;
        }

        const data = await response.json();
        const taskId = data.task_id;

        if (!taskId) {
            throw new Error("No task ID returned");
        }

        const eventSource = new EventSource(`http://127.0.0.1:8000/api/logs/${taskId}`);

        eventSource.onmessage = async (event) => {
            try {
                if (event.data === "__DONE__") {
                    eventSource.close();
                    setIsExecuting(false);
                    return;
                }
                const dataStr = event.data;
                const data = JSON.parse(dataStr);

                if (data.error) {
                    console.error("Execution error:", data.error);
                    setLogs(prev => [...prev, { status: "Error", message: data.error }]);
                    setIsExecuting(false);
                    setNodes(nds => nds.map(n => ({ ...n, data: { ...n.data, executionStatus: 'error' } })));
                    eventSource.close();
                    return;
                }

                if (data.status) {
                    setLogs(prev => [...prev, { status: data.status, message: data.message || data.result || "" }]);
                }

                if (data.step) {
                    // Map step ID (1-based index) to React Flow node ID
                    const targetNodeId = nodeOrder[data.step - 1];
                    if (targetNodeId) {
                        let statusToSet = 'running';
                        if (data.status === 'Complete') statusToSet = 'success';
                        if (data.status === 'Error' || data.status === 'Canceled') statusToSet = 'error';

                        setNodes(nds =>
                            nds.map(n => {
                                if (n.id === targetNodeId) {
                                    // Only upgrade status (don't downgrade success/error back to running)
                                    const currentStatus = n.data.executionStatus;
                                    if (currentStatus === 'success' || currentStatus === 'error') {
                                        return n;
                                    }
                                    return { ...n, data: { ...n.data, executionStatus: statusToSet, result: data.result || data.partial_result || n.data.result } };
                                }
                                return n;
                            })
                        );
                    }
                }

                if (data.status === 'Workflow Finished' || data.status === 'Error' || data.status === 'Canceled') {
                    setIsExecuting(false);

                    // Save to Execution History
                    if (selectedWorkspace) {
                        await fetch(`/api/runs/${selectedWorkspace.id}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                status: data.status,
                                logs: logs,
                                results: data.results || {},
                                nodes: nodes,
                                edges: edges
                            })
                        });
                        // Refresh history
                        fetchWorkflowData(selectedWorkspace.id);
                    }
                    eventSource.close();
                }
            } catch (e) {
                console.error("Error parsing JSON:", e, event.data);
            }
        };

        eventSource.onerror = (err) => {
            console.error("EventSource failed:", err);
            setIsExecuting(false);
            setNodes(nds => nds.map(n => ({ ...n, data: { ...n.data, executionStatus: 'error' } })));
            eventSource.close();
        };

      } catch (error: any) {
          console.error("Execution request failed:", error);
          alert("Network Error: " + error.message);
          setIsExecuting(false);
          setNodes(nds => nds.map(n => ({ ...n, data: { ...n.data, executionStatus: 'error' } })));
      }"""

        with open("app/page.tsx", "w") as f:
            f.write(content[:start_idx] + new_fetch + content[end_idx:])
        print("Replaced successfully")
    else:
        print("Regex not matched")
else:
    print("Start not found")
