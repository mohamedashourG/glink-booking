"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ChevronDown, X } from "lucide-react";

/**
 * Searchable, keyboard-driven timezone picker.
 *
 * Why we wrote this instead of a library:
 * - Only one field uses it today; adding a combobox dependency (e.g.
 *   downshift, react-select) for a single picker is overkill.
 * - Native <datalist> doesn't show options on focus — only after typing,
 *   which the operator (rightly) called out as bad UX.
 *
 * What the component contributes vs. a plain <input>:
 * - Click/focus → panel opens with the full option list visible.
 * - Type → list filters by case-insensitive substring on each open.
 * - ↑/↓ → move the highlighted option; the panel auto-scrolls to keep
 *   the highlight in view.
 * - Enter → select highlighted, close panel, blur input.
 * - Esc → close panel, restore previous value (so a half-typed query
 *   doesn't accidentally become the field value on blur).
 * - Mouse outside → close panel.
 *
 * Form integration: the component renders a hidden <input name={name}>
 * carrying the *selected* value, so the surrounding <form> sees the right
 * thing regardless of what's currently typed in the visible input.
 */
export function TimezoneCombobox({
  id,
  name,
  options,
  defaultValue,
  placeholder = "Type or pick…",
  required = false,
  leftIcon,
}: {
  id: string;
  name: string;
  options: string[];
  defaultValue: string;
  placeholder?: string;
  required?: boolean;
  /** Optional left-side icon. Pass undefined for the minimal/no-icon look. */
  leftIcon?: ReactNode;
}) {
  const [value, setValue] = useState(defaultValue);     // committed selection
  const [query, setQuery] = useState("");                // what's in the text box
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLLIElement | null)[]>([]);

  // Filter list. When `query` is empty the full list is shown — that's the
  // "click to see all" behavior. Filtering uses lowercased substring so
  // both "berl" and "BERLIN" find Europe/Berlin.
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((tz) => tz.toLowerCase().includes(q));
  }, [query, options]);

  // Clamp active index whenever the filtered list shrinks (e.g. typing a
  // long query). Without this the keyboard nav can index off the array
  // end and produce a confusing 'nothing highlighted' state.
  useEffect(() => {
    if (activeIndex >= filtered.length) {
      setActiveIndex(Math.max(0, filtered.length - 1));
    }
  }, [filtered.length, activeIndex]);

  // Scroll the active item into view inside the panel. Native
  // `scrollIntoView({ block: "nearest" })` is the right primitive — it
  // only scrolls when the element is actually off-screen, so mouse
  // hovers don't fight the scroll position.
  useEffect(() => {
    if (!open) return;
    const el = itemRefs.current[activeIndex];
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open]);

  // Close on outside click. Using mousedown (not click) so the panel
  // closes BEFORE the click event fires on whatever was clicked — keeps
  // the focus flow predictable.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!wrapperRef.current?.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  function commit(nextValue: string) {
    setValue(nextValue);
    setQuery("");
    setOpen(false);
    inputRef.current?.blur();
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setActiveIndex((i) => Math.min(filtered.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setActiveIndex((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      if (!open) return;
      e.preventDefault();
      const choice = filtered[activeIndex];
      if (choice) commit(choice);
    } else if (e.key === "Escape") {
      if (open) {
        e.preventDefault();
        setOpen(false);
        setQuery("");
      }
    } else if (e.key === "Home") {
      if (open) {
        e.preventDefault();
        setActiveIndex(0);
      }
    } else if (e.key === "End") {
      if (open) {
        e.preventDefault();
        setActiveIndex(Math.max(0, filtered.length - 1));
      }
    }
  }

  function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    setQuery(e.target.value);
    setActiveIndex(0);                     // every keystroke resets to top match
    if (!open) setOpen(true);
  }

  function onFocus() {
    setOpen(true);
    // Position the highlight on the currently-selected value when the
    // panel opens, so ↓/↑ feel like "move from where I am" not "restart
    // at the top".
    const idx = options.findIndex((o) => o === value);
    if (idx >= 0) setActiveIndex(idx);
  }

  function clear() {
    setValue("");
    setQuery("");
    inputRef.current?.focus();
  }

  // What to show in the input: the live query when typing, otherwise the
  // committed value (so the picker always reflects 'this is what's
  // selected' when it's not focused).
  const displayValue = open ? query : value;

  return (
    <div ref={wrapperRef} className="relative">
      {/* Hidden field — what the surrounding <form> actually submits. */}
      <input type="hidden" name={name} value={value} required={required} />

      <div className="relative">
        {leftIcon && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400 pointer-events-none">
            {leftIcon}
          </span>
        )}
        <input
          ref={inputRef}
          id={id}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={`${id}-listbox`}
          aria-activedescendant={open && filtered[activeIndex] ? `${id}-opt-${activeIndex}` : undefined}
          aria-autocomplete="list"
          autoComplete="off"
          value={displayValue}
          onChange={onChange}
          onFocus={onFocus}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          className={`input pr-16 ${leftIcon ? "input-with-icon" : ""}`}
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {value && !open && (
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}     // keep focus on input
              onClick={clear}
              className="p-1 rounded hover:bg-ink-100 text-ink-400 hover:text-ink-700"
              aria-label="Clear timezone"
              title="Clear"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              if (open) {
                setOpen(false);
              } else {
                inputRef.current?.focus();              // focus triggers open via onFocus
              }
            }}
            className="p-1 rounded hover:bg-ink-100 text-ink-500"
            aria-label={open ? "Close timezone picker" : "Open timezone picker"}
            title={open ? "Close" : "Open"}
          >
            <ChevronDown
              className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`}
            />
          </button>
        </div>
      </div>

      {open && (
        <div
          ref={panelRef}
          className="absolute z-50 left-0 right-0 mt-1 rounded-lg border border-ink-200 bg-white shadow-pop overflow-hidden"
        >
          <ul
            id={`${id}-listbox`}
            role="listbox"
            className="max-h-72 overflow-y-auto py-1"
          >
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-ink-500 italic">
                No timezones match &ldquo;{query}&rdquo;
              </li>
            ) : (
              filtered.map((tz, i) => {
                const isActive = i === activeIndex;
                const isSelected = tz === value;
                return (
                  <li
                    key={tz}
                    id={`${id}-opt-${i}`}
                    ref={(el) => {
                      itemRefs.current[i] = el;
                    }}
                    role="option"
                    aria-selected={isSelected}
                    // Highlight on hover, but don't trigger React re-renders
                    // for every mousemove — onMouseEnter sets active state
                    // which keyboard nav also reads.
                    onMouseEnter={() => setActiveIndex(i)}
                    // Use onMouseDown so the click commits BEFORE the
                    // input loses focus + the outside-click handler tries
                    // to close us prematurely.
                    onMouseDown={(e) => {
                      e.preventDefault();
                      commit(tz);
                    }}
                    className={`px-3 py-1.5 text-sm cursor-pointer flex items-center justify-between ${
                      isActive ? "bg-brand-50 text-brand-900" : "text-ink-800"
                    }`}
                  >
                    <span className="font-mono">{tz}</span>
                    {isSelected && (
                      <span className="text-[0.65rem] uppercase tracking-wider text-brand-700">
                        selected
                      </span>
                    )}
                  </li>
                );
              })
            )}
          </ul>
          <div className="border-t border-ink-100 px-3 py-1.5 text-[0.65rem] text-ink-500 bg-ink-50/60 flex items-center justify-between">
            <span>
              {filtered.length === options.length
                ? `${options.length} timezones`
                : `${filtered.length} of ${options.length}`}
            </span>
            <span>↑↓ navigate · ↵ select · esc close</span>
          </div>
        </div>
      )}
    </div>
  );
}
