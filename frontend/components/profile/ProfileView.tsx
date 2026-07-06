"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { useSession } from "next-auth/react";
import { PillButton } from "@/components/ui/PillButton";
import { Reveal } from "@/components/ui/Reveal";
import { SignInAgainButton } from "@/components/ui/SignInAgainButton";
import {
  ApiError,
  effectiveAvatarUrl,
  effectiveDisplayName,
  getMyProfile,
  isSupportedImageFile,
  resetMyAvatar,
  resolveAssetUrl,
  updateMyProfile,
  uploadMyAvatar,
  userFacingMessage,
  type ProfileUpdateInput,
  type UserProfile,
} from "@/lib/api";
import { notifyProfileUpdated } from "@/lib/profile/useProfile";

type LoadState = "loading" | "ready" | "error";

const MAX_AVATAR_BYTES = 5 * 1024 * 1024;

/** Initials fallback when no avatar image is available at all. */
export function initialsFor(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  return words
    .slice(0, 2)
    .map((word) => word[0]!.toUpperCase())
    .join("");
}

export function ProfileView() {
  const { data: session, status: sessionStatus } = useSession();
  const token = session?.backendAccessToken;

  const [state, setState] = useState<LoadState>("loading");
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      setProfile(await getMyProfile(token));
      setState("ready");
    } catch (err) {
      setErrorMessage(userFacingMessage(err));
      setErrorStatus(err instanceof ApiError ? err.status : null);
      setState("error");
    }
  }, [token]);

  useEffect(() => {
    // Same session gating as DashboardView: wait for the session, then
    // for the backend-token bootstrap, before the first authorized call.
    if (sessionStatus === "loading") return;
    if (sessionStatus === "authenticated" && session?.backendAuthPending) return;
    load();
  }, [load, sessionStatus, session?.backendAuthPending]);

  return (
    <div className="mx-auto max-w-[720px] px-6 pb-24 pt-32 md:px-8">
      <Reveal>
        <h1 className="text-[26px] font-semibold tracking-heading text-carbon">
          Profile &amp; Account
        </h1>
        <p className="mt-1 text-[14px] tracking-body text-graphite">
          Manage how you appear across ClaimSight and where we should reach you.
        </p>
      </Reveal>

      {state === "loading" && (
        <div aria-label="Loading your profile" className="mt-10 space-y-5">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-card border border-fog bg-white p-6">
              <div className="h-4 w-1/4 animate-pulse rounded bg-mist" />
              <div className="mt-4 h-10 w-full animate-pulse rounded-input bg-mist/60" />
              <div className="mt-3 h-10 w-2/3 animate-pulse rounded-input bg-mist/60" />
            </div>
          ))}
        </div>
      )}

      {state === "error" && (
        <div className="mt-16 flex flex-col items-center gap-4 text-center">
          <p className="text-[14px] tracking-body text-carbon">{errorMessage}</p>
          {errorStatus === 401 ? (
            <SignInAgainButton variant="ghost" />
          ) : (
            <PillButton onClick={load} variant="ghost">
              Try again
            </PillButton>
          )}
        </div>
      )}

      {state === "ready" && profile && (
        <div className="mt-10 space-y-5">
          <Reveal delay={0.05}>
            <IdentityCard profile={profile} />
          </Reveal>
          <Reveal delay={0.1}>
            <AvatarCard
              profile={profile}
              token={token}
              onUpdated={(updated) => {
                setProfile(updated);
                notifyProfileUpdated();
              }}
            />
          </Reveal>
          <Reveal delay={0.15}>
            <DetailsCard
              profile={profile}
              token={token}
              onUpdated={(updated) => {
                setProfile(updated);
                notifyProfileUpdated();
              }}
            />
          </Reveal>
        </div>
      )}
    </div>
  );
}

function Avatar({ profile, size }: { profile: UserProfile; size: number }) {
  const url = effectiveAvatarUrl(profile);
  if (url) {
    return (
      <Image
        src={resolveAssetUrl(url)}
        alt=""
        width={size}
        height={size}
        className="rounded-full object-cover"
        style={{ width: size, height: size }}
        unoptimized
      />
    );
  }
  return (
    <span
      aria-hidden
      style={{ width: size, height: size }}
      className="flex items-center justify-center rounded-full bg-lavender/15 text-[18px] font-semibold text-iris"
    >
      {initialsFor(effectiveDisplayName(profile))}
    </span>
  );
}

