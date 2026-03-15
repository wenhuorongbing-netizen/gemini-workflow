import sys
import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# 1. Add WebhookNode component
import_target = '''const FileNode = ({ data, id }: any) => (
  <div className="bg-slate-800 border border-emerald-600 rounded-xl shadow-lg w-64 overflow-hidden relative group">'''

webhook_comp = '''const WebhookNode = ({ data, id }: any) => (
  <div className="bg-slate-800 border border-fuchsia-600 rounded-xl shadow-lg w-64 overflow-hidden relative group">
    <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-fuchsia-500" />
    <div className="px-4 py-2 border-b border-fuchsia-700/50 flex justify-between items-center font-semibold tracking-wide text-fuchsia-100 bg-fuchsia-900/30">
      <div className="flex items-center gap-2"><Globe size={18}/><span>Webhook</span></div>
    </div>
    <div className="p-4 flex-1 text-sm bg-slate-900/50 relative">
      <div className="text-slate-300 truncate">{data.url || "URL missing"}</div>
      <div className="text-xs text-slate-500 mt-1 truncate">{data.prompt || "Payload template"}</div>
    </div>
    <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-fuchsia-500" />
  </div>
);

const FileNode = ({ data, id }: any) => (
  <div className="bg-slate-800 border border-emerald-600 rounded-xl shadow-lg w-64 overflow-hidden relative group">'''

content = content.replace(import_target, webhook_comp)

# 2. Add to nodeTypes
nodeTypes_target = '''const nodeTypes = {
  trigger: TriggerNode,
  gemini: GeminiNode,
  scraper: ScraperNode,
  agentic_loop: AgentLoopNode,
  state: StateNode,
  file: FileNode,
};'''

nodeTypes_rep = '''const nodeTypes = {
  trigger: TriggerNode,
  gemini: GeminiNode,
  scraper: ScraperNode,
  agentic_loop: AgentLoopNode,
  state: StateNode,
  file: FileNode,
  webhook: WebhookNode,
};'''

content = content.replace(nodeTypes_target, nodeTypes_rep)


# 3. Add to compileNodesToSteps mapping
compile_target = '''    if (n.type === 'agentic_loop') {
        step.chat_url = n.data.url as string || '';
        step.max_iterations = n.data.max_iterations as number || 3;
        step.reset_threshold = n.data.reset_threshold as number || 3;
        step.stop_sequence = n.data.stop_sequence as string || 'FINAL_REVIEW_COMPLETE';
    }'''

compile_rep = '''    if (n.type === 'agentic_loop') {
        step.chat_url = n.data.url as string || '';
        step.max_iterations = n.data.max_iterations as number || 3;
        step.reset_threshold = n.data.reset_threshold as number || 3;
        step.stop_sequence = n.data.stop_sequence as string || 'FINAL_REVIEW_COMPLETE';
    }
    if (n.type === 'webhook') {
        step.chat_url = n.data.url as string || '';
        step.prompt = n.data.prompt as string || '{}';
    }'''

content = content.replace(compile_target, compile_rep)

# 4. Add UI Panel support
ui_target = '''            {node.type === 'scraper' && ('''

ui_rep = '''            {node.type === 'webhook' && (
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

            {node.type === 'scraper' && ('''

content = content.replace(ui_target, ui_rep)


# 5. Add button to Toolbar
toolbar_target = '''<button onClick={() => addNode('scraper')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-amber-50 text-amber-700 transition flex items-center gap-1"><Globe size={14}/> Web Scraper</button>'''

toolbar_rep = '''<button onClick={() => addNode('scraper')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-amber-50 text-amber-700 transition flex items-center gap-1"><Globe size={14}/> Web Scraper</button>
                <button onClick={() => addNode('webhook')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-fuchsia-50 text-fuchsia-700 transition flex items-center gap-1"><Globe size={14}/> Webhook</button>'''

content = content.replace(toolbar_target, toolbar_rep)


# 6. Add webhook mapping to publish builder inputs
publish_target = '''                      if (n.type === 'agentic_loop' && !n.data.url) { inputs.push({ id: n.id, type: 'url', label: 'Target URL' }); }'''

publish_rep = '''                      if (n.type === 'agentic_loop' && !n.data.url) { inputs.push({ id: n.id, type: 'url', label: 'Target URL' }); }
                      if (n.type === 'webhook' && !n.data.url) { inputs.push({ id: n.id, type: 'url', label: 'Webhook URL' }); }'''

content = content.replace(publish_target, publish_rep)

with open('app/page.tsx', 'w') as f:
    f.write(content)
