# -*- coding: utf-8 -*-
"""
Parte V: conjuntos frecuentes y reglas de asociacion (Apriori y FP-Growth).

Canasta principal (A): proceso -> conjunto de RUC que postularon.
  Un conjunto frecuente {RUC1, RUC2, RUC3} significa que esas empresas
  concurren juntas a los mismos procesos mucho mas de lo esperable por azar:
  es la pregunta P1. Ventana 2015-2026 (antes de 2015 el SEACE no registraba
  a todos los postores; ver el EDA).

Canasta secundaria (C): entidad-anio -> familias de bienes y servicios
  compradas (codigo CUBSO/UNSPSC truncado). Lectura del lado de la demanda.

Decisiones de preprocesamiento (justificadas con datos en la salida):
  1. Se colapsan las reconvocatorias: la Parte II mostro que el 98 % de los
     pares casi identicos son la MISMA entidad republicando el mismo texto.
     Si no se colapsan, una misma convocatoria cuenta dos o tres veces y
     infla el soporte de los grupos que postulan a ella.
  2. Se descartan canastas de 1 postor (no aportan co-ocurrencia) y las de
     mas de 40 postores: son compras masivas (subastas, catalogos) donde la
     coincidencia no es una eleccion, y un solo proceso con 300 postores
     genera 45 000 pares que dominarian el conteo.

Donde corre cada paso:
  - FP-Growth: SPARK MLlib sobre todas las canastas 2015-2026 (cientos de
    miles de canastas y de items distintos: el arbol FP se construye en
    paralelo por prefijo, algoritmo PFP).
  - Apriori: implementacion propia en estilo MapReduce sobre RDDs (un
    flatMap + reduceByKey por nivel, la formulacion de Apriori de la sesion),
    sobre un subconjunto (un anio). Se valida que da exactamente los mismos
    conjuntos que FP-Growth con el mismo umbral y se comparan tiempos.

Uso:  python scripts/14_parte5_reglas.py
"""
import json
import sys
import time
from itertools import combinations
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno  # noqa: E402

entorno.configurar()

from pyspark.ml.fpm import FPGrowth  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.window import Window  # noqa: E402

PARQUET = entorno.DERIVADOS / "parquet"
ARTEFACTOS = entorno.DERIVADOS / "artefactos"

ANIO_DESDE = 2015
MAX_POSTORES = 40
MIN_CONTEO = 30          # un grupo debe coincidir en >= 30 procesos
MIN_CONFIANZA = 0.5
N_REGLAS_REPORTE = 3000
N_CAMARILLAS = 300
ANIO_APRIORI = 2023      # subconjunto para Apriori
MIN_CONTEO_APRIORI = 15
K_MAX_APRIORI = 4        # Apriori explota en las camarillas grandes (ver salida)
MAX_ANTECEDENTE = 2      # reglas legibles: {A} -> B y {A, B} -> C
CUBSO_DIGITOS = 6        # clase UNSPSC (segmento-familia-clase)
MIN_SOPORTE_CUBSO = 0.10
MIN_CONF_CUBSO = 0.6


def titulo(t):
    print(f"\n{t}\n" + "=" * len(t))


def exportar(objeto, nombre):
    ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    destino = ARTEFACTOS / nombre
    if nombre.endswith(".json"):
        destino.write_text(json.dumps(objeto, indent=2, ensure_ascii=False,
                                      default=str), encoding="utf8")
    else:
        objeto.to_csv(destino, index=False, encoding="utf8")
    print(f"    -> {nombre}")


