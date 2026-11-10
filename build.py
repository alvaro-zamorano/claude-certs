#!/usr/bin/env python3
"""
Build del sitio público de claude-certs.

Las páginas en src/ son fragmentos (título, estilos y cuerpo). Este script las
envuelve en un documento HTML completo y aplica de forma sistemática lo que la
auditoría detectó como ausente, para que no haya que recordarlo página a página:

  · <!doctype html>, <html lang>, <meta charset>
  · meta description, Open Graph con imagen, Twitter card
  · favicon inline (SVG data URI, sin petición extra)
  · :focus-visible en todo lo interactivo
  · prefers-reduced-motion
  · corrección de contraste de --ink-3 a AA
  · estilos de impresión
  · pie con el aviso de material propio, en todas las páginas

Dos idiomas. El español vive en la raíz y el inglés bajo /en/, con slugs
propios (/apuntes/ y /en/notes/). Las páginas de prosa tienen un fragmento por
idioma en src/ y src/en/; las dos páginas interactivas son una sola base de
código con marcadores {{t.clave}} que se resuelven con src/i18n/<lang>.json,
para que la lógica no se duplique.

Uso:  python3 build.py
Salida: site/
"""
import os, re, shutil, json, datetime, hashlib
from collections import Counter

SRC = "src"
OUT = os.environ.get("CC_OUT", "site")
BASE = os.environ.get("CC_BASE", "https://certs.alvarozamorano.com").rstrip("/")

# El sitio vive normalmente en la raíz del dominio. CC_BASE_PATH lo monta bajo un
# subdirectorio (p.ej. /certs) para previsualizarlo dentro de un sitio que ya
# existe, sin tocar nada más: los fetch de datos ya son relativos, así que solo
# hay que prefijar los enlaces y las URLs canónicas.
BASE_PATH = "/" + os.environ.get("CC_BASE_PATH", "").strip("/") if os.environ.get("CC_BASE_PATH") else ""

# Las cuatro certificaciones. El sitio se organiza por ellas: se elige una y
# todo lo que se ve pertenece a ese examen.
CERTS = ["CCAR-F", "CCDV-F", "CCAO-F", "CCAR-P"]
CERT_SLUG = {"CCAR-F": "ccar-f", "CCDV-F": "ccdv-f", "CCAO-F": "ccao-f", "CCAR-P": "ccar-p"}

# Páginas que cuelgan de una certificación: slug canónico -> fragmento.
PAGES = {
    "test":       "test.html",
    "tarjetas":   "tarjetas.html",
    "apuntes":    "apuntes.html",
    "referencia": "referencia.html",
    "flash":      "flash.html",
    "ruta":       None,          # depende de la certificación
}

# Sólo dos exámenes tienen ruta de estudio escrita.
RUTA_SRC = {"CCAR-F": "architect.html", "CCDV-F": "developer.html"}

# El sitio inglés usa slugs ingleses: /ccar-f/apuntes/ y /en/ccar-f/notes/.
SLUG = {
    "es": {k: k for k in PAGES},
    "en": {**{k: k for k in PAGES},
           "tarjetas": "cards", "apuntes": "notes", "referencia": "reference", "ruta": "track"},
}

# Las dos páginas interactivas comparten fuente entre idiomas.
COMPARTIDAS = {"test.html", "tarjetas.html"}
SCORE_JS = open(os.path.join(SRC, "score.js"), encoding="utf-8").read()

LANGS = {
    "es": {"prefix": "", "frag": SRC, "data": "", "locale": "es_ES",
           "name": "Español", "other": "en"},
    "en": {"prefix": "en/", "frag": os.path.join(SRC, "en"), "data": ".en",
           "locale": "en_GB", "name": "English", "other": "es"},
}

META = {
 "es": {
  "test":       ("Simulador", "Simulacros ponderados con los pesos reales del blueprint de {{CERT}} y score proyectado sobre 1000."),
  "tarjetas":   ("Tarjetas", "Tarjetas de memoria con repetición espaciada, acotadas a lo que entra en el {{CERT}}."),
  "apuntes":    ("Apuntes", "El porqué de cada concepto que evalúa el {{CERT}}, verificado contra documentación oficial."),
  "referencia": ("Referencia técnica", "La superficie de API que el {{CERT}} evalúa: campos exactos, valores admitidos y formas de retorno."),
  "flash":      ("Repaso flash", "Hoja de repaso de última hora del {{CERT}}, ordenada por peso y no por temario."),
  "ruta":       ("Ruta de estudio", "Plan de estudio del {{CERT}}, por etapas y con criterio de salida verificable."),
  "home":       ("{{CERT}}", "Dónde estás en el {{CERT}}: score proyectado, acierto por dominio y qué toca estudiar ahora."),
  "index":      ("Claude Certs", "Herramienta de estudio abierta para las certificaciones Claude. Eliges examen y todo el material se acota a lo que ese examen evalúa."),
  "404":        ("Página no encontrada", "Esa página no existe en claude-certs."),
 },
 "en": {
  "test":       ("Simulator", "Weighted mocks using the real {{CERT}} blueprint weights, with a projected score out of 1000."),
  "tarjetas":   ("Flashcards", "Spaced-repetition memory cards, scoped to what the {{CERT}} actually covers."),
  "apuntes":    ("Notes", "The why behind every concept the {{CERT}} tests, verified against official documentation."),
  "referencia": ("Technical reference", "The API surface the {{CERT}} tests: exact fields, permitted values and return shapes."),
  "flash":      ("Cheat sheet", "Last-minute {{CERT}} revision sheet, ordered by weight rather than by syllabus."),
  "ruta":       ("Study route", "A {{CERT}} study plan, stage by stage, with a verifiable exit criterion."),
  "home":       ("{{CERT}}", "Where you stand on the {{CERT}}: projected score, accuracy by domain and what to study next."),
  "index":      ("Claude Certs", "Open study tool for the Claude certifications. Pick an exam and every page narrows to what that exam tests."),
  "404":        ("Page not found", "That page doesn't exist on claude-certs."),
 },
}

FAVICON = ("data:image/svg+xml,"
           "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Crect width='32' height='32' rx='7' fill='%23b5541f'/%3E"
           "%3Ctext x='16' y='23' font-size='19' font-family='system-ui,sans-serif' "
           "font-weight='700' fill='%23fffefb' text-anchor='middle'%3EC%3C/text%3E%3C/svg%3E")

# Tres anchos deliberados en vez de ocho accidentales. La elección es por
# densidad de la página, no por gusto:
#   datos  · tablas de muchas columnas, que en 840 px se leían en carrusel
#   texto  · prosa y tarjetas de navegación
#   foco   · una sola cosa a la vez, donde ensanchar estorba
ANCHO = {
    "test": "var(--w-datos)", "referencia": "var(--w-datos)",
    "apuntes": "var(--w-texto)", "architect": "var(--w-texto)",
    "developer": "var(--w-texto)", "flash": "var(--w-texto)",
    "ruta": "var(--w-texto)", "home": "var(--w-texto)", "index": "var(--w-texto)",
    "tarjetas": "var(--w-foco)", "404": "var(--w-foco)",
}

