"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Loader2, Kanban } from "lucide-react";
import React from 'react';

export default function ClientPortal() {
    const params = useParams();
    const projectId = params?.projectId as string || 'default';

    const [queue, setQueue] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const fetchQueue = async () => {
        try {
            const res = await fetch("/api/devhouse/queue");
            if (res.ok) {
                const data = await res.json();
                setQueue(data.queue || []);
            }
        } catch(e) {
            console.error(e);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchQueue();
        const interval = setInterval(fetchQueue, 5000);
        return () => clearInterval(interval);
    }, []);

    // Phase 3: Real-Time SSE Synchronization
    useEffect(() => {
        const eventSource = new EventSource('/api/devhouse/logs');
        eventSource.onmessage = (e) => {
            if(e.data === '"__DONE__"') return;
            try {
                const data = JSON.parse(e.data);
                if (data.type === 'state_change') {
                    setQueue(prevQueue => {
                        const activeTask = prevQueue.find(t => t.status === 'running');
                        if (activeTask) {
                            return prevQueue.map(t => t.id === activeTask.id ? { ...t, agent_state: data.newState } : t);
                        }
                        return prevQueue;
                    });
                }
                if (data.type === 'finished' || data.type === 'error') {
                    setTimeout(fetchQueue, 1500);
                }
            } catch(err) {
                 console.error("SSE parse err", err);
            }
        };

        return () => eventSource.close();
    }, []);

    // Column logic based on Agent Swarm states
    const getColumnTasks = (columnName: string) => {
        return queue.filter(task => {
            const state = task.agent_state || 'PLANNING';

            if (columnName === 'Backlog') {
                return task.status === 'pending';
            }
            if (columnName === 'In Progress (Dev)') {
                return task.status === 'running' && ['PLANNING', 'CODING'].includes(state);
            }
            if (columnName === 'Audits (QA & SecOps)') {
                return task.status === 'running' && ['SECOPS_AUDIT', 'QA_AUDIT'].includes(state);
            }
            if (columnName === 'UAT & Deployed') {
                return task.status === 'completed' || state === 'DEPLOYED' || (task.status === 'running' && ['UAT_GATE', 'PM_REVIEW'].includes(state));
            }
            return false;
        });
    };

    const columns = [
        { name: 'Backlog', id: 'Backlog', icon: '📝' },
        { name: 'In Progress (Dev)', id: 'In Progress (Dev)', icon: '🛠️' },
        { name: 'Audits (QA & SecOps)', id: 'Audits (QA & SecOps)', icon: '🛡️' },
        { name: 'UAT & Deployed', id: 'UAT & Deployed', icon: '🚀' }
    ];

    if (isLoading) {
        return <div className="h-screen w-full flex items-center justify-center bg-slate-50"><Loader2 className="animate-spin text-blue-500" size={48} /></div>;
    }

    return (
        <div className="h-screen w-full bg-slate-100 flex flex-col font-sans">
            <header className="bg-slate-900 text-white p-6 shadow-md border-b-4 border-blue-500 shrink-0">
                <div className="max-w-7xl mx-auto flex items-center justify-between">
                    <h1 className="text-2xl font-black uppercase tracking-widest flex items-center gap-3">
                        <Kanban className="text-blue-400" size={28} />
                        Client Portal <span className="text-slate-400 font-light mx-2">|</span> <span className="text-blue-400">{projectId.toUpperCase()}</span>
                    </h1>
                    <div className="text-sm font-bold bg-slate-800 px-4 py-2 rounded-full border border-slate-700 shadow-inner">
                        Auto-DevHouse Engine Status: <span className="text-emerald-400 animate-pulse ml-2">● ONLINE</span>
                    </div>
                </div>
            </header>

            <main className="flex-1 overflow-hidden p-6">
                <div className="max-w-7xl mx-auto h-full flex gap-6 overflow-x-auto pb-4 custom-scrollbar">
                    {columns.map(col => {
                        const tasks = getColumnTasks(col.id);
                        return (
                            <div key={col.id} className="w-80 shrink-0 bg-slate-200/50 rounded-xl flex flex-col border border-slate-300 shadow-sm [clip-path:polygon(10px_0,100%_0,100%_calc(100%-10px),calc(100%-10px)_100%,0_100%,0_10px)] relative overflow-hidden">
                                <div className="bg-slate-800 text-white p-4 border-b-4 border-blue-500 shrink-0 flex items-center justify-between relative z-10">
                                    <h2 className="font-bold text-sm uppercase tracking-wider flex items-center gap-2">
                                        <span>{col.icon}</span> {col.name}
                                    </h2>
                                    <span className="bg-slate-700 text-slate-300 text-xs font-black px-2 py-1 rounded-full">{tasks.length}</span>
                                </div>

                                <div className="flex-1 p-3 overflow-y-auto space-y-3 custom-scrollbar relative z-10">
                                    {tasks.length === 0 ? (
                                        <div className="h-32 flex items-center justify-center text-slate-400 font-mono text-sm italic border-2 border-dashed border-slate-300 rounded-lg">
                                            Empty
                                        </div>
                                    ) : (
                                        tasks.map(task => (
                                            <div key={task.id} className="bg-white p-4 rounded-lg shadow-md border border-slate-200 group hover:shadow-lg transition-all hover:-translate-y-1 relative overflow-hidden">
                                                {task.status === 'running' && (
                                                    <div className="absolute top-0 left-0 w-full h-1 bg-blue-100">
                                                        <div className="h-full bg-blue-500 animate-pulse" style={{ width: '60%' }}></div>
                                                    </div>
                                                )}

                                                <div className="flex justify-between items-start mb-3 pt-1">
                                                    <span className="text-xs font-black font-mono text-slate-500 bg-slate-100 px-2 py-1 rounded">#{task.id.split('-')[0]}</span>
                                                    {task.agent_state && (
                                                        <span className="text-[10px] uppercase font-bold tracking-widest bg-blue-100 text-blue-800 px-2 py-1 rounded">
                                                            {task.agent_state.replace('_', ' ')}
                                                        </span>
                                                    )}
                                                </div>

                                                <p className="text-sm text-slate-700 font-medium mb-4 line-clamp-3 leading-relaxed">
                                                    {task.prompt}
                                                </p>

                                                {/* Phase 4: Display live thumbnail for deployed/UAT items */}
                                                {col.id === 'UAT & Deployed' && (
                                                    <div className="mb-4 rounded overflow-hidden border border-slate-200 shadow-inner relative group/img">
                                                        {/* We assume uat_preview.png gets updated globally for now */}
                                                        <img src="/uat_preview.png" alt="Live Preview Thumbnail" className="w-full object-cover h-32 opacity-90 group-hover/img:opacity-100 transition-opacity" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                                                    </div>
                                                )}

                                                {task.status === 'completed' && task.tokensBurned && (
                                                    <div className="mt-3 pt-3 border-t border-slate-100 flex justify-between items-center">
                                                        <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-1 rounded-md">
                                                            Cost: ${(task.tokensBurned / 1000000 * 1.25).toFixed(4)}
                                                        </span>
                                                        <button className="text-[10px] font-black uppercase text-white bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 shadow -skew-x-12 transition-transform">
                                                            <div className="skew-x-12">🧾 Invoice</div>
                                                        </button>
                                                    </div>
                                                )}
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </main>

            <style>{`
            .custom-scrollbar::-webkit-scrollbar {
                width: 6px;
                height: 6px;
            }
            .custom-scrollbar::-webkit-scrollbar-track {
                background: transparent;
            }
            .custom-scrollbar::-webkit-scrollbar-thumb {
                background-color: #cbd5e1;
                border-radius: 10px;
            }
            `}</style>
        </div>
    );
}
