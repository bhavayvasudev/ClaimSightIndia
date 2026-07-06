"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export interface SearchableSelectOption {
  id: string;
  label: string;
  /** e.g. "Historical" / "Discontinued in India" — shown as a subtle tag,
   * never hidden (Task 12: historical/discontinued entries stay visible
   * and selectable, just distinguished). */
  badge?: string | null;
}

type Props = {
  label: string;
  placeholder: string;
  value: string | null;
  options: SearchableSelectOption[];
  onChange: (id: string | null) => void;
  disabled?: boolean;
  loading?: boolean;
  emptyMessage?: string;
  id?: string;
};

/**
 * Searchable, keyboard-accessible combobox shared by the manufacturer,
 * model, and variant selectors (Task 12). Bounded height with internal
 * scrolling rather than a native `<select>` — this catalog runs to
 * hundreds of entries per manufacturer's model list, which a native
 * dropdown handles poorly on both desktop and mobile.
 */
export function SearchableSelect({
  label,
  placeholder,
  value,
  options,
  onChange,
  disabled,
  loading,
  emptyMessage = "No results.",
  id,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlighted, setHighlighted] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const selected = useMemo(() => options.find((o) => o.id === value) ?? null, [options, value]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  useEffect(() => {
    setHighlighted(0);
  }, [query, open]);

  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.children[highlighted] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [highlighted, open]);

  function openList() {
    if (disabled) return;
    setQuery("");
    setOpen(true);
  }

  function selectOption(option: SearchableSelectOption | undefined) {
    if (!option) return;
    onChange(option.id);
    setQuery("");
    setOpen(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter") {
        e.preventDefault();
        openList();
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      selectOption(filtered[highlighted]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      setQuery("");
      inputRef.current?.blur();
    }
  }

  const inputId = id ?? label.toLowerCase().replace(/[^a-z0-9]+/g, "-");

  return (
    <div ref={containerRef} className="relative">
      <label htmlFor={inputId} className="block text-[12px] font-medium uppercase tracking-[0.08em] text-graphite">
        {label}
      </label>
      <input
        ref={inputRef}
        id={inputId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={`${inputId}-listbox`}
        aria-autocomplete="list"
        autoComplete="off"
        disabled={disabled}
        value={open ? query : (selected?.label ?? "")}
        placeholder={disabled ? placeholder : loading ? "Loading…" : placeholder}
        onFocus={openList}
        onClick={openList}
        onChange={(e) => {
          setQuery(e.target.value);
          if (!open) setOpen(true);
        }}
        onKeyDown={handleKeyDown}
        className="mt-3 w-full rounded-input border border-fog bg-white px-4 py-3 text-[15px] tracking-body text-carbon placeholder:text-ash focus:border-lavender focus:outline-none focus:ring-2 focus:ring-lavender/20 disabled:opacity-60"
      />

      {open && !disabled && (
        <ul
          ref={listRef}
          id={`${inputId}-listbox`}
          role="listbox"
          className="absolute z-20 mt-1.5 max-h-64 w-full overflow-y-auto rounded-input border border-fog bg-white py-1.5 shadow-panel"
        >
          {loading ? (
            <li className="px-4 py-3 text-[13px] tracking-body text-ash">Loading…</li>
          ) : filtered.length === 0 ? (
            <li className="px-4 py-3 text-[13px] tracking-body text-ash">{emptyMessage}</li>
          ) : (
            filtered.map((option, i) => (
              <li
                key={option.id}
                role="option"
                aria-selected={option.id === value}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectOption(option);
                }}
                onMouseEnter={() => setHighlighted(i)}
                className={`flex cursor-pointer items-center justify-between gap-2 px-4 py-2.5 text-[14px] tracking-body ${
                  i === highlighted ? "bg-lavender/10 text-carbon" : "text-carbon"
                }`}
              >
                <span>{option.label}</span>
                {option.badge && (
                  <span className="shrink-0 rounded-full bg-mist px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.06em] text-ash">
                    {option.badge}
                  </span>
                )}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
