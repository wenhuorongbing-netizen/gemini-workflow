"use client";

import { useState, useRef, useEffect } from "react";
import { Play, RotateCcw, GitBranch, GitMerge, Loader2, Eye } from "lucide-react";
import ReactMarkdown from "react-markdown";

export default function Cockpit() {
    const [prompt, setPrompt] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [isReviewing, setIsReviewing] = useState(false);
    const [targetRepo, setTargetRepo] = useState("");
    const [kbLinks, setKbLinks] = useState("");
    const [model, setModel] = useState("Pro");
    const [webhookUrl, setWebhookUrl] = useState("");
    const [isStarting, setIsStarting] = useState(false);
    const [attachment, setAttachment] = useState<string | null>(null);
    const [attachmentName, setAttachmentName] = useState<string | null>(null);

    const [activeBranch, setActiveBranch] = useState<string | null>(null);
    const [iteration, setIteration] = useState(1);
    const [maxIterations] = useState(5);
    const [logs, setLogs] = useState<{message: string, type: "info"|"action"|"error"|"review"|"ci"|"ci_failed"|"ci_success"|"preview"|"success"|"state_change"|"finished"|"radar"}[]>([]);
    const [queue, setQueue] = useState<any[]>([]);
    const [isRadarActive, setIsRadarActive] = useState(false);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [isUatPending, setIsUatPending] = useState(false);
    const [uatFeedback, setUatFeedback] = useState("");

    const [isMerging, setIsMerging] = useState(false);

    const fetchQueue = async () => {
        try {
            const res = await fetch("/api/devhouse/queue");
            if (res.ok) {
                const data = await res.json();
                setQueue(data.queue || []);
            }
        } catch(e) {}
    };

    useEffect(() => {
        fetchQueue();
        const interval = setInterval(fetchQueue, 5000);
        return () => clearInterval(interval);
    }, []);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [logs]);

    useEffect(() => {

        const eventSource = new EventSource('/api/devhouse/logs');
        eventSource.onmessage = (e) => {
            if(e.data === '"__DONE__"') {
                 setIsStarting(false);
                 return;
            }
            try {
                const data = JSON.parse(e.data);
                if (data.type) {
                     if (data.type === 'state_change') {
                          // Real-Time SSE Synchronization: Update Kanban queue item
                          setQueue(prevQueue => {
                              const activeTask = prevQueue.find(t => t.status === 'running');
                              if (activeTask) {
                                  return prevQueue.map(t => t.id === activeTask.id ? { ...t, agent_state: data.newState } : t);
                              }
                              return prevQueue;
                          });
                          return; // state_change doesn't need to be in the main logs feed unless we want it
                     }

                     setLogs(prev => [...prev, data]);
                     if (data.type === 'preview' && data.url) {
                         setPreviewUrl(data.url);
                         setIsUatPending(true);
                     }
                     if (data.type === 'success' || data.type === 'error') {
                         setIsUatPending(false);
                     }

                     // If finished, trigger a queue refetch to move it to Completed
                     if (data.type === 'finished' || data.type === 'error') {
                         setTimeout(fetchQueue, 1500);
                     }
                }
// Light state inference from logs (optional enhancement)
                if (data.message && data.message.includes("Iteration")) {
                    const match = data.message.match(/Iteration (\d+)\/(\d+)/);
                    if (match) {
                        setIteration(parseInt(match[1]));
                    }
                }
                if (data.message && data.message.includes("branch 'devhouse-")) {
                    const match = data.message.match(/branch '(devhouse-[^']+)'/);
                    if (match) {
                        setActiveBranch(match[1]);
                    }
                }
            } catch(err) {
                 console.error("SSE parse err", err, e.data);
            }
        };

        return () => eventSource.close();
    }, []);

    const addLog = (msg: string, type: "info"|"action"|"error"|"review"|"ci"|"ci_failed"|"ci_success"|"preview"|"success"|"state_change"|"finished"|"radar" = "info") => {
        setLogs(prev => [...prev, { message: msg, type }]);
    };

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setAttachmentName(file.name);
            const reader = new FileReader();
            reader.onloadend = () => {
                const base64String = reader.result as string;
                setAttachment(base64String);
            };
            reader.readAsDataURL(file);
        }
    };

    const handleAddToQueue = async () => {
        if (!prompt.trim()) {
            alert("Please enter an initial prompt.");
            return;
        }
        if (!targetRepo.trim()) {
            alert("Please enter a Target GitHub Repo URL (e.g. username/repo).");
            return;
        }
        setIsStarting(true);
        try {
            const res = await fetch("/api/devhouse/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt, target_repo: targetRepo.trim(), kbLinks, model, webhookUrl, attachments: attachment ? [attachment] : [] })
            });
            const data = await res.json();
            if (!res.ok || data.status !== "success") {
                addLog(`Failed to add to queue: ${data.error || data.message}`, "error");
            } else {
                setPrompt("");
                setTargetRepo("");
                setKbLinks("");
                setAttachment(null);
                setAttachmentName(null);
                setAttachment(null);
                setAttachmentName(null);
                fetchQueue();
            }
        } catch (error: any) {
            addLog(`Error connecting to backend: ${error.message}`, "error");
        } finally {
            setIsStarting(false);
        }
    };

    const handleUatDecision = async (approved: boolean) => {
        if (!approved && !uatFeedback.trim()) {
            alert("Please provide feedback for Jules on what needs to be fixed.");
            return;
        }

        try {
            await fetch("/api/devhouse/uat_response", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ approved, feedback: uatFeedback })
            });
            setIsUatPending(false);
            setPreviewUrl(null);
            setUatFeedback("");
        } catch(e) {
            console.error("Failed to send UAT response");
        }
    };

    const handleTriggerReview = async () => {
        if (!activeBranch) return;
        setIsReviewing(true);
        addLog(`Triggering code review for branch ${activeBranch}...`, "info");
        try {
            const res = await fetch("/api/devhouse/review", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ feature_branch: activeBranch })
            });
            const data = await res.json();

            if (res.status === 401) {
                 addLog(data.error || "Unauthorized", "error");
            } else if (res.ok && data.status === "success") {
                 addLog(data.review, "review");
            } else if (res.ok && data.status === "no_changes") {
                 addLog(`No changes found on branch ${activeBranch}.`, "info");
            } else {
                 addLog(`Review failed: ${data.message || data.error}`, "error");
            }
        } catch (error: any) {
            addLog(`Error during review: ${error.message}`, "error");
        } finally {
            setIsReviewing(false);
        }
    };

    const handleForceMerge = async () => {
        if (!activeBranch) return;
        setIsMerging(true);
        addLog(`Initiating force merge for branch ${activeBranch}...`, "action");
        try {
            const res = await fetch("/api/devhouse/merge", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ head_branch: activeBranch })
            });
            const data = await res.json();
            if (res.ok && data.status === "success") {
                addLog(`Merge successful: ${data.message}`, "action");
                setActiveBranch(null);
                setIteration(1);
            } else {
                addLog(`Merge failed: ${data.error || data.message}`, "error");
            }
        } catch (error: any) {
            addLog(`Error during merge: ${error.message}`, "error");
        } finally {
            setIsMerging(false);
        }
    };

    return (
        <div className="flex flex-col h-full w-full bg-slate-50 text-slate-800">
            <div className="flex flex-1 h-[60vh] min-h-[400px]">
            {/* Left: Control Panel */}
            <div className="w-1/3 p-6 border-r border-slate-200 flex flex-col gap-4 bg-white shadow-sm z-10">
                <h2 className="text-lg font-bold flex items-center gap-2 mb-2">
                    <Play className="text-blue-600" size={20} /> DevHouse Control Panel
                </h2>

                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Initial Prompt / Feature Request</label>
                    <textarea
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        placeholder="Describe the feature or bug you want Jules to build..."
                        className="w-full h-32 p-3 border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none text-sm"
                    />
                </div>

                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Knowledge Base Links (Comma Separated)</label>
                    <input
                        type="text"
                        value={kbLinks}
                        onChange={(e) => setKbLinks(e.target.value)}
                        placeholder="https://docs.example.com, https://github.com/..."
                        className="w-full p-2 border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
                    />
                </div>

                <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase mb-1 tracking-wider">
                        Target GitHub Repo URL *
                    </label>
                    <input
                        type="text"
                        value={targetRepo}
                        onChange={(e) => setTargetRepo(e.target.value)}
                        placeholder="e.g., username/repository"
                        className="w-full p-2 border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
                        required
                    />
                </div>

                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Model Selection</label>
                    <select
                        value={model}
                        onChange={(e) => setModel(e.target.value)}
                        className="w-full p-2 border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm bg-white"
                    >
                        <option value="Pro">Gemini 1.5 Pro (Best for logic)</option>
                        <option value="Flash">Gemini 1.5 Flash (Faster)</option>
                    </select>
                </div>

                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Webhook URL (Morning Report)</label>
                    <input
                        type="url"
                        value={webhookUrl}
                        onChange={(e) => setWebhookUrl(e.target.value)}
                        placeholder="https://hooks.zapier.com/..."
                        className="w-full p-2 border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
                    />
                </div>

                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">UI Mockup (PNG/JPG)</label>
                    <div className="flex items-center gap-2">
                        <label className="cursor-pointer bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold py-2 px-4 rounded shadow-sm text-sm border border-slate-300 flex-1 text-center transition-colors">
                            📎 {attachmentName || "Upload UI Mockup"}
                            <input type="file" accept="image/png, image/jpeg" className="hidden" onChange={handleFileUpload} />
                        </label>
                        {attachment && (
                            <button onClick={() => { setAttachment(null); setAttachmentName(null); }} className="text-red-500 hover:text-red-700 px-2" title="Remove attachment">
                                ✖
                            </button>
                        )}
                    </div>
                </div>

                <button
                    onClick={handleAddToQueue}
                    disabled={isStarting}
                    className="mt-2 w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-bold py-2 rounded shadow transition-all flex items-center justify-center gap-2 text-sm"
                >
                    {isStarting ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                    Add to Queue
                </button>

                                </div>
            </div>

            {/* Center: Orchestration Feed */}
            <div className="flex-1 p-6 flex flex-col bg-slate-50 relative">

                {isUatPending && previewUrl && (
                    <div className="absolute inset-0 bg-slate-900/90 z-50 flex flex-col p-4 m-6 rounded-lg backdrop-blur-sm shadow-2xl overflow-hidden border border-slate-700">
                        <div className="flex justify-between items-center mb-4 shrink-0">
                            <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                <span className="animate-pulse w-3 h-3 bg-red-500 rounded-full inline-block"></span>
                                UAT Live Preview Gate
                            </h2>
                        </div>
                        <iframe
                            src={previewUrl}
                            className="flex-1 w-full bg-white rounded shadow-inner mb-4 border border-slate-600"
                            title="Live Preview"
                        />
                        <div className="flex flex-col gap-3 shrink-0 bg-slate-800 p-4 rounded border border-slate-700">
                            <h3 className="text-white font-bold text-sm uppercase tracking-wider mb-1">Human Verdict</h3>
                            <textarea
                                value={uatFeedback}
                                onChange={(e) => setUatFeedback(e.target.value)}
                                placeholder="If rejecting, type your UI feedback here (e.g. 'The button is misaligned')..."
                                className="w-full p-3 bg-slate-900 border border-slate-600 text-white rounded focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none h-20 text-sm"
                            />
                            <div className="flex gap-4 mt-2">
                                <button
                                    onClick={() => handleUatDecision(false)}
                                    className="flex-1 bg-rose-600 hover:bg-rose-700 text-white font-black py-4 px-6 rounded shadow-lg text-lg transition-colors border border-rose-500 -skew-x-12"
                                >
                                    <div className="skew-x-12">❌ Reject (Send Feedback)</div>
                                </button>

                                <button
                                    onClick={() => handleUatDecision(true)}
                                    className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-black py-4 px-6 rounded shadow-lg text-lg transition-colors border border-emerald-500 -skew-x-12"
                                >
                                    <div className="skew-x-12">✅ LGTM! Approve & Merge</div>
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                <div className="flex items-center justify-between mb-4 border-b border-slate-200 pb-2">
                    <h2 className="text-lg font-bold text-slate-700 flex items-center gap-2">
                        Orchestration Feed
                        {isRadarActive && <span className="ml-2 text-xs font-bold text-emerald-800 bg-emerald-200 py-1 px-3 rounded-md border border-emerald-400 shadow-sm animate-pulse">
                            🎯 Codebase RAG Active
                        </span>}
                    </h2>

                    <button
                        onClick={handleTriggerReview}
                        disabled={!activeBranch || isReviewing}
                        className="bg-purple-600 hover:bg-purple-700 disabled:bg-purple-300 text-white font-bold py-1.5 px-3 rounded shadow transition-all flex items-center justify-center gap-2 text-sm"
                    >
                        {isReviewing ? <Loader2 size={16} className="animate-spin" /> : <Eye size={16} />}
                        Trigger Code Review
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto space-y-3 font-mono text-sm bg-slate-900 rounded-lg p-4 shadow-inner text-slate-300">
                    {logs.length === 0 ? (
                        <div className="text-slate-500 italic h-full flex items-center justify-center">System idle. Awaiting initial prompt...</div>
                    ) : (
                        logs.map((log, idx) => (
                            <div key={idx} className="border-b border-slate-800 pb-4 last:border-0">
                                <div className={`font-bold mb-1 ${
                                    log.type === 'error' || log.type === 'ci_failed' ? 'text-rose-500' :
                                    log.type === 'action' ? 'text-blue-400' :
                                    log.type === 'review' ? 'text-purple-400' :
                                    log.type === 'ci' ? 'text-amber-500' :
                                    log.type === 'ci_success' ? 'text-emerald-400' :
                                    'text-emerald-400'
                                }`}>
                                    [{new Date().toLocaleTimeString()}] {log.type === 'error' && "ERROR"} {log.type === 'review' && "GEMINI REVIEW"}
                                </div>
                                {log.type === 'review' ? (
                                    <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-slate-800">
                                        <ReactMarkdown>{log.message}</ReactMarkdown>
                                    </div>
                                ) : (
                                    <div className="whitespace-pre-wrap">{log.message}</div>
                                )}
                            </div>
                        ))
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Right: State Monitor */}
            <div className="w-1/4 p-6 border-l border-slate-200 bg-white shadow-sm flex flex-col gap-6">
                 <h2 className="text-lg font-bold text-slate-700 border-b border-slate-200 pb-2">State Monitor</h2>

                 <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 shadow-sm">
                     <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Active Branch</div>
                     <div className="font-mono font-bold text-blue-600 flex items-center gap-2 break-all">
                         <GitBranch size={16} />
                         {activeBranch || "None (main)"}
                     </div>
                 </div>

                 <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 shadow-sm">
                     <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Iteration Count</div>
                     <div className="font-bold text-slate-700 text-xl flex items-center gap-2">
                         <RotateCcw size={18} className="text-emerald-600" />
                         {activeBranch ? `${iteration} / ${maxIterations}` : "-"}
                     </div>
                 </div>

                 <div className="mt-auto">
                    <button
                        onClick={handleForceMerge}
                        disabled={!activeBranch || isMerging}
                        className="w-full bg-rose-600 hover:bg-rose-700 disabled:bg-rose-300 text-white font-bold py-3 rounded shadow transition-all flex items-center justify-center gap-2"
                    >
                        {isMerging ? <Loader2 size={18} className="animate-spin" /> : <GitMerge size={18} />}
                        Force Merge & Reset
                    </button>
                 </div>

            </div>

            {/* Bottom: Client Portal Kanban Storefront */}
            <div className="h-[40vh] min-h-[300px] border-t-4 border-slate-300 bg-slate-200 p-6 shadow-inner flex flex-col z-20 relative">
                <h2 className="text-xl font-black text-slate-800 uppercase mb-4 tracking-widest flex items-center gap-3">
                    <span className="bg-blue-600 text-white p-1.5 rounded shadow-sm"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line><line x1="15" y1="3" x2="15" y2="21"></line></svg></span>
                    Client Portal - Kanban Storefront
                </h2>

                <div className="flex-1 flex gap-6 overflow-x-auto overflow-y-hidden snap-x pb-4 custom-scrollbar">
                    {["pending", "running", "completed", "failed"].map(status => (
                        <div key={status} className="flex-1 min-w-[300px] max-w-[400px] bg-slate-100/90 backdrop-blur rounded-xl p-4 flex flex-col snap-start border border-slate-300 shadow-md h-[100%] [clip-path:polygon(15px_0,100%_0,100%_calc(100%-15px),calc(100%-15px)_100%,0_100%,0_15px)]">
                            <h4 className="text-sm font-bold text-slate-700 uppercase mb-3 pb-2 border-b border-slate-300 tracking-wider flex items-center justify-between">
                                {status}
                                <span className="bg-slate-300 text-slate-700 px-2 py-0.5 rounded-full text-xs shadow-sm font-black">
                                    {queue.filter((t: any) => t.status === status).length}
                                </span>
                            </h4>
                            <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar pb-2">
                                {queue.filter((t: any) => t.status === status).length === 0 ? (
                                    <div className="text-xs text-slate-400 italic text-center mt-8 font-mono">Empty Column</div>
                                ) : (
                                    queue.filter((t: any) => t.status === status).map((task: any) => (
                                        <div key={task.id} className={`p-4 rounded border-2 shadow-sm text-xs relative group transition-all hover:shadow-lg hover:-translate-y-1 ${task.status === 'running' ? 'border-blue-400 bg-blue-50/80' : task.status === 'completed' ? 'border-emerald-400 bg-emerald-50/80' : task.status === 'failed' ? 'border-rose-400 bg-rose-50/80' : 'border-slate-300 bg-white/80'}`}>
                                            <div className="flex justify-between items-start mb-3">
                                                <span className="font-mono font-black text-slate-700 truncate mr-2 text-sm bg-slate-200/50 px-1 rounded shadow-sm" title={task.id}>#{task.id.split('-')[0]}</span>
                                                {task.agent_state && (
                                                    <span className={`px-2 py-1 rounded text-[10px] uppercase font-black tracking-widest shadow-sm whitespace-nowrap ${task.status === 'running' ? 'bg-blue-600 text-white animate-pulse' : 'bg-slate-200 text-slate-600'}`} title={task.agent_state}>
                                                        {task.agent_state.replace('_', ' ')}
                                                    </span>
                                                )}
                                            </div>
                                            <div className="text-slate-700 line-clamp-3 mb-3 font-medium text-sm border-l-2 border-slate-300 pl-2" title={task.prompt}>{task.prompt}</div>

                                            {task.status === 'completed' && task.tokensBurned && (
                                                <div className="mt-2 pt-3 border-t-2 border-emerald-200 border-dashed flex justify-between items-center">
                                                    <span className="text-sm text-emerald-800 font-black font-mono bg-emerald-100 px-2 py-1 rounded shadow-inner flex items-center gap-1">Cost: ${(task.tokensBurned / 1000000 * 1.25).toFixed(4)}</span>
                                                    <button className="text-[10px] bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 shadow-md font-black uppercase -skew-x-12 transition-transform hover:scale-105 border border-emerald-400">
                                                        <div className="skew-x-12 flex items-center gap-1">🧾 Invoice</div>
                                                    </button>
                                                </div>
                                            )}
                                            {task.status === 'running' && task.agent_state && (
                                                <div className="mt-2 pt-3 border-t-2 border-blue-200 border-dashed">
                                                    <div className="w-full bg-blue-200 rounded-full h-2 mb-2 shadow-inner overflow-hidden border border-blue-300 relative">
                                                        <div className="bg-blue-500 h-full rounded-full animate-pulse absolute left-0" style={{ width: '60%' }}></div>
                                                    </div>
                                                    <div className="text-[10px] text-blue-800 font-black uppercase tracking-widest text-center">{task.agent_state.replace('_', ' ')} In Progress...</div>
                                                </div>
                                            )}
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    ))}
                </div>
                <style>{`
                .custom-scrollbar::-webkit-scrollbar {
                  width: 6px;
                  height: 6px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                  background: transparent;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                  background-color: rgba(148, 163, 184, 0.5);
                  border-radius: 10px;
                }
                @keyframes progress {
                  0% { width: 0%; opacity: 0.8; }
                  50% { width: 100%; opacity: 1; }
                  100% { width: 0%; opacity: 0.8; }
                }
                `}</style>
            </div>
        </div>
    );
}
