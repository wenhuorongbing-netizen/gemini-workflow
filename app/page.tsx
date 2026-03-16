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
import { Play, Bot, Globe, Repeat, FileJson, Loader2, CheckCircle2, XCircle, Database, AlertCircle, Zap } from "lucide-react";
import Cockpit from "./components/Cockpit";

interface Workspace {
  id: string;
  name: string;
  steps?: any[];
  quota?: number;
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
      <div className="p-4 flex-1 text-sm bg-slate-900/50 relative">
        <div className="text-slate-300 truncate">{content}</div>
        {((data?.prompt && data.prompt.includes("{{")) || (data?.systemPrompt && data.systemPrompt.includes("{{"))) && (
            <span className="absolute bottom-2 right-2 bg-blue-500 text-white text-[10px] px-1.5 py-0.5 rounded shadow-sm">Var</span>
        )}
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

const FileNode = ({ data }: any) => (
  <BaseNode data={data} icon={Database} title="Local File" content={data.fileName || "Upload a file..."} bgColor="bg-emerald-900" borderColor="border-emerald-700" />
);

const StateNode = ({ data }: any) => {
  const statusClasses = data?.executionStatus === 'running' ? "ring-2 ring-blue-500" : data?.executionStatus === 'success' ? "ring-2 ring-emerald-500" : "";
  return (
    <div className={`w-[280px] rounded-lg shadow-lg border-2 border-slate-500 bg-slate-700 ${statusClasses} transition-all duration-300 overflow-hidden text-slate-50 flex flex-col`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-slate-300" />
      <div className="px-4 py-2 border-b border-slate-500 flex justify-between items-center font-semibold tracking-wide bg-opacity-20 bg-black">
        <div className="flex items-center gap-2">
            <Database size={18} />
            <span>Global State</span>
        </div>
      </div>
      <div className="p-4 flex-1 text-sm bg-slate-900/50">
        <div className="text-slate-300 truncate">{`${data.varName || "VAR_NAME"} = ${data.defaultValue || "..."}`}</div>
      </div>
      <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-slate-300" />
    </div>
  );
};

const AgentLoopNode = ({ data }: any) => (
  <BaseNode data={data} icon={Repeat} title="Agentic Loop" content={`Target: ${data.url || "None"}`} bgColor="bg-purple-900" borderColor="border-purple-700" />
);

const nodeTypes = {
  trigger: TriggerNode,
  gemini: GeminiNode,
  scraper: ScraperNode,
  agentic_loop: AgentLoopNode,
  state: StateNode,
  file: FileNode,
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
            system_prompt: n.data.systemPrompt || '',
            new_chat: n.data.new_chat || false,
            show_result: true,
            profileId: n.data.profileId || '1',
            fileName: n.data.fileName || '',
            fileContent: n.data.fileContent || '',
        };

        if (n.type === 'agentic_loop') {
            return {
                ...base,
                id: n.id,
                chat_url: n.data.url || '',
                max_iterations: n.data.max_iterations || 3,
                reset_threshold: n.data.reset_threshold || 3,
                stop_sequence: n.data.stop_sequence || 'FINAL_REVIEW_COMPLETE'
            };
        }
        return { ...base, id: n.id };
    });

    return { steps, nodeOrder: actionNodes.map(n => n.id) };
}

// --- Main App Shell ---