# ========================================================= 1. canastas
def canastas_postores(spark, resumen):
    titulo("1. Canasta A: proceso -> postores (preprocesamiento)")
    canasta = (spark.read.parquet(str(PARQUET / "canasta_proceso_postores"))
               .where(F.col("anio") >= ANIO_DESDE))
    proc = (spark.read.parquet(str(PARQUET / "repr_proceso"))
            .where(F.col("anio") >= ANIO_DESDE)
            .select("ocid", "buyer_name", "texto", "categoria"))
    fechas = (spark.read.parquet(str(PARQUET / "main"))
              .where(F.col("anio") >= ANIO_DESDE).select("ocid", "fecha"))
    c = canasta.join(proc, "ocid", "left").join(fechas, "ocid", "left")
    n0 = c.count()

    # 1. reconvocatorias: misma entidad + mismo texto -> se queda la ultima
    w = Window.partitionBy("buyer_name", "texto").orderBy(F.desc_nulls_last("fecha"))
    c = c.withColumn("_rn", F.row_number().over(w)).where(F.col("_rn") == 1).drop("_rn")
    n1 = c.count()
    # 2. tamanio de canasta
    c = c.where((F.col("n_postores") >= 2) & (F.col("n_postores") <= MAX_POSTORES))
    c = c.cache()
    n2 = c.count()
    stats = c.select(F.avg("n_postores").alias("m"),
                     F.expr("percentile_approx(n_postores, 0.5)").alias("med")).first()
    resumen["canastas"] = {"inicial": n0, "tras_reconvocatorias": n1,
                           "reconvocatorias_colapsadas": n0 - n1,
                           "final": n2, "postores_medio": round(stats["m"], 2),
                           "postores_mediana": int(stats["med"])}
    print(f"  canastas 2015-2026: {n0:,}")
    print(f"  - reconvocatorias colapsadas: {n0 - n1:,} ({100*(n0-n1)/n0:.1f} %)")
    print(f"  - fuera de 2..{MAX_POSTORES} postores: {n1 - n2:,}")
    print(f"  = canastas usadas: {n2:,}  (media {stats['m']:.2f} postores)")
    return c


# ============================================== 2. Apriori propio (RDD)
def apriori_rdd(spark, canastas, min_conteo, k_max=6):
    """A-priori nivel a nivel en estilo MapReduce.

    Nivel k: map  -> cada canasta emite sus k-subconjuntos cuyos (k-1)
                     subconjuntos son todos frecuentes (poda A-priori)
             reduce-> reduceByKey suma ocurrencias; filter >= min_conteo
    Los frecuentes del nivel k se difunden (broadcast) para el nivel k+1.
    """
    sc = spark.sparkContext
    rdd = canastas.rdd.map(lambda r: sorted(set(r["postores"]))).cache()
    niveles = {}
    # nivel 1
    l1 = (rdd.flatMap(lambda b: [((x,), 1) for x in b])
          .reduceByKey(lambda a, b: a + b)
          .filter(lambda kv: kv[1] >= min_conteo).collectAsMap())
    niveles[1] = l1
    frecuentes = l1
    k = 2
    while frecuentes and k <= k_max:
        items_frec = sc.broadcast({x for it in frecuentes for x in it})
        prev = sc.broadcast(set(frecuentes))

        def emitir(b, k=k):
            b = [x for x in b if x in items_frec.value]
            for comb in combinations(b, k):
                if all(sub in prev.value for sub in combinations(comb, k - 1)):
                    yield comb, 1
        lk = (rdd.flatMap(emitir).reduceByKey(lambda a, b: a + b)
              .filter(lambda kv: kv[1] >= min_conteo).collectAsMap())
        if not lk:
            break
        niveles[k] = lk
        frecuentes = lk
        k += 1
    rdd.unpersist()
    return niveles


def fpgrowth(df, columna, min_soporte, min_conf):
    modelo = FPGrowth(itemsCol=columna, minSupport=min_soporte,
                      minConfidence=min_conf).fit(df)
    return modelo


