"use client";

import React, { useState, useEffect } from 'react';
import RecordCard from './RecordCard';

export default function RecordBrowser() {
  const [query, setQuery] = useState('');
  const [surveyFilter, setSurveyFilter] = useState('ALL'); // ALL, BS, RS, SA, CS
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [databaseAvailable, setDatabaseAvailable] = useState(null);
  const [searchError, setSearchError] = useState('');
  const [totalIsEstimate, setTotalIsEstimate] = useState(false);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);

  const fetchRecords = async (searchTerm, pageNum = 1) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/khatians/search?q=${encodeURIComponent(searchTerm)}&page=${pageNum}&per_page=12`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Search failed');
      setSearchError('');
      setDatabaseAvailable(data.record_database_available ?? null);
      setTotalIsEstimate(Boolean(data.total_is_estimate));
      setRecords(data.records || []);
      setTotal(data.total || 0);
      setPage(pageNum);
    } catch (err) {
      console.error("Error fetching records:", err);
      setSearchError("রেকর্ড অনুসন্ধান করা যায়নি। API সার্ভার চালু আছে কি না দেখুন।");
      setRecords([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Initial query updates the record loading state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchRecords('', 1);
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchRecords(query, 1);
  };

  // Filter records locally by survey type if selected
  const filteredRecords = records.filter((r) => {
    if (surveyFilter === 'ALL') return true;
    const s = (r.details?.SURVEY_NAME || r.survey_name || '').toUpperCase();
    return s.includes(surveyFilter);
  });

  return (
    <div className="h-full flex flex-col bg-slate-950 text-slate-100 p-4 md:p-6 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-800">
      <div className="max-w-6xl mx-auto w-full space-y-6">
        {/* Header Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/80 p-5 rounded-2xl border border-slate-800 backdrop-blur-xl shadow-lg">
          <div>
            <h1 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
              <span className="text-emerald-400">📂</span>
              <span>ভূমি খতিয়ান ডেটাবেস এক্সপ্লোরার</span>
            </h1>
            <p className="text-slate-400 text-xs md:text-sm mt-1">
              আপনার সংযুক্ত ডাটাবেসে খতিয়ান অনুসন্ধান করুন। ফলাফল অফিসিয়াল দলিলের বিকল্প নয়।
            </p>
          </div>
          <div className="bg-slate-950/90 border border-slate-800 px-4 py-2.5 rounded-xl text-xs text-slate-300 flex items-center gap-3">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <div>
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">বর্তমান অনুসন্ধানের ফল</div>
              <strong className="text-emerald-400 font-mono text-base">
                {totalIsEstimate ? "≥ " : ""}{total.toLocaleString()}
              </strong>
            </div>
          </div>
        </div>

        {databaseAvailable === false && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-950/25 px-4 py-3 text-sm text-amber-200" role="status">
            কোনো khatians.db ফাইল সংযুক্ত নেই। জ্ঞানভিত্তিক প্রশ্ন করতে Chat ব্যবহার করুন; প্রকৃত রেকর্ড অনুসন্ধানের জন্য README অনুযায়ী আপনার বৈধ ডাটাবেস যোগ করুন।
          </div>
        )}
        {searchError && <p className="rounded-xl border border-rose-500/30 bg-rose-950/30 p-3 text-sm text-rose-300" role="alert">{searchError}</p>}
        {/* Search & Filter Bar */}
        <div className="space-y-3">
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="flex-1 relative">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="মৌজার নাম, খতিয়ান নম্বর, মালিকের নাম বা দাগ নম্বর দিয়ে খুঁজুন... (e.g. ভাট বাড়িয়া)"
                className="w-full bg-slate-900 border border-slate-700/80 focus:border-emerald-500 rounded-2xl px-4 py-3 text-xs md:text-sm text-slate-100 placeholder-slate-500 outline-none transition-all shadow-inner"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => { setQuery(''); fetchRecords('', 1); }}
                  className="absolute right-3 top-3 text-slate-400 hover:text-white text-sm"
                >
                  ✕
                </button>
              )}
            </div>
            <button
              type="submit"
              disabled={loading}
              className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold px-6 py-3 rounded-2xl transition-all shadow-lg shadow-emerald-950/40 flex items-center gap-2 text-xs md:text-sm disabled:opacity-50 active:scale-95 shrink-0"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                  <span>খোঁজা হচ্ছে...</span>
                </span>
              ) : (
                <span>🔍 অনুসন্ধান</span>
              )}
            </button>
          </form>

          {/* Survey Filter Pills & Quick Tags */}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs pt-1">
            <div className="flex items-center gap-1.5 bg-slate-900 p-1 rounded-xl border border-slate-800">
              {['ALL', 'BS', 'RS', 'SA', 'CS'].map((type) => (
                <button
                  key={type}
                  onClick={() => setSurveyFilter(type)}
                  className={`px-3 py-1 rounded-lg font-mono font-bold transition-all ${
                    surveyFilter === type
                      ? 'bg-emerald-600 text-white shadow-md'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {type === 'ALL' ? 'সব জরিপ' : `${type} রেকর্ড`}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-slate-500">দ্রুত ফিল্টার:</span>
              {["ভাট বাড়িয়া", "খতিয়ান ৩", "সরাইল", "দাগ ৭৪", "কাংশা"].map((tag) => (
                <button
                  key={tag}
                  onClick={() => { setQuery(tag); fetchRecords(tag, 1); }}
                  className="bg-slate-900 hover:bg-emerald-950/60 border border-slate-800 hover:border-emerald-500/40 text-slate-300 hover:text-emerald-300 px-2.5 py-1 rounded-lg transition-all text-xs"
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Records Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-44 bg-slate-900/60 rounded-2xl border border-slate-800/60"></div>
            ))}
          </div>
        ) : filteredRecords.length > 0 ? (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredRecords.map((r, idx) => (
                <div key={r.khatian_id || idx} onClick={() => setSelectedRecord(r)} className="cursor-pointer">
                  <RecordCard record={r} />
                </div>
              ))}
            </div>

            {/* Pagination Controls */}
            <div className="flex justify-between items-center pt-4 border-t border-slate-800/80">
              <button
                disabled={page <= 1 || loading}
                onClick={() => fetchRecords(query, page - 1)}
                className="bg-slate-900 hover:bg-slate-800 disabled:opacity-30 border border-slate-800 text-slate-200 px-4 py-2 rounded-xl text-xs md:text-sm transition-all"
              >
                ⬅️ পূর্ববর্তী পেজ
              </button>
              <span className="text-xs text-slate-400 font-mono">
                পেজ <strong className="text-emerald-400 text-sm">{page}</strong> (মোট ফলাফল: {total})
              </span>
              <button
                disabled={records.length < 12 || loading}
                onClick={() => fetchRecords(query, page + 1)}
                className="bg-slate-900 hover:bg-slate-800 disabled:opacity-30 border border-slate-800 text-slate-200 px-4 py-2 rounded-xl text-xs md:text-sm transition-all"
              >
                পরবর্তী পেজ ➡️
              </button>
            </div>
          </div>
        ) : (
          <div className="text-center py-16 bg-slate-900/40 rounded-3xl border border-slate-800/80 space-y-2">
            <div className="text-3xl">🔍</div>
            <p className="text-slate-300 font-medium text-sm">কোনো খতিয়ান রেকর্ড পাওয়া যায়নি</p>
            <p className="text-slate-500 text-xs">রেকর্ড ডাটাবেস যুক্ত করা আছে কিনা দেখুন, অথবা ভিন্ন অনুসন্ধান ব্যবহার করুন।</p>
          </div>
        )}

        {/* Selected Record Modal / Detailed Inspector */}
        {selectedRecord && (
          <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4">
            <div className="bg-slate-900 border border-emerald-500/40 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl animate-fade-in text-slate-100">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center space-x-2">
                  <span className="bg-emerald-500/20 text-emerald-400 font-bold px-2.5 py-1 rounded-lg border border-emerald-500/40 text-xs font-mono">
                    {selectedRecord.details?.SURVEY_NAME || selectedRecord.survey_name || 'অজানা'} খতিয়ান
                  </span>
                  <h3 className="font-bold text-base text-slate-100">
                    খতিয়ান নং #{selectedRecord.details?.KHATIAN_NO || selectedRecord.khatian_no}
                  </h3>
                </div>
                <button
                  onClick={() => setSelectedRecord(null)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white bg-slate-800 text-sm"
                >
                  ✕
                </button>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-500">মৌজা:</span>
                  <div className="font-semibold text-slate-100 text-sm mt-0.5">{selectedRecord.details?.MOUZA_NAME || "N/A"}</div>
                </div>
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-500">উপজেলা ও জেলা:</span>
                  <div className="font-semibold text-slate-100 text-sm mt-0.5">
                    {selectedRecord.details?.UPAZILA_NAME || "N/A"}, {selectedRecord.details?.DISTRICT_NAME || "N/A"}
                  </div>
                </div>
              </div>

              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2 text-xs">
                <span className="text-emerald-400 font-semibold">মালিকগণের পূর্ণ তালিকা:</span>
                <p className="text-slate-200 leading-relaxed font-mono">
                  {selectedRecord.details?.OWNERS || "মালিক নিবন্ধিত নয়"}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-500">দাগ নম্বরসমূহ:</span>
                  <div className="font-semibold text-emerald-300 font-mono text-sm mt-0.5">
                    {selectedRecord.details?.DAGS || "N/A"}
                  </div>
                </div>
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-500">মোট জমির পরিমাণ:</span>
                  <div className="font-semibold text-teal-300 text-sm mt-0.5">
                    {selectedRecord.details?.TOTAL_LAND || "নির্ধারিত নয়"}
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  onClick={() => setSelectedRecord(null)}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold"
                >
                  বন্ধ করুন
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

