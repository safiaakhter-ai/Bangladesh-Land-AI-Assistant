"use client";

import React, { useState, useEffect } from 'react';

export default function Sidebar({
  activeTab,
  setActiveTab,
  activeSessionId,
  setActiveSessionId,
  onNewSession,
  onCloseMobile
}) {
  const [sessions, setSessions] = useState([]);
  const [searchFilter, setSearchFilter] = useState('');
  const [stats, setStats] = useState(null);

  const fetchSessions = async () => {
    try {
      const res = await fetch('/api/chats');
      const data = await res.json();
      setSessions(data || []);
    } catch (err) {
      console.error("Error fetching sessions:", err);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await fetch('/backend-api/telemetry');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.warn("Telemetry update note:", err.message);
    }
  };

  useEffect(() => {
    // Initial session hydration is intentional for this mounted sidebar.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchSessions();
    fetchStats();
    const interval = setInterval(fetchSessions, 6000);
    return () => clearInterval(interval);
  }, [activeSessionId]);

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    try {
      await fetch(`/api/chats/${sessionId}`, { method: 'DELETE' });
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
      }
      fetchSessions();
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  const filteredSessions = sessions.filter((s) =>
    (s.title || '').toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <aside className="w-80 md:w-84 bg-slate-950/95 backdrop-blur-xl border-r border-slate-800/80 flex flex-col justify-between h-full text-slate-200 shrink-0 select-none shadow-2xl">
      {/* Top Section */}
      <div className="p-4 space-y-4 overflow-y-auto flex-1 scrollbar-thin scrollbar-thumb-slate-800">
        {/* App Title & Brand */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-emerald-600 via-emerald-500 to-teal-400 flex items-center justify-center text-xl shadow-lg shadow-emerald-950/50 ring-1 ring-emerald-400/30">
              🇧🇩
            </div>
            <div>
              <h1 className="font-bold text-slate-100 text-sm tracking-tight flex items-center gap-1.5">
                ভূমি এআই সিস্টেম
              </h1>
              <div className="flex items-center gap-1.5 text-[11px] text-emerald-400 font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>ভূমি সহায় v1.0</span>
              </div>
            </div>
          </div>

          {onCloseMobile && (
            <button
              onClick={onCloseMobile}
              className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-white bg-slate-900 border border-slate-800"
            >
              ✕
            </button>
          )}
        </div>

        {/* Tab Navigation Buttons */}
        <div className="grid grid-cols-2 gap-1.5 bg-slate-900/90 p-1.5 rounded-xl border border-slate-800 text-xs">
          <button
            onClick={() => setActiveTab('chat')}
            className={`py-2 px-3 rounded-lg font-semibold transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'chat'
                ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-950/50'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <span>💬 এআই চ্যাট</span>
          </button>
          <button
            onClick={() => setActiveTab('records')}
            className={`py-2 px-3 rounded-lg font-semibold transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'records'
                ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-950/50'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <span>📂 ডাটাবেস</span>
          </button>
        </div>

        {/* New Chat Button */}
        {activeTab === 'chat' && (
          <button
            onClick={onNewSession}
            className="w-full bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-500/30 hover:border-emerald-400/60 text-emerald-300 hover:text-emerald-100 font-semibold py-2.5 px-4 rounded-xl transition-all shadow-md flex items-center justify-center gap-2 text-xs active:scale-[0.98] group"
          >
            <span className="text-emerald-400 group-hover:rotate-90 transition-transform">➕</span>
            <span>নতুন কথোপকথন শুরু করুন</span>
          </button>
        )}

        {/* Chat History List with Search */}
        {activeTab === 'chat' && (
          <div className="space-y-2 mt-4">
            <div className="flex items-center justify-between px-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                পূর্ববর্তী হিস্ট্রি ({sessions.length})
              </span>
            </div>

            {/* History Search Bar */}
            {sessions.length > 3 && (
              <div className="relative">
                <input
                  type="text"
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  placeholder="হিস্ট্রি খুঁজুন..."
                  className="w-full bg-slate-900/90 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500/60"
                />
                {searchFilter && (
                  <button
                    onClick={() => setSearchFilter('')}
                    className="absolute right-2 top-1.5 text-slate-500 hover:text-slate-300 text-xs"
                  >
                    ✕
                  </button>
                )}
              </div>
            )}

            <div className="space-y-1 mt-1 max-h-72 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-800 pr-1">
              {filteredSessions.length === 0 ? (
                <p className="text-xs text-slate-500 px-2 py-4 text-center">
                  {searchFilter ? 'কোনো ফলাফল পাওয়া যায়নি' : 'কোনো সংরক্ষিত হিস্ট্রি নেই'}
                </p>
              ) : (
                filteredSessions.map((s) => {
                  const isActive = s.session_id === activeSessionId;
                  return (
                    <div
                      key={s.session_id}
                      onClick={() => setActiveSessionId(s.session_id)}
                      className={`group flex items-center justify-between p-2.5 rounded-xl cursor-pointer text-xs transition-all ${
                        isActive
                          ? 'bg-gradient-to-r from-emerald-950/80 to-slate-900 text-emerald-300 font-semibold border border-emerald-500/40 shadow-sm'
                          : 'hover:bg-slate-900/80 text-slate-300 hover:text-slate-100 border border-transparent'
                      }`}
                    >
                      <span className="truncate flex-1 pr-2 flex items-center gap-1.5">
                        <span className="text-emerald-400/80 text-xs">💬</span>
                        <span className="truncate">{s.title || 'অনুসন্ধান'}</span>
                      </span>
                      <button
                        onClick={(e) => handleDeleteSession(e, s.session_id)}
                        className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 p-1 transition-all rounded hover:bg-slate-800"
                        title="মুছে ফেলুন"
                      >
                        🗑️
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>

      {/* Telemetry Stats Footer */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-950/80 shrink-0">
        <div className="bg-slate-900/90 border border-slate-800/80 rounded-xl p-3 text-xs space-y-2 shadow-inner">
          <div className="flex items-center justify-between pb-1 border-b border-slate-800/60 text-slate-400">
            <span className="font-semibold text-slate-300 text-[11px] uppercase tracking-wider">সিস্টেম মেমোরি ও ইনডেক্স</span>
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
          </div>
          <div className="flex justify-between items-center text-slate-400">
            <span>সংরক্ষিত খতিয়ান:</span>
            <strong className="text-emerald-400 font-mono">
              {typeof stats?.saved_details_count === "number" ? stats.saved_details_count.toLocaleString() : "—"}
            </strong>
          </div>
          <div className="flex justify-between items-center text-slate-400">
            <span>ইনডেক্সড মৌজা:</span>
            <strong className="text-teal-300 font-mono">
              {typeof stats?.mouzas_completed === "number" ? stats.mouzas_completed.toLocaleString() : "—"}
            </strong>
          </div>
        </div>
      </div>
    </aside>
  );
}

