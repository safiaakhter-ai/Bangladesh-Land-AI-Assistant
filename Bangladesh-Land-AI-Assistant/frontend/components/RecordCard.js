"use client";

import React from 'react';

export default function RecordCard({ record, onViewOnMap }) {
  if (!record) return null;
  const d = record.details || record;
  const khatianNo = d.KHATIAN_NO || "N/A";
  const mouza = d.MOUZA_NAME || "N/A";
  const upazila = d.UPAZILA_NAME || "N/A";
  const district = d.DISTRICT_NAME || "N/A";
  const owners = d.OWNERS || "মালিকের নাম নিবন্ধিত নয়";
  const dags = d.DAGS || "N/A";
  const totalLand = d.TOTAL_LAND;
  const survey = (d.SURVEY_NAME || record.survey_name || "—").toUpperCase();

  // Color mapping for different survey types
  const getSurveyBadgeColor = (type) => {
    if (type.includes("BS") || type.includes("বিএস")) return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
    if (type.includes("RS") || type.includes("আরএস")) return "bg-blue-500/20 text-blue-300 border-blue-500/40";
    if (type.includes("SA") || type.includes("এসএ")) return "bg-purple-500/20 text-purple-300 border-purple-500/40";
    if (type.includes("CS") || type.includes("সিএস")) return "bg-amber-500/20 text-amber-300 border-amber-500/40";
    return "bg-teal-500/20 text-teal-300 border-teal-500/40";
  };

  return (
    <div className="bg-slate-900/80 hover:bg-slate-850 border border-slate-800 hover:border-emerald-500/50 rounded-2xl p-4 transition-all duration-200 shadow-md hover:shadow-xl hover:shadow-emerald-950/20 text-slate-100 flex flex-col justify-between group">
      <div>
        {String(d.DATA_SOURCE || "").startsWith("DEMO") && (
          <div className="mb-3 rounded-lg border border-amber-500/40 bg-amber-950/40 p-2 text-xs font-semibold text-amber-200">
            DEMO DATA — কৃত্রিম নমুনা, সরকারি রেকর্ড নয়
          </div>
        )}
        {/* Card Header */}
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-2.5 mb-3">
          <div className="flex items-center space-x-2">
            <span className={`text-xs font-bold px-2.5 py-0.5 rounded-lg border font-mono ${getSurveyBadgeColor(survey)}`}>
              {survey}
            </span>
            <span className="text-slate-300 text-xs font-medium">
              খতিয়ান: <strong className="text-emerald-400 text-sm font-mono ml-0.5">{khatianNo}</strong>
            </span>
          </div>
          <span className="text-[11px] text-slate-500 font-mono bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
            #{record.khatian_id || d.ID || 'REC'}
          </span>
        </div>

        {/* Card Body */}
        <div className="space-y-2.5 text-xs">
          <div className="flex items-start space-x-2">
            <span className="text-slate-400 font-semibold min-w-20 shrink-0">👤 মালিকগণ:</span>
            <span className="text-slate-200 font-normal leading-relaxed">{owners}</span>
          </div>

          <div className="flex items-start space-x-2">
            <span className="text-slate-400 font-semibold min-w-20 shrink-0">📍 অবস্থান:</span>
            <span className="text-slate-300">
              <strong className="text-slate-100">{mouza}</strong>, {upazila}, {district}
            </span>
          </div>

          <div className="flex items-start space-x-2">
            <span className="text-slate-400 font-semibold min-w-20 shrink-0">🗺️ দাগ নম্বর:</span>
            <span className="text-emerald-300 font-mono bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
              {dags}
            </span>
          </div>

          {totalLand && (
            <div className="flex items-start space-x-2">
              <span className="text-slate-400 font-semibold min-w-20 shrink-0">📐 মোট জমি:</span>
              <span className="text-teal-300 font-semibold">{totalLand}</span>
            </div>
          )}
        </div>
      </div>

      {/* Action Footer */}
      {onViewOnMap && (
        <button
          onClick={() => onViewOnMap(record)}
          className="mt-3.5 w-full bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-300 hover:text-emerald-100 border border-emerald-500/30 hover:border-emerald-400/50 rounded-xl px-3 py-2 text-xs font-semibold flex items-center justify-center space-x-1.5 transition-all shadow-sm active:scale-95 group-hover:bg-emerald-900/40"
        >
          <span>🗺️ ডিজিটাল মৌজা ম্যাপে দাগ চিহ্নিত করুন</span>
          <span>➔</span>
        </button>
      )}
    </div>
  );
}

