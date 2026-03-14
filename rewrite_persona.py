import re

with open("app/page.tsx", "r") as f:
    content = f.read()

persona_html = """                       {node.type === 'gemini' && (
                         <div className="space-y-4">
                           <div>
                             <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">System Prompt (Persona)</label>
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
                         </div>
                       )}"""

# Replace the existing gemini render block
content = re.sub(r"                       \{node\.type === 'gemini' && \(\n                         <div>\n                           <div className=\"flex justify-between items-center mb-1\">(.*?)                         </div>\n                       \)\}", lambda m: persona_html, content, flags=re.DOTALL)

# Update compileNodesToSteps to include system_prompt
compile_mod = """        const base = {
            type: n.type === 'gemini' ? 'standard' : n.type,
            prompt: n.data.prompt || n.data.url || '',
            system_prompt: n.data.systemPrompt || '',
            new_chat: n.data.new_chat || false,"""

content = re.sub(r"        const base = \{\n            type: n\.type === 'gemini' \? 'standard' : n\.type,\n            prompt: n\.data\.prompt \|\| n\.data\.url \|\| '',\n            new_chat: n\.data\.new_chat \|\| false,", compile_mod, content)


with open("app/page.tsx", "w") as f:
    f.write(content)
