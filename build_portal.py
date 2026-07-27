#!/usr/bin/env python3
"""Buduje portal informacji lokalnych Gotowi Teraz (uklad feed-first).

Zmiany wzgledem build_mapa.py:
  - Glownym widokiem jest strumien kart, nie mapa. Mapa jest panelem obok
    i pokazuje dokladnie to, co aktualnie widac w strumieniu.
  - Zamiast sztucznego podzialu "Mapa 72h" + "Archiwum" jest jeden strumien
    z przelacznikiem zakresu czasu (72h / 7 dni / 30 dni / wszystko).
  - Wyszukiwarka pelnotekstowa (tytul, lokalizacja, rekomendacja, zrodlo).
  - Filtry: wojewodztwo, kategoria. Liczniki aktualizuja sie wzajemnie.
  - Sygnaly ciagle (trwa_do) i leady do terminu maja etykiete "trwa" i nigdy
    nie znikaja z zakresu 72h, dopoki sa aktywne.
  - Responsywnosc: ponizej 900 px mapa laduje sie pod strumieniem.

Uzycie: python3 build_portal.py dane_sygnalow_pl.json Portal_Polska.html [--index]
"""
import json, sys, datetime, pathlib

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'dane_sygnalow_pl.json')
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else 'Portal_Polska.html')

data = json.loads(SRC.read_text(encoding='utf-8'))
data.setdefault('okno_mapy_h', 72)
data.setdefault('retencja_dni', 90)
data.setdefault('promien_geo_km', 15)
data.setdefault('centrum', [52.0, 19.4])
data.setdefault('zoom', 6)
data.setdefault('tytul', 'Monitoring lokalny, Gotowi Teraz')
payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

