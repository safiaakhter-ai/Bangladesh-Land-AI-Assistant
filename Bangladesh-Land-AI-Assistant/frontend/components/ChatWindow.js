"use client";

import React, { useState, useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';
import RecordCard from './RecordCard';

const DigitalMouzaMap = dynamic(() => import('./DigitalMouzaMap'), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full min-h-[450px] flex flex-col items-center justify-center bg-slate-950/80 text-slate-300 rounded-2xl border border-slate-800 backdrop-blur-md">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-emerald-500 mb-3"></div>
      <span className="text-sm font-medium text-emerald-400">ডিজিটাল মৌজা ম্যাপ লোড হচ্ছে...</span>
      <span className="text-xs text-slate-500 mt-1">দাগ ও জ্যামিতিক মানচিত্র প্রস্তুত করা হচ্ছে</span>
    </div>
  ),
});

const STARTER_PROMPTS = [
  {
    icon: "📜",
    title: "খতিয়ান ও রেকর্ড অনুসন্ধান",
    desc: "ভাট বাড়িয়া মৌজার খতিয়ান ৩ বা নির্দিষ্ট খতিয়ানের বিবরণ",
    prompt: "ভাট বাড়িয়া মৌজার খতিয়ান ৩ এর বিস্তারিত বিবরণ দিন"
  },
  {
    icon: "👤",
    title: "দাগ ও মালিকানা যাচাই",
    desc: "দাগ নম্বর ৭৪ এর মালিক কে এবং মোট জমির পরিমাণ কত?",
    prompt: "দাগ নম্বর ৭৪ এর মালিক কে এবং জমিতে কার কত অংশ রয়েছে?"
  },
  {
    icon: "📝",
    title: "ই-নামজারি ও মিউটেশন",
    desc: "অনলাইনে নামজারি আবেদন প্রক্রিয়া ও প্রয়োজনীয় কাগজপত্র",
    prompt: "অনলাইনে ই-নামজারি করার নিয়মাবলী ও প্রয়োজনীয় কাগজপত্র কী কী?"
  },
  {
    icon: "🏛️",
    title: "সিএস/আরএস/বিএস পার্থক্য",
    desc: "বিভিন্ন জরিপ রেকর্ডের আইনি গুরুত্ব ও পার্থক্য কী?",
    prompt: "সিএস (CS), আরএস (RS) ও বিএস (BS) খতিয়ানের মধ্যে আইনি পার্থক্য কী?"
  }
];

