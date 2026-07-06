"use client";

import type { ChangeEvent } from "react";

type UploadFieldProps = {
  label: string;
  hint: string;
  accept: string;
  multiple?: boolean;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
};

/**
 * Same visual language as the upload tiles on `/demo`
 * (components/landing/InteractiveDemo.tsx) — kept as a separate component
 * rather than importing that one because it's a private, differently-typed
 * implementation detail of the marketing mock (tracks file *names* only,
 * never real `File` objects). This version is shared by the real claim
 * intake flow, which needs actual files to upload.
 */
export function UploadField({ label, hint, accept, multiple, onChange }: UploadFieldProps) {
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
