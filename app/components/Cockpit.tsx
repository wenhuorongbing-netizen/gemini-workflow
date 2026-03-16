"use client";

import { useState, useRef, useEffect } from "react";
import { Play, RotateCcw, GitBranch, GitMerge, Loader2, Eye } from "lucide-react";
import ReactMarkdown from "react-markdown";

export default function Cockpit() {
    const [prompt, setPrompt] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [isReviewing, setIsReviewing] = useState(false);
    const [kbLinks, setKbLinks] = useState("");
    const [model, setModel] = useState("Pro");
    const [isStarting, setIsStarting] = useState(false);

    const [activeBranch, setActiveBranch] = useState<string | null>(null);
    const [iteration, setIteration] = useState(1);
    const [maxIterations] = useState(5);
    const [logs, setLogs] = useState<{message: string, type: "info"|"action"|"error"|"review"}[]>([]);

    const [isMerging, setIsMerging] = useState(false);

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
                     setLogs(prev => [...prev, data]);
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

    const addLog = (msg: string, type: "info"|"action"|"error"|"review" = "info") => {
        setLogs(prev => [...prev, { message: msg, type }]);
    };

    const handleStart = async () => {
        if (!prompt.trim()) {
            alert("Please enter an initial prompt.");
            return;
        }
        setIsStarting(true);
        setLogs([]);
        try {
            const res = await fetch("/api/devhouse/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt, kbLinks, model })
            });
            const data = await res.json();
            if (!res.ok || data.status !== "success") {
                addLog(`Failed to start: ${data.error || data.message}`, "error");
                setIsStarting(false);
            }
        } catch (error: any) {
            addLog(`Error connecting to backend: ${error.message}`, "error");
            setIsStarting(false);
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
        <div className="flex h-full w-full bg-slate-50 text-slate-800">
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

                <button
                    onClick={handleStart}
                    disabled={isStarting || activeBranch !== null}
                    className="mt-4 w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-bold py-3 rounded shadow transition-all flex items-center justify-center gap-2"
                >
                    {isStarting ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
                    {activeBranch ? "Auto-Dev Running..." : "Start Auto-Dev"}
                </button>
            </div>

            {/* Center: Orchestration Feed */}
            <div className="flex-1 p-6 flex flex-col bg-slate-50 relative">
                <div className="flex items-center justify-between mb-4 border-b border-slate-200 pb-2">
                    <h2 className="text-lg font-bold text-slate-700">Orchestration Feed</h2>
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
                                <div className={`font-bold mb-1 ${log.type === 'error' ? 'text-rose-500' : log.type === 'action' ? 'text-blue-400' : log.type === 'review' ? 'text-purple-400' : 'text-emerald-400'}`}>
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
        </div>
    );
}
