const LOGO_SRC = "/stockpilot1.png"; // file lives in public/stockpilot1.png

export function LogoMark({ size = 36 }) {
  return (
    <img
      src={LOGO_SRC}
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      className="shrink-0 rounded-2xl bg-white object-contain p-0.5 shadow-sm ring-1 ring-white/20"
    />
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