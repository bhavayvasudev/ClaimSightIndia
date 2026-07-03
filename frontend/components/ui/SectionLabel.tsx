type SectionLabelProps = {
  children: string;
  tone?: "neutral" | "mint";
};

const tones = {
  neutral: "bg-mist text-graphite",
  mint: "bg-mint-wash text-mint",
};

export function SectionLabel({ children, tone = "neutral" }: SectionLabelProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3.5 py-1.5 text-[12px] font-medium uppercase tracking-[0.08em] ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
