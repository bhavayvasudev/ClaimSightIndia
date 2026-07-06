"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type NotificationItem,
} from "@/lib/api";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/**
 * Restrained by design — a bell with an unread count and a short list.
 * Only meaningful events ever appear here (see backend
 * app/services/notifications/service.py: one notification per real event,
 * never per internal graph node), so this never needs to paginate deeply
 * or summarize/collapse entries.
 */
export function NotificationBell() {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  const token = session?.backendAccessToken;

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    async function load() {
      try {
        const result = await listNotifications(token);
        if (!cancelled) {
          setItems(result.items);
          setUnreadCount(result.unread_count);
        }
      } catch {
        // Non-critical background feature — a failed poll never disrupts
        // navigation or the rest of the page.
      }
    }

    load();
    const interval = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [token]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleMarkAllRead() {
    if (!token) return;
    try {
      await markAllNotificationsRead(token);
      setItems((prev) => prev.map((n) => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch {
      // Ignore — user can retry by reopening the panel.
    }
  }

  async function handleMarkRead(id: number) {
    if (!token) return;
    try {
      await markNotificationRead(id, token);
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // Ignore — non-critical.
    }
  }

  if (!token) return null;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label="Notifications"
        className="relative flex h-8 w-8 items-center justify-center rounded-full transition-colors duration-300 hover:bg-white/[0.06]"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path
            d="M12 3a5 5 0 0 0-5 5v3.2c0 .6-.2 1.2-.6 1.7L5 15h14l-1.4-2.1a2.8 2.8 0 0 1-.6-1.7V8a5 5 0 0 0-5-5Z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
            className="text-white/70"
          />
          <path d="M9.5 18a2.5 2.5 0 0 0 5 0" stroke="currentColor" strokeWidth="1.6" className="text-white/70" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute right-0.5 top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-ember text-[9px] font-semibold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-card border border-fog bg-white shadow-panel max-md:fixed max-md:left-1/2 max-md:right-auto max-md:top-16 max-md:w-[calc(100vw-2rem)] max-md:max-w-[360px] max-md:-translate-x-1/2">
          <div className="flex items-center justify-between border-b border-fog px-4 py-3">
            <p className="text-[13px] font-semibold tracking-heading text-carbon">Notifications</p>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAllRead}
                className="text-[12px] font-medium text-lavender hover:text-iris"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 ? (
              <p className="px-4 py-6 text-center text-[13px] tracking-body text-ash">No notifications yet.</p>
            ) : (
              items.map((item) => {
                const content = (
                  <div
                    className={`px-4 py-3 transition-colors ${item.read ? "" : "bg-lavender/[0.06]"}`}
                  >
                    <p className="text-[13px] font-medium tracking-body text-carbon">{item.title}</p>
                    <p className="mt-0.5 text-[12px] leading-relaxed tracking-body text-graphite">{item.body}</p>
                    <p className="mt-1 text-[11px] tracking-body text-ash">{timeAgo(item.created_at)}</p>
                  </div>
                );
                return item.claim_id ? (
                  <Link
                    key={item.id}
                    href={`/claims/${item.claim_id}`}
                    onClick={() => {
                      setOpen(false);
                      if (!item.read) handleMarkRead(item.id);
                    }}
                    className="block border-b border-fog last:border-b-0 hover:bg-mist/50"
                  >
                    {content}
                  </Link>
                ) : (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => !item.read && handleMarkRead(item.id)}
                    className="block w-full border-b border-fog text-left last:border-b-0 hover:bg-mist/50"
                  >
                    {content}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
