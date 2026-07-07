import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearPendingConsent,
  markConsentGiven,
  readPendingConsent,
  syncPendingConsentIfNeeded,
} from "./consentSync";

/** Minimal in-memory Storage stand-in — no jsdom in this project's vitest
 * setup (node environment only), so a real localStorage/sessionStorage
 * isn't available to import. */
function fakeStorage(): Storage {
  const map = new Map<string, string>();
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => {
      map.set(key, value);
    },
    removeItem: (key: string) => {
      map.delete(key);
    },
    clear: () => map.clear(),
    key: () => null,
    get length() {
      return map.size;
    },
  } as Storage;
}

const VERSIONS = { termsVersion: "2026-07-07", privacyVersion: "2026-07-07" };

describe("markConsentGiven / readPendingConsent", () => {
  it("round-trips a freshly written marker", () => {
    const storage = fakeStorage();
    markConsentGiven(storage, VERSIONS, 1_000);
    expect(readPendingConsent(storage, 1_000)).toEqual({ ...VERSIONS, recordedAt: 1_000 });
  });

  it("returns null when nothing was ever written", () => {
    expect(readPendingConsent(fakeStorage())).toBeNull();
  });

  it("returns null for a marker older than the staleness window", () => {
    const storage = fakeStorage();
    markConsentGiven(storage, VERSIONS, 0);
    const elevenMinutesLater = 11 * 60 * 1000;
    expect(readPendingConsent(storage, elevenMinutesLater)).toBeNull();
  });

  it("returns null for malformed JSON instead of throwing", () => {
    const storage = fakeStorage();
    storage.setItem("claimsight:pendingLegalConsent", "not json");
    expect(readPendingConsent(storage)).toBeNull();
  });

  it("clearPendingConsent removes the marker", () => {
    const storage = fakeStorage();
    markConsentGiven(storage, VERSIONS, 1_000);
    clearPendingConsent(storage);
    expect(readPendingConsent(storage, 1_000)).toBeNull();
  });
});

describe("syncPendingConsentIfNeeded", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("does nothing when there is no pending marker", async () => {
    const fetchImpl = vi.fn();
    const outcome = await syncPendingConsentIfNeeded({
      storage: fakeStorage(),
      accessToken: "token",
      apiBaseUrl: "http://api.test",
      fetchImpl,
    });
    expect(outcome).toBe("no-marker");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("leaves the marker in place when there is no access token yet", async () => {
    const storage = fakeStorage();
    markConsentGiven(storage, VERSIONS, 1_000);
    const fetchImpl = vi.fn();

    const outcome = await syncPendingConsentIfNeeded({
      storage,
      accessToken: undefined,
      apiBaseUrl: "http://api.test",
      fetchImpl,
      now: 1_000,
    });

    expect(outcome).toBe("no-token");
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(readPendingConsent(storage, 1_000)).not.toBeNull();
  });

  it("posts the marker and clears it on success", async () => {
    const storage = fakeStorage();
    markConsentGiven(storage, VERSIONS, 1_000);
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true });

    const outcome = await syncPendingConsentIfNeeded({
      storage,
      accessToken: "abc123",
      apiBaseUrl: "http://api.test/",
      fetchImpl,
      now: 1_000,
    });

    expect(outcome).toBe("synced");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://api.test/users/consent",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer abc123" }),
        body: JSON.stringify({ terms_version: "2026-07-07", privacy_version: "2026-07-07" }),
      })
    );
    expect(readPendingConsent(storage, 1_000)).toBeNull();
  });

  it("keeps the marker for a later retry when the request fails", async () => {
    const storage = fakeStorage();
    markConsentGiven(storage, VERSIONS, 1_000);
    const fetchImpl = vi.fn().mockResolvedValue({ ok: false });

    const outcome = await syncPendingConsentIfNeeded({
      storage,
      accessToken: "abc123",
      apiBaseUrl: "http://api.test",
      fetchImpl,
      now: 1_000,
    });

    expect(outcome).toBe("failed");
    expect(readPendingConsent(storage, 1_000)).not.toBeNull();
  });

  it("keeps the marker when the network call throws", async () => {
    const storage = fakeStorage();
    markConsentGiven(storage, VERSIONS, 1_000);
    const fetchImpl = vi.fn().mockRejectedValue(new Error("offline"));

    const outcome = await syncPendingConsentIfNeeded({
      storage,
      accessToken: "abc123",
      apiBaseUrl: "http://api.test",
      fetchImpl,
      now: 1_000,
    });

    expect(outcome).toBe("failed");
    expect(readPendingConsent(storage, 1_000)).not.toBeNull();
  });
});
