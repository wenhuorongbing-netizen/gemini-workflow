"use client";

import React, { useState } from 'react';

export default function Dashboard() {
  const [p1Bet, setP1Bet] = useState(0);
  const [p2Bet, setP2Bet] = useState(0);

  return (
    <div className="p-8">
      <h1 className="text-3xl text-white font-bold mb-8">Match Dashboard</h1>

      {/* FGC MatchCard Skeleton */}
      <div className="relative w-full h-40 flex overflow-hidden mb-6 group" style={{ clipPath: 'polygon(15px 0, 100% 0, 100% calc(100% - 15px), calc(100% - 15px) 100%, 0 100%, 0 15px)' }}>
        {/* Player 1 Side (Red) */}
        <div className="w-1/2 h-full bg-gradient-to-r from-red-900/80 to-red-950/20 flex flex-col justify-center pl-6 border-b-4 border-red-600">
          <div className="text-white text-2xl font-bold flex items-center gap-4">
            <div className="w-16 h-16 bg-red-600 rounded-full flex items-center justify-center font-bold text-xl">P1</div>
            <div>
              <p>Player 1</p>
              <p className="text-sm text-red-300 font-mono">Betting Limit: $500</p>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-sm text-red-200">Bet: $</span>
                <input
                  type="number"
                  value={p1Bet}
                  onChange={(e) => setP1Bet(Number(e.target.value))}
                  className="w-24 bg-red-950/50 border border-red-500 rounded px-2 py-1 text-sm text-white font-mono"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Player 2 Side (Blue) */}
        <div className="w-1/2 h-full bg-gradient-to-l from-blue-900/80 to-blue-950/20 flex flex-col justify-center items-end pr-6 border-b-4 border-blue-600">
          <div className="text-white text-2xl font-bold flex items-center gap-4">
            <div className="text-right">
              <p>Player 2</p>
              <p className="text-sm text-blue-300 font-mono">Betting Limit: $500</p>
              <div className="mt-2 flex items-center gap-2 justify-end">
                <span className="text-sm text-blue-200">Bet: $</span>
                <input
                  type="number"
                  value={p2Bet}
                  onChange={(e) => setP2Bet(Number(e.target.value))}
                  className="w-24 bg-blue-950/50 border border-blue-500 rounded px-2 py-1 text-sm text-white font-mono"
                />
              </div>
            </div>
            <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center font-bold text-xl">P2</div>
          </div>
        </div>

        {/* The Absolute FGC Center "VS" */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-5xl font-black italic text-neutral-200 drop-shadow-[0_0_10px_rgba(255,255,255,0.8)] -skew-x-12 z-10 pointer-events-none">
          VS
        </div>
      </div>

      {/* Skewed Buttons */}
      <div className="flex gap-4 mb-8">
          <button className="bg-[#D91616] text-white font-black italic text-xl px-8 py-3 -skew-x-12 hover:bg-white hover:text-black transition-colors cursor-pointer"><div className="skew-x-12">LET'S ROCK</div></button>
          <button className="bg-[#D91616] text-white font-black italic text-xl px-8 py-3 -skew-x-12 hover:bg-white hover:text-black transition-colors cursor-pointer"><div className="skew-x-12">SLASH!</div></button>
      </div>

      {/* Admin Panel */}
      <div className="bg-slate-900 p-8 border-t-4 border-[#39FF14] [clip-path:polygon(20px_0,100%_0,100%_calc(100%-20px),calc(100%-20px)_100%,0_100%,0_20px)] mb-8">
          <h2 className="text-xl text-[#39FF14] font-mono mb-4">Admin Panel</h2>
          <div className="text-slate-300 font-mono">
              Admin logs here... System initialized. Waiting for match input.
          </div>
      </div>

      {/* Leaderboard */}
      <div className="bg-slate-900 p-8 border-t-4 border-red-600 [clip-path:polygon(20px_0,100%_0,100%_calc(100%-20px),calc(100%-20px)_100%,0_100%,0_20px)]">
          <h2 className="text-xl text-red-500 font-mono mb-4">Leaderboard</h2>
          <div className="text-slate-300">
              <ul>
                  <li className="flex justify-between py-2 border-b border-slate-700">
                      <span>Player 1</span>
                      <span className="font-mono text-red-400">1500 MMR</span>
                  </li>
                  <li className="flex justify-between py-2 border-b border-slate-700">
                      <span>Player 2</span>
                      <span className="font-mono text-blue-400">1450 MMR</span>
                  </li>
              </ul>
          </div>
      </div>

    </div>
  )
}
