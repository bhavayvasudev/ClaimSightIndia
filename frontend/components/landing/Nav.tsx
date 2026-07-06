"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { motion, useMotionValueEvent, useScroll } from "framer-motion";
import { signOut, useSession } from "next-auth/react";
import { AssessmentCTAButton } from "../ui/AssessmentCTAButton";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import { EASE } from "@/lib/motion";

const UNAUTH_LINKS = [
  { label: "How It Works", href: "/#workflow" },
  { label: "About", href: "/#about" },
  { label: "Docs", href: "/docs" },
];

const AUTH_LINKS = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "New Assessment", href: "/claims/new" },
  { label: "Docs", href: "/docs" },
];

/**
 * Floating pill header: dark capsule centered at the top of the viewport,
 * blurred and hairline-bordered. Compresses slightly once the page scrolls.
 *
 * Nav content is driven entirely by the real Auth.js session
 * (`useSession`) — there is no separate "signed in" flag to fake, and
 * nothing here renders until the session has actually resolved.
 */
export function Nav() {
  const { scrollY } = useScroll();
  const [scrolled, setScrolled] = useState(false);
  useMotionValueEvent(scrollY, "change", (v) => setScrolled(v > 48));

  const { data: session, status } = useSession();
  const isAuthed = Boolean(session?.user);
  const links = isAuthed ? AUTH_LINKS : UNAUTH_LINKS;

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-50 flex justify-center px-4 pt-4">
      <motion.nav
        initial={{ opacity: 0, y: -24 }}
        animate={{ opacity: 1, y: 0, scale: scrolled ? 0.955 : 1 }}
        transition={{ duration: 0.8, ease: EASE }}
        className={`pointer-events-auto flex items-center gap-1 rounded-full border border-white/10 bg-carbon/90 backdrop-blur-md transition-[padding,box-shadow] duration-500 ${
          scrolled
            ? "py-1.5 pl-4 pr-1.5 shadow-[0_4px_16px_rgba(24,25,37,0.28),0_1px_2px_rgba(24,25,37,0.2)]"
            : "py-2 pl-5 pr-2 shadow-[0_12px_32px_rgba(24,25,37,0.3),0_2px_6px_rgba(24,25,37,0.22)]"
        }`}
      >
        <Link href="/" className="mr-2 flex items-center gap-2 md:mr-4">
          <span className="h-2.5 w-2.5 rounded-full bg-lavender" aria-hidden />
          <span className="text-[14px] font-semibold tracking-heading text-white">
            ClaimSight
          </span>
        </Link>

        <div className="hidden items-center md:flex">
          {links.map((link) => (
            <Link
              key={link.label}
              href={link.href}
              className="rounded-full px-3 py-1.5 text-[13px] font-medium text-white/65 transition-colors duration-300 hover:bg-white/[0.06] hover:text-white"
            >
              {link.label}
            </Link>
          ))}
        </div>

        {!isAuthed && status !== "loading" && (
          <Link
            href="/signin"
            className="hidden rounded-full px-3 py-1.5 text-[13px] font-medium text-white/65 transition-colors duration-300 hover:bg-white/[0.06] hover:text-white md:inline-flex md:items-center"
          >
            Sign In
          </Link>
        )}

        {isAuthed && (
          <div className="ml-1 hidden md:block">
            <NotificationBell />
          </div>
        )}

        {isAuthed && (
          <div ref={menuRef} className="relative ml-2 hidden md:block">
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-haspopup="true"
              className="flex items-center gap-2 rounded-full border-l border-white/10 py-1 pl-3 pr-2 transition-colors duration-300 hover:bg-white/[0.06]"
            >
              {session?.user?.image && (
                <Image
                  src={session.user.image}
                  alt=""
                  width={22}
                  height={22}
                  className="rounded-full"
                  unoptimized
                />
              )}
              <span className="max-w-[110px] truncate text-[13px] text-white/70">
                {session?.user?.name ?? session?.user?.email}
              </span>
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-full mt-2 w-56 rounded-card border border-fog bg-white p-1.5 shadow-panel">
                <div className="px-3 py-2">
                  <p className="truncate text-[13px] font-medium text-carbon">
                    {session?.user?.name ?? "Signed in"}
                  </p>
                  <p className="truncate text-[12px] text-ash">{session?.user?.email}</p>
                </div>
                <div className="my-1 h-px bg-fog" aria-hidden />
                <Link
                  href="/dashboard"
                  onClick={() => setMenuOpen(false)}
                  className="block rounded-input px-3 py-2 text-[13px] font-medium text-graphite transition-colors hover:bg-mist hover:text-carbon"
                >
                  Dashboard
                </Link>
                <button
                  type="button"
                  onClick={() => signOut({ callbackUrl: "/" })}
                  className="block w-full rounded-input px-3 py-2 text-left text-[13px] font-medium text-graphite transition-colors hover:bg-mist hover:text-carbon"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        )}

        {!isAuthed && (
          <div className="ml-2 md:ml-3">
            <AssessmentCTAButton size="sm">Request Demo</AssessmentCTAButton>
          </div>
        )}
      </motion.nav>
    </div>
  );
}
