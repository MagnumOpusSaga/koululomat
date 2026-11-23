// "Ilmoita oikea päivä" -> D1 (sidonta DB). Ei IP-osoitteita, ei evästeitä, ei henkilötietoja.
export async function onRequestPost({ request, env }) {
  const f = await request.formData();
  if (f.get("website")) return Response.redirect(new URL("/", request.url), 303); // houkutuskenttä
  const municipality = String(f.get("municipality") || "").slice(0, 8);
  const message = String(f.get("message") || "").slice(0, 600).trim();
  let src = String(f.get("source_url") || "").slice(0, 300).trim();
  if (src && !/^https?:\/\//i.test(src)) src = "";
  if (!/^\d{3}$/.test(municipality) || message.length < 3) return new Response("Virheellinen ilmoitus", { status: 400 });
  await env.DB.prepare("CREATE TABLE IF NOT EXISTS report (id INTEGER PRIMARY KEY, municipality TEXT, year TEXT, message TEXT, source_url TEXT, day_hash TEXT, created_at TEXT)").run();
  await env.DB.prepare("INSERT INTO report (municipality, message, source_url, created_at) VALUES (?, ?, ?, datetime('now'))")
    .bind(municipality, message, src || null).run();
  // 24 kk säilytys
  if (Math.random() < 0.01) await env.DB.prepare("DELETE FROM report WHERE created_at < datetime('now','-24 months')").run();
  const back = new URL(request.headers.get("Referer") || "/", request.url);
  return new Response(`<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width"><p style="font:18px system-ui;max-width:600px;margin:40px auto">Kiitos! Ilmoitus tallennettu – luemme lähteen ja tarkistamme tiedon. <a href="${back.pathname}">Takaisin</a></p>`, { headers: { "content-type": "text/html; charset=utf-8" } });
}
