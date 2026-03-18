"use client";

import React, { useState, useEffect } from 'react';

type TelemetryLog = {
  id: string;
  runId: string;
  agentRole: string;
  tokensPrompt: number;
  tokensCompletion: number;
  costEstimated: number;
  createdAt: string;
};

export default function Dashboard() {
  const [logs, setLogs] = useState<TelemetryLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchTelemetry = async () => {
    try {
      const res = await fetch("/api/telemetry");
      const data = await res.json();
      if (data.success) {
        setLogs(data.logs);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 5000);
    return () => clearInterval(interval);
  }, []);

  // Compute Metrics
  const totalCost = logs.reduce((sum, log) => sum + log.costEstimated, 0);
  // Estimate revenue: For this mock, assume every unique runId generated $500 revenue
  const uniqueRuns = new Set(logs.map(log => log.runId)).size;
  const totalRevenue = uniqueRuns * 500;

  const netProfit = totalRevenue - totalCost;
  const netProfitMargin = totalRevenue > 0 ? ((netProfit / totalRevenue) * 100).toFixed(2) : 0;

  // Compute Burn Rate by Agent
  const agentCosts: Record<string, number> = {};
  logs.forEach(log => {
    agentCosts[log.agentRole] = (agentCosts[log.agentRole] || 0) + log.costEstimated;
  });

  const totalAgentCost = Object.values(agentCosts).reduce((a, b) => a + b, 0);

  const getAgentPercentage = (cost: number) => {
    if (totalAgentCost === 0) return 0;
    return ((cost / totalAgentCost) * 100).toFixed(1);
  };

  const agentColors: Record<string, string> = {
    "DEV": "bg-blue-500",
    "PM": "bg-emerald-500",
    "QA": "bg-purple-500",
    "SECOPS": "bg-rose-500"
  };

  if (isLoading) {
    return <div className="p-8 text-white font-mono">Loading Telemetry Data...</div>;
  }

  return (
    <div className="min-h-screen bg-[#060606] p-8 font-sans" style={{ backgroundImage: 'radial-gradient(circle at center, #111 0%, #060606 100%)' }}>
      <header className="mb-8 border-b-2 border-slate-800 pb-4">
        <h1 className="text-3xl font-black text-white uppercase tracking-widest flex items-center gap-3">
          <span className="text-[#39FF14]">●</span> Auto-DevHouse Commercial Dashboard
        </h1>
        <p className="text-slate-400 font-mono mt-2">Executive telemetry & API Cost tracking.</p>
      </header>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl shadow-lg relative overflow-hidden group hover:border-[#39FF14] transition-colors [clip-path:polygon(15px_0,100%_0,100%_calc(100%-15px),calc(100%-15px)_100%,0_100%,0_15px)]">
          <div className="absolute top-0 right-0 w-24 h-24 bg-[#39FF14]/10 rounded-full blur-2xl group-hover:bg-[#39FF14]/20 transition-colors"></div>
          <h3 className="text-slate-400 text-sm font-bold uppercase tracking-wider mb-2 relative z-10">Total Agency Revenue</h3>
          <div className="text-4xl font-black text-white font-mono relative z-10">${totalRevenue.toFixed(2)}</div>
          <div className="text-[#39FF14] text-xs font-bold mt-2 relative z-10 font-mono">Based on {uniqueRuns} completed runs ($500/run)</div>
        </div>

        <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl shadow-lg relative overflow-hidden group hover:border-red-500 transition-colors [clip-path:polygon(15px_0,100%_0,100%_calc(100%-15px),calc(100%-15px)_100%,0_100%,0_15px)]">
          <div className="absolute top-0 right-0 w-24 h-24 bg-red-500/10 rounded-full blur-2xl group-hover:bg-red-500/20 transition-colors"></div>
          <h3 className="text-slate-400 text-sm font-bold uppercase tracking-wider mb-2 relative z-10">Total API Cost (COGS)</h3>
          <div className="text-4xl font-black text-white font-mono relative z-10">${totalCost.toFixed(4)}</div>
          <div className="text-red-400 text-xs font-bold mt-2 relative z-10 font-mono">Tokens burned across {logs.length} API calls</div>
        </div>

        <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl shadow-lg relative overflow-hidden group hover:border-blue-500 transition-colors [clip-path:polygon(15px_0,100%_0,100%_calc(100%-15px),calc(100%-15px)_100%,0_100%,0_15px)]">
          <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/10 rounded-full blur-2xl group-hover:bg-blue-500/20 transition-colors"></div>
          <h3 className="text-slate-400 text-sm font-bold uppercase tracking-wider mb-2 relative z-10">Net Profit Margin</h3>
          <div className="text-4xl font-black text-white font-mono relative z-10">{netProfitMargin}%</div>
          <div className="text-blue-400 text-xs font-bold mt-2 relative z-10 font-mono">Net Profit: ${netProfit.toFixed(2)}</div>
        </div>
      </div>

      {/* Burn Rate Chart */}
      <div className="bg-slate-900 p-8 border-t-4 border-blue-600 [clip-path:polygon(20px_0,100%_0,100%_calc(100%-20px),calc(100%-20px)_100%,0_100%,0_20px)] mb-8 shadow-2xl">
        <h2 className="text-xl text-blue-400 font-bold mb-6 uppercase tracking-widest flex items-center gap-2">
          Agent Token Burn Rate Breakdown
        </h2>

        {totalAgentCost === 0 ? (
          <div className="text-slate-500 italic font-mono">No token burn data available yet.</div>
        ) : (
          <div className="space-y-6">
            {/* Visual Flex Bar */}
            <div className="w-full h-8 flex rounded overflow-hidden shadow-inner bg-slate-800">
              {Object.entries(agentCosts).map(([agent, cost]) => (
                <div
                  key={agent}
                  className={`h-full ${agentColors[agent] || 'bg-slate-500'} transition-all duration-1000 ease-out`}
                  style={{ width: `${getAgentPercentage(cost)}%` }}
                  title={`${agent}: $${cost.toFixed(4)}`}
                ></div>
              ))}
            </div>

            {/* Legend / Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(agentCosts).map(([agent, cost]) => (
                <div key={agent} className="bg-slate-800 p-4 rounded border border-slate-700 flex flex-col gap-1">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`w-3 h-3 rounded-full ${agentColors[agent] || 'bg-slate-500'}`}></div>
                    <span className="font-bold text-slate-300 uppercase text-sm">{agent} Agent</span>
                  </div>
                  <span className="text-2xl font-mono text-white">{getAgentPercentage(cost)}%</span>
                  <span className="text-xs text-slate-400 font-mono">Cost: ${cost.toFixed(4)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Recent Telemetry Logs Table */}
      <div className="bg-slate-900 p-8 border-t-4 border-purple-600 [clip-path:polygon(20px_0,100%_0,100%_calc(100%-20px),calc(100%-20px)_100%,0_100%,0_20px)] shadow-2xl">
        <h2 className="text-xl text-purple-400 font-bold mb-6 uppercase tracking-widest">Recent Telemetry Firehose</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300 font-mono">
            <thead className="text-xs uppercase bg-slate-800 text-slate-400 border-b border-slate-700">
              <tr>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Run ID</th>
                <th className="px-4 py-3">Agent Role</th>
                <th className="px-4 py-3 text-right">Prompt Tokens</th>
                <th className="px-4 py-3 text-right">Completion Tokens</th>
                <th className="px-4 py-3 text-right">Est. Cost</th>
              </tr>
            </thead>
            <tbody>
              {logs.slice(0, 10).map((log) => (
                <tr key={log.id} className="border-b border-slate-800 hover:bg-slate-800/50 transition-colors">
                  <td className="px-4 py-3 text-slate-500">{new Date(log.createdAt).toLocaleString()}</td>
                  <td className="px-4 py-3 truncate max-w-[150px]" title={log.runId}>{log.runId}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs font-black text-white ${agentColors[log.agentRole] || 'bg-slate-600'}`}>
                      {log.agentRole}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">{log.tokensPrompt.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-emerald-400">+{log.tokensCompletion.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right font-bold text-rose-400">${log.costEstimated.toFixed(5)}</td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500 italic">No telemetry data recorded yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