CSS_UNIFICADO = """
/* --- build.py · capa unificada: una sola versión de lo compartido --- */
*,*::before,*::after{box-sizing:border-box}
/* Paleta. Vivía duplicada en los 16 fragmentos y las páginas generadas no la
   tenían: la home de certificación se servía sin un solo token, con el botón
   principal en blanco sobre blanco. Aquí está una vez, para todas. */
:root{
  --bg:#f7f6f3; --surface:#fffefb; --surface-2:#f0eee8; --line:#e0ddd4; --line-strong:#c9c5b8;
  --ink:#20201d; --ink-2:#57544c; --ink-3:#6f6b5e;
  --accent:#b5541f; --accent-soft:#f6e8de; --accent-ink:#8c3f16;
  --ok:#2f6b46; --ok-soft:#e2efe7; --bad:#a32f28; --bad-soft:#f8e5e3;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace;
  --sans:ui-sans-serif,-apple-system,"Segoe UI",Inter,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#16161a; --surface:#1e1e23; --surface-2:#26262c; --line:#33333b; --line-strong:#4a4a55;
  --ink:#eceae4; --ink-2:#a8a49b; --ink-3:#948f85;
  --accent:#e0834c; --accent-soft:#3a2617; --accent-ink:#f0a274;
  --ok:#6dbb8e; --ok-soft:#1c2f24; --bad:#e0817a; --bad-soft:#33201e;
}}
:root[data-theme="dark"]{
  --bg:#16161a; --surface:#1e1e23; --surface-2:#26262c; --line:#33333b; --line-strong:#4a4a55;
  --ink:#eceae4; --ink-2:#a8a49b; --ink-3:#948f85;
  --accent:#e0834c; --accent-soft:#3a2617; --accent-ink:#f0a274;
  --ok:#6dbb8e; --ok-soft:#1c2f24; --bad:#e0817a; --bad-soft:#33201e;
}
body{background:var(--bg);color:var(--ink);font-family:var(--sans)}

:root{
  --w-datos:1240px; --w-texto:1040px; --w-foco:780px;
  --gutter:20px;
  --paso:1.6;                      /* interlineado de lectura */
}
@media(max-width:720px){:root{--gutter:16px}}

.wrap,.app,.layout{
  max-width:__ANCHO__ !important;
  margin-inline:auto;
  padding-left:var(--gutter);padding-right:var(--gutter);
  padding-top:calc(24px + env(safe-area-inset-top));
  padding-bottom:calc(72px + env(safe-area-inset-bottom));
}
body{line-height:var(--paso);font-size:var(--t-base)}

/* Escala tipográfica. Ocho pasos y ninguno más: seis de texto y dos de display
   para las cifras sueltas que son el contenido de su panel. Antes de esto había
   57 tamaños distintos declarados entre los 16 fragmentos. */
:root{
  --t-micro:12px;   /* versalitas, metadatos. Mínimo absoluto del sitio */
  --t-menor:13px;   /* pies y notas al margen */
  --t-dato:15px;    /* celdas de tabla y texto de tarjeta */
  --t-base:16px;    /* párrafo y lista */
  --t-sub:20px;     /* h3 y titulares de bloque */
  --t-tit:28px;     /* h1 y h2 de página */
  --t-cifra:36px;   /* cifra suelta que es el punto de su panel */
  --t-xl:48px;      /* la cifra principal de una pantalla */
}
h1{font-size:var(--t-tit);line-height:1.2;letter-spacing:-.025em;margin:0 0 6px}
h2{letter-spacing:-.01em}
h3{letter-spacing:-.005em}
p,li,ul,ol{font-size:var(--t-base)}
p{margin:0 0 12px}
table{font-size:var(--t-dato)}
@media(max-width:720px){
  :root{--t-tit:22px;--t-cifra:30px;--t-xl:38px}
}

/* La prosa no crece con el contenedor: las tablas sí necesitan el ancho,
   un párrafo de 120 caracteres por línea no. Incluye lo que se lee dentro de
   los paneles del simulador, que llegaba a estirarse a 1162 px por línea. */
p,li,.lead,.sub,.nota,.paso-lead,.cob,.stem,.rat,.empty,.note,.q,.a{max-width:58ch}
/* Bloques de prosa que los fragmentos habían dejado al tamaño de metadato.
   Son texto para leer, no etiquetas: 487 caracteres de nota del simulador y
   519 de descripciones de tarjeta estaban a 12 y 13 px. */
.note,.nota,.lead,.empty,.sub,.paso-lead,.cob,.salida,.qa,.ctx,
.c .d,.cert .meta,.cc-fuera>.nota,.tema .t1{font-size:var(--t-dato)}
/* Las citas de fuente de los apuntes son 1.859 caracteres: letra pequeña, sí,
   pero no la mínima del sitio. */
.src,.w{font-size:var(--t-menor)}
/* Las celdas de tabla y las etiquetas cortas no llevan tope: ahí el ancho lo
   manda la columna, no la comodidad de lectura. */
td p,td li,th p,.chip,.tag,.pc,.n{max-width:none}
.opt>span:last-child{max-width:76ch}

/* --- Móvil: que nada obligue a arrastrar de lado --- */
table{width:100%;border-collapse:collapse}
/* break-word y no anywhere: "anywhere" afecta al ancho mínimo intrínseco, así
   que el navegador encoge la columna a un carácter y parte las palabras por la
   mitad ("Obli/gat/orio", "stop_sequence/s"). break-word sólo parte cuando de
   verdad no cabe, y en una referencia de nombres de campo eso importa. */
th,td{overflow-wrap:break-word;hyphens:none}
code{overflow-wrap:break-word}
@media(max-width:720px){
  /* 43 celdas con nowrap convertían cada tabla en un carrusel */
  th,td{white-space:normal !important;padding:7px 8px;font-size:var(--t-dato);
        overflow-wrap:break-word}
  /* y los bloques de código pedían 597 px en un hueco de 345 */
  pre,pre code{white-space:pre-wrap !important;overflow-wrap:break-word}
  pre{overflow-x:visible}
  /* Sólo los identificadores pueden partirse donde sea: son los tokens largos
     que impiden encoger la tabla (model_context_window_exceeded son 29
     caracteres). La prosa se queda en break-word, que es lo que evita leer
     "Obli/gat/orio". */
  td code,th code{overflow-wrap:anywhere}
  /* El índice de los apuntes era una fila de 2318 px que había que arrastrar
     entera para llegar a la sección 20. En móvil envuelve. */
  nav.toc,.jump{flex-wrap:wrap !important;overflow-x:visible !important}
  .cards,.certs,.dos{grid-template-columns:1fr !important}
}
/* Red de seguridad: si aun así una tabla no cabe, scrollea ella, nunca la página */
body{overflow-x:hidden}
"""

# Parche de CSS común. Se inyecta al final del <style> de cada página.
CSS_PATCH = """
/* --- build.py · correcciones de accesibilidad aplicadas a todas las páginas --- */
:root{--ink-3:#6f6b5e}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ink-3:#948f85}}
:root[data-theme="dark"]{--ink-3:#948f85}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,
label:focus-within,[tabindex]:focus-visible{
  outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;
    transition-duration:.01ms!important;scroll-behavior:auto!important}}
.cc-foot{max-width:__ANCHO__;margin:38px auto 0;padding:16px 18px calc(24px + env(safe-area-inset-bottom));
  border-top:1px solid var(--line);font-size:var(--t-menor);line-height:1.6;color:var(--ink-3)}
.cc-foot a{color:var(--ink-3)}
.cc-foot b{color:var(--ink-2)}
.cc-skip{position:absolute;left:-9999px;top:0;background:var(--accent);color:#fff;
  padding:10px 16px;z-index:100;border-radius:0 0 8px 0}
.cc-skip:focus{left:0}
.cc-bar{border-bottom:1px solid var(--line);background:var(--surface)}
.cc-bar div{max-width:__ANCHO__;margin:0 auto;padding:9px 18px;display:flex;align-items:center;gap:8px;
  font-size:var(--t-micro);flex-wrap:wrap}
.cc-bar a.home{font-weight:650;color:var(--ink);text-decoration:none;letter-spacing:-.01em}
.cc-bar a.home span{color:var(--accent-ink)}
.cc-bar .sep{color:var(--ink-3);margin-left:auto}
.cc-bar nav{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 16px}
.cc-bar nav .grp{display:flex;align-items:baseline;gap:9px}
.cc-bar nav .grp b{font-size:var(--t-micro);text-transform:uppercase;letter-spacing:.09em;
  color:var(--ink-3);font-weight:600}
.cc-bar nav a{color:var(--ink-2);text-decoration:none}
.cc-bar nav a:hover{color:var(--ink)}
.cc-bar nav a[aria-current="page"]{color:var(--accent-ink);font-weight:600}
.cc-toc{max-width:__ANCHO__;margin:0 auto 6px;padding:13px 18px 0}
.cc-toc>b{display:block;font-size:var(--t-micro);text-transform:uppercase;letter-spacing:.1em;
  color:var(--ink-3);margin-bottom:7px;font-weight:600}
.cc-toc>div{display:flex;flex-wrap:wrap;gap:5px}
.cc-toc a{background:var(--surface);border:1px solid var(--line);border-radius:99px;
  padding:4px 11px;font-size:var(--t-micro);text-decoration:none;color:var(--ink-2)}
.cc-toc a:hover{border-color:var(--accent);color:var(--ink)}
.cc-fuera{max-width:__ANCHO__;margin:34px auto 0;padding:0 18px;border-top:1px dashed var(--line-strong,var(--line))}
.cc-fuera>summary{cursor:pointer;padding:14px 0 10px;font-size:var(--t-menor);color:var(--ink-3);
  font-weight:600;letter-spacing:.02em;list-style:none}
.cc-fuera>summary::-webkit-details-marker{display:none}
.cc-fuera>summary::before{content:"▸ ";color:var(--ink-3)}
.cc-fuera[open]>summary::before{content:"▾ "}
.cc-fuera>summary:hover{color:var(--ink-2)}
.cc-fuera>.nota{font-size:var(--t-menor);color:var(--ink-3);background:var(--surface-2);
  border-radius:8px;padding:10px 13px;margin:0 0 14px;max-width:70ch}
.cc-fuera[open]{padding-bottom:20px}
.cc-bar a.salir{color:var(--ink-3);text-decoration:none;font-size:var(--t-base);padding:0 3px;line-height:1}
.cc-bar a.salir:hover{color:var(--ink)}
.cc-bar a.lang{margin-left:13px;color:var(--ink-3);text-decoration:none;
  border:1px solid var(--line);border-radius:99px;padding:2px 9px;font-size:var(--t-micro)}
.cc-bar a.lang:hover{color:var(--ink)}
/* Objetivos de toque. En móvil la barra tenía 16 px de alto en el enlace de
   salida y 20 en los de navegación, la mitad de lo aceptable. */
@media(pointer:coarse){
  .cc-bar nav a,.cc-bar a.home,.cc-bar a.lang{min-height:44px;display:inline-flex;align-items:center}
  .cc-bar a.salir{min-width:44px;min-height:44px;display:inline-flex;align-items:center;justify-content:center;margin-left:-10px}
  .cc-toc a,.jump a,nav.toc a,.certs a,.tema{min-height:44px;display:inline-flex;align-items:center}
  .modes .btn,.btn{min-height:44px}
}
@media(max-width:560px){.cc-bar .sep{display:none}
  .cc-bar div{gap:6px}.cc-bar nav{gap:3px 12px}.cc-bar a.lang{margin:0}}
/* Impresión: los apuntes y la hoja de repaso se imprimen mucho */
@media print{
  :root{--bg:#fff;--surface:#fff;--surface-2:#f4f4f2;--ink:#000;--ink-2:#333;--ink-3:#555;
        --line:#bbb;--accent:#000;--accent-ink:#000;--accent-soft:#f0f0ee;
        --ok-soft:#f4f4f2;--bad-soft:#f4f4f2}
  .cc-bar,.cc-skip,.cc-foot,.jump,nav.toc,.cc-toc,.modes,.prog,.reset,.acts,.cacts{display:none!important}
  body{font-size:10.5pt}
  .wrap,.layout,.app{max-width:100%;padding:0}
  a{text-decoration:none}
  a[href^="http"]::after{content:" (" attr(href) ")";font-size:8pt;color:#555;word-break:break-all}
  table,.r,.key,.trap,.win,.ask,.esc,.etapa,.ts,pre{break-inside:avoid}
  h2,h3{break-after:avoid}
}
"""

