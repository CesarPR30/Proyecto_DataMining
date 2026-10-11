# -*- coding: utf-8 -*-
"""
Parte III: busqueda aproximada de vecinos (ANN) con IVF y HNSW.

Donde corre cada paso y por que:

  1. TF-IDF  -> SPARK (distribuido). El IDF necesita la frecuencia de cada
     termino sobre TODO el corpus 2015-2026 (~880 mil procesos, ~20 millones
     de pares documento-termino): es un groupBy masivo, justo lo que Spark
     resuelve bien. Se calcula con Spark SQL puro (explode + groupBy) y se
     exporta como tripletas (doc, termino, peso) en Parquet.

  2. LSA (TruncatedSVD a 128 dimensiones) -> LOCAL. FAISS trabaja con
     vectores densos; un TF-IDF denso de 20 000 terminos por 880 mil
     documentos pesaria 70 GB. La SVD aleatorizada sobre la matriz dispersa
     cabe en memoria (scipy) y tarda un par de minutos.

  3. Indices ANN -> LOCAL con FAISS. Ni IVF ni HNSW tienen implementacion en
     Spark MLlib, y su gracia es justamente responder una consulta en
     milisegundos desde memoria: distribuirlos no tendria sentido a este
     volumen (el indice entero ocupa ~450 MB).

  4. Uso del resultado para la pregunta P2 -> SPARK para los joins con las
     canastas de postores y los ganadores, LOCAL para el resumen.

Medidas: recall@10 frente a la busqueda exacta (fuerza bruta en el mismo
espacio), latencia por consulta en un solo hilo, tiempo de construccion y
memoria del indice, para varios valores de nprobe (IVF) y efSearch (HNSW).
Las curvas se exportan para el reporte web.

Uso:  python scripts/12_parte3_ann.py            # todo
      python scripts/12_parte3_ann.py ann        # salta el TF-IDF si ya existe
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno  # noqa: E402

entorno.configurar()

PARQUET = entorno.DERIVADOS / "parquet"
ARTEFACTOS = entorno.DERIVADOS / "artefactos"
TFIDF = PARQUET / "p3_tfidf"

ANIO_DESDE = 2015
VOCABULARIO = 20000       # terminos mas frecuentes que se conservan
MIN_DF = 5                # un termino en menos de 5 procesos es ruido
MAX_DF = 0.30             # en mas del 30 % no discrimina (p.ej. "SERVICIO")
DIM_MAX = 256             # componentes de la SVD (la curva usa sus prefijos)
DIM = 256                 # dimension del espacio en que se indexa (ver curva)
N_CONSULTAS = 1000        # consultas para medir recall y latencia
K = 10                    # vecinos por consulta
SEMILLA = 42


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


def _normalizador():
    """La misma normalizacion de texto que las representaciones (script 07)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "repr07", Path(__file__).with_name("07_representaciones.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.normalizar


# ================================================= 1. TF-IDF en Spark
def tfidf_spark():
    titulo("1. TF-IDF sobre Spark (corpus 2015-2026)")
    from pyspark.ml.feature import StopWordsRemover
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    spark = entorno.crear_spark("p3-tfidf", memoria="8g", particiones=64)
    t0 = time.time()
    # Texto del vector: DESCRIPCION + descripciones CUBSO de sus items.
    # No se usa el titulo (que si entra en los shingles de la Parte II): en
    # el SEACE el titulo es la nomenclatura del procedimiento
    # ("DIRECTA-PROC-7-2016-UNT-1") y sus siglas dominaban el TF-IDF; en una
    # primera corrida un liofilizador y un potenciostato de la misma
    # universidad salian con coseno 1,0. Las descripciones CUBSO agregan el
    # vocabulario controlado del catalogo, menos dependiente de la redaccion.
    normalizar = _normalizador()
    cubso = (spark.read.parquet(str(PARQUET / "tender_items"))
             .where(F.col("anio") >= ANIO_DESDE)
             .groupBy(F.col("main_ocid").alias("ocid"))
             .agg(F.concat_ws(" ", F.collect_set("classification_description"))
                  .alias("cubso_txt")))
    docs = (spark.read.parquet(str(PARQUET / "main"))
            .where(F.col("anio") >= ANIO_DESDE)
            .select("ocid", "anio", "buyer_name",
                    F.col("tender_mainProcurementCategory").alias("categoria"),
                    "tender_description")
            .join(cubso, "ocid", "left")
            .withColumn("texto", normalizar("tender_description", "cubso_txt"))
            .withColumn("tokens", F.split("texto", " "))
            .drop("tender_description", "cubso_txt"))

    # Stopwords de Spark llevadas a la misma normalizacion que el texto
    # (mayusculas, sin tildes) para que realmente coincidan.
    import unicodedata
    stop = {unicodedata.normalize("NFKD", w).encode("ascii", "ignore")
            .decode().upper()
            for w in StopWordsRemover.loadDefaultStopWords("spanish")}

    # Se descartan numeros y tokens de 1-2 letras: son correlativos de
    # nomenclatura (AS-SM-12-2019) que acercarian procesos sin relacion.
    tok = (docs.select("ocid", F.explode("tokens").alias("t"))
           .where((F.length("t") >= 3) & ~F.col("t").rlike("^[0-9]+$")
                  & ~F.col("t").isin(list(stop))))
    tf = tok.groupBy("ocid", "t").agg(F.count("*").alias("tf")).cache()
    n_docs = docs.count()
    df_t = tf.groupBy("t").agg(F.count("*").alias("df"))
    vocab = (df_t.where((F.col("df") >= MIN_DF) & (F.col("df") <= MAX_DF * n_docs))
             .orderBy(F.desc("df")).limit(VOCABULARIO)
             .withColumn("term_id", F.row_number().over(
                 Window.orderBy(F.desc("df"), "t")) - 1)
             .withColumn("idf", F.log(F.lit(n_docs) / F.col("df")))
             .cache())
    n_vocab = vocab.count()

    # Identificador denso de documento (fila de la matriz). Solo entran los
    # procesos con al menos un termino del vocabulario: un vector nulo no
    # tiene vecinos con sentido y ensuciaria el recall.
    ids = (tf.join(F.broadcast(vocab.select("t")), "t").select("ocid").distinct()
           .withColumn("doc_id", F.row_number().over(Window.orderBy("ocid")) - 1))
    # TF sublineal: (1 + log tf) * idf. Reduce el peso de terminos repetidos
    # en descripciones largas, que si no dominarian el coseno.
    trip = (tf.join(F.broadcast(vocab.select("t", "term_id", "idf")), "t")
            .join(ids, "ocid")
            .select("doc_id", "term_id",
                    ((1 + F.log("tf")) * F.col("idf")).cast("float").alias("w")))
    trip.repartition(8).write.mode("overwrite").parquet(str(TFIDF / "tripletas"))
    (docs.drop("tokens").join(ids, "ocid")
     .write.mode("overwrite").parquet(str(TFIDF / "documentos")))
    (vocab.select("term_id", "t", "df", "idf")
     .write.mode("overwrite").parquet(str(TFIDF / "vocabulario")))
    n_trip = spark.read.parquet(str(TFIDF / "tripletas")).count()
    n_con = spark.read.parquet(str(TFIDF / "documentos")).count()
    seg = time.time() - t0
    print(f"  procesos: {n_docs:,}  con terminos: {n_con:,}  vocabulario: {n_vocab:,}  "
          f"pares doc-termino: {n_trip:,}  ({seg:.0f} s)")
    resumen = {"procesos": n_docs, "documentos": n_con, "vocabulario": n_vocab,
               "no_ceros": n_trip, "segundos_spark": round(seg, 1),
               "min_df": MIN_DF, "max_df": MAX_DF}
    spark.stop()
    return resumen


# ======================================================= 2. LSA en local
def cargar_matriz():
    import pyarrow.parquet as pq
    from scipy import sparse
    t = pq.read_table(str(TFIDF / "tripletas")).to_pandas()
    docs = pq.read_table(str(TFIDF / "documentos")).to_pandas()
    docs = docs.sort_values("doc_id").reset_index(drop=True)
    n = len(docs)
    v = int(t["term_id"].max()) + 1
    X = sparse.csr_matrix((t["w"].values, (t["doc_id"].values, t["term_id"].values)),
                          shape=(n, v), dtype=np.float32)
    return X, docs


def normalizar_filas(X):
    from sklearn.preprocessing import normalize
    return normalize(X, norm="l2", axis=1)


def lsa(X):
    """SVD con DIM_MAX componentes; las de menor dimension son sus prefijos.

    Las componentes de la SVD salen ordenadas por valor singular, de modo que
    quedarse con las primeras d es (salvo el ruido del metodo aleatorizado)
    la mejor aproximacion de rango d: una sola SVD alimenta toda la curva.
    """
    titulo("2. Reduccion LSA (TruncatedSVD) en local")
    from sklearn.decomposition import TruncatedSVD
    t0 = time.time()
    svd = TruncatedSVD(n_components=DIM_MAX, algorithm="randomized", n_iter=5,
                       random_state=SEMILLA)
    U = svd.fit_transform(X).astype(np.float32)
    seg = time.time() - t0
    var = np.cumsum(svd.explained_variance_ratio_)
    print(f"  {X.shape[0]:,} x {X.shape[1]:,} -> {DIM_MAX} dimensiones en {seg:.0f} s")
    return U, var, seg


def proyectar(U, d):
    return normalizar_filas(U[:, :d]).astype(np.float32)


def particion(n):
    """Consultas separadas de la base: ningun metodo 'se encuentra a si mismo'."""
    rng = np.random.default_rng(SEMILLA)
    q_idx = rng.choice(n, N_CONSULTAS, replace=False)
    mask = np.ones(n, bool)
    mask[q_idx] = False
    return q_idx, np.where(mask)[0]


# ===================================================== 3. indices FAISS
def recall_por_distancia(I_ann, D_exacto, Z, Q):
    """Recall@K tolerante a empates.

    El corpus tiene muchas descripciones identicas (reconvocatorias): una
    consulta puede tener 30 vecinos con coseno 1,0 y cualquier subconjunto de
    10 es una respuesta exacta valida. Contar coincidencia de ids penalizaria
    al ANN por elegir otro empate igual de bueno, asi que un resultado cuenta
    como acierto si su similitud alcanza la del K-esimo vecino exacto.
    """
    umbral = D_exacto[:, K - 1][:, None] - 1e-5
    sims = np.einsum("qd,qkd->qk", Q, Z[np.clip(I_ann, 0, None)])
    sims[I_ann < 0] = -1
    return float((sims >= umbral).mean())


def latencia(index, Q, k=K, repeticiones=1):
    """ms por consulta en un solo hilo, consultando de a una."""
    import faiss
    faiss.omp_set_num_threads(1)
    t0 = time.perf_counter()
    for _ in range(repeticiones):
        for i in range(len(Q)):
            index.search(Q[i:i + 1], k)
    ms = 1000 * (time.perf_counter() - t0) / (len(Q) * repeticiones)
    faiss.omp_set_num_threads(0)
    return ms


def tam_indice(index):
    import faiss
    return len(faiss.serialize_index(index)) / 1024 ** 2


def experimentos_ann(Z, q_idx, base_idx):
    import faiss
    titulo(f"4. Busqueda exacta vs IVF vs HNSW (FAISS, {Z.shape[1]} dims)")
    rng = np.random.default_rng(SEMILLA)
    B, Q = Z[base_idx], Z[q_idx]
    print(f"  base: {len(B):,} vectores de {Z.shape[1]} dims  consultas: {len(Q):,}")
    d = Z.shape[1]

    # ---- exacta (fuerza bruta). IndexFlatIP = producto interno = coseno
    t0 = time.time()
    flat = faiss.IndexFlatIP(d)
    flat.add(B)
    t_flat = time.time() - t0
    D_ex, I_ex = flat.search(Q, K)
    ms_flat = latencia(flat, Q[:200])
    exacto = {"metodo": "Exacta (fuerza bruta)", "construccion_s": round(t_flat, 2),
              "ms_consulta": round(ms_flat, 3), "recall": 1.0,
              "mb": round(B.nbytes / 1024 ** 2, 1)}
    print(f"  exacta: {ms_flat:.2f} ms/consulta, {exacto['mb']} MB")

    filas = [dict(exacto, familia="exacta", param="-", valor=0, config="Flat")]

    # ---- IVF: k-means en nlist celdas, se exploran nprobe celdas
    for nlist in (256, 1024, 4096):
        t0 = time.time()
        quant = faiss.IndexFlatIP(d)
        ivf = faiss.IndexIVFFlat(quant, d, nlist, faiss.METRIC_INNER_PRODUCT)
        entren = B[rng.choice(len(B), min(len(B), 100 * nlist), replace=False)]
        ivf.train(entren)
        ivf.add(B)
        t_build = time.time() - t0
        mb = tam_indice(ivf)
        for nprobe in (1, 2, 4, 8, 16, 32, 64, 128):
            if nprobe > nlist:
                continue
            ivf.nprobe = nprobe
            _, I = ivf.search(Q, K)
            rec = recall_por_distancia(I, D_ex, B, Q)
            ms = latencia(ivf, Q[:300])
            filas.append({"familia": "IVF", "config": f"nlist={nlist}",
                          "param": "nprobe", "valor": nprobe, "recall": round(rec, 4),
                          "ms_consulta": round(ms, 3), "construccion_s": round(t_build, 1),
                          "mb": round(mb, 1)})
            print(f"  IVF nlist={nlist:5d} nprobe={nprobe:4d}: recall {rec:.3f}  "
                  f"{ms:.3f} ms  (build {t_build:.0f} s, {mb:.0f} MB)")

    # ---- HNSW: grafo navegable por capas; M vecinos por nodo
    for M in (8, 16, 32):
        t0 = time.time()
        hnsw = faiss.IndexHNSWFlat(d, M, faiss.METRIC_INNER_PRODUCT)
        hnsw.hnsw.efConstruction = 80
        hnsw.add(B)
        t_build = time.time() - t0
        mb = tam_indice(hnsw)
        for ef in (10, 16, 32, 64, 128, 256, 512):
            hnsw.hnsw.efSearch = ef
            _, I = hnsw.search(Q, K)
            rec = recall_por_distancia(I, D_ex, B, Q)
            ms = latencia(hnsw, Q[:300])
            filas.append({"familia": "HNSW", "config": f"M={M}",
                          "param": "efSearch", "valor": ef, "recall": round(rec, 4),
                          "ms_consulta": round(ms, 3), "construccion_s": round(t_build, 1),
                          "mb": round(mb, 1)})
            print(f"  HNSW M={M:2d} efSearch={ef:4d}: recall {rec:.3f}  "
                  f"{ms:.3f} ms  (build {t_build:.0f} s, {mb:.0f} MB)")

    return filas


def curva_dimensiones(X, U, var, q_idx, base_idx, dims=(16, 32, 64, 128, 256)):
    """Cuanto se pierde por pasar del TF-IDF disperso al espacio LSA.

    La comparacion ANN vs exacta (paso 4) se hace dentro del espacio LSA, que
    es lo justo para medir el INDICE. Pero hay una aproximacion previa
    escondida: la propia SVD. Aqui se mide contra el coseno exacto sobre el
    TF-IDF completo (producto de matrices dispersas en bloques) con dos
    metricas:
      - recall@10 tolerante a empates, y
      - recall de casi-duplicados: de los vecinos TF-IDF con coseno >= 0,8
        (los que interesan para P2), que fraccion aparece en el top 10 LSA.
    """
    titulo("3. Costo de la reduccion LSA frente al TF-IDF exacto")
    Xn = normalizar_filas(X).tocsr()
    Xb = Xn[base_idx].T.tocsc()
    q_sub = q_idx[:300]
    S_t = np.vstack([(Xn[q_sub[i:i + 50]] @ Xb).toarray()
                     for i in range(0, len(q_sub), 50)])
    filas = []
    for d in dims:
        Z = proyectar(U, d)
        S_l = Z[q_sub] @ Z[base_idx].T
        aciertos = cerca_ok = cerca_tot = 0
        for j in range(len(q_sub)):
            top_t = np.argpartition(-S_t[j], K)[:K]
            kth = S_t[j][top_t].min()
            top_l = np.argpartition(-S_l[j], K)[:K]
            aciertos += int((S_t[j][top_l] >= kth - 1e-5).sum())
            cercanos = set(np.where(S_t[j] >= 0.8)[0])
            if cercanos:
                # a lo sumo K pueden caber en el top K
                cerca_tot += min(len(cercanos), K)
                cerca_ok += len(cercanos & set(top_l.tolist()))
        filas.append({"dim": d, "varianza_explicada": round(float(var[d - 1]), 4),
                      "recall_top10": round(aciertos / (K * len(q_sub)), 4),
                      "recall_casi_duplicados": round(cerca_ok / max(cerca_tot, 1), 4),
                      "mb_base": round(len(base_idx) * d * 4 / 1024 ** 2, 1)})
        f = filas[-1]
        print(f"  d={d:4d}  varianza {100*f['varianza_explicada']:5.1f} %  "
              f"recall@10 vs TF-IDF {f['recall_top10']:.3f}  "
              f"casi-duplicados {f['recall_casi_duplicados']:.3f}  ({f['mb_base']} MB)")
    return filas


# ============================================ 5. lectura para la pregunta P2
def pares_vecinos(B_idx, q_idx, D_ex, I_ex, docs):
    """Pares (consulta, vecino) de la busqueda exacta, con su similitud."""
    import pandas as pd
    filas = []
    for qi in range(len(q_idx)):
        for j in range(K):
            filas.append((str(docs.loc[q_idx[qi], "ocid"]),
                          str(docs.loc[B_idx[I_ex[qi, j]], "ocid"]),
                          float(D_ex[qi, j])))
    return pd.DataFrame(filas, columns=["a", "b", "coseno"])


def p2_postores_y_ganadores(pares, docs):
    """¿Los procesos casi identicos terminan con los mismos postores y ganador?

    Se cruza cada par de vecinos con sus canastas de postores y con el
    ganador adjudicado, y se compara con una linea base de pares al azar de
    la misma categoria. El contraste, no la similitud sola, es el hallazgo.
    """
    titulo("6. Pregunta P2: vecinos de texto vs postores y ganadores (Spark)")
    import pandas as pd
    from pyspark.sql import functions as F
    spark = entorno.crear_spark("p3-p2", memoria="6g", particiones=32)

    ocid_por_id = docs.set_index("doc_id")["ocid"]
    rng = np.random.default_rng(SEMILLA)
    # linea base: pares al azar de la misma categoria
    base = []
    for cat, g in docs.groupby("categoria"):
        if len(g) < 2:
            continue
        a = rng.choice(g["doc_id"].values, 3000)
        b = rng.choice(g["doc_id"].values, 3000)
        base += list(zip(ocid_por_id[a].values, ocid_por_id[b].values,
                         [np.nan] * len(a)))
    base = pd.DataFrame(base, columns=["a", "b", "coseno"])
    base = base[base["a"] != base["b"]]
    pares = pares.assign(tipo="vecino")
    base = base.assign(tipo="azar")
    todos = pd.concat([pares, base], ignore_index=True)
    todos["a"] = todos["a"].astype(str)
    todos["b"] = todos["b"].astype(str)

    p = spark.createDataFrame(todos)
    ocids = (p.select(F.col("a").alias("ocid"))
             .union(p.select(F.col("b").alias("ocid"))).distinct())
    canasta = (spark.read.parquet(str(PARQUET / "canasta_proceso_postores"))
               .join(F.broadcast(ocids), "ocid").select("ocid", "postores"))
    ganador = (spark.read.parquet(str(PARQUET / "awards_suppliers"))
               .select(F.col("main_ocid").alias("ocid"), F.col("id").alias("ganador"))
               .join(F.broadcast(ocids), "ocid")
               .groupBy("ocid").agg(F.array_sort(F.collect_set("ganador"))
                                    .alias("ganadores")))
    meta = (spark.read.parquet(str(PARQUET / "main"))
            .select("ocid", "buyer_name").join(F.broadcast(ocids), "ocid"))
    info = canasta.join(ganador, "ocid", "full").join(meta, "ocid", "left")
    ia = info.select(*[F.col(c).alias(c + "_a") for c in info.columns])
    ib = info.select(*[F.col(c).alias(c + "_b") for c in info.columns])
    res = (p.join(ia, p["a"] == ia["ocid_a"], "left")
           .join(ib, p["b"] == ib["ocid_b"], "left")
           .withColumn("jac_postores", F.when(
               F.col("postores_a").isNotNull() & F.col("postores_b").isNotNull(),
               F.size(F.array_intersect("postores_a", "postores_b")) /
               F.size(F.array_union("postores_a", "postores_b"))))
           .withColumn("mismo_ganador", F.when(
               F.col("ganadores_a").isNotNull() & F.col("ganadores_b").isNotNull(),
               (F.size(F.array_intersect("ganadores_a", "ganadores_b")) > 0)
               .cast("int")))
           .withColumn("misma_entidad",
                       (F.col("buyer_name_a") == F.col("buyer_name_b")).cast("int"))
           .select("a", "b", "coseno", "tipo", "jac_postores", "mismo_ganador",
                   "misma_entidad"))
    df = res.toPandas()
    spark.stop()

    def tramo(c):
        if np.isnan(c):
            return "azar (misma categoria)"
        if c >= 0.95:
            return ">= 0,95"
        if c >= 0.8:
            return "0,80 - 0,95"
        if c >= 0.6:
            return "0,60 - 0,80"
        return "< 0,60"
    df["tramo"] = df["coseno"].apply(tramo)
    resumen = (df.groupby("tramo")
               .agg(pares=("a", "size"),
                    jac_postores_medio=("jac_postores", "mean"),
                    pct_mismo_ganador=("mismo_ganador", "mean"),
                    pct_misma_entidad=("misma_entidad", "mean"),
                    con_ganador=("mismo_ganador", "count"))
               .reset_index())
    for c in ("jac_postores_medio", "pct_mismo_ganador", "pct_misma_entidad"):
        resumen[c] = resumen[c].round(4)
    print(resumen.to_string(index=False))

    # Contraste de la pregunta P2: entre los vecinos casi identicos de
    # DISTINTA entidad, ¿cuantos comparten ganador?
    casi = df[(df["tipo"] == "vecino") & (df["coseno"] >= 0.8)]
    contraste = (casi.groupby("misma_entidad")
                 .agg(pares=("a", "size"), jac_postores_medio=("jac_postores", "mean"),
                      pct_mismo_ganador=("mismo_ganador", "mean"))
                 .reset_index())
    print(contraste.to_string(index=False))
    return resumen, contraste


def ejemplo_consulta(Z, docs, B_idx, q_idx, I_ex, D_ex):
    """Un par de consultas legibles para el reporte (sin RUC, solo texto)."""
    salida = []
    for qi in range(5):
        q = docs.loc[q_idx[qi]]
        vecinos = [{"texto": str(docs.loc[B_idx[I_ex[qi, j]], "texto"])[:160],
                    "entidad": str(docs.loc[B_idx[I_ex[qi, j]], "buyer_name"]),
                    "coseno": round(float(D_ex[qi, j]), 3)} for j in range(5)]
        salida.append({"consulta": str(q["texto"])[:160],
                       "entidad": str(q["buyer_name"]), "vecinos": vecinos})
    return salida


def vecinos_tfidf(Xn, q_idx, base_idx):
    """Top-K EXACTO por coseno sobre el TF-IDF completo (sin reducir).

    Es la referencia mas fiel de "que procesos se parecen", asi que la
    lectura de la pregunta P2 se hace sobre estos vecinos y no sobre los del
    espacio LSA: la conclusion no depende de la calidad de la SVD.
    """
    Xb = Xn[base_idx].T.tocsc()
    D = np.zeros((len(q_idx), K), np.float32)
    I = np.zeros((len(q_idx), K), np.int64)
    for i in range(0, len(q_idx), 50):
        S = (Xn[q_idx[i:i + 50]] @ Xb).toarray()
        top = np.argpartition(-S, K, axis=1)[:, :K]
        orden = np.argsort(-np.take_along_axis(S, top, 1), axis=1)
        I[i:i + 50] = np.take_along_axis(top, orden, 1)
        D[i:i + 50] = np.take_along_axis(S, I[i:i + 50], 1)
    return D, I


def main():
    pasos = sys.argv[1:]
    resumen = {}
    if "tfidf" in pasos or not (TFIDF / "tripletas").exists():
        resumen.update(tfidf_spark())
    elif (ARTEFACTOS / "p3_resumen.json").exists():
        previo = json.loads((ARTEFACTOS / "p3_resumen.json").read_text(encoding="utf8"))
        resumen.update({k: previo[k] for k in ("procesos", "documentos", "vocabulario",
                                              "no_ceros", "segundos_spark", "min_df",
                                              "max_df") if k in previo})

    import pandas as pd
    X, docs = cargar_matriz()
    Xn = normalizar_filas(X)
    U, var, seg_svd = lsa(Xn)
    q_idx, base_idx = particion(X.shape[0])
    curva = curva_dimensiones(X, U, var, q_idx, base_idx)
    exportar(pd.DataFrame(curva), "p3_curva_dimensiones.csv")
    if "solo-curva" in pasos:
        return

    Z = proyectar(U, DIM)
    resumen.update({"dim": DIM, "varianza_explicada": round(float(var[DIM - 1]), 4),
                    "segundos_svd": round(seg_svd, 1), "base": int(len(base_idx)),
                    "consultas": int(len(q_idx)), "k": K})
    filas = experimentos_ann(Z, q_idx, base_idx)
    exportar(pd.DataFrame(filas), "p3_ann_curvas.csv")

    titulo("5. Vecinos exactos sobre el TF-IDF completo (referencia para P2)")
    t0 = time.time()
    D_t, I_t = vecinos_tfidf(Xn, q_idx, base_idx)
    resumen["ms_consulta_tfidf_disperso"] = round(1000 * (time.time() - t0) / len(q_idx), 2)
    print(f"  {len(q_idx):,} consultas, {resumen['ms_consulta_tfidf_disperso']} ms por "
          f"consulta (producto disperso por lotes de 50, todos los hilos)")
    resumen["ejemplos"] = ejemplo_consulta(None, docs, base_idx, q_idx, I_t, D_t)

    pares = pares_vecinos(base_idx, q_idx, D_t, I_t, docs)
    r_p2, contraste = p2_postores_y_ganadores(pares, docs)
    exportar(r_p2, "p3_p2_vecinos_postores.csv")
    exportar(contraste, "p3_p2_contraste_entidad.csv")
    exportar(resumen, "p3_resumen.json")


if __name__ == "__main__":
    main()
