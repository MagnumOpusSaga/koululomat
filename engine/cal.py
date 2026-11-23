"""Kalenterityökalut: pyhäpäivät (FI/SE/NO/DK), arkipäivät, viikot."""
from datetime import date, timedelta


def easter(y: int) -> date:
    a = y % 19
    b, c = divmod(y, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(y, month, day)


def public_holidays(country: str, y: int) -> dict:
    """Arkipyhät, jotka osuvat lukuvuoteen (vain päivämäärät -> nimi)."""
    e = easter(y)
    h = {}
    if country == "fi":
        h[date(y, 1, 1)] = "uudenvuodenpäivä"
        h[date(y, 1, 6)] = "loppiainen"
        h[e - timedelta(2)] = "pitkäperjantai"
        h[e + timedelta(1)] = "2. pääsiäispäivä"
        h[date(y, 5, 1)] = "vappu"
        h[e + timedelta(39)] = "helatorstai"
        h[date(y, 12, 6)] = "itsenäisyyspäivä"
        for d in (24, 25, 26):
            h[date(y, 12, d)] = "joulu"
    elif country == "no":
        h[date(y, 1, 1)] = "nyttårsdag"
        h[e - timedelta(3)] = "skjærtorsdag"
        h[e - timedelta(2)] = "langfredag"
        h[e + timedelta(1)] = "2. påskedag"
        h[date(y, 5, 1)] = "1. mai"
        h[date(y, 5, 17)] = "17. mai"
        h[e + timedelta(39)] = "Kristi himmelfartsdag"
        h[e + timedelta(50)] = "2. pinsedag"
        for d in (25, 26):
            h[date(y, 12, d)] = "jul"
    elif country == "se":
        h[date(y, 1, 1)] = "nyårsdagen"
        h[date(y, 1, 6)] = "trettondedag jul"
        h[e - timedelta(2)] = "långfredagen"
        h[e + timedelta(1)] = "annandag påsk"
        h[date(y, 5, 1)] = "första maj"
        h[e + timedelta(39)] = "Kristi himmelsfärdsdag"
        h[date(y, 6, 6)] = "nationaldagen"
        for d in (24, 25, 26):
            h[date(y, 12, d)] = "jul"
    elif country == "dk":
        h[date(y, 1, 1)] = "nytårsdag"
        h[e - timedelta(3)] = "skærtorsdag"
        h[e - timedelta(2)] = "langfredag"
        h[e + timedelta(1)] = "2. påskedag"
        h[e + timedelta(39)] = "Kristi himmelfartsdag"
        h[e + timedelta(50)] = "2. pinsedag"
        h[date(y, 6, 5)] = "grundlovsdag"
        for d in (24, 25, 26):
            h[date(y, 12, d)] = "jul"
    return h


def school_year_holidays(country: str, y1: int) -> dict:
    out = {}
    for y in (y1, y1 + 1):
        out.update(public_holidays(country, y))
    return out


def weekdays(a: date, b: date):
    d = a
    while d <= b:
        if d.weekday() < 5:
            yield d
        d += timedelta(1)


def clip_to_weekdays(a: date, b: date):
    ds = list(weekdays(a, b))
    return (ds[0], ds[-1]) if ds else (None, None)


def iso_week_range(y: int, w: int):
    mon = date.fromisocalendar(y, w, 1)
    return mon, mon + timedelta(4)


def week_of(d: date) -> int:
    return d.isocalendar()[1]
