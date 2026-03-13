"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
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
import { Play, Bot, Globe, Repeat, FileJson } from "lucide-react";

interface Workspace {
  id: string;
  name: string;
  steps?: any[];
}

// --- Custom Nodes ---

const BaseNode = ({ icon: Icon, title, content, bgColor, borderColor }: any) => (
  <div className={`w-[280px] rounded-lg shadow-lg border-2 ${borderColor} ${bgColor} overflow-hidden text-slate-50 flex flex-col`}>
    <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-slate-300" />
    <div className={`px-4 py-2 border-b ${borderColor} flex items-center gap-2 font-semibold tracking-wide bg-opacity-20 bg-black`}>
      <Icon size={18} />
      <span>{title}</span>
    </div>
    <div className="p-4 flex-1 text-sm bg-slate-900/50">
      <div className="text-slate-300 truncate">{content}</div>
    </div>
    <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-slate-300" />
  </div>
);

const TriggerNode = ({ data }: any) => (
  <BaseNode icon={Play} title="Trigger" content={data.label || "Manual Run"} bgColor="bg-emerald-900" borderColor="border-emerald-700" />
);

const GeminiNode = ({ data }: any) => (
  <BaseNode icon={Bot} title="Gemini AI" content={data.prompt || "Enter prompt..."} bgColor="bg-blue-900" borderColor="border-blue-700" />
);

const ScraperNode = ({ data }: any) => (
  <BaseNode icon={Globe} title="Web Scraper" content={data.url || "https://..."} bgColor="bg-amber-900" borderColor="border-amber-700" />
);

const AgentLoopNode = ({ data }: any) => (
  <BaseNode icon={Repeat} title="Agentic Loop" content={`Target: ${data.url || "None"}`} bgColor="bg-purple-900" borderColor="border-purple-700" />
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
    return actionNodes.map(n => {
        const base = {
            type: n.type === 'gemini' ? 'standard' : n.type,
            prompt: n.data.prompt || n.data.url || '',
            new_chat: n.data.new_chat || false,
            show_result: true,
        };

        if (n.type === 'agentic_loop') {
            return {
                ...base,
                chat_url: n.data.url || '',
                max_iterations: n.data.max_iterations || 3
            };
        }
        return base;
    });
}

// --- Main App Shell ---

export default function AppShell() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null);
  const [activeTab, setActiveTab] = useState<"editor" | "dashboard">("editor");
  const [isLoading, setIsLoading] = useState(true);

  // React Flow State
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);

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
      // Mocked for Next.js shell disconnected from backend for visual testing
      // A real integration would fetch from actual FastAPI
      const mockWorkspaces = [
        { id: "1", name: "Content Pipeline", steps: [] },
        { id: "2", name: "Agentic Researcher", steps: [] }
      ];
      setWorkspaces(mockWorkspaces);
      if (mockWorkspaces.length > 0 && !selectedWorkspace) {
        setSelectedWorkspace(mockWorkspaces[0]);
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

  const handleCompile = () => {
      const compiledSteps = compileNodesToSteps(nodes, edges);
      console.log("Compiled JSON Payload for app.py:", compiledSteps);
      alert("Compiled Steps Payload logged to console!\\n\\n" + JSON.stringify(compiledSteps, null, 2));
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
                onClick={() => setActiveTab("dashboard")}
                className={`px-4 py-1.5 text-sm font-semibold rounded-md transition-all ${
                  activeTab === "dashboard"
                    ? "bg-white text-blue-600 shadow-sm border border-slate-200"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                Dashboard
              </button>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={handleCompile}
              className="bg-slate-800 hover:bg-slate-900 text-white px-4 py-2 rounded-md font-medium text-sm transition-colors shadow-sm flex items-center gap-2"
            >
              <FileJson size={16} /> Compile JSON
            </button>
            <button
              className="bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2 rounded-md font-bold text-sm transition-colors shadow-md shadow-emerald-900/20 flex items-center gap-2"
              disabled={!selectedWorkspace}
            >
              <Play size={16} /> Run Canvas
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
             <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                nodeTypes={nodeTypes}
                fitView
                className="bg-slate-950"
             >
                <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#334155" />
                <Controls className="bg-slate-800 text-white border-slate-700 fill-white" />
             </ReactFlow>
          ) : (
            <div className="h-full flex flex-col items-center justify-center p-8">
              <div className="w-full max-w-4xl bg-white rounded-xl shadow-sm border border-slate-200 p-8 text-center h-[500px] flex flex-col items-center justify-center">
                 <h3 className="text-2xl font-bold text-slate-700 mb-2">Dashboard Analytics</h3>
                 <p className="text-slate-500">Execution results will appear here after running the canvas.</p>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