TPL = r"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Centrum informacji lokalnych | Gotowi Teraz</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>
  :root{--brand:#1F3B2C;--red:#C0392B;--yellow:#E8A200;--grey:#7F8C8D;--blue:#2E6DA4;
        --line:#e2e6e0;--bg:#F4F6F3;--card:#fff;--txt:#1a1a1a;--dim:#666;}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',system-ui,Arial,sans-serif;background:var(--bg);color:var(--txt);
       -webkit-font-smoothing:antialiased}
  header{background:var(--brand);color:#fff;padding:14px 20px;position:sticky;top:0;z-index:1200}
  .hrow{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}
  header h1{font-size:18px;font-weight:700;letter-spacing:-.2px}
  header .sub{font-size:12px;opacity:.82;margin-top:2px}
  .live{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.14);
        padding:4px 11px;border-radius:14px;font-size:12px;font-weight:600}
  .pulse{width:7px;height:7px;border-radius:50%;background:#57D9A3;animation:p 2s infinite}
  @keyframes p{0%,100%{opacity:1}50%{opacity:.35}}
  .stale{background:#B3261E;color:#fff;padding:9px 20px;font-size:13px;font-weight:600;display:none}

  .toolbar{background:#fff;border-bottom:1px solid var(--line);padding:11px 20px;
           position:sticky;top:62px;z-index:1100}
  .search{width:100%;max-width:520px;padding:9px 13px 9px 34px;border:1px solid #cfd6cc;
          border-radius:8px;font-size:14px;font-family:inherit;background:#fff url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='2'><circle cx='11' cy='11' r='7'/><path d='M21 21l-4.3-4.3'/></svg>") no-repeat 10px center}
  .search:focus{outline:none;border-color:var(--brand);box-shadow:0 0 0 3px rgba(31,59,44,.09)}
  .frow{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:9px}
  .flabel{font-size:11.5px;font-weight:700;color:#555;text-transform:uppercase;
          letter-spacing:.4px;margin-right:3px}
  .fb{border:1px solid #cfd6cc;background:#fff;padding:5px 12px;border-radius:15px;
      font-size:12.5px;cursor:pointer;font-family:inherit;color:#444;transition:.12s}
  .fb:hover{border-color:var(--brand);color:var(--brand)}
  .fb.active{background:var(--brand);color:#fff;border-color:var(--brand)}
  .fb .n{opacity:.6;margin-left:4px;font-size:11.5px}
  .fb.active .n{opacity:.75}

  .wrap{display:grid;grid-template-columns:1fr 480px;gap:18px;padding:18px 20px 40px;
        align-items:start;max-width:1700px;margin:0 auto}
  .feed{min-width:0}
  .side{position:sticky;top:150px}
  #map{height:calc(100vh - 210px);min-height:420px;border-radius:10px;
       border:1px solid var(--line);box-shadow:0 1px 3px rgba(0,0,0,.05)}
  .maphint{font-size:11.5px;color:var(--dim);margin-top:7px;line-height:1.5}

  .count{font-size:12.5px;color:var(--dim);margin-bottom:11px}
  .count b{color:var(--txt)}
  .day{font-size:12.5px;font-weight:700;color:var(--brand);text-transform:uppercase;
       letter-spacing:.5px;padding:14px 0 8px;display:flex;justify-content:space-between;
       align-items:baseline;border-bottom:2px solid var(--brand);margin-bottom:10px}
  .day span{font-size:11.5px;font-weight:400;color:var(--dim);text-transform:none;letter-spacing:0}
  .day:first-child{padding-top:0}

  .card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--grey);
        border-radius:8px;padding:13px 15px;margin-bottom:10px;cursor:pointer;transition:.14s}
  .card:hover{box-shadow:0 3px 12px rgba(0,0,0,.09);transform:translateY(-1px)}
  .card.sel{box-shadow:0 0 0 2px var(--brand)}
  .card.reaktywna{border-left-color:var(--red)}
  .card.wyprzedzajaca{border-left-color:var(--yellow)}
  .card.swiadomosc{border-left-color:var(--grey)}
  .card.lead-samorzad{border-left-color:var(--blue)}
  .ctop{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:7px}
  .badge{display:inline-block;padding:2px 8px;border-radius:10px;color:#fff;font-size:10px;
         font-weight:700;letter-spacing:.3px}
  .tag{display:inline-block;padding:2px 8px;border-radius:10px;background:#eef1ec;color:#555;
       font-size:10.5px;font-weight:600}
  .tag.trwa{background:#FDECEA;color:#B3261E}
  .score{margin-left:auto;font-size:11px;font-weight:700;color:var(--dim);
         background:#f1f3ef;padding:2px 8px;border-radius:9px}
  .card h3{font-size:14.5px;font-weight:650;line-height:1.4;margin-bottom:6px}
  .meta{font-size:11.5px;color:var(--dim);margin-bottom:7px}
  .card p{font-size:12.5px;line-height:1.6;color:#333;margin-bottom:7px}
  .srcs{font-size:11.5px}
  .srcs a{color:var(--blue);text-decoration:none;margin-right:11px}
  .srcs a:hover{text-decoration:underline}

  .empty{padding:44px 20px;text-align:center;color:var(--dim);background:#fff;
         border:1px solid var(--line);border-radius:10px}
  .empty h3{font-size:16px;color:var(--brand);margin-bottom:7px}
  .empty p{font-size:13px;line-height:1.6}
  .legend{background:#fff;border:1px solid var(--line);border-radius:8px;padding:11px 13px;
          font-size:11.5px;line-height:1.9;margin-top:10px}
  .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;
       vertical-align:middle}
  .popup-t{font-weight:700;margin-bottom:4px;font-size:13px}
  .popup-s{font-size:12px;line-height:1.5}
  .popup-s a{color:var(--blue)}

  @media(max-width:900px){
    .wrap{grid-template-columns:1fr;padding:14px 13px 30px}
    .side{position:static;order:2}
    #map{height:340px;min-height:0}
    .toolbar{position:static}
    header{position:static}
  }
</style>
</head>
<body>
<header>
  <div class="hrow">
    <div>
      <h1 id="tyt">Centrum informacji lokalnych</h1>
      <div class="sub" id="hdr">Gotowi Teraz</div>
    </div>
    <div class="live"><span class="pulse"></span><span id="livetxt">na żywo</span></div>
  </div>
</header>
<div class="stale" id="stale"></div>

<div class="toolbar">
  <input class="search" id="q" type="search" placeholder="Szukaj: miejscowość, powiat, temat, źródło...">
  <div class="frow" id="f-czas"><span class="flabel">Okres</span></div>
  <div class="frow" id="f-woj"><span class="flabel">Województwo</span></div>
  <div class="frow" id="f-kat"><span class="flabel">Kategoria</span></div>
</div>

<div class="wrap">
  <section class="feed">
    <div class="count" id="count"></div>
    <div id="feed"></div>
  </section>
  <aside class="side">
    <div id="map"></div>
    <div class="maphint" id="maphint"></div>
    <div class="legend">
      <span class="dot" style="background:#C0392B"></span><b>Reklama reaktywna</b>: kryzys trwa teraz<br>
      <span class="dot" style="background:#E8A200"></span><b>Reklama wyprzedzająca</b>: ostrzeżenie, kampania zanim uderzy<br>
      <span class="dot" style="background:#7F8C8D"></span><b>Budowanie świadomości</b>: dłuższy trend<br>
      <span class="dot" style="background:#2E6DA4"></span><b>Lead do samorządu</b>: sprzedaż do gminy, nie reklama konsumencka<br>
      <span style="color:#666">Wielkość markera odpowiada sile sygnału, okrąg to obszar targetowania.</span>
    </div>
  </aside>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const DATA = __DATA__;
const COLORS={reaktywna:"#C0392B",wyprzedzajaca:"#E8A200",swiadomosc:"#7F8C8D","lead-samorzad":"#2E6DA4"};
const LABELS={reaktywna:"REAKTYWNA",wyprzedzajaca:"WYPRZEDZAJĄCA",swiadomosc:"ŚWIADOMOŚĆ","lead-samorzad":"LEAD DO SAMORZĄDU"};
const NAZWY={all:"Wszystkie",reaktywna:"Reaktywna",wyprzedzajaca:"Wyprzedzająca",swiadomosc:"Świadomość","lead-samorzad":"Lead do samorządu"};
const PROMIEN = DATA.promien_geo_km;
const now = new Date();

document.getElementById('tyt').textContent = DATA.tytul;
document.title = DATA.tytul + ' | Gotowi Teraz';

function fmtDT(d){return d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric'})+' godz. '+d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'});}
function fmtD(d){return d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric'});}
function fmtDzien(d){
  const dzis=new Date(now.getFullYear(),now.getMonth(),now.getDate());
  const t=new Date(d.getFullYear(),d.getMonth(),d.getDate());
  const r=Math.round((dzis-t)/86400000);
  const nz=d.toLocaleDateString('pl-PL',{weekday:'long',day:'numeric',month:'long'});
  if(r===0) return 'Dzisiaj, '+nz;
  if(r===1) return 'Wczoraj, '+nz;
  return nz.charAt(0).toUpperCase()+nz.slice(1);
}
function ileTemu(d){
  const m=Math.round((now-d)/60000);
  if(m<60) return m+' min temu';
  const h=Math.round(m/60);
  if(h<24) return h+' godz. temu';
  const dn=Math.round(h/24);
  return dn+(dn===1?' dzień temu':' dni temu');
}

// Sygnal jest aktywny (trwajacy), gdy ma trwa_do w przyszlosci albo jest
// leadem, ktorego termin ofert jeszcze nie minal.
function aktywny(s){
  if(s.trwa_do) return new Date(s.trwa_do) >= now;
  if(s.prio==='lead-samorzad' && s.termin) return new Date(s.termin) >= now;
  return false;
}

DATA.sygnaly.forEach(s=>{ s._d=new Date(s.ts); s._akt=aktywny(s);
  s._txt=[s.title,s.loc,s.rec,s.woj,(s.src||[]).map(x=>x.label).join(' ')].join(' ').toLowerCase(); });
DATA.sygnaly.sort((a,b)=>b._d-a._d);

const OKRESY=[{k:'72',l:'Ostatnie 72h',h:72},{k:'7',l:'7 dni',h:168},
              {k:'30',l:'30 dni',h:720},{k:'all',l:'Wszystko',h:null}];
let stan={okres:'7',woj:'all',kat:'all',q:''};

function wOkresie(s,okresKey){
  const o=OKRESY.find(x=>x.k===okresKey);
  if(!o.h) return true;
  if(s._akt) return true;           // trwajace zawsze widoczne
  return s._d >= new Date(now.getTime()-o.h*3600*1000);
}
// Filtr bez jednego wymiaru, zeby liczniki pokazywaly realne wyniki
function pas(s,pomin){
  if(pomin!=='okres' && !wOkresie(s,stan.okres)) return false;
  if(pomin!=='woj' && stan.woj!=='all' && s.woj!==stan.woj) return false;
  if(pomin!=='kat' && stan.kat!=='all' && s.prio!==stan.kat) return false;
  if(stan.q && !s._txt.includes(stan.q)) return false;
  return true;
}
const widoczne=()=>DATA.sygnaly.filter(s=>pas(s,null));

function chip(txt,n,akt,fn){
  const b=document.createElement('button');
  b.className='fb'+(akt?' active':'');
  b.innerHTML=txt+(n!==null?' <span class="n">'+n+'</span>':'');
  b.onclick=fn;
  return b;
}
function rysujFiltry(){
  const fc=document.getElementById('f-czas');
  fc.querySelectorAll('.fb').forEach(e=>e.remove());
  OKRESY.forEach(o=>{
    const n=DATA.sygnaly.filter(s=>pas(s,'okres')&&wOkresie(s,o.k)).length;
    fc.appendChild(chip(o.l,n,stan.okres===o.k,()=>{stan.okres=o.k;rysuj();}));
  });

  const fw=document.getElementById('f-woj');
  fw.querySelectorAll('.fb').forEach(e=>e.remove());
  const woje=[...new Set(DATA.sygnaly.map(s=>s.woj).filter(Boolean))].sort();
  fw.appendChild(chip('Cała Polska',DATA.sygnaly.filter(s=>pas(s,'woj')).length,stan.woj==='all',()=>{stan.woj='all';rysuj();}));
  woje.forEach(w=>{
    const n=DATA.sygnaly.filter(s=>pas(s,'woj')&&s.woj===w).length;
    if(n===0 && stan.woj!==w) return;
    fw.appendChild(chip(w,n,stan.woj===w,()=>{stan.woj=w;rysuj();}));
  });
  fw.style.display = woje.length>1 ? '' : 'none';

  const fk=document.getElementById('f-kat');
  fk.querySelectorAll('.fb').forEach(e=>e.remove());
  fk.appendChild(chip('Wszystkie',DATA.sygnaly.filter(s=>pas(s,'kat')).length,stan.kat==='all',()=>{stan.kat='all';rysuj();}));
  ['reaktywna','wyprzedzajaca','swiadomosc','lead-samorzad'].forEach(k=>{
    const n=DATA.sygnaly.filter(s=>pas(s,'kat')&&s.prio===k).length;
    if(n===0 && stan.kat!==k) return;
    fk.appendChild(chip(NAZWY[k],n,stan.kat===k,()=>{stan.kat=k;rysuj();}));
  });
}

function kartaHTML(s){
  const kiedy=fmtDT(s._d)+' ('+ileTemu(s._d)+')';
  const wykr=s.wykryto?'<br>Wykryto: '+fmtDT(new Date(s.wykryto)):'';
  let tagi='';
  if(s._akt && s.trwa_do) tagi+='<span class="tag trwa">TRWA do '+fmtD(new Date(s.trwa_do))+'</span>';
  if(s._akt && s.prio==='lead-samorzad'&&s.termin) tagi+='<span class="tag trwa">OFERTY do '+fmtD(new Date(s.termin))+'</span>';
  if(s.woj) tagi+='<span class="tag">'+s.woj+'</span>';
  const src=(s.src||[]).map(x=>'<a href="'+x.url+'" target="_blank" rel="noopener">'+x.label+'</a>').join('');
  return '<div class="ctop"><span class="badge" style="background:'+COLORS[s.prio]+'">'+LABELS[s.prio]+'</span>'
    +tagi+'<span class="score">'+s.score+' pkt</span></div>'
    +'<h3>'+s.title+'</h3>'
    +'<div class="meta">'+s.loc+'<br>'+kiedy+wykr+'</div>'
    +'<p>'+s.rec+'</p><div class="srcs">'+src+'</div>';
}

let map,warstwa;
function rysujMape(lista){
  if(!map){
    map=L.map('map',{scrollWheelZoom:false}).setView(DATA.centrum,DATA.zoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {maxZoom:18,attribution:'&copy; OpenStreetMap'}).addTo(map);
    warstwa=L.layerGroup().addTo(map);
  }
  warstwa.clearLayers();
  const pkt=[];
  lista.forEach(s=>{
    if(typeof s.lat!=='number'||typeof s.lon!=='number') return;
    if(s.prio!=='lead-samorzad'){
      L.circle([s.lat,s.lon],{radius:PROMIEN*1000,color:COLORS[s.prio],weight:1,
        opacity:.35,fillOpacity:.07}).addTo(warstwa);
    }
    const m=L.circleMarker([s.lat,s.lon],{radius:5+s.score/11,color:'#fff',weight:2,
      fillColor:COLORS[s.prio],fillOpacity:.9}).addTo(warstwa);
    m.bindPopup('<div class="popup-t">'+s.title+'</div><div class="popup-s">'+s.loc
      +'<br>'+fmtDT(s._d)+'<br><br>'+s.rec+'</div>',{maxWidth:320});
    m.on('click',()=>{
      const el=document.getElementById('c-'+s.id);
      if(el){document.querySelectorAll('.card').forEach(c=>c.classList.remove('sel'));
             el.classList.add('sel');el.scrollIntoView({behavior:'smooth',block:'center'});}
    });
    s._marker=m; pkt.push([s.lat,s.lon]);
  });
  if(pkt.length) map.fitBounds(pkt,{padding:[45,45],maxZoom:9});
  document.getElementById('maphint').textContent =
    pkt.length+' z '+lista.length+' pozycji ma współrzędne. Klik w marker podświetla wpis na liście.';
}

function rysuj(){
  rysujFiltry();
  const lista=widoczne();
  const feed=document.getElementById('feed');
  const cnt=document.getElementById('count');
  feed.innerHTML='';

  if(!lista.length){
    cnt.textContent='';
    feed.innerHTML='<div class="empty"><h3>Brak wyników</h3>'
      +'<p>Żaden wpis nie pasuje do wybranych filtrów. Spróbuj poszerzyć okres '
      +'lub wyczyścić wyszukiwanie.</p></div>';
    rysujMape([]);
    return;
  }
  const akt=lista.filter(s=>s._akt).length;
  cnt.innerHTML='<b>'+lista.length+'</b> '+(lista.length===1?'pozycja':'pozycji')
    +(akt?', w tym <b>'+akt+'</b> nadal aktywnych':'')
    +' | łącznie w bazie: '+DATA.sygnaly.length;

  let ostatni='';
  lista.forEach(s=>{
    const klucz=s._d.toDateString();
    if(klucz!==ostatni){
      ostatni=klucz;
      const n=lista.filter(x=>x._d.toDateString()===klucz).length;
      const h=document.createElement('div');
      h.className='day';
      h.innerHTML=fmtDzien(s._d)+'<span>'+n+(n===1?' wpis':' wpisy')+'</span>';
      feed.appendChild(h);
    }
    const c=document.createElement('article');
    c.className='card '+s.prio; c.id='c-'+s.id;
    c.innerHTML=kartaHTML(s);
    c.onclick=e=>{
      if(e.target.tagName==='A') return;
      document.querySelectorAll('.card').forEach(x=>x.classList.remove('sel'));
      c.classList.add('sel');
      if(s._marker){map.setView([s.lat,s.lon],10);s._marker.openPopup();}
    };
    feed.appendChild(c);
  });
  rysujMape(lista);
}

let t;
document.getElementById('q').addEventListener('input',e=>{
  clearTimeout(t);
  t=setTimeout(()=>{stan.q=e.target.value.trim().toLowerCase();rysuj();},180);
});

const akt=new Date(DATA.aktualizacja);
document.getElementById('hdr').textContent =
  'Gotowi Teraz | aktualizacja '+fmtDT(akt)+' | '+DATA.sygnaly.length+' pozycji w bazie';
document.getElementById('livetxt').textContent = ileTemu(akt).replace(' temu','');
const godz=(now-akt)/3600000;
if(godz>24){
  const b=document.getElementById('stale');
  b.style.display='block';
  b.textContent='Uwaga: dane nie były odświeżane od '+Math.round(godz)
    +' godzin. Sprawdź, czy codzienny przebieg monitoringu się wykonuje.';
}
rysuj();
</script>
</body>
</html>
"""

html = TPL.replace('__DATA__', payload)
OUT.write_text(html, encoding='utf-8')

if '--index' in sys.argv:
    idx = OUT.parent / 'index.html'
    idx.write_text(
        '<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={OUT.name}">'
        f'<link rel="canonical" href="{OUT.name}"><title>Gotowi Teraz</title></head>'
        f'<body><a href="{OUT.name}">Przejdź do portalu</a></body></html>',
        encoding='utf-8')

# Raport kontrolny
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2)))
def akt(s):
    if s.get('trwa_do'):
        return datetime.datetime.fromisoformat(s['trwa_do']) >= now
    if s['prio'] == 'lead-samorzad' and s.get('termin'):
        return datetime.datetime.fromisoformat(s['termin']) >= now
    return False

sig = data['sygnaly']
for h, lab in [(72, '72h'), (168, '7 dni'), (720, '30 dni')]:
    prog = now - datetime.timedelta(hours=h)
    n = sum(1 for s in sig if akt(s) or datetime.datetime.fromisoformat(s['ts']) >= prog)
    print(f'  {lab:>7}: {n:>3} pozycji')
print(f'  wszystko: {len(sig):>3} pozycji, aktywnych: {sum(1 for s in sig if akt(s))}')
woj = {}
for s in sig:
    woj[s.get('woj', 'brak')] = woj.get(s.get('woj', 'brak'), 0) + 1
print('  województwa:', len(woj))
print(f'plik: {OUT.name} {OUT.stat().st_size} B')