const PropertiesPanel = ({ selectedNodeId, nodes, updateNodeData, isPlaybackMode, setSelectedNodeId, playbackRun }: any) => {
  return (
    <aside className="absolute top-0 right-0 w-[300px] h-full bg-white border-l border-slate-200 shadow-xl z-20 flex flex-col PropertiesPanel">
      <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
        <h3 className="font-bold text-slate-800">Node Properties</h3>
        <button onClick={() => setSelectedNodeId(null)} className="text-slate-400 hover:text-slate-600">✕</button>
      </div>
      <div className="p-4 flex-1 overflow-y-auto">
        {nodes.filter((n: any) => n.id === selectedNodeId).map((node: any) => (
          <div key={node.id} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Node Type</label>
              <div className="px-3 py-1.5 bg-slate-100 rounded text-sm text-slate-700 font-medium capitalize">{node.type?.replace('_', ' ')}</div>
            </div>

            {node.type === 'gemini' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Model Selection</label>
                  <select
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                    value={node.data.model as string || 'Flash'}
                    onChange={(e) => updateNodeData(node.id, { model: e.target.value })}
                    disabled={isPlaybackMode}
                  >
                    <option value="Flash">Gemini 1.5 Flash</option>
                    <option value="Pro">Gemini 1.5 Pro</option>
                    <option value="Advanced">Advanced</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Account Profile</label>
                  <select
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                    value={node.data.profileId as string || '1'}
                    onChange={(e) => updateNodeData(node.id, { profileId: e.target.value })}
                    disabled={isPlaybackMode}
                  >
                    <option value="1">Main Account (Profile 1)</option>
                    <option value="2">Secondary Bot (Profile 2)</option>
                    <option value="3">Tertiary Bot (Profile 3)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">System Role (System Prompt)</label>
                  <textarea
                    className="w-full h-20 px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={node.data.systemPrompt as string || ''}
                    onChange={(e) => updateNodeData(node.id, { systemPrompt: e.target.value })}
                    disabled={isPlaybackMode}
                    placeholder="e.g., You are a senior code reviewer..."
                  />
                </div>
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">User Prompt</label>

                    <div className="relative group">
                      <button className="text-xs bg-slate-200 hover:bg-blue-100 text-blue-700 px-2 py-0.5 rounded transition InsertVariableBtn">
                        Insert Variable
                      </button>
                      <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-slate-200 rounded-md shadow-xl opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto transition-opacity z-50 p-1 flex flex-col gap-1 max-h-48 overflow-y-auto">
                        {nodes.filter((n: any) => n.id !== node.id).map((n: any) => (
                          <button
                            key={n.id}
                            onClick={() => {
                              const newVal = (node.data.prompt || '') + ` {{${n.id}}}`;
                              updateNodeData(node.id, { prompt: newVal });
                            }}
                            className="text-left text-xs px-2 py-1.5 hover:bg-slate-100 rounded text-slate-700 truncate"
                            disabled={isPlaybackMode}
                          >
                            <span className="font-semibold">{n.type}</span>: {String(n.data.prompt || n.data.url || 'Node')}
                          </button>
                        ))}
                        {nodes.length <= 1 && <div className="text-xs text-slate-400 p-2 text-center">No other nodes</div>}
                      </div>
                    </div>
                  </div>
                  <textarea
                    className="w-full h-32 px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={node.data.prompt as string || ''}
                    onChange={(e) => updateNodeData(node.id, { prompt: e.target.value })}
                    disabled={isPlaybackMode}
                    placeholder="Enter AI prompt... Use {{NODE_ID}} to inject previous outputs."
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Attachments</label>
                  {node.data.attachments && (node.data.attachments as string[]).length > 0 && (
                      <div className="flex flex-col gap-1 mb-2">
                          {(node.data.attachments as string[]).map((att, idx) => (
                              <div key={idx} className="text-xs text-slate-600 bg-slate-100 p-1 rounded flex justify-between items-center">
                                  <span className="truncate max-w-[200px]">{att.split('/').pop()}</span>
                                  {!isPlaybackMode && (
                                    <button onClick={() => {
                                        const newAtts = [...(node.data.attachments as string[])];
                                        newAtts.splice(idx, 1);
                                        updateNodeData(node.id, { attachments: newAtts });
                                    }} className="text-red-500 hover:text-red-700">✕</button>
                                  )}
                              </div>
                          ))}
                      </div>
                  )}
                  {!isPlaybackMode && (
                      <label className="cursor-pointer flex items-center justify-center w-full px-3 py-2 border-2 border-dashed border-slate-300 rounded text-sm text-slate-500 hover:border-blue-500 hover:text-blue-500 transition-colors bg-white">
                          📎 Add Attachment (Image/PDF)
                          <input type="file" className="hidden" accept="image/*,.pdf" onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if(!file) return;
                              const formData = new FormData();
                              formData.append('file', file);
                              try {
                                  const res = await fetch('/api/upload', { method: 'POST', body: formData });
                                  const data = await res.json();
                                  if(data.status === 'success') {
                                      const currentAtts = (node.data.attachments as string[]) || [];
                                      updateNodeData(node.id, { attachments: [...currentAtts, data.path] });
                                  } else {
                                      alert('Upload failed');
                                  }
                              } catch(err) {
                                  console.error(err);
                                  alert('Upload error');
                              }
                          }} />
                      </label>
                  )}
                </div>
              </div>
            )}

            {node.type === 'file' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Upload Local File</label>
                  <input
                    type="file"
                    className="w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100"
                    onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        const reader = new FileReader();
                        reader.onload = (event) => {
                            const result = event.target?.result as string;
                            updateNodeData(node.id, { fileName: file.name, fileContent: result });
                        };
                        reader.readAsText(file);
                    }}
                    disabled={isPlaybackMode}
                  />
                </div>
                {node.data.fileName && (
                    <div className="text-xs text-emerald-600 bg-emerald-50 p-2 rounded">
                        <strong>Loaded:</strong> {node.data.fileName as string}
                    </div>
                )}
                <div className="text-[10px] text-slate-500">
                    Extracts text to be referenced downstream using {'{{'}NODE_ID{'}}'} or {'{{'}FILE_CONTENT{'}}'}.
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Attachments</label>
                  {node.data.attachments && (node.data.attachments as string[]).length > 0 && (
                      <div className="flex flex-col gap-1 mb-2">
                          {(node.data.attachments as string[]).map((att, idx) => (
                              <div key={idx} className="text-xs text-slate-600 bg-slate-100 p-1 rounded flex justify-between items-center">
                                  <span className="truncate max-w-[200px]">{att.split('/').pop()}</span>
                                  {!isPlaybackMode && (
                                    <button onClick={() => {
                                        const newAtts = [...(node.data.attachments as string[])];
                                        newAtts.splice(idx, 1);
                                        updateNodeData(node.id, { attachments: newAtts });
                                    }} className="text-red-500 hover:text-red-700">✕</button>
                                  )}
                              </div>
                          ))}
                      </div>
                  )}
                  {!isPlaybackMode && (
                      <label className="cursor-pointer flex items-center justify-center w-full px-3 py-2 border-2 border-dashed border-slate-300 rounded text-sm text-slate-500 hover:border-blue-500 hover:text-blue-500 transition-colors bg-white">
                          📎 Add Attachment (Image/PDF)
                          <input type="file" className="hidden" accept="image/*,.pdf" onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if(!file) return;
                              const formData = new FormData();
                              formData.append('file', file);
                              try {
                                  const res = await fetch('/api/upload', { method: 'POST', body: formData });
                                  const data = await res.json();
                                  if(data.status === 'success') {
                                      const currentAtts = (node.data.attachments as string[]) || [];
                                      updateNodeData(node.id, { attachments: [...currentAtts, data.path] });
                                  } else {
                                      alert('Upload failed');
                                  }
                              } catch(err) {
                                  console.error(err);
                                  alert('Upload error');
                              }
                          }} />
                      </label>
                  )}
                </div>
              </div>
            )}

            {node.type === 'approval' && (
              <div className="space-y-4">
                <p className="text-sm text-amber-700 bg-amber-50 p-3 rounded border border-amber-200">
                  This node will pause the workflow execution. A human user must manually approve the state in the App Dashboard before the workflow can proceed to the next node.
                </p>
              </div>
            )}

            {node.type === 'router' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Target Variable</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500"
                    value={node.data.targetVariable as string || ''}
                    onChange={(e) => updateNodeData(node.id, { targetVariable: e.target.value })}
                    disabled={isPlaybackMode}
                    placeholder="{{NODE_1_OUTPUT}}"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Condition</label>
                  <select
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500 bg-white"
                    value={node.data.condition as string || 'CONTAINS'}
                    onChange={(e) => updateNodeData(node.id, { condition: e.target.value })}
                    disabled={isPlaybackMode}
                  >
                    <option value="CONTAINS">Contains</option>
                    <option value="EQUALS">Equals</option>
                    <option value="NOT CONTAINS">Does Not Contain</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Value</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500"
                    value={node.data.conditionValue as string || ''}
                    onChange={(e) => updateNodeData(node.id, { conditionValue: e.target.value })}
                    disabled={isPlaybackMode}
                    placeholder="e.g. URGENT"
                  />
                </div>
              </div>
            )}

            {node.type === 'webhook' && (
              <div className="space-y-4">
                <div className="relative">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Target URL</label>
                <input
                  type="text"
                  className={`w-full px-3 py-2 border rounded text-sm focus:outline-none focus:ring-2 ${
                    (node.data.url && !(node.data.url as string).startsWith('http://') && !(node.data.url as string).startsWith('https://'))
                      ? 'border-red-500 focus:ring-red-500 bg-red-50 text-red-900'
                      : 'border-slate-300 focus:ring-fuchsia-500 focus:border-fuchsia-500'
                  }`}
                  value={node.data.url as string || ''}
                  onChange={(e) => updateNodeData(node.id, { url: e.target.value })}
                  disabled={isPlaybackMode}
                  placeholder="https://hooks.zapier.com/..."
                />
                {(node.data.url && !(node.data.url as string).startsWith('http://') && !(node.data.url as string).startsWith('https://')) && (
                  <div className="absolute -top-8 right-0 bg-red-600 text-white text-[10px] px-2 py-1 rounded shadow-lg after:content-[''] after:absolute after:top-full after:right-4 after:border-4 after:border-transparent after:border-t-red-600">
                    ⚠️ Must start with http:// or https://
                  </div>
                )}
                </div>
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">Payload Template (JSON)</label>

                    <div className="relative group">
                      <button className="text-xs bg-slate-200 hover:bg-fuchsia-100 text-fuchsia-700 px-2 py-0.5 rounded transition InsertVariableBtn">
                        Insert Variable
                      </button>
                      <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-slate-200 rounded-md shadow-xl opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto transition-opacity z-50 p-1 flex flex-col gap-1 max-h-48 overflow-y-auto">
                        {nodes.filter((n: any) => n.id !== node.id).map((n: any) => (
                          <button
                            key={n.id}
                            onClick={() => {
                              const newVal = (node.data.prompt || '') + ` {{${n.id}}}`;
                              updateNodeData(node.id, { prompt: newVal });
                            }}
                            className="text-left text-xs px-2 py-1.5 hover:bg-slate-100 rounded text-slate-700 truncate"
                            disabled={isPlaybackMode}
                          >
                            <span className="font-semibold">{n.type}</span>: {String(n.data.prompt || n.data.url || 'Node')}
                          </button>
                        ))}
                        {nodes.length <= 1 && <div className="text-xs text-slate-400 p-2 text-center">No other nodes</div>}
                      </div>
                    </div>
                  </div>
                  <textarea
                    className="w-full h-32 px-3 py-2 border border-slate-300 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-fuchsia-500 focus:border-fuchsia-500"
                    value={node.data.prompt as string || ''}
                    onChange={(e) => updateNodeData(node.id, { prompt: e.target.value })}
                    disabled={isPlaybackMode}
                    placeholder='{"message": "{{NODE_1_ID}}"}'
                  />
                </div>
              </div>
            )}

            {node.type === 'scraper' && (
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Target URL</label>
                <div className="relative">
                <input
                  type="text"
                  className={`w-full px-3 py-2 border rounded text-sm focus:outline-none focus:ring-2 ${
                    (node.data.url && !(node.data.url as string).startsWith('http://') && !(node.data.url as string).startsWith('https://'))
                      ? 'border-red-500 focus:ring-red-500 bg-red-50 text-red-900'
                      : 'border-slate-300 focus:ring-amber-500 focus:border-amber-500'
                  }`}
                  value={node.data.url as string || ''}
                  onChange={(e) => updateNodeData(node.id, { url: e.target.value })}
                    disabled={isPlaybackMode}
                  placeholder="https://..."
                />
                {(node.data.url && !(node.data.url as string).startsWith('http://') && !(node.data.url as string).startsWith('https://')) && (
                  <div className="absolute -top-8 right-0 bg-red-600 text-white text-[10px] px-2 py-1 rounded shadow-lg after:content-[''] after:absolute after:top-full after:right-4 after:border-4 after:border-transparent after:border-t-red-600">
                    ⚠️ Must start with http:// or https://
                  </div>
                )}
                </div>
                {(node.data.url && !(node.data.url as string).startsWith('http://') && !(node.data.url as string).startsWith('https://')) && (
                    <div className="text-xs text-red-500 mt-1 flex items-center gap-1">
                        <AlertCircle size={12}/> ⚠️ Must start with http:// or https://
                    </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Attachments</label>
                  {node.data.attachments && (node.data.attachments as string[]).length > 0 && (
                      <div className="flex flex-col gap-1 mb-2">
                          {(node.data.attachments as string[]).map((att, idx) => (
                              <div key={idx} className="text-xs text-slate-600 bg-slate-100 p-1 rounded flex justify-between items-center">
                                  <span className="truncate max-w-[200px]">{att.split('/').pop()}</span>
                                  {!isPlaybackMode && (
                                    <button onClick={() => {
                                        const newAtts = [...(node.data.attachments as string[])];
                                        newAtts.splice(idx, 1);
                                        updateNodeData(node.id, { attachments: newAtts });
                                    }} className="text-red-500 hover:text-red-700">✕</button>
                                  )}
                              </div>
                          ))}
                      </div>
                  )}
                  {!isPlaybackMode && (
                      <label className="cursor-pointer flex items-center justify-center w-full px-3 py-2 border-2 border-dashed border-slate-300 rounded text-sm text-slate-500 hover:border-blue-500 hover:text-blue-500 transition-colors bg-white">
                          📎 Add Attachment (Image/PDF)
                          <input type="file" className="hidden" accept="image/*,.pdf" onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if(!file) return;
                              const formData = new FormData();
                              formData.append('file', file);
                              try {
                                  const res = await fetch('/api/upload', { method: 'POST', body: formData });
                                  const data = await res.json();
                                  if(data.status === 'success') {
                                      const currentAtts = (node.data.attachments as string[]) || [];
                                      updateNodeData(node.id, { attachments: [...currentAtts, data.path] });
                                  } else {
                                      alert('Upload failed');
                                  }
                              } catch(err) {
                                  console.error(err);
                                  alert('Upload error');
                              }
                          }} />
                      </label>
                  )}
                </div>
              </div>
            )}

            {node.type === 'agentic_loop' && (
              <>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Repository/Target URL</label>
                  <input
                    type="text"
                    className={`w-full px-3 py-2 border rounded text-sm focus:outline-none focus:ring-2 ${
                        (node.data.url && !(node.data.url as string).startsWith('http://') && !(node.data.url as string).startsWith('https://'))
                          ? 'border-red-500 focus:ring-red-500 bg-red-50 text-red-900'
                          : 'border-slate-300 focus:ring-purple-500 focus:border-purple-500'
                      }`}
                    value={node.data.url as string || ''}
                    onChange={(e) => updateNodeData(node.id, { url: e.target.value })}
                    disabled={isPlaybackMode}
                    placeholder="https://github.com/..."
                  />
                  {(node.data.url && !(node.data.url as string).startsWith('http://') && !(node.data.url as string).startsWith('https://')) && (
                      <div className="text-xs text-red-500 mt-1 flex items-center gap-1">
                          <AlertCircle size={12}/> ⚠️ Must start with http:// or https://
                      </div>
                  )}
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
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Stop Sequence</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500"
                    value={node.data.stop_sequence as string || 'FINAL_REVIEW_COMPLETE'}
                    onChange={(e) => updateNodeData(node.id, { stop_sequence: e.target.value })}
                    disabled={isPlaybackMode}
                    placeholder="e.g., DONE"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">If Gemini outputs this string, the loop finishes immediately.</p>
                </div>
              </>
            )}

            {node.type === 'state' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Variable Name</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-slate-500 focus:border-slate-500"
                    value={node.data.varName as string || ''}
                    onChange={(e) => updateNodeData(node.id, { varName: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '') })}
                    disabled={isPlaybackMode}
                    placeholder="e.g., USER_PREFS"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Default Value</label>
                  <textarea
                    className="w-full h-24 px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-slate-500 focus:border-slate-500"
                    value={node.data.defaultValue as string || ''}
                    onChange={(e) => updateNodeData(node.id, { defaultValue: e.target.value })}
                    disabled={isPlaybackMode}
                    placeholder="Enter default text or JSON..."
                  />
                </div>
                <div className="text-xs text-slate-500 italic">
                  Use {`{{GLOBAL_VAR_NAME}}`} in any prompt downstream to inject this value.
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Attachments</label>
                  {node.data.attachments && (node.data.attachments as string[]).length > 0 && (
                      <div className="flex flex-col gap-1 mb-2">
                          {(node.data.attachments as string[]).map((att, idx) => (
                              <div key={idx} className="text-xs text-slate-600 bg-slate-100 p-1 rounded flex justify-between items-center">
                                  <span className="truncate max-w-[200px]">{att.split('/').pop()}</span>
                                  {!isPlaybackMode && (
                                    <button onClick={() => {
                                        const newAtts = [...(node.data.attachments as string[])];
                                        newAtts.splice(idx, 1);
                                        updateNodeData(node.id, { attachments: newAtts });
                                    }} className="text-red-500 hover:text-red-700">✕</button>
                                  )}
                              </div>
                          ))}
                      </div>
                  )}
                  {!isPlaybackMode && (
                      <label className="cursor-pointer flex items-center justify-center w-full px-3 py-2 border-2 border-dashed border-slate-300 rounded text-sm text-slate-500 hover:border-blue-500 hover:text-blue-500 transition-colors bg-white">
                          📎 Add Attachment (Image/PDF)
                          <input type="file" className="hidden" accept="image/*,.pdf" onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if(!file) return;
                              const formData = new FormData();
                              formData.append('file', file);
                              try {
                                  const res = await fetch('/api/upload', { method: 'POST', body: formData });
                                  const data = await res.json();
                                  if(data.status === 'success') {
                                      const currentAtts = (node.data.attachments as string[]) || [];
                                      updateNodeData(node.id, { attachments: [...currentAtts, data.path] });
                                  } else {
                                      alert('Upload failed');
                                  }
                              } catch(err) {
                                  console.error(err);
                                  alert('Upload error');
                              }
                          }} />
                      </label>
                  )}
                </div>
              </div>
            )}

            {node.type === 'trigger' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Trigger Type</label>
                  <select
                    className="w-full bg-slate-900 border border-slate-700 rounded-md p-2 text-sm text-slate-300"
                    value={node.data.triggerType || 'manual'}
                    onChange={(e) => updateNodeData(node.id, { triggerType: e.target.value })}
                  >
                    <option value="manual">Manual Execution</option>
                    <option value="cron">Scheduled (Cron)</option>
                  </select>
                </div>
                {node.data.triggerType === 'cron' && (
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">Cron Expression</label>
                    <input
                      type="text"
                      className={`w-full bg-slate-900 border rounded-md p-2 text-sm text-slate-300 focus:outline-none ${
                        (node.data.cron && !/^(\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*\/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])) (\*|([0-9]|1[0-9]|2[0-3])|\*\/([0-9]|1[0-9]|2[0-3])) (\*|([1-9]|1[0-9]|2[0-9]|3[0-1])|\*\/([1-9]|1[0-9]|2[0-9]|3[0-1])) (\*|([1-9]|1[0-2])|\*\/([1-9]|1[0-2])) (\*|([0-6])|\*\/([0-6]))$/.test(node.data.cron as string))
                        ? 'border-red-500 focus:ring-1 focus:ring-red-500'
                        : 'border-slate-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500'
                      }`}
                      value={(node.data.cron as string) || ""}
                      onChange={(e) => updateNodeData(node.id, { cron: e.target.value })}
                      placeholder="e.g., */5 * * * *"
                    />
                    {(node.data.cron && !/^(\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*\/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])) (\*|([0-9]|1[0-9]|2[0-3])|\*\/([0-9]|1[0-9]|2[0-3])) (\*|([1-9]|1[0-9]|2[0-9]|3[0-1])|\*\/([1-9]|1[0-9]|2[0-9]|3[0-1])) (\*|([1-9]|1[0-2])|\*\/([1-9]|1[0-2])) (\*|([0-6])|\*\/([0-6]))$/.test(node.data.cron as string)) && (
                        <div className="text-xs text-red-500 mt-1 flex items-center gap-1">
                            <AlertCircle size={12}/> ⚠️ Invalid Cron Expression
                        </div>
                    )}
                    <div className="text-xs text-slate-500 mt-1 mt-2">
                        Use standard cron format. e.g. "0 0 * * *" for daily at midnight.
                        Saves to the backend automatically.
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Attachments</label>
                  {node.data.attachments && (node.data.attachments as string[]).length > 0 && (
                      <div className="flex flex-col gap-1 mb-2">
                          {(node.data.attachments as string[]).map((att, idx) => (
                              <div key={idx} className="text-xs text-slate-600 bg-slate-100 p-1 rounded flex justify-between items-center">
                                  <span className="truncate max-w-[200px]">{att.split('/').pop()}</span>
                                  {!isPlaybackMode && (
                                    <button onClick={() => {
                                        const newAtts = [...(node.data.attachments as string[])];
                                        newAtts.splice(idx, 1);
                                        updateNodeData(node.id, { attachments: newAtts });
                                    }} className="text-red-500 hover:text-red-700">✕</button>
                                  )}
                              </div>
                          ))}
                      </div>
                  )}
                  {!isPlaybackMode && (
                      <label className="cursor-pointer flex items-center justify-center w-full px-3 py-2 border-2 border-dashed border-slate-300 rounded text-sm text-slate-500 hover:border-blue-500 hover:text-blue-500 transition-colors bg-white">
                          📎 Add Attachment (Image/PDF)
                          <input type="file" className="hidden" accept="image/*,.pdf" onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if(!file) return;
                              const formData = new FormData();
                              formData.append('file', file);
                              try {
                                  const res = await fetch('/api/upload', { method: 'POST', body: formData });
                                  const data = await res.json();
                                  if(data.status === 'success') {
                                      const currentAtts = (node.data.attachments as string[]) || [];
                                      updateNodeData(node.id, { attachments: [...currentAtts, data.path] });
                                  } else {
                                      alert('Upload failed');
                                  }
                              } catch(err) {
                                  console.error(err);
                                  alert('Upload error');
                              }
                          }} />
                      </label>
                  )}
                </div>
              </div>
            )}

            {isPlaybackMode && playbackRun && playbackRun.parsedResults && playbackRun.parsedResults[node.id] && (
                <div className="mt-6 border-t border-slate-200 pt-4">
                    <label className="block text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-2">Snapshot Output Result</label>
                    <div className="p-3 bg-slate-900 text-slate-300 text-xs rounded-md overflow-x-auto whitespace-pre-wrap font-mono max-h-96 overflow-y-auto">
                        {playbackRun.parsedResults[node.id]}
                    </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Attachments</label>
                  {node.data.attachments && (node.data.attachments as string[]).length > 0 && (
                      <div className="flex flex-col gap-1 mb-2">
                          {(node.data.attachments as string[]).map((att, idx) => (
                              <div key={idx} className="text-xs text-slate-600 bg-slate-100 p-1 rounded flex justify-between items-center">
                                  <span className="truncate max-w-[200px]">{att.split('/').pop()}</span>
                                  {!isPlaybackMode && (
                                    <button onClick={() => {
                                        const newAtts = [...(node.data.attachments as string[])];
                                        newAtts.splice(idx, 1);
                                        updateNodeData(node.id, { attachments: newAtts });
                                    }} className="text-red-500 hover:text-red-700">✕</button>
                                  )}
                              </div>
                          ))}
                      </div>
                  )}
                  {!isPlaybackMode && (
                      <label className="cursor-pointer flex items-center justify-center w-full px-3 py-2 border-2 border-dashed border-slate-300 rounded text-sm text-slate-500 hover:border-blue-500 hover:text-blue-500 transition-colors bg-white">
                          📎 Add Attachment (Image/PDF)
                          <input type="file" className="hidden" accept="image/*,.pdf" onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if(!file) return;
                              const formData = new FormData();
                              formData.append('file', file);
                              try {
                                  const res = await fetch('/api/upload', { method: 'POST', body: formData });
                                  const data = await res.json();
                                  if(data.status === 'success') {
                                      const currentAtts = (node.data.attachments as string[]) || [];
                                      updateNodeData(node.id, { attachments: [...currentAtts, data.path] });
                                  } else {
                                      alert('Upload failed');
                                  }
                              } catch(err) {
                                  console.error(err);
                                  alert('Upload error');
                              }
                          }} />
                      </label>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
};

export default function AppShell() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null);
  const [activeTab, setActiveTab] = useState<"editor" | "cockpit">("editor");
  const [isLoading, setIsLoading] = useState(true);

  // React Flow State
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [logs, setLogs] = useState<{status: string, message: string}[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Snapshot / Run History State
  const [runHistory, setRunHistory] = useState<any[]>([]);
  const [playbackRun, setPlaybackRun] = useState<any | null>(null);
  const isPlaybackMode = !!playbackRun;

  const [showAccountModal, setShowAccountModal] = useState(false);
  const [accountProfileStr, setAccountProfileStr] = useState("1");
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [currentUserId, setCurrentUserId] = useState<string>("user1");
  const [userStats, setUserStats] = useState<any>(null);

  useEffect(() => {
    const savedUserId = localStorage.getItem('current_userId');
    if (savedUserId) setCurrentUserId(savedUserId);
  }, []);

  useEffect(() => {
    localStorage.setItem('current_userId', currentUserId);
    fetchWorkspaces();
    fetchUserStats();
  }, [currentUserId]);

  const fetchUserStats = async () => {
      try {
          const res = await fetch('/api/user', { headers: { 'x-user-id': currentUserId } });
          if (res.ok) setUserStats(await res.json());
      } catch(e) {}
  };

  useEffect(() => {
    logsEndRef.current?.scrollIntoView(false);
  }, [logs]);

  useEffect(() => {
    if (selectedWorkspace) {
      fetchWorkflowData(selectedWorkspace.id);
    }
  }, [selectedWorkspace]);


  // Auto-Save Debounce
  useEffect(() => {
    if (!selectedWorkspace || isLoading || isPlaybackMode) return;

    const timeoutId = setTimeout(() => {
        fetch(`/api/workflows/save`, { method: "POST", headers: { "Content-Type": "application/json", "x-user-id": currentUserId },
            body: JSON.stringify({ workspaceId: selectedWorkspace.id, nodes, edges })
        }).then(() => {
            setIsSyncing(true);
            setTimeout(() => setIsSyncing(false), 2000);
        }).catch(e => console.error("Silent auto-save failed", e));
    }, 1000);

    return () => clearTimeout(timeoutId);
  }, [nodes, edges, selectedWorkspace, isLoading, isPlaybackMode]);

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
  }, [nodes, isExecuting]);

  const saveWorkflowSilent = async () => {
    if (!selectedWorkspace) return;
    try {
        await fetch(`/api/workflows/${selectedWorkspace.id}`, { method: "POST", headers: { "Content-Type": "application/json", "x-user-id": currentUserId },
            body: JSON.stringify({ nodes, edges })
        });
    } catch (e) {
        console.error("Silent auto-save failed", e);
    }
  };

  const fetchWorkflowData = async (workspaceId: string) => {
    try {
      const res = await fetch(`/api/workflows/${workspaceId}`, { headers: { "x-user-id": currentUserId } });
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

      const runRes = await fetch(`/api/runs/${workspaceId}`, { headers: { "x-user-id": currentUserId } });
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
        const res = await fetch(`/api/workflows/${selectedWorkspace.id}`, { method: "POST", headers: { "Content-Type": "application/json", "x-user-id": currentUserId },
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

  useEffect(() => {
    const savedTaskId = localStorage.getItem('current_task_id');
    if (savedTaskId) {
      console.log("Resuming task:", savedTaskId);
      setIsExecuting(true);
      const eventSource = new EventSource(`http://127.0.0.1:5000/api/logs/${savedTaskId}`);

        eventSource.onmessage = async (event) => {
            try {
                if (event.data === "__DONE__") {
                    eventSource.close();
                    setIsExecuting(false);
                    return;
                }
                const dataStr = event.data;
                const data = JSON.parse(dataStr);

                if (data.error) {
                    console.error("Execution error:", data.error);
                    setLogs(prev => [...prev, { status: "Error", message: data.error }]);
                    setIsExecuting(false);
                    setNodes(nds => nds.map(n => ({ ...n, data: { ...n.data, executionStatus: 'error' } })));
                    eventSource.close();
                    return;
                }

                if (data.status) {
                    setLogs(prev => [...prev, { status: data.status, message: data.message || data.result || "" }]);
                }

                if (data.status === 'Workflow Finished' || data.status === 'Error' || data.status === 'Canceled') {
                    setIsExecuting(false);
                    localStorage.removeItem('current_task_id');
                    eventSource.close();
                    fetchUserStats();
                }
            } catch (e) {
                console.error("Error parsing JSON:", e, event.data);
            }
        };

        eventSource.onerror = (err) => {
            console.error("EventSource failed:", err);
            setIsExecuting(false);
            eventSource.close();
        };
    }
  }, []);

  const fetchWorkspaces = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/workspaces", { headers: { "x-user-id": currentUserId } });
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
      const res = await fetch("/api/workspaces", { method: "POST", headers: { "Content-Type": "application/json", "x-user-id": currentUserId }, body: JSON.stringify({ name }) });
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
    if (!selectedWorkspace) return;
    if (nodes.length === 0) {
        alert("Drag a node to the canvas to begin.");
        return;
    }

    let compiledData;
    try {
        compiledData = compileNodesToSteps(nodes, edges);
    } catch (err: any) {
        alert(err.message || "Failed to compile workflow");
        return;
    }
    const { steps: compiledSteps, nodeOrder } = compiledData;
      console.log("Compiled JSON Payload for app.py:", compiledSteps);

      setLogs([]); // Clear previous logs
      setIsExecuting(true);

      // Reset all node statuses
      setNodes(nds => nds.map(n => ({...n, data: {...n.data, executionStatus: 'idle'}})));

      const stateNodes = nodes.filter(n => n.type === 'state');
      const global_state: Record<string, string> = {};
      stateNodes.forEach(n => {
          if (n.data.varName) {
              global_state[n.data.varName as string] = n.data.defaultValue as string || '';
          }
      });

      try {
        const response = await fetch("http://127.0.0.1:5000/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ steps: compiledSteps, workspace_id: selectedWorkspace?.id || "temp", profile_id: "1", global_state, user_id: currentUserId })
        });

        if (!response.ok) {
           const err = await response.json();
           alert("Failed to queue workflow: " + (err.error || "Unknown error"));
           setIsExecuting(false);
           return;
        }

        const data = await response.json();
        const taskId = data.task_id;

        if (!taskId) {
            throw new Error("No task ID returned");
        }

        localStorage.setItem('current_task_id', taskId);
        const eventSource = new EventSource(`http://127.0.0.1:5000/api/logs/${taskId}`);

        eventSource.onmessage = async (event) => {
            try {
                if (event.data === "__DONE__") {
                    eventSource.close();
                    setIsExecuting(false);
                    return;
                }
                const dataStr = event.data;
                const data = JSON.parse(dataStr);

                if (data.error) {
                    console.error("Execution error:", data.error);
                    setLogs(prev => [...prev, { status: "Error", message: data.error }]);
                    setIsExecuting(false);
                    setNodes(nds => nds.map(n => ({ ...n, data: { ...n.data, executionStatus: 'error' } })));
                    eventSource.close();
                    return;
                }

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
                                    return { ...n, data: { ...n.data, executionStatus: statusToSet, result: data.result || data.partial_result || n.data.result } };
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
                        await fetch(`/api/runs/${selectedWorkspace.id}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                status: data.status,
                                logs: logs,
                                results: data.results || {},
                                nodes: nodes,
                                edges: edges
                            })
                        });
                        // Refresh history
                        fetchWorkflowData(selectedWorkspace.id);
                    }
                    localStorage.removeItem('current_task_id');
                    eventSource.close();
                }
            } catch (e) {
                console.error("Error parsing JSON:", e, event.data);
            }
        };

        eventSource.onerror = (err) => {
            console.error("EventSource failed:", err);
            setIsExecuting(false);
            setNodes(nds => nds.map(n => ({ ...n, data: { ...n.data, executionStatus: 'error' } })));
            eventSource.close();
        };

      } catch (error: any) {
          console.error("Execution request failed:", error);
          alert("Network Error: " + error.message);
          setIsExecuting(false);
          setNodes(nds => nds.map(n => ({ ...n, data: { ...n.data, executionStatus: 'error' } })));
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
          <div className="flex flex-col gap-1 items-end">
            {selectedWorkspace && selectedWorkspace.quota !== undefined && (
                <span className="text-[10px] bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full border border-amber-500/30 font-bold whitespace-nowrap">
                    ⚡ Tokens left: {selectedWorkspace.quota}
                </span>
            )}
            <button onClick={() => setShowAccountModal(true)} className="text-[10px] bg-slate-800 text-slate-300 px-2 py-1 rounded hover:bg-slate-700 transition">
                👤 Accounts
            </button>
          </div>
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
            workspaces.map((ws: any) => (
              <div key={ws.id} className="flex flex-col mb-1">
                  <button
                    onClick={() => setSelectedWorkspace(ws)}
                    className={`w-full text-left px-3 py-2 rounded-md transition-all text-sm flex justify-between items-center group ${
                      selectedWorkspace?.id === ws.id
                        ? "bg-blue-600 text-white font-medium shadow-md shadow-blue-900/20"
                        : "hover:bg-slate-800 hover:text-white"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                        <FileJson size={16} className={selectedWorkspace?.id === ws.id ? "text-blue-200" : "text-slate-500"}/>
                        <span className="truncate">{ws.name}</span>
                    </div>
                  </button>
                  {ws.workflows && ws.workflows.length > 0 && ws.workflows[0].isPublished && (
                      <a href={`/apps/${ws.workflows[0].id}`} target="_blank" className="ml-6 mt-1 text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition-colors">
                          <Play size={10}/> Launch Published App
                      </a>
                  )}
              </div>
            ))
          )}
        </div>

        {selectedWorkspace && runHistory.length > 0 && (
          <div className="flex-1 overflow-y-auto p-3 space-y-1 border-t border-slate-800 bg-slate-900/50">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-2 mt-2">
              🕰️ History
            </div>
            {runHistory.map(run => (
              <button
                key={run.id}
                onClick={() => {
                    try {
                        const parsedResults = JSON.parse(run.results || "{}");
                        setPlaybackRun({ ...run, parsedResults });

                        let historicalNodes = nodes;
                        let historicalEdges = [];
                        try {
                            if (run.nodes) historicalNodes = JSON.parse(run.nodes);
                            if (run.edges) historicalEdges = JSON.parse(run.edges);
                            setEdges(historicalEdges);
                            if (run.logs) {
                                try { setLogs(JSON.parse(run.logs)); } catch(e){}
                            }
                        } catch(e) {}

                        setNodes(historicalNodes.map((n: any) => {
                            if (parsedResults[n.id]) {
                                return { ...n, data: { ...n.data, executionStatus: 'success' } };
                            }
                            return n;
                        }));
                    } catch(e) {
                        alert("Failed to parse run results snapshot.");
                    }
                }}
                className={`w-full text-left px-3 py-2 rounded-md transition-all text-xs flex flex-col gap-1 border ${
                  playbackRun?.id === run.id
                    ? "bg-slate-800 border-slate-700 shadow-inner"
                    : "hover:bg-slate-800/80 border-transparent hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${run.status === 'Workflow Finished' || run.status === 'Complete' ? 'bg-emerald-900/50 text-emerald-400' : 'bg-rose-900/50 text-rose-400'}`}>
                        {run.status === 'Workflow Finished' ? 'SUCCESS' : 'FAILED'}
                    </span>
                    <span className="text-slate-500 font-mono text-[10px]">{new Date(run.createdAt).toLocaleTimeString()}</span>
                </div>
                <div className="text-slate-400 font-mono truncate">{new Date(run.createdAt).toLocaleDateString()}</div>
              </button>
            ))}
          </div>
        )}

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

            {/* View Toggle */}
            <div className="ml-4 flex bg-slate-100 p-1 rounded-lg">
                <button
                    onClick={() => setActiveTab('editor')}
                    className={`px-4 py-1.5 text-sm font-bold rounded-md transition-colors ${activeTab === 'editor' ? 'bg-white shadow-sm text-blue-600' : 'text-slate-500 hover:text-slate-700'}`}
                >
                    Workflow Editor
                </button>
                <button
                    onClick={() => setActiveTab('cockpit')}
                    className={`px-4 py-1.5 text-sm font-bold rounded-md transition-colors ${activeTab === 'cockpit' ? 'bg-white shadow-sm text-blue-600' : 'text-slate-500 hover:text-slate-700'}`}
                >
                    DevHouse Cockpit
                </button>
            </div>

            {/* User Switcher Dropdown */}
            <select
                value={currentUserId}
                onChange={e => setCurrentUserId(e.target.value)}
                className="ml-4 text-xs border-slate-300 rounded px-2 py-1 bg-slate-100 text-slate-600 focus:ring-blue-500 font-medium"
            >
                <option value="user1">User 1 (Free)</option>
                <option value="user2">User 2 (Team)</option>
                <option value="user3">User 3 (Enterprise)</option>
            </select>
          </div>

          <div className="flex items-center space-x-4">
            {/* Token Analytics Widget */}
            {userStats && (
                <div className="hidden md:flex flex-col items-end mr-6 pr-6 border-r border-slate-200">
                    <div className="text-xs font-bold text-slate-500 mb-1 flex items-center gap-1">
                        <Zap size={12} className={userStats.tokens_balance > 0 ? "text-amber-500" : "text-slate-400"}/>
                        {userStats.tokens_balance} Tokens Left
                    </div>
                    <div className="w-32 h-1.5 bg-slate-200 rounded-full overflow-hidden flex">
                        <div
                            className={`h-full ${userStats.tokens_balance > 100 ? 'bg-indigo-500' : userStats.tokens_balance > 0 ? 'bg-amber-500' : 'bg-red-500'}`}
                            style={{ width: `${Math.min((userStats.tokens_balance / 500) * 100, 100)}%` }}
                        ></div>
                    </div>
                    <div className="text-[10px] text-slate-400 mt-1">{userStats.totalRunsThisMonth} automated runs this month</div>
                    <a href="/pricing" className="text-[10px] text-blue-600 font-bold mt-0.5 hover:underline">Upgrade Plan →</a>
                </div>
            )}

            <div className="flex items-center gap-2 mr-2">
                {isSyncing ? (
                    <div className="flex items-center gap-1 text-emerald-600 text-xs font-bold animate-pulse">
                        <CheckCircle2 size={14} /> Cloud Sync
                    </div>
                ) : null}
            </div>
            <button
              onClick={handleSave}
              disabled={
                !selectedWorkspace ||
                isSaving ||
                nodes.some(n =>
                  n.type === 'trigger' &&
                  n.data?.triggerType === 'cron' &&
                  n.data?.cron &&
                  !/^(\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*\/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])) (\*|([0-9]|1[0-9]|2[0-3])|\*\/([0-9]|1[0-9]|2[0-3])) (\*|([1-9]|1[0-9]|2[0-9]|3[0-1])|\*\/([1-9]|1[0-9]|2[0-9]|3[0-1])) (\*|([1-9]|1[0-2])|\*\/([1-9]|1[0-2])) (\*|([0-6])|\*\/([0-6]))$/.test(n.data.cron as string)
                )
              }
              className="bg-slate-800 hover:bg-slate-900 text-white px-4 py-2 rounded-md font-medium text-sm transition-colors shadow-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <FileJson size={16} /> Save
            </button>
            <button
              onClick={handleRun}
              disabled={!selectedWorkspace || isExecuting || nodes.length === 0}
              title={nodes.length === 0 ? "Drag a node to the canvas to begin." : ""}
              className={`text-white px-5 py-2 rounded-md font-bold text-sm transition-colors shadow-md flex items-center gap-2 ${
                 (isExecuting || nodes.length === 0) ? "bg-emerald-800 opacity-70 cursor-not-allowed" : "bg-emerald-600 hover:bg-emerald-700 shadow-emerald-900/20"
              }`}
            >
              <Play size={16} /> {isExecuting ? "Executing..." : "▶ Run Workflow"}
            </button>
            <button
              onClick={async () => {
                  if (!selectedWorkspace || nodes.length === 0) { alert("Add nodes before publishing."); return; }

                  // Extract inputs: URLs that are empty in Scraper, Prompts that are empty in Gemini
                  const inputs: any[] = [];
                  nodes.forEach(n => {
                      if (n.type === 'scraper' && !n.data.url) { inputs.push({ id: n.id, type: 'url', label: 'Target URL' }); }
                      if (n.type === 'gemini' && !n.data.prompt) { inputs.push({ id: n.id, type: 'prompt', label: 'AI Prompt' }); }
                      if (n.type === 'agentic_loop' && !n.data.url) { inputs.push({ id: n.id, type: 'url', label: 'Target URL' }); }
                      if (n.type === 'webhook' && !n.data.url) { inputs.push({ id: n.id, type: 'url', label: 'Webhook URL' }); }
                  });

                  try {
                      const res = await fetch(`/api/workflows/${(selectedWorkspace as any).workflows && (selectedWorkspace as any).workflows.length > 0 ? (selectedWorkspace as any).workflows[0].id : ''}/publish`, { method: "POST", headers: { "Content-Type": "application/json", "x-user-id": currentUserId },
                          body: JSON.stringify({ isPublished: true, publishedInputs: inputs })
                      });
                      if(res.ok) {
                          alert("Published successfully!");
                          fetchWorkspaces();
                      } else {
                          alert("Failed to publish.");
                      }
                  } catch(e) { console.error(e); }
              }}
              className="text-white px-5 py-2 rounded-md font-bold text-sm transition-colors shadow-md flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 shadow-indigo-900/20"
            >
              🚀 Publish App
            </button>
          </div>
        </header>

        {/* Toolbar */}
        {activeTab === "editor" && (
            <div className="bg-slate-100 border-b border-slate-200 px-6 py-2 flex flex-wrap items-center gap-2 z-10 shadow-sm">
                <span className="text-sm font-bold text-slate-500 mr-2 uppercase tracking-wide">Nodes:</span>
                <button onClick={() => addNode('gemini')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-blue-50 text-blue-700 transition flex items-center gap-1"><Bot size={14}/> Gemini AI</button>
                <button onClick={() => addNode('scraper')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-amber-50 text-amber-700 transition flex items-center gap-1"><Globe size={14}/> Web Scraper</button>
                <button onClick={() => addNode('webhook')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-fuchsia-50 text-fuchsia-700 transition flex items-center gap-1"><Globe size={14}/> Webhook</button>
                <button onClick={() => addNode('router')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-yellow-50 text-yellow-700 transition flex items-center gap-1"><Repeat size={14}/> Router</button>
                <button onClick={() => addNode('approval')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-bold hover:bg-amber-100 text-amber-700 transition flex items-center gap-1">✋ Approval</button>
                <button onClick={() => addNode('file')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-emerald-50 text-emerald-700 transition flex items-center gap-1"><Database size={14}/> Upload File</button>
                <button onClick={() => addNode('agentic_loop')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-purple-50 text-purple-700 transition flex items-center gap-1"><Repeat size={14}/> Agent Loop</button>
                <button onClick={() => addNode('state')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-slate-200 text-slate-700 transition flex items-center gap-1"><Database size={14}/> Global State</button>
            </div>
        )}

        {/* Workspace Content Area */}
        <div className="flex-1 relative w-full h-full">
          {activeTab === 'cockpit' ? (
              <Cockpit />
          ) : (
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
                        setLogs([]);
                        if (selectedWorkspace) {
                            fetchWorkflowData(selectedWorkspace.id);
                        }
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
                         <div className="flex items-center gap-3">
                             {isExecuting && (
                                <button
                                    onClick={async () => {
                                        try {
                                            const taskId = localStorage.getItem('current_task_id');
                                            if (taskId) {
                                                await fetch(`http://127.0.0.1:5000/stop_task/${taskId}`, { method: 'POST' });
                                            } else {
                                                await fetch("http://127.0.0.1:5000/stop");
                                            }
                                            setIsExecuting(false);
                                        } catch (e) {}
                                    }}
                                    className="text-xs bg-rose-500/20 hover:bg-rose-500/30 text-rose-400 px-2 py-1 rounded transition flex items-center gap-1 font-bold"
                                >
                                    <XCircle size={12}/> ⏹ Stop Workflow
                                </button>
                             )}
                             <button onClick={() => setLogs([])} className="text-slate-500 hover:text-slate-300 transition-colors">✕</button>
                         </div>
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

             {/* Properties Panel Component */}
             {selectedNodeId && (
                <PropertiesPanel
                    selectedNodeId={selectedNodeId}
                    nodes={nodes}
                    updateNodeData={updateNodeData}
                    isPlaybackMode={isPlaybackMode}
                    setSelectedNodeId={setSelectedNodeId}
                    playbackRun={playbackRun}
                />
             )}
            </>
          )}
        </div>
      </main>
      {/* Account Modal */}
      {showAccountModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-2xl p-6 w-96 relative max-w-full">
                <button onClick={() => setShowAccountModal(false)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-600"><XCircle size={20}/></button>
                <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><Bot className="text-blue-500"/> Account Manager</h3>
                <p className="text-sm text-slate-500 mb-4">Initialize a browser session for a specific profile. This opens a visible browser so you can log into Google Gemini.</p>
                <div className="mb-4">
                    <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Profile Name/ID</label>
                    <input
                        type="text"
                        value={accountProfileStr}
                        onChange={e => setAccountProfileStr(e.target.value)}
                        className="w-full p-2 border rounded focus:ring-2 focus:ring-blue-500"
                        placeholder="e.g. 1, work, personal"
                    />
                </div>
                <button
                    onClick={async () => {
                        setIsLoggingIn(true);
                        try {
                            const res = await fetch(`/api/accounts/login?profile_id=${accountProfileStr}`, { method: 'POST' });
                            const data = await res.json();
                            if(data.status === 'success') {
                                alert(data.message);
                            } else {
                                alert("Error: " + data.message);
                            }
                        } catch(e) {
                            alert("Failed to reach backend.");
                        }
                        setIsLoggingIn(false);
                    }}
                    disabled={isLoggingIn}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition flex justify-center items-center gap-2"
                >
                    {isLoggingIn ? <Loader2 size={16} className="animate-spin"/> : <Globe size={16}/>}
                    Launch Headful Browser
                </button>
            </div>
        </div>
      )}
    </div>
  );
}
