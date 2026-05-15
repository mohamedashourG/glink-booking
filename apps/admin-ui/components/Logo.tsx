export function Logo({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="g-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#4338ca" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="28" height="28" rx="8" fill="url(#g-logo)" />
      <path
        d="M11.2 14.5a4.8 4.8 0 1 1 4.8 4.8h-1.6"
        stroke="white"
        strokeWidth="2.2"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="20.8" cy="11.2" r="1.6" fill="white" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <Logo className="h-7 w-7" />
      <span className="text-[1.05rem] font-semibold tracking-tight text-ink-900">
        glink<span className="text-brand-600">.</span>
      </span>
    </div>
  );
}
