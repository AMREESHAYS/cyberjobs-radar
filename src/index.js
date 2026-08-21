// Gate in front of the static site. Cloudflare Access would be the nicer
// answer, but it needs Zero Trust enabled on the account; this needs nothing
// beyond a Worker secret, and keeps the job list off the open internet.
const COOKIE = "cjr_key";
const YEAR = 60 * 60 * 24 * 365;

// constant-time-ish compare: same cost whatever the mismatch, so the response
// timing does not leak how much of the key was right
function sameKey(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function readCookie(header, name) {
  for (const part of (header || "").split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return null;
}

// Chrome fetches the manifest and the icons without credentials while deciding
// whether a site is installable, so gating those breaks "Install app". They
// carry no private data — the job list lives in /data.
const PUBLIC = [/^\/manifest\.webmanifest$/, /^\/icons\//, /^\/favicon\.ico$/];

export function isPublicPath(pathname) {
  return PUBLIC.some(rx => rx.test(pathname));
}

export function authorize(request, key) {
  if (!key) return { ok: true, reason: "no key configured — site is public" };
  const url = new URL(request.url);
  if (isPublicPath(url.pathname)) return { ok: true, reason: "installability asset" };
  const supplied = url.searchParams.get("k");
  if (supplied !== null) {
    return sameKey(supplied, key)
      ? { ok: true, setCookie: true, cleanUrl: url.pathname }
      : { ok: false };
  }
  return { ok: sameKey(readCookie(request.headers.get("cookie"), COOKIE), key) };
}

const LOCKED = `<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CyberJobs Radar</title>
<style>
 body{margin:0;min-height:100vh;display:grid;place-items:center;background:#070b18;
      color:#eaf0ff;font:16px/1.5 ui-sans-serif,system-ui,sans-serif}
 .box{background:#111935;border:1px solid #263056;border-radius:18px;padding:28px;max-width:320px}
 h1{font-size:18px;margin:0 0 6px} p{color:#9aa7c7;font-size:13px;margin:0 0 16px}
 input{width:100%;padding:11px 13px;border-radius:11px;border:1px solid #263056;
       background:#0b1226;color:#eaf0ff;font-size:15px;box-sizing:border-box}
 button{width:100%;margin-top:10px;padding:11px;border:0;border-radius:999px;font-weight:700;
        background:linear-gradient(120deg,#4fd6e0,#8b7bff);color:#06111f;font-size:15px}
</style>
<div class="box"><h1>CyberJobs Radar</h1><p>This list is private. Enter the access key.</p>
<form method="GET"><input name="k" type="password" autofocus placeholder="Access key"
 autocomplete="current-password"><button type="submit">Open</button></form></div>`;

export default {
  async fetch(request, env) {
    const verdict = authorize(request, env.SITE_KEY);
    if (!verdict.ok) {
      return new Response(LOCKED, {
        status: 401,
        headers: { "content-type": "text/html;charset=utf-8", "cache-control": "no-store" },
      });
    }
    if (verdict.setCookie) {
      // drop the key out of the URL so it stops appearing in history and referrers
      return new Response(null, {
        status: 302,
        headers: {
          location: verdict.cleanUrl,
          "set-cookie": `${COOKIE}=${encodeURIComponent(env.SITE_KEY)}; Max-Age=${YEAR}; Path=/; Secure; HttpOnly; SameSite=Lax`,
          "cache-control": "no-store",
        },
      });
    }
    return env.ASSETS.fetch(request);
  },
};