# Paso 1: llevar cualquier enlace interno al slug canónico en ruta absoluta.
# Las páginas arrastran enlaces relativos y alguna URL del dashboard privado.
NORMALIZA = [
    (r'href="/en/', 'href="/'),
    (r'https://alvaro-pipeline\.pages\.dev/examen/([a-z]+)/', r'/\1/'),
    (r'https://alvaro-pipeline\.pages\.dev/examen/', '/test/'),
    (r'href="\.\./([a-z]+)/#([a-z0-9-]+)"', r'href="/\1/#\2"'),
    (r'href="\.\./([a-z]+)/"', r'href="/\1/"'),
    (r'href="\.\./#', 'href="/test/#'),
    (r'href="\.\./"', 'href="/test/"'),
]
# Los fetch de datos se quedan relativos a propósito: así /tarjetas/ pide
# /cards.json y /en/cards/ pide /en/cards.json sin saber en qué idioma está.

FOOT = {
 "es": """<footer class="cc-foot">
<b>Material propio.</b> Los ítems, tarjetas y apuntes de este sitio están escritos contra los
objetivos publicados de cada examen. <b>No proceden del banco real ni lo reproducen</b>, y este
proyecto no está afiliado a Anthropic ni avalado por ella. Para el temario, los pesos oficiales
y las políticas, la fuente es siempre la guía de examen que Anthropic distribuye a sus partners.
<br><br>Verificado contra documentación pública de Anthropic y la especificación MCP.
La documentación cambia con frecuencia: comprueba cualquier dato antes de apoyarte en él.
· <a href="https://github.com/alvaro-zamorano/claude-certs">Código y banco de ítems en GitHub</a>
· <a href="{ALT}" hreflang="en">Read this in English</a>
</footer>""",
 "en": """<footer class="cc-foot">
<b>Independent material.</b> The items, cards and notes on this site are written against the
objectives each exam guide publishes. <b>They do not come from the live item bank and do not
reproduce it</b>, and this project is neither affiliated with nor endorsed by Anthropic. For the
syllabus, the official weights and the policies, the source is always the exam guide Anthropic
distributes to its partners.
<br><br>Verified against Anthropic's public documentation and the MCP specification.
That documentation changes often: check any fact before you rely on it.
· <a href="https://github.com/alvaro-zamorano/claude-certs">Code and item bank on GitHub</a>
· <a href="{ALT}" hreflang="es">Léelo en español</a>
</footer>""",
}

# Dentro de una certificación, la barra agrupa por para qué sirve cada página.
NAV = {
 "es": [("Practicar", [("test", "Simulador"), ("tarjetas", "Tarjetas")]),
        ("Estudiar",  [("apuntes", "Apuntes"), ("referencia", "Referencia"), ("flash", "Repaso flash")]),
        ("Plan",      [("ruta", "Ruta de estudio")])],
 "en": [("Practise", [("test", "Simulator"), ("tarjetas", "Flashcards")]),
        ("Study",    [("apuntes", "Notes"), ("referencia", "Reference"), ("flash", "Cheat sheet")]),
        ("Plan",     [("ruta", "Study route")])],
}

VOLVER = {"es": "Cambiar de certificación", "en": "Change certification"}
FUERA = {"es": ("Fuera del alcance del {C}",
                "Esto no lo evalúa el {C}. Se deja accesible porque saber qué <i>no</i> entra "
                "también ahorra tiempo, pero no lo estudies para este examen."),
         "en": ("Outside the scope of the {C}",
                "The {C} does not test this. It stays reachable because knowing what is <i>not</i> "
                "examinable saves time too, but don't study it for this exam.")}

# Etiquetas con las que cada página se nombra a sí misma en las filas de
# navegación heredadas, para poder reconocerlas y quitarlas.
ETIQUETAS = {t.strip().lower()
             for idioma in NAV.values() for _, pares in idioma for _, t in pares}
ETIQUETAS |= {"test", "flash", "cards", "simulador", "simulator", "notes",
              "reference", "referencia", "tarjetas", "apuntes", "flashcards",
              "architect", "developer", "cheat sheet", "repaso flash", "inicio", "home"}


# Contenedores donde cada página metía su propia fila de enlaces.
CABECERAS = [r'<header class="top">.*?</header>',
             r'<div class="top" id="top">.*?</div>',
             r'<div class="top-nav">.*?</div>']


def limpia_nav(raw, lang):
    """Quita la fila de navegación propia de la página.

    Cada fragmento traía su lista de enlaces heredada del dashboard, y ninguna
    coincidía con otra. Se borran sólo las anclas cuyo texto visible es el
    nombre de otra página del sitio, y sólo dentro de la cabecera: así
    sobreviven los enlaces de contenido ("Estudiar con tarjetas →") y las
    mismas palabras cuando aparecen en una frase del cuerpo.
    """
    def fuera(m):
        txt = re.sub(r"<[^>]+>", "", m.group(1)).strip().lower().strip(" →·").strip()
        return "" if txt in ETIQUETAS else m.group(0)

    def limpia(m):
        cab = re.sub(r'<a\s[^>]*href="[^"]*"[^>]*>(.*?)</a>', fuera, m.group(0), flags=re.S)
        # contenedores que se quedan vacíos al retirar los enlaces
        cab = re.sub(r'<(div|nav)\s+class="nav"[^>]*>\s*</\1>', "", cab)
        cab = re.sub(r'<div style="display:flex;gap:14px;align-items:center">\s*</div>', "", cab)
        return cab

    cuerpo = raw.split("</style>", 1)
    if len(cuerpo) == 1:
        return raw
    cab, resto = cuerpo[0] + "</style>", cuerpo[1]
    for pat in CABECERAS:
        nuevo, n = re.subn(pat, limpia, resto, count=1, flags=re.S)
        if n:
            resto = nuevo
            break
    else:
        # flash y similares: la fila vive suelta al principio del cuerpo
        resto = re.sub(r'<div class="top-nav">.*?</div>', "", resto, count=1, flags=re.S)
    return cab + resto


def indice(raw, lang, hasta=None):
    """Índice de secciones para las páginas largas que no lo traen.

    Una página de 11 o 20 secciones sin índice obliga a recorrerla entera para
    saber qué hay dentro. Se genera del propio documento, así que no puede
    quedarse a medias cuando se añade una sección.
    """
    if re.search(r'<nav class="toc"', raw) or re.search(r'<div class="jump"', raw):
        return raw
    mirar = raw.partition('<details class="cc-fuera"')[0]
    secs = re.findall(r'<section id="([^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*?<h2[^>]*>(.*?)</h2>', mirar, re.S)
    if len(secs) < 6:
        # páginas sin <section>: se numeran los propios h2 para poder enlazarlos
        h2 = re.findall(r"<h2[^>]*>(.*?)</h2>", mirar, re.S)
        if len(h2) < 6:
            return raw
        secs, n = [], [0]

        def ancla(m):
            n[0] += 1
            return f'<h2 id="s{n[0]}"{m.group(1)}>'   # el > va aquí: sin él la etiqueta queda abierta
        raw = re.sub(r"<h2((?![^>]*\bid=)[^>]*)>", ancla, raw)
        secs = [(f"s{i}", t) for i, t in enumerate(h2, 1)]
    quita = lambda t: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t)).strip()
    pills = "".join(f'<a href="#{i}">{quita(t)}</a>' for i, t in secs)
    lbl = "En esta página" if lang == "es" else "On this page"
    nav = f'<nav class="cc-toc" aria-label="{lbl}"><b>{lbl}</b><div>{pills}</div></nav>'
    # después del primer h1, o al principio del cuerpo si no hay
    m = re.search(r"</h1>", raw)
    if m:
        cierre = raw.find(">", raw.find("</header>", m.end())) if "</header>" in raw[m.end():m.end() + 900] else -1
        corte = cierre + 1 if cierre > 0 else m.end()
        return raw[:corte] + "\n" + nav + raw[corte:]
    return nav + raw

