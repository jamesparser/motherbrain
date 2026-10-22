// Signed tokens (HMAC-SHA256 via Web Crypto — works in middleware/edge and node).
export const COOKIE = "mb_session";
const enc = new TextEncoder();

function b64url(buf: ArrayBuffer | Uint8Array): string {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function unb64url(s: string): string {
  return atob(s.replace(/-/g, "+").replace(/_/g, "/"));
}

function secret(): string {
  return process.env.SESSION_SECRET || "dev-only-insecure-secret-change-me";
}

async function sign(data: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret()), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64url(await crypto.subtle.sign("HMAC", key, enc.encode(data)));
}

export async function seal(obj: Record<string, unknown>): Promise<string> {
  const payload = b64url(enc.encode(JSON.stringify(obj)));
  return `${payload}.${await sign(payload)}`;
}

export async function unseal<T extends { exp: number }>(token?: string | null): Promise<T | null> {
  if (!token) return null;
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return null;
  const expected = await sign(payload);
  if (expected.length !== sig.length) return null;
  let diff = 0;
  for (let i = 0; i < sig.length; i++) diff |= expected.charCodeAt(i) ^ sig.charCodeAt(i);
  if (diff !== 0) return null;
  try {
    const v = JSON.parse(unb64url(payload)) as T;
    return v.exp > Date.now() ? v : null;
  } catch {
    return null;
  }
}

// method: "demo" (unverified, any email) | "google" | "email" (magic link)
export type Session = { email: string; exp: number; demo: boolean; verified?: boolean; method?: string; name?: string };

export async function createSession(email: string, demo: boolean, method = "demo", name?: string): Promise<string> {
  const verified = method === "google" || method === "email";
  return seal({ email: email.toLowerCase(), demo, verified, method, name, exp: Date.now() + 7 * 86400_000 });
}

export async function readSession(token?: string): Promise<Session | null> {
  return unseal<Session>(token);
}

export function ownerEmails(): string[] {
  return (process.env.OWNER_EMAILS || "").split(",").map((e) => e.trim().toLowerCase()).filter(Boolean);
}

export function isOwner(s: Session | null): boolean {
  return Boolean(s?.verified && ownerEmails().includes(s.email.toLowerCase()));
}

export function siteUrl(reqUrl: string): string {
  return (process.env.NEXT_PUBLIC_SITE_URL || new URL(reqUrl).origin).replace(/\/$/, "");
}

export const COOKIE_OPTS = {
  httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax" as const, path: "/", maxAge: 7 * 86400,
};
