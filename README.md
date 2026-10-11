# Proyecto Integrador 1 — Minería de Datos Masivos y Flujos de Datos

Análisis de las **contrataciones públicas del Estado peruano** (estándar OCDS, OECE/SEACE, 2003-2026) con Apache Spark: KDD y EDA, similitud con MinHash y LSH, búsqueda aproximada de vecinos (IVF y HNSW), minería de flujos (Bloom, Count-Min Sketch, DGIM) y reglas de asociación (Apriori y FP-Growth). Los resultados se comunican en un **reporte web interactivo** (`web/index.html`).

## Fuente de datos

- **OECE** (ex OSCE) — Contrataciones Abiertas de la Compra Pública (OCDS): <https://contratacionesabiertas.oece.gob.pe/descargas>
- Descarga masiva vía **OCP Data Registry**, publicación 135: <https://data.open-contracting.org/es/publication/135>
- Licencia: **CC BY 4.0**. Los datos fueron transformados (descompresión, conversión a Parquet, agregación) con fines académicos.

Corpus (colección del 04/10/2026): 25 particiones anuales, 2 760 591 procesos y 46,5 millones de filas en 12 tablas (17 GB en CSV, 2,6 GB en Parquet), verificadas fila a fila contra lo que declara el publicador. Ventana analítica para competencia y montos: 2015-2026 (ver Parte I).

## Resultados principales

| Parte | Técnica | Hallazgo |
|---|---|---|
| I | EDA en Spark | El registro de postores cambia en 2015 (de 1,5-2,3 a 4-15 postores por proceso): la competencia se analiza solo sobre 2015-2026. El 1 % de las entidades concentra el 40,6 % del monto. RDD 58 veces más lento que DataFrame en la misma agregación. |
| II | MinHash + LSH propios | 589 224 pares de procesos casi idénticos (98 % de la misma entidad: reconvocatorias). 2 275 pares de proveedores acoplados; un grupo de 4 nunca se presenta por separado. |
| III | TF-IDF (Spark) + FAISS IVF/HNSW | IVF: recall 0,98 en 0,5 ms frente a 58 ms de la búsqueda exacta (120×). La pérdida real está en la reducción LSA (33 % del top 10 del TF-IDF). Procesos con texto casi idéntico comparten ganador en el 15 % de los casos frente al 0,02 % al azar. |
| IV | Bloom, Count-Min, DGIM propios | Bloom de 0,67 MB (100× menos que el set exacto) pierde el 0,41 % de alertas de proveedor nuevo; CMS de 512 KB recupera el 100 % del top 20; DGIM cuenta la ventana con 4-11 % de error usando el 2 % de la memoria. |
| V | Apriori (RDD) + FP-Growth | Mismos conjuntos que FP-Growth (19× más lento). 183 630 conjuntos maximales; grupos de 9-10 proveedores del sistema judicial ganan el 90-97 % frente al 32-41 % esperado. Parejas que coinciden en miles de procesos y no ganan nunca revelan registros pasivos en la tabla de postores. |
| VI | Discusión | Dentro de `web/index.html`: valor de cada técnica, costo de aproximar, Spark vs local, escala 10×/100× e implicancias éticas. |

## Estructura

```
data/                      Datos locales (NO versionados, ver .gitignore)
  raw/tar/                   particiones .csv.tar.gz descargadas
  raw/ocds/<AÑO>/            CSV descomprimidos
  derivados/parquet/         corpus en Parquet + representaciones
  derivados/artefactos/      agregados ligeros (CSV/JSON) que alimentan la web
informe/                   Informe de avance 1 (.docx) y figuras
web/                       Reporte técnico interactivo
  index.html                 página (metodología, hallazgos y discusión)
  assets/                    estilos, gráficos y lógica interactiva
  data/datos.js              artefactos empaquetados (generado por el paso 15)
scripts/
  entorno.py                 JDK/winutils, rutas de datos y SparkSession
  descargar_datos.py         [local] descarga y descompresión del corpus
  ejecutar_todo.py           [orquestador] corre el pipeline completo en orden
  04_verificar_entorno.py    [Spark] verifica Java, Spark, Parquet y MLlib
  05_ingesta_parquet.py      [Spark] CSV -> Parquet particionado por año de publicación
  06_verificar_ingesta.py    [Spark] contrasta conteos con los del publicador
  07_representaciones.py     [Spark] shingles por proceso, procesos por RUC y canastas
  08_eda_parte1.py           [Spark] Parte I: EDA y RDD vs DataFrame/SQL
  09_figuras.py              [local] figuras de la Parte I
  10_parte2_similitud.py     [Spark] Parte II: Jaccard, MinHash y LSH propios
  11_figuras_parte2.py       [local] figuras de la Parte II
  12_parte3_ann.py           [Spark + local] Parte III: TF-IDF en Spark, LSA, FAISS IVF/HNSW
  13_parte4_flujos.py        [Spark + local] Parte IV: Bloom, Count-Min Sketch y DGIM
  14_parte5_reglas.py        [Spark] Parte V: Apriori (RDD propio) y FP-Growth (MLlib)
  15_exportar_web.py         [local] empaqueta los artefactos para la web
  00..03                     perfilado inicial e informe de avance 1
```

Cada script indica en su cabecera qué corre en Spark (distribuido) y qué en local, y por qué.

## Reproducir

Requisitos: Python 3.10+ y JDK 17. En Windows, además `winutils.exe` y `hadoop.dll` en `~/tools/hadoop-<versión>/bin` (Spark los necesita para escribir Parquet en disco local).

```bash
python -m venv .venv
.venv/Scripts/python -m pip install pyspark==4.2.0 faiss-cpu==1.15.1 pandas pyarrow numpy scipy scikit-learn matplotlib python-docx requests
```

1. Descargar el corpus (~2,3 GB comprimidos, ~17 GB descomprimidos) en `data/raw/`:

```bash
.venv/Scripts/python scripts/descargar_datos.py
```

2. Ejecutar el pipeline completo (≈1,5 h en un portátil de 12 núcleos y 24 GB de RAM; la Parte II sola toma ~45 min):

```bash
.venv/Scripts/python scripts/ejecutar_todo.py            # pasos 04 a 15
.venv/Scripts/python scripts/ejecutar_todo.py --desde 12 # retomar desde un paso
```

Los registros de cada paso quedan en `data/derivados/logs/`. Las rutas de datos se pueden cambiar con las variables `OCDS_DATA` y `OCDS_DERIVED`.

## Ver el reporte web

El reporte no necesita servidor: `web/data/datos.js` ya trae los artefactos precalculados, de modo que basta con abrir `web/index.html` en el navegador (los gráficos usan Chart.js desde un CDN, así que requiere conexión). Para servirlo localmente:

```bash
python -m http.server 8000 --directory web
# y abrir http://localhost:8000
```

Arquitectura «calcular una vez, explorar muchas»: lo pesado corre en Spark una sola vez y se exporta como agregados ligeros; la página solo lee esos artefactos y recalcula en vivo las fórmulas analíticas de los compromisos (curva S de LSH, error de MinHash, falsos positivos de Bloom).

## Privacidad

Los artefactos con RUC y nombres de proveedores llevan el sufijo `_PRIVADO` y no se exportan a la web: el reporte usa etiquetas anónimas (`P0001`). Las técnicas producen indicios estadísticos de co-ocurrencia, no pruebas de irregularidad.

## Equipo

- César Pajuelo
- Aleksander Paico
