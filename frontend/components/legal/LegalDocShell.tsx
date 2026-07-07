"use client";

import { useEffect, useRef, useState } from "react";

export interface LegalSection {
  id: string;
  label: string;
  heading: string;
  paragraphs: string[];
  /** Optional bullet list rendered after the paragraphs, for scannable items
   * like "what we collect" or "what you can do". */
  bullets?: string[];
}

/**
 * Shared shell for /terms and /privacy: same sidebar-TOC pattern as
 * `components/docs/DocsShell.tsx` (active section tracked via
 * IntersectionObserver, same pill nav, same typographic scale) but for a
 * single legal document — narrow reading width (`max-w-copy`, the same
 * token the rest of the app uses for body copy) rather than the docs
 * page's wider content column, since long paragraphs of legal text read
 * better narrow.
 */
export function LegalDocShell({
  title,
  lastUpdatedLabel,
  intro,
  sections,
}: {
  title: string;
  lastUpdatedLabel: string;
  intro?: string;
  sections: LegalSection[];
}) {
  const [activeId, setActiveId] = useState(sections[0].id);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) {
          setActiveId(visible[0].target.id);
        }
      },
      { rootMargin: "-15% 0px -70% 0px", threshold: 0 }
    );

    sections.forEach((section) => {
      const el = sectionRefs.current[section.id];
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [sections]);

  function handleNavClick(id: string) {
    setActiveId(id);
    setMobileNavOpen(false);
  }

  return (
    <div className="mx-auto max-w-content px-6 pb-24 pt-32 md:px-8">
      <div className="mb-10 max-w-copy">
        <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">
          Last updated {lastUpdatedLabel}
        </p>
        <h1 className="mt-2 text-[30px] font-semibold tracking-heading text-carbon md:text-[38px]">
          {title}
        </h1>
        {intro && (
          <p className="mt-4 text-[15px] leading-relaxed tracking-body text-graphite">{intro}</p>
        )}
      </div>

      {/* Compact mobile nav */}
      <div className="mb-8 md:hidden">
        <button
          type="button"
          onClick={() => setMobileNavOpen((open) => !open)}
          aria-expanded={mobileNavOpen}
          className="flex w-full items-center justify-between rounded-full border border-fog bg-white px-4 py-3 text-[14px] font-medium text-carbon"
        >
          {sections.find((s) => s.id === activeId)?.label ?? "Contents"}
          <span aria-hidden className={`transition-transform ${mobileNavOpen ? "rotate-180" : ""}`}>
            ⌄
          </span>
        </button>
        {mobileNavOpen && (
          <nav className="mt-2 flex flex-col gap-1 rounded-card border border-fog bg-white p-2">
            {sections.map((section) => (
              <a
                key={section.id}
                href={`#${section.id}`}
                onClick={() => handleNavClick(section.id)}
                className={`rounded-full px-4 py-2.5 text-[14px] font-medium transition-colors ${
                  activeId === section.id ? "bg-mist text-carbon" : "text-graphite hover:bg-mist/60"
                }`}
              >
                {section.label}
              </a>
            ))}
          </nav>
        )}
      </div>

      <div className="grid grid-cols-1 gap-12 md:grid-cols-[220px_1fr]">
        <nav aria-label={`${title} sections`} className="hidden md:block">
          <div className="sticky top-32 flex flex-col gap-1">
            {sections.map((section) => (
              <a
                key={section.id}
                href={`#${section.id}`}
                onClick={() => handleNavClick(section.id)}
                aria-current={activeId === section.id ? "true" : undefined}
                className={`rounded-full px-4 py-2 text-[13px] font-medium transition-colors ${
                  activeId === section.id
                    ? "bg-mist text-carbon"
                    : "text-graphite hover:bg-mist/60 hover:text-carbon"
                }`}
              >
                {section.label}
              </a>
            ))}
          </div>
        </nav>

        <div className="flex max-w-copy flex-col gap-14">
          {sections.map((section) => (
            <section
              key={section.id}
              id={section.id}
              ref={(el) => {
                sectionRefs.current[section.id] = el;
              }}
              className="scroll-mt-32"
            >
              <h2 className="text-[20px] font-semibold tracking-heading text-carbon md:text-[24px]">
                {section.heading}
              </h2>
              <div className="mt-4 flex flex-col gap-4">
                {section.paragraphs.map((paragraph, i) => (
                  <p key={i} className="text-[15px] leading-relaxed tracking-body text-graphite">
                    {paragraph}
                  </p>
                ))}
              </div>
              {section.bullets && (
                <ul className="mt-4 flex flex-col gap-2">
                  {section.bullets.map((bullet, i) => (
                    <li
                      key={i}
                      className="flex gap-3 text-[15px] leading-relaxed tracking-body text-graphite"
                    >
                      <span aria-hidden className="mt-2.5 h-1 w-1 shrink-0 rounded-full bg-ash" />
                      {bullet}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