function IdentityCard({ profile }: { profile: UserProfile }) {
  const memberSince = profile.created_at
    ? new Date(profile.created_at).toLocaleDateString("en-IN", {
        year: "numeric",
        month: "long",
      })
    : null;
  const stats = profile.claim_stats;

  return (
    <section className="rounded-card border border-fog bg-white p-6">
      <div className="flex flex-wrap items-center gap-4">
        <Avatar profile={profile} size={56} />
        <div className="min-w-0">
          <p className="truncate text-[18px] font-semibold tracking-heading text-carbon">
            {effectiveDisplayName(profile)}
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-[13px] tracking-body text-graphite">
            <span className="truncate">{profile.email}</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-mist px-2 py-0.5 text-[11px] font-medium text-graphite">
              <GoogleMark />
              Signed in with Google
            </span>
          </p>
          {memberSince && (
            <p className="mt-0.5 text-[12px] tracking-body text-ash">Member since {memberSince}</p>
          )}
        </div>
      </div>

      {stats && stats.total > 0 && (
        <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="Total claims" value={stats.total} />
          <StatTile label="Under review" value={stats.under_review} />
          <StatTile label="Completed" value={stats.completed} />
          <StatTile label="Failed" value={stats.failed} />
        </dl>
      )}
    </section>
  );
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-input border border-fog bg-mist/30 px-4 py-3">
      <dt className="whitespace-nowrap text-[11px] font-medium uppercase tracking-[0.08em] text-ash">
        {label}
      </dt>
      <dd className="mt-1 text-[20px] font-semibold tracking-heading text-carbon">{value}</dd>
    </div>
  );
}

