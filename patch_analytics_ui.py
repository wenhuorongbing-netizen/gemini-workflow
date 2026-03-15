import sys

with open('app/page.tsx', 'r') as f:
    content = f.read()

replacement = '''          <div className="flex items-center gap-4">
            <h2 className="text-xl font-bold text-slate-800 truncate">
              {selectedWorkspace ? selectedWorkspace.name : "Select a Workspace"}
            </h2>

            {/* User Switcher Dropdown */}
            <select
                value={currentUserId}
                onChange={e => setCurrentUserId(e.target.value)}
                className="ml-4 text-xs border-slate-300 rounded px-2 py-1 bg-slate-100 text-slate-600 focus:ring-blue-500 font-medium"
            >
                <option value="user1">User 1 (Free)</option>
                <option value="user2">User 2 (Team)</option>
                <option value="user3">User 3 (Enterprise)</option>
            </select>
          </div>

          <div className="flex items-center space-x-4">
            {/* Token Analytics Widget */}
            {userStats && (
                <div className="hidden md:flex flex-col items-end mr-6 pr-6 border-r border-slate-200">
                    <div className="text-xs font-bold text-slate-500 mb-1 flex items-center gap-1">
                        <Zap size={12} className={userStats.tokens_balance > 0 ? "text-amber-500" : "text-slate-400"}/>
                        {userStats.tokens_balance} Tokens Left
                    </div>
                    <div className="w-32 h-1.5 bg-slate-200 rounded-full overflow-hidden flex">
                        <div
                            className={`h-full ${userStats.tokens_balance > 100 ? 'bg-indigo-500' : userStats.tokens_balance > 0 ? 'bg-amber-500' : 'bg-red-500'}`}
                            style={{ width: `${Math.min((userStats.tokens_balance / 500) * 100, 100)}%` }}
                        ></div>
                    </div>
                    <div className="text-[10px] text-slate-400 mt-1">{userStats.totalRunsThisMonth} automated runs this month</div>
                    <a href="/pricing" className="text-[10px] text-blue-600 font-bold mt-0.5 hover:underline">Upgrade Plan →</a>
                </div>
            )}

            <div className="flex items-center gap-2 mr-2">'''

target = '''          <div className="flex items-center gap-4">
            <h2 className="text-xl font-bold text-slate-800 truncate">
              {selectedWorkspace ? selectedWorkspace.name : "Select a Workspace"}
            </h2>

          </div>

          <div className="flex items-center space-x-3">
            <div className="flex items-center gap-2 mr-2">'''

content = content.replace(target, replacement)

with open('app/page.tsx', 'w') as f:
    f.write(content)
