// The mark itself — the glnk emblem, lifted from gtm-engine. Plain <img>
// rather than next/image: the file is ~2 KB, optimization buys nothing.
export function Logo({ className = "h-7 w-7" }: { className?: string; priority?: boolean }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src="/logo.png" alt="glink" className={`object-contain ${className}`} />
  );
}

// Mark + wordmark side by side. Used on the login card.
export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <Logo className="h-7 w-7" />
      <span className="text-[1.05rem] font-semibold tracking-tight text-brand-700">
        glink
      </span>
    </div>
  );
}