SKIP = {"es": "Saltar al contenido", "en": "Skip to content"}

EN_404 = ('<p style="font-size:var(--t-dato);color:var(--ink-3);margin-top:18px">'
          'English? The English site is at <a href="/en/">claude-certs /en/</a>.</p>')


def hoja_de(slug):
    """Estilos compartidos, con el ancho que corresponde a la densidad de la página."""
    return (CSS_PATCH + CSS_UNIFICADO).replace("__ANCHO__", ANCHO.get(slug, "var(--w-texto)"))


def ruta(lang, slug, cert=None):
    """URL pública, ya con el prefijo de montaje y la certificación."""
    p = LANGS[lang]["prefix"]
    if slug == "index":
        return f"{BASE_PATH}/{p}"
    if slug == "404":
        return f"{BASE_PATH}/404.html"
    c = CERT_SLUG[cert]
    if slug == "home":
        return f"{BASE_PATH}/{p}{c}/"
    return f"{BASE_PATH}/{p}{c}/{SLUG[lang][slug]}/"


def localiza(s, lang, cert):
    """Canónico -> localizado dentro de la certificación."""
    for canon in sorted(PAGES, key=len, reverse=True):
        s = s.replace(f'href="/{canon}/', f'href="{ruta(lang, canon, cert)[:-1]}/')
    # los fragmentos heredados enlazaban a /architect/ y /developer/
    for viejo in ("architect", "developer"):
        s = s.replace(f'href="/{viejo}/', f'href="{ruta(lang, "ruta", cert)[:-1]}/'
                      if cert in RUTA_SRC else f'href="{ruta(lang, "home", cert)[:-1]}/')
    return s.replace('href="/"', f'href="{ruta(lang, "home", cert)}"'.replace('href="', 'href="'))


def secciona(raw):
    """Envuelve en <section id="sN"> cada h2 y lo que le sigue.

    La hoja de repaso no tenía secciones, sólo h2 sueltos, así que no había
    nada que acotar ni que indexar. Se agrupan aquí para que el resto del
    build las trate igual que a las demás páginas.
    """
    if "<section" in raw or raw.count("<h2") < 3:
        return raw
    cortes = [m.start() for m in re.finditer(r"<h2[^>]*>", raw)]
    fin = raw.rfind("</div>")
    fin = fin if fin > cortes[-1] else len(raw)
    fuera = [(0, cortes[0])] + [(a, b) for a, b in zip(cortes, cortes[1:] + [fin])]
    out = raw[:cortes[0]]
    for i, (a, b) in enumerate(fuera[1:], 1):
        out += f'<section id="s{i}">' + raw[a:b] + "</section>"
    return out + raw[fin:]


def recorta(raw, pagina, cert, lang, scope):
    """Baja al final lo que ese examen no evalúa, en un bloque plegado.

    No se esconde: saber qué NO entra también es conocimiento de examen, y si
    una etiqueta está mal puesta no te deja sin el contenido.
    """
    reglas = scope["sections"].get(pagina)
    if not reglas:
        return raw, []
    fuera, ids = [], []

    def saca(m):
        sid = m.group(1)
        if sid not in reglas:
            raise SystemExit(f"BUILD DETENIDO · sección '{sid}' de {pagina} sin declarar en scope.json")
        if cert in reglas[sid]:
            return m.group(0)
        fuera.append(m.group(0)); ids.append(sid)
        return ""

    raw = re.sub(r'<section id="([^"]+)".*?</section>', saca, raw, flags=re.S)
    if not fuera:
        return raw, []
    titulo, explica = (t.replace("{C}", cert) for t in FUERA[lang])
    bloque = (f'<details class="cc-fuera"><summary>{titulo} · {len(fuera)}</summary>'
              f'<p class="nota">{explica}</p>' + "".join(fuera) + "</details>")
    return raw + "\n" + bloque, ids


def poda_indice(raw, ids):
    """Quita del índice las secciones que ese examen no evalúa.

    Los índices escritos a mano listaban las veinte secciones; dejar ahí las
    que se han bajado al bloque plegado devuelve al lector al problema que
    veníamos a resolver.
    """
    if not ids:
        return raw

    def limpia(m):
        nav = m.group(0)
        for sid in ids:
            nav = re.sub(rf'<a href="#{re.escape(sid)}"[^>]*>.*?</a>', "", nav, flags=re.S)
        # grupos que se quedan sin ninguna entrada
        nav = re.sub(r'<div class="grp">[^<]*</div>(?=\s*(?:<div class="grp">|</nav>))', "", nav)
        return nav

    return re.sub(r'<nav class="(?:cc-toc|toc)".*?</nav>|<div class="jump">.*?</div>',
                  limpia, raw, flags=re.S)


def barra(lang, slug, cert, alt, otro):
    """Una sola barra, siempre dentro de la certificación elegida.

    No hay conmutador de examen: se sale hacia atrás, al selector. Mezclar
    certificaciones dentro de las páginas es lo que hacía que uno se estudiase
    material que su examen no evalúa.
    """
    grupos = []
    for titulo, pares in NAV[lang]:
        enlaces = "".join(
            f'<a href="{ruta(lang, sl, cert)}"'
            + (' aria-current="page"' if sl == slug else "")
            + f">{lbl}</a>"
            for sl, lbl in pares if sl != "ruta" or cert in RUTA_SRC)
        if enlaces:
            grupos.append(f'<span class="grp"><b>{titulo}</b>{enlaces}</span>')
    actual = ' aria-current="page"' if slug == "home" else ""
    return f"""
<div class="cc-bar"><div>
<a class="salir" href="{ruta(lang, "index")}" title="{VOLVER[lang]}">←</a>
<a class="home" href="{ruta(lang, "home", cert)}"{actual}>{cert}</a>
<span class="sep"></span>
<nav>{"".join(grupos)}</nav>
<a class="lang" href="{alt}" hreflang="{otro}">{LANGS[otro]['name']}</a>
</div></div>"""


def wrap(lang, slug, cert, cifras, T, scope):
    cfg = LANGS[lang]
    src_file = RUTA_SRC[cert] if slug == "ruta" else PAGES[slug]
    carpeta = SRC if src_file in COMPARTIDAS else cfg["frag"]
    raw = open(os.path.join(carpeta, src_file), encoding="utf-8").read()
    short, desc = (t.replace("{{CERT}}", cert) for t in META[lang][slug])

    # Cadenas de interfaz. Fuera del <script> se sustituyen como texto; dentro,
    # el código usa T.clave y aquí se inyecta T como JSON, que escapa comillas y
    # apóstrofos correctamente (un "Couldn't" partiría el literal si no).
    def tt(m):
        k = m.group(1)
        if k not in T:
            raise SystemExit(f"BUILD DETENIDO · falta la cadena '{k}' en src/i18n/{lang}.json")
        return T[k]
    raw = re.sub(r"\{\{t\.([a-z_0-9]+)\}\}", tt, raw)
    if src_file in COMPARTIDAS:
        usadas = sorted(set(re.findall(r"\bT\.([a-z_0-9]+)", raw)))
        faltan = [k for k in usadas if k not in T]
        if faltan:
            raise SystemExit(f"BUILD DETENIDO · faltan cadenas en src/i18n/{lang}.json: {faltan}")
        tjson = json.dumps({k: T[k] for k in usadas}, ensure_ascii=False)
        raw = raw.replace("<script>", f"<script>\nconst T={tjson};\n", 1)
    # La proyección es una sola: el simulador y la portada de la certificación
    # incrustan el mismo src/score.js en vez de calcularla cada uno a su manera.
    raw = raw.replace("/*@SCORE*/", SCORE_JS)

    for k, v in cifras.items():
        raw = raw.replace("{{%s}}" % k, str(v))
        desc = desc.replace("{{%s}}" % k, str(v))

    m = re.search(r"<title>(.*?)</title>", raw, re.S)
    title = m.group(1).strip() if m else short
    raw = re.sub(r"<title>.*?</title>\s*", "", raw, count=1, flags=re.S)
    raw = re.sub(r'<meta name="viewport"[^>]*>\s*', "", raw, count=1)

    for pat, rep in NORMALIZA:
        raw = re.sub(pat, rep, raw)
    raw = limpia_nav(raw, lang)
    raw = secciona(raw)
    raw, fuera_ids = recorta(raw, slug, cert, lang, scope)
    raw = poda_indice(raw, fuera_ids)   # lo que no entra tampoco se indexa
    raw = indice(raw, lang)
    raw = localiza(raw, lang, cert)

    hoja = hoja_de(slug)
    if "</style>" in raw:
        raw = raw.replace("</style>", hoja + "</style>", 1)
    else:
        raw = f"<style>{hoja}</style>" + raw

    full = f"{title} · {cert} · Claude Certs"
    url = BASE + ruta(lang, slug, cert)
    otro = cfg["other"]
    alt = ruta(otro, slug, cert)
    og = f"{BASE}{BASE_PATH}/{cfg['prefix']}og.png"

    alternates = "".join(
        f'\n<link rel="alternate" hreflang="{l}" href="{BASE}{ruta(l, slug, cert)}">' for l in LANGS)
    alternates += f'\n<link rel="alternate" hreflang="x-default" href="{BASE}{ruta("es", slug, cert)}">'

    head = f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{full}</title>
