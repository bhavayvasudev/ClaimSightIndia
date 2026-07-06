/** Minimal, recognizable provider marks — flat single/multi-tone SVGs,
 * not trademarked brand asset files. Sized via the parent's font-size
 * through `1em` width/height. */

export function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden width="1.15em" height="1.15em">
      <path
        fill="#4285F4"
        d="M46.5 24.5c0-1.6-.15-3.2-.42-4.7H24v9h12.6c-.55 2.9-2.2 5.35-4.7 7v5.8h7.6c4.45-4.1 7-10.15 7-17.1z"
      />
      <path
        fill="#34A853"
        d="M24 47c6.35 0 11.7-2.1 15.6-5.7l-7.6-5.8c-2.1 1.4-4.8 2.25-8 2.25-6.15 0-11.35-4.15-13.2-9.75H2.9v6.05C6.75 41.85 14.7 47 24 47z"
      />
      <path
        fill="#FBBC05"
        d="M10.8 27.9c-.45-1.35-.7-2.8-.7-4.3s.25-2.95.7-4.3v-6.05H2.9C1.35 16.35.5 20.05.5 23.6s.85 7.25 2.4 10.35z"
      />
      <path
        fill="#EA4335"
        d="M24 9.5c3.45 0 6.55 1.2 9 3.5l6.75-6.75C35.7 2.6 30.35.5 24 .5 14.7.5 6.75 5.65 2.9 13.4l7.9 6.05C12.65 13.85 17.85 9.5 24 9.5z"
      />
    </svg>
  );
}

export function AppleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden width="1.05em" height="1.05em" fill="currentColor">
      <path d="M16.365 1.43c0 1.14-.468 2.19-1.24 2.98-.83.86-2.19 1.53-3.31 1.44-.13-1.1.42-2.24 1.19-3.02.85-.86 2.29-1.5 3.36-1.4zM20.6 17.34c-.5 1.15-.74 1.66-1.38 2.68-.9 1.42-2.16 3.19-3.73 3.2-1.39.02-1.75-.9-3.64-.9-1.89 0-2.29.88-3.68.92-1.57.05-2.77-1.53-3.67-2.95C2.5 17.14 1.55 12.9 3.06 10.06c.85-1.6 2.36-2.62 4.02-2.64 1.53-.03 2.98.98 3.64.98.65 0 2.36-1.21 4.02-1.03.68.03 2.6.27 3.83 2.05-.1.06-2.29 1.31-2.27 3.9.03 3.1 2.75 4.13 2.78 4.14-.02.06-.42 1.42-1.48 2.88z" />
    </svg>
  );
}

export function FacebookIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden width="1.05em" height="1.05em" fill="currentColor">
      <path d="M13.5 21v-7.9h2.66l.4-3.09h-3.06V8.1c0-.9.25-1.5 1.53-1.5h1.64V3.85C15.9 3.8 15 3.72 13.94 3.72c-2.2 0-3.7 1.34-3.7 3.8v2.1H7.56v3.1H10.24V21z" />
    </svg>
  );
}
