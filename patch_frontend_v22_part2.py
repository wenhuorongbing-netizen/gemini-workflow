import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Let's add the Publish button next to "Run Workflow"
run_btn = """              <Play size={16} /> {isExecuting ? "Executing..." : "▶ Run Workflow"}
            </button>
          </div>
        </header>"""

new_run_btn = """              <Play size={16} /> {isExecuting ? "Executing..." : "▶ Run Workflow"}
            </button>
            <button
              onClick={async () => {
                  if (!selectedWorkspace || nodes.length === 0) { alert("Add nodes before publishing."); return; }

                  // Extract inputs: URLs that are empty in Scraper, Prompts that are empty in Gemini
                  const inputs = [];
                  nodes.forEach(n => {
                      if (n.type === 'scraper' && !n.data.url) { inputs.push({ id: n.id, type: 'url', label: 'Target URL' }); }
                      if (n.type === 'gemini' && !n.data.prompt) { inputs.push({ id: n.id, type: 'prompt', label: 'AI Prompt' }); }
                      if (n.type === 'agentic_loop' && !n.data.url) { inputs.push({ id: n.id, type: 'url', label: 'Target URL' }); }
                  });

                  try {
                      const res = await fetch(`/api/workflows/${selectedWorkspace.id}/publish`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
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
        </header>"""

if run_btn in content:
    content = content.replace(run_btn, new_run_btn)


# And update Dashboard view to render App Cards
# Search for:   return (
#     <div className="flex-1 bg-white flex items-center justify-center p-8 overflow-y-auto">
dashboard = """  if (!selectedWorkspace) {
    return (
      <div className="flex-1 bg-white flex items-center justify-center p-8 overflow-y-auto">
        <div className="text-center max-w-lg">
          <div className="bg-blue-50 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6">
            <Bot size={40} className="text-blue-500" />
          </div>
          <h2 className="text-3xl font-bold text-slate-800 mb-4 tracking-tight">Gemini Workflow Builder</h2>
          <p className="text-slate-500 mb-8 leading-relaxed">
            Create multi-agent automation chains. Drag and drop visual nodes to build powerful workflows utilizing Google's Gemini models.
          </p>
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 text-left shadow-sm">
            <h3 className="font-semibold text-slate-800 mb-3 flex items-center gap-2">
              <span className="bg-blue-100 text-blue-700 w-6 h-6 rounded-full flex items-center justify-center text-xs">1</span>
              Create a Workspace
            </h3>
            <p className="text-sm text-slate-500 mb-4 ml-8">Click "+ New Workspace" in the sidebar to begin.</p>

            <h3 className="font-semibold text-slate-800 mb-3 flex items-center gap-2">
              <span className="bg-blue-100 text-blue-700 w-6 h-6 rounded-full flex items-center justify-center text-xs">2</span>
              Add Nodes
            </h3>
            <p className="text-sm text-slate-500 mb-4 ml-8">Add Gemini AI, Web Scrapers, File Uploads, or Agentic Loops to the canvas.</p>

            <h3 className="font-semibold text-slate-800 flex items-center gap-2">
              <span className="bg-blue-100 text-blue-700 w-6 h-6 rounded-full flex items-center justify-center text-xs">3</span>
              Run Automation
            </h3>
            <p className="text-sm text-slate-500 mt-2 ml-8">Link nodes together and execute your custom multi-agent pipeline.</p>
          </div>
        </div>
      </div>
    );
  }"""

new_dashboard = """  if (!selectedWorkspace) {
    const publishedWorkspaces = workspaces.filter(w => w.workflows && w.workflows.length > 0 && w.workflows[0].isPublished);
    return (
      <div className="flex-1 bg-slate-50 flex flex-col p-8 overflow-y-auto">
        <div className="max-w-6xl mx-auto w-full">
            <div className="text-center mb-12">
                <div className="bg-blue-100 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 shadow-inner">
                    <Bot size={40} className="text-blue-600" />
                </div>
                <h2 className="text-4xl font-extrabold text-slate-900 mb-4 tracking-tight">AI App Store</h2>
                <p className="text-slate-600 text-lg max-w-2xl mx-auto leading-relaxed">
                    Discover and launch automated workflows published by the community. Minimalist interfaces for powerful multi-agent automations.
                </p>
            </div>

            {publishedWorkspaces.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {publishedWorkspaces.map(ws => (
                        <div key={ws.id} className="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-xl transition-all p-6 flex flex-col group">
                            <h3 className="text-xl font-bold text-slate-800 mb-2 group-hover:text-blue-600 transition-colors">{ws.name}</h3>
                            <p className="text-sm text-slate-500 flex-1 mb-6">
                                A predefined AI workflow. Setup variables and launch immediately.
                            </p>
                            <a href={`/apps/${ws.workflows[0].id}`} className="w-full block text-center bg-slate-900 hover:bg-slate-800 text-white font-medium py-2.5 rounded-lg transition-colors">
                                Launch App
                            </a>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="text-center p-12 bg-white rounded-2xl border border-slate-200 border-dashed shadow-sm">
                    <p className="text-slate-500 mb-4">No applications published yet.</p>
                    <p className="text-sm text-slate-400">Create a workspace, build a workflow, and click 'Publish App' to see it here.</p>
                </div>
            )}
        </div>
      </div>
    );
  }"""

if dashboard in content:
    content = content.replace(dashboard, new_dashboard)

with open('app/page.tsx', 'w') as f:
    f.write(content)
