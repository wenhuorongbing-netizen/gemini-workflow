"use client";
import { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import { Play, Bot, ArrowLeft, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { Node, Edge } from '@xyflow/react';

// Similar compile logic to page.tsx, adapted for headless running
const compileNodesToSteps = (nodes: Node[], edges: Edge[]) => {
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
  const nodeOrder: string[] = [];

  const addStep = (nodeId: string) => {
    if (nodeOrder.includes(nodeId)) return;
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;

    const incomingEdges = edges.filter(e => e.target === nodeId);
    for (const edge of incomingEdges) {
      addStep(edge.source);
    }

    const stepData: any = { id: node.id, type: node.type, ...node.data };

    // Convert array format to backend expected format if needed
    if (node.type === 'gemini') {
        stepData.type = 'gemini';
        stepData.profile_id = node.data.profileId || '1';
    } else if (node.type === 'agentLoop') {
        stepData.type = 'agentic_loop';
    } else if (node.type === 'fileNode') {
        stepData.type = 'file_reader';
    }

    steps.push(stepData);
    nodeOrder.push(node.id);
  };

  const leafNodes = nodes.filter(n => !edges.find(e => e.source === n.id));
  leafNodes.forEach(leaf => addStep(leaf.id));

  nodes.filter(n => !nodeOrder.includes(n.id)).forEach(unconnected => addStep(unconnected.id));

  return { steps, nodeOrder };
};

export default function MagicFormApp() {
    const params = useParams();
    const workflowId = params.workflowId as string;

    const [workflow, setWorkflow] = useState<any>(null);
    const [nodes, setNodes] = useState<Node[]>([]);
    const [edges, setEdges] = useState<Edge[]>([]);
    const [inputs, setInputs] = useState<any[]>([]);
    const [inputValues, setInputValues] = useState<Record<string, string>>({});

    const [isExecuting, setIsExecuting] = useState(false);
    const [logs, setLogs] = useState<any[]>([]);
    const logsEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    useEffect(() => {
        if (!workflowId) return;

        const fetchWf = async () => {
            try {
                // We reuse the workspace fetch by just filtering the workspace's workflows.
                // In a true prod app we'd have a specific GET /api/workflows/[id]
                const res = await fetch('/api/workspaces');
                const wss = await res.json();
                let foundWf = null;
                for (const ws of wss) {
                    const wf = ws.workflows?.find((w: any) => w.id === workflowId);
                    if (wf) { foundWf = wf; break; }
                }

                if (foundWf) {
                    setWorkflow(foundWf);
                    setNodes(JSON.parse(foundWf.nodes || "[]"));
                    setEdges(JSON.parse(foundWf.edges || "[]"));
                    const parsedInputs = JSON.parse(foundWf.publishedInputs || "[]");
                    setInputs(parsedInputs);

                    const initialVals: Record<string, string> = {};
                    parsedInputs.forEach((i: any) => initialVals[i.id] = "");
                    setInputValues(initialVals);
                }
            } catch(e) { console.error(e); }
        };
        fetchWf();
    }, [workflowId]);

    const handleRun = async () => {
        // Apply user inputs to nodes
        const updatedNodes = nodes.map(n => {
            const override = inputValues[n.id];
            if (override !== undefined && override !== "") {
                if (n.type === 'scraper' || n.type === 'agentic_loop') {
                    return { ...n, data: { ...n.data, url: override }};
                }
                if (n.type === 'gemini') {
                    return { ...n, data: { ...n.data, prompt: override }};
                }
            }
            return n;
        });

        let compiledData;
        try {
            compiledData = compileNodesToSteps(updatedNodes, edges);
        } catch (err: any) {
            alert(err.message || "Failed to compile workflow");
            return;
        }

        setLogs([]);
        setIsExecuting(true);

        try {
            const response = await fetch("http://127.0.0.1:8000/execute", {
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

            const eventSource = new EventSource(`http://127.0.0.1:8000/api/logs/${taskId}`);

            eventSource.onmessage = async (event) => {
                if (event.data === "__DONE__") {
                    eventSource.close();
                    setIsExecuting(false);
                    return;
                }
                try {
                    const parsed = JSON.parse(event.data);
                    if (parsed.error) {
                        setLogs(prev => [...prev, { status: "Error", message: parsed.error }]);
                        setIsExecuting(false);
                        eventSource.close();
                        return;
                    }
                    if (parsed.status) {
                        setLogs(prev => [...prev, { status: parsed.status, message: parsed.message || parsed.result || "" }]);
                    }
                    if (parsed.status === 'Workflow Finished' || parsed.status === 'Error' || parsed.status === 'Canceled') {
                        setIsExecuting(false);
                        eventSource.close();
                    }
                } catch(e) {}
            };

            eventSource.onerror = () => {
                setIsExecuting(false);
                eventSource.close();
            };
        } catch (e: any) {
            alert(e.message);
            setIsExecuting(false);
        }
    };

    if (!workflow) return <div className="h-screen flex items-center justify-center text-slate-500">Loading App...</div>;

    return (
        <div className="min-h-screen bg-slate-50 flex flex-col items-center py-12 px-4">
            <div className="max-w-2xl w-full">
                <a href="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-blue-600 mb-8 font-medium transition-colors">
                    <ArrowLeft size={16}/> Back to App Store
                </a>

                <div className="bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
                    <div className="bg-blue-600 px-8 py-10 text-white text-center">
                        <div className="bg-white/20 w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 backdrop-blur-sm">
                            <Bot size={32} />
                        </div>
                        <h1 className="text-3xl font-extrabold tracking-tight mb-2">AI Automation</h1>
                        <p className="text-blue-100 opacity-90">Fill out the required parameters below to launch.</p>
                    </div>

                    <div className="p-8">
                        {inputs.length === 0 ? (
                            <p className="text-slate-500 text-center mb-8">This app requires no inputs. Ready to run.</p>
                        ) : (
                            <div className="space-y-6 mb-8">
                                {inputs.map((inp, idx) => (
                                    <div key={idx}>
                                        <label className="block text-sm font-bold text-slate-700 mb-2">{inp.label}</label>
                                        <textarea
                                            value={inputValues[inp.id]}
                                            onChange={e => setInputValues({...inputValues, [inp.id]: e.target.value})}
                                            className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all resize-none h-24 text-slate-800"
                                            placeholder="Enter value here..."
                                        />
                                    </div>
                                ))}
                            </div>
                        )}

                        <button
                            onClick={handleRun}
                            disabled={isExecuting}
                            className={`w-full py-4 rounded-xl font-bold text-lg flex items-center justify-center gap-2 transition-all shadow-lg ${isExecuting ? 'bg-blue-400 text-white cursor-not-allowed shadow-none' : 'bg-blue-600 hover:bg-blue-700 hover:-translate-y-1 text-white shadow-blue-600/30'}`}
                        >
                            {isExecuting ? <Loader2 size={24} className="animate-spin" /> : <Play size={24} />}
                            {isExecuting ? 'Running Automation...' : '▶ Run Automation'}
                        </button>
                    </div>
                </div>

                {/* Floating Log Terminal (Mimicking main app but simpler) */}
                {(logs.length > 0 || isExecuting) && (
                    <div className="mt-8 bg-slate-900 rounded-xl shadow-2xl border border-slate-800 overflow-hidden font-mono text-sm">
                         <div className="bg-slate-950 px-4 py-3 flex items-center justify-between border-b border-slate-800">
                             <span className="text-slate-300 font-bold flex items-center gap-2">
                                 {isExecuting ? <Loader2 size={16} className="text-blue-500 animate-spin"/> : <CheckCircle2 size={16} className="text-emerald-500"/>}
                                 Live Execution Terminal
                             </span>
                         </div>
                         <div className="p-4 h-64 overflow-y-auto space-y-2">
                             {logs.map((log, i) => (
                                 <div key={i} className={`pb-2 border-b border-slate-800/50 last:border-0 ${log.status === 'Error' ? 'text-rose-400' : 'text-slate-400'}`}>
                                    <span className={`font-bold mr-2 ${log.status === 'Error' ? 'text-rose-500' : 'text-blue-400'}`}>[{log.status}]</span>
                                    {log.message}
                                 </div>
                             ))}
                             <div ref={logsEndRef}/>
                         </div>
                    </div>
                )}
            </div>
        </div>
    );
}
