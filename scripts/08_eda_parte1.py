# -*- coding: utf-8 -*-
"""
Parte I: EDA sobre Spark y comparacion MapReduce (RDD) vs DataFrames/Spark SQL.

Cubre los minimos que pide el enunciado para la Parte I:
  - distribucion temporal,
  - distribucion de variables categoricas y de montos,
  - frecuencia de las entidades y categorias principales,
  - dos operaciones de agregacion relevantes implementadas en los DOS estilos,
    con medicion de tiempo,
  - efecto del particionado sobre el plan de ejecucion.

Todo el calculo pesado corre en Spark y se exporta como artefactos ligeros
(CSV y JSON) en derivados/artefactos/, siguiendo la arquitectura "calcular una
vez, explorar muchas" que pide el reporte web.

Uso:  python scripts/08_eda_parte1.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno

entorno.configurar()

from pyspark.sql import functions as F  # noqa: E402

PARQUET = entorno.DERIVADOS / "parquet"
ARTEFACTOS = entorno.DERIVADOS / "artefactos"

# El monto normalizado a soles solo existe desde 2015 (ver seccion 10 del
# informe). Todo analisis monetario de serie larga se acota a este periodo.
ANIO_MONTO_DESDE = 2015


def exportar(df, nombre, orden=None):
    """Guarda un agregado como CSV unico, legible por la pagina web."""
    ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    if orden:
        df = df.orderBy(*orden)
    pdf = df.toPandas()
    destino = ARTEFACTOS / f"{nombre}.csv"
    pdf.to_csv(destino, index=False, encoding="utf8")
    print(f"    -> {nombre}.csv ({len(pdf):,} filas)")
    return pdf


def titulo(t):
    print(f"\n{t}\n" + "=" * len(t))


# --------------------------------------------------------------------- EDA
def eda_temporal(m):
    titulo("1. Distribucion temporal")
    mensual = (m.where(F.col("anio") > 0)
               .groupBy("anio", "mes")
               .agg(F.count("*").alias("procesos"),
                    F.sum(F.when(F.col("anio") >= ANIO_MONTO_DESDE,
                                 F.col("monto_pen"))).alias("monto_pen"))
               .withColumn("periodo",
                           F.concat_ws("-", F.col("anio"),
                                       F.lpad(F.col("mes"), 2, "0"))))
    pdf = exportar(mensual, "eda_temporal_mensual", orden=["anio", "mes"])
    pico = pdf.loc[pdf["procesos"].idxmax()]
    print(f"    pico mensual: {int(pico['procesos']):,} en {pico['periodo']}")
    por_anio = pdf.groupby("anio")["procesos"].sum()
    print(f"    ano mas activo: {por_anio.idxmax()} con {por_anio.max():,} procesos")
    # estacionalidad: cuanto cae enero respecto del promedio del ano
    enero = pdf[pdf["mes"] == 1]["procesos"].mean()
    resto = pdf[pdf["mes"] != 1]["procesos"].mean()
    print(f"    enero promedia {enero:,.0f} procesos frente a {resto:,.0f} del "
          f"resto de meses ({100*(1-enero/resto):.0f} % menos)")


def eda_categorias(m):
    titulo("2. Variables categoricas")
    cat = (m.where(F.col("anio") > 0)
           .groupBy("anio", "categoria").agg(F.count("*").alias("procesos")))
    exportar(cat, "eda_categoria_por_anio", orden=["anio", "categoria"])

    met = (m.where(F.col("anio") >= ANIO_MONTO_DESDE)
           .groupBy("metodo")
           .agg(F.count("*").alias("procesos"),
                F.round(F.sum("monto_pen") / 1e9, 2).alias("monto_mil_millones"),
                F.round(F.avg("monto_pen"), 0).alias("monto_medio")))
    pdf = exportar(met, "eda_metodo", orden=[F.desc("procesos")])
    print("    metodos mas usados (2015-2026):")
    for _, r in pdf.head(5).iterrows():
        print(f"      {str(r['metodo'])[:34]:34} {int(r['procesos']):>8,} procesos"
              f"  S/ {r['monto_mil_millones']:>7,.2f} mil millones")


def eda_montos(m):
    titulo("3. Distribucion de montos (2015-2026)")
    mm = m.where((F.col("anio") >= ANIO_MONTO_DESDE) & (F.col("monto_pen") > 0))
    total = mm.count()
    q = mm.approxQuantile("monto_pen", [0.25, 0.5, 0.75, 0.9, 0.99], 0.001)
    resumen = mm.select(
        F.count("*").alias("n"), F.round(F.avg("monto_pen"), 2).alias("media"),
        F.round(F.sum("monto_pen") / 1e9, 1).alias("total_mil_millones"),
        F.round(F.max("monto_pen"), 2).alias("maximo")).first()
    print(f"    procesos con monto > 0 : {total:,}")
    print(f"    mediana S/ {q[1]:,.0f}   p75 S/ {q[2]:,.0f}   "
          f"p90 S/ {q[3]:,.0f}   p99 S/ {q[4]:,.0f}")
    print(f"    media   S/ {resumen['media']:,.0f}   maximo S/ {resumen['maximo']:,.0f}")
    print(f"    total convocado: S/ {resumen['total_mil_millones']:,} mil millones")

    # histograma en escala logaritmica: los montos abarcan 9 ordenes de magnitud
    hist = (mm.withColumn("log10", F.floor(F.log10("monto_pen")))
            .groupBy("log10").agg(F.count("*").alias("procesos"),
                                  F.round(F.sum("monto_pen") / 1e9, 3)
                                  .alias("monto_mil_millones")))
    exportar(hist, "eda_montos_histograma_log", orden=["log10"])

    no_positivos = m.where((F.col("anio") >= ANIO_MONTO_DESDE)
                           & (F.col("monto_pen") <= 0)).count()
    print(f"    montos no positivos excluidos: {no_positivos:,} "
          f"({100*no_positivos/(total+no_positivos):.1f} %)")


def eda_entidades(m):
    titulo("4. Entidades compradoras")
    ent = (m.where(F.col("anio") >= ANIO_MONTO_DESDE)
           .groupBy("buyer_name")
           .agg(F.count("*").alias("procesos"),
                F.round(F.sum("monto_pen") / 1e6, 1).alias("monto_millones"))
           .where(F.col("buyer_name").isNotNull()))
    pdf = exportar(ent, "eda_entidades", orden=[F.desc("monto_millones")])
    print(f"    entidades distintas: {len(pdf):,}")
    print("    top 5 por monto convocado (2015-2026):")
    for _, r in pdf.head(5).iterrows():
        print(f"      {str(r['buyer_name'])[:46]:46} S/ {r['monto_millones']:>10,.0f} M"
              f"  ({int(r['procesos']):,} procesos)")
    # concentracion
    orden = pdf.sort_values("monto_millones", ascending=False)
    acum = orden["monto_millones"].cumsum() / orden["monto_millones"].sum() * 100
    for pcte in (1, 5, 10):
        i = max(int(len(orden) * pcte / 100) - 1, 0)
        print(f"    el {pcte:>2} % de las entidades concentra "
              f"{acum.iloc[i]:.1f} % del monto")


def eda_postores(spark):
    titulo("5. Competencia: postores por proceso")
    canasta = spark.read.parquet(str(PARQUET / "canasta_proceso_postores"))
    dist = (canasta.groupBy("n_postores").agg(F.count("*").alias("procesos")))
    exportar(dist, "eda_postores_distribucion", orden=["n_postores"])
    r = canasta.select(F.count("*").alias("n"),
                       F.avg("n_postores").alias("media"),
                       F.count(F.when(F.col("n_postores") == 1, 1)).alias("unico"),
                       F.count(F.when(F.col("n_postores") >= 2, 1)).alias("dos_mas")
                       ).first()
    print(f"    procesos con postores registrados: {r['n']:,}")
    print(f"    media de postores: {r['media']:.2f}")
    print(f"    con un unico postor: {r['unico']:,} ({100*r['unico']/r['n']:.1f} %)")
    print(f"    con dos o mas     : {r['dos_mas']:,} "
          f"({100*r['dos_mas']/r['n']:.1f} %)")

    por_anio = (canasta.where(F.col("anio") > 0).groupBy("anio")
                .agg(F.count("*").alias("procesos"),
                     F.round(F.avg("n_postores"), 2).alias("postores_medio"),
                     F.round(100 * F.count(F.when(F.col("n_postores") == 1, 1))
                             / F.count("*"), 1).alias("pct_postor_unico")))
    exportar(por_anio, "eda_postores_por_anio", orden=["anio"])


# ------------------------------------- Agregaciones: RDD vs DataFrame/SQL
def comparar_estilos(spark, m):
    titulo("6. Misma agregacion en MapReduce (RDD) y en DataFrame/Spark SQL")
    base = (m.where((F.col("anio") >= ANIO_MONTO_DESDE)
                    & (F.col("monto_pen") > 0)
                    & F.col("buyer_name").isNotNull())
            .select("buyer_name", "monto_pen", "anio", "categoria"))
    base.cache()
    n = base.count()          # materializa la cache: la comparacion mide solo
    print(f"    filas en memoria: {n:,}")   # el costo de la agregacion

    resultados = []

    def cronometrar(etiqueta, fn, repeticiones=3):
        tiempos = []
        for _ in range(repeticiones):
            t0 = time.time()
            salida = fn()
            tiempos.append(time.time() - t0)
        mejor = min(tiempos)
        resultados.append({"operacion": etiqueta, "segundos": round(mejor, 3)})
        print(f"    {etiqueta:<52} {mejor:6.3f} s")
        return salida

    # --- Agregacion A: monto total por entidad -------------------------------
    print("\n  A. Monto total convocado por entidad")

    def a_rdd():
        return (base.rdd
                .map(lambda f: (f["buyer_name"], f["monto_pen"]))   # map
                .reduceByKey(lambda x, y: x + y)                    # reduce
                .takeOrdered(10, key=lambda kv: -kv[1]))

    def a_df():
        return (base.groupBy("buyer_name")
                .agg(F.sum("monto_pen").alias("monto"))
                .orderBy(F.desc("monto")).limit(10).collect())

    base.createOrReplaceTempView("procesos")

    def a_sql():
        return spark.sql("""
            SELECT buyer_name, SUM(monto_pen) AS monto
            FROM procesos GROUP BY buyer_name
            ORDER BY monto DESC LIMIT 10""").collect()

    top_rdd = cronometrar("A - RDD (map + reduceByKey)", a_rdd)
    top_df = cronometrar("A - DataFrame (groupBy + sum)", a_df)
    cronometrar("A - Spark SQL (GROUP BY)", a_sql)

    # los tres caminos deben dar lo mismo: es la comprobacion de equivalencia
    iguales = abs(top_rdd[0][1] - top_df[0]["monto"]) < 1.0
    print(f"    los tres estilos coinciden en el top 1: {iguales}")
    print(f"      {top_rdd[0][0][:50]}  S/ {top_rdd[0][1]/1e6:,.0f} M")

    # --- Agregacion B: procesos y monto medio por anio y categoria -----------
    print("\n  B. Procesos y monto medio por anio y categoria")

    def b_rdd():
        return (base.rdd
                .map(lambda f: ((f["anio"], f["categoria"]), (1, f["monto_pen"])))
                .reduceByKey(lambda x, y: (x[0] + y[0], x[1] + y[1]))
                .mapValues(lambda v: (v[0], v[1] / v[0]))
                .collect())

    def b_df():
        return (base.groupBy("anio", "categoria")
                .agg(F.count("*").alias("n"), F.avg("monto_pen").alias("medio"))
                .collect())

    cronometrar("B - RDD (map + reduceByKey + mapValues)", b_rdd)
    salida_b = cronometrar("B - DataFrame (groupBy + count/avg)", b_df)

    exportar(spark.createDataFrame(salida_b), "eda_anio_categoria",
             orden=["anio", "categoria"])

    (ARTEFACTOS / "eda_tiempos_rdd_vs_df.json").write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf8")
    print(f"\n    -> eda_tiempos_rdd_vs_df.json")
    base.unpersist()
    return resultados


# ------------------------------------------------- Particionado y plan
def explicar_particionado(spark, m):
    titulo("7. Particionado y plan de ejecucion")
    ruta = PARQUET / "main"
    archivos = list(ruta.rglob("*.parquet"))
    particiones = sorted(d.name for d in ruta.iterdir() if d.is_dir())
    print(f"    el dataset esta particionado por anio: {len(particiones)} "
          f"directorios, {len(archivos)} archivos Parquet")
    print(f"    ejemplo: {particiones[-3:]}")

    sin_filtro = m.groupBy("categoria").count()
    con_filtro = m.where(F.col("anio") == 2025).groupBy("categoria").count()

    def archivos_leidos(df):
        plan = df._jdf.queryExecution().executedPlan().toString()
        for linea in plan.split("\n"):
            if "PartitionFilters" in linea or "number of files" in linea:
                return linea.strip()[:150]
        return "(no disponible)"

    for etiqueta, df in (("sin filtro de anio", sin_filtro),
                         ("con filtro anio = 2025", con_filtro)):
        t0 = time.time()
        df.collect()
        print(f"    {etiqueta:<26} {time.time() - t0:5.2f} s")

    print("\n    filtros de particion que Spark empuja al lector de archivos:")
    print("      " + archivos_leidos(con_filtro))
    print("\n    Lectura: al filtrar por anio, Spark no abre los Parquet de los "
          "otros\n    anios (partition pruning). Por eso la particion se eligio "
          "por anio de\n    publicacion y no por el anio del archivo de origen, "
          "que no coincide.")


def main():
    spark = entorno.crear_spark("eda-parte1", memoria="8g", particiones=64)
    ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    # nombres cortos para las dos categoricas que se usan en todo el EDA
    m = (spark.read.parquet(str(PARQUET / "main"))
         .withColumnRenamed("tender_mainProcurementCategory", "categoria")
         .withColumnRenamed("tender_procurementMethodDetails", "metodo"))

    eda_temporal(m)
    eda_categorias(m)
    eda_montos(m)
    eda_entidades(m)
    eda_postores(spark)
    comparar_estilos(spark, m)
    explicar_particionado(spark, m)

    print(f"\nArtefactos exportados en: {ARTEFACTOS}")
    for f in sorted(ARTEFACTOS.iterdir()):
        print(f"  {f.name:<38} {f.stat().st_size/1024:>8,.1f} KB")
    spark.stop()


if __name__ == "__main__":
    main()
