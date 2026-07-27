#!/usr/bin/env python3
"""Kolektor sygnalow dla portalu Gotowi Teraz. Uruchamiany przez GitHub Actions.

Co robi:
  1. Czyta rejestr_zrodel.json i pobiera kazdy kanal RSS/Atom/sitemap-news.
  2. Filtruje pozycje po slowach kluczowych (woda, prad, pozar, pogoda, OC).
  3. Klasyfikuje do kategorii, liczy score, zgaduje wspolrzedne po nazwie miasta.
  4. Deduplikuje po URL i dopisuje nowe pozycje do dane_sygnalow_pl.json.

Zasady bezpieczenstwa marki:
  - Pozycje ze smiercia ofiar sa odrzucane calkowicie.
  - Pozycje z rannymi dostaja flage tonu informacyjnego i nizszy score.

Uzycie: python3 collect.py [rejestr_zrodel.json] [dane_sygnalow_pl.json]
Standardowa biblioteka, bez zaleznosci zewnetrznych.
"""
import json, re, sys, html, pathlib, hashlib
import datetime as dt
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

REJESTR = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'rejestr_zrodel.json')
DANE = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else 'dane_sygnalow_pl.json')

TZ = dt.timezone(dt.timedelta(hours=2))
NOW = dt.datetime.now(TZ)
OKNO_DNI = 14          # ile dni wstecz przyjmujemy z kanalu
UA = 'Mozilla/5.0 (compatible; GotowiTerazMonitor/1.0; +https://github.com/jakubmiszt-gt/gotowi-mapa)'

# --- Normalizacja ------------------------------------------------------------
# Czesc kanalow publikuje tytuly bez polskich znakow albo z encjami. Wszystkie
# wzorce dopasowujemy do tekstu pozbawionego diakrytykow, zeby filtr dzialal
# niezaleznie od tego, jak redakcja zapisala tytul. Dotyczy to zwlaszcza filtru
# ofiar smiertelnych, ktory nie moze przepuscic pozycji przez brak ogonka.
_MAPA = str.maketrans('ąćęłńóśźżĄĆĘŁŃÓŚŹŻ', 'acelnoszzACELNOSZZ')


def norm(s):
    return s.translate(_MAPA).lower()


# --- Slowniki tematyczne -----------------------------------------------------
# Wzorce pisane BEZ diakrytykow, bo dopasowujemy je do norm(tekst).
# waga: punkty bazowe, kat: kategoria sygnalu na portalu
TEMATY = [
    (r'brak wody|awaria wodoci|awaria sieci wodoc|wylacz\w* wody|przerw\w* w dostaw\w* wody|beczkowoz|bez wody', 72, 'reaktywna', 'woda'),
    (r'skazen\w* wody|woda nie nadaje sie|zakaz picia|bakteri\w* coli|enterokok|sanepid.{0,40}wod', 78, 'reaktywna', 'woda'),
    (r'zakaz podlewania|ograniczen\w* poboru wody|reglamentacj\w* wody|niedobor wody|susza.{0,30}wod|wod.{0,30}susza', 55, 'swiadomosc', 'susza'),
    (r'brak pradu|awari\w* zasilania|wylacz\w* pradu|bez pradu|przerw\w* w dostaw\w* (energii|pradu)|awaria pradu', 66, 'reaktywna', 'prad'),
    (r'pozar.{0,60}ewakuac|ewakuac.{0,60}pozar|pozar (bloku|kamienic|akademik|budynku|domu|mieszkani)', 74, 'reaktywna', 'pozar'),
    (r'podtopieni|zalan\w* (posesj|dom|ulic|piwnic|budynk)|wystapil\w* z brzegow|powodz|oberwanie chmury', 76, 'reaktywna', 'powodz'),
    (r'interwencj\w* strazak|zgloszen.{0,30}strazac|strazacy interweniowali|nawalnic|wichur|zerwan\w* dach', 68, 'reaktywna', 'burza'),
    (r'imgw|ostrzezeni\w* (meteo|hydro|przed)|alert rcb|burz\w* z gradem|ostrzega przed|alarm przeciwpowodziow', 62, 'wyprzedzajaca', 'pogoda'),
    (r'obron\w* cywiln|ochron\w* ludnosci|syren\w* alarmow|cwiczeni\w*.{0,30}alarm|magazyn przeciwkryzysow|schron', 60, 'lead-samorzad', 'oc'),
    (r'zarzadzani\w* kryzysow|sztab kryzysow|stan alarmow|pogotowi\w* przeciwpowodziow', 64, 'wyprzedzajaca', 'kryzys'),
    (r'survival|prepping|zestaw przetrwania|torb\w* ewakuacyjn|plecak ewakuacyjn', 45, 'swiadomosc', 'survival'),
    (r'(dotacj|dofinansowani).{0,60}(obron\w* cywiln|ochron\w* ludnosci|bezpieczenstw)', 58, 'lead-samorzad', 'dotacja'),
]
# Wykluczenia: typowe falszywe alarmy i zdarzenia spoza kraju
STOP = re.compile(
    r'\bmecz\b|pilkar|siatkar|koszykar|zuzl|festiwal|koncert|jarmark|wernisaz'
    r'|horoskop|przepis na|konkurs pieknos|\bmiss \b|transfer.{0,20}klub|rozklad jazdy'
    r'|\bwe? (hiszpanii|francji|grecji|portugalii|kalifornii|turcji|wloszech|niemczech|czechach|ukrainie|rosji|usa)'
    r'|\b(hiszpani|francj|grecj|portugali|kaliforni|turcj)\w*\b.{0,30}\b(pozar|ewakuac|powodz)')
