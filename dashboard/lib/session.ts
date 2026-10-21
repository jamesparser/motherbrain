// Signed session cookie (HMAC-SHA256 via Web Crypto — works in middleware/edge and node).
export const COOKIE = "mb_session";
const enc = new TextEncoder();

function b64url(buf: ArrayBuffer | Uint8Array): string {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function secret(): string {
  return process.env.SESSION_SECRET || "dev-only-insecure-secret-change-me";
}

async function sign(data: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret()), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64url(await crypto.subtle.sign("HMAC", key, enc.encode(data)));
}

export type Session = { email: string; exp: number; demo: boolean };

export async function createSession(email: string, demo: boolean): Promise<string> {
  const payload = b64url(enc.encode(JSON.stringify({ email, demo, exp: Date.now() + 7 * 86400_000 })));
  return `${payload}.${await sign(payload)}`;
}

export async function readSession(token?: string): Promise<Session | null> {
  if (!token) return null;
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return null;
  const expected = await sign(payload);
  if (expected.length !== sig.length) return null;
  let diff = 0;
  for (let i = 0; i < sig.length; i++) diff |= expected.charCodeAt(i) ^ sig.charCodeAt(i);
  if (diff !== 0) return null;
  try {
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const s = JSON.parse(json) as Session;
    return s.exp > Date.now() ? s : null;
  } catch {
    return null;
  }
}
