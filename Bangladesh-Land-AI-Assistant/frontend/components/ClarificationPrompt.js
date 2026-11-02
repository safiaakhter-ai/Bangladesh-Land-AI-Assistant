'use client';

export default function ClarificationPrompt({ options, onSelect }) {
  if (!options || options.length === 0) return null;

  return (
    <div className="mt-3 p-3 rounded-2xl bg-amber-950/30 border border-amber-500/30 text-amber-200 text-xs space-y-2">
      <div className="flex items-center gap-2 font-medium text-amber-400">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>Select or click options to clarify / সঠিক তথ্যের জন্য নির্বাচন করুন:</span>
      </div>

      <div className="flex flex-wrap gap-2 pt-1">
        {options.map((opt, idx) => (
          <button
            key={idx}
            onClick={() => onSelect(opt)}
            className="px-3 py-1.5 rounded-xl bg-amber-900/40 hover:bg-amber-800/60 active:scale-95 text-amber-200 hover:text-white border border-amber-500/40 transition-all cursor-pointer font-medium"
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}
