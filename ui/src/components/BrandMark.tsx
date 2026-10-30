const SIZES = {
  sm: { box: "size-8 rounded-xl", icon: "size-4.5" },
  lg: { box: "size-14 rounded-2xl", icon: "size-7" },
};

/** The product mark: an "L" axis with a token dot, on the brand gradient. */
export function BrandMark({ size = "sm" }: { size?: keyof typeof SIZES }) {
  const s = SIZES[size];
  return (
    <div
      className={`flex shrink-0 items-center justify-center bg-gradient-to-br from-violet-500 to-fuchsia-500 shadow-lg shadow-violet-500/30 ${s.box}`}
    >
      <svg viewBox="0 0 24 24" className={`${s.icon} text-white`} fill="none" aria-hidden="true">
        <path
          d="M5 4v16h14"
          stroke="currentColor"
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="15" cy="9" r="2.6" fill="currentColor" />
      </svg>
    </div>
  );
}
