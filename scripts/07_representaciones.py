# -*- coding: utf-8 -*-
"""
Construye y persiste las representaciones reutilizables del corpus.

El enunciado recomienda reutilizar entre las Partes II, III y V la
representacion construida en la Parte I. Este script la materializa una sola
vez sobre el Parquet ya ingestado, de modo que las partes siguientes no
vuelvan a recorrer los 46 millones de filas crudas.

Salidas (en derivados/parquet/):

  repr_proceso              ocid -> texto normalizado, tokens y shingles de 5
                            caracteres. Alimenta Jaccard/MinHash/LSH (Parte II)
                            y la vectorizacion TF-IDF (Parte III).

  repr_proveedor            RUC -> conjunto de procesos a los que postulo.
                            Es la representacion de entidad como conjunto: dos
                            proveedores con Jaccard alto postulan a lo mismo.

  canasta_proceso_postores  proceso -> conjunto de postores. Canasta principal
                            de la Parte V (11,9 items de promedio).

  canasta_entidad_cubso     entidad-anio -> conjunto de codigos CUBSO comprados.
                            Canasta secundaria de la Parte V.

Decision de diseno: los shingles se persisten como array<string> y no como
hash. Medido sobre 2025, ocupan 1,7 GB proyectados al corpus completo gracias
a la codificacion por diccionario de Parquet, y mantenerlos legibles permite
inspeccionar los pares similares que encuentre LSH.

Uso:  python scripts/07_representaciones.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno

entorno.configurar()

from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.window import Window  # noqa: E402

PARQUET = entorno.DERIVADOS / "parquet"
K_SHINGLE = 5          # k-shingles de caracteres, como en la sesion 03

# Acentos -> sin acento, para que el shingling no dependa de la tildacion
CON_TILDE = "ÁÉÍÓÚÜÑáéíóúüñ"
SIN_TILDE = "AEIOUUNAEIOUUN"


def normalizar(*columnas):
    """Texto en mayusculas, sin tildes ni puntuacion y con espacios colapsados."""
    crudo = F.concat_ws(" ", *[F.coalesce(F.col(c), F.lit("")) for c in columnas])
    sin_tildes = F.translate(F.upper(crudo), CON_TILDE, SIN_TILDE)
    solo_alfanum = F.regexp_replace(sin_tildes, r"[^A-Z0-9 ]", " ")
    return F.trim(F.regexp_replace(solo_alfanum, r"\s+", " "))


def shingles(columna, k=K_SHINGLE):
    """Conjunto de k-shingles de caracteres.

    El guardia sobre la longitud es necesario: sequence(0, n) con n negativo
    invierte el paso en Spark y devolveria subcadenas sin sentido para los
    textos mas cortos que k.
    """
    expr = F.expr(
        f"transform(sequence(0, length({columna}) - {k}), "
        f"i -> substring({columna}, i + 1, {k}))")
    return F.when(F.length(columna) >= k, F.array_distinct(expr)) \
            .otherwise(F.array(F.col(columna)))


def guardar(df, nombre, particionar=True, reporte=None, t0=None):
    destino = PARQUET / nombre
    if particionar:
        # una sola salida por anio en lugar de un archivo por tarea
        df = df.repartition(F.col("anio"))
    escritor = df.write.mode("overwrite").option("compression", "snappy")
    if particionar:
        escritor = escritor.partitionBy("anio")
    escritor.parquet(str(destino))
    n = df.sparkSession.read.parquet(str(destino)).count()
    mb = sum(f.stat().st_size for f in destino.rglob("*.parquet")) / 1024 ** 2
    if reporte is not None:
        reporte[nombre] = {"filas": n, "mb": round(mb, 1),
                           "segundos": round(time.time() - t0, 1)}
    print(f"    {n:,} filas  ({mb:,.0f} MB, {time.time() - t0:.1f} s)")
    return destino


def main():
    spark = entorno.crear_spark("representaciones", memoria="8g",
                                particiones=64, verbose=True)
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", str(384 * 1024 ** 2))
    reporte = {}

    main_df = spark.read.parquet(str(PARQUET / "main"))
    postores = spark.read.parquet(str(PARQUET / "tender_tenderers"))
    items = spark.read.parquet(str(PARQUET / "tender_items"))

    # ------------------------------------------------ 1. proceso -> texto
    print("\n>>> repr_proceso (texto, tokens y shingles por proceso)")
    t0 = time.time()
    proc = (main_df
            .select("ocid", "anio", "mes", "buyer_name", "monto_pen",
                    F.col("tender_mainProcurementCategory").alias("categoria"),
                    F.col("tender_procurementMethodDetails").alias("metodo"),
                    "tender_title", "tender_description")
            .withColumn("texto", normalizar("tender_title", "tender_description"))
            .drop("tender_title", "tender_description"))
    proc = (proc
            .withColumn("tokens", F.split(F.col("texto"), " "))
            .withColumn("shingles", shingles("texto"))
            .withColumn("n_tokens", F.size("tokens"))
            .withColumn("n_shingles", F.size("shingles")))
    guardar(proc, "repr_proceso", reporte=reporte, t0=t0)

    # -------------------------------------- 2. proveedor -> conjunto de procesos
    print("\n>>> repr_proveedor (RUC -> conjunto de procesos)")
    t0 = time.time()
    anios = main_df.select("ocid", "anio")
    post = (postores.select(F.col("id").alias("ruc"), "name", "main_ocid")
            .where(F.col("ruc").isNotNull())
            .join(F.broadcast(anios), F.col("main_ocid") == F.col("ocid"), "left")
            .drop("ocid"))
    # El nombre del proveedor varia entre registros; se toma el mas frecuente
    ventana_nombre = Window.partitionBy("ruc").orderBy(F.desc("count"))
    nombre_frecuente = (post.groupBy("ruc", "name").count()
                        .withColumn("rk", F.row_number().over(ventana_nombre))
                        .where(F.col("rk") == 1).select("ruc", "name"))
    prov = (post.groupBy("ruc").agg(
                F.array_distinct(F.collect_list("main_ocid")).alias("procesos"),
                F.min("anio").alias("primer_anio"),
                F.max("anio").alias("ultimo_anio"))
            .withColumn("n_procesos", F.size("procesos"))
            .join(F.broadcast(nombre_frecuente), "ruc", "left"))
    guardar(prov, "repr_proveedor", particionar=False, reporte=reporte, t0=t0)

    # ------------------------------- 3. canasta principal: proceso -> postores
    print("\n>>> canasta_proceso_postores (canasta principal, Parte V)")
    t0 = time.time()
    canasta = (postores
               .select("main_ocid", F.col("id").alias("ruc"), "anio")
               .where(F.col("ruc").isNotNull())
               .groupBy("main_ocid", "anio")
               .agg(F.array_distinct(F.collect_list("ruc")).alias("postores"))
               .withColumn("n_postores", F.size("postores"))
               .withColumnRenamed("main_ocid", "ocid"))
    guardar(canasta, "canasta_proceso_postores", reporte=reporte, t0=t0)

    # ----------------------------- 4. canasta secundaria: entidad -> CUBSO
    print("\n>>> canasta_entidad_cubso (canasta secundaria, Parte V)")
    t0 = time.time()
    it = (items.select("main_ocid", "anio",
                       F.col("classification_id").alias("cubso"),
                       F.col("classification_description").alias("cubso_desc"))
          .where(F.col("cubso").isNotNull())
          .join(main_df.select(F.col("ocid"), "buyer_name"),
                F.col("main_ocid") == F.col("ocid"), "left"))
    canasta_c = (it.where(F.col("buyer_name").isNotNull())
                 .groupBy("buyer_name", "anio")
                 .agg(F.array_distinct(F.collect_list("cubso")).alias("codigos"))
                 .withColumn("n_codigos", F.size("codigos")))
    guardar(canasta_c, "canasta_entidad_cubso", reporte=reporte, t0=t0)

    # ------------------------------------------------------------ diagnostico
    print("\n>>> diagnostico de las representaciones")
    print("-" * 62)
    r = spark.read.parquet(str(PARQUET / "repr_proceso"))
    s = r.select(F.avg("n_shingles").alias("sh"), F.avg("n_tokens").alias("tk"),
                 F.min("n_shingles").alias("sh_min"),
                 F.max("n_shingles").alias("sh_max")).first()
    print(f"  shingles por proceso : media {s['sh']:.0f}  "
          f"min {s['sh_min']}  max {s['sh_max']}")
    print(f"  tokens por proceso   : media {s['tk']:.1f}")

    pv = spark.read.parquet(str(PARQUET / "repr_proveedor"))
    q = pv.select(F.count("*").alias("n"), F.avg("n_procesos").alias("m"),
                  F.max("n_procesos").alias("mx"),
                  F.count(F.when(F.col("n_procesos") >= 10, 1)).alias("d10")).first()
    print(f"  proveedores          : {q['n']:,}  media {q['m']:.1f} procesos  "
          f"max {q['mx']:,}  con >=10: {q['d10']:,}")

    cb = spark.read.parquet(str(PARQUET / "canasta_proceso_postores"))
    c = cb.select(F.count("*").alias("n"), F.avg("n_postores").alias("m"),
                  F.count(F.when(F.col("n_postores") >= 2, 1)).alias("d2")).first()
    print(f"  canastas de postores : {c['n']:,}  media {c['m']:.2f} items  "
          f"con >=2: {c['d2']:,} ({100*c['d2']/c['n']:.1f} %)")

    cc = spark.read.parquet(str(PARQUET / "canasta_entidad_cubso"))
    e = cc.select(F.count("*").alias("n"), F.avg("n_codigos").alias("m")).first()
    print(f"  canastas entidad-anio: {e['n']:,}  media {e['m']:.1f} codigos")

    total_mb = sum(v["mb"] for v in reporte.values())
    print(f"\nTOTAL representaciones: {total_mb / 1024:.2f} GB")
    destino = entorno.DERIVADOS / "manifiesto_representaciones.json"
    destino.write_text(json.dumps(reporte, indent=2, ensure_ascii=False),
                       encoding="utf8")
    print(f"manifiesto: {destino}")
    spark.stop()


if __name__ == "__main__":
    main()
