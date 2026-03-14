import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

old_run = """  const handleRun = async () => {
      const { steps: compiledSteps, nodeOrder } = compileNodesToSteps(nodes, edges);"""

new_run = """  const handleRun = async () => {
    if (!selectedWorkspace) return;
    if (nodes.length === 0) {
        alert("Please drag at least one node to the canvas before running.");
        return;
    }

    let compiledData;
    try {
        compiledData = compileNodesToSteps(nodes, edges);
    } catch (err: any) {
        alert(err.message || "Failed to compile workflow");
        return;
    }
    const { steps: compiledSteps, nodeOrder } = compiledData;"""

if old_run in content:
    content = content.replace(old_run, new_run)

# Add cycle detection to compileNodesToSteps in frontend as well for safety
old_compile = """const compileNodesToSteps = (nodes: Node[], edges: Edge[]) => {
  const steps: any[] = [];
  const nodeOrder: string[] = [];"""

new_compile = """const compileNodesToSteps = (nodes: Node[], edges: Edge[]) => {
  const inDegree: Record<string, number> = {};
  nodes.forEach(n => inDegree[n.id] = 0);
  edges.forEach(e => {
      if (inDegree[e.target] !== undefined) {
          inDegree[e.target]++;
      }
  });

  const queue = nodes.filter(n => inDegree[n.id] === 0).map(n => n.id);
  let visitedCount = 0;

  while (queue.length > 0) {
      const curr = queue.shift()!;
      visitedCount++;
      edges.forEach(e => {
          if (e.source === curr) {
              if (inDegree[e.target] !== undefined) {
                  inDegree[e.target]--;
                  if (inDegree[e.target] === 0) queue.push(e.target);
              }
          }
      });
  }

  if (visitedCount !== nodes.length && nodes.length > 0) {
      throw new Error("警告：存在循环依赖 / Circular dependency detected in workflow diagram.");
  }

  const steps: any[] = [];
  const nodeOrder: string[] = [];"""

if old_compile in content:
    content = content.replace(old_compile, new_compile)


with open('app/page.tsx', 'w') as f:
    f.write(content)
