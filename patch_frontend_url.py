import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Replace Scraper Target URL
old_scraper_url = """                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Target URL</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                  value={node.data.url as string || ''}
                  onChange={(e) => updateNodeData(node.id, { url: e.target.value })}
                    disabled={isPlaybackMode}
                />"""

new_scraper_url = """                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Target URL</label>
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
                />
                {(node.data.url && !(node.data.url as string).startsWith('http://') && !(node.data.url as string).startsWith('https://')) && (
                    <div className="text-xs text-red-500 mt-1 flex items-center gap-1">
                        <AlertCircle size={12}/> ⚠️ Must start with http:// or https://
                    </div>
                )}"""
content = content.replace(old_scraper_url, new_scraper_url)

# Replace Agent Loop Repo/Target URL
old_agent_url = """                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Repository/Target URL</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                    value={node.data.url as string || ''}
                    onChange={(e) => updateNodeData(node.id, { url: e.target.value })}
                    disabled={isPlaybackMode}
                  />
                </div>"""

new_agent_url = """                <div>
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
                  />
                  {(node.data.url && !(node.data.url as string).startsWith('http://') && !(node.data.url as string).startsWith('https://')) && (
                      <div className="text-xs text-red-500 mt-1 flex items-center gap-1">
                          <AlertCircle size={12}/> ⚠️ Must start with http:// or https://
                      </div>
                  )}
                </div>"""
content = content.replace(old_agent_url, new_agent_url)

with open('app/page.tsx', 'w') as f:
    f.write(content)
