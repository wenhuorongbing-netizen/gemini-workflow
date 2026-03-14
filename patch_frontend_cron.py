with open("app/page.tsx", "r") as f:
    content = f.read()

props_old = """            {node.type === 'trigger' && (
              <div className="text-sm text-slate-500 italic">
                Trigger nodes are the starting point of the execution graph. No configuration needed.
              </div>
            )}"""

props_new = """            {node.type === 'trigger' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Trigger Type</label>
                  <select
                    className="w-full bg-slate-900 border border-slate-700 rounded-md p-2 text-sm text-slate-300"
                    value={node.data.triggerType || 'manual'}
                    onChange={(e) => updateNodeData(node.id, 'triggerType', e.target.value)}
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
                      className="w-full bg-slate-900 border border-slate-700 rounded-md p-2 text-sm text-slate-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                      value={(node.data.cron as string) || ""}
                      onChange={(e) => updateNodeData(node.id, 'cron', e.target.value)}
                      placeholder="e.g., */5 * * * *"
                    />
                    <div className="text-xs text-slate-500 mt-1 mt-2">
                        Use standard cron format. e.g. "0 0 * * *" for daily at midnight.
                        Saves to the backend automatically.
                    </div>
                  </div>
                )}
              </div>
            )}"""

if props_old in content:
    content = content.replace(props_old, props_new)

with open("app/page.tsx", "w") as f:
    f.write(content)