function AvatarCard({
  profile,
  token,
  onUpdated,
}: {
  profile: UserProfile;
  token: string | undefined;
  onUpdated: (profile: UserProfile) => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"upload" | "reset" | null>(null);
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  async function handleFile(file: File) {
    setFeedback(null);
    if (!isSupportedImageFile(file)) {
      setFeedback({ kind: "error", text: "Please choose a JPEG, PNG or WebP image." });
      return;
    }
    if (file.size > MAX_AVATAR_BYTES) {
      setFeedback({ kind: "error", text: "Profile photos must be 5MB or smaller." });
      return;
    }
    setBusy("upload");
    try {
      onUpdated(await uploadMyAvatar(file, token));
      setFeedback({ kind: "success", text: "Profile photo updated." });
    } catch (err) {
      setFeedback({ kind: "error", text: userFacingMessage(err) });
    } finally {
      setBusy(null);
    }
  }

  async function handleReset() {
    setFeedback(null);
    setBusy("reset");
    try {
      onUpdated(await resetMyAvatar(token));
      setFeedback({ kind: "success", text: "Back to your Google photo." });
    } catch (err) {
      setFeedback({ kind: "error", text: userFacingMessage(err) });
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="rounded-card border border-fog bg-white p-6">
      <h2 className="text-[15px] font-semibold tracking-heading text-carbon">Profile photo</h2>
      <p className="mt-1 text-[13px] leading-relaxed tracking-body text-graphite">
        Shown in the navigation and on your profile. Your Google photo is used until you upload one.
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-4">
        <Avatar profile={profile} size={64} />
        <div className="flex flex-wrap items-center gap-2">
          <PillButton
            size="sm"
            variant="ghost"
            disabled={busy !== null}
            onClick={() => fileInputRef.current?.click()}
          >
            {busy === "upload" ? "Uploading…" : "Upload photo"}
          </PillButton>
          {profile.custom_avatar_url && (
            <PillButton size="sm" variant="ghost" disabled={busy !== null} onClick={handleReset}>
              {busy === "reset" ? "Resetting…" : "Use Google photo"}
            </PillButton>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            // Allow re-selecting the same file after a failure.
            event.target.value = "";
            if (file) void handleFile(file);
          }}
        />
      </div>

      {feedback && <InlineFeedback kind={feedback.kind} text={feedback.text} />}
    </section>
  );
}

function DetailsCard({
  profile,
  token,
  onUpdated,
}: {
  profile: UserProfile;
  token: string | undefined;
  onUpdated: (profile: UserProfile) => void;
}) {
  const [displayName, setDisplayName] = useState(profile.display_name ?? profile.name ?? "");
  const [contactEmail, setContactEmail] = useState(profile.contact_email ?? "");
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  // What "no change" means against the loaded profile: the display-name
  // field shows the effective name, so matching either the custom or the
  // Google-derived value counts as untouched.
  const displayNameDirty =
    displayName.trim() !== (profile.display_name ?? profile.name ?? "").trim();
  const contactEmailDirty = contactEmail.trim() !== (profile.contact_email ?? "");
  const dirty = displayNameDirty || contactEmailDirty;

  async function handleSave() {
    setFeedback(null);
    const input: ProfileUpdateInput = {};
    if (displayNameDirty) {
      const trimmed = displayName.trim();
      if (!trimmed) {
        setFeedback({ kind: "error", text: "Display name cannot be blank." });
        return;
      }
      // Typing your Google name back = clearing the customization.
      input.display_name = trimmed === (profile.name ?? "").trim() ? null : trimmed;
    }
    if (contactEmailDirty) {
      input.contact_email = contactEmail.trim() === "" ? null : contactEmail.trim();
    }

    setSaving(true);
    try {
      const updated = await updateMyProfile(input, token);
      onUpdated(updated);
      setDisplayName(updated.display_name ?? updated.name ?? "");
      setContactEmail(updated.contact_email ?? "");
      setFeedback({ kind: "success", text: "Profile updated." });
    } catch (err) {
      setFeedback({ kind: "error", text: userFacingMessage(err) });
    } finally {
      setSaving(false);
    }
  }

  const inputClass =
    "mt-2 w-full rounded-input border border-fog bg-white px-4 py-3 text-[15px] tracking-body text-carbon placeholder:text-ash focus:border-lavender focus:outline-none focus:ring-2 focus:ring-lavender/20 disabled:opacity-60";

  return (
    <section className="rounded-card border border-fog bg-white p-6">
      <h2 className="text-[15px] font-semibold tracking-heading text-carbon">Account details</h2>

      <form
        className="mt-5 space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          if (dirty && !saving) void handleSave();
        }}
      >
        <div>
          <label htmlFor="profile-display-name" className="text-[13px] font-medium tracking-body text-carbon">
            Display name
          </label>
          <input
            id="profile-display-name"
            type="text"
            value={displayName}
            maxLength={64}
            disabled={saving}
            onChange={(event) => setDisplayName(event.target.value)}
            className={inputClass}
          />
          <p className="mt-1.5 text-[12px] tracking-body text-ash">
            How your name appears across ClaimSight.
          </p>
        </div>

        <div>
          <span className="text-[13px] font-medium tracking-body text-carbon">Account email</span>
          <div className="mt-2 w-full rounded-input border border-fog bg-mist/40 px-4 py-3 text-[15px] tracking-body text-graphite">
            {profile.email}
          </div>
          <p className="mt-1.5 text-[12px] tracking-body text-ash">
            Signed in through Google — this is your account identity and can&apos;t be edited here.
          </p>
        </div>

        <div>
          <label htmlFor="profile-contact-email" className="text-[13px] font-medium tracking-body text-carbon">
            Contact email <span className="font-normal text-ash">(optional)</span>
          </label>
          <input
            id="profile-contact-email"
            type="email"
            value={contactEmail}
            maxLength={320}
            disabled={saving}
            placeholder={profile.email}
            onChange={(event) => setContactEmail(event.target.value)}
            className={inputClass}
          />
          <p className="mt-1.5 text-[12px] tracking-body text-ash">
            Stored as your preferred contact for claim updates. Leave blank to use your account
            email.
          </p>
        </div>

        <div className="flex items-center gap-3 pt-1">
          <PillButton type="submit" size="md" disabled={!dirty || saving}>
            {saving ? "Saving…" : "Save changes"}
          </PillButton>
          {feedback && <InlineFeedback kind={feedback.kind} text={feedback.text} inline />}
        </div>
      </form>
    </section>
  );
}

function InlineFeedback({
  kind,
  text,
  inline = false,
}: {
  kind: "success" | "error";
  text: string;
  inline?: boolean;
}) {
  return (
    <p
      role="status"
      className={`${inline ? "" : "mt-4"} text-[13px] tracking-body ${
        kind === "success" ? "text-mint" : "text-ember"
      }`}
    >
      {text}
    </p>
  );
}

function GoogleMark() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="#4285F4"
        d="M23.5 12.27c0-.85-.08-1.66-.22-2.45H12v4.64h6.45a5.52 5.52 0 0 1-2.39 3.62v3h3.87c2.26-2.09 3.57-5.16 3.57-8.81Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.87-3c-1.07.72-2.45 1.15-4.06 1.15-3.12 0-5.77-2.11-6.71-4.95H1.29v3.1A11.99 11.99 0 0 0 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.29 14.29A7.2 7.2 0 0 1 4.91 12c0-.8.14-1.57.38-2.29v-3.1H1.29a12 12 0 0 0 0 10.78l4-3.1Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.77c1.76 0 3.34.6 4.58 1.79l3.44-3.44C17.95 1.19 15.24 0 12 0A11.99 11.99 0 0 0 1.29 6.61l4 3.1C6.23 6.88 8.88 4.77 12 4.77Z"
      />
    </svg>
  );
}
