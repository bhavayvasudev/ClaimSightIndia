import { describe, expect, it } from "vitest";
import { canStartGoogleSignIn } from "./signInGate";

describe("canStartGoogleSignIn", () => {
  it("blocks sign-in before the consent checkbox is checked", () => {
    expect(canStartGoogleSignIn(false, false)).toBe(false);
  });

  it("allows sign-in once consent is checked", () => {
    expect(canStartGoogleSignIn(true, false)).toBe(true);
  });

  it("blocks sign-in while a redirect is already in flight, even with consent", () => {
    expect(canStartGoogleSignIn(true, true)).toBe(false);
  });

  it("blocks sign-in when neither condition is met", () => {
    expect(canStartGoogleSignIn(false, true)).toBe(false);
  });
});
