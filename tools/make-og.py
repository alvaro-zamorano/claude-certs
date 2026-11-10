#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera src/static/og.png (1200x630). Se ejecuta a mano cuando cambian las cifras.

    python3 tools/make-og.py

La tarjeta usa la misma paleta que el sitio: papel crudo, terracota y tinta cálida.
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = sys.argv[2] if len(sys.argv) > 2 else "es"
SUF = "" if LANG == "es" else "." + LANG
OUT = os.path.join(ROOT, "src", "static", f"og{SUF}.png")

TEXTO = {
 "es": {"eyebrow": "P R O Y E C T O   A B I E R T O   ·   N O   O F I C I A L",
        "titulo": ["Certificaciones Claude,", "con material que", "puedes auditar."],
        "sub": ["Simulador con los pesos reales de cada blueprint, tarjetas con",
                "repetición espaciada y la fuente oficial enlazada en cada ítem."],
        "cifras": ["ÍTEMS", "TARJETAS", "EXÁMENES", "LICENCIA"]},
 "en": {"eyebrow": "O P E N   P R O J E C T   ·   U N O F F I C I A L",
        "titulo": ["Claude certifications,", "with material you", "can audit."],
        "sub": ["A simulator with the real blueprint weights, spaced-repetition",
                "flashcards, and the official source linked on every item."],
        "cifras": ["ITEMS", "CARDS", "EXAMS", "LICENCE"]},
}[LANG]

W, H = 1200, 630
PAPEL = (247, 246, 243)
TINTA = (32, 32, 29)
TINTA2 = (87, 84, 76)
TINTA3 = (139, 135, 121)
TERRA = (181, 84, 31)
LINEA = (224, 221, 212)

G = "/usr/share/fonts/truetype/google-fonts"
L = "/usr/share/fonts/truetype/liberation"


def f(path, size):
    return ImageFont.truetype(path, size)


titulo = lambda s: f(os.path.join(G, "Lora-Variable.ttf"), s)
sans = lambda s: f(os.path.join(L, "LiberationSans-Regular.ttf"), s)
sansb = lambda s: f(os.path.join(L, "LiberationSans-Bold.ttf"), s)
mono = lambda s: f(os.path.join(L, "LiberationMono-Bold.ttf"), s)

# Cifras reales del banco, para que la tarjeta no mienta al envejecer.
items = json.load(open(os.path.join(ROOT, "src", "data", f"items{SUF}.json"), encoding="utf-8"))["items"]
cards = json.load(open(os.path.join(ROOT, "src", "data", f"cards{SUF}.json"), encoding="utf-8"))
n_cards = cards.get("count") or len(cards.get("cards", []))
n_exam = len(json.load(open(os.path.join(ROOT, "src", "data", "exams.json"), encoding="utf-8")))

im = Image.new("RGB", (W, H), PAPEL)
d = ImageDraw.Draw(im)

M = 84  # margen

# Filete superior de acento
d.rectangle([M, 74, M + 62, 79], fill=TERRA)

# Antetítulo
d.text((M, 108), "P R O Y E C T O   A B I E R T O   ·   N O   O F I C I A L",
       font=sansb(17), fill=TERRA)

# Titular
y = 152
for linea in TEXTO["titulo"]:
    d.text((M, y), linea, font=titulo(63), fill=TINTA)
    y += 76

# Subtítulo
d.text((M, y + 14), TEXTO["sub"][0], font=sans(25), fill=TINTA2)
d.text((M, y + 50), TEXTO["sub"][1], font=sans(25), fill=TINTA2)

# Línea de cifras
yc = H - 110
d.line([M, yc - 40, W - M, yc - 40], fill=LINEA, width=2)
cifras = list(zip([str(len(items)), str(n_cards), str(n_exam), "CC BY"], TEXTO["cifras"]))
x = M
for num, lbl in cifras:
    d.text((x, yc), num, font=mono(40), fill=TINTA)
    d.text((x, yc + 50), lbl, font=sansb(15), fill=TINTA3)
    x += max(d.textlength(num, font=mono(40)), d.textlength(lbl, font=sansb(15))) + 62

# Marca, alineada a la derecha sobre la misma línea base
marca = "claude-certs"
wm = d.textlength(marca, font=sansb(27))
d.text((W - M - wm, yc + 6), marca, font=sansb(27), fill=TERRA)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
im.save(OUT, "PNG", optimize=True)
print(f"{OUT}  {os.path.getsize(OUT)//1024} KB  ({len(items)} ítems, {n_cards} tarjetas)")
