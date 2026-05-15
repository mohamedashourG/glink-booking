function initials(input: string | null | undefined): string {
  const trimmed = (input ?? "").trim();
  if (!trimmed) return "?";
  const local = trimmed.includes("@") ? trimmed.split("@")[0] : trimmed;
  const parts = local.split(/[._\s-]+/).filter(Boolean);
  if (parts.length === 0) return local[0]?.toUpperCase() ?? "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

const PALETTE = [
  "from-brand-500 to-brand-700",
  "from-emerald-500 to-emerald-700",
  "from-rose-500 to-rose-700",
  "from-amber-500 to-amber-700",
  "from-sky-500 to-sky-700",
  "from-fuchsia-500 to-fuchsia-700",
];

function hueFor(seed: string | null | undefined): string {
  const s = seed ?? "";
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export function Avatar({
  seed,
  size = "md",
}: {
  seed: string | null | undefined;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  const sz = {
    sm: "h-7 w-7 text-[0.7rem]",
    md: "h-9 w-9 text-xs",
    lg: "h-12 w-12 text-sm",
    xl: "h-16 w-16 text-lg",
  }[size];
  return (
    <div
      aria-hidden="true"
      className={`${sz} rounded-full bg-gradient-to-br ${hueFor(seed)} text-white font-semibold flex items-center justify-center shrink-0 shadow-soft ring-2 ring-white`}
    >
      {initials(seed)}
    </div>
  );
}
