# -*- coding: utf-8 -*-
"""
Ingesta del corpus OCDS-OECE: de 498 CSV crudos a Parquet particionado.

Que hace y por que:

1. Lee cada tabla PARTICION POR PARTICION y las une con unionByName. No se
   puede leer con un unico glob porque los encabezados cambian entre anios
   (verificado: main.csv tiene 5 esquemas distintos entre 2003 y 2026); un
   lector unico inferiria el esquema del primer archivo y desalinearia las
   columnas del resto en silencio.
2. Castea las columnas de fecha e importe que el proyecto usa; el resto queda
   como texto.
3. Deriva el anio y el mes de tender_datePublished y reparticiona por anio.
   El anio del ARCHIVO no es el anio de publicacion del proceso, asi que la
   particion fisica original no sirve para podar por fecha.
4. Propaga ese anio a las tablas hijas mediante un join por main_ocid, para
   que toda consulta por periodo pode particiones en cualquier tabla.
5. Verifica que el numero de filas escritas coincide con las lineas de los CSV
   de origen y deja un manifiesto JSON con los conteos.

Uso:
    python scripts/05_ingesta_parquet.py            # todas las tablas
    python scripts/05_ingesta_parquet.py main       # solo algunas
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno

entorno.configurar()

from pyspark.sql import DataFrame, functions as F  # noqa: E402
from pyspark.sql.window import Window  # noqa: E402

DESTINO = entorno.DERIVADOS / "parquet"

# Columnas a castear por tabla. Las que no aparecen quedan como string.
# Solo se castea lo que realmente se usa: castear de mas cuesta tiempo y
# esconde errores de calidad detras de un null.
CAST = {
    "main": {
        "timestamp": ["date", "publishedDate", "tender_datePublished",
                      "tender_tenderPeriod_startDate", "tender_tenderPeriod_endDate",
                      "tender_enquiryPeriod_startDate", "tender_enquiryPeriod_endDate"],
        "double": ["tender_value_amount", "tender_value_amount_PEN",
                   "planning_budget_amount_amount"],
        "int": ["tender_numberOfTenderers", "tender_enquiryPeriod_durationInDays"],
    },
    "tender_items": {"double": ["quantity", "totalValue_amount"]},
    "awards": {"timestamp": ["date"], "double": ["value_amount"]},
    "awards_items": {"double": ["quantity", "totalValue_amount"]},
    "contracts": {
        "timestamp": ["dateSigned", "period_startDate", "period_endDate",
                      "implementation_endDate"],
        "double": ["value_amount", "implementation_finalValue_amount"],
        "int": ["period_durationInDays"],
    },
    "contracts_items": {"double": ["quantity", "totalValue_amount"]},
}

# Tablas que se convierten. Se omiten a proposito:
#   *_documents        -> 80 MB/anio de URLs de adjuntos, sin uso en el proyecto
#   sources            -> constante (siempre SEACE v3)
#   *_exchangeRates    -> tipo de cambio de los pocos procesos en moneda extranjera
TABLAS = [
    "main",
    "tender_tenderers",
    "tender_items",
    "tender_items_additionalClassifications",
    "parties",
    "parties_additionalIdentifiers",
    "awards",
    "awards_items",
    "awards_items_additionalClassifications",
    "awards_suppliers",
    "contracts",
    "contracts_items",
]


def lineas_de_datos(rutas):
    """Filas reales de un conjunto de CSV: lineas fisicas menos el encabezado.

    Es valido porque se verifico que estos archivos no traen saltos de linea
    dentro de los campos; sirve como conteo de control independiente de Spark.
    """
    total = 0
    for r in rutas:
        with open(r, "rb") as fh:
            n = sum(c.count(b"\n") for c in iter(lambda: fh.read(1 << 22), b""))
        total += max(n - 1, 0)          # -1 por el encabezado
    return total


def leer_tabla(spark, tabla):
    """Une las particiones anuales respetando los cambios de esquema."""
    rutas = sorted(entorno.DATOS.glob(f"[0-9][0-9][0-9][0-9]/{tabla}.csv"))
    if not rutas:
        return None, []
    partes = []
    for r in rutas:
        df = (spark.read
              .option("header", True)
              .option("multiLine", False)   # verificado: sin saltos internos
              .option("quote", '"')
              .option("escape", '"')
              .option("mode", "PERMISSIVE")
              .csv(str(r)))
        partes.append(df.withColumn("particion_origen", F.lit(r.parent.name)))
    df = partes[0]
    for otra in partes[1:]:
        df = df.unionByName(otra, allowMissingColumns=True)
    return df, rutas


def castear(df: DataFrame, tabla: str) -> DataFrame:
    for tipo, columnas in CAST.get(tabla, {}).items():
        for c in columnas:
            if c in df.columns:
                df = df.withColumn(c, F.col(c).cast(tipo))
    return df


def escribir(df: DataFrame, tabla: str, particiones=1):
    destino = DESTINO / tabla
    (df.repartition(F.col("anio"))
       .write.mode("overwrite")
       .option("compression", "snappy")
       .partitionBy("anio")
       .parquet(str(destino)))
    return destino


def ingestar_main(spark, reporte):
    print("\n>>> main")
    t0 = time.time()
    df, rutas = leer_tabla(spark, "main")
    esperado = lineas_de_datos(rutas)
    df = castear(df, "main")

    df = (df
          .withColumn("fecha", F.col("tender_datePublished"))
          .withColumn("anio", F.coalesce(F.year("fecha"), F.lit(0)))
          .withColumn("mes", F.coalesce(F.month("fecha"), F.lit(0)))
          .withColumn("monto_pen", F.col("tender_value_amount_PEN")))

    # Salvaguarda: quedarse con la version mas reciente de cada proceso.
    # Se verifico que no hay OCID repetidos entre particiones, de modo que
    # esto no deberia eliminar nada; se deja por si una recarga futura los trae.
    ventana = Window.partitionBy("ocid").orderBy(F.col("date").desc_nulls_last())
    df = (df.withColumn("_rn", F.row_number().over(ventana))
            .where(F.col("_rn") == 1).drop("_rn"))

    destino = escribir(df, "main")
    escrito = spark.read.parquet(str(destino)).count()
    reporte["main"] = {
        "archivos_csv": len(rutas), "filas_csv": esperado,
        "filas_parquet": escrito, "duplicados_eliminados": esperado - escrito,
        "segundos": round(time.time() - t0, 1),
        "mb": round(sum(f.stat().st_size for f in destino.rglob("*.parquet"))
                    / 1024 ** 2, 1),
    }
    print(f"    CSV {esperado:,} -> Parquet {escrito:,}  "
          f"({reporte['main']['mb']} MB, {reporte['main']['segundos']} s)")
    return destino


def ingestar_hija(spark, tabla, mapa, reporte):
    print(f"\n>>> {tabla}")
    t0 = time.time()
    df, rutas = leer_tabla(spark, tabla)
    if df is None:
        print("    sin archivos, se omite")
        return
    esperado = lineas_de_datos(rutas)
    df = castear(df, tabla)

    # El anio de publicacion vive en main; se propaga para poder podar por fecha
    df = (df.join(F.broadcast(mapa), df["main_ocid"] == mapa["ocid"], "left")
            .drop(mapa["ocid"])
            .withColumn("anio", F.coalesce(F.col("anio"), F.lit(0))))

    destino = escribir(df, tabla)
    escrito = spark.read.parquet(str(destino)).count()
    reporte[tabla] = {
        "archivos_csv": len(rutas), "filas_csv": esperado,
        "filas_parquet": escrito, "diferencia": escrito - esperado,
        "segundos": round(time.time() - t0, 1),
        "mb": round(sum(f.stat().st_size for f in destino.rglob("*.parquet"))
                    / 1024 ** 2, 1),
    }
    marca = "OK" if escrito == esperado else "REVISAR"
    print(f"    [{marca}] CSV {esperado:,} -> Parquet {escrito:,}  "
          f"({reporte[tabla]['mb']} MB, {reporte[tabla]['segundos']} s)")


def main():
    pedidas = sys.argv[1:] or TABLAS
    DESTINO.mkdir(parents=True, exist_ok=True)

    spark = entorno.crear_spark("ingesta-parquet", memoria="8g",
                                particiones=64, verbose=True)
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", str(384 * 1024 ** 2))
    print(f"destino: {DESTINO}")

    reporte = {}
    t0 = time.time()

    if "main" in pedidas:
        ingestar_main(spark, reporte)

    mapa = (spark.read.parquet(str(DESTINO / "main"))
            .select("ocid", "anio").cache())
    print(f"\nmapa ocid -> anio: {mapa.count():,} procesos")

    for tabla in pedidas:
        if tabla != "main":
            ingestar_hija(spark, tabla, mapa, reporte)

    total_mb = sum(v["mb"] for v in reporte.values())
    total_filas = sum(v["filas_parquet"] for v in reporte.values())
    print("\n" + "=" * 70)
    print(f"INGESTA COMPLETA: {len(reporte)} tablas, {total_filas:,} filas, "
          f"{total_mb / 1024:.2f} GB en Parquet, "
          f"{(time.time() - t0) / 60:.1f} min")
    fallas = [t for t, v in reporte.items() if v.get("diferencia", 0) != 0]
    print("tablas con diferencia de conteo:", fallas or "ninguna")

    manifiesto = entorno.DERIVADOS / "manifiesto_ingesta.json"
    manifiesto.write_text(json.dumps(reporte, indent=2, ensure_ascii=False),
                          encoding="utf8")
    print(f"manifiesto: {manifiesto}")
    spark.stop()


if __name__ == "__main__":
    main()