<meta name="description" content="{desc}">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="{FAVICON}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Claude Certs">
<meta property="og:title" content="{full}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="{cfg['locale']}">
<meta property="og:image" content="{og}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Claude Certs">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{og}">
<link rel="canonical" href="{url}">{alternates}
</head>
<body>
<a class="cc-skip" href="#main">{SKIP[lang]}</a>"""

    bar = barra(lang, slug, cert, alt, otro)
    foot = FOOT[lang].replace("{ALT}", alt)
    return head + bar + '\n<main id="main">\n' + raw.strip() + "\n</main>\n" + foot + "\n</body>\n</html>\n"



FICHA = {"es": "{n} ítems · 120 minutos · corte 720 sobre 1000 · vigencia 12 meses",
         "en": "{n} items · 120 minutes · 720 out of 1000 to pass · valid 12 months"}

HOME_T = {
 "es": {"estado": "Dónde estás", "sin": "Aún no has respondido nada de este examen.",
        "empezar": "Hacer un simulacro y medir →", "dom": "Los dominios y lo que pesan",
        "peso": "Peso", "tuyo": "Tu acierto", "mat": "El material de este examen",
        "cob": "{i} ítems propios · {c} tarjetas · {a} de {at} secciones de apuntes aplican a este examen",
        "flojo": "Lo más flojo ahora mismo es <b>{d}</b>, al {p}%.",
        "como": "Mide antes de estudiar: un simulacro ponderado te da un número por dominio, y ese número te dice qué estudiar en vez de adivinarlo.",
        "drill": "Drill de ese dominio →", "proy": "Score proyectado",
        "rango": "Intervalo aproximado {lo}–{hi}; el corte está en 720.",
        "faltan": "Llevas {n} de {min} ítems distintos: con menos de {min} todavía no se proyecta un score.",
        "parcial": "Cobertura parcial: este examen tiene menos material escrito que los demás."},
 "en": {"estado": "Where you stand", "sin": "You haven't answered anything for this exam yet.",
        "empezar": "Take a mock and measure →", "dom": "The domains and what they weigh",
        "peso": "Weight", "tuyo": "Your accuracy", "mat": "The material for this exam",
        "cob": "{i} original items · {c} cards · {a} of {at} note sections apply to this exam",
        "flojo": "Your weakest right now is <b>{d}</b>, at {p}%.",
        "como": "Measure before you study: a weighted mock gives you a number per domain, and that number tells you what to study instead of guessing it.",
        "drill": "Drill that domain →", "proy": "Projected score",
        "rango": "Approximate range {lo}–{hi}; the cut score is 720.",
        "faltan": "You have answered {n} of {min} distinct items: below {min} no score is projected yet.",
        "parcial": "Partial coverage: this exam has less written material than the others."},
}


def home(lang, cert, ex, n_items, n_cards, n_ap, n_ap_tot, T):
    """La página que no existía: el estado de TU examen, no un menú de herramientas.

    Es lo primero que quiere ver alguien con fecha de examen: un número, el
    dominio más flojo y una acción. El menú va debajo.
    """
    t = HOME_T[lang]
    filas = "".join(
        f'<tr><td>{d}</td><td class="n">{w}%</td>'
        f'<td class="n" data-dom="{d}">—</td></tr>'
        for d, w in sorted(ex[cert]["w"].items(), key=lambda kv: -kv[1]))
    tarjetas = []
    for titulo, pares in NAV[lang]:
        enlaces = "".join(
            f'<a class="c" href="{ruta(lang, sl, cert)}"><div class="t">{lbl}</div>'
            f'<div class="d">{META[lang][sl][1].replace("{{CERT}}", cert)}</div></a>'
            for sl, lbl in pares if sl != "ruta" or cert in RUTA_SRC)
        if enlaces:
            tarjetas.append(f'<h3 class="grupo">{titulo}</h3><div class="cards">{enlaces}</div>')
    aviso = (f'<p class="parcial">{t["parcial"]}</p>' if n_items < 40 else "")
    return f"""<title>{ex[cert]['name']}</title>
<style>{HOME_CSS}</style>
<div class="wrap">
<div class="cod">{cert}</div>
<h1>{ex[cert]['name']}</h1>
<div class="sub">{FICHA[lang].format(n=n_items)}</div>
{aviso}

<div class="estado" id="estado">
  <div class="lbl">{t['estado']}</div>
  <div class="num" id="score">—</div>
  <p id="msg">{t['sin']}</p>
  <p class="como">{t['como']}</p>
  <a class="cta" id="cta" href="{ruta(lang, 'test', cert)}">{t['empezar']}</a>
</div>

<h2>{t['dom']}</h2>
<table><tr><th>Dominio</th><th class="n">{t['peso']}</th><th class="n">{t['tuyo']}</th></tr>
{filas}</table>

<h2>{t['mat']}</h2>
{''.join(tarjetas)}
<p class="cob">{t['cob'].format(i=n_items, c=n_cards, a=n_ap, at=n_ap_tot)}</p>
</div>

<script>
{SCORE_JS}
const CERT={json.dumps(cert)}, TT={json.dumps(t, ensure_ascii=False)};
const RUTA_TEST={json.dumps(ruta(lang, 'test', cert))};
let ST={{}}; try{{ST=JSON.parse(localStorage.getItem("claude-certs-v1")||"{{}}")}}catch(e){{}}
Promise.all([fetch("items.json").then(r=>r.json()),fetch("exams.json").then(r=>r.json())])
 .then(([a,b])=>{{
  const p=ccScore(a.items,b[CERT].w,ST);
  if(!p.n)return;
  let flojo=null,peor=2;
  for(const d in p.dom){{
    const o=p.dom[d]; if(!o.n)continue;
    const celda=document.querySelector(`[data-dom="${{d}}"]`), pc=Math.round(o.ok/o.n*100);
    if(celda){{celda.textContent=pc+"% · "+o.n;celda.className="n "+(pc>=85?"bien":pc<60?"mal":"");}}
    if(o.ok/o.n<peor){{peor=o.ok/o.n;flojo=d}}
  }}
  const sc=document.getElementById("score"), msg=document.getElementById("msg");
  const txt=TT.flojo.replace("{{d}}",flojo).replace("{{p}}",Math.round(peor*100));
  if(p.enough){{
    sc.textContent=p.scaled;
    sc.className="num "+(p.lo>=CC_CORTE?"bien":p.hi<CC_CORTE?"mal":"");
    msg.innerHTML=TT.rango.replace("{{lo}}",p.lo).replace("{{hi}}",p.hi)+" "+txt;
  }} else {{
    msg.innerHTML=TT.faltan.replace("{{n}}",p.n).split("{{min}}").join(p.min)+" "+txt;
  }}
  const cta=document.getElementById("cta");
  cta.textContent=TT.drill; cta.href=RUTA_TEST;
  const como=document.querySelector(".estado .como"); if(como) como.hidden=true;
 }}).catch(()=>{{}});
