// Nimetön laskuri (K4-D): kasvattaa päiväkohtaista summaa. Ei tallenna IP-osoitetta, selainta, evästeitä
// eikä mitään, mistä kävijän voisi tunnistaa. Robotit ja testiselaimet ohitetaan (niitä ei tallenneta).
const KINDS = new Set(["view", "click", "quick_exit"]);
const KEY_RX = /^[a-z0-9_]{1,20}(:[01])?(>[a-z0-9_-]{1,30})?$/;
const BOT_RX = /bot|crawl|spider|slurp|headless|lighthouse|preview|monitor|curl|python|playwright/i;

export async function onRequestPost({ request, env }) {
  const ok = new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
  if (BOT_RX.test(request.headers.get("user-agent") || "")) return ok;
  let body;
  try { body = JSON.parse((await request.text()).slice(0, 200)); } catch { return ok; }
  const kind = String(body.k || ""), key = String(body.v || "");
  if (!KINDS.has(kind) || !KEY_RX.test(key)) return ok;
  const day = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Helsinki" });
  try {
    await env.DB.prepare("INSERT INTO counters (day, kind, key, n) VALUES (?, ?, ?, 1) " +
      "ON CONFLICT(day, kind, key) DO UPDATE SET n = n + 1").bind(day, kind, key).run();
  } catch (e) {
    await env.DB.prepare("CREATE TABLE IF NOT EXISTS counters (day TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, kind, key))").run();
  }
  return ok;
}
export const onRequest = () => new Response(null, { status: 405 });
