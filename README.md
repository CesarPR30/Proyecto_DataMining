# Proyecto Integrador 1 — Minería de Datos Masivos y Flujos de Datos

Análisis de las **contrataciones públicas del Estado peruano** (estándar OCDS, OECE/SEACE, 2003-2026) con Apache Spark: KDD y EDA, similitud con MinHash y LSH, búsqueda aproximada de vecinos, minería de flujos y reglas de asociación.

## Fuente de datos

- **OECE** (ex OSCE) — Contrataciones Abiertas de la Compra Pública (OCDS): <https://contratacionesabiertas.oece.gob.pe/descargas>
- Descarga masiva vía **OCP Data Registry**, publicación 135: <https://data.open-contracting.org/es/publication/135>
- Licencia: **CC BY 4.0**. Los datos fueron transformados (descompresión, conversión a Parquet, agregación) con fines académicos.

Corpus: 25 particiones anuales, 2 753 905 procesos, 46,3 millones de filas en 12 tablas (17 GB en CSV, 2,6 GB en Parquet).

## Estructura

```
informe/                 Informe de avance (.docx) y figuras
scripts/
  entorno.py             Localiza JDK y winutils y crea la SparkSession
  00_perfilado_dataset.py    Perfilado local de una partición (criterios C1-C4)
  01_prueba_viabilidad.py    Prueba de señal de las técnicas del curso
  02_figuras_informe.py      (sustituido por 09) figuras con pandas
  03_generar_informe_docx.py Ensambla el informe
  04_verificar_entorno.py    Verifica Java, Spark, Parquet y MLlib
  05_ingesta_parquet.py      CSV -> Parquet particionado por año de publicación
  06_verificar_ingesta.py    Contrasta conteos con los del publicador
  07_representaciones.py     Shingles por proceso, procesos por RUC y canastas
  08_eda_parte1.py           Parte I: EDA en Spark y RDD vs DataFrame/SQL
  09_figuras.py              Figuras de la Parte I desde los artefactos
  10_parte2_similitud.py     Parte II: Jaccard, MinHash, LSH (etapas A..E)
  11_figuras_parte2.py       Figuras de la Parte II
```

Los datos **no** se versionan: viven en `~/Proyecto-DataMining-data` (`raw/` y `derivados/`).

## Reproducir

Requisitos: Python 3.10+, JDK 17, `pip install pyspark pyarrow pandas matplotlib python-docx`. En Windows, además `winutils.exe` y `hadoop.dll` en `~/tools/hadoop-<versión>/bin` (necesarios para que Spark escriba Parquet).

1. Descargar las particiones anuales en `~/Proyecto-DataMining-data/raw/ocds/` y descomprimirlas:
   `https://data.open-contracting.org/en/publication/135/download?name=<AÑO>.csv.tar.gz`
2. Ejecutar en orden:

```bash
python scripts/04_verificar_entorno.py
python scripts/05_ingesta_parquet.py
python scripts/06_verificar_ingesta.py
python scripts/07_representaciones.py
python scripts/08_eda_parte1.py
python scripts/09_figuras.py
python scripts/10_parte2_similitud.py      # o solo algunas etapas: ... D E
python scripts/11_figuras_parte2.py
python scripts/03_generar_informe_docx.py
```

Las rutas de datos se pueden cambiar con las variables `OCDS_DATA` y `OCDS_DERIVED`.

## Equipo

- [Integrante 1]
- [Integrante 2]
- [Integrante 3]
