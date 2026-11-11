# claude-certs

Herramienta de estudio abierta para las certificaciones Claude de Anthropic.
Material libre bajo CC BY 4.0: páginas estáticas y unos ficheros JSON, sin backend
ni seguimiento. Se puede reutilizar, no solo consultar.

**No es un proyecto oficial ni está afiliado a Anthropic.**

Español en la raíz, inglés bajo `/en/`.

## Qué incluye

| Ruta | `/en/` | Qué es |
|---|---|---|
| `/` | `/en/` | Landing: qué es, por dónde empezar y qué no es |
| `/test/` | `/en/test/` | Simulador con los pesos reales de cada blueprint y score proyectado sobre 1000 |
| `/tarjetas/` | `/en/cards/` | Tarjetas con repetición espaciada, tandas de diez y racha diaria |
| `/apuntes/` | `/en/notes/` | Veinte secciones con el porqué de cada concepto |
| `/referencia/` | `/en/reference/` | La superficie de API: campos, valores admitidos y formas de retorno |
| `/architect/` · `/developer/` | ídem | Rutas de estudio por examen |
| `/flash/` | `/en/flash/` | Repaso de última hora ordenado por peso |

## Datos

`src/data/` es la fuente de verdad y la web los consume tal cual:

| Fichero | Qué es |
|---|---|
| `items.json` · `items.en.json` | 245 ítems de práctica. El HTML de los campos es intencionado: se renderiza |
| `exams.json` | Los cuatro exámenes con los pesos oficiales de cada dominio. Común a los dos idiomas |
| `cards.json` · `cards.en.json` | 184 tarjetas agrupadas por tema |

Las dos versiones de un ítem comparten `e`, `d`, `a` y `s` byte a byte: solo cambian el
enunciado, las opciones y la explicación. El orden de las opciones **no** puede alterarse entre
idiomas, porque `a` guarda índices.

El build genera además `item-bank.json` por idioma: el mismo banco sin HTML y con nombres
legibles, para quien quiera reutilizarlo fuera de esta web.

## Cómo funciona

Las páginas de `src/` son fragmentos (título, estilos y cuerpo). `build.py` las envuelve en
documentos completos y aplica de una sola vez lo que si no habría que recordar en cada página:
doctype y `lang`, charset, meta description, Open Graph con imagen, favicon inline,
`:focus-visible`, `prefers-reduced-motion`, corrección de contraste a AA, estilos de impresión,
barra de navegación, conmutador de idioma, `hreflang` y pie con el aviso.

### Los dos idiomas

Las páginas de prosa tienen un fragmento por idioma: `src/` para el español y `src/en/` para el
inglés. Las **dos páginas interactivas son una sola base de código** —`src/test.html` y
`src/tarjetas.html`— porque duplicarlas significaría arreglar cada fallo dos veces. Se traducen
con `src/i18n/<lang>.json` por dos vías, según dónde esté la cadena:

- **fuera del `<script>`**, con marcadores `{{t.clave}}` que el build sustituye como texto;
- **dentro del `<script>`**, con referencias `T.clave`, y el build inyecta `T` como JSON.

La segunda vía no es un capricho: sustituir texto dentro de un literal de JavaScript se rompe en
cuanto una cadena inglesa lleva apóstrofo (`Couldn't load`). Pasando por JSON, el escapado lo
hace el serializador.

Los `fetch` de datos son **relativos a propósito**: `/tarjetas/` pide `../cards.json` y resuelve
a `/cards.json`, mientras que `/en/cards/` resuelve a `/en/cards.json`. La página no necesita
saber en qué idioma está.


### Una sola capa de presentación

Cada fragmento trae su propia hoja de estilos con sus componentes, y durante un
tiempo trajo también su propia idea de lo compartido: llegó a haber ocho anchos
de contenedor entre 560 y 1120 px, ocho tamaños de `h1` entre 1,05 y 2 rem,
siete paddings y cinco tamaños de párrafo. Los colores sí coincidían; todo lo
que va por encima, no.

`build.py` inyecta ahora `CSS_UNIFICADO` al final del `<style>` de cada página.
Al ir el último dentro de la misma hoja, gana a las reglas propias de igual
especificidad sin tener que reescribir nueve fragmentos, y basta con tocar un
sitio para cambiar el sistema entero.

Tres anchos, elegidos por densidad y no por gusto:

| token | valor | para qué |
|---|---|---|
| `--w-datos` | 1240 px | tablas de muchas columnas (referencia, simulador) |
| `--w-texto` | 1040 px | prosa y tarjetas de navegación |
| `--w-foco` | 780 px | una sola cosa a la vez (tarjetas, 404) |

La prosa no crece con el contenedor: se acota a 74-78 caracteres por línea,
porque una tabla necesita el ancho y un párrafo no.

**En móvil nada obliga a arrastrar de lado.** Eso costó tres iteraciones y las
tres lecciones están en el CSS como comentario, porque son contraintuitivas:
`overflow-wrap:anywhere` reduce el ancho mínimo intrínseco y parte las palabras
por la mitad (`Obli/gat/orio`), así que la prosa usa `break-word`; pero
`break-word` no baja del ancho de la palabra más larga, así que los
identificadores largos —`model_context_window_exceeded`— sí necesitan
`anywhere`; y un `min-width` puesto para «proteger» una columna es lo que
volvía a desbordar la tabla entera.

