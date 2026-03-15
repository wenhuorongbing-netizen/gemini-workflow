import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# 1. Manage Accounts Button
account_btn = """          <h1 className="font-bold text-white text-lg tracking-tight flex items-center gap-2">
            <Bot size={20} className="text-blue-500" />
            Gemini Builder
          </h1>"""

new_account_btn = """          <h1 className="font-bold text-white text-lg tracking-tight flex items-center gap-2">
            <Bot size={20} className="text-blue-500" />
            Gemini Builder
          </h1>
          <button onClick={() => setShowAccountModal(true)} className="text-xs bg-slate-800 text-slate-300 px-2 py-1 rounded hover:bg-slate-700 transition">
              👤 Accounts
          </button>"""

if account_btn in content:
    content = content.replace(account_btn, new_account_btn)

# 2. Add Modal State
modal_state = """  const [selectedWorkspace, setSelectedWorkspace] = useState<any | null>(null);"""
new_modal_state = """  const [selectedWorkspace, setSelectedWorkspace] = useState<any | null>(null);
  const [showAccountModal, setShowAccountModal] = useState(false);
  const [accountProfileStr, setAccountProfileStr] = useState("1");
  const [isLoggingIn, setIsLoggingIn] = useState(false);"""

if modal_state in content:
    content = content.replace(modal_state, new_modal_state)

# 3. Add Attachment and Model to Gemini Properties Panel
old_gemini_props = """                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Account Profile</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={node.data.profileId as string || '1'}
                    onChange={(e) => updateNodeData(node.id, { profileId: e.target.value })}
                    disabled={isPlaybackMode}
                  />
                  <div className="text-[10px] text-slate-500 mt-1">Isolates browser session (e.g. '1', 'work', 'personal').</div>
                </div>"""

new_gemini_props = """                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Account Profile</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={node.data.profileId as string || '1'}
                    onChange={(e) => updateNodeData(node.id, { profileId: e.target.value })}
                    disabled={isPlaybackMode}
                  />
                  <div className="text-[10px] text-slate-500 mt-1">Isolates browser session (e.g. '1', 'work', 'personal').</div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Model Selection</label>
                  <select
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                    value={node.data.model as string || 'Auto'}
                    onChange={(e) => updateNodeData(node.id, { model: e.target.value })}
                    disabled={isPlaybackMode}
                  >
                      <option value="Auto">Auto (Default)</option>
                      <option value="Gemini 1.5 Flash">Gemini 1.5 Flash</option>
                      <option value="Gemini 1.5 Pro">Gemini 1.5 Pro</option>
                      <option value="Advanced">Advanced (if subscribed)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1 flex justify-between items-center">
                      Attachments
                      {!isPlaybackMode && (
                        <label className="cursor-pointer text-blue-600 hover:text-blue-700 flex items-center gap-1 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                            📎 Upload
                            <input
                                type="file"
                                className="hidden"
                                onChange={async (e) => {
                                    if(e.target.files && e.target.files[0]) {
                                        const file = e.target.files[0];
                                        const formData = new FormData();
                                        formData.append("file", file);
                                        try {
                                            const res = await fetch("http://127.0.0.1:8000/api/upload", { method: "POST", body: formData });
                                            const data = await res.json();
                                            if (data.status === "success") {
                                                const currentAtt = (node.data.attachments as string[]) || [];
                                                updateNodeData(node.id, { attachments: [...currentAtt, data.path] });
                                            }
                                        } catch(err) { console.error("Upload failed", err); }
                                    }
                                }}
                            />
                        </label>
                      )}
                  </label>
                  {(node.data.attachments as string[])?.length > 0 && (
                      <div className="text-xs text-slate-600 bg-slate-50 p-2 rounded border">
                          {(node.data.attachments as string[]).map((att, i) => (
                              <div key={i} className="truncate" title={att}>📎 {att.split('/').pop()}</div>
                          ))}
                          {!isPlaybackMode && (
                            <button onClick={() => updateNodeData(node.id, { attachments: [] })} className="text-red-500 mt-1 hover:underline">Clear</button>
                          )}
                      </div>
                  )}
                </div>"""

if old_gemini_props in content:
    content = content.replace(old_gemini_props, new_gemini_props)


# 4. Account Modal HTML + Publish App logic
# Let's add the Account modal at the bottom.
account_modal = """      {/* Account Modal */}
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
                            const res = await fetch(`http://127.0.0.1:8000/api/accounts/login?profile_id=${accountProfileStr}`, { method: 'POST' });
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
      )}"""

content = content.replace("    </div>\n  );\n}\n", account_modal + "\n    </div>\n  );\n}\n")


with open('app/page.tsx', 'w') as f:
    f.write(content)
