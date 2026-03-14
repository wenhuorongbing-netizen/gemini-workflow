import re

with open("app/page.tsx", "r") as f:
    content = f.read()

# 1. Frontend: Add Stop Sequence to Agent Loop properties
stop_seq = """                           <div>
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
                           </div>"""

content = re.sub(r"                           <div>\n                             <label className=\"block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1\">Context Reset Frequency</label>\n                             <input \n                               type=\"number\"\n                               min=\"1\"\n                               max=\"10\"\n                               className=\"w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500\"\n                               value=\{node\.data\.reset_threshold as number \|\| 3\}\n                               onChange=\{\(e\) => updateNodeData\(node\.id, \{ reset_threshold: parseInt\(e\.target\.value, 10\) \|\| 3 \}\)\}\n                               disabled=\{isPlaybackMode\}\n                             />\n                             <p className=\"text-\[10px\] text-slate-500 mt-1\">Clears DOM every N steps to prevent crashing\.</p>\n                           </div>", stop_seq, content)

# 2. Update compileNodesToSteps to include stop_sequence
compile_mod = """        if (n.type === 'agentic_loop') {
            return {
                ...base,
                id: n.id,
                chat_url: n.data.url || '',
                max_iterations: n.data.max_iterations || 3,
                reset_threshold: n.data.reset_threshold || 3,
                stop_sequence: n.data.stop_sequence || 'FINAL_REVIEW_COMPLETE'
            };
        }"""
content = content.replace("""        if (n.type === 'agentic_loop') {
            return {
                ...base,
                id: n.id,
                chat_url: n.data.url || '',
                max_iterations: n.data.max_iterations || 3,
                reset_threshold: n.data.reset_threshold || 3
            };
        }""", compile_mod)


# 3. Add Manual Override Button to floating log
stop_btn = """                     <div className="px-4 py-3 border-b border-slate-800 bg-slate-950 flex justify-between items-center shrink-0">
                         <div className="font-semibold text-sm flex items-center gap-2">
                             {isExecuting ? <Loader2 size={14} className="animate-spin text-blue-500"/> : <CheckCircle2 size={14} className="text-emerald-500"/>}
                             Execution Telemetry
                         </div>
                         <div className="flex items-center gap-3">
                             {isExecuting && (
                                <button
                                    onClick={async () => {
                                        try {
                                            await fetch("http://127.0.0.1:8000/stop");
                                        } catch (e) {}
                                    }}
                                    className="text-xs bg-rose-500/20 hover:bg-rose-500/30 text-rose-400 px-2 py-1 rounded transition flex items-center gap-1 font-bold"
                                >
                                    <XCircle size={12}/> Stop Execution
                                </button>
                             )}
                             <button onClick={() => setLogs([])} className="text-slate-500 hover:text-slate-300 transition-colors">✕</button>
                         </div>
                     </div>"""

content = re.sub(r"                     <div className=\"px-4 py-3 border-b border-slate-800 bg-slate-950 flex justify-between items-center shrink-0\">\n                         <div className=\"font-semibold text-sm flex items-center gap-2\">\n                             \{isExecuting \? <Loader2 size=\{14\} className=\"animate-spin text-blue-500\"/> : <CheckCircle2 size=\{14\} className=\"text-emerald-500\"/>\}\n                             Execution Telemetry\n                         </div>\n                         <button onClick=\{\(\) => setLogs\(\[\]\)\} className=\"text-slate-500 hover:text-slate-300 transition-colors\">✕</button>\n                     </div>", stop_btn, content)


with open("app/page.tsx", "w") as f:
    f.write(content)
