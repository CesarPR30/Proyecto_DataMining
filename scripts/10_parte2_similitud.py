# -*- coding: utf-8 -*-
"""
Parte II: similitud por Jaccard, MinHash y LSH sobre Spark.

Estructura del experimento:

  A. Verdad de terreno. Se toma una muestra de procesos y se calcula el
     Jaccard EXACTO de todos sus pares por fuerza bruta. Sirve de referencia
     para medir el error de todo lo demas.

  B. MinHash propio. Se implementan T funciones hash universales
     h_i(x) = (a_i * x + b_i) mod p, como en la sesion 03, con funciones de
     orden superior de Spark SQL (todo dentro de la JVM, sin UDF de Python).
     Se mide el error de estimacion del Jaccard frente a T.

  C. LSH por bandas propio. Se parte la firma en b bandas de r filas y se
     agrupan los documentos que coinciden en alguna banda. Se comparan la
     curva S teorica 1-(1-s^r)^b y la empirica, y se miden precision y recall
     -es decir, falsos positivos y falsos negativos- para varias (b, r).

  D. LSH por bandas a escala, sobre el corpus 2015-2026, para encontrar
     procesos casi duplicados que la fuerza bruta no podria buscar. Se explica
     ahi por que no se usa MinHashLSH de MLlib en este paso.

  E. Similitud entre proveedores: cada RUC como el conjunto de procesos a los
     que postulo. Es la pregunta de interes P1.

Uso:  python scripts/10_parte2_similitud.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno

entorno.configurar()

from pyspark.sql import functions as F  # noqa: E402
from pyspark.storagelevel import StorageLevel  # noqa: E402

PARQUET = entorno.DERIVADOS / "parquet"
ARTEFACTOS = entorno.DERIVADOS / "artefactos"

ANIO_DESDE = 2015        # ventana analitica fijada en el EDA (seccion 12.2)
N_MUESTRA = 2000         # documentos para la verdad de terreno
T_MAX = 256              # funciones hash de la firma mas larga
# Primo de Mersenne 2^31-1. No se usa 2^61-1 a proposito: con coeficientes de
# ese tamano el producto a*x desborda el entero de 64 bits de Spark y el
# hashing deja de ser uniforme. Con 2^31-1 el producto cabe holgadamente.
PRIMO = (1 << 31) - 1
UMBRAL = 0.6             # "similar de verdad" para precision y recall


def titulo(t):
    print(f"\n{t}\n" + "=" * len(t))


def exportar(objeto, nombre):
    ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    destino = ARTEFACTOS / nombre
    if nombre.endswith(".json"):
        destino.write_text(json.dumps(objeto, indent=2, ensure_ascii=False),
                           encoding="utf8")
    else:
        objeto.to_csv(destino, index=False, encoding="utf8")
    print(f"    -> {nombre}")


# ===================================================== A. verdad de terreno
def verdad_de_terreno(spark):
    titulo("A. Jaccard exacto por fuerza bruta (verdad de terreno)")
    r = (spark.read.parquet(str(PARQUET / "repr_proceso"))
         .where((F.col("anio") >= ANIO_DESDE) & (F.col("n_shingles") >= 40))
         .select("ocid", "buyer_name", "shingles", "n_shingles"))
    # El repartition no es cosmetico: limit() deja el resultado en UNA sola
    # particion y el crossJoin posterior correria en un unico hilo, midiendo
    # mal la fuerza bruta y desperdiciando 15 de los 16 nucleos.
    # Los shingles se pasan una sola vez a enteros: el crossJoin mueve cada
    # documento 2 000 veces, y un array de 170 enteros pesa bastante menos que
    # uno de 170 cadenas. El Jaccard no cambia porque la funcion es inyectiva
    # en la practica.
    muestra = (r.orderBy(F.hash("ocid")).limit(N_MUESTRA)
               .withColumn("xs", F.expr(
                   "array_sort(array_distinct("
                   "  transform(shingles, s -> abs(cast(xxhash64(s) as bigint)))))"))
               .repartition(32).cache())
    n = muestra.count()
    print(f"  muestra: {n:,} procesos "
          f"({n*(n-1)//2:,} pares a comparar por fuerza bruta)")

    a = muestra.select(F.col("ocid").alias("a"), F.col("xs").alias("sa"))
    b = muestra.select(F.col("ocid").alias("b"), F.col("xs").alias("sb"))
    t0 = time.time()
    pares = (a.crossJoin(b).where(F.col("a") < F.col("b"))
             .withColumn("inter", F.size(F.array_intersect("sa", "sb")))
             .withColumn("union", F.size(F.array_union("sa", "sb")))
             .withColumn("jaccard", F.col("inter") / F.col("union"))
             .select("a", "b", "jaccard")
             .where(F.col("jaccard") > 0)
             # a disco si no cabe: son millones de pares y el heap es de 8 GB
             .persist(StorageLevel.MEMORY_AND_DISK))
    n_pares = pares.count()
    seg = time.time() - t0
    similares = pares.where(F.col("jaccard") >= UMBRAL).cache()
    n_sim = similares.count()
    total_pares = n * (n - 1) // 2
    print(f"  pares con interseccion no vacia: {n_pares:,}")
    print(f"  pares con Jaccard >= {UMBRAL}: {n_sim:,} "
          f"({100*n_sim/total_pares:.4f} % del total)")
    print(f"  tiempo de la fuerza bruta: {seg:.1f} s")
    print(f"  extrapolacion a los 746 615 procesos de 2015-2026: "
          f"{seg * (746615/n)**2 / 3600:,.0f} horas")
    return muestra, pares, similares, n, seg, n_pares


# ============================================================ B. MinHash propio
def minhash_propio(spark, muestra):
    titulo("B. MinHash propio: h_i(x) = (a_i*x + b_i) mod p")
    import random
    random.seed(42)
    coef = [(random.randrange(1, PRIMO - 1), random.randrange(0, PRIMO - 1))
            for _ in range(T_MAX)]
    print(f"  {T_MAX} funciones hash universales, p = 2^31 - 1")

    firmas = muestra          # ya trae xs: los shingles como enteros

    # transform anidado: para cada (a,b) se toma el minimo sobre los shingles.
    # Va como expresion SQL para que Catalyst lo compile y no cruce a Python.
    pares_ab = ", ".join(f"struct({a}L as a, {b}L as b)" for a, b in coef)
    expr_firma = (
        f"transform(array({pares_ab}), c -> "
        f"  aggregate(xs, cast(9223372036854775807 as bigint), "
        f"    (acc, x) -> least(acc, pmod(c.a * pmod(x, {PRIMO}L) + c.b, {PRIMO}L))))")
    t0 = time.time()
    firmas = firmas.select("ocid", F.expr(expr_firma).alias("firma")).cache()
    firmas.count()
    print(f"  firmas de longitud {T_MAX} calculadas en {time.time() - t0:.1f} s")
    return firmas


def error_vs_T(spark, firmas, exactos, n_pares_exactos):
    titulo("B.2 Error de estimacion frente al numero de funciones hash")
    # No se puede materializar el join completo: son millones de pares y cada
    # uno cargaria DOS firmas de 256 enteros (unos 4 KB por fila). Se evalua
    # sobre una submuestra aleatoria, que para estimar una media basta y sobra.
    objetivo = 200_000
    frac = min(1.0, objetivo / max(n_pares_exactos, 1))
    muestra_pares = (exactos.sample(False, frac, seed=11)
                     if frac < 1.0 else exactos)
    fa = firmas.select(F.col("ocid").alias("a"), F.col("firma").alias("fa"))
    fb = firmas.select(F.col("ocid").alias("b"), F.col("firma").alias("fb"))
    pares = muestra_pares.join(F.broadcast(fa), "a").join(F.broadcast(fb), "b")

    # Todos los T en UNA sola pasada: se calculan las coincidencias acumuladas
    # una vez y cada T es un prefijo de ese mismo vector.
    Ts = (8, 16, 32, 64, 128, 256)
    columnas = []
    for T in Ts:
        coinc = F.expr(
            f"aggregate(zip_with(slice(fa,1,{T}), slice(fb,1,{T}), "
            f"(x,y) -> if(x = y, 1, 0)), 0, (acc,v) -> acc + v)")
        columnas.append(F.abs(coinc / F.lit(T) - F.col("jaccard")).alias(f"e{T}"))
    est = pares.select(F.col("jaccard"), *columnas)

    agregados = []
    for T in Ts:
        agregados += [F.avg(f"e{T}").alias(f"mae{T}"),
                      F.sqrt(F.avg(F.pow(f"e{T}", 2))).alias(f"rmse{T}"),
                      F.max(f"e{T}").alias(f"max{T}")]
    total = est.count()
    r = est.agg(*agregados).first()
    print(f"  pares evaluados: {total:,}")

    filas = []
    for T in Ts:
        teorico = (1 / T) ** 0.5 / 2     # desviacion tipica maxima: 0,5/sqrt(T)
        filas.append({"T": T, "mae": round(r[f"mae{T}"], 4),
                      "rmse": round(r[f"rmse{T}"], 4),
                      "max": round(r[f"max{T}"], 4),
                      "cota_teorica": round(teorico, 4)})
        print(f"  T={T:>3}  MAE {r[f'mae{T}']:.4f}  RMSE {r[f'rmse{T}']:.4f}  "
              f"error max {r[f'max{T}']:.4f}   (cota teorica ~{teorico:.4f})")
    exportar(filas, "p2_error_minhash_vs_T.json")
    return filas


# ======================================================= C. LSH por bandas
def lsh_por_bandas(spark, firmas, similares, n_muestra):
    titulo("C. LSH propio por bandas: efecto de (b, r) sobre falsos "
           "positivos y negativos")
    reales = similares.select("a", "b").cache()
    n_reales = reales.count()
    print(f"  pares realmente similares (Jaccard >= {UMBRAL}): {n_reales:,}")

    filas = []
    for b, r in ((128, 2), (64, 4), (32, 8), (16, 16), (8, 32), (4, 64)):
        T = b * r
        # cada documento entra en b cubetas; los que comparten cubeta son candidatos
        bandas = (firmas.select(
            "ocid",
            F.expr(f"transform(sequence(0, {b-1}), i -> "
                   f"  struct(i as banda, "
                   f"    hash(concat_ws(',', slice(firma, i*{r}+1, {r}))) as h))")
            .alias("bs"))
            .select("ocid", F.explode("bs").alias("bk"))
            .select("ocid", "bk.banda", "bk.h"))
        x = bandas.select(F.col("ocid").alias("a"), "banda", "h")
        y = bandas.select(F.col("ocid").alias("b"), "banda", "h")
        # el conteo se hace en Spark: para b grande los candidatos son
        # millones y traerlos al driver reventaria la memoria
        cand = (x.join(y, ["banda", "h"]).where(F.col("a") < F.col("b"))
                .select("a", "b").distinct().cache())
        n_cand = cand.count()
        vp = cand.join(reales, ["a", "b"]).count()
        fp = n_cand - vp
        fn = n_reales - vp
        cand.unpersist()
        prec = vp / n_cand if n_cand else 0.0
        rec = vp / n_reales if n_reales else 0.0
        # umbral donde la curva S cruza 1/2: (1/b)^(1/r)
        umbral_efectivo = (1 / b) ** (1 / r)
        filas.append({"b": b, "r": r, "T": T, "candidatos": n_cand,
                      "verdaderos_positivos": vp, "falsos_positivos": fp,
                      "falsos_negativos": fn, "precision": round(prec, 4),
                      "recall": round(rec, 4),
                      "umbral_efectivo": round(umbral_efectivo, 3)})
        print(f"  b={b:>3} r={r:>2} (T={T:>3})  candidatos {n_cand:>9,}  "
              f"VP {vp:>5,}  FP {fp:>7,}  FN {fn:>5,}  "
              f"prec {prec:.3f}  rec {rec:.3f}  umbral~{umbral_efectivo:.2f}")
    exportar(filas, "p2_lsh_bandas.json")

    # curva S: probabilidad de que un par de similitud s sea candidato
    curva = []
    for s in [i / 50 for i in range(51)]:
        fila = {"s": round(s, 2)}
        for b, r in ((64, 4), (32, 8), (16, 16)):
            fila[f"b{b}_r{r}"] = round(1 - (1 - s ** r) ** b, 4)
        curva.append(fila)
    exportar(curva, "p2_curva_s.json")
    return filas


# ================================================ D. LSH propio a escala
def lsh_escala(spark):
    """LSH por bandas sobre los 746 mil procesos de 2015-2026.

    Se usa la implementacion propia y no MinHashLSH de MLlib por una razon
    tecnica concreta: MLlib construye una tabla hash por funcion, es decir
    b = numHashTables y r = 1 SIEMPRE. Su umbral efectivo es entonces 1/b, de
    modo que con 8 tablas cualquier par con Jaccard 0,125 ya es candidato.
    Sobre este corpus eso genera una explosion de candidatos (se midio: mas de
    11 GB volcados a disco sin terminar). El esquema de bandas con r > 1 es el
    que permite subir el umbral, y es justamente lo que ense~na la sesion 04.
    """
    titulo("D. LSH por bandas propio sobre el corpus 2015-2026")
    B, R = 16, 8                  # umbral efectivo (1/16)^(1/8) = 0,71
    T = B * R
    import random
    random.seed(42)
    coef = [(random.randrange(1, PRIMO - 1), random.randrange(0, PRIMO - 1))
            for _ in range(T)]

    base = (spark.read.parquet(str(PARQUET / "repr_proceso"))
            .where((F.col("anio") >= ANIO_DESDE) & (F.col("n_shingles") >= 40))
            .select("ocid", "anio", "buyer_name", "shingles"))
    n = base.count()
    print(f"  procesos en juego: {n:,}")
    print(f"  b={B}, r={R} (T={T}), umbral efectivo "
          f"{(1/B)**(1/R):.2f}; se filtra despues a Jaccard >= 0,8")

    t0 = time.time()
    pares_ab = ", ".join(f"struct({a}L as a, {b}L as b)" for a, b in coef)
    firmas = (base
              .withColumn("xs", F.expr(
                  "array_distinct(transform(shingles, "
                  "  s -> abs(cast(xxhash64(s) as bigint))))"))
              .withColumn("firma", F.expr(
                  f"transform(array({pares_ab}), c -> "
                  f"  aggregate(xs, cast(9223372036854775807 as bigint), "
                  f"    (acc, x) -> least(acc, "
                  f"      pmod(c.a * pmod(x, {PRIMO}L) + c.b, {PRIMO}L))))"))
              .select("ocid", "anio", "buyer_name", "xs", "firma")
              .persist(StorageLevel.MEMORY_AND_DISK))
    firmas.count()
    print(f"  firmas MinHash de {n:,} documentos en {time.time() - t0:.1f} s")

    t0 = time.time()
    bandas = (firmas.select(
        "ocid",
        F.expr(f"transform(sequence(0, {B-1}), i -> "
               f"  struct(i as banda, "
               f"    hash(concat_ws(',', slice(firma, i*{R}+1, {R}))) as h))")
        .alias("bs"))
        .select("ocid", F.explode("bs").alias("bk"))
        .select("ocid", "bk.banda", "bk.h"))
    x = bandas.select(F.col("ocid").alias("ocid_a"), "banda", "h")
    y = bandas.select(F.col("ocid").alias("ocid_b"), "banda", "h")
    candidatos = (x.join(y, ["banda", "h"])
                  .where(F.col("ocid_a") < F.col("ocid_b"))
                  .select("ocid_a", "ocid_b").distinct()
                  .persist(StorageLevel.MEMORY_AND_DISK))
    n_cand = candidatos.count()
    seg_cand = time.time() - t0
    print(f"  pares candidatos: {n_cand:,} en {seg_cand:.1f} s")

    # verificacion exacta solo sobre los candidatos: es el paso que convierte
    # el recall alto de LSH en precision alta
    t0 = time.time()
    sa = firmas.select(F.col("ocid").alias("ocid_a"), F.col("xs").alias("xa"),
                       F.col("buyer_name").alias("entidad_a"),
                       F.col("anio").alias("anio_a"))
    sb = firmas.select(F.col("ocid").alias("ocid_b"), F.col("xs").alias("xb"),
                       F.col("buyer_name").alias("entidad_b"),
                       F.col("anio").alias("anio_b"))
    pares = (candidatos.join(sa, "ocid_a").join(sb, "ocid_b")
             .withColumn("jaccard",
                         F.size(F.array_intersect("xa", "xb"))
                         / F.size(F.array_union("xa", "xb")))
             .where(F.col("jaccard") >= 0.8)
             .select("ocid_a", "ocid_b", "entidad_a", "entidad_b",
                     "anio_a", "anio_b", "jaccard")
             .persist(StorageLevel.MEMORY_AND_DISK))
    n_pares = pares.count()
    seg = seg_cand + (time.time() - t0)
    print(f"  pares confirmados con Jaccard >= 0,8: {n_pares:,} "
          f"(total {seg:.1f} s)")
    print(f"  la fuerza bruta habria comparado {n*(n-1)//2:,} pares")
    print(f"  los candidatos fueron el "
          f"{100*n_cand/(n*(n-1)//2):.6f} % de ese total")
    candidatos.unpersist()

    misma = pares.where(F.col("entidad_a") == F.col("entidad_b")).count()
    print(f"  de esos pares, {misma:,} ({100*misma/max(n_pares,1):.1f} %) son de "
          f"la MISMA entidad")

    print("\n  casos concretos (mismo texto, distinta convocatoria):")
    textos = (spark.read.parquet(str(PARQUET / "repr_proceso"))
              .select(F.col("ocid").alias("ocid_a"), F.col("texto").alias("texto_a")))
    ejemplos = (pares.where((F.col("entidad_a") == F.col("entidad_b"))
                            & (F.col("jaccard") < 1.0))
                .orderBy(F.desc("jaccard")).limit(3)
                .join(textos, "ocid_a", "left"))
    for f in ejemplos.collect():
        print(f"    J={f['jaccard']:.3f}  {str(f['entidad_a'])[:56]}")
        print(f"      {f['ocid_a']} ({f['anio_a']})  vs  "
              f"{f['ocid_b']} ({f['anio_b']})")
        print(f"      {str(f['texto_a'])[:104]}")

    resumen = {"procesos": n, "candidatos": n_cand, "pares_similares": n_pares,
               "pares_fuerza_bruta": n * (n - 1) // 2,
               "b": B, "r": R, "segundos_lsh": round(seg, 1),
               "pct_misma_entidad": round(100 * misma / max(n_pares, 1), 1)}
    exportar(resumen, "p2_lsh_escala.json")

    # distribucion de similitud, para el reporte web
    dist = (pares.withColumn("banda", F.round(F.col("jaccard"), 2))
            .groupBy("banda").count().orderBy("banda"))
    exportar(dist.toPandas(), "p2_distribucion_jaccard.csv")
    firmas.unpersist()
    return resumen


# ================================================ E. proveedores similares
def lsh_proveedores(spark):
    titulo("E. Proveedores que postulan a lo mismo (pregunta P1)")
    from pyspark.ml.feature import HashingTF, MinHashLSH

    canasta = (spark.read.parquet(str(PARQUET / "canasta_proceso_postores"))
               .where(F.col("anio") >= ANIO_DESDE))
    prov = (canasta.select(F.explode("postores").alias("ruc"), "ocid")
            .groupBy("ruc")
            .agg(F.array_distinct(F.collect_list("ocid")).alias("procesos"))
            .withColumn("n", F.size("procesos"))
            .where(F.col("n") >= 10)
            .cache())
    n = prov.count()
    print(f"  proveedores con 10 o mas procesos en {ANIO_DESDE}-2026: {n:,}")

    tf = HashingTF(inputCol="procesos", outputCol="vec", numFeatures=1 << 20,
                   binary=True)
    vect = (tf.transform(prov).select("ruc", "n", "vec")
            .persist(StorageLevel.MEMORY_AND_DISK))
    vect.count()
    mh = MinHashLSH(inputCol="vec", outputCol="firma", numHashTables=10, seed=7)
    modelo = mh.fit(vect)

    t0 = time.time()
    pares = (modelo.approxSimilarityJoin(vect, vect, 1 - 0.5, distCol="dist")
             .where(F.col("datasetA.ruc") < F.col("datasetB.ruc"))
             .select(F.col("datasetA.ruc").alias("ruc_a"),
                     F.col("datasetB.ruc").alias("ruc_b"),
                     F.col("datasetA.n").alias("n_a"),
                     F.col("datasetB.n").alias("n_b"),
                     (1 - F.col("dist")).alias("jaccard"))
             .persist(StorageLevel.MEMORY_AND_DISK))
    n_pares = pares.count()
    print(f"  pares de proveedores con Jaccard >= 0,5: {n_pares:,} "
          f"en {time.time() - t0:.1f} s")
    print(f"  la fuerza bruta habria comparado {n*(n-1)//2:,} pares")

    nombres = (spark.read.parquet(str(PARQUET / "repr_proveedor"))
               .select(F.col("ruc"), F.col("name").alias("nombre")))
    top = (pares.join(nombres.withColumnRenamed("nombre", "nombre_a")
                      .withColumnRenamed("ruc", "ruc_a"), "ruc_a", "left")
           .join(nombres.withColumnRenamed("nombre", "nombre_b")
                 .withColumnRenamed("ruc", "ruc_b"), "ruc_b", "left")
           .orderBy(F.desc("jaccard"), F.desc("n_a")))
    print("\n  pares mas acoplados (ambos con historial amplio):")
    for f in top.where((F.col("n_a") >= 20) & (F.col("n_b") >= 20)).limit(6).collect():
        print(f"    J={f['jaccard']:.3f}  {str(f['nombre_a'])[:38]:38} ({f['n_a']:>3})"
              f"  <->  {str(f['nombre_b'])[:38]:38} ({f['n_b']:>3})")

    exportar(top.limit(500).toPandas(), "p2_proveedores_similares.csv")
    dist = (pares.withColumn("banda", F.round(F.col("jaccard"), 2))
            .groupBy("banda").count().orderBy("banda"))
    exportar(dist.toPandas(), "p2_distribucion_jaccard_proveedores.csv")
    prov.unpersist()
    return {"proveedores": n, "pares": n_pares,
            "pares_fuerza_bruta": n * (n - 1) // 2}


def main():
    # Permite reejecutar solo una etapa: python 10_parte2_similitud.py D E
    etapas = set(a.upper() for a in sys.argv[1:]) or {"A", "B", "C", "D", "E"}
    spark = entorno.crear_spark("parte2-similitud", memoria="8g",
                                particiones=64)
    if {"A", "B", "C"} & etapas:
        muestra, exactos, similares, n, seg_bruta, n_ex = verdad_de_terreno(spark)
        firmas = minhash_propio(spark, muestra)
        if "B" in etapas:
            error_vs_T(spark, firmas, exactos, n_ex)
        if "C" in etapas:
            lsh_por_bandas(spark, firmas, similares, n)
        exactos.unpersist()
        muestra.unpersist()
        firmas.unpersist()
    if "D" in etapas:
        lsh_escala(spark)
    if "E" in etapas:
        lsh_proveedores(spark)
    print(f"\nArtefactos en: {ARTEFACTOS}")
    spark.stop()


if __name__ == "__main__":
    main()