</script>
"""


HOME_CSS = '''
.wrap{max-width:820px;margin:0 auto;padding:26px 18px 60px}
.cod{font-family:var(--mono);font-size:var(--t-micro);letter-spacing:.1em;color:var(--accent-ink);font-weight:700}
h1{font-size:var(--t-tit);margin:4px 0 5px;letter-spacing:-.025em}
.sub{color:var(--ink-3);font-size:var(--t-menor);margin-bottom:20px}
.parcial{background:var(--accent-soft);color:var(--accent-ink);border-radius:8px;
  padding:9px 13px;font-size:var(--t-menor);margin:0 0 18px}
.estado{background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:19px 21px;margin-bottom:28px}
.estado .lbl{font-size:var(--t-micro);text-transform:uppercase;letter-spacing:.11em;color:var(--ink-3);font-weight:600}
.estado .num{font-size:var(--t-xl);font-weight:650;letter-spacing:-.035em;line-height:1.05;margin:2px 0 4px}
.estado .num.bien{color:var(--ok)} .estado .num.mal{color:var(--bad)}
.estado p{margin:0 0 9px;font-size:var(--t-dato);color:var(--ink-2)}
.estado .como{color:var(--ink-3);margin-bottom:15px}
.cta{display:inline-block;background:var(--accent);color:#fff;padding:11px 19px;border-radius:9px;
  font-size:var(--t-dato);font-weight:550;text-decoration:none}
h2{font-size:var(--t-micro);text-transform:uppercase;letter-spacing:.12em;color:var(--ink-3);
  margin:28px 0 11px;font-weight:700}
table{width:100%;border-collapse:collapse;font-size:var(--t-dato);margin-bottom:6px;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left}
th{background:var(--surface-2);font-size:var(--t-micro);font-weight:600;white-space:nowrap}
td.n,th.n{text-align:right;font-family:var(--mono);white-space:nowrap}
td.n.bien{color:var(--ok);font-weight:600} td.n.mal{color:var(--bad);font-weight:600}
.grupo{font-size:var(--t-dato);margin:18px 0 9px;letter-spacing:-.01em}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:680px){.cards{grid-template-columns:1fr}}
.c{display:block;background:var(--surface);border:1px solid var(--line);border-radius:11px;
  padding:14px 15px;text-decoration:none;color:var(--ink)}
.c:hover{border-color:var(--line-strong)}
.c .t{font-size:var(--t-dato);font-weight:600;margin-bottom:3px}
.c .d{font-size:var(--t-menor);color:var(--ink-2);line-height:1.5}
.cob{font-size:var(--t-micro);color:var(--ink-3);margin-top:20px}
'''


SELECTOR_T = {"es": ("Elige tu certificación",
                     "Todo el material se acota a lo que ese examen evalúa. Para cambiar, vuelves aquí.",
                     "Seguir con {c} →", "ítems", "tarjetas", "cobertura parcial"),
              "en": ("Pick your certification",
                     "Every page narrows to what that exam tests. To change, you come back here.",
                     "Continue with {c} →", "items", "cards", "partial coverage")}


def selector(lang, ex, conteos):
    """Portada: elegir examen es la primera decisión, no un filtro escondido."""
    tit, sub, seguir, lbl_i, lbl_c, parcial = SELECTOR_T[lang]
    cards = []
    for c in CERTS:
        i, ca = conteos[c]
        marca = f' · <b>{parcial}</b>' if i < 40 else ""
        cards.append(
            f'<a class="cert" href="{ruta(lang, "home", c)}">'
            f'<div class="cod">{c}</div><div class="nm">{ex[c]["name"]}</div>'
            f'<div class="meta">{i} {lbl_i} · {ca} {lbl_c}{marca}</div></a>')
    return (f'<h2>{tit}</h2><p class="paso-lead">{sub}</p>'
            f'<div class="certs">{"".join(cards)}</div>'
            f'<a class="seguir" id="seguir" hidden href="#"></a>'
            f'<script>\ntry{{const c=localStorage.getItem("claude-certs-cert");'
            f'if(c&&{json.dumps(CERT_SLUG)}[c]){{const a=document.getElementById("seguir");'
            f'a.href={json.dumps(BASE_PATH + "/" + LANGS[lang]["prefix"])}+{json.dumps(CERT_SLUG)}[c]+"/";'
            f'a.textContent={json.dumps(seguir)}.replace("{{c}}",c);a.hidden=false;}}}}catch(e){{}}\n</script>')




# Umbrales de las guardias de calidad. Cada uno lleva su fecha y su motivo: un
# umbral sin explicación acaba subiéndose para que el build deje de molestar.
# Los temporales existen para no bloquear el trabajo en curso; bajarlos al
# definitivo es el criterio de terminación de su fase, no una tarea opcional.
UMBRALES = {
    # % de ítems donde la correcta es la opción más larga. Por azar sería 25.
    # 17-09-2026 · DEFINITIVO. Partía del 98 % en CCAO-F y CCAR-P; tras emparejar
    # las longitudes de las cuatro opciones, el peor examen queda en 8 %. Por azar
    # sería 25 %. Subir este número exige justificarlo aquí.
    "sesgo_longitud": 35,
    # % de correctas concentradas en un mismo índice, antes de barajar.
    # 17-09-2026 · DEFINITIVO. Partía del 100 % en el índice 0 del CCDV-F; tras la
    # rotación determinista por enunciado, el peor examen queda en 31 %. Por azar
    # sería 25 %.
    "sesgo_posicion": 40,
    # puntos de desvío de un dominio frente a su peso oficial en el blueprint.
    # 17-09-2026 · el CCDV-F partía de +8,4 pts por cinco ítems mal clasificados.
    "desvio_blueprint": 5,
    # tamaños de letra distintos declarados en una página.
    # 17-09-2026 · DEFINITIVO. Partía de 37 declarados en la ruta de estudio;
    # tras pasar los 16 fragmentos a la escala de ocho pasos, ninguna página
    # supera los 8. Subir este número exige justificarlo aquí.
    "tamanos_letra": 8,
}


def _largo(t):
    return len(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t)).strip())


def sesgo_longitud(items):
    """% de ítems donde la correcta es la opción más larga.

    Es el hallazgo central de la auditoría del 16-09-2026: con el 88 % se podía
    aprobar el simulador eligiendo siempre la opción larga, sin leer nada. Un
    banco así enseña a reconocer la respuesta, no a saberla.
    """
    n = mal = 0
    for x in items:
        otras = [_largo(o) for i, o in enumerate(x["o"]) if i not in x["a"]]
        if not otras:
            continue
        n += 1
        if max(_largo(x["o"][i]) for i in x["a"]) > max(otras):
            mal += 1
    return (mal * 100 // n if n else 0), mal, n


def sesgo_posicion(items):
    """% de correctas concentradas en el índice más repetido."""
    c = Counter(x["a"][0] for x in items if len(x["a"]) == 1)
    if not c:
        return 0, None
    idx, n = c.most_common(1)[0]
    return n * 100 // sum(c.values()), idx


def valida_banco(items, ex):
    """Sesgo de longitud, de posición y desvío frente al blueprint.

    Los tres son formas de que el banco enseñe algo distinto de lo que dice:
    que se pueda acertar por la forma de la opción, por su sitio, o practicando
    un dominio que en el examen real casi no cae.
    """
    errores = []
    for e in ex:
        sub = [x for x in items if x["e"] == e]
        if not sub:
            continue
        pc, mal, n = sesgo_longitud(sub)
        if pc > UMBRALES["sesgo_longitud"]:
            errores.append(f"{e}: la correcta es la opción más larga en {mal} de {n} ítems "
                           f"({pc} %), por encima del umbral de {UMBRALES['sesgo_longitud']} %")
        pp, idx = sesgo_posicion(sub)
        if pp > UMBRALES["sesgo_posicion"]:
            errores.append(f"{e}: el {pp} % de las correctas está en el índice {idx}, "
                           f"por encima del umbral de {UMBRALES['sesgo_posicion']} %")
        c = Counter(x["d"] for x in sub)
        for d_, w in ex[e]["w"].items():
            dev = c.get(d_, 0) / len(sub) * 100 - w
            if abs(dev) > UMBRALES["desvio_blueprint"]:
                errores.append(f"{e}: «{d_}» se desvía {dev:+.1f} pts de su peso oficial "
                               f"({w} %), por encima del umbral de "
                               f"±{UMBRALES['desvio_blueprint']} pts")
    return errores


def valida_tipografia(construidas):
    """Cuenta los tamaños de letra distintos declarados en cada página."""
    errores = []
    for rel, html in construidas:
        vals = set()
        for m in re.finditer(r"font-size:\s*([0-9.]+)(px|rem|em)", html):
            v = float(m.group(1))
            vals.add(round(v * (16 if m.group(2) != "px" else 1), 1))
        if len(vals) > UMBRALES["tamanos_letra"]:
            errores.append(f"{rel}: {len(vals)} tamaños de letra distintos "
                           f"(umbral {UMBRALES['tamanos_letra']}) -> {sorted(vals)}")
    return errores

def ident(x):
    """Identificador estable de un ítem, derivado de su enunciado.

    Antes el progreso se guardaba por posición en el array, así que reordenar
    o filtrar el banco reasignaba el historial a otras preguntas sin avisar.
    Con el enunciado como semilla, un ítem conserva su identidad aunque se
    mueva, y añadir ítems nuevos no toca a los demás.
    """
    semilla = re.sub(r"<[^>]+>", "", x["q"]).strip()
    return x["e"] + "#" + hashlib.sha1(semilla.encode("utf-8")).hexdigest()[:10]


def migracion(items):
    """Mapa del identificador viejo (posición global) al nuevo, para no perder
    el progreso ya guardado. La app lo aplica una sola vez."""
    return {f'{x["e"]}#{g}': ident(x) for g, x in enumerate(items)}


def valida_scope(scope, cd, ex):
    """Cada tema y cada sección tiene que declarar en qué exámenes entra.

    Sin esto, añadir contenido nuevo lo dejaría fuera de todos los exámenes en
    silencio, o dentro de todos por descuido.
    """
    errores = []
    temas = [t["es"] for t in scope["card_topics"]]
    if temas != cd["temas"] and len(temas) != len(cd["temas"]):
        errores.append(f"scope.json declara {len(temas)} temas y el mazo tiene {len(cd['temas'])}")
    for t in scope["card_topics"]:
        malos = [c for c in t["x"] if c not in ex]
        if malos: errores.append(f'scope.json · tema "{t["es"]}": examen desconocido {malos}')
        if not t["x"]: errores.append(f'scope.json · tema "{t["es"]}" no entra en ningún examen')
    for pagina, reglas in scope["sections"].items():
        for sid, xs in reglas.items():
            malos = [c for c in xs if c not in ex]
            if malos: errores.append(f"scope.json · {pagina}#{sid}: examen desconocido {malos}")
            if not xs: errores.append(f"scope.json · {pagina}#{sid} no entra en ningún examen")
    for cert in CERTS:
        if not any(cert in t["x"] for t in scope["card_topics"]):
            errores.append(f"scope.json · {cert} se queda sin ninguna tarjeta")
    return errores


def envuelve(lang, slug, cert, fragmento):
    """Envuelve un fragmento generado (portada, home, 404) igual que a los de src/."""
    cfg = LANGS[lang]
    short, desc = (t.replace("{{CERT}}", cert or "") for t in META[lang][slug])
    m = re.search(r"<title>(.*?)</title>", fragmento, re.S)
    title = m.group(1).strip() if m else short
    raw = re.sub(r"<title>.*?</title>\s*", "", fragmento, count=1, flags=re.S)
    hoja = hoja_de(slug)
    raw = raw.replace("</style>", hoja + "</style>", 1) if "</style>" in raw \
        else f"<style>{hoja}</style>" + raw
    full = title if slug == "index" else (f"{title} · Claude Certs" if slug == "404"
                                          else f"{title} · Claude Certs")
    url = BASE + ruta(lang, slug, cert)
    otro = cfg["other"]
    alt = ruta(otro, "index" if slug == "404" else slug, cert)
    og = f"{BASE}{BASE_PATH}/{cfg['prefix']}og.png"
    alternates = "".join(
        f'\n<link rel="alternate" hreflang="{l}" href="{BASE}{ruta(l, slug, cert)}">' for l in LANGS)
    alternates += f'\n<link rel="alternate" hreflang="x-default" href="{BASE}{ruta("es", slug, cert)}">'
    head = f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{full}</title>
<meta name="description" content="{desc}">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="{FAVICON}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Claude Certs">
<meta property="og:title" content="{full}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="{cfg['locale']}">
<meta property="og:image" content="{og}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Claude Certs">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{og}">
<link rel="canonical" href="{url}">{alternates}
</head>
<body>
<a class="cc-skip" href="#main">{SKIP[lang]}</a>"""
    if cert:
        bar = barra(lang, slug, cert, alt, otro)
        # dentro de una certificación se recuerda cuál, para poder volver a ella
        bar += (f'<script>try{{localStorage.setItem("claude-certs-cert",{json.dumps(cert)})}}'
                f'catch(e){{}}</script>')
    else:
        bar = (f'<div class="cc-bar"><div><span class="sep"></span><nav></nav>'
               f'<a class="lang" href="{alt}" hreflang="{otro}">{LANGS[otro]["name"]}</a>'
               f'</div></div>')
    foot = FOOT[lang].replace("{ALT}", alt)
    return head + bar + '\n<main id="main">\n' + raw.strip() + "\n</main>\n" + foot + "\n</body>\n</html>\n"


