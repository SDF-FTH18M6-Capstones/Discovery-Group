export function LogoMark({ size = 36 }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 64 64" className="shrink-0">
      <rect width="64" height="64" rx="16" fill="#124a40" />
      <rect x="1" y="1" width="62" height="62" rx="15" fill="none" stroke="rgb(255 255 255 / .1)" />
      <path
        d="M15 39 32 19l17 20"
        fill="none"
        stroke="#f2b655"
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M21 47h22" stroke="#3ccb95" strokeWidth="6" strokeLinecap="round" />
    </svg>
  );
}

export default function Logo({ size = 36, className = "text-white" }) {
  return (
    <span className={`flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} />
      <span className="font-display text-[1.2rem] font-bold tracking-[-0.02em]">StockPilot</span>
    </span>
  );
}