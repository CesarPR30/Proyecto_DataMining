# -*- coding: utf-8 -*-
"""
Verificacion del Parquet generado por la ingesta.

Comprueba tres cosas que el conteo de filas por si solo no garantiza:
  1. Que los conteos coinciden con los que declara el publicador (OCP Data
     Registry), no solo con los CSV descargados.
  2. Que la particion por anio es util: distribucion de filas y volumen de la
     particion anio=0 (registros sin fecha valida).
  3. Que los tipos quedaron bien casteados y que la poda de particiones
     funciona, midiendo una consulta acotada por anio contra una sin acotar.

Uso:  python scripts/06_verificar_ingesta.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno

entorno.configurar()

from pyspark.sql import functions as F  # noqa: E402

PARQUET = entorno.DERIVADOS / "parquet"

# Conteos publicados por el OCP Data Registry para la publicacion 135 (Peru).
# Sirven como control externo: si cuadran, el corpus local esta completo.
DECLARADO = {
    "main": 2_753_905,                  # contracting processes / tenders
    "tender_tenderers": 10_011_706,
    "tender_items": 5_138_329,
    "parties": 12_765_637,
    "awards": 2_011_059,
    "awards_items": 2_953_782,
    "awards_suppliers": 2_001_831,
    "contracts": 1_320_800,
    "contracts_items": 1_606_559,
}


def main():
    spark = entorno.crear_spark("verificar-ingesta", memoria="8g")

    print("1. Conteos frente a lo declarado por el publicador")
    print("-" * 62)
    todo_ok = True
    for tabla, esperado in DECLARADO.items():
        n = spark.read.parquet(str(PARQUET / tabla)).count()
        ok = n == esperado
        todo_ok &= ok
        print(f"  [{'OK ' if ok else 'DIF'}] {tabla:<38} {n:>12,}"
              + ("" if ok else f"  (declarado {esperado:,})"))

    print("\n2. Particionado por anio (tabla main)")
    print("-" * 62)
    m = spark.read.parquet(str(PARQUET / "main"))
    por_anio = (m.groupBy("anio").count().orderBy("anio")).collect()
    sin_fecha = next((r["count"] for r in por_anio if r["anio"] == 0), 0)
    print(f"  particiones: {len(por_anio)}  |  filas sin fecha valida "
          f"(anio=0): {sin_fecha}")
    cuerpo = [r for r in por_anio if r["anio"] != 0]
    print(f"  rango: {cuerpo[0]['anio']} - {cuerpo[-1]['anio']}")
    for r in cuerpo[-6:]:
        print(f"    {r['anio']}: {r['count']:>9,}")

    print("\n3. Tipos y calidad del casteo")
    print("-" * 62)
    tipos = dict(m.dtypes)
    for c in ["fecha", "monto_pen", "tender_numberOfTenderers", "anio"]:
        print(f"  {c:<28} {tipos.get(c)}")
    stats = m.select(
        F.count(F.when(F.col("fecha").isNull(), 1)).alias("fecha_nula"),
        F.count(F.when(F.col("monto_pen").isNull(), 1)).alias("monto_nulo"),
        F.round(F.sum("monto_pen") / 1e9, 1).alias("monto_total_mm"),
        F.min("fecha").alias("desde"), F.max("fecha").alias("hasta"),
    ).first()
    print(f"  fechas nulas: {stats['fecha_nula']:,}  |  montos nulos: "
          f"{stats['monto_nulo']:,}")
    print(f"  rango real  : {stats['desde']} .. {stats['hasta']}")
    print(f"  monto convocado acumulado: S/ {stats['monto_total_mm']:,} mil millones")

    print("\n4. Poda de particiones (mismo agregado, con y sin filtro de anio)")
    print("-" * 62)
    for etiqueta, df in (("todo el corpus", m),
                         ("solo 2025", m.where(F.col("anio") == 2025))):
        t0 = time.time()
        r = df.agg(F.count("*").alias("n"),
                   F.round(F.avg("monto_pen"), 0).alias("monto_medio")).first()
        print(f"  {etiqueta:<16} {r['n']:>10,} filas  "
              f"monto medio S/ {r['monto_medio']:>12,.0f}  "
              f"{time.time() - t0:.2f} s")

    print("\n5. Propagacion del anio a las tablas hijas")
    print("-" * 62)
    for tabla in ["tender_tenderers", "parties", "awards_suppliers"]:
        d = spark.read.parquet(str(PARQUET / tabla))
        huerfanas = d.where(F.col("anio") == 0).count()
        print(f"  {tabla:<20} filas sin anio resuelto: {huerfanas:,}")

    print("\n" + ("VERIFICACION SUPERADA" if todo_ok
                  else "HAY DIFERENCIAS - revisar arriba"))
    spark.stop()
    return 0 if todo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
