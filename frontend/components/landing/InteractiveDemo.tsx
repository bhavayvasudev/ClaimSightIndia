"use client";

import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PillButton } from "../ui/PillButton";
import { SectionLabel } from "../ui/SectionLabel";
import { Reveal } from "../ui/Reveal";
import { agents } from "@/lib/content";
import { EASE } from "@/lib/motion";

type Status = "idle" | "analyzing" | "done";

const AGENT_TICK_MS = 420;

const mockResult = [
  { label: "Status", value: "Damage detected" },
  { label: "Severity", value: "Moderate" },
  { label: "Fraud risk", value: "Low · 12/100" },
  { label: "Plate OCR", value: "DL 3C CX 1234" },
  { label: "Est. cost", value: "₹35,000–₹45,000" },
];

export function InteractiveDemo() {
  const [photos, setPhotos] = useState<string[]>([]);
  const [policy, setPolicy] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [agentsDone, setAgentsDone] = useState(0);
  const timers = useRef<number[]>([]);

  useEffect(() => () => timers.current.forEach(window.clearTimeout), []);

  function handlePhotos(e: ChangeEvent<HTMLInputElement>) {
    setPhotos(Array.from(e.target.files ?? []).map((f) => f.name));
  }

  function handlePolicy(e: ChangeEvent<HTMLInputElement>) {
    setPolicy(e.target.files?.[0]?.name ?? null);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (status === "analyzing") return;
    timers.current.forEach(window.clearTimeout);
    timers.current = [];
    setAgentsDone(0);
    setStatus("analyzing");
    agents.forEach((_, i) => {
      timers.current.push(window.setTimeout(() => setAgentsDone(i + 1), (i + 1) * AGENT_TICK_MS));
    });
    timers.current.push(
      window.setTimeout(() => setStatus("done"), agents.length * AGENT_TICK_MS + 500)
    );
  }

  return (
    <section id="demo" className="relative bg-white">
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-[4%] h-[420px] w-[680px] -translate-x-1/2 rounded-full bg-lavender/[0.1] blur-[130px]" />
      </div>
      <div className="relative mx-auto flex min-h-screen max-w-content flex-col items-center justify-center px-6 pb-24 pt-32 md:px-8">
        <Reveal className="text-center">
          <SectionLabel>Interactive preview · sample data</SectionLabel>
        </Reveal>
        <Reveal delay={0.1} className="text-center">
          <h1 className="mx-auto mt-6 max-w-[680px] text-balance text-[34px] font-semibold leading-[1.12] tracking-display text-carbon sm:text-[44px] md:text-[54px]">
            Watch a triage report take shape.
          </h1>
        </Reveal>
        <Reveal delay={0.18} className="text-center">
          <p className="mx-auto mt-6 max-w-copy text-[16px] leading-relaxed tracking-body text-graphite">
            Add the claim artefacts below and run the pipeline — six agents read them together
            and hand back one structured report.
          </p>
          <p className="mx-auto mt-3 max-w-copy text-[13px] font-medium tracking-body text-ember">
            This is a simulation with sample data, not connected to the real assessment service.
          </p>
        </Reveal>

        <Reveal delay={0.2} className="w-full">
          <form
            onSubmit={handleSubmit}
            className="mx-auto mt-14 w-full max-w-[820px] rounded-card border border-fog bg-white p-6 shadow-panel md:p-10"
          >
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <UploadField
                label="Vehicle & damage photos"
                hint={photos.length ? `${photos.length} file(s) selected` : "Click to upload images"}
                accept="image/*"
                multiple
                onChange={handlePhotos}
              />
              <UploadField
                label="Policy PDF"
                hint={policy ?? "Click to upload PDF"}
                accept="application/pdf"
                onChange={handlePolicy}
              />
            </div>

            <div className="mt-6">
              <label
                htmlFor="description"
                className="block text-[12px] font-medium uppercase tracking-[0.08em] text-graphite"
              >
                Incident description
              </label>
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                placeholder="Describe what happened — where, when, and how the collision occurred."
                className="mt-3 w-full resize-none rounded-input border border-fog bg-white px-4 py-3 text-[15px] tracking-body text-carbon placeholder:text-ash focus:border-lavender focus:outline-none focus:ring-2 focus:ring-lavender/20"
              />
            </div>

            <div className="mt-8 flex justify-center">
              <PillButton type="submit" size="lg">
                {status === "analyzing" ? "Analyzing…" : "Analyze claim"}
              </PillButton>
            </div>

            <AnimatePresence>
              {status !== "idle" && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.6, ease: EASE }}
                  className="overflow-hidden"
                >
                  <div className="mt-10 border-t border-fog pt-8">
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                      {agents.map((agent, i) => {
                        const done = i < agentsDone;
                        const active = i === agentsDone && status === "analyzing";
                        return (
                          <div
                            key={agent.name}
                            className={`flex items-center gap-2 rounded-input border px-3 py-2.5 transition-colors duration-500 ${
                              done ? "border-fog bg-linen" : "border-fog bg-white"
                            }`}
                          >
                            <span
                              className={`h-1.5 w-1.5 rounded-full transition-colors duration-500 ${
                                done ? "bg-mint" : active ? "animate-pulse bg-lavender" : "bg-fog"
                              }`}
                            />
                            <span className="text-[12px] font-medium tracking-body text-graphite">
                              {agent.name}
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    <AnimatePresence>
                      {status === "done" && (
                        <motion.div
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.8, ease: EASE }}
                        >
                          <div className="mt-8 rounded-card border border-fog bg-linen p-6">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <p className="text-[14px] font-semibold tracking-body text-carbon">
                                Triage report
                              </p>
                              <span className="inline-flex rounded-full bg-mint-wash px-2.5 py-1 text-[11px] font-medium text-mint">
                                Fast-track recommended
                              </span>
                            </div>
                            <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5 border-t border-fog pt-5 sm:grid-cols-5">
                              {mockResult.map((item, i) => (
                                <motion.div
                                  key={item.label}
                                  initial={{ opacity: 0, y: 10 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  transition={{ duration: 0.6, ease: EASE, delay: 0.15 + i * 0.1 }}
                                >
                                  <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-ash">
                                    {item.label}
                                  </p>
                                  <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">
                                    {item.value}
                                  </p>
                                </motion.div>
                              ))}
                            </div>
                          </div>
                          <p className="mt-6 text-center text-[13px] tracking-body text-ash">
                            Sample output for demonstration — connect the ClaimSight India API for a
                            live triage report.
                          </p>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </form>
        </Reveal>
      </div>
    </section>
  );
}

function UploadField({
  label,
  hint,
  accept,
  multiple,
  onChange,
}: {
  label: string;
  hint: string;
  accept: string;
  multiple?: boolean;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
}) {
  const inputId = label.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return (
    <div>
      <label
        htmlFor={inputId}
        className="block text-[12px] font-medium uppercase tracking-[0.08em] text-graphite"
      >
        {label}
      </label>
      <label
        htmlFor={inputId}
        className="mt-3 flex h-[120px] cursor-pointer flex-col items-center justify-center rounded-input border border-dashed border-fog bg-linen px-4 text-center transition-colors hover:border-lavender"
      >
        <span className="text-[14px] tracking-body text-graphite">{hint}</span>
      </label>
      <input
        id={inputId}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={onChange}
        className="sr-only"
      />
    </div>
  );
}
