import re

with open("app/page.tsx", "r") as f:
    content = f.read()

# 1. Add StateNode to imports and nodes
import_str = 'import { Play, Bot, Globe, Repeat, FileJson, Loader2, CheckCircle2, XCircle, Database } from "lucide-react";'
content = re.sub(r'import \{ Play, Bot, Globe, Repeat, FileJson, Loader2, CheckCircle2, XCircle \} from "lucide-react";', import_str, content)

statenode = """const StateNode = ({ data }: any) => (
  <BaseNode data={data} icon={Database} title="Global State" content={`${data.varName || "VAR_NAME"} = ${data.defaultValue || "..."}`} bgColor="bg-slate-700" borderColor="border-slate-500" />
);"""

content = content.replace("const AgentLoopNode =", statenode + "\n\nconst AgentLoopNode =")

nodetypes = """const nodeTypes = {
  trigger: TriggerNode,
  gemini: GeminiNode,
  scraper: ScraperNode,
  agentic_loop: AgentLoopNode,
  state: StateNode,
};"""

content = re.sub(r"const nodeTypes = \{(.*?)\};", lambda m: nodetypes, content, flags=re.DOTALL)


# 2. Add StateNode to Toolbar
btn = """                <button onClick={() => addNode('agentic_loop')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-purple-50 text-purple-700 transition flex items-center gap-1"><Repeat size={14}/> Agent Loop</button>
                <button onClick={() => addNode('state')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-slate-200 text-slate-700 transition flex items-center gap-1"><Database size={14}/> Global State</button>"""

content = content.replace("""                <button onClick={() => addNode('agentic_loop')} className="px-3 py-1.5 bg-white border border-slate-300 rounded text-sm font-medium hover:bg-purple-50 text-purple-700 transition flex items-center gap-1"><Repeat size={14}/> Agent Loop</button>""", btn)

# 3. Add Properties Panel logic
panel_logic = """                       {node.type === 'state' && (
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
                             Use `{{GLOBAL_VAR_NAME}}` in any prompt downstream to inject this value.
                           </div>
                         </div>
                       )}"""

content = content.replace("""                       {node.type === 'trigger' && (""", panel_logic + "\n\n" + """                       {node.type === 'trigger' && (""")

# 4. Modify Handle Run to extract metadata and pass it down
# Find the handleRun POST logic
run_mod = """      const stateNodes = nodes.filter(n => n.type === 'state');
      const global_state: Record<string, string> = {};
      stateNodes.forEach(n => {
          if (n.data.varName) {
              global_state[n.data.varName as string] = n.data.defaultValue as string || '';
          }
      });

      try {
        const response = await fetch("http://127.0.0.1:8000/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ steps: compiledSteps, workspace_id: selectedWorkspace?.id || "temp", profile_id: "1", global_state })
        });"""

content = re.sub(r"      try \{\n        const response = await fetch\(\"http://127\.0\.0\.1:8000/execute\", \{\n          method: \"POST\",\n          headers: \{ \"Content-Type\": \"application/json\" \},\n          body: JSON\.stringify\(\{ steps: compiledSteps, workspace_id: selectedWorkspace\?\.id \|\| \"temp\", profile_id: \"1\" \}\)\n        \}\);", run_mod, content)


with open("app/page.tsx", "w") as f:
    f.write(content)
