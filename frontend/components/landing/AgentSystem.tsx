import { Reveal } from "../ui/Reveal";
import { SectionLabel } from "../ui/SectionLabel";
import { SectionDivider } from "../ui/SectionDivider";
import { agents } from "@/lib/content";

export function AgentSystem() {
  return (
    <section id="agents" className="relative bg-linen">
      <SectionDivider />
      <div className="mx-auto flex min-h-screen max-w-content flex-col items-center justify-center px-6 py-28 md:px-8">
        <Reveal className="text-center">
          <SectionLabel>Multi-agent architecture</SectionLabel>
        </Reveal>
        <Reveal delay={0.1} className="text-center">
          <h2 className="mx-auto mt-6 max-w-[680px] text-balance text-[34px] font-semibold leading-[1.12] tracking-display text-carbon sm:text-[44px] md:text-[54px]">
            Six specialists. One report.
          </h2>
        </Reveal>
        <Reveal delay={0.2} className="text-center">
          <p className="mx-auto mt-6 max-w-copy text-[16px] leading-relaxed tracking-body text-graphite">
            Each agent owns one dimension of the claim. An orchestrator sequences them, resolves
            conflicts between their findings, and composes the final triage report.
          </p>
        </Reveal>

        <div className="mt-16 grid w-full grid-cols-1 gap-x-8 gap-y-12 sm:grid-cols-2 md:mt-20 lg:grid-cols-3">
          {agents.map((agent, i) => (
            <Reveal key={agent.name} delay={0.1 + i * 0.08}>
              <div className="group flex flex-col items-center px-4 text-center">
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-b from-[#a29ef8] to-lavender text-white transition-[transform,box-shadow] duration-500 ease-out group-hover:scale-110 group-hover:shadow-[0_8px_20px_rgba(145,141,246,0.4)]">
                  <AgentGlyph name={agent.glyph} />
                </span>
                <h3 className="mt-5 text-[17px] font-medium tracking-heading text-carbon">
                  {agent.name}
                </h3>
                <p className="mt-2 max-w-[280px] text-[14px] leading-relaxed tracking-body text-graphite">
                  {agent.description}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

function AgentGlyph({ name }: { name: string }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (name) {
    case "plate":
      return (
        <svg {...common}>
          <rect x="3" y="8" width="18" height="8" rx="2" />
          <path d="M7 12h.01M11 12h2M17 12h.01" />
        </svg>
      );
    case "document":
      return (
        <svg {...common}>
          <path d="M6 3h8l4 4v14H6z" />
          <path d="M14 3v4h4M9 12h6M9 16h6" />
        </svg>
      );
    case "scan":
      return (
        <svg {...common}>
          <path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" />
          <path d="M4 12h16" />
        </svg>
      );
    case "rupee":
      return (
        <svg {...common}>
          <path d="M7 4h10M7 8h10M7 4c6 0 6 8 0 8l7 8" />
        </svg>
      );
    case "shield":
      return (
        <svg {...common}>
          <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" />
          <path d="M9.5 12l1.8 1.8L15 10" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <rect x="4" y="4" width="16" height="16" rx="2" />
          <path d="M8 9h8M8 13h8M8 17h5" />
        </svg>
      );
  }
}