def portada(lang, ex, conteos, T):
    """Portada: qué es esto y elegir examen."""
    frag = open(os.path.join(LANGS[lang]["frag"], "landing.html"), encoding="utf-8").read()
    frag = re.sub(r'<meta name="viewport"[^>]*>\s*', "", frag, count=1)
    tot_i = sum(v[0] for v in conteos.values())
    frag = frag.replace("{{N_ITEMS}}", str(tot_i)).replace("{{N_EXAMS}}", str(len(CERTS)))
    frag = frag.replace("{{N_CARDS}}", str(max(v[1] for v in conteos.values())))
    frag = frag.replace("{{SELECTOR}}", selector(lang, ex, conteos))
    frag = frag.replace("</style>", SELECTOR_CSS + "</style>", 1)
    return frag


def pagina_404(lang):
    """La 404 vive fuera de toda certificación, así que no puede enlazar a
    /test/ ni a /tarjetas/: desde la reestructuración esas páginas solo existen
    dentro de una. Antes aquí se borraban todos los enlaces con una expresión
    regular, y la página quedaba prometiendo una lista de destinos y pintando
    un hueco vacío. Ahora quedan los dos que sí existen siempre: elegir
    certificación, y volver a la última elegida si el navegador la recuerda."""
    frag = open(os.path.join(LANGS[lang]["frag"], "404src.html"), encoding="utf-8").read()
    frag = re.sub(r'<meta name="viewport"[^>]*>\s*', "", frag, count=1)
    frag = frag.replace('href="/en/"', f'href="{ruta(lang, "index")}"')
    frag = frag.replace('href="/"', f'href="{ruta(lang, "index")}"')
    seguir = SELECTOR_T[lang][2]
    etiqueta = "Seguir donde lo dejaste" if lang == "es" else "Pick up where you left off"
    return frag + (
        f'<script>\ntry{{const c=localStorage.getItem("claude-certs-cert");'
        f'if(c&&{json.dumps(CERT_SLUG)}[c]){{const a=document.getElementById("ult");'
        f'a.href={json.dumps(BASE_PATH + "/" + LANGS[lang]["prefix"])}+{json.dumps(CERT_SLUG)}[c]+"/";'
        f'a.innerHTML={json.dumps(seguir)}.replace("{{c}}",c)'
        f'+{json.dumps("<span>" + etiqueta + "</span>")};a.hidden=false;}}}}catch(e){{}}\n</script>')


SELECTOR_CSS = '''
.certs{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-bottom:14px}
@media(max-width:680px){.certs{grid-template-columns:1fr}}
.cert{display:block;background:var(--surface);border:1px solid var(--line);border-radius:12px;
  padding:16px 17px;text-decoration:none;color:var(--ink);transition:.14s}
.cert:hover{border-color:var(--accent);transform:translateY(-1px)}
.cert .cod{font-family:var(--mono);font-size:var(--t-micro);letter-spacing:.09em;color:var(--accent-ink);font-weight:700}
.cert .nm{font-size:var(--t-base);font-weight:600;letter-spacing:-.015em;margin:3px 0 5px}
.cert .meta{font-size:var(--t-menor);color:var(--ink-3)}
.seguir{display:inline-block;margin-bottom:8px;font-size:var(--t-dato);font-weight:550}
'''


def datos(lang):
    suf = LANGS[lang]["data"]
    d = os.path.join(SRC, "data")
    it = json.load(open(os.path.join(d, f"items{suf}.json"), encoding="utf-8"))
    cd = json.load(open(os.path.join(d, f"cards{suf}.json"), encoding="utf-8"))
    ex = json.load(open(os.path.join(d, "exams.json"), encoding="utf-8"))
    return it, cd, ex


def valida(it, cd, ex, lang):
    errores = []
    for n, x in enumerate(it["items"]):
        ctx = f'[{lang}] ítem {n} ({x.get("e","?")})'
        if x["e"] not in ex: errores.append(f"{ctx}: examen desconocido")
        elif x["d"] not in ex[x["e"]]["w"]: errores.append(f'{ctx}: dominio fuera del blueprint: {x["d"]}')
        if len(x["o"]) < 2: errores.append(f"{ctx}: menos de dos opciones")
        if not x["a"] or any(a >= len(x["o"]) for a in x["a"]): errores.append(f"{ctx}: respuesta fuera de rango")
        if len(set(x["a"])) != len(x["a"]): errores.append(f"{ctx}: respuesta duplicada")
        if not x.get("s", "").startswith("http"): errores.append(f"{ctx}: sin fuente")
        if len(set(x["o"])) != len(x["o"]): errores.append(f"{ctx}: opciones repetidas")
        if "v" in x and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", x["v"]): errores.append(f"{ctx}: fecha de verificación mal formada")
        if "c" in x and not x["c"].strip(): errores.append(f"{ctx}: cita vacía")
    vistos = {}
    for n, x in enumerate(it["items"]):
        k = x["q"][:90]
        if k in vistos: errores.append(f'[{lang}] ítem {n}: enunciado duplicado del {vistos[k]}')
        vistos[k] = n
    # las tarjetas se agrupan por el nombre del tema: un desajuste lo esconde
    temas = set(cd["temas"])
    huerfanos = sorted({c["t"] for c in cd["cards"]} - temas)
    for t in huerfanos:
        errores.append(f'[{lang}] tarjetas: el tema "{t}" no está en la lista de temas')
    if cd["count"] != len(cd["cards"]):
        errores.append(f'[{lang}] tarjetas: count={cd["count"]} pero hay {len(cd["cards"])}')
    return errores


