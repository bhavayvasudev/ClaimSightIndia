import { Nav } from "@/components/landing/Nav";

/**
 * Route-level loading state for /claims/[id]. Rendered by the App Router
 * the instant navigation starts, before the page segment is ready — so
 * the handoff from the intake form's "Preparing your assessment report"
 * bridge is never a blank frame or a hard content pop.
 *
 * Deliberately identical in copy and layout to ClaimResultView's own
 * loading state (which takes over once the client component mounts and
 * fetches), so the two are indistinguishable to the user. Server
 * component: CSS-only animation, `motion-reduce:` honours
 * prefers-reduced-motion without JS.
 */
export default function ClaimReportLoading() {
  return (
    <main>
      <Nav />
      <div className="mx-auto flex min-h-screen max-w-content flex-col items-center justify-center px-6">
        <span
          className="h-5 w-5 animate-spin rounded-full border-2 border-fog border-t-lavender motion-reduce:animate-none"
          aria-hidden
        />
        <div className="mt-5 text-center">
          <p className="text-[15px] font-medium tracking-body text-carbon">
            Preparing your assessment report
          </p>
        </div>
      </div>
    </main>
  );
}
