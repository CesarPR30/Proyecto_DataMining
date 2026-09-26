# -*- coding: utf-8 -*-
"""
Verifica que el entorno de ejecucion del proyecto esta completo y funcional.

Comprueba, en este orden:
  1. Java (JDK 17) y las variables JAVA_HOME / HADOOP_HOME.
  2. Arranque de una SparkSession local y lectura de un CSV real del dataset.
  3. Escritura y relectura de Parquet (requiere winutils.exe en Windows).
  4. Las piezas de MLlib de las que dependen las Partes II y V:
     MinHashLSH y FPGrowth, ejecutadas sobre datos reales del corpus.
  5. Inventario de las particiones descargadas.

Uso:  python scripts/04_verificar_entorno.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno                      # configura JAVA_HOME / HADOOP_HOME / PATH

entorno.configurar()
DATOS = entorno.DATOS
ANIO_PRUEBA = "2025"

ok_total = True


def check(nombre, condicion, detalle=""):
    global ok_total
    marca = "OK  " if condicion else "FALLA"
    ok_total = ok_total and bool(condicion)
    print(f"  [{marca}] {nombre}" + (f" - {detalle}" if detalle else ""))
    return condicion


def seccion(titulo):
    print(f"\n{titulo}\n" + "-" * len(titulo))


def main():
    seccion("1. Java y variables de entorno")
    java_home = os.environ.get("JAVA_HOME", "")
    hadoop_home = os.environ.get("HADOOP_HOME", "")
    check("JAVA_HOME definido", bool(java_home), java_home)
    check("HADOOP_HOME definido", bool(hadoop_home), hadoop_home)
    java = shutil.which("java")
    check("java en el PATH", bool(java), java or "no encontrado")
    if java:
        ver = subprocess.run([java, "-version"], capture_output=True, text=True)
        linea = (ver.stderr or ver.stdout).splitlines()[0]
        check("version de Java 17+", '"17' in linea or '"21' in linea, linea)
    if hadoop_home:
        check("winutils.exe presente",
              (Path(hadoop_home) / "bin" / "winutils.exe").exists())

    seccion("2. SparkSession y lectura del dataset")
    from pyspark.sql import functions as F

    spark = entorno.crear_spark("verificacion-entorno")
    print(f"  Spark {spark.version} | nucleos {spark.sparkContext.defaultParallelism}")

    base = DATOS / ANIO_PRUEBA
    main_csv = base / "main.csv"
    check(f"main.csv de {ANIO_PRUEBA} existe", main_csv.exists(), str(main_csv))

    df = entorno.leer_csv(spark, main_csv)
    n = df.count()
    check("lectura de CSV con Spark", n > 100000, f"{n:,} filas")

    seccion("3. Escritura y relectura de Parquet")
    salida = DATOS.parent / "_verificacion_parquet"
    (df.select("ocid", "buyer_name", "tender_datePublished")
       .write.mode("overwrite").parquet(str(salida)))
    n2 = spark.read.parquet(str(salida)).count()
    check("escritura/relectura de Parquet", n2 == n, f"{n2:,} filas")
    shutil.rmtree(salida, ignore_errors=True)

    seccion("4. MLlib: piezas de las Partes II y V")
    postores = entorno.leer_csv(spark, base / "tender_tenderers.csv")
    canastas = (postores.groupBy("main_ocid")
                .agg(F.collect_set("id").alias("ruc"))
                .where(F.size("ruc").between(2, 40)))
    canastas.cache()
    n_can = canastas.count()
    print(f"  canastas 'proceso -> postores': {n_can:,}")

    # --- Parte V: FP-Growth
    from pyspark.ml.fpm import FPGrowth
    fp = FPGrowth(itemsCol="ruc", minSupport=0.004, minConfidence=0.3)
    modelo = fp.fit(canastas)
    n_frec = modelo.freqItemsets.count()
    n_reglas = modelo.associationRules.count()
    check("FPGrowth ejecuta", n_frec > 0,
          f"{n_frec:,} conjuntos frecuentes, {n_reglas:,} reglas")
    if n_reglas:
        print("  regla de mayor lift:")
        r = modelo.associationRules.orderBy(F.desc("lift")).first()
        print(f"    {r['antecedent']} -> {r['consequent']}  "
              f"conf={r['confidence']:.3f} lift={r['lift']:.1f}")

    # --- Parte II: MinHashLSH sobre proveedor -> conjunto de procesos
    from pyspark.ml.feature import MinHashLSH, CountVectorizer
    proveedores = (postores.groupBy("id")
                   .agg(F.collect_set("main_ocid").alias("procesos"))
                   .where(F.size("procesos") >= 10))
    cv = CountVectorizer(inputCol="procesos", outputCol="vec", binary=True,
                         minDF=1.0)
    cv_m = cv.fit(proveedores)
    vect = cv_m.transform(proveedores).where(F.size("procesos") > 0)
    mh = MinHashLSH(inputCol="vec", outputCol="firma", numHashTables=8, seed=42)
    mh_m = mh.fit(vect)
    pares = (mh_m.approxSimilarityJoin(vect, vect, 0.6, distCol="dist")
             .where(F.col("datasetA.id") < F.col("datasetB.id")))
    n_pares = pares.count()
    check("MinHashLSH ejecuta", n_pares >= 0,
          f"{n_pares:,} pares candidatos con Jaccard >= 0,4")
    if n_pares:
        p0 = pares.orderBy("dist").first()
        print(f"  par mas similar: {p0['datasetA']['id']} <-> "
              f"{p0['datasetB']['id']}  Jaccard={1 - p0['dist']:.3f}")

    seccion("5. Inventario de particiones descargadas")
    dirs = sorted(d for d in DATOS.glob("[0-9][0-9][0-9][0-9]") if d.is_dir())
    total_csv = sum(len(list(d.glob("*.csv"))) for d in dirs)
    peso = sum(f.stat().st_size for d in dirs for f in d.glob("*.csv"))
    check("particiones descomprimidas", len(dirs) >= 24, f"{len(dirs)} particiones")
    print(f"  archivos CSV: {total_csv:,} | peso total: {peso / 1024**3:.1f} GB")
    faltan = [d.name for d in dirs if not (d / "main.csv").exists()]
    check("todas tienen main.csv", not faltan, f"faltan en {faltan}" if faltan else "")

    spark.stop()
    print("\n" + ("ENTORNO LISTO" if ok_total else "HAY FALLAS - revisar arriba"))
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