# Ofiary smiertelne: pozycja odrzucana calkowicie (zasada bezpieczenstwa marki)
SMIERC = re.compile(
    r'nie zyj|zginal|zginela|zginelo|zgineli|smiertel|ofiar\w* smiertel|zmarl|poniosl smierc'
    r'|znaleziono zwloki|tragiczn\w* (wypadek|smierc|final)|potracil.{0,20}smier')
RANNI = re.compile(r'rann\w|poszkodowan\w|trafil\w* do szpitala|w ciezkim stanie')

REKOMENDACJE = {
    'woda': 'Sygnal produktowy wprost: mieszkancy bez wody z kranu. Geo-fence na wskazany obszar, przekaz o zapasie wody na 72 godziny.',
    'susza': 'Formalne ograniczenie w korzystaniu z wody. Material do tresci edukacyjnych o zapasie wody w domu, ton rzeczowy.',
    'prad': 'Brak zasilania: latarki, powerbank, radio na baterie. Geo-fence na obszar wylaczenia, przekaz poradnikowy.',
    'pozar': 'Ewakuacja to moment wyjscia z domu bez niczego. Przekaz o torbie ewakuacyjnej i dokumentach pod reka.',
    'powodz': 'Kampania reaktywna w promieniu 15 km. Przekaz o zabezpieczeniu domu i zapasie na wypadek odciecia mediow.',
    'burza': 'Skutki nawalnicy usuwane teraz. Kampania reaktywna lokalna, ton informacyjno-poradnikowy.',
    'pogoda': 'Ostrzezenie przed zjawiskiem, ktore jeszcze nie uderzylo. Kampania wyprzedzajaca, przekaz: przygotuj sie zanim uderzy.',
    'oc': 'Watek obrony cywilnej i ochrony ludnosci. Lead do samorzadu oraz material do kampanii swiadomosciowej.',
    'kryzys': 'Sluzby w trybie kryzysowym. Kampania wyprzedzajaca na obszar objety dzialaniami.',
    'survival': 'Trafienie w slowo kluczowe z listy. Material do tresci i remarketingu, nie do kampanii sprzedazowej.',
    'dotacja': 'Gmina pozyskala srodki na ochrone ludnosci. Lead B2G: sprawdzic zakres zadania i termin realizacji.',
}


def pobierz(url, timeout=25):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA, 'Accept': 'application/rss+xml, application/xml, text/xml, */*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    if raw[:2] == b'\x1f\x8b':
        import gzip
        raw = gzip.decompress(raw)
    return raw


def tekst(el):
    return html.unescape(''.join(el.itertext())).strip() if el is not None else ''


def parsuj_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=TZ)
    except Exception:
        pass
    for f in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            d = dt.datetime.strptime(s.replace('Z', '+0000') if f.endswith('%z') else s[:len(f) + 6], f)
            return d if d.tzinfo else d.replace(tzinfo=TZ)
        except Exception:
            continue
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return dt.datetime(int(m[1]), int(m[2]), int(m[3]), 12, 0, tzinfo=TZ)
    return None


