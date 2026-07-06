"use client";

import { useEffect, useRef, useState } from "react";
import { DOC_SECTIONS } from "@/lib/docsContent";

/**
 * Single scrollable page with anchor sections rather than one route per
 * section — every "docs link" is a same-page hash link, so there is no
 * way for a docs nav item to point at a route that doesn't exist. Active
 * section state is tracked via IntersectionObserver, not scroll-position
 * math, so it stays correct regardless of section height.
 */
export function DocsShell() {
  const [activeId, setActiveId] = useState(DOC_SECTIONS[0].id);
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

    DOC_SECTIONS.forEach((section) => {
      const el = sectionRefs.current[section.id];
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  function handleNavClick(id: string) {
    setActiveId(id);
    setMobileNavOpen(false);
  }

  return (
    <div className="mx-auto max-w-content px-6 pb-24 pt-32 md:px-8">
      <div className="mb-10">
        <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">Documentation</p>
        <h1 className="mt-2 text-[30px] font-semibold tracking-heading text-carbon md:text-[38px]">
          ClaimSight Docs
        </h1>
      </div>

      {/* Compact mobile nav */}
      <div className="mb-8 md:hidden">
        <button
          type="button"
          onClick={() => setMobileNavOpen((open) => !open)}
          aria-expanded={mobileNavOpen}
          className="flex w-full items-center justify-between rounded-full border border-fog bg-white px-4 py-3 text-[14px] font-medium text-carbon"
        >
          {DOC_SECTIONS.find((s) => s.id === activeId)?.label ?? "Contents"}
          <span aria-hidden className={`transition-transform ${mobileNavOpen ? "rotate-180" : ""}`}>
            ⌄
          </span>
        </button>
        {mobileNavOpen && (
          <nav className="mt-2 flex flex-col gap-1 rounded-card border border-fog bg-white p-2">
            {DOC_SECTIONS.map((section) => (
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
        {/* Desktop sidebar */}
        <nav aria-label="Docs sections" className="hidden md:block">
          <div className="sticky top-32 flex flex-col gap-1">
            {DOC_SECTIONS.map((section) => (
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

        <div className="flex flex-col gap-16">
          {DOC_SECTIONS.map((section) => (
            <section
              key={section.id}
              id={section.id}
              ref={(el) => {
                sectionRefs.current[section.id] = el;
              }}
              className="scroll-mt-32"
            >
              <h2 className="text-[22px] font-semibold tracking-heading text-carbon md:text-[26px]">
                {section.heading}
              </h2>
              <div className="mt-4 flex flex-col gap-4">
                {section.paragraphs.map((paragraph, i) => (
                  <p key={i} className="max-w-copy text-[15px] leading-relaxed tracking-body text-graphite">
                    {paragraph}
                  </p>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