def comparar_apriori_fpgrowth(spark, c, resumen):
    titulo(f"2. Apriori (RDD, propio) vs FP-Growth (MLlib) - subconjunto {ANIO_APRIORI}")
    sub = c.where(F.col("anio") == ANIO_APRIORI).select("postores").cache()
    n = sub.count()
    t0 = time.time()
    niveles = apriori_rdd(spark, sub, MIN_CONTEO_APRIORI, K_MAX_APRIORI)
    t_ap = time.time() - t0
    ap = {frozenset(s): v for nivel in niveles.values() for s, v in nivel.items()}

    t0 = time.time()
    # MLlib usa ceil(minSupport * n): se resta 0,5 para no caer en 16 por
    # redondeo de coma flotante y comparar con el MISMO umbral entero
    modelo = fpgrowth(sub, "postores", (MIN_CONTEO_APRIORI - 0.5) / n, 0.5)
    fi = modelo.freqItemsets.toPandas()
    t_fp = time.time() - t0
    fp = {frozenset(r["items"]): int(r["freq"]) for _, r in fi.iterrows()}
    # Apriori se detiene en K_MAX_APRIORI; FP-Growth no tiene tope de tamanio.
    # La validacion compara ambos hasta el mismo tamanio.
    k_max = max(niveles)
    fp_k = {s_: v for s_, v in fp.items() if len(s_) <= k_max}
    iguales = ap == fp_k
    por_tam_fp = pd.Series([len(s_) for s_ in fp]).value_counts().sort_index()
    print(f"  canastas: {n:,}  umbral: {MIN_CONTEO_APRIORI} canastas")
    for k, nivel in niveles.items():
        print(f"    nivel {k}: {len(nivel):,} conjuntos (FP-Growth: {por_tam_fp.get(k, 0):,})")
    print(f"  Apriori (RDD, k <= {k_max}): {len(ap):,} conjuntos en {t_ap:.1f} s")
    print(f"  FP-Growth (sin tope)   : {len(fp):,} conjuntos en {t_fp:.1f} s, "
          f"tamanio maximo {por_tam_fp.index.max()}")
    print(f"  ¿mismos conjuntos y soportes hasta k = {k_max}? {'SI' if iguales else 'NO'}")
    resumen["apriori_vs_fpgrowth"] = {
        "anio": ANIO_APRIORI, "canastas": n, "min_conteo": MIN_CONTEO_APRIORI,
        "k_max_apriori": k_max,
        "por_nivel_apriori": {int(k): len(v) for k, v in niveles.items()},
        "por_tamanio_fpgrowth": {int(k): int(v) for k, v in por_tam_fp.items()},
        "conjuntos_apriori": len(ap), "conjuntos_fpgrowth": len(fp),
        "conjuntos_fpgrowth_hasta_kmax": len(fp_k),
        "segundos_apriori": round(t_ap, 1), "segundos_fpgrowth": round(t_fp, 1),
        "identicos_hasta_kmax": iguales}
    sub.unpersist()


# ======================================== 3. FP-Growth sobre todo 2015-2026
def reglas_postores(spark, c, resumen):
    titulo("3. FP-Growth (MLlib) sobre todas las canastas 2015-2026")
    n = c.count()
    t0 = time.time()
    modelo = fpgrowth(c.select("postores"), "postores", (MIN_CONTEO - 0.5) / n,
                      MIN_CONFIANZA)
    fi = (modelo.freqItemsets
          .select(F.array_sort("items").alias("items"), "freq")
          .withColumn("k", F.size("items")).cache())
    n_fi = fi.count()
    seg_fi = time.time() - t0
    por_tam = (fi.groupBy("k").agg(F.count("*").alias("conjuntos"),
                                   F.max("freq").alias("freq_max"))
               .orderBy("k").toPandas())
    print(f"  {n_fi:,} conjuntos frecuentes en {seg_fi:.0f} s")
    print("  " + por_tam.to_string(index=False).replace("\n", "\n  "))

    # Conjuntos MAXIMALES: frecuentes sin ningun superconjunto frecuente.
    # Un grupo de 20 RUC que postula junto genera 2^20 subconjuntos
    # frecuentes; el maximal lo describe una sola vez. Por la clausura hacia
    # abajo basta mirar los superconjuntos de tamanio k+1: se generan los
    # k-subconjuntos de cada (k+1)-conjunto y se hace un anti-join.
    t0 = time.time()
    subs = (fi.where(F.col("k") >= 2)
            .select(F.explode(F.expr(
                "transform(sequence(0, k - 1), "
                "i -> array_remove(items, items[i]))")).alias("items"))
            .distinct())
    maximales = fi.join(subs, "items", "left_anti").cache()
    n_max = maximales.count()
    dist_max = maximales.groupBy("k").count().orderBy("k").toPandas()
    print(f"  conjuntos maximales: {n_max:,} ({time.time() - t0:.0f} s)")
    print("  " + dist_max.to_string(index=False).replace("\n", "\n  "))

    t0 = time.time()
    reglas = (modelo.associationRules
              .where(F.size("antecedent") <= MAX_ANTECEDENTE).cache())
    n_r = reglas.count()
    seg_r = time.time() - t0
    print(f"  reglas con antecedente <= {MAX_ANTECEDENTE} y confianza >= "
          f"{MIN_CONFIANZA}: {n_r:,} ({seg_r:.0f} s)")
    resumen["fpgrowth"] = {
        "canastas": n, "min_conteo": MIN_CONTEO, "min_soporte": MIN_CONTEO / n,
        "min_confianza": MIN_CONFIANZA, "conjuntos": n_fi, "maximales": n_max,
        "reglas": n_r, "max_antecedente": MAX_ANTECEDENTE,
        "segundos_conjuntos": round(seg_fi, 1), "segundos_reglas": round(seg_r, 1),
        "por_tamanio": {int(r.k): int(r.conjuntos) for r in por_tam.itertuples()},
        "maximales_por_tamanio": {int(r.k): int(r.count) for r in dist_max.itertuples()}}
    return fi, maximales, reglas