Medido sobre doce páginas a 375 y a 1512 px: cero scroll lateral.

### El simulador y la proyección

Cuatro modos: drill del dominio más flojo, simulacro ponderado de 20, **examen completo** (el
número de ítems y los minutos reales, de `exams.json`; corrige al final y deja marcar, saltar y
volver) y repaso de fallos. Cada bloque termina en un informe con nota, acierto por dominio,
tiempo, los fallos con su explicación y los bloques anteriores.

`src/score.js` es la única definición del score proyectado; el build la incrusta en el simulador
y en la portada de cada certificación. Cuenta ítems distintos y solo el último intento de cada
uno, no proyecta por debajo de 30 ítems y da un intervalo además del punto. La conversión a
100-1000 es lineal y aproximada, y la interfaz lo dice.

Un fallo entra en la cola de repaso al momento y sale tras dos aciertos seguidos separados por
dos días. El progreso vive en `localStorage` y se puede exportar e importar como JSON.

### Apuntes, simulador y ruta conectados

`src/data/sources.json` lista las fuentes de cada sección de los apuntes con la URL completa. El
build las pinta como enlaces y deduce de ellas a qué sección pertenece cada ítem (la que cita su
misma fuente). Con eso:

- cada explicación del simulador enlaza a su sección de apuntes, y el informe de bloque dice qué
  secciones repasar;
- cada sección de los apuntes enlaza a un drill con sus ítems (`/test/?sec=<id>`) y muestra tu
  acierto en ella;
- la ruta de estudio abre con tu estado real por dominio y un drill de cada uno (`?dom=`).

### Metodología y calidad del banco

`/metodologia/` (`/en/methodology/`) se genera en el build con los números reales del banco:
ítems con cita y fecha, sesgo de longitud en los dos sentidos, posición, desvío del blueprint,
absolutos y enunciados sin pregunta. Los mismos datos salen en `site/quality.json` y por consola.

```bash
python3 tools/check-sources.py   # ¿siguen vivas las fuentes del banco y de los apuntes?
```

### Verificación por ítem

Además de la fuente `s`, un ítem puede llevar `c` (cita literal de la fuente que sostiene la
clave) y `v` (fecha de verificación, `AAAA-MM-DD`). Son opcionales; el simulador los muestra
junto a la explicación. La meta es que todo ítem los tenga: una URL de página dice de qué va el
ítem, la cita demuestra que la clave es correcta.

### Validaciones que detienen el build

- Ítem con dominio fuera del blueprint, respuesta fuera de rango, menos de dos opciones,
  opciones repetidas, enunciado duplicado o sin fuente.
- Tarjeta cuyo tema no aparece en la lista de temas: el agrupamiento es por cadena, así que un
  desajuste hace desaparecer un tema entero sin dar error en el navegador.
- Cadena de interfaz ausente del diccionario de un idioma.

Después informa del reparto por examen y del mayor desvío frente al peso oficial, para detectar
cuándo el banco se desequilibra.

```bash
python3 build.py             # src/ -> site/
python3 tools/make-og.py . es
python3 tools/make-og.py . en   # regenera las tarjetas Open Graph con las cifras reales
npm install jsdom && node tools/smoke.cjs   # prueba de humo de la interfaz
```

`site/` es la carpeta que se despliega. No se edita a mano: se regenera.

### La prueba de humo

`tools/smoke.cjs` levanta un servidor sobre `site/`, carga el simulador y las tarjetas en los dos
idiomas con jsdom y recorre el flujo entero: elegir examen, responder, atajos de teclado, una
tanda completa de diez tarjetas y la persistencia en `localStorage`. El build valida los datos;
esto valida que la interfaz sigue viva después de tocar el i18n o las rutas de datos.

## Desplegar

Cloudflare Pages o cualquier host de estáticos:

| Campo | Valor |
|---|---|
| Build command | `python3 build.py` |
| Build output directory | `site` |
| Framework preset | None |

No hace falta nada más: no hay dependencias de Python fuera de la biblioteca estándar. `jsdom`
solo se necesita para la prueba de humo, y Pillow solo para regenerar las imágenes Open Graph.

## Contribuir

El banco de ítems y las tarjetas viven en `src/data/`. Tres reglas duras:

1. **Nada que proceda del examen real.** Ni recordado, ni parafraseado, ni «reconstruido».
2. **Ningún ítem sin una URL oficial que lo respalde**, en el campo `s`. El build lo comprueba.
3. **Nunca reproducir las guías de examen**, que Anthropic distribuye bajo acuerdo a sus
   partners. Se puede citar un objetivo y enlazar; no copiar.

Si añades un ítem en un idioma, añádelo en el otro con el mismo índice y el mismo orden de
opciones. El build comprueba que los dos bancos están alineados —mismo número de ítems y, en
cada posición, el mismo examen, dominio, clave de respuesta y fuente— y se detiene si no lo
están, porque un desajuste ahí no da ningún error visible en el navegador: simplemente marca
como correcta la opción equivocada.

## Licencia

Código bajo MIT. Contenido (ítems, tarjetas, apuntes) bajo CC BY 4.0.