def export(it, ex, lang):
    """Banco documentado, sin HTML, para quien lo reutilice fuera de la web."""
    strip = lambda s: re.sub(r"<[^>]+>", "", s)
    aviso = {"es": ("Ítems propios escritos contra los objetivos publicados de cada examen. "
                    "No proceden del banco real ni lo reproducen. Proyecto no afiliado a Anthropic."),
             "en": ("Original items written against the objectives each exam guide publishes. "
                    "They do not come from the live exam bank and do not reproduce it. "
                    "Project not affiliated with Anthropic.")}[lang]
    return {
        "generated": it["generated"], "language": lang, "count": len(it["items"]),
        "disclaimer": aviso, "license": "CC BY 4.0",
        "exams": {k: {"name": v["name"], "domain_weights": v["w"]} for k, v in ex.items()},
        "items": [{"id": f'{x["e"]}-{i:03d}', "exam": x["e"], "domain": x["d"],
                   "stem": strip(x["q"]), "options": [strip(o) for o in x["o"]],
                   "answer": x["a"], "multi": len(x["a"]) > 1,
                   "rationale": strip(x["r"]), "source": x["s"]}
                  for i, x in enumerate(it["items"])],
    }


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    errores, resumen, construidas = [], [], []
    scope = json.load(open(os.path.join(SRC, "data", "scope.json"), encoding="utf-8"))

    def emite(path, html):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").write(html)
        construidas.append((os.path.relpath(path, OUT), html))

    for lang, cfg in LANGS.items():
        base = os.path.join(OUT, cfg["prefix"].rstrip("/")) if cfg["prefix"] else OUT
        os.makedirs(base, exist_ok=True)
        it, cd, ex = datos(lang)
        errores += valida(it, cd, ex, lang)
        errores += valida_scope(scope, cd, ex)
        if lang == "es":                       # el banco es el mismo traducido
            errores += valida_banco(it["items"], ex)
        T = json.load(open(os.path.join(SRC, "i18n", f"{lang}.json"), encoding="utf-8"))

        # Los temas se declaran por posición en scope.json, así que el nombre
        # traducido sale del índice y no hace falta traducir el etiquetado.
        tema_x = {cd["temas"][t["i"]]: t["x"] for t in scope["card_topics"]}
        ap_tot = len(scope["sections"]["apuntes"])
        conteos = {}

        for cert in CERTS:
            cbase = os.path.join(base, CERT_SLUG[cert])
            items = [x for x in it["items"] if x["e"] == cert]
            temas_in = [t for t in cd["temas"] if cert in tema_x[t]]
            cartas = [c for c in cd["cards"] if cert in tema_x[c["t"]]]
            conteos[cert] = (len(items), len(cartas))
            n_ap = sum(1 for v in scope["sections"]["apuntes"].values() if cert in v)

            cifras = {"N_ITEMS": len(items), "N_CARDS": len(cartas), "N_EXAMS": len(ex)}
            for slug in PAGES:
                if slug == "ruta" and cert not in RUTA_SRC:
                    continue
                emite(os.path.join(cbase, SLUG[lang][slug], "index.html"),
                      wrap(lang, slug, cert, cifras, T, scope))

            emite(os.path.join(cbase, "index.html"),
                  envuelve(lang, "home", cert,
                           home(lang, cert, ex, len(items), len(cartas), n_ap, ap_tot, T)))

            # Datos acotados al examen. El simulador ya no tiene que filtrar ni
            # ofrecer un conmutador: lo que se sirve aquí es sólo de esta cert.
            json.dump({"generated": it["generated"], "exam": cert,
                       "items": [dict(x, i=ident(x)) for x in items]},
                      open(os.path.join(cbase, "items.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            # El mazo entero viaja, pero cada tarjeta dice si entra en este
            # examen: las tandas sólo usan las que entran y el resto queda
            # accesible en un bloque aparte.
            json.dump({"generated": cd["generated"], "exam": cert, "count": len(cartas),
                       "temas": temas_in,
                       "fuera": [t for t in cd["temas"] if cert not in tema_x[t]],
                       "cards": [dict(c, x=cert in tema_x[c["t"]]) for c in cd["cards"]]},
                      open(os.path.join(cbase, "cards.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            shutil.copy(os.path.join(SRC, "data", "exams.json"), os.path.join(cbase, "exams.json"))
            # sólo las claves de esta certificación: la app lo pide desde aquí
            json.dump({k: v for k, v in migracion(it["items"]).items() if k.startswith(cert + "#")},
                      open(os.path.join(cbase, "migra.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
            json.dump(export({"generated": it["generated"], "items": items}, ex, lang),
                      open(os.path.join(cbase, "item-bank.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)

        # Portada: elegir certificación
        emite(os.path.join(base, "index.html"),
              envuelve(lang, "index", None, portada(lang, ex, conteos, T)))
        if lang == "es":
            emite(os.path.join(OUT, "404.html"), envuelve(lang, "404", None, pagina_404(lang)))

        ogsrc = os.path.join(SRC, "static", f'og{cfg["data"]}.png')
        if os.path.exists(ogsrc):
            shutil.copy(ogsrc, os.path.join(base, "og.png"))
        resumen.append((lang, len(it["items"]), cd["count"], it, ex))

    # Los dos idiomas son el mismo banco traducido: si se desalinean, la clave de
    # respuesta de un idioma deja de corresponder con sus opciones. Esto no se ve
    # en el navegador, así que se comprueba aquí.
    if len(resumen) > 1:
        base_lang, _, _, base_it, _ = resumen[0]
        base_cd = json.load(open(os.path.join(SRC, "data", "cards.json"), encoding="utf-8"))
        for lang, _, _, it, _ in resumen[1:]:
            a, b = base_it["items"], it["items"]
            if len(a) != len(b):
                errores.append(f"[{lang}] el banco tiene {len(b)} ítems y [{base_lang}] {len(a)}")
            for n, (x, y) in enumerate(zip(a, b)):
                for k in ("e", "d", "a", "s", "c", "v"):
                    if x.get(k) != y.get(k):
                        errores.append(f'[{lang}] ítem {n}: "{k}" no coincide con [{base_lang}]')
                if len(x["o"]) != len(y["o"]):
                    errores.append(f"[{lang}] ítem {n}: distinto número de opciones que [{base_lang}]")
            cd2 = json.load(open(os.path.join(SRC, "data", f'cards{LANGS[lang]["data"]}.json'), encoding="utf-8"))
            if len(base_cd["cards"]) != len(cd2["cards"]):
                errores.append(f"[{lang}] el mazo tiene {len(cd2['cards'])} tarjetas y [{base_lang}] {len(base_cd['cards'])}")
            for n, (x, y) in enumerate(zip(base_cd["cards"], cd2["cards"])):
                if x["id"] != y["id"]:
                    errores.append(f'[{lang}] tarjeta {n}: id "{y["id"]}" no coincide con "{x["id"]}"')

    # Una etiqueta de apertura sin su ">" no da error en ninguna parte: el
    # navegador se traga el texto como si fueran atributos y el resto de la
    # página hereda los estilos de esa etiqueta. Pasó de verdad al generar
    # anclas en los h2, y con el recuento de aperturas y cierres cuadrando.
    errores += valida_tipografia(construidas)

    ABIERTA = re.compile(r"<(h[1-6]|section|nav|div|a|td|th|tr|table)\b[^>]*?<")
    for rel, html in construidas:
        for m in ABIERTA.finditer(html):
            errores.append(f"{rel}: <{m.group(1)}> sin cerrar -> {m.group(0)[:60]!r}")
        for tag in ("h1", "h2", "h3", "section", "table", "nav"):
            ab, ce = len(re.findall(rf"<{tag}\b", html)), len(re.findall(rf"</{tag}>", html))
            if ab != ce:
                errores.append(f"{rel}: <{tag}> abre {ab} y cierra {ce}")

    if errores:
        print("BUILD DETENIDO · los datos tienen problemas:")
        for e in errores[:20]: print("  ·", e)
        raise SystemExit(1)

    hoy = datetime.date.today().isoformat()
    def todas(l):
        yield ("index", None)
        for c in CERTS:
            yield ("home", c)
            for sl in PAGES:
                if sl != "ruta" or c in RUTA_SRC:
                    yield (sl, c)
    urls = "".join(
        f'<url><loc>{BASE}{ruta(l, sl, c)}</loc><lastmod>{hoy}</lastmod>'
        + "".join(f'<xhtml:link rel="alternate" hreflang="{o}" href="{BASE}{ruta(o, sl, c)}"/>' for o in LANGS)
        + "</url>"
        for l in LANGS for sl, c in todas(l))
    open(os.path.join(OUT, "sitemap.xml"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        f'xmlns:xhtml="http://www.w3.org/1999/xhtml">{urls}</urlset>\n')
    open(os.path.join(OUT, "robots.txt"), "w").write(
        f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")

    # reparto real frente al peso oficial, por si el banco se desequilibra
    _, _, _, it, ex = resumen[0]
    print("Datos validados. Reparto por examen:")
    for e_, cfgx in ex.items():
        sub = [x for x in it["items"] if x["e"] == e_]
        c = Counter(x["d"] for x in sub)
        peor = max(((d, abs(c.get(d, 0) / len(sub) * 100 - w)) for d, w in cfgx["w"].items()),
                   key=lambda t: t[1]) if sub else ("-", 0)
        print(f"  {e_:<8} {len(sub):>3} ítems · mayor desvío: {peor[0]} ({peor[1]:.0f} pts)")
    print()
    for lang, n_it, n_cd, _, _ in resumen:
        print(f"  {lang}  {ruta(lang, 'index'):<6} {n_it} ítems · {n_cd} tarjetas · {len(CERTS)} certificaciones")
    n = sum(len(fs) for _, _, fs in os.walk(OUT))
    print(f"\nSitio en {OUT}/ · {n} ficheros · montado en {BASE}{BASE_PATH or '/'}")


if __name__ == "__main__":
    main()
