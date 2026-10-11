# -*- coding: utf-8 -*-
"""
Exporta los artefactos ligeros de todas las partes al reporte web.

Arquitectura "calcular una vez, explorar muchas": Spark ya dejo agregados,
curvas y rankings en data/derivados/artefactos/. Este paso (LOCAL, sin Spark)
los empaqueta en web/data/datos.js como un unico objeto window.DATOS, de modo
que la pagina:
  - responde al instante, sin volver a tocar Spark ni el Parquet;
  - funciona tambien abriendo index.html directamente (file://), sin servidor,
    porque un <script> no esta sujeto a las restricciones de fetch() local.

Privacidad: se EXCLUYEN los artefactos *_PRIVADO* (RUC y nombres de
proveedores). El reporte publico usa solo etiquetas anonimas (regla de la
seccion 14 del informe de avance).

Uso:  python scripts/15_exportar_web.py
"""
import ast
import json
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno  # noqa: E402

ARTEFACTOS = entorno.DERIVADOS / "artefactos"
DESTINO = entorno.RAIZ / "web" / "data" / "datos.js"
MAX_FILAS = 5000          # ningun artefacto de la web necesita mas
# Columnas que la pagina realmente usa, para no inflar datos.js
COLUMNAS = {
    "p5_reglas_postores": ["antecedente", "consecuente", "n_grupo", "soporte",
                           "confianza", "lift", "procesos_grupo", "entidades",
                           "rubro_principal", "pct_gana_grupo", "pct_gana_esperado"],
}


def limpiar(v):
    """NaN/inf no son JSON valido."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, dict):
        return {k: limpiar(x) for k, x in v.items()}
    if isinstance(v, list):
        return [limpiar(x) for x in v]
    return v


def listas(df):
    """Las columnas con listas llegan del CSV como texto de Python
    ("['P0001 (empresa)']"); se devuelven a listas para que el JSON las
    tenga como arreglos."""
    for c in df.columns:
        # pandas 3 guarda el texto como dtype "str", no "object"
        es_texto = (pd.api.types.is_object_dtype(df[c])
                    or pd.api.types.is_string_dtype(df[c]))
        if es_texto and len(df) and df[c].astype(str).str.startswith("[").all():
            df[c] = df[c].map(ast.literal_eval)
    return df


def tipo_ruc(v):
    num = str(v).replace("PE-RUC-", "")
    return {"10": "persona natural", "20": "empresa"}.get(num[:2], "otro")


def anonimizar(df):
    """Segunda barrera: aunque un artefacto traiga RUC o nombres de
    proveedores (p.ej. los pares de la Parte II), a la web solo llega el tipo
    de contribuyente. Los nombres de ENTIDADES publicas (buyer_name) se
    conservan: son organismos del Estado, no personas."""
    for c in list(df.columns):
        if c.startswith("ruc"):
            df["tipo" + c[3:]] = df[c].map(tipo_ruc)
    quitar = [c for c in df.columns
              if c.startswith(("ruc", "nombre", "name")) or c in ("ganador", "postores")]
    return df.drop(columns=quitar)


def main():
    datos, tamanios = {}, {}
    for ruta in sorted(ARTEFACTOS.iterdir()):
        if "PRIVADO" in ruta.name or ruta.suffix not in (".csv", ".json"):
            continue
        clave = ruta.stem
        if ruta.suffix == ".json":
            datos[clave] = json.loads(ruta.read_text(encoding="utf8"))
        else:
            df = listas(anonimizar(pd.read_csv(ruta).head(MAX_FILAS)))
            if clave in COLUMNAS:
                df = df[COLUMNAS[clave]]
            datos[clave] = df.to_dict(orient="records")
        datos[clave] = limpiar(datos[clave])
        tamanios[clave] = len(json.dumps(datos[clave], ensure_ascii=False))

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    js = ("// Generado por scripts/15_exportar_web.py - no editar a mano\n"
          "window.DATOS = " + json.dumps(datos, ensure_ascii=False,
                                         separators=(",", ":")) + ";\n")
    DESTINO.write_text(js, encoding="utf8")
    for k, v in sorted(tamanios.items(), key=lambda kv: -kv[1]):
        print(f"  {k:45s} {v / 1024:8.1f} KB")
    print(f"\n{len(datos)} artefactos -> {DESTINO} ({len(js) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
