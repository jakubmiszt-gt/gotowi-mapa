#!/usr/bin/env python3
"""Buduje strone monitoringu regionalnego z pliku dane_sygnalow.json.
Mapa pokazuje sygnaly z ostatnich 72h, starsze trafiaja do zakladki Archiwum,
pogrupowane po dniach malejaco."""
import json, sys, datetime, pathlib

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'dane_sygnalow.json')
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else 'Mapa_Sygnalow_lubelskie.html')

data = json.loads(SRC.read_text(encoding='utf-8'))
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
  /* archiwum */
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
  <h1>Monitoring regionalny sygnałów reklamowych, województwo lubelskie</h1>
  <p id="hdr">Gotowi Teraz</p>
</header>

<div class="tabs">
  <button class="tab active" data-v="mapa">Mapa, ostatnie 72h <span class="cnt" id="c-mapa">0</span></button>
  <button class="tab" data-v="arch">Archiwum <span class="cnt" id="c-arch">0</span></button>
</div>

<section class="view active" id="v-mapa">
  <div class="bar" id="f-mapa"><strong>Filtr:</strong></div>
  <div id="map"></div>
  <div class="empty" id="empty-mapa" style="display:none">
    <h3>Brak sygnałów w ostatnich 72 godzinach</h3>
    <p>To normalny stan, gdy w regionie nie dzieje się nic, co uzasadnia kampanię. Starsze sygnały znajdziesz w zakładce Archiwum.</p>
  </div>
  <div class="legend">
    <span class="dot" style="background:#C0392B"></span><strong>Reklama reaktywna</strong>: kryzys trwa teraz &nbsp;
    <span class="dot" style="background:#E8A200"></span><strong>Reklama wyprzedzająca</strong>: ostrzeżenie, kampania zanim uderzy &nbsp;
    <span class="dot" style="background:#7F8C8D"></span><strong>Budowanie świadomości</strong>: dłuższy trend &nbsp;
    <span class="dot" style="background:#2E6DA4"></span><strong>Lead do samorządu</strong>: sprzedaż do gminy, nie reklama konsumencka.
    Wielkość markera odpowiada sile sygnału (Signal Score).
  </div>
  <div class="note">Na mapie są wyłącznie sygnały z ostatnich 72 godzin. Po tym czasie sygnał automatycznie przechodzi do Archiwum, gdzie jest uporządkowany według dni.</div>
</section>

<section class="view" id="v-arch">
  <div class="bar" id="f-arch"><strong>Filtr:</strong></div>
  <div class="arch" id="arch-body"></div>
</section>

<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const DATA = __DATA__;
const COLORS={reaktywna:"#C0392B",wyprzedzajaca:"#E8A200",swiadomosc:"#7F8C8D","lead-samorzad":"#2E6DA4"};
const LABELS={reaktywna:"REKLAMA REAKTYWNA",wyprzedzajaca:"REKLAMA WYPRZEDZAJĄCA",swiadomosc:"BUDOWANIE ŚWIADOMOŚCI","lead-samorzad":"LEAD DO SAMORZĄDU"};
const NAZWY={all:"Wszystkie",reaktywna:"Reaktywna",wyprzedzajaca:"Wyprzedzająca",swiadomosc:"Świadomość","lead-samorzad":"Lead do samorządu"};
const OKNO_H = DATA.okno_mapy_h || 72;

const now = new Date();
const prog = new Date(now.getTime() - OKNO_H*3600*1000);
const wszystkie = (DATA.sygnaly||[]).map(s => Object.assign({}, s, {d:new Date(s.ts)}))
                                    .sort((a,b) => b.d - a.d);
const swieze = wszystkie.filter(s => s.d >= prog);
const stare  = wszystkie.filter(s => s.d <  prog);

document.getElementById('c-mapa').textContent = swieze.length;
document.getElementById('c-arch').textContent = stare.length;
document.getElementById('hdr').textContent =
  'Gotowi Teraz | aktualizacja ' + fmtDT(new Date(DATA.aktualizacja)) +
  ' | okno mapy: ' + OKNO_H + 'h | sygnałów łącznie: ' + wszystkie.length;

