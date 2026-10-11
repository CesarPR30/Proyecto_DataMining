# -*- coding: utf-8 -*-
"""
Ejecuta el pipeline completo en orden, con el mismo interprete de Python.

    python scripts/ejecutar_todo.py                # desde la ingesta
    python scripts/ejecutar_todo.py --desde 12     # retoma en un paso
    python scripts/ejecutar_todo.py --hasta 09     # se detiene en un paso
    python scripts/ejecutar_todo.py --con-descarga # incluye la descarga

Cada paso deja su salida en data/derivados/logs/<paso>.log. Si un paso falla
se detiene: los siguientes dependen de sus artefactos.
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
PASOS = [
    ("00", "descargar_datos.py"),         # solo con --con-descarga
    ("04", "04_verificar_entorno.py"),
    ("05", "05_ingesta_parquet.py"),
    ("06", "06_verificar_ingesta.py"),
    ("07", "07_representaciones.py"),
    ("08", "08_eda_parte1.py"),
    ("09", "09_figuras.py"),
    ("10", "10_parte2_similitud.py"),
    ("11", "11_figuras_parte2.py"),
    ("12", "12_parte3_ann.py"),
    ("13", "13_parte4_flujos.py"),
    ("14", "14_parte5_reglas.py"),
    ("15", "15_exportar_web.py"),
]


def main():
    args = sys.argv[1:]
    desde = args[args.index("--desde") + 1] if "--desde" in args else "04"
    logs = entorno.DERIVADOS / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    hasta = args[args.index("--hasta") + 1] if "--hasta" in args else "99"
    pasos = [(n, s) for n, s in PASOS if desde <= n <= hasta]
    if "--con-descarga" not in args:
        pasos = [(n, s) for n, s in pasos if n != "00"]
    t_total = time.time()
    for n, script in pasos:
        t0 = time.time()
        log = logs / f"{Path(script).stem}.log"
        print(f"[{n}] {script} ...", end=" ", flush=True)
        with open(log, "w", encoding="utf8") as fh:
            r = subprocess.run([sys.executable, str(SCRIPTS / script)],
                               stdout=fh, stderr=subprocess.STDOUT,
                               env={**__import__("os").environ,
                                    "PYTHONIOENCODING": "utf-8",
                                    "PYTHONUNBUFFERED": "1"})
        print(f"{'OK' if r.returncode == 0 else 'FALLO'} "
              f"({(time.time() - t0) / 60:.1f} min) -> {log.name}", flush=True)
        if r.returncode != 0:
            sys.exit(r.returncode)
    print(f"pipeline completo en {(time.time() - t_total) / 60:.1f} min")


if __name__ == "__main__":
    main()