def pozycje(raw):
    """Zwraca liste (tytul, link, data, opis) z RSS, Atom albo sitemap-news."""
    out = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    ns = {'a': 'http://www.w3.org/2005/Atom',
          'n': 'http://www.google.com/schemas/sitemap-news/0.9',
          's': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for it in root.iter():
        tag = it.tag.split('}')[-1]
        if tag == 'item':                                  # RSS 2.0
            out.append((tekst(it.find('title')), tekst(it.find('link')),
                        parsuj_date(tekst(it.find('pubDate'))), tekst(it.find('description'))))
        elif tag == 'entry':                               # Atom
            ln = it.find('a:link', ns)
            out.append((tekst(it.find('a:title', ns)),
                        (ln.get('href') if ln is not None else ''),
                        parsuj_date(tekst(it.find('a:updated', ns)) or tekst(it.find('a:published', ns))),
                        tekst(it.find('a:summary', ns))))
        elif tag == 'url':                                 # sitemap-news
            nw = it.find('n:news', ns)
            if nw is None:
                continue
            out.append((tekst(nw.find('n:title', ns)), tekst(it.find('s:loc', ns)),
                        parsuj_date(tekst(nw.find('n:publication_date', ns))), ''))
    return [(t, l, d, o) for t, l, d, o in out if t and l]


def klasyfikuj(tekst_norm):
    """Przyjmuje tekst juz znormalizowany przez norm()."""
    if STOP.search(tekst_norm):
        return None
    best = None
    for wzor, waga, kat, temat in TEMATY:
        if re.search(wzor, tekst_norm):
            if best is None or waga > best[0]:
                best = (waga, kat, temat)
    return best


def zgadnij_geo(tekst_norm, miasta, domyslne):
    naj = None
    for nazwa, geo in miasta.items():
        if re.search(r'\b' + re.escape(norm(nazwa)), tekst_norm):
            if naj is None or len(nazwa) > len(naj[0]):
                naj = (nazwa, geo)
    if naj:
        return naj[1], naj[0].title()
    return domyslne, None


def main():
    rej = json.loads(REJESTR.read_text(encoding='utf-8'))
    dane = json.loads(DANE.read_text(encoding='utf-8'))
    miasta = rej.get('miasta', {})

    znane = set()
    for s in dane['sygnaly']:
        for src in s.get('src', []):
            znane.add(src.get('url', '').split('?')[0].rstrip('/'))
        znane.add(s['id'])

    prog = NOW - dt.timedelta(days=OKNO_DNI)
    nowe, stat_ok, stat_err = [], 0, []

    for z in rej['zrodla']:
        try:
            raw = pobierz(z['url'])
            items = pozycje(raw)
            stat_ok += 1
        except Exception as e:
            stat_err.append(f"{z['id']}: {type(e).__name__}")
            continue

        for tytul, link, data, opis in items:
            klucz = link.split('?')[0].rstrip('/')
            if klucz in znane:
                continue
            if data is None or data < prog or data > NOW + dt.timedelta(hours=6):
                continue
            opis_czysty = re.sub(r'<[^>]+>', ' ', opis)[:400]
            tn = norm(f'{tytul} {opis_czysty}')
            if SMIERC.search(tn):
                continue                                   # zasada bezpieczenstwa marki
            k = klasyfikuj(tn)
            if not k:
                continue
            waga, kat, temat = k

            score = waga
            wiek_h = (NOW - data).total_seconds() / 3600
            score += 8 if wiek_h <= 24 else (3 if wiek_h <= 72 else -6)
            ton = ''
            if RANNI.search(tn):
                score -= 10
                ton = ' Flaga wrazliwosci: sa poszkodowani, ton wylacznie informacyjny, bez przekazu sprzedazowego.'
            score = max(20, min(95, score))

            geo, miasto = zgadnij_geo(tn, miasta, z.get('geo'))
            sid = 'auto-' + data.strftime('%Y-%m-%d') + '-' + hashlib.md5(klucz.encode()).hexdigest()[:8]

            nowe.append({
                'id': sid,
                'ts': data.astimezone(TZ).isoformat(),
                'wykryto': NOW.isoformat(timespec='minutes'),
                'woj': z['woj'],
                'prio': kat,
                'score': int(score),
                'title': tytul[:220],
                'loc': (miasto + ', ' if miasto else '') + z['nazwa'],
                'lat': geo[0] if geo else None,
                'lon': geo[1] if geo else None,
                'rec': REKOMENDACJE.get(temat, 'Sygnal do przegladu recznego.') + ton,
                'auto': True,
                'temat': temat,
                'src': [{'label': z['nazwa'] + ', ' + data.strftime('%d.%m'), 'url': link}],
            })
            znane.add(klucz)

    # Najnowsze na gorze, laczymy z dotychczasowymi
    dane['sygnaly'] = nowe + dane['sygnaly']
    dane['sygnaly'].sort(key=lambda s: s['ts'], reverse=True)
    dane['aktualizacja'] = NOW.isoformat(timespec='minutes')
    DANE.write_text(json.dumps(dane, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'Zrodla OK: {stat_ok}/{len(rej["zrodla"])}')
    if stat_err:
        print('Bledy:', '; '.join(stat_err[:12]))
    print(f'Nowych pozycji: {len(nowe)}')
    for s in nowe[:15]:
        print(f'  + [{s["score"]:>2}] {s["woj"]:<20} {s["title"][:70]}')
    print(f'Lacznie w bazie: {len(dane["sygnaly"])}')


if __name__ == '__main__':
    main()
