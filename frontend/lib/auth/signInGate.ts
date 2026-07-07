/**
 * The exact gating rule the sign-in page's Google button uses — both for
 * its `disabled` prop and for the click-handler guard, so there is a
 * single tested source of truth rather than two hand-kept copies that
 * could drift apart.
 */
export function canStartGoogleSignIn(consentChecked: boolean, isRedirecting: boolean): boolean {
  return consentChecked && !isRedirecting;
}
