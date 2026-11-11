# Publicar este sitio

La carpeta está lista para moverse a un repositorio público propio.

## 1 · Crear el repositorio

En GitHub, repositorio nuevo **público** llamado `claude-certs`. Después:

```bash
cp -r claude-certs-public /ruta/claude-certs && cd /ruta/claude-certs
git init && git add -A
git commit -m "claude-certs: herramienta de estudio abierta"
git remote add origin git@github.com:TU-USUARIO/claude-certs.git
git push -u origin main
```

## 2 · Cloudflare Pages

Workers & Pages → Create application → Pages → Connect to Git → `claude-certs`.

| Campo | Valor |
|---|---|
| Production branch | `main` |
| Framework preset | None |
| Build command | `python3 build.py` |
| Build output directory | `site` |

**Sin Cloudflare Access**: este proyecto sí es público, al revés que el dashboard.

## 3 · Dominio (opcional)

Custom domains → añadir `certs.tu-dominio.com`. Después, cambiar `BASE` en `build.py`
para que las URLs canónicas, los `hreflang`, el `og:image` y el sitemap apunten al dominio
real. Es el único sitio donde está escrita la URL: una línea.

## 4 · Comprobar el despliegue

```bash
python3 build.py                             # se detiene solo si los datos no cuadran
npm install jsdom && node tools/smoke.cjs    # recorre la interfaz en es y en
```

Y sobre el sitio ya desplegado, mirar que responden `/`, `/en/`, una ruta inexistente
(debe dar 404, no la portada) y `/og.png`.

## Qué NO se lleva

Este sitio es independiente del dashboard privado. No contiene threads, misiones,
credenciales ni nada del pipeline: solo las páginas de estudio y los JSON de datos.

## Un aviso sobre los dos idiomas

El sitio se publica en español (raíz) e inglés (`/en/`). Mantener dos idiomas cuesta: cada
ítem nuevo hay que escribirlo dos veces o el build se detiene por desalineo, que es
deliberado — es preferible un build roto a un examen que marca como correcta la opción
equivocada en un idioma. Si en algún momento el inglés deja de merecer la pena, quitarlo es
borrar `src/en/`, `src/data/*.en.json` y la entrada `"en"` de `LANGS` en `build.py`.