def contexto_grupos(spark, c, grupos):
    """Lectura de cada grupo de RUC mas alla de la metrica.

    grupos: DataFrame (gid, grupo). Se recuperan los procesos donde concurren
    TODOS los del grupo (join por RUC y conteo = tamanio del grupo, en lugar
    de un crossJoin canastas x grupos) y se resume: en cuantas entidades
    ocurre, que porcentaje se concentra en la entidad principal, rubro, anios
    y si alguno del grupo gana (awards_suppliers). Un grupo que coincide
    siempre en UNA entidad y rota el triunfo cuenta una historia distinta de
    uno que coincide en muchas entidades de un mismo rubro.
    """
    gx = grupos.select("gid", F.size("grupo").alias("n"), F.explode("grupo").alias("ruc"))
    bx = c.select("ocid", F.explode("postores").alias("ruc"))
    match = (gx.join(bx, "ruc").groupBy("gid", "n", "ocid").count()
             .where(F.col("count") == F.col("n")).select("gid", "ocid"))
    ganadores = (spark.read.parquet(str(PARQUET / "awards_suppliers"))
                 .select(F.col("main_ocid").alias("ocid"), F.col("id").alias("ganador"))
                 .groupBy("ocid").agg(F.collect_set("ganador").alias("ganadores")))
    m = (match.join(c.select("ocid", "buyer_name", "categoria", "anio", "n_postores"), "ocid")
         .join(ganadores, "ocid", "left").join(grupos, "gid")
         .withColumn("gana_grupo", (F.size(F.array_intersect(
             F.coalesce("ganadores", F.array().cast("array<string>")), "grupo")) > 0)
             .cast("int"))
         .withColumn("con_adjudicacion", F.col("ganadores").isNotNull().cast("int"))
         # Linea base: si el ganador saliera al azar entre los postores, el
         # grupo ganaria con probabilidad k / n_postores. Sin esta referencia
         # "el grupo gana el 95 %" no dice nada cuando son 11 de 12 postores.
         .withColumn("esperado", F.when(F.col("con_adjudicacion") == 1,
                                        F.size("grupo") / F.col("n_postores")))
         .cache())

    def principal(col, alias):
        return (m.groupBy("gid", col).count()
                .withColumn("rk", F.row_number().over(
                    Window.partitionBy("gid").orderBy(F.desc("count"), col)))
                .where(F.col("rk") == 1)
                .select("gid", F.col(col).alias(alias),
                        F.col("count").alias(f"procesos_{alias}")))

    agg = (m.groupBy("gid").agg(
        F.count("*").alias("procesos_grupo"),
        F.countDistinct("buyer_name").alias("entidades"),
        F.min("anio").alias("desde"), F.max("anio").alias("hasta"),
        F.sum("con_adjudicacion").alias("adjudicados"),
        F.sum("gana_grupo").alias("ganados_por_grupo"),
        F.avg("esperado").alias("pct_gana_esperado"),
        F.avg("n_postores").alias("postores_medio")))
    ctx = (agg.join(principal("buyer_name", "entidad_principal"), "gid")
           .join(principal("categoria", "rubro_principal"), "gid")
           .withColumn("pct_entidad_principal",
                       F.col("procesos_entidad_principal") / F.col("procesos_grupo"))
           .withColumn("pct_gana_grupo", F.when(F.col("adjudicados") > 0,
                       F.col("ganados_por_grupo") / F.col("adjudicados"))))
    pdf = ctx.toPandas()
    m.unpersist()
    return pdf


