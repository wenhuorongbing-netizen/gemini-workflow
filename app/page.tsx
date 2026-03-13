"use client";

import { useState, useEffect } from "react";

interface Workspace {
  id: string;
  name: string;
  // Other properties exist but we only need these for the sidebar
}

export default function AppShell() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null);
  const [activeTab, setActiveTab] = useState<"editor" | "dashboard">("editor");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const fetchWorkspaces = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/epics");
      if (res.ok) {
        const data = await res.json();
        setWorkspaces(data);
        if (data.length > 0 && !selectedWorkspace) {
          setSelectedWorkspace(data[0]);
        }
      } else {
        console.error("Failed to fetch workspaces");
      }
    } catch (error) {
      console.error("Error fetching workspaces:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewWorkspace = async () => {
    const name = prompt("Enter a name for the new workspace:");
    if (!name) return;

    const id = Date.now().toString();
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/workspaces/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, steps: [], results: {} }),
      });
      if (res.ok) {
        fetchWorkspaces();
      }
    } catch (e) {
      console.error("Error creating workspace", e);
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 font-sans text-slate-800">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 flex-shrink-0">
        <div className="p-4 border-b border-slate-800 flex justify-between items-center">
          <h1 className="font-bold text-white text-lg tracking-tight">🤖 Gemini Builder</h1>
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
            workspaces.map((ws) => (
              <button
                key={ws.id}
                onClick={() => setSelectedWorkspace(ws)}
                className={`w-full text-left px-3 py-2 rounded-md transition-colors text-sm ${
                  selectedWorkspace?.id === ws.id
                    ? "bg-blue-600 text-white font-medium shadow-sm"
                    : "hover:bg-slate-800 hover:text-white"
                }`}
              >
                {ws.name}
              </button>
            ))
          )}
        </div>

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
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 h-16 flex items-center justify-between px-6 flex-shrink-0">
          <h2 className="text-xl font-semibold text-slate-800 truncate">
            {selectedWorkspace ? selectedWorkspace.name : "Select a Workspace"}
          </h2>

          <div className="flex items-center space-x-4">
            <button
              className="bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2 rounded-md font-medium text-sm transition-colors shadow-sm disabled:opacity-50"
              disabled={!selectedWorkspace}
            >
              ▶ Run Workflow
            </button>
          </div>
        </header>

        {/* View Toggles */}
        <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-center flex-shrink-0">
          <div className="flex bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => setActiveTab("editor")}
              className={`px-6 py-1.5 text-sm font-medium rounded-md transition-all ${
                activeTab === "editor"
                  ? "bg-white text-blue-600 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              Editor View
            </button>
            <button
              onClick={() => setActiveTab("dashboard")}
              className={`px-6 py-1.5 text-sm font-medium rounded-md transition-all ${
                activeTab === "dashboard"
                  ? "bg-white text-blue-600 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              Dashboard View
            </button>
          </div>
        </div>

        {/* Workspace Content Area */}
        <div className="flex-1 overflow-auto bg-gray-50 p-6">
          {!selectedWorkspace ? (
            <div className="h-full flex flex-col items-center justify-center text-gray-400">
              <div className="text-4xl mb-4">📝</div>
              <p className="text-lg">Select or create a workspace to get started</p>
            </div>
          ) : activeTab === "editor" ? (
            <div className="h-full flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-xl bg-white shadow-sm">
              <h3 className="text-xl font-medium text-slate-700 mb-2">Workflow Editor</h3>
              <p className="text-slate-500">(Coming in Next Sprint)</p>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-xl bg-white shadow-sm">
              <h3 className="text-xl font-medium text-slate-700 mb-2">Dashboard View</h3>
              <p className="text-slate-500">(Coming in Next Sprint)</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
