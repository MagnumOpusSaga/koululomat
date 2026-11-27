-- Koululomat – tietomalli (Cloudflare D1 / SQLite)
-- Yksi malli neljälle maalle. Kaikki päivämäärät ISO (YYYY-MM-DD).

CREATE TABLE IF NOT EXISTS municipality (
  id          TEXT PRIMARY KEY,          -- 'fi:091', 'no:0301', 'se:0180', 'dk:101'
  country     TEXT NOT NULL CHECK (country IN ('fi','se','no','dk')),
  code        TEXT NOT NULL,             -- Tilastokeskus / SCB / SSB / DST
  name        TEXT NOT NULL,             -- pääkieli
  name_alt    TEXT,                      -- JSON {"sv":"Helsingfors","se":"..."}
  region      TEXT,                      -- maakunta / län / fylke / region
  population  INTEGER,
  website     TEXT,
  slug        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source (
  id            INTEGER PRIMARY KEY,
  municipality  TEXT NOT NULL REFERENCES municipality(id),
  url           TEXT NOT NULL,
  kind          TEXT NOT NULL CHECK (kind IN
                  ('kuntasivu','paatos','liite','forskrift','lovdata','wilma','koulu','muu')),
  format        TEXT CHECK (format IN ('html','pdf','pdf_scan','docx','image','xml')),
  fetched_at    TEXT NOT NULL,
  content_hash  TEXT NOT NULL,           -- sha256 tekstistä -> muutosvalvonta
  http_status   INTEGER,
  is_proposal   INTEGER NOT NULL DEFAULT 0,  -- "ehdotus/förslag/forslag/xx.xx"
  decided_on    TEXT,                    -- päätöspäivä, jos luettavissa
  last_checked  TEXT,
  UNIQUE (municipality, url)
);

CREATE TABLE IF NOT EXISTS school_year (
  id            INTEGER PRIMARY KEY,
  municipality  TEXT NOT NULL REFERENCES municipality(id),
  year          TEXT NOT NULL,           -- '2026-2027'
  school_form   TEXT NOT NULL DEFAULT 'perus' CHECK (school_form IN ('perus','esi','lukio','kaikki')),
  variant       TEXT NOT NULL DEFAULT '', -- '' | 'fi' | 'sv' | koulun nimi (kaksikieliset kunnat, poikkeavat koulut)
  status        TEXT NOT NULL CHECK (status IN ('päätetty','ehdotus','arvio')),
  confidence    TEXT NOT NULL CHECK (confidence IN ('varmistettu','yksi_lähde','ehdotus','arvio')),
  term1_start   TEXT,                    -- ensimmäinen koulupäivä
  term1_end     TEXT,                    -- viimeinen koulupäivä ennen joulua
  term2_start   TEXT,
  term2_end     TEXT,                    -- viimeinen koulupäivä keväällä
  school_days_doc   INTEGER,             -- dokumentin ilmoittama
  school_days_calc  INTEGER,             -- laskettu
  checks_json   TEXT,                    -- tarkistusten tulokset
  updated_at    TEXT NOT NULL,
  UNIQUE (municipality, year, school_form, variant)
);

CREATE TABLE IF NOT EXISTS holiday (
  id            INTEGER PRIMARY KEY,
  school_year   INTEGER NOT NULL REFERENCES school_year(id) ON DELETE CASCADE,
  kind          TEXT NOT NULL CHECK (kind IN
                  ('syys','joulu','talvi','paasiainen','kesa','vapaapaiva','koulupaiva_la','muu')),
  start_date    TEXT NOT NULL,           -- ensimmäinen koulupäivä, jolloin ei koulua (ei viikonloppuja)
  end_date      TEXT NOT NULL,
  label         TEXT,                    -- alkuperäinen nimi (hiihtoloma, sportlov, vinterferie…)
  source_id     INTEGER REFERENCES source(id),
  quote         TEXT,                    -- lyhyt kohta, josta luettiin
  page          INTEGER,                 -- pdf-sivu
  status        TEXT NOT NULL CHECK (status IN ('varmistettu','ehdotus','arvio','yksi_lähde')),
  updated_at    TEXT NOT NULL
);

-- Kaikki eri lähteistä luetut havainnot (ristiintarkistus tehdään näistä)
CREATE TABLE IF NOT EXISTS observation (
  id            INTEGER PRIMARY KEY,
  municipality  TEXT NOT NULL,
  year          TEXT NOT NULL,
  variant       TEXT NOT NULL DEFAULT '',
  field         TEXT NOT NULL,           -- 'term1_start' | 'syys' | 'talvi' …
  start_date    TEXT,
  end_date      TEXT,
  source_id     INTEGER NOT NULL REFERENCES source(id),
  reader        TEXT NOT NULL,           -- 'rules' | 'lovdata' | 'haiku' | 'sonnet' | 'human'
  quote         TEXT,
  page          INTEGER,
  observed_at   TEXT NOT NULL
);

-- Ihmistarkistusjono (laskentavirhe, poikkeama, ristiriita, ilmoitus kävijältä)
CREATE TABLE IF NOT EXISTS review_queue (
  id            INTEGER PRIMARY KEY,
  municipality  TEXT NOT NULL,
  year          TEXT,
  reason        TEXT NOT NULL,
  detail        TEXT,
  created_at    TEXT NOT NULL,
  resolved_at   TEXT
);

-- "Ilmoita oikea päivä" -lomake (ei IP-osoitteita, ei evästeitä)
CREATE TABLE IF NOT EXISTS report (
  id            INTEGER PRIMARY KEY,
  municipality  TEXT NOT NULL,
  year          TEXT,
  message       TEXT,
  source_url    TEXT,
  day_hash      TEXT,                    -- päiväkohtainen tiiviste rajoitukseen, ei tunnistettavissa
  created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_obs_mun_year ON observation(municipality, year);
CREATE INDEX IF NOT EXISTS idx_holiday_year ON holiday(school_year);

-- Nimetön laskuri (K4-D, Branun lupa 27.11.2026): vain päiväkohtaiset summat. Ei IP-osoitteita, ei evästeitä,
-- ei käyttäjätunnisteita. kind = view | click | quick_exit, key = sivutyyppi tai sivutyyppi>kohde.
CREATE TABLE IF NOT EXISTS counters (
  day TEXT NOT NULL,
  kind TEXT NOT NULL,
  key TEXT NOT NULL,
  n INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, kind, key)
);
