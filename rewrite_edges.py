import re

with open("app/page.tsx", "r") as f:
    content = f.read()

# We want to animate edges that are connected to a running node.
# Since handleRun updates nodes, we can add an effect that watches `nodes` and updates `edges`.

edge_effect = """  // Auto-Save Debounce
  useEffect(() => {
    if (!selectedWorkspace || isLoading) return;

    const timeoutId = setTimeout(() => {
      saveWorkflowSilent();
    }, 2000);

    return () => clearTimeout(timeoutId);
  }, [nodes, edges, selectedWorkspace]);

  // Animated Edges Logic
  useEffect(() => {
      if (isExecuting) {
          const runningNodes = new Set(nodes.filter(n => n.data?.executionStatus === 'running').map(n => n.id));
          setEdges(eds => eds.map(e => ({
              ...e,
              animated: runningNodes.has(e.source) || runningNodes.has(e.target)
          })));
      } else {
          // Turn off animations when not executing
          setEdges(eds => eds.map(e => ({ ...e, animated: false })));
      }
  }, [nodes, isExecuting]);"""

content = content.replace("""  // Auto-Save Debounce
  useEffect(() => {
    if (!selectedWorkspace || isLoading) return;

    const timeoutId = setTimeout(() => {
      saveWorkflowSilent();
    }, 2000);

    return () => clearTimeout(timeoutId);
  }, [nodes, edges, selectedWorkspace]);""", edge_effect)

with open("app/page.tsx", "w") as f:
    f.write(content)
