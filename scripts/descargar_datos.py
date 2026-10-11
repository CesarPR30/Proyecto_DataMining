# -*- coding: utf-8 -*-
"""
Descarga masiva del corpus OCDS del OECE desde el OCP Data Registry.

Se ejecuta en LOCAL (no usa Spark): es E/S de red y disco, no hay nada que
distribuir. Descarga las particiones anuales en CSV (publicacion 135),
verifica el tamanio contra el Content-Length del servidor y las descomprime en
data/raw/ocds/<ANIO>/<tabla>.csv, que es la estructura que espera la ingesta
(script 05).

Fuente: Open Contracting Partnership, OCP Data Registry, publicacion 135
(Peru - OECE), https://data.open-contracting.org/es/publication/135
Licencia de los datos: CC BY 4.0.

Uso:
    python scripts/descargar_datos.py              # 1900 y 2003..anio actual
    python scripts/descargar_datos.py 2024 2025    # solo algunas particiones
    python scripts/descargar_datos.py --sin-extraer

Es idempotente: si el .tar.gz ya existe con el tamanio correcto no se vuelve a
bajar, y si la carpeta del anio ya tiene main.csv no se vuelve a extraer.
"""
import datetime as dt
import json
import sys
import tarfile
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno  # noqa: E402

URL = ("https://data.open-contracting.org/en/publication/135/"
       "download?name={anio}.csv.tar.gz")
COMPRIMIDOS = entorno.DATOS.parent / "tar"


def descargar(anio, reintentos=3):
    destino = COMPRIMIDOS / f"{anio}.csv.tar.gz"
    url = URL.format(anio=anio)
    for intento in range(1, reintentos + 1):
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                if r.status_code == 404:
                    return None, 0
                r.raise_for_status()
                esperado = int(r.headers.get("Content-Length", 0))
                if destino.exists() and destino.stat().st_size == esperado:
                    return destino, esperado
                parcial = destino.with_suffix(".part")
                with open(parcial, "wb") as fh:
                    for bloque in r.iter_content(1 << 20):
                        fh.write(bloque)
                if esperado and parcial.stat().st_size != esperado:
                    raise IOError(f"tamanio {parcial.stat().st_size} != {esperado}")
                parcial.replace(destino)
                return destino, esperado
        except Exception as e:  # red inestable: reintentar con espera
            print(f"    intento {intento} fallo: {e}")
            time.sleep(5 * intento)
    raise RuntimeError(f"No se pudo descargar {anio}")


def extraer(archivo, anio):
    carpeta = entorno.DATOS / str(anio)
    if (carpeta / "main.csv").exists():
        return carpeta
    entorno.DATOS.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archivo) as t:
        # filter="data" bloquea rutas absolutas, ".." y enlaces fuera del destino
        t.extractall(entorno.DATOS, filter="data")
    return carpeta


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sin_extraer = "--sin-extraer" in sys.argv
    anios = [int(a) for a in args] or [1900] + list(
        range(2003, dt.date.today().year + 1))

    COMPRIMIDOS.mkdir(parents=True, exist_ok=True)
    print(f"destino: {entorno.DATOS}")
    manifiesto = {}
    t0 = time.time()
    for anio in anios:
        t1 = time.time()
        archivo, bytes_ = descargar(anio)
        if archivo is None:
            print(f"{anio}: no publicado, se omite")
            continue
        if not sin_extraer:
            extraer(archivo, anio)
        manifiesto[anio] = {"bytes_comprimido": bytes_,
                            "segundos": round(time.time() - t1, 1)}
        print(f"{anio}: {bytes_ / 1024 ** 2:8.1f} MB  "
              f"({manifiesto[anio]['segundos']} s)")

    total = sum(v["bytes_comprimido"] for v in manifiesto.values())
    print(f"\n{len(manifiesto)} particiones, {total / 1024 ** 3:.2f} GB "
          f"comprimidos, {(time.time() - t0) / 60:.1f} min")
    (entorno.DATOS.parent / "manifiesto_descarga.json").write_text(
        json.dumps({"fuente": URL, "fecha": dt.datetime.now().isoformat(),
                    "particiones": manifiesto}, indent=2), encoding="utf8")


if __name__ == "__main__":
    main()
