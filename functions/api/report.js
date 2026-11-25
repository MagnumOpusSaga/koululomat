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
  const sv = f.get("lang") === "sv";
  let back = String(f.get("back") || "/");
  if (!/^\/(fi|sv)\/[a-z0-9-]+\/$/.test(back)) back = sv ? "/sv/" : "/";
  const msg = sv ? ["Tack!", "Meddelandet har sparats – vi läser källan och kontrollerar uppgiften.", "Tillbaka"]
                 : ["Kiitos!", "Ilmoitus tallennettu – luemme lähteen ja tarkistamme tiedon.", "Takaisin"];
  return new Response(`<!doctype html><html lang="${sv ? "sv" : "fi"}"><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>${msg[0]} | Koululomat</title><meta name="robots" content="noindex">` +
    `<body style="margin:0;background:#FFF6E5;color:#2A1B0F;font:18px/1.5 Nunito,system-ui,sans-serif"><main style="max-width:560px;margin:60px auto;padding:28px;background:#fff;border-radius:28px;box-shadow:0 6px 0 #E8D9C4">` +
    `<h1 style="margin:0 0 8px;font-weight:900">${msg[0]}</h1><p>${msg[1]}</p><p><a href="${back}" style="display:inline-block;background:#2A1B0F;color:#fff;padding:12px 22px;border-radius:99px;text-decoration:none;font-weight:900">${msg[2]}</a></p></main></body></html>`,
    { headers: { "content-type": "text/html; charset=utf-8" } });
}
