import { PillButton } from "../ui/PillButton";
import { Reveal } from "../ui/Reveal";

export function Footer() {
  return (
    <footer className="border-t border-fog bg-white">
      <div className="mx-auto max-w-content px-6 py-24 text-center md:px-8 md:py-32">
        <Reveal>
          <h2 className="mx-auto max-w-[640px] text-[34px] font-semibold leading-[1.15] tracking-display text-carbon sm:text-[44px] md:text-[52px]">
            Bring sight to your claims.
          </h2>
        </Reveal>
        <Reveal delay={0.12}>
          <p className="mx-auto mt-6 max-w-copy text-[16px] leading-relaxed tracking-body text-ash">
            See how ClaimSight India fits your triage workflow — from first photo to final report.
          </p>
        </Reveal>
        <Reveal delay={0.22}>
          <div className="mt-9 flex justify-center">
            <PillButton href="#demo" size="lg">
              Request a demo
            </PillButton>
          </div>
        </Reveal>
      </div>

      <div className="border-t border-fog">
        <div className="mx-auto flex max-w-content flex-col items-center gap-5 px-6 py-10 md:flex-row md:justify-between md:px-8">
          <a href="#" className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-lavender" aria-hidden />
            <span className="text-[15px] font-semibold tracking-heading text-carbon">
              ClaimSight <span className="font-normal text-ash">India</span>
            </span>
          </a>
          <nav className="flex flex-wrap items-center justify-center gap-7">
            {[
              { label: "The problem", href: "#problem" },
              { label: "How it works", href: "#workflow" },
              { label: "Agents", href: "#agents" },
              { label: "Demo", href: "#demo" },
            ].map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="text-[14px] font-medium text-graphite transition-colors hover:text-carbon"
              >
                {item.label}
              </a>
            ))}
          </nav>
          <p className="text-[13px] tracking-body text-ash">AI-powered multimodal claim triage</p>
        </div>
      </div>
    </footer>
  );
}
