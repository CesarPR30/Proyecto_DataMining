# -*- coding: utf-8 -*-
"""
Configuracion del entorno de ejecucion de Spark para el proyecto.

Importar este modulo ANTES de importar pyspark. Localiza el JDK y el
HADOOP_HOME (winutils) aunque la terminal actual no tenga las variables de
entorno cargadas, de modo que los scripts corren igual desde cualquier consola,
IDE o notebook:

    from entorno import crear_spark
    spark = crear_spark("mi-app")

Variables que se pueden sobrescribir desde fuera:
    JAVA_HOME, HADOOP_HOME, OCDS_DATA, SPARK_DRIVER_MEMORY
"""
import os
import sys
from pathlib import Path

HERRAMIENTAS = Path.home() / "tools"
RAIZ = Path(__file__).resolve().parent.parent

# Raiz de los datos crudos: carpeta data/ del proyecto (ignorada por git).
# Si el proyecto vive en una carpeta sincronizada (OneDrive), conviene
# redirigirla fuera con OCDS_DATA / OCDS_DERIVED.
DATOS = Path(os.environ.get(
    "OCDS_DATA", str(RAIZ / "data" / "raw" / "ocds")))

# Raiz de los artefactos derivados (Parquet, agregados para la web)
DERIVADOS = Path(os.environ.get(
    "OCDS_DERIVED", str(RAIZ / "data" / "derivados")))


def _buscar(patron, marcador):
    """Primer directorio bajo ~/tools que coincide y contiene `marcador`."""
    for d in sorted(HERRAMIENTAS.glob(patron), reverse=True):
        if (d / marcador).exists():
            return d
    return None


def configurar(verbose=False):
    """Deja JAVA_HOME, HADOOP_HOME, PATH y PYSPARK_PYTHON listos."""
    if not os.environ.get("JAVA_HOME") or not Path(
            os.environ.get("JAVA_HOME", ""), "bin", "java.exe").exists():
        jdk = _buscar("jdk-*", Path("bin") / "java.exe")
        if jdk is None:
            raise RuntimeError(
                "No se encontro un JDK. Instalalo en ~/tools/jdk-<version> "
                "o define JAVA_HOME.")
        os.environ["JAVA_HOME"] = str(jdk)

    if not os.environ.get("HADOOP_HOME") or not Path(
            os.environ.get("HADOOP_HOME", ""), "bin", "winutils.exe").exists():
        hadoop = _buscar("hadoop-*", Path("bin") / "winutils.exe")
        if hadoop is not None:
            os.environ["HADOOP_HOME"] = str(hadoop)
        elif sys.platform == "win32":
            raise RuntimeError(
                "Falta winutils.exe: Spark no podra escribir Parquet en "
                "Windows. Instalalo en ~/tools/hadoop-<version>/bin.")

    rutas = [str(Path(os.environ["JAVA_HOME"]) / "bin")]
    if os.environ.get("HADOOP_HOME"):
        rutas.append(str(Path(os.environ["HADOOP_HOME"]) / "bin"))
    for r in rutas:
        if r not in os.environ["PATH"]:
            os.environ["PATH"] = r + os.pathsep + os.environ["PATH"]

    # Que los workers usen el mismo interprete que el driver
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    if verbose:
        print(f"JAVA_HOME   = {os.environ['JAVA_HOME']}")
        print(f"HADOOP_HOME = {os.environ.get('HADOOP_HOME', '(no definido)')}")
        print(f"datos       = {DATOS}")


def crear_spark(app="proyecto-integrador", memoria=None, particiones=16,
                verbose=False):
    """SparkSession local con los ajustes por defecto del proyecto."""
    configurar(verbose=verbose)
    from pyspark.sql import SparkSession

    memoria = memoria or os.environ.get("SPARK_DRIVER_MEMORY", "6g")
    spark = (SparkSession.builder
             .appName(app)
             .master("local[*]")
             .config("spark.driver.memory", memoria)
             .config("spark.sql.shuffle.partitions", str(particiones))
             .config("spark.sql.session.timeZone", "America/Lima")
             .config("spark.ui.showConsoleProgress", "false")
             # el dataset trae comillas y saltos de linea dentro de los campos
             .config("spark.sql.parquet.compression.codec", "snappy")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def leer_csv(spark, ruta):
    """Lector de CSV con las opciones que exige este dataset."""
    return (spark.read
            .option("header", True)
            .option("multiLine", True)
            .option("escape", '"')
            .option("mode", "PERMISSIVE")
            .csv(str(ruta)))


if __name__ == "__main__":
    configurar(verbose=True)
