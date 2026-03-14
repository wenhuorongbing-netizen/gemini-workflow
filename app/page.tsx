"use client";

import { useState, useEffect, useCallback, useMemo, useRef, useTransition } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  applyNodeChanges,
  applyEdgeChanges,
  NodeChange,
  EdgeChange,
  Connection,
  addEdge,
  Handle,
  Position,
  Node,
  Edge,
  BackgroundVariant
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Play, Bot, Globe, Repeat, FileJson, Loader2, CheckCircle2, XCircle } from "lucide-react";

interface Workspace {
  id: string;
  name: string;
  steps?: any[];
}

// --- Custom Nodes ---

const BaseNode = ({ icon: Icon, title, content, bgColor, borderColor, data }: any) => {
  const status = data?.executionStatus || 'idle';

  let statusClasses = "";
  let StatusIcon = null;

  if (status === 'running') {
      statusClasses = "ring-2 ring-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.5)]";
      StatusIcon = Loader2;
  } else if (status === 'success') {
      statusClasses = "ring-2 ring-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.3)] border-emerald-500";
      StatusIcon = CheckCircle2;
  } else if (status === 'error') {
      statusClasses = "ring-2 ring-rose-500 shadow-[0_0_15px_rgba(244,63,94,0.3)] border-rose-500";
      StatusIcon = XCircle;
  }

  return (
    <div className={`w-[280px] rounded-lg shadow-lg border-2 ${borderColor} ${bgColor} ${statusClasses} transition-all duration-300 overflow-hidden text-slate-50 flex flex-col`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-slate-300" />
      <div className={`px-4 py-2 border-b ${borderColor} flex justify-between items-center font-semibold tracking-wide bg-opacity-20 bg-black`}>
        <div className="flex items-center gap-2">
            <Icon size={18} />
            <span>{title}</span>
        </div>
        {StatusIcon && <StatusIcon size={16} className={status === 'running' ? 'animate-spin text-blue-400' : status === 'success' ? 'text-emerald-400' : 'text-rose-400'} />}
      </div>
      <div className="p-4 flex-1 text-sm bg-slate-900/50">
        <div className="text-slate-300 truncate">{content}</div>
      </div>
      <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-slate-300" />
    </div>
  );
};

const TriggerNode = ({ data }: any) => (
  <BaseNode data={data} icon={Play} title="Trigger" content={data.label || "Manual Run"} bgColor="bg-emerald-900" borderColor="border-emerald-700" />
);

const GeminiNode = ({ data }: any) => (
  <BaseNode data={data} icon={Bot} title="Gemini AI" content={data.prompt || "Enter prompt..."} bgColor="bg-blue-900" borderColor="border-blue-700" />
);

const ScraperNode = ({ data }: any) => (
  <BaseNode data={data} icon={Globe} title="Web Scraper" content={data.url || "https://..."} bgColor="bg-amber-900" borderColor="border-amber-700" />
);

const AgentLoopNode = ({ data }: any) => (
  <BaseNode data={data} icon={Repeat} title="Agentic Loop" content={`Target: ${data.url || "None"}`} bgColor="bg-purple-900" borderColor="border-purple-700" />
);

const nodeTypes = {
  trigger: TriggerNode,
  gemini: GeminiNode,
  scraper: ScraperNode,
  agentic_loop: AgentLoopNode,
};

const initialNodes: Node[] = [
  { id: "1", type: "trigger", position: { x: 250, y: 50 }, data: { label: "Manual Run" } },
  { id: "2", type: "gemini", position: { x: 250, y: 200 }, data: { prompt: "Analyze the following data..." } },
];
const initialEdges: Edge[] = [{ id: "e1-2", source: "1", target: "2" }];

// --- Topology Compiler ---
// Sorts nodes based on edge connections to generate a linear execution plan for app.py
function compileNodesToSteps(nodes: Node[], edges: Edge[]) {
    const inDegree: Record<string, number> = {};
    const adjList: Record<string, string[]> = {};
    const nodeMap: Record<string, Node> = {};

    nodes.forEach(n => {
        inDegree[n.id] = 0;
        adjList[n.id] = [];
        nodeMap[n.id] = n;
    });

    edges.forEach(e => {
        if (adjList[e.source]) {
            adjList[e.source].push(e.target);
            if (inDegree[e.target] !== undefined) {
                inDegree[e.target]++;
            }
        }
    });

    const queue: string[] = [];
    nodes.forEach(n => {
        if (inDegree[n.id] === 0) queue.push(n.id);
    });

    const sortedIds: string[] = [];
    while (queue.length > 0) {
        const u = queue.shift()!;
        sortedIds.push(u);
        adjList[u].forEach(v => {
            inDegree[v]--;
            if (inDegree[v] === 0) queue.push(v);
        });
    }

    // Filter out the trigger node, as app.py only wants actionable steps
    const actionNodes = sortedIds.map(id => nodeMap[id]).filter(n => n.type !== 'trigger');

    // Map to app.py schema
    const steps = actionNodes.map(n => {
        const base = {
            type: n.type === 'gemini' ? 'standard' : n.type,
            prompt: n.data.prompt || n.data.url || '',
            new_chat: n.data.new_chat || false,
            show_result: true,
        };

        if (n.type === 'agentic_loop') {
            return {
                ...base,
                id: n.id,
                chat_url: n.data.url || '',
                max_iterations: n.data.max_iterations || 3,
                reset_threshold: n.data.reset_threshold || 3
            };
        }
        return { ...base, id: n.id };
    });

    return { steps, nodeOrder: actionNodes.map(n => n.id) };
}

// --- Main App Shell ---

export default function AppShell() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null);
  const [activeTab, setActiveTab] = useState<"editor" | "dashboard" | "runs">("editor");
  const [isLoading, setIsLoading] = useState(true);

  // React Flow State
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [logs, setLogs] = useState<{status: string, message: string}[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Snapshot / Run History State
  const [runHistory, setRunHistory] = useState<any[]>([]);
  const [playbackRun, setPlaybackRun] = useState<any | null>(null);
  const isPlaybackMode = !!playbackRun;

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  useEffect(() => {
    if (selectedWorkspace) {
      fetchWorkflowData(selectedWorkspace.id);
    }
  }, [selectedWorkspace]);


  // Auto-Save Debounce
  useEffect(() => {
    if (!selectedWorkspace || isLoading) return;

    const timeoutId = setTimeout(() => {
      saveWorkflowSilent();
    }, 2000);

    return () => clearTimeout(timeoutId);
  }, [nodes, edges, selectedWorkspace]);

  const saveWorkflowSilent = async () => {
    if (!selectedWorkspace) return;
    try {
        await fetch(`/api/workflows/${selectedWorkspace.id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nodes, edges })
        });
    } catch (e) {
        console.error("Silent auto-save failed", e);
    }
  };

  const fetchWorkflowData = async (workspaceId: string) => {
    try {
      const res = await fetch(`/api/workflows/${workspaceId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.nodes && data.nodes.length > 0) {
            setNodes(data.nodes);
            setEdges(data.edges || []);
        } else {
            setNodes(initialNodes);
            setEdges(initialEdges);
        }
      }

      const runRes = await fetch(`/api/runs/${workspaceId}`);
      if (runRes.ok) {
          setRunHistory(await runRes.json());
      }
    } catch (e) {
      console.error("Failed to load workflow data", e);
    }
  };

  const handleSave = async () => {
    if (!selectedWorkspace) return;
    setIsSaving(true);
    try {
        const res = await fetch(`/api/workflows/${selectedWorkspace.id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nodes, edges })
        });
        if (res.ok) {
            alert("Blueprint saved successfully!");
        }
    } catch (e) {
        console.error("Failed to save workflow", e);
        alert("Failed to save workflow");
    } finally {
        setIsSaving(false);
    }
  };

  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  const updateNodeData = (id: string, newData: any) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === id) {
          return { ...node, data: { ...node.data, ...newData } };
        }
        return node;
      })
    );
  };


  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );
  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    []
  );

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const fetchWorkspaces = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/workspaces");
      if (res.ok) {
        const data = await res.json();
        setWorkspaces(data);
        if (data.length > 0 && !selectedWorkspace) {
          setSelectedWorkspace(data[0]);
        }
      }
    } catch (error) {
      console.error("Error fetching workspaces:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const addNode = (type: string) => {
    const newNode: Node = {
      id: Date.now().toString(),
      type,
      position: { x: Math.random() * 200 + 100, y: Math.random() * 200 + 100 },
      data: { prompt: "New Step...", url: "https://..." }
    };
    setNodes((nds) => [...nds, newNode]);
  };

  const handleNewWorkspace = async () => {
    const name = prompt("Enter a name for the new workspace:");
    if (!name) return;

    try {
      const res = await fetch("/api/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (res.ok) {
        const newWs = await res.json();
        fetchWorkspaces();
        setSelectedWorkspace(newWs);
      }
    } catch (e) {
      console.error("Error creating workspace", e);
    }
  };

  const handleRun = async () => {
      const { steps: compiledSteps, nodeOrder } = compileNodesToSteps(nodes, edges);
      console.log("Compiled JSON Payload for app.py:", compiledSteps);

      setLogs([]); // Clear previous logs
      setIsExecuting(true);

      // Reset all node statuses
      setNodes(nds => nds.map(n => ({...n, data: {...n.data, executionStatus: 'idle'}})));

      try {
        const response = await fetch("http://127.0.0.1:8000/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ steps: compiledSteps, workspace_id: selectedWorkspace?.id || "temp", profile_id: "1" })
        });

        if (!response.ok) {
           const err = await response.json();
           alert("Failed to start workflow: " + (err.error || "Unknown error"));
           setIsExecuting(false);
           return;
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body reader.");
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split('\n\n');
            buffer = events.pop() || "";

            for (let evt of events) {
                if (evt.startsWith('data: ')) {
                    const dataStr = evt.substring(6);
                    if (!dataStr) continue;

                    try {
                        const data = JSON.parse(dataStr);

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
                                            return { ...n, data: { ...n.data, executionStatus: statusToSet } };
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
                                // Re-map results to node IDs based on step numbers if they aren't already
                                // app.py returns strings matching past_id. Our past_id logic uses `step.id`, which we set to `nodeOrder[index]`.
                                // Wait, `app.py` `step_id` is now literally `step.get('id')` which IS the React Flow Node ID.
                                // So `data.results` dictionary has keys that are exactly `node.id`.
                                await fetch(`/api/runs/${selectedWorkspace.id}`, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        status: data.status,
                                        logs: [], // We can pass accumulated logs here if desired
                                        results: data.results || {}
                                    })
                                });
                                // Refresh history
                                fetchWorkflowData(selectedWorkspace.id);
                            }
                        }
                    } catch (e) {
                        console.error("Error parsing chunk:", e);
                    }
                }
            }
        }
      } catch (error: any) {
        alert("Network Error: " + error.message);
      } finally {
        setIsExecuting(false);
      }
  };

  return (
    <div className="flex h-screen bg-slate-50 font-sans text-slate-800">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 flex-shrink-0 shadow-2xl z-10">
        <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-950">
          <h1 className="font-bold text-white text-lg tracking-tight flex items-center gap-2">
            <Bot size={20} className="text-blue-500" />
            Gemini Builder
          </h1>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-2 mt-2">
            Workspaces
          </div>

          {isLoading ? (
            <div className="px-2 text-sm text-slate-500">Loading...</div>
          ) : workspaces.length === 0 ? (
            <div className="px-2 text-sm text-slate-500">No workspaces found.</div>
          ) : (
            workspaces.map((ws) => (
              <button
                key={ws.id}
                onClick={() => setSelectedWorkspace(ws)}
                className={`w-full text-left px-3 py-2 rounded-md transition-all text-sm flex items-center gap-2 ${
                  selectedWorkspace?.id === ws.id
                    ? "bg-blue-600 text-white font-medium shadow-md shadow-blue-900/20"
                    : "hover:bg-slate-800 hover:text-white"
                }`}
              >
                <FileJson size={16} className={selectedWorkspace?.id === ws.id ? "text-blue-200" : "text-slate-500"}/>
                {ws.name}
              </button>
            ))
          )}
        </div>
        <div className="p-4 border-t border-slate-800">
          <button
            onClick={handleNewWorkspace}
            className="w-full flex items-center justify-center space-x-2 bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-md transition-colors text-sm font-medium border border-slate-700"
          >
            <span>+ New Workspace</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 bg-slate-50">
        {/* Header */}
        <header className="bg-white border-b border-slate-200 h-16 flex items-center justify-between px-6 flex-shrink-0 shadow-sm z-10">
          <div className="flex items-center gap-4">
            <h2 className="text-xl font-bold text-slate-800 truncate">
              {selectedWorkspace ? selectedWorkspace.name : "Select a Workspace"}
            </h2>
            <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200 ml-4">
              <button
                onClick={() => setActiveTab("editor")}
                className={`px-4 py-1.5 text-sm font-semibold rounded-md transition-all ${
                  activeTab === "editor"
                    ? "bg-white text-blue-600 shadow-sm border border-slate-200"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                Canvas Editor
              </button>
              <button
                onClick={() => setActiveTab("runs")}
                className={`px-4 py-1.5 text-sm font-semibold rounded-md transition-all ${
                  activeTab === "runs"
                    ? "bg-white text-blue-600 shadow-sm border border-slate-200"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                Run History
              </button>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={handleSave}
              disabled={!selectedWorkspace || isSaving}
              className="bg-slate-800 hover:bg-slate-900 text-white px-4 py-2 rounded-md font-medium text-sm transition-colors shadow-sm flex items-center gap-2 disabled:opacity-50"
            >
              <FileJson size={16} /> {isSaving ? "Saving..." : "💾 Save Workflow"}
            </button>
            <button
              onClick={handleRun}
              disabled={!selectedWorkspace || isExecuting}
              className={`text-white px-5 py-2 rounded-md font-bold text-sm transition-colors shadow-md flex items-center gap-2 ${
                 isExecuting ? "bg-emerald-800 opacity-70 cursor-not-allowed" : "bg-emerald-600 hover:bg-emerald-700 shadow-emerald-900/20"
              }`}
            >
              <Play size={16} /> {isExecuting ? "Executing..." : "▶ Run Workflow"}
            </button>
          </div>
        </header>

        {/* Toolbar */}
        {activeTab === "editor" && (
            <div className="bg-slate-100 border-b border-slate-200 px-6 py-2 flex items-center gap-2 z-10 shadow-sm">
                <span className="text-sm font-bold text-slate-500 mr-2 uppercase tracking-wide">Nodes:</span>
                <button onClick={() => addNode('gemini')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-blue-50 text-blue-700 transition flex items-center gap-1"><Bot size={14}/> Gemini AI</button>
                <button onClick={() => addNode('scraper')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-amber-50 text-amber-700 transition flex items-center gap-1"><Globe size={14}/> Web Scraper</button>
                <button onClick={() => addNode('agentic_loop')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-purple-50 text-purple-700 transition flex items-center gap-1"><Repeat size={14}/> Agent Loop</button>
            </div>
        )}

        {/* Workspace Content Area */}
        <div className="flex-1 relative w-full h-full">
          {activeTab === "editor" ? (
            <>
             <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onNodeClick={onNodeClick}
                onPaneClick={onPaneClick}
                nodeTypes={nodeTypes}
                fitView
                className="bg-slate-950"
             >
                <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#334155" />
                <Controls className="bg-slate-800 border-slate-700 !fill-slate-800" />
             </ReactFlow>

             {isPlaybackMode && (
                 <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-rose-500 text-white px-6 py-2 rounded-full font-bold shadow-lg shadow-rose-500/30 z-40 flex items-center gap-2 border-2 border-rose-400">
                    <CheckCircle2 size={18} /> PLAYBACK MODE ACTIVE (Read-Only)
                    <button onClick={() => {
                        setPlaybackRun(null);
                        setNodes(nds => nds.map(n => ({...n, data: {...n.data, executionStatus: 'idle'}})));
                    }} className="ml-4 bg-white text-rose-600 px-3 py-1 rounded text-xs hover:bg-rose-50">Exit Playback</button>
                 </div>
             )}

             {/* Floating Execution Log Panel */}
             {logs.length > 0 && (
                 <div className="absolute bottom-6 left-6 w-[400px] h-[300px] bg-slate-900 border border-slate-700 rounded-xl shadow-[0_10px_40px_-10px_rgba(0,0,0,0.8)] z-30 flex flex-col overflow-hidden text-slate-300 transition-all">
                     <div className="px-4 py-3 border-b border-slate-800 bg-slate-950 flex justify-between items-center shrink-0">
                         <div className="font-semibold text-sm flex items-center gap-2">
                             {isExecuting ? <Loader2 size={14} className="animate-spin text-blue-500"/> : <CheckCircle2 size={14} className="text-emerald-500"/>}
                             Execution Telemetry
                         </div>
                         <button onClick={() => setLogs([])} className="text-slate-500 hover:text-slate-300 transition-colors">✕</button>
                     </div>
                     <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-xs">
                         {logs.map((log, i) => (
                             <div key={i} className="flex flex-col gap-1 border-b border-slate-800/50 pb-2 last:border-0">
                                 <span className={`font-bold uppercase tracking-wider ${
                                     log.status === 'Error' || log.status === 'Jules Error' ? 'text-rose-500' :
                                     log.status === 'Complete' || log.status === 'Workflow Finished' ? 'text-emerald-500' : 'text-blue-400'
                                 }`}>[{log.status}]</span>
                                 <span className="text-slate-400 whitespace-pre-wrap">{log.message}</span>
                             </div>
                         ))}
                         <div ref={logsEndRef} />
                     </div>
                 </div>
             )}

             {/* Properties Panel */}
             {selectedNodeId && (
               <div className="absolute top-0 right-0 w-[300px] h-full bg-white border-l border-slate-200 shadow-xl z-20 flex flex-col">
                 <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
                   <h3 className="font-bold text-slate-800">Node Properties</h3>
                   <button onClick={() => setSelectedNodeId(null)} className="text-slate-400 hover:text-slate-600">✕</button>
                 </div>
                 <div className="p-4 flex-1 overflow-y-auto">
                   {nodes.filter(n => n.id === selectedNodeId).map(node => (
                     <div key={node.id} className="space-y-4">
                       <div>
                         <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Node Type</label>
                         <div className="px-3 py-1.5 bg-slate-100 rounded text-sm text-slate-700 font-medium capitalize">{node.type?.replace('_', ' ')}</div>
                       </div>

                       {node.type === 'gemini' && (
                         <div>
                           <div className="flex justify-between items-center mb-1">
                             <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">Prompt</label>

                             <div className="relative group">
                               <button className="text-xs bg-slate-200 hover:bg-blue-100 text-blue-700 px-2 py-0.5 rounded transition">
                                 + Insert Variable
                               </button>
                               <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-slate-200 rounded-md shadow-xl opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto transition-opacity z-50 p-1 flex flex-col gap-1 max-h-48 overflow-y-auto">
                                 {nodes.filter(n => n.id !== node.id).map(n => (
                                   <button
                                     key={n.id}
                                     onClick={() => {
                                       const newVal = (node.data.prompt || '') + ` {{${n.id}}}`;
                                       updateNodeData(node.id, { prompt: newVal });
                                     }}
                                     className="text-left text-xs px-2 py-1.5 hover:bg-slate-100 rounded text-slate-700 truncate"
                                   >
                                     <span className="font-semibold">{n.type}</span>: {String(n.data.prompt || n.data.url || 'Node')}
                                   </button>
                                 ))}
                                 {nodes.length <= 1 && <div className="text-xs text-slate-400 p-2 text-center">No other nodes</div>}
                               </div>
                             </div>
                           </div>
                           <textarea
                             className="w-full h-48 px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                             value={node.data.prompt as string || ''}
                             onChange={(e) => updateNodeData(node.id, { prompt: e.target.value })}
                             disabled={isPlaybackMode}
                             placeholder="Enter AI prompt... Use {{NODE_ID}} to inject previous outputs."
                           />
                         </div>
                       )}

                       {node.type === 'scraper' && (
                         <div>
                           <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Target URL</label>
                           <input
                             type="text"
                             className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                             value={node.data.url as string || ''}
                             onChange={(e) => updateNodeData(node.id, { url: e.target.value })}
                               disabled={isPlaybackMode}
                             placeholder="https://..."
                           />
                         </div>
                       )}

                       {node.type === 'agentic_loop' && (
                         <>
                           <div>
                             <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Repository/Target URL</label>
                             <input
                               type="text"
                               className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                               value={node.data.url as string || ''}
                               onChange={(e) => updateNodeData(node.id, { url: e.target.value })}
                               disabled={isPlaybackMode}
                               placeholder="https://github.com/..."
                             />
                           </div>
                           <div>
                             <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Max Iterations</label>
                             <input
                               type="number"
                               min="1"
                               max="10"
                               className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                               value={node.data.max_iterations as number || 3}
                               onChange={(e) => updateNodeData(node.id, { max_iterations: parseInt(e.target.value, 10) || 3 })}
                               disabled={isPlaybackMode}
                             />
                           </div>
                           <div>
                             <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Context Reset Frequency</label>
                             <input
                               type="number"
                               min="1"
                               max="10"
                               className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                               value={node.data.reset_threshold as number || 3}
                               onChange={(e) => updateNodeData(node.id, { reset_threshold: parseInt(e.target.value, 10) || 3 })}
                               disabled={isPlaybackMode}
                             />
                             <p className="text-[10px] text-slate-500 mt-1">Clears DOM every N steps to prevent crashing.</p>
                           </div>
                         </>
                       )}

                       {node.type === 'trigger' && (
                         <div className="text-sm text-slate-500 italic">
                           Trigger nodes are the starting point of the execution graph. No configuration needed.
                         </div>
                       )}

                       {isPlaybackMode && playbackRun && playbackRun.parsedResults && playbackRun.parsedResults[node.id] && (
                           <div className="mt-6 border-t border-slate-200 pt-4">
                               <label className="block text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-2">Snapshot Output Result</label>
                               <div className="p-3 bg-slate-900 text-slate-300 text-xs rounded-md overflow-x-auto whitespace-pre-wrap font-mono max-h-96 overflow-y-auto">
                                   {playbackRun.parsedResults[node.id]}
                               </div>
                           </div>
                       )}
                     </div>
                   ))}
                 </div>
               </div>
             )}
            </>
          ) : activeTab === "runs" ? (
            <div className="w-full max-w-5xl mx-auto p-8">
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
                    <h3 className="font-bold text-slate-800 text-lg flex items-center gap-2"><Bot className="text-blue-500"/> Execution History</h3>
                </div>
                <div className="divide-y divide-slate-100">
                    {runHistory.length === 0 ? (
                        <div className="p-8 text-center text-slate-500">No runs recorded for this workspace yet. Execute the canvas to create a snapshot.</div>
                    ) : runHistory.map(run => (
                        <div key={run.id} className="p-6 flex items-center justify-between hover:bg-slate-50 transition">
                            <div>
                                <div className="flex items-center gap-3 mb-1">
                                    <span className={`px-2.5 py-0.5 rounded text-xs font-bold ${run.status === 'Workflow Finished' || run.status === 'Complete' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                                        {run.status === 'Workflow Finished' ? 'SUCCESS' : run.status.toUpperCase()}
                                    </span>
                                    <span className="text-sm font-medium text-slate-700">{new Date(run.createdAt).toLocaleString()}</span>
                                </div>
                                <div className="text-xs text-slate-500 font-mono">Run ID: {run.id}</div>
                            </div>
                            <button
                                onClick={() => {
                                    try {
                                        const parsedResults = JSON.parse(run.results || "{}");
                                        setPlaybackRun({ ...run, parsedResults });
                                        // Update nodes to show success state for all nodes that have a result
                                        setNodes(nds => nds.map(n => {
                                            if (parsedResults[n.id]) {
                                                return { ...n, data: { ...n.data, executionStatus: 'success' } };
                                            }
                                            return n;
                                        }));
                                        setActiveTab('editor');
                                    } catch(e) {
                                        alert("Failed to parse run results snapshot.");
                                    }
                                }}
                                className="px-4 py-2 bg-slate-900 text-white rounded text-sm font-medium hover:bg-slate-800 shadow-sm transition flex items-center gap-2"
                            >
                                <Play size={14} /> View Snapshot
                            </button>
                        </div>
                    ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="hidden"></div>
          )}
        </div>
      </main>
    </div>
  );
}
