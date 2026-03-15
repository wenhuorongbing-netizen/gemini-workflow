import sys

with open('app/apps/[workflowId]/page.tsx', 'r') as f:
    content = f.read()

replacement = '''                             {recentRuns.map(run => {
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
                                            <span className={`text-xs font-bold px-2 py-1 rounded ${run.status === 'Workflow Finished' || run.status === 'Complete' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                                                {run.status === 'Workflow Finished' ? 'Success' : 'Failed'}
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
                                 </div>
                             )})}'''

target = '''                             {recentRuns.map(run => (
                                 <div key={run.id} className="p-6">
                                     <div className="flex justify-between items-center mb-4">
                                         <span className={`text-xs font-bold px-2 py-1 rounded ${run.status === 'Workflow Finished' || run.status === 'Complete' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                                             {run.status === 'Workflow Finished' ? 'Success' : 'Failed'}
                                         </span>
                                         <span className="text-xs text-slate-400 font-mono">
                                             {new Date(run.createdAt).toLocaleString()}
                                         </span>
                                     </div>
                                     <div className="text-sm text-slate-600 bg-slate-50 p-4 rounded-lg font-mono overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
                                         {(() => {
                                             try {
                                                 const results = JSON.parse(run.results);
                                                 // Try to find the last step's result if it exists, otherwise dump all
                                                 const keys = Object.keys(results);
                                                 if (keys.length > 0) return results[keys[keys.length - 1]];
                                                 return "No results recorded.";
                                             } catch(e) {
                                                 return "Could not parse results.";
                                             }
                                         })()}
                                     </div>
                                 </div>
                             ))}'''

content = content.replace(target, replacement)

with open('app/apps/[workflowId]/page.tsx', 'w') as f:
    f.write(content)
