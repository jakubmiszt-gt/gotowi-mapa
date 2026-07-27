#!/usr/bin/env python3
"""Buduje strone monitoringu regionalnego Gotowi Teraz z pliku dane_sygnalow.json.

Zasady:
  - Mapa pokazuje sygnaly swieze. Sygnal reklamowy jest swiezy, gdy jego data
    zdarzenia (ts) miesci sie w oknie okno_mapy_h. Lead do samorzadu jest swiezy,
    dopoki nie minal termin skladania ofert (pole termin); bez terminu dziala
    zwykla regula okna.
  - Starsze sygnaly trafiaja do zakladki Archiwum, pogrupowane po dniach malejaco,
    ograniczone do retencja_dni. Nic nie jest kasowane z pliku danych.
  - Kazdy sygnal moze miec pole wykryto (kiedy narzedzie go znalazlo). Jest
    pokazywane obok daty zdarzenia.
Uzycie: python3 build_mapa.py dane_sygnalow.json Mapa_Sygnalow_lubelskie.html
"""
import json, sys, datetime, pathlib

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'dane_sygnalow.json')
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else 'Mapa_Sygnalow_lubelskie.html')

data = json.loads(SRC.read_text(encoding='utf-8'))
data.setdefault('okno_mapy_h', 72)
data.setdefault('retencja_dni', 90)
data.setdefault('promien_geo_km', 15)
data.setdefault('centrum', [51.25, 22.9])
data.setdefault('zoom', 8)
data.setdefault('tytul', 'Monitoring regionalny sygnałów reklamowych, województwo lubelskie')
payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

