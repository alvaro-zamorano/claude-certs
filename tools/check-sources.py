#!/usr/bin/env python3
"""Comprueba que las fuentes del sitio siguen vivas.

    python3 tools/check-sources.py            # todas
    python3 tools/check-sources.py --fail     # sale con 1 si alguna está rota

Recorre el campo `s` de cada ítem y las fuentes de los apuntes
(src/data/sources.json), pide cada URL una vez y avisa de tres cosas: las que
no responden, las que redirigen a otra dirección y las que no se han podido
comprobar desde esta red. «Fuente enlazada en cada ítem» solo vale algo si el
enlace lleva a alguna parte; la documentación se mueve y esto lo detecta sin
esperar a que lo avise un lector.

No entra en el build: depende de la red y un fallo ajeno no debe impedir
publicar. Pensado para lanzarlo antes de cada revisión del banco.
"""
import json, os, sys, urllib.request, urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
UA = {"User-Agent": "Mozilla/5.0 (link checker)"}


def usos():
    d = os.path.join(ROOT, "src", "data")
    u = defaultdict(list)
    for n, x in enumerate(json.load(open(os.path.join(d, "items.json"), encoding="utf-8"))["items"]):
        u[x["s"]].append(f'ítem {n} ({x["e"]})')
    for sec, v in json.load(open(os.path.join(d, "sources.json"), encoding="utf-8"))["apuntes"].items():
        for url in v.get("src", []) + v.get("extra", []):
            u[url].append(f"apuntes §{sec}")
    return u


def pide(url):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25)
        return url, r.status, r.geturl()
    except urllib.error.HTTPError as e:
        return url, e.code, url
    except Exception as e:                      # red, proxy, TLS
        return url, 0, type(e).__name__


def norm(u):
    return u.rstrip("/").replace("://www.", "://").split("#")[0]


def main():
    u = usos()
    with ThreadPoolExecutor(8) as ex:
        res = sorted(ex.map(pide, u))
    rotas = [(a, c) for a, c, _ in res if c >= 400]
    sin = [(a, f) for a, c, f in res if c == 0]
    movidas = [(a, f) for a, c, f in res if 200 <= c < 400 and norm(f) != norm(a)]
    print(f"{len(u)} fuentes distintas · {len(res) - len(rotas) - len(sin)} responden · "
          f"{len(movidas)} redirigen · {len(rotas)} rotas · {len(sin)} sin comprobar\n")
    for tit, lista in (("ROTAS", rotas), ("REDIRIGEN", movidas), ("SIN COMPROBAR", sin)):
        if lista:
            print(tit)
            for a, b in lista:
                print(f"  {a}\n     -> {b}   [{len(u[a])} usos: {', '.join(u[a][:3])}{'…' if len(u[a]) > 3 else ''}]")
            print()
    sys.exit(1 if rotas and "--fail" in sys.argv else 0)


if __name__ == "__main__":
    main()
