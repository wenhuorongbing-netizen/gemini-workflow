"use client";
import { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import { Play, Bot, ArrowLeft, Loader2, CheckCircle2, AlertCircle, UploadCloud, Copy, Download } from 'lucide-react';
import { Node, Edge } from '@xyflow/react';
import Papa from 'papaparse';

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

    const [isBatchMode, setIsBatchMode] = useState(false);
    const [csvData, setCsvData] = useState<any[]>([]);
    const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
    const [columnMapping, setColumnMapping] = useState<Record<string, string>>({}); // workflowInputId -> csvHeader
    const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 });

    const [isExecuting, setIsExecuting] = useState(false);
    const [logs, setLogs] = useState<any[]>([]);
    const [recentRuns, setRecentRuns] = useState<any[]>([]);
    const logsEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    const [currentUserId, setCurrentUserId] = useState<string>("user1");

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
                const res = await fetch('/api/workspaces', { headers: { 'x-user-id': currentUserId } });
                const wss = await res.json();
                let foundWf = null;
                for (const ws of wss) {
                    const wf = ws.workflows?.find((w: any) => w.id === workflowId);
                    if (wf) {
                        foundWf = { ...wf, workspace: ws };
                        break;
                    }
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

                    fetchRecentRuns(foundWf.id);
                }
            } catch(e) { console.error(e); }
        };

        const fetchRecentRuns = async (wid: string) => {
            try {
                const rRes = await fetch(`/api/runs/app/${wid}`, { headers: { 'x-user-id': currentUserId } });
                if (rRes.ok) {
                    setRecentRuns(await rRes.json());
                }
            } catch(e) {}
        };
        fetchWf();
    }, [workflowId]);

        const executeSingleRun = async (overrideValues: Record<string, string>) => {
        return new Promise((resolve, reject) => {
            const updatedNodes = nodes.map(n => {
                const override = overrideValues[n.id];
                if (override !== undefined && override !== "") {
                    if (n.type === 'scraper' || n.type === 'agentic_loop' || n.type === 'webhook') {
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
                reject(err.message || "Failed to compile workflow");
                return;
            }

            fetch("http://127.0.0.1:5000/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ steps: compiledData.steps, nodeOrder: compiledData.nodeOrder, user_id: currentUserId }),
            }).then(async (response) => {
                if (!response.ok) {
                    const errData = await response.json();
                    reject(new Error(errData.error || "Failed to start execution"));
                    return;
                }

                const data = await response.json();
                const taskId = data.task_id;

                const eventSource = new EventSource(`http://127.0.0.1:5000/api/logs/${taskId}`);

                eventSource.onmessage = async (event) => {
                    if (event.data === "__DONE__") {
                        eventSource.close();
                        resolve(true);
                        return;
                    }
                    try {
                        const parsed = JSON.parse(event.data);
                        if (parsed.error) {
                            setLogs(prev => [...prev, { status: "Error", message: parsed.error }]);
                            eventSource.close();
                            resolve(false);
                            return;
                        }
                        if (parsed.status) {
                            setLogs(prev => [...prev, { status: parsed.status, message: parsed.message || parsed.result || "" }]);
                        }
                        if (parsed.status === 'Workflow Finished' || parsed.status === 'Error' || parsed.status === 'Canceled') {
                            eventSource.close();
                            resolve(parsed.status === 'Workflow Finished');
                        }
                    } catch(e) {}
                };

                eventSource.onerror = () => {
                    eventSource.close();
                    resolve(false);
                };
            }).catch(reject);
        });
    };

    const handleBatchRun = async () => {
        if (csvData.length === 0) { alert("Please upload a valid CSV first."); return; }

        setIsExecuting(true);
        setLogs([]);
        setBatchProgress({ current: 0, total: csvData.length });

        for (let i = 0; i < csvData.length; i++) {
            const row = csvData[i];

            // Build override values for this specific row based on mapping
            const rowOverrides: Record<string, string> = {};
            for (const inputId of Object.keys(columnMapping)) {
                const headerName = columnMapping[inputId];
                if (headerName && row[headerName] !== undefined) {
                    rowOverrides[inputId] = row[headerName];
                }
            }

            setLogs(prev => [...prev, { status: "Batch", message: `--- Starting Row ${i + 1} of ${csvData.length} ---` }]);
            setBatchProgress({ current: i + 1, total: csvData.length });

            try {
                const success = await executeSingleRun(rowOverrides);
                if (!success) {
                    setLogs(prev => [...prev, { status: "Batch Error", message: `Row ${i + 1} Failed. Continuing to next row...` }]);
                }
            } catch (err: any) {
                setLogs(prev => [...prev, { status: "Batch Error", message: `Row ${i + 1} Threw Exception: ${err.message}. Continuing...` }]);
            }
        }

        setLogs(prev => [...prev, { status: "Batch Complete", message: "--- All rows processed ---" }]);
        setIsExecuting(false);
    };

    const handleRun = async () => {
        if (isBatchMode) {
            await handleBatchRun();
            return;
        }

        setIsExecuting(true);
        setLogs([]);
        try {
            await executeSingleRun(inputValues);
        } catch (e: any) {
            alert(e.message);
        }
        setIsExecuting(false);
    };

    /* Legacy Handle Run implementation replaced above */
if (!workflow) return <div className="h-screen flex items-center justify-center text-slate-500">Loading App...</div>;

    return (
        <div className="min-h-screen bg-slate-50 flex flex-col items-center py-12 px-4">
            <div className="max-w-2xl w-full">
                <a href="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-blue-600 mb-8 font-medium transition-colors">
                    <ArrowLeft size={16}/> Back to App Store
                </a>

                <div className="bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
                    <div className="bg-blue-600 px-8 py-10 text-white text-center">
                        <div className="bg-white/20 w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 backdrop-blur-sm relative">
                            <Bot size={32} />
                            {workflow?.workspace?.quota !== undefined && (
                                <div className="absolute -right-16 -top-4 bg-amber-500 text-white text-xs font-bold px-2 py-1 rounded-full shadow-lg border-2 border-amber-400 whitespace-nowrap z-10">
                                    ⚡ Tokens left: {workflow.workspace.quota}
                                </div>
                            )}
                        </div>
                        <h1 className="text-3xl font-extrabold tracking-tight mb-2">AI Automation</h1>
                        <p className="text-blue-100 opacity-90">Fill out the required parameters below to launch.</p>
                    </div>

                    <div className="p-8">
                        {/* Toggle Batch Mode */}
                        <div className="flex justify-center mb-8 bg-slate-100 p-1 rounded-xl max-w-sm mx-auto shadow-inner">
                            <button onClick={() => setIsBatchMode(false)} className={`flex-1 py-2 text-sm font-bold rounded-lg transition-all ${!isBatchMode ? 'bg-white shadow text-blue-600' : 'text-slate-500 hover:text-slate-700'}`}>
                                Single Run
                            </button>
                            <button onClick={() => setIsBatchMode(true)} className={`flex-1 py-2 text-sm font-bold rounded-lg transition-all ${isBatchMode ? 'bg-white shadow text-blue-600' : 'text-slate-500 hover:text-slate-700'}`}>
                                Batch CSV Run
                            </button>
                        </div>

                        {isBatchMode ? (
                            <div className="space-y-6 mb-8">
                                <label className="block text-sm font-bold text-slate-700 mb-2">Upload CSV Dataset</label>
                                <div className="w-full px-4 py-8 bg-slate-50 border-2 border-dashed border-slate-300 rounded-xl hover:bg-slate-100 hover:border-blue-400 transition-all text-center">
                                    <input type="file" accept=".csv" className="hidden" id="csv-upload" onChange={(e) => {
                                        const file = e.target.files?.[0];
                                        if (file) {
                                            Papa.parse(file, {
                                                header: true,
                                                skipEmptyLines: "greedy",
                                                complete: (results) => {
                                                    if (results.data && results.data.length > 0) {
                                                        // Filter out rows where every column value is empty or just whitespace
                                                        const cleanData = results.data.filter((row: any) =>
                                                            Object.values(row).some((val: any) => typeof val === 'string' && val.trim() !== '')
                                                        );
                                                        setCsvData(cleanData);
                                                        if(cleanData.length > 0) {
                                                            setCsvHeaders(Object.keys(cleanData[0] as object));
                                                        }
                                                    }
                                                },
                                                error: (err) => alert(err.message)
                                            });
                                        }
                                    }} />
                                    <label htmlFor="csv-upload" className="cursor-pointer flex flex-col items-center justify-center text-slate-500">
                                        <UploadCloud size={32} className="mb-2 text-blue-500"/>
                                        <span className="font-medium text-slate-700">{csvData.length > 0 ? `${csvData.length} Rows Loaded` : 'Click to Upload CSV'}</span>
                                    </label>
                                </div>

                                {csvHeaders.length > 0 && inputs.length > 0 && (
                                    <div className="mt-6">
                                        <h4 className="font-bold text-slate-700 mb-3">Map CSV Columns to Inputs</h4>
                                        <div className="space-y-3 bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
                                            {inputs.map((inp, idx) => (
                                                <div key={idx} className="flex items-center justify-between gap-4">
                                                    <span className="text-sm font-bold text-slate-600">{inp.label}</span>
                                                    <select
                                                        className="px-3 py-2 bg-slate-50 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                                                        value={columnMapping[inp.id] || ""}
                                                        onChange={(e) => setColumnMapping({...columnMapping, [inp.id]: e.target.value})}
                                                    >
                                                        <option value="">-- Select Column --</option>
                                                        {csvHeaders.map(h => <option key={h} value={h}>{h}</option>)}
                                                    </select>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {isExecuting && batchProgress.total > 0 && (
                                    <div className="w-full mt-4">
                                        <div className="flex justify-between text-xs text-slate-500 font-bold mb-1">
                                            <span>Batch Progress</span>
                                            <span>{batchProgress.current} / {batchProgress.total}</span>
                                        </div>
                                        <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                                            <div className="h-full bg-blue-500 transition-all duration-300" style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}></div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="space-y-6 mb-8">
                                {inputs.length === 0 ? (
                                    <p className="text-slate-500 text-center mb-8">This app requires no inputs. Ready to run.</p>
                                ) : (
                                    inputs.map((inp, idx) => (
                                        <div key={idx}>
                                            <label className="block text-sm font-bold text-slate-700 mb-2">{inp.label}</label>
                                            <textarea
                                                value={inputValues[inp.id] || ""}
                                                onChange={e => setInputValues({...inputValues, [inp.id]: e.target.value})}
                                                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all resize-none h-24 text-slate-800 shadow-inner"
                                                placeholder="Enter value here..."
                                            />
                                        </div>
                                    ))
                                )}
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

                {recentRuns.length > 0 && !isExecuting && (
                    <div className="mt-8 bg-white rounded-xl shadow-md border border-slate-200 overflow-hidden">
                         <div className="bg-slate-50 px-6 py-4 border-b border-slate-200">
                             <h3 className="font-bold text-slate-700">Recent Outputs</h3>
                         </div>
                         <div className="divide-y divide-slate-100">
                             {recentRuns.map(run => {
                                 let finalOutput = "No results recorded.";
                                 try {
                                     const results = JSON.parse(run.results);
                                     const keys = Object.keys(results);
                                     if (keys.length > 0) finalOutput = results[keys[keys.length - 1]];
                                 } catch(e) {
                                     finalOutput = "Could not parse results.";
                                 }

                                 return (
                                 <div key={run.id} className="p-6">
                                     <div className="flex justify-between items-center mb-4">
                                         <div className="flex items-center gap-3">
                                            <span className={`text-xs font-bold px-2 py-1 rounded ${run.status === 'Workflow Finished' || run.status === 'Complete' ? 'bg-emerald-100 text-emerald-700' : run.status === 'PENDING_APPROVAL' ? 'bg-amber-100 text-amber-700' : 'bg-rose-100 text-rose-700'}`}>
                                                {run.status === 'Workflow Finished' ? 'Success' : run.status === 'PENDING_APPROVAL' ? 'Needs Approval' : 'Failed'}
                                            </span>
                                            <span className="text-xs text-slate-400 font-mono">
                                                {new Date(run.createdAt).toLocaleString()}
                                            </span>
                                         </div>
                                         <div className="flex gap-2">
                                            <button
                                                onClick={() => {
                                                    navigator.clipboard.writeText(finalOutput);
                                                    alert("Copied to clipboard!");
                                                }}
                                                className="text-[10px] flex items-center gap-1 bg-white border border-slate-200 text-slate-600 hover:text-blue-600 hover:border-blue-300 px-2 py-1 rounded transition shadow-sm"
                                            >
                                                <Copy size={12}/> Copy Markdown
                                            </button>
                                            <button
                                                onClick={() => {
                                                    const blob = new Blob([finalOutput], { type: "text/plain" });
                                                    const url = URL.createObjectURL(blob);
                                                    const a = document.createElement('a');
                                                    a.href = url;
                                                    a.download = `Export_${run.id.substring(0,6)}.txt`;
                                                    a.click();
                                                    URL.revokeObjectURL(url);
                                                }}
                                                className="text-[10px] flex items-center gap-1 bg-white border border-slate-200 text-slate-600 hover:text-emerald-600 hover:border-emerald-300 px-2 py-1 rounded transition shadow-sm"
                                            >
                                                <Download size={12}/> Download .txt
                                            </button>
                                         </div>
                                     </div>
                                     <div className="text-sm text-slate-600 bg-slate-50 p-4 rounded-lg font-mono overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
                                         {finalOutput}
                                     </div>

                                     {run.status === 'PENDING_APPROVAL' && (
                                         <div className="mt-4 flex gap-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                                            <div className="flex-1">
                                                <p className="text-xs font-bold text-amber-800 mb-2">HITL Approval Required</p>
                                                <p className="text-xs text-amber-700">The workflow has paused at this node. Review the output above before proceeding.</p>
                                            </div>
                                            <div className="flex gap-2">
                                                <button onClick={async () => {
                                                    const res = await fetch('/api/runs/resume', {
                                                        method: 'POST',
                                                        headers: { 'Content-Type': 'application/json', 'x-user-id': currentUserId },
                                                        body: JSON.stringify({ run_id: run.id, action: 'reject' })
                                                    });
                                                }} className="px-4 py-2 bg-white text-rose-600 border border-rose-200 hover:bg-rose-50 rounded font-bold text-xs shadow-sm">
                                                    ❌ Reject
                                                </button>
                                                <button onClick={async () => {
                                                    setIsExecuting(true);
                                                    const res = await fetch('/api/runs/resume', {
                                                        method: 'POST',
                                                        headers: { 'Content-Type': 'application/json', 'x-user-id': currentUserId },
                                                        body: JSON.stringify({ run_id: run.id, action: 'approve', text: finalOutput })
                                                    });
                                                    if(res.ok) {
                                                        const data = await res.json();
                                                        const eventSource = new EventSource(`http://127.0.0.1:5000/api/logs/${data.task_id}`);
                                                        eventSource.onmessage = async (event) => {
                                                            if (event.data === "__DONE__") {
                                                                eventSource.close();
                                                                setIsExecuting(false);
                                                                return;
                                                            }
                                                            try {
                                                                const parsed = JSON.parse(event.data);
                                                                if (parsed.status) setLogs(prev => [...prev, { status: parsed.status, message: parsed.message || parsed.result || "" }]);
                                                                if (parsed.status === 'Workflow Finished' || parsed.status === 'Error' || parsed.status === 'Canceled') {
                                                                    setIsExecuting(false);
                                                                    eventSource.close();
                                                                }
                                                            } catch(e){}
                                                        };
                                                    } else {
                                                        setIsExecuting(false);
                                                        alert("Failed to resume.");
                                                    }
                                                }} className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded font-bold text-xs shadow-md">
                                                    ✅ Approve & Continue
                                                </button>
                                            </div>
                                         </div>
                                     )}
                                 </div>
                             )})}
                         </div>
                    </div>
                )}
            </div>
        </div>
    );
}
