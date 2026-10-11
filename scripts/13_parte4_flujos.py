# -*- coding: utf-8 -*-
"""
Parte IV: mineria de flujos con Bloom Filter, Count-Min Sketch y DGIM.

Pregunta P3: ¿se puede vigilar el flujo de contrataciones en una sola pasada
y con memoria acotada sin perder las alertas que daria el conteo exacto?

Donde corre cada paso y por que:

  SPARK (distribuido)
    - Ordenar los ~880 mil procesos y los ~9 millones de postulaciones de
      2015-2026 por fecha de publicacion: es un sort global sobre la tabla
      mas grande del corpus.
    - Calcular la VERDAD EXACTA contra la que se mide cada estructura:
      primera aparicion de cada RUC (row_number por clave), conteo exacto por
      RUC y por entidad (groupBy) y conteo exacto en ventana deslizante
      (funcion de ventana rowsBetween). Es lo que un analista haria "sin
      restricciones de memoria", y es lo que el sketch intenta evitar.

  LOCAL (Python, una sola pasada)
    - Las tres estructuras se implementan desde cero, procesando el flujo
      elemento a elemento en orden de llegada: es la semantica de un flujo y
      no tiene sentido distribuirla (el objetivo es justamente que quepa en
      la memoria de UNA maquina).
    - Para barrer muchos parametros (m, k, w, d) sin repetir 9 millones de
      iteraciones por configuracion, se usan formulas vectorizadas que dan
      EXACTAMENTE el mismo resultado que la pasada secuencial; la igualdad se
      verifica en este mismo script para una configuracion de cada estructura.

Funciones hash: doble hashing de Kirsch-Mitzenmacher, g_i(x) = h1(x) + i*h2(x)
mod m, con h1 y h2 dos SipHash de 64 bits con claves distintas. Da k funciones
de la calidad de un hash de 64 bits sin calcular k hashes, y evita el piso de
colisiones que tendria reducir la clave a 31 bits.

Uso:  python scripts/13_parte4_flujos.py           # todo
      python scripts/13_parte4_flujos.py local     # reutiliza el flujo exportado
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno  # noqa: E402

entorno.configurar()

PARQUET = entorno.DERIVADOS / "parquet"
ARTEFACTOS = entorno.DERIVADOS / "artefactos"
FLUJO = PARQUET / "p4_flujo"

ANIO_DESDE = 2015
UMBRAL_MONTO = 1_000_000              # S/: "proceso de monto alto" para DGIM
VENTANAS = (1000, 4000, 10000, 50000)  # ~134 procesos/dia habil -> 4000 ~ 1 mes
CLAVE_H1 = "proyecto-ocds-h1"          # SipHash necesita claves de 16 bytes
CLAVE_H2 = "proyecto-ocds-h2"
MASCARA64 = (1 << 64) - 1              # para que Python envuelva como numpy


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


# ===================================================== 1. el flujo en Spark
def preparar_flujo():
    titulo("1. Flujo ordenado y verdad exacta (Spark)")
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    spark = entorno.crear_spark("p4-flujo", memoria="8g", particiones=64)
    t0 = time.time()
    m = (spark.read.parquet(str(PARQUET / "repr_proceso"))
         .where((F.col("anio") >= ANIO_DESDE)))
    fechas = (spark.read.parquet(str(PARQUET / "main"))
              .where(F.col("anio") >= ANIO_DESDE)
              .select("ocid", "fecha").where(F.col("fecha").isNotNull()))

    # ---- flujo de procesos: un evento por proceso publicado
    proc = (m.join(fechas, "ocid")
            .select("ocid", "fecha", "buyer_name", "monto_pen", "categoria",
                    # clave de reconvocatoria: misma entidad + mismo texto
                    F.xxhash64("buyer_name", "texto").alias("clave_texto"))
            .withColumn("pos", F.row_number().over(Window.orderBy("fecha", "ocid")) - 1)
            .withColumn("alto", (F.coalesce(F.col("monto_pen"), F.lit(0))
                                 >= UMBRAL_MONTO).cast("int")))
    # Exacto para DGIM: cuantos "altos" hay en los ultimos N procesos.
    # NO se usa sum().over(rowsBetween(-(N-1), 0)): con un marco deslizante
    # Spark recalcula la suma entera del marco en cada fila, O(n*N); con
    # N = 50 000 son ~44 mil millones de sumas y la etapa no termina. Se usa
    # la identidad conteo(t-N+1..t) = acumulado(t) - acumulado(t-N), que solo
    # necesita una suma acumulada (marco creciente, O(n)) y un lag.
    # Ventana sin particion: una sola tarea, aceptable para 880 mil filas.
    w_orden = Window.orderBy("pos")
    proc = proc.withColumn("_acum", F.sum("alto").over(
        w_orden.rowsBetween(Window.unboundedPreceding, 0)))
    for n in VENTANAS:
        proc = proc.withColumn(f"exacto_{n}", F.col("_acum") -
                               F.lag("_acum", n, 0).over(w_orden))
    proc = proc.drop("_acum")
    # Exacto para Bloom (tarea B): ¿este texto ya se publico antes en la
    # misma entidad? -> reconvocatoria
    proc = proc.withColumn("visto_antes", (F.row_number().over(
        Window.partitionBy("clave_texto").orderBy("pos")) > 1).cast("int"))
    proc.coalesce(1).sortWithinPartitions("pos").write.mode("overwrite") \
        .parquet(str(FLUJO / "procesos"))

    # ---- flujo de postulaciones: un evento por (proceso, postor)
    post = (spark.read.parquet(str(PARQUET / "tender_tenderers"))
            .where(F.col("anio") >= ANIO_DESDE)
            .select(F.col("main_ocid").alias("ocid"), F.col("id").alias("ruc"))
            .where(F.col("ruc").isNotNull()).distinct()
            .join(fechas, "ocid")
            .withColumn("pos", F.row_number().over(
                Window.orderBy("fecha", "ocid", "ruc")) - 1)
            # Exacto para Bloom (tarea A): ¿este RUC ya postulo antes?
            .withColumn("visto_antes", (F.row_number().over(
                Window.partitionBy("ruc").orderBy("pos")) > 1).cast("int")))
    post.select("pos", "fecha", "ruc", "visto_antes").coalesce(1) \
        .sortWithinPartitions("pos").write.mode("overwrite") \
        .parquet(str(FLUJO / "postulaciones"))

    # ---- conteos exactos para Count-Min Sketch
    (post.groupBy("ruc").count().write.mode("overwrite")
     .parquet(str(FLUJO / "exacto_ruc")))
    (proc.groupBy("buyer_name").count().write.mode("overwrite")
     .parquet(str(FLUJO / "exacto_entidad")))
    seg = time.time() - t0
    n_p = spark.read.parquet(str(FLUJO / "procesos")).count()
    n_q = spark.read.parquet(str(FLUJO / "postulaciones")).count()
    print(f"  procesos: {n_p:,}  postulaciones: {n_q:,}  ({seg:.0f} s en Spark)")
    spark.stop()
    return {"spark_segundos": round(seg, 1)}


# =================================================================== hashes
def hashes(claves):
    """h1, h2 de 64 bits por clave (SipHash con dos claves distintas)."""
    v = pd.Series(claves).astype(str).values
    h1 = pd.util.hash_array(v, hash_key=CLAVE_H1, categorize=True).astype(np.uint64)
    h2 = pd.util.hash_array(v, hash_key=CLAVE_H2, categorize=True).astype(np.uint64)
    return h1, h2 | np.uint64(1)          # h2 impar: recorre todas las posiciones


def posiciones(h1, h2, i, m):
    """g_i(x) = (h1 + i*h2) mod m, con aritmetica de 64 bits que envuelve."""
    with np.errstate(over="ignore"):
        return ((h1 + np.uint64(i) * h2) % np.uint64(m)).astype(np.int64)


# ============================================================== Bloom Filter
class BloomFilter:
    """Bloom Filter clasico: m bits, k funciones hash. Sin falsos negativos."""

    def __init__(self, m, k):
        self.m, self.k = m, k
        self.bits = bytearray((m + 7) // 8)

    def _pos(self, h1, h2):
        return [((h1 + i * h2) & MASCARA64) % self.m for i in range(self.k)]

    def consultar_e_insertar(self, h1, h2):
        """True si el elemento PARECIA visto; luego lo inserta."""
        visto = True
        for p in self._pos(h1, h2):
            byte, bit = p >> 3, 1 << (p & 7)
            if not self.bits[byte] & bit:
                visto = False
                self.bits[byte] |= bit
        return visto

    def bytes(self):
        return len(self.bits)


def bloom_vectorizado(h1, h2, primera, n_eventos, m, k):
    """Falsos positivos de una pasada secuencial, sin el bucle.

    Un bit b se enciende por primera vez en el instante primer[b] = minima
    primera aparicion de las claves que lo usan. Cuando una clave aparece por
    primera vez en t, el filtro responde "visto" si y solo si sus k bits ya
    estaban encendidos antes de t, es decir max_i primer[g_i(x)] < t. Las
    reapariciones siempre dan "visto" (no hay falsos negativos), asi que el
    error solo puede ocurrir en primeras apariciones.
    """
    primer = np.full(m, np.iinfo(np.int64).max, dtype=np.int64)
    pos = [posiciones(h1, h2, i, m) for i in range(k)]
    for p in pos:
        np.minimum.at(primer, p, primera)
    peor = np.max(np.stack([primer[p] for p in pos]), axis=0)
    fp = int((peor < primera).sum())
    return fp


def experimento_bloom(eventos, nombre_tarea):
    """eventos: DataFrame en orden de llegada con 'clave' y 'visto_antes'."""
    titulo(f"2. Bloom Filter - {nombre_tarea}")
    claves = eventos["clave"].values
    n = len(claves)
    # Distintas con su primera aparicion (verdad exacta de Spark)
    nuevos = eventos[eventos["visto_antes"] == 0]
    distintos = nuevos["clave"].values
    primera = nuevos.index.values.astype(np.int64)
    n_dist = len(distintos)
    print(f"  eventos: {n:,}  claves distintas: {n_dist:,}  "
          f"reapariciones: {n - n_dist:,} ({100*(n-n_dist)/n:.1f} %)")
    h1, h2 = hashes(distintos)

    filas = []
    for bits_por_clave in (1, 2, 4, 6, 8, 10, 12, 16, 20):
        m = int(bits_por_clave * n_dist)
        k_opt = max(1, round(m / n_dist * math.log(2)))
        for k in sorted({1, 2, 3, 4, 6, 8, k_opt}):
            fp = bloom_vectorizado(h1, h2, primera, n, m, k)
            teorico = (1 - math.exp(-k * n_dist / m)) ** k
            filas.append({"bits_por_clave": bits_por_clave, "m_bits": m,
                          "mb": round(m / 8 / 1024 ** 2, 3), "k": k,
                          "k_optimo": int(k == k_opt), "fp": fp,
                          "tasa_fp": round(fp / n_dist, 6),
                          "tasa_fp_teorica_final": round(teorico, 6)})
    tabla = pd.DataFrame(filas)
    opt = tabla[tabla["k_optimo"] == 1]
    print(opt[["bits_por_clave", "mb", "k", "tasa_fp", "tasa_fp_teorica_final"]]
          .to_string(index=False))

    # ---- validacion: la pasada secuencial real da el mismo numero de FP
    m_val, k_val = int(8 * n_dist), 6
    H1, H2 = hashes(claves)
    H1, H2 = H1.tolist(), H2.tolist()
    bf = BloomFilter(m_val, k_val)
    vistos_exactos = set()
    t0 = time.perf_counter()
    respuestas = [bf.consultar_e_insertar(a, b) for a, b in zip(H1, H2)]
    t_bloom = time.perf_counter() - t0
    t0 = time.perf_counter()
    for c in claves:
        vistos_exactos.add(c)
    t_set = time.perf_counter() - t0
    resp = np.array(respuestas)
    verdad = eventos["visto_antes"].values.astype(bool)
    fp_seq = int((resp & ~verdad).sum())
    fn_seq = int((~resp & verdad).sum())
    fp_vec = bloom_vectorizado(h1, h2, primera, n, m_val, k_val)
    print(f"  validacion m={m_val:,} k={k_val}: secuencial FP={fp_seq:,} FN={fn_seq} "
          f"| vectorizado FP={fp_vec:,}  -> {'IGUALES' if fp_seq == fp_vec else 'DISTINTOS'}")
    mem_set = sys.getsizeof(vistos_exactos) + sum(sys.getsizeof(c) for c in vistos_exactos)
    resumen = {
        "tarea": nombre_tarea, "eventos": n, "distintos": n_dist,
        "validacion": {"m_bits": m_val, "k": k_val, "fp_secuencial": fp_seq,
                       "fn_secuencial": fn_seq, "fp_vectorizado": fp_vec},
        "memoria_bloom_mb": round(bf.bytes() / 1024 ** 2, 3),
        "memoria_set_exacto_mb": round(mem_set / 1024 ** 2, 1),
        "us_por_evento_bloom": round(1e6 * t_bloom / n, 3),
        "us_por_evento_set": round(1e6 * t_set / n, 3),
    }
    print(f"  memoria: Bloom {resumen['memoria_bloom_mb']} MB vs set exacto "
          f"{resumen['memoria_set_exacto_mb']} MB | tiempo: "
          f"{resumen['us_por_evento_bloom']} vs {resumen['us_por_evento_set']} us/evento")
    return tabla, resumen


# ========================================================== Count-Min Sketch
class CountMinSketch:
    def __init__(self, w, d):
        self.w, self.d = w, d
        self.tabla = np.zeros((d, w), dtype=np.int64)

    def agregar(self, h1, h2, c=1):
        for i in range(self.d):
            self.tabla[i, ((h1 + i * h2) & MASCARA64) % self.w] += c

    def estimar(self, h1, h2):
        return min(int(self.tabla[i, ((h1 + i * h2) & MASCARA64) % self.w])
                   for i in range(self.d))


def cms_vectorizado(h1, h2, conteos, w, d):
    """Tabla final identica a la de la pasada secuencial (la suma conmuta)."""
    est = None
    for i in range(d):
        p = posiciones(h1, h2, i, w)
        fila = np.bincount(p, weights=conteos, minlength=w)
        e = fila[p]
        est = e if est is None else np.minimum(est, e)
    return est.astype(np.int64)


def experimento_cms(exacto, eventos_claves, nombre):
    titulo(f"3. Count-Min Sketch - {nombre}")
    claves = exacto["clave"].values
    reales = exacto["count"].values.astype(np.int64)
    N = int(reales.sum())
    h1, h2 = hashes(claves)
    orden = np.argsort(-reales)
    top = orden[:100]
    print(f"  N = {N:,} eventos, {len(claves):,} claves distintas")
    filas = []
    for w in (2 ** e for e in range(6, 18)):
        for d in (1, 2, 3, 4, 5, 6, 8):
            est = cms_vectorizado(h1, h2, reales, w, d)
            err = est - reales                       # siempre >= 0
            eps, delta = math.e / w, math.exp(-d)
            top_est = set(np.argsort(-est)[:20])
            filas.append({
                "w": w, "d": d, "kb": round(w * d * 8 / 1024, 1),
                "error_medio": round(float(err.mean()), 3),
                "error_rel_top100": round(float((err[top] / reales[top]).mean()), 5),
                "error_rel_medio": round(float((err / reales).mean()), 4),
                "pct_dentro_cota": round(float((err <= eps * N).mean()), 5),
                "cota_eps_N": round(eps * N, 1), "delta": round(delta, 4),
                "recall_top20": len(top_est & set(orden[:20])) / 20})
    tabla = pd.DataFrame(filas)
    print(tabla[tabla["d"] == 4][["w", "kb", "error_medio", "error_rel_top100",
                                  "error_rel_medio", "pct_dentro_cota",
                                  "recall_top20"]].to_string(index=False))

    # ---- validacion secuencial en una configuracion
    w_val, d_val = 2 ** 14, 4
    H1, H2 = hashes(eventos_claves)
    cms = CountMinSketch(w_val, d_val)
    t0 = time.perf_counter()
    for a, b in zip(H1.tolist(), H2.tolist()):
        cms.agregar(a, b)
    t_cms = time.perf_counter() - t0
    exacto_dict = {}
    t0 = time.perf_counter()
    for c in eventos_claves:
        exacto_dict[c] = exacto_dict.get(c, 0) + 1
    t_dict = time.perf_counter() - t0
    est_vec = cms_vectorizado(h1, h2, reales, w_val, d_val)
    est_seq = np.array([cms.estimar(a, b) for a, b in zip(h1.tolist(), h2.tolist())])
    iguales = bool((est_vec == est_seq).all())
    mem_dict = (sys.getsizeof(exacto_dict) +
                sum(sys.getsizeof(k) + 28 for k in exacto_dict))
    print(f"  validacion w={w_val} d={d_val}: secuencial == vectorizado -> {iguales}")
    resumen = {"N": N, "distintos": int(len(claves)),
               "validacion_iguales": iguales,
               "memoria_cms_kb": round(cms.tabla.nbytes / 1024, 1),
               "memoria_dict_exacto_mb": round(mem_dict / 1024 ** 2, 1),
               "us_por_evento_cms": round(1e6 * t_cms / len(eventos_claves), 3),
               "us_por_evento_dict": round(1e6 * t_dict / len(eventos_claves), 3)}
    print(f"  memoria: CMS {resumen['memoria_cms_kb']} KB vs dict exacto "
          f"{resumen['memoria_dict_exacto_mb']} MB")
    # Heavy hitters de la configuracion validada, para el reporte (anonimos)
    hh = pd.DataFrame({"rank": np.arange(1, 21), "exacto": reales[orden[:20]],
                       "estimado": est_vec[orden[:20]]})
    return tabla, resumen, hh


# ===================================================================== DGIM
class DGIM:
    """Conteo de unos en los ultimos N bits con O(r log^2 N) bits de memoria.

    Cubetas (marca_de_tiempo, tamanio) con tamanios potencia de 2; se admiten
    hasta r cubetas del mismo tamanio (r = 2 es el DGIM clasico). Al llegar
    la r+1-esima se fusionan las dos mas antiguas. La estimacion suma todas
    las cubetas menos la mitad de la mas antigua.
    """

    def __init__(self, N, r=2):
        self.N, self.r = N, r
        self.cubetas = []        # de la mas reciente a la mas antigua
        self.t = 0
        self.max_cubetas = 0

    def agregar(self, bit):
        self.t += 1
        if self.cubetas and self.cubetas[-1][0] <= self.t - self.N:
            self.cubetas.pop()           # la mas antigua salio de la ventana
        if not bit:
            return
        self.cubetas.insert(0, (self.t, 1))
        tam, i = 1, 0
        while True:
            mismos = [j for j in range(i, len(self.cubetas))
                      if self.cubetas[j][1] == tam]
            if len(mismos) <= self.r:
                break
            a, b = mismos[-2], mismos[-1]          # las dos mas antiguas
            self.cubetas[a] = (self.cubetas[a][0], 2 * tam)
            del self.cubetas[b]
            tam, i = 2 * tam, a
        self.max_cubetas = max(self.max_cubetas, len(self.cubetas))

    def estimar(self):
        if not self.cubetas:
            return 0
        total = sum(s for _, s in self.cubetas)
        return total - self.cubetas[-1][1] // 2

    def bits_memoria(self):
        # cada cubeta guarda su marca (log2 N bits) y log2(tamanio) (log2 log2 N)
        return self.max_cubetas * (math.ceil(math.log2(self.N)) +
                                   math.ceil(math.log2(math.log2(self.N) + 1)))


def experimento_dgim(procesos):
    titulo(f"4. DGIM - procesos de monto >= S/ {UMBRAL_MONTO:,} en la ventana")
    bits = procesos["alto"].values.astype(int)
    print(f"  {len(bits):,} bits, {bits.mean()*100:.1f} % son 1")
    filas, series = [], []
    paso = 1000
    for N in VENTANAS:
        exacto = procesos[f"exacto_{N}"].values
        for r in (2, 3, 5):
            dg = DGIM(N, r)
            est = np.empty(len(bits), dtype=np.int64)
            t0 = time.perf_counter()
            for i, b in enumerate(bits):
                dg.agregar(b)
                est[i] = dg.estimar()
            seg = time.perf_counter() - t0
            validos = np.arange(len(bits)) >= N   # ventana ya llena
            e, x = est[validos], exacto[validos]
            rel = np.abs(e - x) / np.maximum(x, 1)
            filas.append({"N": N, "r": r, "error_rel_medio": round(float(rel.mean()), 4),
                          "error_rel_max": round(float(rel.max()), 4),
                          "cota_teorica": round(1 / (r - 1) if r > 2 else 0.5, 3),
                          "max_cubetas": dg.max_cubetas,
                          "bits_memoria": dg.bits_memoria(),
                          "bits_exacto": N, "us_por_bit": round(1e6 * seg / len(bits), 2)})
            idx = np.arange(N, len(bits), paso)
            series.append({"N": N, "r": r, "pos": idx.tolist(),
                           "estimado": est[idx].tolist(), "exacto": exacto[idx].tolist()})
            print(f"  N={N:6d} r={r}: error rel medio {rel.mean():.3f}  max "
                  f"{rel.max():.3f}  memoria {dg.bits_memoria():,} bits vs {N:,}")
    fechas = procesos["fecha"].iloc[np.arange(0, len(bits), paso)]
    return pd.DataFrame(filas), series, [str(f)[:10] for f in fechas]


def main():
    resumen = {}
    if "local" not in sys.argv[1:] or not (FLUJO / "postulaciones").exists():
        resumen.update(preparar_flujo())

    procesos = pd.read_parquet(FLUJO / "procesos").sort_values("pos") \
        .reset_index(drop=True)
    post = pd.read_parquet(FLUJO / "postulaciones").sort_values("pos") \
        .reset_index(drop=True)

    # ---- Bloom A: ¿el RUC ya postulo antes? (proveedor nuevo vs recurrente)
    ev = post.rename(columns={"ruc": "clave"})[["clave", "visto_antes"]]
    tabla_a, res_a = experimento_bloom(ev, "RUC que reaparece (proveedor recurrente)")
    tabla_a["tarea"] = "ruc"
    # ---- Bloom B: ¿texto + entidad ya publicado? (reconvocatoria)
    ev = procesos.rename(columns={"clave_texto": "clave"})[["clave", "visto_antes"]]
    tabla_b, res_b = experimento_bloom(ev, "Texto ya publicado por la entidad (reconvocatoria)")
    tabla_b["tarea"] = "reconvocatoria"
    exportar(pd.concat([tabla_a, tabla_b]), "p4_bloom.csv")
    resumen["bloom"] = [res_a, res_b]

    # ---- Count-Min Sketch: frecuencia de postulaciones por RUC
    ex = pd.read_parquet(FLUJO / "exacto_ruc").rename(columns={"ruc": "clave"})
    tabla_c, res_c, hh = experimento_cms(ex, post["ruc"].values, "postulaciones por RUC")
    tabla_c["tarea"] = "ruc"
    ex2 = pd.read_parquet(FLUJO / "exacto_entidad").dropna() \
        .rename(columns={"buyer_name": "clave"})
    tabla_d, res_d, _ = experimento_cms(ex2, procesos["buyer_name"].dropna().values,
                                        "procesos por entidad")
    tabla_d["tarea"] = "entidad"
    exportar(pd.concat([tabla_c, tabla_d]), "p4_cms.csv")
    exportar(hh, "p4_cms_heavy_hitters.csv")
    resumen["cms"] = [dict(res_c, tarea="ruc"), dict(res_d, tarea="entidad")]

    # ---- DGIM
    tabla_e, series, fechas = experimento_dgim(procesos)
    exportar(tabla_e, "p4_dgim.csv")
    exportar({"paso": 1000, "fechas": fechas, "series": series}, "p4_dgim_series.json")
    resumen["dgim"] = {"umbral_monto": UMBRAL_MONTO,
                       "pct_altos": round(float(procesos["alto"].mean()), 4),
                       "procesos": int(len(procesos))}
    exportar(resumen, "p4_resumen.json")


if __name__ == "__main__":
    main()
