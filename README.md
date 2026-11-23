# Koululomat

Koulujen lomat kunnittain (FI → NO → SE → DK). Data aina kunnan omasta lähteestä; jokaisella päivällä lähde, tila ja päivityspäivä.
Ei evästeitä, ei seurantaa, ei kohdennettua mainontaa.

- `engine/` – löytö, lähdesovittimet, lukijat (säännöt + tekoäly), tarkistukset
- `build/` – data → staattinen sivusto (Cloudflare Pages), `functions/` – palautelomake (D1)
- `.github/workflows/update.yml` – ajo viikoittain (loka–helmi) / kuukausittain

Salaisuudet (Settings → Secrets → Actions): `ANTHROPIC_API_KEY`, `BRAVE_API_KEY`, `CLOUDFLARE_API_TOKEN`.
Muuttujat (Variables): `CLOUDFLARE_ACCOUNT_ID`, `PREVIEW` (1 = noindex), `KOULULOMAT_CONTACT`.

© BR Entertainment (Y-tunnus 3183394-5)