export default function ChatWindow({ activeSessionId, onSessionTitleUpdate }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' or 'map'
  const [activePlot, setActivePlot] = useState('74');
  const [activeMouzaCode, setActiveMouzaCode] = useState('201294082069');
  const [targetRecord, setTargetRecord] = useState(null);
  const [copiedIndex, setCopiedIndex] = useState(null);
  
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const handleViewRecordOnMap = (record) => {
    const d = record.details || record;
    const sp = record.spatial_info || {};
    const dags = d.DAGS || "";
    const firstPlot = sp.plot_no || (typeof dags === 'string' ? dags.replace("...", "").split(",")[0].trim() : dags);
    const targetMouza = sp.mauza_code || '201294082069';

    if (firstPlot) {
      setActivePlot(firstPlot);
    }
    if (targetMouza) {
      setActiveMouzaCode(targetMouza);
    }
    setTargetRecord(record);
    setActiveTab('map');
  };

  useEffect(() => {
    let cancelled = false;
    async function syncSession() {
      if (!activeSessionId) {
        if (!cancelled) setMessages([]);
        return;
      }
      try {
        const response = await fetch(`/api/chats/${activeSessionId}`);
        if (!response.ok) throw new Error("Cannot load session");
        const data = await response.json();
        if (!cancelled) setMessages(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error("Failed to load session messages:", error);
      }
    }
    syncSession();
    return () => { cancelled = true; };
  }, [activeSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleCopy = (text, index) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handlePinDrop = async (lat, lon, spatialMeta = {}) => {
    const customPrompt = spatialMeta.custom_prompt || `📍 দাগ নম্বর ${spatialMeta.plot_no && spatialMeta.plot_no !== 'N/A' ? spatialMeta.plot_no : ''} (${spatialMeta.mouza_name || 'মৌজা'} - ${lat.toFixed(4)}, ${lon.toFixed(4)}) চিহ্নিত করা হয়েছে`;
    
    // Immediately switch to chat tab so the user sees their prompt and response loading
    setActiveTab('chat');
    
    // Immediately display user message in the chat feed
    const userMsg = { sender: 'user', content: customPrompt };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    let targetSessionId = activeSessionId;
    if (!targetSessionId) {
      try {
        const createRes = await fetch('/api/chats', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: customPrompt.slice(0, 30) || `📍 Location (${lat.toFixed(2)}, ${lon.toFixed(2)})` })
        });
        if (!createRes.ok) throw new Error('Session creation failed');
        const sessionData = await createRes.json();
        targetSessionId = sessionData.session_id;
        if (onSessionTitleUpdate) onSessionTitleUpdate(targetSessionId);
      } catch (err) {
        console.error("Error creating session:", err);
        setLoading(false);
        return;
      }
    }

    try {
      const res = await fetch('/api/reverse-geocode-plot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lat,
          lon,
          session_id: targetSessionId,
          mauza_code: spatialMeta.mauza_code,
          plot_no: spatialMeta.plot_no,
          district_name: spatialMeta.district_name,
          upazila_name: spatialMeta.upazila_name,
          mouza_name: spatialMeta.mouza_name,
          custom_prompt: spatialMeta.custom_prompt
        })
      });
      if (!res.ok) {
        throw new Error(`Reverse geocode failed with status: ${res.status}`);
      }
      const data = await res.json();
      
      const aiMsg = { sender: 'ai', content: data.answer, metadata: data };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      console.error("Pin drop reverse geocoding failed:", err);
      setMessages((prev) => [
        ...prev,
        {
          sender: 'ai',
          content: "❌ দাগ বা অবস্থান সংক্রান্ত তথ্য বিশ্লেষণে সমস্যা হয়েছে। অনুগ্রহ করে ব্যাকএন্ড সক্রিয় আছে কিনা তা পরীক্ষা করে পুনরায় চেষ্টা করুন।"
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async (textToSend) => {
    const query = textToSend || input;
    if (!query.trim() || loading) return;

    let targetSessionId = activeSessionId;

    // Auto-create session if none active
    if (!targetSessionId) {
      try {
        const createRes = await fetch('/api/chats', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: query.slice(0, 30) })
        });
        if (!createRes.ok) throw new Error('Session creation failed');
        const sessionData = await createRes.json();
        targetSessionId = sessionData.session_id;
        if (onSessionTitleUpdate) onSessionTitleUpdate(targetSessionId);
      } catch (err) {
        console.error("Error creating session:", err);
        return;
      }
    }

    const userMsg = { sender: 'user', content: query };
    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setLoading(true);

    try {
      const res = await fetch(`/api/chats/${targetSessionId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Request failed');

      const aiMsg = {
        sender: 'ai',
        content: data.content,
        metadata: data.metadata
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      console.error("Error sending message:", err);
      setMessages((prev) => [
        ...prev,
        {
          sender: 'ai',
          content: "❌ দুঃখিত, ব্যাকএন্ড সার্ভারের সাথে সংযোগ করা সম্ভব হয়নি। অনুগ্রহ করে ব্যাকএন্ড সক্রিয় আছে কিনা তা পরীক্ষা করুন।"
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handlePillClick = (pillText) => {
    sendMessage(pillText);
  };

  // Helper to render markdown text with bolding and lists
  const renderFormattedText = (content) => {
    if (!content) return null;
    
    const lines = content.split('\n');
    return lines.map((line, i) => {
      let trimmed = line.trim();
      
      if (trimmed.startsWith('#### ')) {
        return <h4 key={i} className="text-sm font-bold text-teal-300 mt-3 mb-1">{renderInlineBold(trimmed.replace('#### ', ''))}</h4>;
      }
      if (trimmed.startsWith('### ')) {
        return <h3 key={i} className="text-base font-bold text-emerald-400 mt-4 mb-2">{renderInlineBold(trimmed.replace('### ', ''))}</h3>;
      }
      if (trimmed.startsWith('## ')) {
        return <h2 key={i} className="text-lg font-bold text-emerald-300 mt-5 mb-2">{renderInlineBold(trimmed.replace('## ', ''))}</h2>;
      }
      if (trimmed.startsWith('# ')) {
        return <h1 key={i} className="text-xl font-bold text-emerald-200 mt-6 mb-3">{renderInlineBold(trimmed.replace('# ', ''))}</h1>;
      }
      if (trimmed.startsWith('- ') || trimmed.startsWith('• ') || trimmed.startsWith('* ')) {
        const itemText = trimmed.replace(/^[-•*]\s+/, '');
        return (
          <li key={i} className="ml-4 list-disc text-slate-200 my-1 leading-relaxed">
            {renderInlineBold(itemText)}
          </li>
        );
      }
      if (trimmed === '') {
        return <div key={i} className="h-2"></div>;
      }

      return (
        <p key={i} className="my-1 text-slate-200 leading-relaxed">
          {renderInlineBold(trimmed)}
        </p>
      );
    });
  };

  const renderInlineBold = (text) => {
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, idx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={idx} className="text-emerald-300 font-semibold">{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  return (
    <div className="flex flex-col h-full w-full bg-slate-950 text-slate-100 overflow-hidden select-text">
      {/* Header Bar */}
      <div className="bg-slate-900/90 backdrop-blur-xl px-4 md:px-6 py-3.5 border-b border-slate-800/80 flex items-center justify-between shadow-md shrink-0 z-10">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-white shadow-lg shadow-emerald-950/40 text-lg font-bold">
            📜
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-bold text-slate-100 text-sm md:text-base tracking-tight">
                বাংলাদেশ ভূমি এআই সহকারী
              </h2>
              <span className="text-[10px] bg-emerald-500/15 text-emerald-400 font-mono px-2 py-0.5 rounded-full border border-emerald-500/30">
                Gemini RAG 2.5
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">
              খতিয়ান, ই-নামজারি, মৌজা ও ভূমি আইন সংক্রান্ত বহুমাত্রিক এআই পরামর্শক
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Tab Switcher */}
          <div className="bg-slate-950/80 p-1 rounded-xl border border-slate-800 flex space-x-1">
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === 'chat'
                  ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>💬 এআই চ্যাট</span>
            </button>
            <button
              onClick={() => setActiveTab('map')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === 'map'
                  ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>🗺️ ডিজিটাল মৌজা ম্যাপ</span>
            </button>
          </div>

          <div className="hidden lg:flex items-center space-x-1.5 bg-emerald-950/40 border border-emerald-500/30 px-2.5 py-1.5 rounded-lg text-xs text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>স্থানীয় সহকারী</span>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden relative flex flex-col bg-gradient-to-b from-slate-950 via-slate-900/40 to-slate-950">
        {activeTab === 'map' ? (
          <div className="p-3 md:p-4 flex-1 h-full overflow-hidden">
            <DigitalMouzaMap
              activePlot={activePlot}
              activeMouzaCode={activeMouzaCode}
              targetRecord={targetRecord}
              onPinDrop={handlePinDrop}
            />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scrollbar-thin scrollbar-thumb-slate-800">
            {messages.length === 0 ? (
              <div className="h-full min-h-[400px] flex flex-col items-center justify-center text-center p-4 max-w-3xl mx-auto space-y-6 animate-fade-in">
                <div className="w-16 h-16 rounded-3xl bg-gradient-to-tr from-emerald-600/20 to-teal-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 text-3xl shadow-xl shadow-emerald-950/40">
                  🏡
                </div>
                <div>
                  <h3 className="text-xl md:text-2xl font-bold text-slate-100 mb-2">
                    স্বাগতম! কীভাবে সাহায্য করতে পারি?
                  </h3>
                  <p className="text-xs md:text-sm text-slate-400 max-w-lg mx-auto">
                    জরিপের ইতিহাস, নামজারি ও খতিয়ান সম্পর্কে প্রশ্ন করুন। নির্দিষ্ট মালিকানা অনুসন্ধানের জন্য স্থানীয় রেকর্ড ডাটাবেস সংযুক্ত থাকতে হবে।
                  </p>
                </div>

                {/* Starter Question Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left pt-2">
                  {STARTER_PROMPTS.map((starter, sIdx) => (
                    <button
                      key={sIdx}
                      onClick={() => sendMessage(starter.prompt)}
                      className="p-3.5 rounded-2xl bg-slate-900/80 hover:bg-emerald-950/50 border border-slate-800 hover:border-emerald-500/40 text-left transition-all duration-200 group shadow-sm hover:shadow-emerald-950/30 flex items-start gap-3 active:scale-[0.98]"
                    >
                      <div className="w-9 h-9 rounded-xl bg-slate-800 group-hover:bg-emerald-900/60 border border-slate-700 group-hover:border-emerald-500/40 flex items-center justify-center text-base shrink-0 transition-colors">
                        {starter.icon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-xs text-slate-200 group-hover:text-emerald-300 transition-colors flex items-center justify-between">
                          <span>{starter.title}</span>
                          <span className="text-slate-600 group-hover:text-emerald-400 transition-colors text-xs">➔</span>
                        </div>
                        <div className="text-[11px] text-slate-400 truncate mt-0.5">{starter.desc}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, index) => {
                const isUser = msg.sender === 'user';
                const meta = msg.metadata || {};
                const records = meta.records || [];
                const pills = meta.clarification_options || [];

                return (
                  <div
                    key={index}
                    className={`flex gap-3 max-w-3xl animate-fade-in ${
                      isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'
                    }`}
                  >
                    <div
                      className={`w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold shrink-0 shadow-md ${
                        isUser
                          ? 'bg-gradient-to-tr from-emerald-600 to-teal-600 text-white'
                          : 'bg-slate-800 text-emerald-400 border border-slate-700'
                      }`}
                    >
                      {isUser ? 'ইউজার' : 'এআই'}
                    </div>

                    <div className="flex flex-col space-y-2 max-w-full min-w-0">
                      <div
                        className={`rounded-2xl p-4 text-sm leading-relaxed shadow-lg relative group ${
                          isUser
                            ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-tr-none'
                            : meta.is_out_of_scope
                            ? 'bg-slate-900 border border-amber-500/40 text-slate-100 rounded-tl-none'
                            : 'bg-slate-900/90 border border-slate-800 text-slate-100 rounded-tl-none'
                        }`}
                      >
                        {renderFormattedText(msg.content)}

                        {/* Copy button for AI message */}
                        {!isUser && (
                          <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                            <span className="text-[11px] text-slate-500">তথ্যমূলক উত্তর · সরকারি উৎসে যাচাই প্রয়োজন</span>
                            <button
                              onClick={() => handleCopy(msg.content, index)}
                              className="px-2 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all flex items-center gap-1 text-[11px]"
                            >
                              <span>{copiedIndex === index ? '✓ কপি হয়েছে' : '📋 কপি করুন'}</span>
                            </button>
                          </div>
                        )}

                        {/* Display Khatian Record Cards in expandable section */}
                        {records.length > 0 && (
                          <details className="mt-3 pt-2 border-t border-slate-800 group/details" open={records.length <= 2}>
                            <summary className="text-xs font-semibold text-emerald-400 cursor-pointer select-none flex items-center justify-between hover:text-emerald-300 py-1">
                              <span>📜 সংশ্লিষ্ট খতিয়ান রেকর্ড ({records.length} টি পাওয়া গেছে)</span>
                              <span className="text-slate-500 group-open/details:rotate-180 transition-transform">▼</span>
                            </summary>
                            <div className="mt-2 space-y-2">
                              {records.map((r, rIdx) => (
                                <RecordCard key={rIdx} record={r} onViewOnMap={handleViewRecordOnMap} />
                              ))}
                            </div>
                          </details>
                        )}
                      </div>

                      {/* Interactive Follow-up Question Pills */}
                      {!isUser && pills.length > 0 && index === messages.length - 1 && (
                        <div className="flex flex-wrap gap-2 mt-2 pt-1 animate-fade-in">
                          <span className="w-full text-xs text-slate-400 font-medium">💡 পরবর্তী প্রস্তাবিত প্রশ্নসমূহ:</span>
                          {pills.map((pill, pIdx) => (
                            <button
                              key={pIdx}
                              onClick={() => handlePillClick(pill)}
                              className="bg-slate-900/90 hover:bg-emerald-950/80 border border-emerald-500/30 hover:border-emerald-400 text-emerald-300 hover:text-emerald-200 text-xs px-3 py-1.5 rounded-full transition-all shadow-sm flex items-center gap-1.5 active:scale-95"
                            >
                              <span>{pill}</span>
                              <span className="text-emerald-400 font-bold">➔</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}

            {loading && (
              <div className="flex gap-3 mr-auto animate-fade-in">
                <div className="w-9 h-9 rounded-xl bg-slate-800 text-emerald-400 border border-slate-700 flex items-center justify-center text-xs font-bold animate-pulse">
                  এআই
                </div>
                <div className="bg-slate-900/90 border border-slate-800 rounded-2xl rounded-tl-none p-4 text-sm text-slate-300 flex items-center gap-3 shadow-lg">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></span>
                  <span>ভূমি তথ্য ও খতিয়ান ডেটাবেস অনুসন্ধান করা হচ্ছে...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Form */}
      {activeTab === 'chat' && (
        <div className="p-3 md:p-4 bg-slate-900/95 backdrop-blur-xl border-t border-slate-800/80 shrink-0 z-10">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
            className="flex items-end gap-2 max-w-4xl mx-auto"
          >
            <div className="flex-1 relative bg-slate-950 border border-slate-700/80 focus-within:border-emerald-500/80 rounded-2xl transition-all shadow-inner">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                placeholder="খতিয়ান নম্বর, মৌজা বা ভূমি সংক্রান্ত প্রশ্ন লিখুন... (e.g. ভাট বাড়িয়া মৌজার খতিয়ান ৩)"
                className="w-full bg-transparent text-slate-100 placeholder-slate-500 px-4 py-3 text-xs md:text-sm focus:outline-none resize-none max-h-32 scrollbar-thin"
              />
            </div>
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-40 text-white font-semibold px-5 py-3 rounded-2xl text-xs md:text-sm transition-all shadow-lg shadow-emerald-950/40 flex items-center gap-1.5 shrink-0 active:scale-95"
            >
              <span>পাঠান</span>
              <span>➔</span>
            </button>
          </form>
          <div className="flex items-center justify-between max-w-4xl mx-auto mt-2 px-1 text-[11px] text-slate-500">
            <span>Enter চাপলে মেসেজ পাঠানো হবে, Shift+Enter এ নতুন লাইন</span>
            <span>সিদ্ধান্তের আগে সরকারি রেকর্ড যাচাই করুন</span>
          </div>
        </div>
      )}
    </div>
  );
}