def contexto(spark, c, reglas, maximales):
    titulo("4. Contexto de reglas y camarillas: entidad, rubro y ganadores")
    t0 = time.time()
    # Reglas para el reporte: las de mayor soporte (todas tienen lift >> 1
    # porque cada RUC aparece en una fraccion minima de las canastas)
    top = (reglas.withColumn("grupo", F.array_sort(F.array_union("antecedent", "consequent")))
           .withColumn("n_grupo", F.size("grupo"))
           .orderBy(F.desc("support"), F.desc("confidence"), F.desc("lift"))
           .limit(N_REGLAS_REPORTE).toPandas())
    # Camarillas: maximales de 3 o mas RUC, las mas grandes y frecuentes
    cam = (maximales.where(F.col("k") >= 3)
           .orderBy(F.desc("k"), F.desc("freq")).limit(N_CAMARILLAS).toPandas())
    grupos_unicos = {tuple(g) for g in top["grupo"]} | {tuple(g) for g in cam["items"]}
    gid = {g: i for i, g in enumerate(sorted(grupos_unicos))}
    grupos = spark.createDataFrame([(i, list(g)) for g, i in gid.items()],
                                   "gid long, grupo array<string>")
    ctx = contexto_grupos(spark, c, grupos).set_index("gid")
    top["gid"] = top["grupo"].apply(lambda g: gid[tuple(g)])
    cam["gid"] = cam["items"].apply(lambda g: gid[tuple(g)])
    top = top.join(ctx, on="gid")
    cam = cam.join(ctx, on="gid")
    print(f"  {len(gid):,} grupos contextualizados en {time.time() - t0:.0f} s")
    nombres = (spark.read.parquet(str(PARQUET / "repr_proveedor"))
               .select("ruc", "name", "n_procesos").toPandas().set_index("ruc"))
    return top, cam, nombres


def tipo_ruc(ruc):
    num = str(ruc).replace("PE-RUC-", "")
    if num.startswith("10"):
        return "persona natural"
    if num.startswith("20"):
        return "empresa"
    return "otro"


def anonimizar(top, cam, nombres):
    """Etiquetas estables P0001.. por RUC (orden de aparicion: camarillas y
    luego reglas). El reporte publico solo ve la etiqueta y el tipo de
    contribuyente; la correspondencia RUC-etiqueta queda en *_PRIVADO."""
    etiqueta = {}
    for lista in list(cam["items"]) + [list(a) + list(b) for a, b in
                                       zip(top["antecedent"], top["consequent"])]:
        for x in lista:
            etiqueta.setdefault(x, f"P{len(etiqueta) + 1:04d}")

    def fmt(lista):
        return [f"{etiqueta[x]} ({tipo_ruc(x)})" for x in lista]

    contexto_cols = ["procesos_grupo", "entidades", "pct_entidad_principal",
                     "entidad_principal", "rubro_principal", "desde", "hasta",
                     "postores_medio", "adjudicados", "pct_gana_grupo",
                     "pct_gana_esperado"]
    reglas_pub = pd.DataFrame({
        "antecedente": top["antecedent"].apply(fmt),
        "consecuente": top["consequent"].apply(fmt),
        "n_grupo": top["n_grupo"], "soporte": top["support"].round(6),
        "confianza": top["confidence"].round(4), "lift": top["lift"].round(1)})
    reglas_pub = pd.concat([reglas_pub, top[contexto_cols].reset_index(drop=True)], axis=1)
    cam_pub = pd.DataFrame({"grupo": cam["items"].apply(fmt), "k": cam["k"],
                            "freq": cam["freq"]})
    cam_pub = pd.concat([cam_pub, cam[contexto_cols].reset_index(drop=True)], axis=1)
    for df in (reglas_pub, cam_pub):
        df["pct_entidad_principal"] = df["pct_entidad_principal"].round(3)
        df["pct_gana_grupo"] = df["pct_gana_grupo"].round(3)
        df["pct_gana_esperado"] = df["pct_gana_esperado"].round(3)
        df["postores_medio"] = df["postores_medio"].round(1)
    cam_pub["tipos"] = cam["items"].apply(
        lambda l: ", ".join(f"{sum(tipo_ruc(x) == t for x in l)} {t}"
                            for t in ("empresa", "persona natural")
                            if any(tipo_ruc(x) == t for x in l)))

    nombre = lambda l: [nombres["name"].get(x, "") for x in l]  # noqa: E731
    privado = top.assign(antecedente_nombres=top["antecedent"].apply(nombre),
                         consecuente_nombres=top["consequent"].apply(nombre))
    cam_priv = cam.assign(nombres=cam["items"].apply(nombre))
    tabla_etq = pd.DataFrame({"etiqueta": list(etiqueta.values()),
                              "ruc": list(etiqueta.keys()),
                              "nombre": [nombres["name"].get(x, "") for x in etiqueta],
                              "tipo": [tipo_ruc(x) for x in etiqueta]})
    return reglas_pub, cam_pub, privado, cam_priv, tabla_etq


