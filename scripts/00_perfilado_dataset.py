# -*- coding: utf-8 -*-
"""
Perfilado exploratorio del dataset OCDS - OECE/SEACE (Peru) para la
justificacion de seleccion del dataset (Semana 1, Parte I).

Ejecuta un perfilado *local* con pandas sobre un anio de datos para verificar
que el dataset cumple los cuatro criterios exigidos por el enunciado:
volumen, representabilidad como conjuntos/vectores, dimension temporal y
estructura transaccional derivable.

El pipeline definitivo del proyecto corre sobre Spark; este script solo
sustenta la eleccion del dataset.

Uso:  python scripts/00_perfilado_dataset.py <ruta_carpeta_anio> [salida.json]
"""
import json
import sys
from pathlib import Path

import pandas as pd


def pct(n, d):
    return round(100.0 * n / d, 2) if d else 0.0


def top(serie, k=12):
    return {str(i): int(v) for i, v in serie.value_counts().head(k).items()}


def perfilar(base: Path) -> dict:
    rep = {"anio": base.name, "ruta": str(base)}

    main = pd.read_csv(base / "main.csv", low_memory=False)
    items = pd.read_csv(base / "tender_items.csv", low_memory=False)
    tenderers = pd.read_csv(base / "tender_tenderers.csv", low_memory=False)
    parties = pd.read_csv(base / "parties.csv", low_memory=False)

    # ---------------------------------------------------------------- volumen
    rep["volumen"] = {
        "procesos_main": len(main),
        "ocid_unicos": int(main["ocid"].nunique()),
        "items_licitados": len(items),
        "postores_filas": len(tenderers),
        "postores_ruc_unicos": int(tenderers["id"].nunique()),
        "parties_filas": len(parties),
        "peso_mb_csv_anio": round(
            sum(f.stat().st_size for f in base.glob("*.csv")) / 1024 ** 2, 1
        ),
    }

    # --------------------------------------------------------------- temporal
    fechas = pd.to_datetime(main["tender_datePublished"], errors="coerce", utc=True)
    por_mes = fechas.dt.to_period("M").value_counts().sort_index()
    rep["temporal"] = {
        "campo_usado": "tender_datePublished",
        "min": str(fechas.min()),
        "max": str(fechas.max()),
        "nulos_pct": pct(fechas.isna().sum(), len(main)),
        "procesos_por_mes": {str(k): int(v) for k, v in por_mes.items()},
    }

    # ---------------------------------------------------------- calidad/nulos
    cols_clave = [
        "ocid", "buyer_name", "tender_title", "tender_description",
        "tender_mainProcurementCategory", "tender_procurementMethodDetails",
        "tender_value_amount_PEN", "tender_numberOfTenderers",
        "tender_datePublished", "planning_budget_projectID",
    ]
    rep["nulos_main_pct"] = {
        c: pct(main[c].isna().sum(), len(main)) for c in cols_clave if c in main.columns
    }
    rep["duplicados"] = {
        "ocid_duplicados": int(len(main) - main["ocid"].nunique()),
        "filas_duplicadas_exactas": int(main.duplicated().sum()),
    }

    # ----------------------------------------------------------------- montos
    montos = pd.to_numeric(main["tender_value_amount_PEN"], errors="coerce").dropna()
    rep["montos_pen"] = {
        "n": int(len(montos)),
        "suma_millones": round(float(montos.sum()) / 1e6, 1),
        "media": round(float(montos.mean()), 2),
        "mediana": round(float(montos.median()), 2),
        "p90": round(float(montos.quantile(0.90)), 2),
        "p99": round(float(montos.quantile(0.99)), 2),
        "max": round(float(montos.max()), 2),
        "ceros_o_negativos": int((montos <= 0).sum()),
    }

    # ------------------------------------------------------------ categoricas
    rep["categoricas"] = {
        "mainProcurementCategory": top(main["tender_mainProcurementCategory"]),
        "procurementMethodDetails": top(main["tender_procurementMethodDetails"]),
        "top_entidades_compradoras": top(main["buyer_name"], 15),
        "n_entidades_compradoras": int(main["buyer_name"].nunique()),
    }

    # ------------------------------ criterio 2: registros como conjuntos/texto
    desc = main["tender_description"].dropna().astype(str)
    titulo = main["tender_title"].dropna().astype(str)
    rep["texto_para_shingling"] = {
        "desc_no_nulas_pct": pct(len(desc), len(main)),
        "desc_long_media_chars": round(float(desc.str.len().mean()), 1),
        "desc_long_mediana_chars": int(desc.str.len().median()),
        "titulo_long_media_chars": round(float(titulo.str.len().mean()), 1),
        "desc_palabras_media": round(float(desc.str.split().str.len().mean()), 1),
        "desc_exactamente_duplicadas": int(desc.duplicated().sum()),
        "desc_exactamente_duplicadas_pct": pct(desc.duplicated().sum(), len(desc)),
    }

    # clasificacion de items (UNSPSC/CUBSO) -> vocabulario de items
    if "classification_id" in items.columns:
        cls = items["classification_id"].dropna().astype(str)
        rep["clasificacion_items"] = {
            "esquemas": top(items["classification_scheme"]),
            "codigos_unicos": int(cls.nunique()),
            "cobertura_pct": pct(len(cls), len(items)),
            "top_codigos": top(items["classification_description"], 10),
        }

    # ------------------------- criterio 4: estructura transaccional (canastas)
    # Canasta A: proceso -> conjunto de postores (RUC)
    can_a = tenderers.groupby("main_ocid")["id"].nunique()
    # Canasta B: proceso -> conjunto de codigos de item
    can_b = items.groupby("main_ocid")["classification_id"].nunique()
    # Canasta C: entidad -> conjunto de codigos de item comprados en el anio
    it_buyer = items.merge(main[["ocid", "buyer_name"]], left_on="main_ocid",
                           right_on="ocid", how="left")
    can_c = it_buyer.groupby("buyer_name")["classification_id"].nunique()

    rep["canastas"] = {
        "A_proceso_postores": {
            "n_canastas": int(len(can_a)),
            "items_promedio": round(float(can_a.mean()), 2),
            "mediana": int(can_a.median()),
            "p90": int(can_a.quantile(0.90)),
            "max": int(can_a.max()),
            "con_2_o_mas_pct": pct((can_a >= 2).sum(), len(can_a)),
        },
        "B_proceso_codigos_item": {
            "n_canastas": int(len(can_b)),
            "items_promedio": round(float(can_b.mean()), 2),
            "con_2_o_mas_pct": pct((can_b >= 2).sum(), len(can_b)),
        },
        "C_entidad_codigos_item": {
            "n_canastas": int(len(can_c)),
            "items_promedio": round(float(can_c.mean()), 2),
            "mediana": int(can_c.median()),
            "max": int(can_c.max()),
            "con_2_o_mas_pct": pct((can_c >= 2).sum(), len(can_c)),
        },
    }

    # --------------- criterio 2b: entidades como conjuntos (para MinHash/LSH)
    prov = tenderers.groupby("id")["main_ocid"].nunique()
    rep["proveedores_como_conjuntos"] = {
        "n_proveedores": int(len(prov)),
        "procesos_promedio_por_proveedor": round(float(prov.mean()), 2),
        "mediana": int(prov.median()),
        "p95": int(prov.quantile(0.95)),
        "max": int(prov.max()),
        "con_5_o_mas_procesos": int((prov >= 5).sum()),
        "con_5_o_mas_pct": pct((prov >= 5).sum(), len(prov)),
    }

    # ------------------------------------------------- cobertura territorial
    if "address_department" in parties.columns:
        dep = parties["address_department"].dropna()
        rep["territorial"] = {
            "cobertura_departamento_pct": pct(len(dep), len(parties)),
            "departamentos_distintos": int(dep.nunique()),
            "top_departamentos": top(dep, 10),
        }
    rep["roles_parties"] = top(parties["roles"], 8)

    return rep


def main_cli():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    base = Path(sys.argv[1])
    rep = perfilar(base)
    txt = json.dumps(rep, indent=2, ensure_ascii=False)
    print(txt)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(txt, encoding="utf8")


if __name__ == "__main__":
    main_cli()