TPL = r"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitoring regionalny, woj. lubelskie | Gotowi Teraz</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>
  :root{--brand:#1F3B2C;--red:#C0392B;--yellow:#E8A200;--grey:#7F8C8D;--blue:#2E6DA4;--line:#e0e4de;}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',Arial,sans-serif;background:#F4F6F3;color:#1a1a1a}
  header{background:var(--brand);color:#fff;padding:16px 22px}
  header h1{font-size:19px;font-weight:700}
  header p{font-size:12.5px;opacity:.85;margin-top:3px}
  .stale{background:#B3261E;color:#fff;padding:9px 22px;font-size:13px;font-weight:600;display:none}
  .tabs{display:flex;background:#16301f;padding:0 12px;gap:2px}
  .tab{padding:11px 20px;color:#c6d4c8;font-size:14px;font-weight:600;cursor:pointer;border-bottom:3px solid transparent;background:none;border-top:none;border-left:none;border-right:none;font-family:inherit}
  .tab:hover{color:#fff}
  .tab.active{color:#fff;border-bottom-color:var(--yellow);background:rgba(255,255,255,.07)}
  .tab .cnt{display:inline-block;background:rgba(255,255,255,.18);border-radius:10px;padding:0 7px;margin-left:6px;font-size:12px}
  .view{display:none}
  .view.active{display:block}
  .bar{display:flex;flex-wrap:wrap;gap:7px;align-items:center;padding:11px 22px;background:#fff;border-bottom:1px solid var(--line)}
  .bar strong{font-size:12.5px;margin-right:3px}
  .fb{border:1px solid #cfd6cc;background:#fff;padding:5px 13px;border-radius:15px;font-size:12.5px;cursor:pointer;font-family:inherit;color:#444}
  .fb.active{background:var(--brand);color:#fff;border-color:var(--brand)}
  #map{height:60vh;min-height:400px}
  .empty{padding:44px 22px;text-align:center;color:#666;background:#fff}
  .empty h3{font-size:16px;color:var(--brand);margin-bottom:7px}
  .empty p{font-size:13px}
  .legend{padding:13px 22px;background:#fff;font-size:12.5px;line-height:1.75;border-top:1px solid var(--line)}
  .dot{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;vertical-align:middle}
  .note{padding:12px 22px 24px;font-size:11.5px;color:#555;line-height:1.6}
  .arch{padding:6px 22px 30px}
  .day{margin-top:20px}
  .day h2{font-size:14px;color:var(--brand);padding:8px 0 7px;border-bottom:2px solid var(--brand);display:flex;justify-content:space-between;align-items:baseline}
  .day h2 span{font-size:11.5px;font-weight:400;color:#777}
  .card{background:#fff;border:1px solid var(--line);border-left:4px solid var(--grey);border-radius:5px;padding:11px 13px;margin-top:9px}
  .card.reaktywna{border-left-color:var(--red)}
  .card.wyprzedzajaca{border-left-color:var(--yellow)}
  .card.swiadomosc{border-left-color:var(--grey)}
  .card.lead-samorzad{border-left-color:var(--blue)}
  .card h3{font-size:13.5px;margin-bottom:5px;font-weight:600}
  .meta{font-size:11.5px;color:#666;margin-bottom:6px}
  .badge{display:inline-block;padding:1px 8px;border-radius:10px;color:#fff;font-size:10.5px;font-weight:600;margin-right:6px}
  .card p{font-size:12.5px;line-height:1.55;margin-bottom:4px}
  .card a{color:var(--blue)}
  .popup-t{font-weight:700;margin-bottom:4px;font-size:13px}
  .popup-s{font-size:12px;line-height:1.5}
  .popup-s a{color:var(--blue)}
</style>
</head>
<body>
<header>
  <h1 id="tyt">Monitoring sygnałów reklamowych</h1>
  <p id="hdr">Gotowi Teraz</p>
</header>
<div class="stale" id="stale"></div>

<div class="tabs">
  <button class="tab active" data-v="mapa"><span id="lbl-mapa">Mapa</span> <span class="cnt" id="c-mapa">0</span></button>
  <button class="tab" data-v="arch">Archiwum <span class="cnt" id="c-arch">0</span></button>
</div>

<section class="view active" id="v-mapa">
  <div class="bar" id="w-mapa" style="display:none"><strong>Województwo:</strong></div>
  <div class="bar" id="f-mapa"><strong>Kategoria:</strong></div>
  <div id="map"></div>
  <div class="empty" id="empty-mapa" style="display:none">
    <h3 id="empty-h">Brak świeżych sygnałów</h3>
    <p>To normalny stan, gdy w regionie nie dzieje się nic, co uzasadnia kampanię. Starsze sygnały znajdziesz w zakładce Archiwum.</p>
  </div>
  <div class="legend">
    <span class="dot" style="background:#C0392B"></span><strong>Reklama reaktywna</strong>: kryzys trwa teraz &nbsp;
    <span class="dot" style="background:#E8A200"></span><strong>Reklama wyprzedzająca</strong>: ostrzeżenie, kampania zanim uderzy &nbsp;
    <span class="dot" style="background:#7F8C8D"></span><strong>Budowanie świadomości</strong>: dłuższy trend &nbsp;
    <span class="dot" style="background:#2E6DA4"></span><strong>Lead do samorządu</strong>: sprzedaż do gminy, nie reklama konsumencka.
    Wielkość markera odpowiada sile sygnału (Signal Score), a przezroczysty okrąg to obszar targetowania.
  </div>
  <div class="note" id="note-mapa"></div>
</section>

<section class="view" id="v-arch">
  <div class="bar" id="w-arch" style="display:none"><strong>Województwo:</strong></div>
  <div class="bar" id="f-arch"><strong>Kategoria:</strong></div>
  <div class="arch" id="arch-body"></div>
  <div class="note" id="note-arch"></div>
</section>

<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const DATA = __DATA__;
const COLORS={reaktywna:"#C0392B",wyprzedzajaca:"#E8A200",swiadomosc:"#7F8C8D","lead-samorzad":"#2E6DA4"};
const LABELS={reaktywna:"REKLAMA REAKTYWNA",wyprzedzajaca:"REKLAMA WYPRZEDZAJĄCA",swiadomosc:"BUDOWANIE ŚWIADOMOŚCI","lead-samorzad":"LEAD DO SAMORZĄDU"};
const NAZWY={all:"Wszystkie",reaktywna:"Reaktywna",wyprzedzajaca:"Wyprzedzająca",swiadomosc:"Świadomość","lead-samorzad":"Lead do samorządu"};
document.getElementById('tyt').textContent = DATA.tytul;
document.title = DATA.tytul + ' | Gotowi Teraz';
const OKNO_H   = DATA.okno_mapy_h;
const RETENCJA = DATA.retencja_dni;
const PROMIEN  = DATA.promien_geo_km;

const now  = new Date();
const prog = new Date(now.getTime() - OKNO_H*3600*1000);

function fmtDT(d){
  return d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric'}) + ' godz. ' +
         d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'});
}
function fmtD(d){ return d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric'}); }
function fmtDzien(d){
  const s = d.toLocaleDateString('pl-PL',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
  return s.charAt(0).toUpperCase()+s.slice(1);
}
function klucz(d){ return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
function zrodla(s){ return (s.src||[]).map(x => '<a href="'+x.url+'" target="_blank" rel="noopener">'+x.label+'</a>').join(', '); }

/* swiezosc: lead zyje do terminu skladania ofert, reszta wg okna */
function czySwiezy(s){
  if(s.trwa_do){ return new Date(s.trwa_do) >= now; }        /* zdarzenie ciagle, np. zakaz picia wody */
  if(s.prio === 'lead-samorzad' && s.termin){ return new Date(s.termin) >= now; }
  return s.d >= prog;
}

const wszystkie = (DATA.sygnaly||[]).map(s => Object.assign({}, s, {d:new Date(s.ts)})).sort((a,b)=>b.d-a.d);
const swieze = wszystkie.filter(czySwiezy);
const granicaRet = new Date(now.getTime() - RETENCJA*24*3600*1000);
const stareWszystkie = wszystkie.filter(s => !czySwiezy(s));
const stare = stareWszystkie.filter(s => s.d >= granicaRet);
const poza  = stareWszystkie.length - stare.length;

document.getElementById('lbl-mapa').textContent = 'Mapa, ostatnie ' + OKNO_H + 'h';
document.getElementById('empty-h').textContent  = 'Brak sygnałów w ostatnich ' + OKNO_H + ' godzinach';
document.getElementById('c-mapa').textContent = swieze.length;
document.getElementById('c-arch').textContent = stare.length;
document.getElementById('hdr').textContent =
  'Gotowi Teraz | aktualizacja ' + fmtDT(new Date(DATA.aktualizacja)) +
  ' | okno mapy: ' + OKNO_H + 'h | sygnałów łącznie: ' + wszystkie.length;
document.getElementById('note-mapa').textContent =
  'Na mapie są wszystkie sygnały z ostatnich ' + OKNO_H + ' godzin, także słabe, bo one też niosą informację. ' +
  'Siłę sygnału pokazuje Signal Score i wielkość markera. Leady do samorządu zostają widoczne do upływu terminu składania ofert, ' +
  'potem sygnał przechodzi do Archiwum, uporządkowanego według dni.';
document.getElementById('note-arch').textContent =
  'Archiwum pokazuje ostatnie ' + RETENCJA + ' dni.' +
  (poza > 0 ? ' Starszych sygnałów: ' + poza + '. Pozostają w pliku dane_sygnalow.json i nie są kasowane.' : '');

/* ostrzezenie o nieaktualnosci */
const godzOdAkt = (now - new Date(DATA.aktualizacja)) / 3600000;
if(godzOdAkt > 24){
  const el = document.getElementById('stale');
  const dni = Math.floor(godzOdAkt/24);
  el.textContent = 'Uwaga: ostatni przebieg monitoringu był ' +
    (dni >= 1 ? dni + (dni === 1 ? ' dzień' : (dni < 5 ? ' dni' : ' dni')) : Math.round(godzOdAkt) + ' godzin') +
    ' temu. Dane mogą być nieaktualne, sprawdź, czy zadanie cykliczne działa.';
  el.style.display = 'block';
}

/* ---------- filtry ---------- */
function buildFiltry(boxId, zbior, cb){
  const box = document.getElementById(boxId);
  ['all','reaktywna','wyprzedzajaca','swiadomosc','lead-samorzad'].forEach(k => {
    const n = k==='all' ? zbior.length : zbior.filter(s=>s.prio===k).length;
    const b = document.createElement('button');
    b.className = 'fb' + (k==='all'?' active':'');
    b.textContent = NAZWY[k] + ' (' + n + ')';
    b.dataset.k = k;
    b.addEventListener('click', () => {
      box.querySelectorAll('.fb').forEach(x=>x.classList.remove('active'));
      b.classList.add('active'); cb(k);
    });
    box.appendChild(b);
  });
}

/* ---------- mapa ---------- */
let wojMapa='all', wojArch='all';
function buildWoj(boxId, zbior, cb){
  const lista = [...new Set(zbior.map(s=>s.woj).filter(Boolean))].sort();
  if(lista.length < 2) return;                     /* jedno wojewodztwo: filtr zbedny */
  const box = document.getElementById(boxId);
  box.style.display = 'flex';
  ['all', ...lista].forEach(w => {
    const n = w==='all' ? zbior.length : zbior.filter(s=>s.woj===w).length;
    const b = document.createElement('button');
    b.className = 'fb' + (w==='all'?' active':'');
    b.textContent = (w==='all' ? 'Cała Polska' : w) + ' (' + n + ')';
    b.addEventListener('click', () => {
      box.querySelectorAll('.fb').forEach(x=>x.classList.remove('active'));
      b.classList.add('active'); cb(w);
    });
    box.appendChild(b);
  });
}

let map=null, warstwa=null;
function promien(s){ return Math.max(8, 8 + (s-55)/45*16); }
function liniaCzasu(s){
  let t = '<strong>Zdarzenie:</strong> ' + fmtDT(s.d);
  if(s.wykryto) t += '<br><strong>Wykryto:</strong> ' + fmtDT(new Date(s.wykryto));
  if(s.termin)  t += '<br><strong>Termin ofert:</strong> ' + fmtDT(new Date(s.termin));
  if(s.trwa_do) t += '<br><strong>Obowiazuje do:</strong> ' + fmtDT(new Date(s.trwa_do));
  return t;
}
let katMapa='all';
function rysujMape(k){
  if(!map) return;
  warstwa.clearLayers();
  katMapa = (k===undefined ? katMapa : k);
  swieze.filter(s => (katMapa==='all' || s.prio===katMapa) && (wojMapa==='all' || s.woj===wojMapa)).forEach(s => {
    if(s.prio !== 'lead-samorzad'){
      L.circle([s.lat,s.lon],{radius:(s.promien_km||PROMIEN)*1000,color:COLORS[s.prio],weight:1,
        opacity:.5,fillColor:COLORS[s.prio],fillOpacity:.10}).addTo(warstwa);
    }
    L.circleMarker([s.lat,s.lon],{radius:promien(s.score),color:'#fff',weight:2,
      fillColor:COLORS[s.prio],fillOpacity:.9}).addTo(warstwa)
     .bindPopup('<div class="popup-t"><span class="badge" style="background:'+COLORS[s.prio]+'">'+
        LABELS[s.prio]+' | SCORE '+s.score+'</span><br>'+s.title+'</div>'+
        '<div class="popup-s">'+liniaCzasu(s)+'<br><strong>Lokalizacja:</strong> '+s.loc+
        '<br><strong>Rekomendacja:</strong> '+s.rec+'<br><strong>Źródła:</strong> '+zrodla(s)+'</div>',{maxWidth:340});
  });
}
if(swieze.length === 0){
  document.getElementById('map').style.display='none';
  document.getElementById('empty-mapa').style.display='block';
} else {
  map = L.map('map').setView(DATA.centrum, DATA.zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OpenStreetMap'}).addTo(map);
  warstwa = L.layerGroup().addTo(map);
  rysujMape('all');
}
buildFiltry('f-mapa', swieze, rysujMape);
buildWoj('w-mapa', swieze, w => { wojMapa = w; rysujMape(); });

/* ---------- archiwum ---------- */
let katArch='all';
function rysujArchiwum(k){
  const box = document.getElementById('arch-body');
  box.innerHTML = '';
  katArch = (k===undefined ? katArch : k);
  const lista = stare.filter(s => (katArch==='all' || s.prio===katArch) && (wojArch==='all' || s.woj===wojArch));
  if(lista.length === 0){
    box.innerHTML = '<div class="empty"><h3>Brak wpisów w archiwum dla tego filtru</h3><p>Zmień filtr kategorii.</p></div>';
    return;
  }
  const dni = {};
  lista.forEach(s => { const kk = klucz(s.d); (dni[kk] = dni[kk] || []).push(s); });
  Object.keys(dni).sort().reverse().forEach(kk => {
    const grupa = dni[kk];
    const sek = document.createElement('div');
    sek.className = 'day';
    const n = grupa.length;
    const ile = n === 1 ? '1 sygnał' : (n < 5 ? n+' sygnały' : n+' sygnałów');
    sek.innerHTML = '<h2>'+fmtDzien(grupa[0].d)+'<span>'+ile+'</span></h2>';
    grupa.sort((a,b)=>b.score-a.score).forEach(s => {
      const c = document.createElement('div');
      c.className = 'card ' + s.prio;
      let meta = fmtDT(s.d);
      if(s.wykryto) meta += ' &nbsp;|&nbsp; wykryto ' + fmtD(new Date(s.wykryto));
      if(s.termin)  meta += ' &nbsp;|&nbsp; termin ofert ' + fmtD(new Date(s.termin));
      if(s.trwa_do) meta += ' &nbsp;|&nbsp; obowiązywało do ' + fmtD(new Date(s.trwa_do));
      c.innerHTML = '<h3>'+s.title+'</h3>'+
        '<div class="meta"><span class="badge" style="background:'+COLORS[s.prio]+'">'+LABELS[s.prio]+
        ' | SCORE '+s.score+'</span> '+meta+' &nbsp;|&nbsp; '+s.loc+'</div>'+
        '<p><strong>Rekomendacja:</strong> '+s.rec+'</p>'+
        '<p style="font-size:11.5px;color:#666"><strong>Źródła:</strong> '+zrodla(s)+'</p>';
      sek.appendChild(c);
    });
    box.appendChild(sek);
  });
}
buildFiltry('f-arch', stare, rysujArchiwum);
buildWoj('w-arch', stare, w => { wojArch = w; rysujArchiwum(); });
rysujArchiwum('all');

/* ---------- zakladki ---------- */
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');
  document.getElementById('v-'+t.dataset.v).classList.add('active');
  if(t.dataset.v==='mapa' && map) setTimeout(()=>map.invalidateSize(),50);
}));
</script>
</body>
</html>
"""

OUT.write_text(TPL.replace('__DATA__', payload), encoding='utf-8')

# index.html tworzony tylko dla strony glownej (flaga --index),
# zeby przy wielu mapach nie nadpisywac przekierowania
idx = OUT.parent / 'index.html'
if '--index' in sys.argv:
    idx.write_text(
        '<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">'
        '<meta http-equiv="refresh" content="0; url=' + OUT.name + '">'
        '<link rel="canonical" href="' + OUT.name + '">'
        '<title>Monitoring | Gotowi Teraz</title></head>'
        '<body><p>Przekierowanie do <a href="' + OUT.name + '">mapy sygnałów</a>.</p></body></html>',
        encoding='utf-8')

# raport kontrolny
now = datetime.datetime.now(datetime.timezone.utc).astimezone()
prog = now - datetime.timedelta(hours=data['okno_mapy_h'])
gran = now - datetime.timedelta(days=data['retencja_dni'])
def swiezy(s):
    if s.get('trwa_do'):
        return datetime.datetime.fromisoformat(s['trwa_do']) >= now
    if s['prio'] == 'lead-samorzad' and s.get('termin'):
        return datetime.datetime.fromisoformat(s['termin']) >= now
    return datetime.datetime.fromisoformat(s['ts']) >= prog
sw = [s for s in data['sygnaly'] if swiezy(s)]
st = [s for s in data['sygnaly'] if not swiezy(s)]
st_w = [s for s in st if datetime.datetime.fromisoformat(s['ts']) >= gran]
print('teraz:', now.strftime('%Y-%m-%d %H:%M %Z'), '| okno:', data['okno_mapy_h'], 'h | retencja:', data['retencja_dni'], 'dni')
print('NA MAPIE (%d):' % len(sw))
for s in sw: print('   ', s['ts'][:16], s['prio'], s['score'], ('termin ' + s['termin'][:10]) if s.get('termin') else '', s['title'][:45])
dni = {}
for s in st_w: dni.setdefault(s['ts'][:10], []).append(s)
print('W ARCHIWUM (%d) w %d dniach, poza retencja: %d' % (len(st_w), len(dni), len(st)-len(st_w)))
for d in sorted(dni, reverse=True): print('   ', d, '->', len(dni[d]))
print('pliki:', OUT.name, OUT.stat().st_size, 'B' + (' | index.html -> ' + OUT.name if '--index' in sys.argv else ''))