function fmtDT(d){
  return d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric'}) + ' godz. ' +
         d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'});
}
function fmtDzien(d){
  const s = d.toLocaleDateString('pl-PL',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
  return s.charAt(0).toUpperCase()+s.slice(1);
}
function klucz(d){ return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
function zrodla(s){ return (s.src||[]).map(x => '<a href="'+x.url+'" target="_blank" rel="noopener">'+x.label+'</a>').join(', '); }

/* ---------- filtry ---------- */
function buildFiltry(boxId, zbior, cb){
  const box = document.getElementById(boxId);
  const kat = ['all','reaktywna','wyprzedzajaca','swiadomosc','lead-samorzad'];
  kat.forEach(k => {
    const n = k==='all' ? zbior.length : zbior.filter(s=>s.prio===k).length;
    const b = document.createElement('button');
    b.className = 'fb' + (k==='all'?' active':'');
    b.textContent = NAZWY[k] + ' (' + n + ')';
    b.dataset.k = k;
    b.addEventListener('click', () => {
      box.querySelectorAll('.fb').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');
      cb(k);
    });
    box.appendChild(b);
  });
}

/* ---------- mapa ---------- */
let map=null, warstwa=null;
function promien(s){ return Math.max(8, 8 + (s-55)/45*16); }
function rysujMape(k){
  if(!map) return;
  warstwa.clearLayers();
  const lista = swieze.filter(s => k==='all' || s.prio===k);
  lista.forEach(s => {
    L.circleMarker([s.lat,s.lon],{radius:promien(s.score),color:'#fff',weight:2,
      fillColor:COLORS[s.prio],fillOpacity:.9}).addTo(warstwa)
     .bindPopup('<div class="popup-t"><span class="badge" style="background:'+COLORS[s.prio]+'">'+
        LABELS[s.prio]+' | SCORE '+s.score+'</span><br>'+s.title+'</div>'+
        '<div class="popup-s"><strong>Kiedy:</strong> '+fmtDT(s.d)+'<br><strong>Lokalizacja:</strong> '+s.loc+
        '<br><strong>Rekomendacja:</strong> '+s.rec+'<br><strong>Źródła:</strong> '+zrodla(s)+'</div>',{maxWidth:340});
  });
}
if(swieze.length === 0){
  document.getElementById('map').style.display='none';
  document.getElementById('empty-mapa').style.display='block';
} else {
  map = L.map('map').setView([51.25,22.9],8);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OpenStreetMap'}).addTo(map);
  warstwa = L.layerGroup().addTo(map);
  rysujMape('all');
}
buildFiltry('f-mapa', swieze, rysujMape);

/* ---------- archiwum ---------- */
function rysujArchiwum(k){
  const box = document.getElementById('arch-body');
  box.innerHTML = '';
  const lista = stare.filter(s => k==='all' || s.prio===k);
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
    const ile = grupa.length === 1 ? '1 sygnał' : (grupa.length < 5 ? grupa.length+' sygnały' : grupa.length+' sygnałów');
    sek.innerHTML = '<h2>'+fmtDzien(grupa[0].d)+'<span>'+ile+'</span></h2>';
    grupa.sort((a,b)=>b.score-a.score).forEach(s => {
      const c = document.createElement('div');
      c.className = 'card ' + s.prio;
      c.innerHTML = '<h3>'+s.title+'</h3>'+
        '<div class="meta"><span class="badge" style="background:'+COLORS[s.prio]+'">'+LABELS[s.prio]+
        ' | SCORE '+s.score+'</span> '+fmtDT(s.d)+' &nbsp;|&nbsp; '+s.loc+'</div>'+
        '<p><strong>Rekomendacja:</strong> '+s.rec+'</p>'+
        '<p style="font-size:11.5px;color:#666"><strong>Źródła:</strong> '+zrodla(s)+'</p>';
      sek.appendChild(c);
    });
    box.appendChild(sek);
  });
}
buildFiltry('f-arch', stare, rysujArchiwum);
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

html = TPL.replace('__DATA__', payload)
OUT.write_text(html, encoding='utf-8')

# raport kontrolny
now = datetime.datetime.now(datetime.timezone.utc).astimezone()
prog = now - datetime.timedelta(hours=data.get('okno_mapy_h', 72))
sw, st = [], []
for s in data['sygnaly']:
    (sw if datetime.datetime.fromisoformat(s['ts']) >= prog else st).append(s)
print('teraz:', now.strftime('%Y-%m-%d %H:%M %Z'))
print('prog 72h:', prog.strftime('%Y-%m-%d %H:%M %Z'))
print('NA MAPIE (%d):' % len(sw))
for s in sw: print('   ', s['ts'][:16], s['prio'], s['score'], s['title'][:55])
dni = {}
for s in st: dni.setdefault(s['ts'][:10], []).append(s)
print('W ARCHIWUM (%d) w %d dniach:' % (len(st), len(dni)))
for d in sorted(dni, reverse=True):
    print('   ', d, '->', len(dni[d]), 'szt.')
print('plik:', OUT, OUT.stat().st_size, 'B')
