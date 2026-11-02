"use client";

import { useEffect, useState } from "react";

const formatCount = (value) => typeof value === "number" ? value.toLocaleString("en-US") : "—";

export default function TelemetryBanner() {
  const [status, setStatus] = useState({ state: "checking", data: null });

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const res = await fetch("/api/telemetry", { cache: "no-store" });
        if (!res.ok) throw new Error("Backend did not respond");
        const data = await res.json();
        if (mounted) setStatus({ state: "connected", data });
      } catch {
        if (mounted) setStatus({ state: "offline", data: null });
      }
    };
    check();
    const timer = setInterval(check, 30000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);

  const connected = status.state === "connected";
  const hasRecords = Boolean(status.data?.database_connected);
  const color = !connected ? "bg-rose-400" : hasRecords ? "bg-emerald-400" : "bg-amber-400";

  return (
    <div className="w-full bg-slate-950/95 border-b border-slate-800 px-4 md:px-6 py-2 flex items-center justify-between text-xs shrink-0 z-20 gap-3" role="status" aria-live="polite">
      <div className="flex items-center gap-3 md:gap-6 min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`h-2 w-2 shrink-0 rounded-full ${color}`} />
          <span className="text-slate-300 truncate font-medium">
            {status.state === "offline" ? "API সংযোগ নেই" : !connected ? "সার্ভার পরীক্ষা করা হচ্ছে" : hasRecords ? "লোকাল রেকর্ড ডাটাবেস সংযুক্ত" : "রেকর্ড ডাটাবেস যুক্ত করা হয়নি"}
          </span>
        </div>
        {hasRecords && <>
          <span className="hidden sm:inline text-slate-400">ইনডেক্স: <b className="text-slate-100 font-mono">{formatCount(status.data.index_khatians_count)}</b></span>
          <span className="hidden md:inline text-slate-400">বিস্তারিত রেকর্ড: <b className="text-slate-100 font-mono">{formatCount(status.data.saved_details_count)}</b></span>
        </>}
      </div>
      <span className="shrink-0 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1 text-slate-400 hidden xs:inline">Local-first · v1.0</span>
    </div>
  );
}