def cruce_parte2(maximales, resumen):
    """¿Los pares con Jaccard >= 0,9 de la Parte II (proveedor como conjunto
    de procesos, MinHash + LSH) aparecen dentro de algun conjunto frecuente
    maximal de la Parte V (proceso como canasta de postores, FP-Growth)?
    Son dos representaciones y dos tecnicas independientes: si coinciden,
    el hallazgo de P1 no es un artefacto de un metodo."""
    titulo("5. Cruce con la Parte II (MinHash/LSH sobre proveedores)")
    ruta = ARTEFACTOS / "p2_proveedores_similares.csv"
    if not ruta.exists():
        print("  sin artefacto de la Parte II")
        return
    p2 = pd.read_csv(ruta)
    p2 = p2[p2["jaccard"] >= 0.9]
    if p2.empty:
        return
    spark = maximales.sparkSession
    pares = spark.createDataFrame(
        [(a, b, float(j), int(na), int(nb)) for a, b, j, na, nb in
         zip(p2["ruc_a"], p2["ruc_b"], p2["jaccard"], p2["n_a"], p2["n_b"])],
        "ruc_a string, ruc_b string, jaccard double, n_a long, n_b long")
    mx = maximales.select("items")
    cubiertos = (pares.join(mx, F.array_contains("items", F.col("ruc_a"))
                            & F.array_contains("items", F.col("ruc_b")), "left_semi"))
    n_p, n_c = pares.count(), cubiertos.count()
    # los pares no cubiertos suelen coincidir en menos de MIN_CONTEO procesos
    bajo = int((p2[["n_a", "n_b"]].min(axis=1) < MIN_CONTEO).sum())
    resumen["cruce_parte2"] = {"pares_jaccard_090": n_p, "en_algun_maximal": n_c,
                               "pares_con_menos_de_min_conteo": bajo}
    print(f"  pares con Jaccard >= 0,9 (Parte II): {n_p:,}; dentro de algun conjunto "
          f"frecuente maximal (Parte V): {n_c:,}")
    print(f"  pares donde algun proveedor tiene < {MIN_CONTEO} procesos (no pueden "
          f"ser frecuentes con este umbral): {bajo:,}")


# =========================================== 6. canasta C: entidad -> CUBSO
def reglas_cubso(spark, resumen):
    titulo(f"6. Canasta C: entidad-anio -> clases de bienes (CUBSO {CUBSO_DIGITOS} dig.)")
    items = (spark.read.parquet(str(PARQUET / "tender_items"))
             .where(F.col("anio") >= ANIO_DESDE)
             .select("main_ocid", "anio",
                     F.substring("classification_id", 1, CUBSO_DIGITOS).alias("clase"),
                     "classification_description")
             .where(F.col("clase").rlike(f"^[0-9]{{{CUBSO_DIGITOS}}}$")))
    # descripcion legible de la clase: la descripcion de item mas frecuente
    desc = (items.groupBy("clase", "classification_description").count()
            .withColumn("rk", F.row_number().over(
                Window.partitionBy("clase").orderBy(F.desc("count"))))
            .where(F.col("rk") == 1)
            .select("clase", F.col("classification_description").alias("ejemplo")))
    main = (spark.read.parquet(str(PARQUET / "main"))
            .where(F.col("anio") >= ANIO_DESDE).select("ocid", "buyer_name"))
    canasta = (items.join(main, items["main_ocid"] == main["ocid"])
               .groupBy("buyer_name", "anio")
               .agg(F.array_distinct(F.collect_list("clase")).alias("clases"))
               .where(F.size("clases") >= 2).cache())
    n = canasta.count()
    media = canasta.select(F.avg(F.size("clases"))).first()[0]
    t0 = time.time()
    modelo = fpgrowth(canasta, "clases", MIN_SOPORTE_CUBSO, MIN_CONF_CUBSO)
    reglas = modelo.associationRules.toPandas()
    n_fi = modelo.freqItemsets.count()
    seg = time.time() - t0
    d = dict(desc.toPandas().values)
    reglas["antecedente"] = reglas["antecedent"].apply(
        lambda l: [f"{x} (ej. {str(d.get(x, ''))[:45]})" for x in l])
    reglas["consecuente"] = reglas["consequent"].apply(
        lambda l: [f"{x} (ej. {str(d.get(x, ''))[:45]})" for x in l])
    reglas = reglas.sort_values(["lift", "support"], ascending=False)
    print(f"  {n:,} canastas entidad-anio (media {media:.1f} clases); "
          f"{n_fi:,} conjuntos y {len(reglas):,} reglas en {seg:.0f} s")
    for _, r in reglas.head(8).iterrows():
        print(f"    {r['antecedente']} -> {r['consecuente']}  "
              f"sop {r['support']:.3f} conf {r['confidence']:.2f} lift {r['lift']:.1f}")
    resumen["cubso"] = {"canastas": n, "clases_media": round(media, 1),
                        "conjuntos": n_fi, "reglas": int(len(reglas)),
                        "min_soporte": MIN_SOPORTE_CUBSO, "min_confianza": MIN_CONF_CUBSO}
    salida = reglas[["antecedente", "consecuente", "support", "confidence", "lift"]] \
        .rename(columns={"support": "soporte", "confidence": "confianza"})
    salida[["soporte", "confianza"]] = salida[["soporte", "confianza"]].round(4)
    salida["lift"] = salida["lift"].round(2)
    return salida.head(3000)


