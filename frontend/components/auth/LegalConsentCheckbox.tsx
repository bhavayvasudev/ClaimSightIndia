"use client";

import Link from "next/link";

/**
 * Custom-styled but fully native checkbox: the real `<input>` is visually
 * hidden (`sr-only`) but stays in the tab order and keyboard-operable
 * (Space toggles it, same as any checkbox) — a sibling `<span>` reflects
 * its checked/focus state via the `peer-*` variants, so there is a real
 * visible focus ring even though the native control itself is invisible.
 * The Terms/Privacy links are descendants of the `<label>`, not of the
 * checkbox itself: clicking a link inside a label activates the link,
 * not the label's control, so following either link can never toggle
 * consent or reach the sign-in button.
 */
export function LegalConsentCheckbox({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label htmlFor="legal-consent" className="flex cursor-pointer items-start gap-3 text-left">
      <input
        id="legal-consent"
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-[6px] border transition-colors duration-150 peer-focus-visible:ring-2 peer-focus-visible:ring-lavender peer-focus-visible:ring-offset-2 ${
          checked ? "border-lavender bg-lavender" : "border-fog bg-white"
        }`}
      >
        <svg
          width="11"
          height="9"
          viewBox="0 0 11 9"
          fill="none"
          className={`transition-opacity duration-150 ${checked ? "opacity-100" : "opacity-0"}`}
        >
          <path
            d="M1 4.3L4 7.3L10 1.3"
            stroke="white"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span className="text-[13px] leading-relaxed tracking-body text-graphite">
        I agree to the{" "}
        <Link
          href="/terms"
          onClick={(e) => e.stopPropagation()}
          className="font-medium text-carbon underline underline-offset-2 hover:text-lavender"
        >
          Terms of Service
        </Link>{" "}
        and{" "}
        <Link
          href="/privacy"
          onClick={(e) => e.stopPropagation()}
          className="font-medium text-carbon underline underline-offset-2 hover:text-lavender"
        >
          Privacy Policy
        </Link>
        .
      </span>
    </label>
  );
}
