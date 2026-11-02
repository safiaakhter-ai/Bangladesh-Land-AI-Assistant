'use client';

import { useState, useEffect } from 'react';
import Sidebar from '../components/Sidebar';
import ChatWindow from '../components/ChatWindow';
import RecordBrowser from '../components/RecordBrowser';
import TelemetryBanner from '../components/TelemetryBanner';

export default function Home() {
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' or 'records'
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Load existing session or auto-create one
  useEffect(() => {
    fetch('/api/chats')
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setActiveSessionId(data[0].session_id);
        }
      })
      .catch((err) => console.error("Error loading sessions on mount:", err));
  }, []);

  const handleNewSession = async () => {
    try {
      const res = await fetch('/api/chats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'নতুন তথ্য অনুসন্ধান' })
      });
      const data = await res.json();
      setActiveSessionId(data.session_id);
      setActiveTab('chat');
      setSidebarOpen(false);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  return (
    <main className="w-screen h-screen flex flex-col overflow-hidden bg-slate-950 text-slate-100 antialiased">
      {/* Top Telemetry & Status Bar */}
      <TelemetryBanner />

      {/* Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Mobile Sidebar Backdrop */}
        {sidebarOpen && (
          <div
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden transition-opacity"
          />
        )}

        {/* Sidebar Navigation (Desktop & Mobile Drawer) */}
        <div
          className={`fixed inset-y-0 left-0 z-50 md:static md:z-auto transition-transform duration-300 ease-in-out md:translate-x-0 ${
            sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <Sidebar
            activeTab={activeTab}
            setActiveTab={(tab) => {
              setActiveTab(tab);
              setSidebarOpen(false);
            }}
            activeSessionId={activeSessionId}
            setActiveSessionId={(id) => {
              setActiveSessionId(id);
              setActiveTab('chat');
              setSidebarOpen(false);
            }}
            onNewSession={handleNewSession}
            onCloseMobile={() => setSidebarOpen(false)}
          />
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col h-full overflow-hidden relative">
          {/* Mobile Header Bar with Hamburger */}
          <div className="md:hidden flex items-center justify-between p-3 bg-slate-900 border-b border-slate-800 shrink-0">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-2 rounded-lg bg-slate-800 text-slate-200 hover:text-white border border-slate-700 flex items-center gap-2 text-xs font-semibold"
            >
              <span>☰ মেনু</span>
            </button>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="font-bold text-xs text-emerald-400">ভূমি রেকর্ড এআই</span>
            </div>
            <button
              onClick={handleNewSession}
              className="p-2 rounded-lg bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 text-xs font-semibold"
            >
              ➕ নতুন
            </button>
          </div>

          {/* Active View */}
          <div className="flex-1 h-full overflow-hidden">
            {activeTab === 'chat' ? (
              <ChatWindow
                activeSessionId={activeSessionId}
                onSessionTitleUpdate={(newId) => setActiveSessionId(newId)}
              />
            ) : (
              <RecordBrowser />
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