def main():
    spark = entorno.crear_spark("p5-reglas", memoria="8g", particiones=64)
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", str(256 * 1024 ** 2))
    resumen = {}
    c = canastas_postores(spark, resumen)
    if "sin-apriori" not in sys.argv[1:]:
        comparar_apriori_fpgrowth(spark, c, resumen)
    elif (ARTEFACTOS / "p5_resumen.json").exists():
        previo = json.loads((ARTEFACTOS / "p5_resumen.json").read_text(encoding="utf8"))
        if "apriori_vs_fpgrowth" in previo:
            resumen["apriori_vs_fpgrowth"] = previo["apriori_vs_fpgrowth"]
    fi, maximales, reglas = reglas_postores(spark, c, resumen)
    top, cam, nombres = contexto(spark, c, reglas, maximales)
    cruce_parte2(maximales, resumen)
    reglas_pub, cam_pub, privado, cam_priv, etiquetas = anonimizar(top, cam, nombres)
    exportar(reglas_pub, "p5_reglas_postores.csv")
    exportar(cam_pub, "p5_camarillas.csv")
    # Con identificadores: solo para el codigo reproducible, no para la web
    exportar(privado, "p5_reglas_postores_PRIVADO.csv")
    exportar(cam_priv, "p5_camarillas_PRIVADO.csv")
    exportar(etiquetas, "p5_etiquetas_PRIVADO.csv")

    print("\n  Camarillas mas grandes (conjuntos maximales, anonimizados):")
    for _, r in cam_pub.head(8).iterrows():
        print(f"    {r['k']} RUC ({r['tipos']}) juntos en {r['procesos_grupo']} procesos, "
              f"{r['entidades']} entidades ({100*r['pct_entidad_principal']:.0f} % en "
              f"{str(r['entidad_principal'])[:40]}), rubro {r['rubro_principal']}, "
              f"gana el grupo {r['pct_gana_grupo']} (azar {r['pct_gana_esperado']})")
    print("\n  Reglas de mayor soporte (anonimizadas):")
    for _, r in reglas_pub.head(12).iterrows():
        print(f"    {r['antecedente']} -> {r['consecuente']}  sop {r['soporte']:.5f} "
              f"conf {r['confianza']:.2f} lift {r['lift']:.0f} | "
              f"{r['procesos_grupo']} procesos, {r['entidades']} entidades, "
              f"{100*r['pct_entidad_principal']:.0f} % en la principal, "
              f"rubro {r['rubro_principal']}")
    tam = pd.DataFrame([{"k": k, "conjuntos": v,
                         "maximales": resumen["fpgrowth"]["maximales_por_tamanio"].get(k, 0)}
                        for k, v in resumen["fpgrowth"]["por_tamanio"].items()])
    exportar(tam, "p5_conjuntos_por_tamanio.csv")
    exportar(reglas_cubso(spark, resumen), "p5_reglas_cubso.csv")
    exportar(resumen, "p5_resumen.json")
    spark.stop()


if __name__ == "__main__":
    main()
