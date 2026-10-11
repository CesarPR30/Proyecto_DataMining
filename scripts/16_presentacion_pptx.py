# -*- coding: utf-8 -*-
"""
Genera la presentacion de resultados (presentacion/Presentacion_Proyecto_Integrador.pptx).

LOCAL, sin Spark: lee las cifras ya exportadas en web/data/datos.js (las
mismas del reporte web) y arma los graficos como graficos nativos de
PowerPoint, editables. Cada diapositiva lleva el guion en las notas del orador.

Uso:  python scripts/16_presentacion_pptx.py
"""
import json
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_AXIS_CROSSES, XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt, Emu

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "presentacion" / "Presentacion_Proyecto_Integrador.pptx"

_s = (RAIZ / "web" / "data" / "datos.js").read_text(encoding="utf-8")
D = json.loads(_s[_s.index("{"):_s.rindex("}") + 1])

# ---------------------------------------------------------------- estilo
TINTA = RGBColor(0x1C, 0x1F, 0x24)      # fondo oscuro / texto principal
TINTA2 = RGBColor(0x5B, 0x60, 0x68)     # texto secundario
ROJO = RGBColor(0xC2, 0x1F, 0x32)       # acento (rojo del Perú) = Spark
VERDE = RGBColor(0x0E, 0x7C, 0x74)      # secundario = local / aproximado
GRIS = RGBColor(0xEE, 0xF0, 0xF2)       # tarjetas
GRIS_LINEA = RGBColor(0xD4, 0xD7, 0xDB)
BLANCO = RGBColor(0xFF, 0xFF, 0xFF)
SUAVE = RGBColor(0xB9, 0xBE, 0xC6)
TITULO_F, CUERPO_F = "Cambria", "Calibri"

MOSTRAR_EXPOSITOR = False   # pie "Expone: ..." en cada diapositiva
CESAR, ALEK, AMBOS = "César Pajuelo", "Aleksander Paico", "César y Aleksander"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
VACIO = prs.slide_layouts[6]
W = 13.333


def txt(sl, x, y, w, h, contenido, size=16, color=TINTA, bold=False,
        font=CUERPO_F, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False,
        espacio=6, nombre=None):
    """Caja de texto. `contenido` es str o lista de parrafos; un parrafo puede
    ser str o lista de (texto, {opciones}) para mezclar estilos."""
    tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if nombre:
        tb.name = nombre
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    parrafos = contenido if isinstance(contenido, list) else [contenido]
    for i, par in enumerate(parrafos):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(espacio)
        runs = par if isinstance(par, list) else [(par, {})]
        for t, o in runs:
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = o.get("font", font)
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.color.rgb = o.get("color", color)
    return tb


def viñetas(sl, x, y, w, h, items, size=16, color=TINTA, espacio=10):
    tb = txt(sl, x, y, w, h, items, size=size, color=color, espacio=espacio)
    for p in tb.text_frame.paragraphs:
        pPr = p._p.get_or_add_pPr()
        pPr.set("marL", str(Emu(Inches(0.28))))
        pPr.set("indent", str(-Emu(Inches(0.28))))
        bu = etree.SubElement(pPr, qn("a:buChar"))
        bu.set("char", "•")
    return tb


def caja(sl, x, y, w, h, fill=GRIS, radio=True, linea=None):
    forma = MSO_SHAPE.ROUNDED_RECTANGLE if radio else MSO_SHAPE.RECTANGLE
    s = sl.shapes.add_shape(forma, Inches(x), Inches(y), Inches(w), Inches(h))
    if radio:
        s.adjustments[0] = 0.08
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if linea:
        s.line.color.rgb = linea
        s.line.width = Pt(1)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    return s


def ficha(sl, x, y, etiqueta, fill=ROJO, d=0.62, size=16):
    """Motivo visual: circulo con el numero de la parte."""
    c = sl.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    c.fill.solid()
    c.fill.fore_color.rgb = fill
    c.line.fill.background()
    c.shadow.inherit = False
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = etiqueta
    r.font.size, r.font.bold, r.font.name = Pt(size), True, TITULO_F
    r.font.color.rgb = BLANCO
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return c


def diapositiva(titulo, parte=None, expone=None, notas="", oscura=False, n=[0]):
    n[0] += 1
    sl = prs.slides.add_slide(VACIO)
    fondo = sl.background.fill
    fondo.solid()
    fondo.fore_color.rgb = TINTA if oscura else BLANCO
    if titulo:
        x0 = 0.6
        if parte:
            ficha(sl, 0.6, 0.5, parte)
            x0 = 1.42
        txt(sl, x0, 0.47, W - x0 - 0.6, 0.7, titulo, size=28, bold=True,
            font=TITULO_F, color=BLANCO if oscura else TINTA,
            anchor=MSO_ANCHOR.MIDDLE, nombre="Titulo")
    # pie: numero y quien expone
    col = SUAVE if oscura else TINTA2
    txt(sl, 0.6, 7.02, 6, 0.3, "Proyecto Integrador 1 · Minería de Datos Masivos · 2026-2",
        size=10, color=col)
    if expone and MOSTRAR_EXPOSITOR:
        txt(sl, W - 4.6, 7.02, 3.5, 0.3, [[("Expone: ", {"color": col}),
            (expone, {"bold": True, "color": ROJO if not oscura else BLANCO})]],
            size=10, align=PP_ALIGN.RIGHT)
    txt(sl, W - 1.0, 7.02, 0.4, 0.3, str(n[0]), size=10, color=col, align=PP_ALIGN.RIGHT)
    if notas:
        sl.notes_slide.notes_text_frame.text = notas
    return sl


def cifra(sl, x, y, w, valor, etiqueta, color=ROJO, size=40, fondo=GRIS, h=1.55, sub=None):
    caja(sl, x, y, w, h, fill=fondo)
    txt(sl, x + 0.25, y + 0.18, w - 0.5, 0.75, valor, size=size, bold=True,
        font=TITULO_F, color=color)
    txt(sl, x + 0.25, y + 0.18 + size / 72 + 0.2, w - 0.5, h - 0.9, etiqueta, size=13,
        color=TINTA2 if fondo != TINTA else SUAVE)


def estilo_grafico(ch, leyenda=False, size=12):
    ch.font.size = Pt(size)
    ch.font.name = CUERPO_F
    ch.font.color.rgb = TINTA2
    ch.has_legend = leyenda
    if leyenda:
        ch.legend.position = XL_LEGEND_POSITION.TOP
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(12)
    try:
        va = ch.value_axis
        va.has_major_gridlines = True
        va.major_gridlines.format.line.color.rgb = GRIS_LINEA
        va.format.line.fill.background()
        va.tick_labels.font.size = Pt(size)
        ca = ch.category_axis
        ca.format.line.color.rgb = GRIS_LINEA
        ca.tick_labels.font.size = Pt(size)
        ca.has_major_gridlines = False
    except Exception:
        pass


def titulo_eje(eje, texto):
    eje.has_title = True
    eje.axis_title.text_frame.text = texto
    r = eje.axis_title.text_frame.paragraphs[0].runs[0]
    r.font.size, r.font.bold, r.font.color.rgb = Pt(12), False, TINTA2


def eje_log(eje):
    sc = eje._element.find(qn("c:scaling"))
    lb = etree.SubElement(sc, qn("c:logBase"))
    lb.set("val", "10")
    sc.remove(lb)
    sc.insert(0, lb)


def color_serie(serie, color, linea=False, ancho=2.5):
    if linea:
        serie.format.line.color.rgb = color
        serie.format.line.width = Pt(ancho)
        serie.smooth = False
    else:
        serie.format.fill.solid()
        serie.format.fill.fore_color.rgb = color


# =================================================================== 1 PORTADA
sl = diapositiva(None, oscura=True, expone=CESAR, notas=(
    "CÉSAR (≈40 s). Buenos días. Somos César Pajuelo y Aleksander Paico. Nuestro proyecto aplica "
    "las seis familias de técnicas del curso al registro completo de contrataciones públicas del "
    "Perú: 2,76 millones de procesos del SEACE publicados por el OECE en estándar OCDS. "
    "El título resume las tres preguntas: quién compite, quién se repite y cómo vigilarlo. "
    "Yo presento los datos, el EDA en Spark y la similitud; Aleksander, vecinos aproximados, flujos, "
    "reglas y la discusión. Al final mostramos el reporte web y el código en vivo."))
ficha(sl, 0.8, 0.9, "OCDS", d=0.95, size=15)
txt(sl, 0.8, 2.05, 11.5, 2.2, "Quién compite, quién se repite y cómo vigilarlo",
    size=48, bold=True, font=TITULO_F, color=BLANCO)
txt(sl, 0.8, 3.75, 11, 0.9, "Minería de 2,76 millones de contrataciones públicas del Perú "
    "con Spark, MinHash/LSH, ANN, sketches de flujo y reglas de asociación",
    size=20, color=SUAVE)
txt(sl, 0.8, 5.25, 11, 1.2, [
    [("César Pajuelo · Aleksander Paico", {"bold": True, "color": BLANCO, "size": 18})],
    [("Proyecto Integrador 1 · Minería de Datos Masivos y Flujos de Datos · Prof. Heider Sánchez · 2026-2",
      {"color": SUAVE, "size": 14})]])

# =================================================================== 2 PREGUNTAS
sl = diapositiva("Tres preguntas que apuntan a decisiones de control", expone=CESAR, notas=(
    "CÉSAR (≈1 min). Formulamos las preguntas después de perfilar el dataset, para que fueran "
    "respondibles con los campos reales. Ninguna es descriptiva. "
    "P1: si un grupo de empresas se presenta siempre en bloque, la competencia puede ser solo aparente; "
    "la atacamos con dos representaciones independientes: LSH sobre proveedor→procesos y FP-Growth sobre proceso→postores. "
    "P2: reutilizar especificaciones puede ser estandarización sana o TDR copiados; cruzamos similitud de texto con quién gana. "
    "P3: un órgano de control no puede reprocesar el histórico cada día; ¿cuánta precisión perdemos vigilando con resúmenes? "
    "Cada pregunta usa al menos dos técnicas, y eso es lo que integra el proyecto."))
preg = [
    ("P1", "¿Hay grupos de proveedores que concurren sistemáticamente a los mismos procesos?",
     "Competencia aparente vs. real", "MinHash + LSH · FP-Growth"),
    ("P2", "¿Los procesos con especificaciones casi idénticas terminan con los mismos ganadores?",
     "Estandarización vs. TDR copiados", "Shingling + LSH · TF-IDF + IVF/HNSW"),
    ("P3", "¿Se puede vigilar el flujo en una pasada y con memoria acotada sin perder alertas?",
     "Monitoreo continuo y barato", "Bloom · Count-Min · DGIM"),
]
for i, (k, q, por, tec) in enumerate(preg):
    x = 0.6 + i * 4.1
    caja(sl, x, 1.6, 3.85, 4.95)
    ficha(sl, x + 0.3, 1.9, k, d=0.75, size=18)
    txt(sl, x + 0.3, 2.9, 3.25, 1.9, q, size=18, bold=True, font=TITULO_F)
    txt(sl, x + 0.3, 4.75, 3.25, 0.4, por, size=14, color=ROJO, bold=True)
    txt(sl, x + 0.3, 5.3, 3.25, 0.9, [[("Técnicas: ", {"bold": True}), (tec, {})]],
        size=14, color=TINTA2)

# =================================================================== 3 DATOS
sl = diapositiva("Por qué OCDS: la única fuente que cumple los cuatro requisitos", expone=CESAR, notas=(
    "CÉSAR (≈1 min 15 s). Evaluamos las seis fuentes sugeridas. OCDS es la única que cumple los cuatro "
    "requisitos de forma natural: volumen (17 GB en CSV, tablas de hasta 12,8 millones de filas), conjuntos "
    "comparables (texto por proceso, RUC por postor), una marca de tiempo al minuto sin nulos, y una canasta "
    "densa proceso→postores. Descargamos las 25 particiones con un script automatizado desde el OCP Data "
    "Registry, licencia CC BY 4.0. Verificamos fila a fila que los conteos coinciden con lo que declara el "
    "publicador. Un dato clave: analizamos competencia solo en 2015-2026; en un momento explico por qué."))
cifra(sl, 0.6, 1.6, 2.9, "2,76 M", "procesos de contratación, 2003 – oct. 2026")
cifra(sl, 3.7, 1.6, 2.9, "46,5 M", "filas en 12 tablas · 17 GB CSV → 2,6 GB Parquet")
cifra(sl, 0.6, 3.35, 2.9, "885 mil", "procesos en la ventana analítica 2015-2026")
cifra(sl, 3.7, 3.35, 2.9, "8 M", "postulaciones (proceso × RUC) en 2015-2026")
txt(sl, 0.6, 5.2, 6.0, 1.5, [
    [("Fuente: ", {"bold": True}), ("OECE (ex OSCE), Contrataciones Abiertas OCDS, vía OCP Data Registry "
     "(publicación 135), colección del 04/10/2026. Licencia CC BY 4.0.", {})]], size=13, color=TINTA2)
req = [("Volumen", "17 GB y tablas de 12,8 M filas: justifica Spark"),
       ("Conjuntos / vectores", "Texto libre por proceso, RUC por postor"),
       ("Dimensión temporal", "tender_datePublished al minuto, sin nulos"),
       ("Canasta de ítems", "Proceso → postores: 9,4 RUC de media")]
for i, (a, b) in enumerate(req):
    y = 1.6 + i * 1.27
    ficha(sl, 7.1, y + 0.17, "✓", fill=VERDE, d=0.6, size=18)
    txt(sl, 7.95, y + 0.05, 4.8, 0.45, a, size=18, bold=True, font=TITULO_F)
    txt(sl, 7.95, y + 0.5, 4.8, 0.5, b, size=15, color=TINTA2)

# =================================================================== 4 KDD
sl = diapositiva("El proceso KDD, con las decisiones que lo cambiaron", parte="I", expone=CESAR, notas=(
    "CÉSAR (≈1 min 15 s). Recorro el KDD rápido, quedándome con lo que no era obvio. "
    "Preprocesamiento: main.csv tiene cinco esquemas distintos entre años; un glob desalinea columnas en "
    "silencio, por eso leemos partición por partición y unimos con unionByName. 52 603 procesos con monto ≤ 0 "
    "se excluyen de montos; el número de postores se recalcula desde la tabla de postores. "
    "Transformación: Parquet particionado por año de PUBLICACIÓN, no por el año del archivo, que no coincide. "
    "Y materializamos una sola vez las representaciones que reutilizan las Partes II, III y V, como recomienda el enunciado."))
pasos = [("1", "Selección", "6 fuentes evaluadas; OCDS, 12 de 21 tablas"),
         ("2", "Preprocesamiento", "5 esquemas → unionByName; 52 603 montos ≤ 0 fuera; postores recalculados"),
         ("3", "Transformación", "Parquet por año de publicación; shingles, RUC → procesos, canastas"),
         ("4", "Minería", "Partes I a V: Spark donde escala, local donde no"),
         ("5", "Interpretación", "Reporte web: cada hallazgo con su lectura alternativa")]
for i, (k, a, b) in enumerate(pasos):
    x = 0.6 + i * 2.48
    caja(sl, x, 1.75, 2.28, 3.2)
    ficha(sl, x + 0.25, 2.0, k, d=0.6, size=18, fill=ROJO if i < 3 else VERDE)
    txt(sl, x + 0.25, 2.8, 1.9, 0.5, a, size=15, bold=True, font=TITULO_F)
    txt(sl, x + 0.25, 3.35, 1.85, 1.5, b, size=13, color=TINTA2)
    if i < 4:
        ar = sl.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + 2.3), Inches(3.2),
                                 Inches(0.16), Inches(0.3))
        ar.fill.solid(); ar.fill.fore_color.rgb = SUAVE; ar.line.fill.background()
caja(sl, 0.6, 5.3, 12.13, 1.35, fill=TINTA)
txt(sl, 0.95, 5.45, 11.5, 1.1, [
    [("Verificación: ", {"bold": True, "color": BLANCO}),
     ("2 760 591 procesos, 10 077 133 postulaciones y 12 837 750 partes coinciden fila a fila con lo que "
      "declara el publicador. La ingesta completa (17 GB, 46,5 M filas) toma 5 minutos en Spark.",
      {"color": SUAVE})]], size=16, anchor=MSO_ANCHOR.MIDDLE)

# =================================================================== 5 QUIEBRE 2015
sl = diapositiva("El EDA cambió el diseño: el quiebre de 2015", parte="I",
                 expone=CESAR, notas=(
    "CÉSAR (≈1 min 30 s). Este es el hallazgo que cambió todo el proyecto. Entre 2004 y 2014 hay 1,5 a 2,3 "
    "postores por proceso; en 2015 salta a 4 y llega a 14,6 en 2024. Un cambio así en un año no describe "
    "un mercado que se volvió competitivo: describe un cambio en lo que el sistema registra, antes se "
    "publicaba sobre todo al ganador. Tomarlo literal daría el hallazgo espectacular y falso de que la "
    "competencia se multiplicó por siete. Decisión: toda pregunta de competencia se resuelve en 2015-2026. "
    "También es el año desde el que existe el monto en soles. (Si preguntan: más adelante veremos que "
    "incluso después de 2015 'postor' incluye registros pasivos.)"))
pa = [x for x in D["eda_postores_por_anio"] if x["anio"] >= 2004]
cd = CategoryChartData()
cd.categories = [str(x["anio"]) for x in pa]
cd.add_series("Postores promedio por proceso", [x["postores_medio"] for x in pa])
gf = sl.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.5),
                         Inches(8.3), Inches(5.3), cd)
ch = gf.chart
estilo_grafico(ch)
ch.plots[0].gap_width = 40
s = ch.series[0]
for i, x in enumerate(pa):
    pt = s.points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = SUAVE if x["anio"] < 2015 else ROJO
ch.has_title = True
ch.chart_title.text_frame.text = "Postores promedio por proceso (gris: descartado para competencia)"
ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
ch.chart_title.text_frame.paragraphs[0].runs[0].font.bold = False
ch.value_axis.tick_labels.font.size = Pt(12)
cifra(sl, 9.3, 1.6, 3.43, "1,5 → 14,6", "postores por proceso entre 2008 y 2024", size=32)
cifra(sl, 9.3, 3.35, 3.43, "81 % → 11 %", "procesos con postor único", size=32, color=VERDE)
txt(sl, 9.3, 5.1, 3.43, 1.6, [[("Decisión: ", {"bold": True, "color": ROJO}),
    ("competencia, montos y co-postulación solo sobre 2015-2026.", {})]], size=15)

# =================================================================== 6 DINERO
sl = diapositiva("El dinero se concentra en pocas entidades y procesos", parte="I",
                 expone=CESAR, notas=(
    "CÉSAR (≈1 min). Tres hallazgos de distribución. Los montos abarcan nueve órdenes de magnitud: mediana "
    "S/ 144 mil, máximo S/ 3 035 millones; el promedio engaña, por eso usamos escala logarítmica. "
    "Los procesos de diez millones o más son solo el 1,6 % pero mueven el 58 % del dinero. "
    "El 1 % de las 3 163 entidades concentra el 40,6 % del monto: proyectos del MTC, EsSalud, Sedapal. "
    "Y la adjudicación simplificada domina en número, pero la licitación pública mueve 2,6 veces más dinero. "
    "Para P3 esto sugiere un caso de heavy hitters: pocos actores explican casi todo."))
cifra(sl, 0.6, 1.6, 3.85, "1 % → 40,6 %", "de las 3 163 entidades concentra el 40,6 % del monto; el 10 % llega al 76,9 %", size=34, h=2.1)
cifra(sl, 4.74, 1.6, 3.85, "1,6 % → 58 %", "de los procesos (≥ S/ 10 M) mueve el 58 % de los S/ 996 mil M convocados", size=34, h=2.1)
cifra(sl, 8.88, 1.6, 3.85, "7× / 2,6×", "la licitación pública: 7 veces menos procesos que la adjudicación simplificada y 2,6 veces más dinero", size=34, h=2.1, color=VERDE)
caja(sl, 0.6, 4.05, 12.13, 2.6, fill=GRIS)
txt(sl, 0.95, 4.3, 11.4, 2.2, [
    [("Por qué importa para las preguntas", {"bold": True, "size": 18, "font": TITULO_F})],
    [("Montos en 9 órdenes de magnitud ", {"bold": True}),
     ("(mediana S/ 144 mil, p99 S/ 14,6 M, máx. S/ 3 035 M): el promedio engaña y se trabaja en escala logarítmica.", {})],
    [("Heavy hitters: ", {"bold": True}),
     ("un puñado de entidades explica el grueso del riesgo monetario; es justo el caso de uso del Count-Min Sketch (P3).", {})],
    [("Estacionalidad: ", {"bold": True}),
     ("enero tiene 68 % menos procesos por el ciclo presupuestal; un flujo estacional es buen banco de pruebas para DGIM.", {})]],
    size=15, espacio=8)

# =================================================================== 7 RDD vs DF
sl = diapositiva("RDD vs DataFrames: mismo resultado, 58 veces más lento",
                 parte="I", expone=CESAR, notas=(
    "CÉSAR (≈1 min 30 s). Implementamos dos agregaciones de las preguntas —monto por entidad, y procesos y "
    "monto medio por año y categoría— en RDD con map y reduceByKey, en DataFrames y en Spark SQL. Mismo "
    "resultado, pero el RDD tarda 22,6 s contra 0,39 s. No es que los RDD sean lentos en abstracto: en "
    "PySpark cada fila viaja de la JVM a un proceso Python y vuelve; el DataFrame se queda en la JVM, "
    "Catalyst hace agregación parcial antes del shuffle y trabaja en memoria columnar. "
    "En claridad, SQL es el más legible; el RDD lo reservamos para lo que SQL no expresa bien, el Apriori. "
    "Particionado: al filtrar por año, el plan muestra PartitionFilters en el FileScan y Spark no abre los "
    "otros 24 directorios: de 0,61 a 0,15 s."))
t = D["eda_tiempos_rdd_vs_df"]
cd = CategoryChartData()
cd.categories = ["A · RDD", "A · DataFrame", "A · Spark SQL", "B · RDD", "B · DataFrame"]
cd.add_series("Segundos (mejor de 3)", [x["segundos"] for x in t])
gf = sl.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.5),
                         Inches(7.2), Inches(4.0), cd)
ch = gf.chart
estilo_grafico(ch)
ch.plots[0].gap_width = 45
ch.plots[0].has_data_labels = True
dl = ch.plots[0].data_labels
dl.number_format, dl.number_format_is_linked = '0.00" s"', False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size = Pt(12)
ch.category_axis.reverse_order = True
for i, x in enumerate(t):
    pt = ch.series[0].points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = ROJO if "RDD" in x["operacion"] else VERDE
txt(sl, 0.6, 5.65, 7.2, 1.1, [[("A: ", {"bold": True}), ("monto por entidad.  ", {}),
    ("B: ", {"bold": True}), ("procesos y monto medio por año y categoría. 830 974 filas en caché.", {})]],
    size=13, color=TINTA2)
caja(sl, 8.2, 1.6, 4.53, 2.45)
txt(sl, 8.5, 1.8, 4.0, 2.1, [
    [("Por qué la diferencia", {"bold": True, "size": 18, "font": TITULO_F})],
    "Cada fila del RDD viaja JVM → Python → JVM.",
    "El DataFrame no sale de la JVM: Catalyst agrega antes del shuffle, en memoria columnar."], size=14)
caja(sl, 8.2, 4.3, 4.53, 2.4, fill=TINTA)
txt(sl, 8.5, 4.5, 4.0, 2.1, [
    [("Particionado por año", {"bold": True, "size": 18, "font": TITULO_F, "color": BLANCO})],
    [("anio = 2025 → PartitionFilters en el FileScan: lee 1 de 25 directorios.", {"color": SUAVE})],
    [("0,61 s → 0,15 s", {"bold": True, "size": 24, "color": BLANCO, "font": TITULO_F})]], size=14)

# =================================================================== 8 MINHASH
sl = diapositiva("Similitud sin comparar todos los pares: MinHash", parte="II", expone=CESAR, notas=(
    "CÉSAR (≈1 min 30 s). Representación: cada proceso es el conjunto de sus shingles de 5 caracteres sobre "
    "título y descripción normalizados; caracteres y no palabras porque el texto mezcla códigos y siglas. "
    "Primero la verdad: Jaccard exacto sobre 2 000 procesos, casi 2 millones de pares, 22 s. Extrapolado a "
    "883 mil procesos son 49 días: crece con n². "
    "MinHash propio: 256 funciones h(x)=(a·x+b) mod p escritas en Spark SQL con funciones de orden superior, "
    "sin UDF de Python. El error sigue 1/√T y queda bajo la cota teórica. T=128 es el punto de operación: "
    "RMSE 0,02, que no cambia qué pares superan 0,8. Detalle: con el primo 2^61−1 de la literatura el "
    "producto desborda el entero de 64 bits de Spark, por eso usamos 2^31−1."))
cifra(sl, 0.6, 1.6, 3.6, "≈ 49 días", "fuerza bruta extrapolada a 882 895 procesos (21,9 s para 2 000)", size=36)
cifra(sl, 0.6, 3.35, 3.6, "10 / millón", "densidad de pares con Jaccard ≥ 0,6: casi todo par comparado es inútil", size=36, color=VERDE)
txt(sl, 0.6, 5.15, 3.6, 1.6, [[("Representación: ", {"bold": True}),
    ("shingles de 5 caracteres (174 por proceso). Hash: (a·x + b) mod (2³¹−1) en Spark SQL, sin UDF.", {})]],
    size=13, color=TINTA2)
m = D["p2_error_minhash_vs_T"]
cd = CategoryChartData()
cd.categories = [str(x["T"]) for x in m]
cd.add_series("RMSE medido", [x["rmse"] for x in m])
cd.add_series("Cota teórica 0,5/√T", [x["cota_teorica"] for x in m])
gf = sl.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(4.6), Inches(1.5),
                         Inches(8.13), Inches(5.3), cd)
ch = gf.chart
estilo_grafico(ch, leyenda=True)
color_serie(ch.series[0], ROJO, linea=True)
color_serie(ch.series[1], SUAVE, linea=True)
ch.series[1].format.line.dash_style = 4
for sr, c in ((ch.series[0], ROJO), (ch.series[1], SUAVE)):
    sr.marker.format.fill.solid(); sr.marker.format.fill.fore_color.rgb = c
    sr.marker.format.line.color.rgb = c
ch.value_axis.tick_labels.number_format = "0.00"
ch.value_axis.tick_labels.number_format_is_linked = False
titulo_eje(ch.category_axis, "Número de funciones hash T")
titulo_eje(ch.value_axis, "Error del Jaccard estimado")

# =================================================================== 9 LSH
sl = diapositiva("LSH: bandas y filas deciden qué pares se pierden", parte="II", expone=CESAR, notas=(
    "CÉSAR (≈1 min 30 s). LSH por bandas, implementación propia en Spark. La firma de 256 se parte en b "
    "bandas de r filas; el umbral efectivo es aproximadamente (1/b)^(1/r). La tabla es la curva S vista "
    "desde los datos: con r=2 recuperamos todo pero con 577 mil falsos positivos, LSH no ahorra nada; con "
    "r ≥ 16 la precisión es perfecta pero perdemos casi todos. Elegimos b=32, r=8: umbral 0,65, 85 % de "
    "recall, 37 candidatos, y un filtro exacto posterior elimina los falsos positivos a costo despreciable. "
    "Advertencia honesta: con 20 pares reales cada par vale 5 puntos de recall. "
    "¿Por qué no MinHashLSH de MLlib? Usa r=1 siempre: su umbral es 1/b. Volcó más de 11 GB a disco y no "
    "terminó; la nuestra con r=8 no volcó un byte."))
filas = D["p2_lsh_bandas"]
tbl = sl.shapes.add_table(len(filas) + 1, 6, Inches(0.6), Inches(1.6), Inches(7.6), Inches(4.2)).table
cab = ["b × r", "Umbral", "Candidatos", "Falsos pos.", "Falsos neg.", "Recall"]
anchos = [1.15, 1.1, 1.45, 1.35, 1.35, 1.2]
for j, (c, a) in enumerate(zip(cab, anchos)):
    tbl.columns[j].width = Inches(a)
    cell = tbl.cell(0, j)
    cell.text = c
for i, f in enumerate(filas, start=1):
    vals = [f"{f['b']} × {f['r']}", f"{f['umbral_efectivo']:.2f}".replace(".", ","),
            f"{f['candidatos']:,}".replace(",", " "), f"{f['falsos_positivos']:,}".replace(",", " "),
            str(f["falsos_negativos"]), f"{f['recall']:.0%}".replace("%", " %")]
    for j, v in enumerate(vals):
        tbl.cell(i, j).text = v
for i in range(len(filas) + 1):
    elegida = i > 0 and filas[i - 1]["b"] == 32
    for j in range(6):
        cell = tbl.cell(i, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = TINTA if i == 0 else (ROJO if elegida else (GRIS if i % 2 else BLANCO))
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT
        r = p.runs[0]
        r.font.size, r.font.name = Pt(15), CUERPO_F
        r.font.bold = i == 0 or elegida
        r.font.color.rgb = BLANCO if (i == 0 or elegida) else TINTA
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
txt(sl, 0.6, 6.0, 7.6, 0.8, "Muestra de 2 000 procesos, 20 pares reales con Jaccard ≥ 0,6. "
    "En rojo, el punto de operación elegido.", size=13, color=TINTA2)
caja(sl, 8.6, 1.6, 4.13, 2.3)
txt(sl, 8.9, 1.8, 3.6, 2.0, [[("Umbral efectivo", {"bold": True, "size": 18, "font": TITULO_F})],
    [("s* ≈ (1/b)^(1/r)", {"size": 22, "font": TITULO_F})],
    "b = 32, r = 8 → 0,65: 85 % de recall con solo 37 candidatos."], size=14)
caja(sl, 8.6, 4.15, 4.13, 2.55, fill=TINTA)
txt(sl, 8.9, 4.35, 3.6, 2.2, [
    [("MLlib no escaló", {"bold": True, "size": 18, "font": TITULO_F, "color": BLANCO})],
    [("MinHashLSH usa r = 1: umbral 1/b. Con 8 tablas, Jaccard 0,125 ya es candidato. Volcó > 11 GB a disco y no terminó.",
      {"color": SUAVE})]], size=14)

# =================================================================== 10 HALLAZGOS LSH
sl = diapositiva("LSH a escala: reconvocatorias y un grupo inseparable",
                 parte="II", expone=CESAR, notas=(
    "CÉSAR (≈1 min 30 s). A escala: 883 mil procesos, 4,2 millones de candidatos —0,001 % de los pares— y "
    "589 mil pares con Jaccard ≥ 0,8. El hallazgo no es el número sino la composición: el 98 % es de la misma "
    "entidad. No es plagio entre entidades; es reconvocatoria: un proceso desierto se vuelve a publicar con el "
    "mismo texto y otro OCID. LSH, planteada como búsqueda, terminó siendo una herramienta de limpieza: la "
    "Parte V colapsa esas reconvocatorias para no contar dos veces. "
    "Para P1: proveedor como conjunto de procesos. 2 275 pares con Jaccard ≥ 0,5 en 54 s, y un grupo de cuatro "
    "proveedores que aparecen en exactamente los mismos 37 procesos. Puede ser un consorcio o un mercado local "
    "pequeño: es una pista para mirar, no una conclusión. "
    "Le paso la palabra a Aleksander para vecinos aproximados."))
cifra(sl, 0.6, 1.6, 3.85, "589 224", "pares de procesos con Jaccard ≥ 0,8 (4,2 M candidatos, 0,001 % de los pares)", size=38, h=1.85)
cifra(sl, 0.6, 3.7, 3.85, "98,1 %", "de la misma entidad: son reconvocatorias, no copias entre entidades", size=38, h=1.85, color=VERDE)
txt(sl, 0.6, 5.8, 3.85, 0.9, "Firmas 37 min + LSH y verificación 4 min, en Spark.", size=13, color=TINTA2)
caja(sl, 4.85, 1.6, 7.88, 5.1, fill=TINTA)
txt(sl, 5.25, 1.85, 7.1, 0.5, "P1 · Proveedores como conjunto de procesos", size=20, bold=True,
    font=TITULO_F, color=BLANCO)
for i, (v, e) in enumerate([("2 275", "pares con Jaccard ≥ 0,5 entre 68 381 proveedores"),
                            ("2 338 M", "comparaciones evitadas; resuelto en 54 s"),
                            ("4 RUC", "en exactamente los mismos 37 procesos (Jaccard 1,000)")]):
    y = 2.6 + i * 1.0
    txt(sl, 5.25, y, 2.3, 0.7, v, size=30, bold=True, font=TITULO_F, color=BLANCO)
    txt(sl, 7.6, y + 0.1, 4.8, 0.7, e, size=15, color=SUAVE, anchor=MSO_ANCHOR.MIDDLE)
txt(sl, 5.25, 5.65, 7.1, 0.9, [[("Lectura: ", {"bold": True, "color": BLANCO}),
    ("consorcio, empresas vinculadas o mercado local muy pequeño. Es una pista que justifica mirar, no una conclusión.",
     {"color": SUAVE})]], size=14)

# =================================================================== 11 ANN
sl = diapositiva("IVF y HNSW: de 120 a 420 veces más rápidos", parte="III",
                 expone=ALEK, notas=(
    "ALEKSANDER (≈2 min). Representación: TF-IDF calculado en Spark SQL sobre 885 mil procesos, reducido con "
    "LSA a 256 dimensiones porque FAISS necesita vectores densos; el TF-IDF denso pesaría 70 GB. "
    "IVF agrupa los vectores con k-means en nlist celdas; la consulta solo recorre las nprobe celdas más "
    "cercanas. Falla si el vecino real cae al otro lado de una frontera; subir nprobe lo corrige. "
    "HNSW es un grafo en capas: arriba saltos largos, abajo todos los nodos; búsqueda voraz con efSearch "
    "candidatos, costo logarítmico. "
    "Resultados: exacta 57,6 ms. IVF nlist 4096, nprobe 16: recall 0,98 en 0,48 ms, 120 veces más rápido. "
    "HNSW gana a latencia muy baja —0,95 en 0,14 ms— pero se estanca en 0,98: los miles de vectores idénticos "
    "de las reconvocatorias crean mesetas donde la búsqueda voraz se atasca. Elegimos IVF."))
caja(sl, 0.6, 1.6, 4.3, 2.45)
txt(sl, 0.9, 1.8, 3.8, 2.1, [[("IVF", {"bold": True, "size": 20, "font": TITULO_F, "color": ROJO})],
    "k-means en nlist celdas; la consulta recorre solo las nprobe más cercanas. Más nprobe = más recall y más tiempo."],
    size=14)
caja(sl, 0.6, 4.25, 4.3, 2.45)
txt(sl, 0.9, 4.45, 3.8, 2.1, [[("HNSW", {"bold": True, "size": 20, "font": TITULO_F, "color": VERDE})],
    "Grafo en capas con M vecinos por nodo; búsqueda voraz con efSearch candidatos. Costo logarítmico; usa más memoria."],
    size=14)
cd = XyChartData()
s_ivf = cd.add_series("IVF nlist=4096 (nprobe 1→128)")
s_hn = cd.add_series("HNSW M=32 (efSearch 10→512)")
for x in D["p3_ann_curvas"]:
    if x["config"] == "nlist=4096":
        s_ivf.add_data_point(x["ms_consulta"], x["recall"])
    elif x["config"] == "M=32":
        s_hn.add_data_point(x["ms_consulta"], x["recall"])
gf = sl.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER_LINES, Inches(5.2), Inches(1.5),
                         Inches(7.53), Inches(5.3), cd)
ch = gf.chart
estilo_grafico(ch, leyenda=True)
for sr, c in ((ch.series[0], ROJO), (ch.series[1], VERDE)):
    color_serie(sr, c, linea=True)
    sr.marker.format.fill.solid(); sr.marker.format.fill.fore_color.rgb = c
    sr.marker.format.line.color.rgb = c
eje_log(ch.category_axis)
ch.category_axis.crosses = XL_AXIS_CROSSES.MINIMUM
ch.category_axis.minimum_scale, ch.category_axis.maximum_scale = 0.01, 10
ch.category_axis.has_major_gridlines = False
ch.value_axis.minimum_scale, ch.value_axis.maximum_scale = 0.7, 1.0
ch.value_axis.tick_labels.number_format = "0.00"
ch.value_axis.tick_labels.number_format_is_linked = False
titulo_eje(ch.category_axis, "ms por consulta (escala log) · exacta = 57,6 ms")
titulo_eje(ch.value_axis, "Recall@10")

# =================================================================== 12 LSA + P2
sl = diapositiva("La pérdida real estaba en la representación, no en el índice", parte="III",
                 expone=ALEK, notas=(
    "ALEKSANDER (≈1 min 30 s). Este es el hallazgo más importante de la Parte III. Medimos contra el TF-IDF "
    "disperso exacto: incluso con 256 dimensiones, LSA solo recupera el 33 % de los 10 vecinos reales. Las "
    "descripciones son cortas y el vocabulario enorme; la SVD conserva temas generales y pierde los detalles. "
    "Ningún índice recupera lo que la SVD ya perdió. Por eso P2 se respondió con vecinos exactos del TF-IDF "
    "disperso, que a este volumen cuesta 13 ms por consulta. "
    "Respuesta a P2: dos procesos al azar del mismo tipo comparten ganador el 0,02 % de las veces; con texto "
    "casi idéntico, el 15 %. Y entre entidades distintas aún el 10 %. Dos lecturas: mercado especializado con "
    "pocos oferentes, o TDR copiados que reproducen al ganador. Sirve para priorizar auditorías."))
cv = D["p3_curva_dimensiones"]
cd = CategoryChartData()
cd.categories = [str(x["dim"]) for x in cv]
cd.add_series("Recall de los 10 vecinos exactos", [x["recall_top10"] for x in cv])
cd.add_series("Recall de casi-duplicados", [x["recall_casi_duplicados"] for x in cv])
gf = sl.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.5),
                         Inches(6.4), Inches(5.3), cd)
ch = gf.chart
estilo_grafico(ch, leyenda=True)
color_serie(ch.series[0], ROJO)
color_serie(ch.series[1], SUAVE)
ch.plots[0].gap_width = 60
ch.plots[0].has_data_labels = True
dl = ch.plots[0].data_labels
dl.number_format, dl.number_format_is_linked = "0%", False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size = Pt(11)
ch.value_axis.maximum_scale = 1.0
ch.value_axis.tick_labels.number_format = "0%"
ch.value_axis.tick_labels.number_format_is_linked = False
titulo_eje(ch.category_axis, "Dimensiones LSA")
caja(sl, 7.4, 1.6, 5.33, 5.1, fill=TINTA)
txt(sl, 7.75, 1.85, 4.7, 0.5, "P2 · ¿Texto casi igual, mismo ganador?", size=20, bold=True,
    font=TITULO_F, color=BLANCO)
for i, (v, e) in enumerate([("0,02 %", "dos procesos al azar del mismo tipo"),
                            ("15 %", "con texto casi idéntico (coseno ≥ 0,95)"),
                            ("10 %", "aun entre entidades distintas")]):
    y = 2.6 + i * 1.05
    txt(sl, 7.75, y, 1.9, 0.8, v, size=30, bold=True, font=TITULO_F,
        color=BLANCO if i else SUAVE)
    txt(sl, 9.75, y + 0.05, 2.8, 0.8, e, size=15, color=SUAVE, anchor=MSO_ANCHOR.MIDDLE)
txt(sl, 7.75, 5.75, 4.7, 0.85, [[("Lectura: ", {"bold": True, "color": BLANCO}),
    ("mercados especializados o TDR copiados que reproducen al ganador. Prioriza auditorías.",
     {"color": SUAVE})]], size=14)

# =================================================================== 13 FLUJOS
sl = diapositiva("Flujos: memoria ahorrada frente a alertas perdidas",
                 parte="IV", expone=ALEK, notas=(
    "ALEKSANDER (≈2 min). Spark ordena por fecha los 885 mil procesos y sus 8 millones de postulaciones y "
    "calcula la verdad exacta; las tres estructuras las implementamos desde cero y procesan el flujo en una sola pasada. "
    "Bloom: '¿este RUC ya postuló antes?'. Sin falsos negativos; el error es un proveedor nuevo marcado como "
    "ya visto, justo la alerta que importa. Con 8 bits por clave ocupa 0,67 MB, 100 veces menos que el set, y "
    "pierde 0,41 % de las alertas. Ojo: en Python es más lento que el set nativo; la ganancia es de memoria. "
    "Count-Min: 512 KB contra 86 MB; recupera el 100 % del top 20, error 3 % en el top 100. Para la cola "
    "larga es inútil: convierte un 1 en 153. Responde '¿quién domina?', no '¿cuántas veces postuló este pequeño?'. "
    "DGIM: procesos de más de un millón en el último mes; error de 4 a 11 % con el 2 % de la memoria. "
    "Honestamente, a este volumen la ventana exacta de un año ocupa 6 KB: DGIM es para otra escala."))
tarjetas = [
    ("Bloom Filter", "¿Este RUC ya postuló antes?", "100×", "menos memoria: 0,67 MB vs 69,6 MB",
     "0,41 % de proveedores nuevos no alertados (2 900 de 705 mil). Cero falsos negativos.", ROJO),
    ("Count-Min Sketch", "¿Quién domina el flujo?", "100 %", "del top 20 recuperado con 512 KB (vs 85,8 MB)",
     "Error 3 % en el top 100; inútil en la cola larga (un 1 se vuelve 153).", VERDE),
    ("DGIM", "¿Cuántos procesos ≥ S/ 1 M hubo el último mes?", "4-11 %", "de error con el 2 % de la memoria de la ventana",
     "Memoria crece con log N. A este volumen la ventana exacta de un año pesa 6 KB.", TINTA),
]
for i, (nom, q, v, ve, lect, col) in enumerate(tarjetas):
    x = 0.6 + i * 4.1
    caja(sl, x, 1.6, 3.85, 5.1)
    txt(sl, x + 0.3, 1.85, 3.3, 0.5, nom, size=21, bold=True, font=TITULO_F, color=col)
    txt(sl, x + 0.3, 2.4, 3.3, 0.8, q, size=15, italic=True, color=TINTA2)
    txt(sl, x + 0.3, 3.25, 3.3, 0.9, v, size=44, bold=True, font=TITULO_F, color=col)
    txt(sl, x + 0.3, 4.15, 3.3, 0.8, ve, size=14, bold=True)
    txt(sl, x + 0.3, 5.0, 3.3, 1.5, lect, size=14, color=TINTA2)

# =================================================================== 14 APRIORI vs FP
sl = diapositiva("Apriori valida a FP-Growth; FP-Growth hace el trabajo", parte="V", expone=ALEK, notas=(
    "ALEKSANDER (≈1 min 30 s). Transacción: cada proceso es una canasta y sus ítems son los RUC postores. "
    "Descartamos proceso→códigos de ítem porque solo el 3,7 % tiene dos o más códigos. Preprocesamiento: "
    "colapsamos 35 100 reconvocatorias que detectó LSH y quitamos canastas de 1 postor o de más de 40 —compras "
    "masivas donde coincidir no es una elección—. Quedan 618 mil canastas. "
    "Apriori propio sobre RDD y FP-Growth de MLlib dan exactamente los mismos conjuntos y soportes en 2023: "
    "eso valida la implementación. Apriori tardó 484 s llegando a tamaño 4; FP-Growth 26 s sin tope. FP-Growth "
    "comprime en un árbol de prefijos y no genera candidatos. "
    "Sobre todo el periodo: 585 mil conjuntos frecuentes, porque un grupo de 14 RUC genera 2^14 subconjuntos. "
    "Por eso analizamos los 183 mil maximales: cada grupo se cuenta una vez."))
cifra(sl, 0.6, 1.6, 3.85, "484 s vs 26 s", "Apriori (RDD, hasta tamaño 4) vs FP-Growth (MLlib, sin tope) en 2023", size=32)
cifra(sl, 0.6, 3.35, 3.85, "Idénticos", "125 689 conjuntos con los mismos soportes, nivel por nivel", size=32, color=VERDE)
txt(sl, 0.6, 5.15, 3.85, 1.6, [[("Canasta: ", {"bold": True}),
    ("proceso → RUC postores. 618 440 canastas tras colapsar 35 100 reconvocatorias y quitar las de 1 o > 40 postores.", {})]],
    size=13, color=TINTA2)
fr = D["p5_resumen"]["fpgrowth"]
ks = [str(k) for k in range(1, 15)]
cd = CategoryChartData()
cd.categories = ks
cd.add_series("Conjuntos frecuentes", [fr["por_tamanio"].get(k, 0) for k in ks])
cd.add_series("Maximales", [fr["maximales_por_tamanio"].get(k, 0) for k in ks])
gf = sl.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(4.85), Inches(1.5),
                         Inches(7.88), Inches(5.3), cd)
ch = gf.chart
estilo_grafico(ch, leyenda=True)
color_serie(ch.series[0], SUAVE)
color_serie(ch.series[1], ROJO)
ch.plots[0].gap_width = 50
ch.value_axis.tick_labels.number_format = '0," mil"'
ch.value_axis.tick_labels.number_format_is_linked = False
titulo_eje(ch.category_axis, "RUC en el conjunto · 585 205 frecuentes → 183 630 maximales")

# =================================================================== 15 CAMARILLAS
sl = diapositiva("Grupos que ganan de más y parejas que nunca ganan", parte="V",
                 expone=ALEK, notas=(
    "ALEKSANDER (≈2 min). 'Gana el grupo' solo no dice nada: si 11 de 12 postores son del grupo, ganar el "
    "92 % es lo esperable. Por eso comparamos con la tasa esperada al azar. "
    "Patrón 1: 157 de las 300 camarillas mayores son grupos de 9 a 11 proveedores de bienes que concurren en "
    "15 a 31 sedes del Poder Judicial y ganan, en mediana, el 83 % frente al 36 % esperado; hasta 97 %. Es el "
    "patrón más consistente del dataset. Lectura alternativa: un rubro con pocos proveedores reales. "
    "Patrón 2, las reglas: P0205→P0206, confianza 0,81, lift 60, 4 406 procesos en 913 entidades, y no ganan "
    "nunca. Una pareja que se presenta a 4 400 procesos y no gana ninguno no compite: la tabla de postores "
    "incluye participantes registrados que no ofertan. Es un hallazgo de calidad de datos como el de 2015. "
    "Lift aquí separa poco —todas las reglas tienen lift ≫ 1—; ordenan la confianza y el soporte. "
    "En el reporte web están las ocho reglas comentadas."))
caja(sl, 0.6, 1.6, 6.0, 5.1, fill=TINTA)
txt(sl, 0.95, 1.85, 5.3, 0.5, "Red de proveedores del Poder Judicial", size=20, bold=True,
    font=TITULO_F, color=BLANCO)
txt(sl, 0.95, 2.4, 5.3, 0.8, "157 de las 300 camarillas mayores · grupos de 9-11 RUC · bienes · 15-31 sedes",
    size=14, color=SUAVE)
cd = CategoryChartData()
cd.categories = ["Esperado al azar", "Gana el grupo"]
cd.add_series("Mediana", [0.359, 0.828])
gf = sl.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.95), Inches(3.15),
                         Inches(5.3), Inches(2.3), cd)
ch = gf.chart
estilo_grafico(ch)
ch.has_title = False
ch.font.color.rgb = SUAVE
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
ch.value_axis.maximum_scale, ch.value_axis.minimum_scale = 1.0, 0
ch.category_axis.reverse_order = True
ch.category_axis.tick_labels.font.color.rgb = BLANCO
ch.category_axis.tick_labels.font.size = Pt(14)
ch.plots[0].gap_width = 45
ch.plots[0].has_data_labels = True
dl = ch.plots[0].data_labels
dl.number_format, dl.number_format_is_linked = "0%", False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size, dl.font.bold = Pt(18), True
dl.font.color.rgb = BLANCO
ch.series[0].points[0].format.fill.solid(); ch.series[0].points[0].format.fill.fore_color.rgb = TINTA2
ch.series[0].points[1].format.fill.solid(); ch.series[0].points[1].format.fill.fore_color.rgb = ROJO
txt(sl, 0.95, 5.6, 5.3, 1.0, [[("Alternativa: ", {"bold": True, "color": BLANCO}),
    ("un rubro con pocos proveedores reales. Distinguirlo exige revisar ofertas y precios.", {"color": SUAVE})]],
    size=14)
caja(sl, 7.0, 1.6, 5.73, 5.1)
txt(sl, 7.35, 1.85, 5.1, 0.5, "Reglas: parejas que nunca ganan", size=20, bold=True, font=TITULO_F)
txt(sl, 7.35, 2.45, 5.1, 0.6, "P0205 → P0206", size=28, bold=True, font=TITULO_F, color=ROJO)
txt(sl, 7.35, 3.1, 5.1, 1.0, "confianza 0,81 · lift 60 · 4 406 procesos en 913 entidades · gana 0 % (esperado 15 %)",
    size=15)
txt(sl, 7.35, 4.15, 5.1, 2.4, [
    [("Interpretación: ", {"bold": True}),
     ("la tabla de postores incluye participantes registrados que no presentan oferta. Es un hallazgo de calidad "
      "de datos: «postor» mide interés registrado, no necesariamente competencia.", {})],
    [("Lift ≫ 1 en todas las reglas (25 a 1 700): ordenan la confianza y el soporte.", {"color": TINTA2})]],
    size=14)

# =================================================================== 16 VI: APROXIMAR
sl = diapositiva("¿Cuánto se pierde al aproximar, y vale la pena?", parte="VI", expone=ALEK, notas=(
    "ALEKSANDER (≈1 min 30 s). Resumen de la Parte VI. Valor por técnica: EDA alto, porque el quiebre de 2015 "
    "cambió el diseño; MinHash/LSH alto, respondió P1 y destapó las reconvocatorias; FP-Growth alto; Bloom y "
    "Count-Min medio, porque hoy el exacto cabe en memoria; ANN medio-bajo por la pérdida de LSA; DGIM bajo a "
    "esta escala; Apriori didáctico. "
    "La lección transversal: la aproximación del algoritmo casi nunca fue el problema; la de la representación "
    "sí. LSA perdió dos tercios de los vecinos, más que cualquier índice. Medir contra la verdad exacta en cada "
    "paso fue lo que nos permitió verlo."))
filas = [("MinHash T=128", "RMSE 0,020", "Firma fija de 512 B", "Sí", VERDE),
         ("LSH b=32, r=8", "15 % de pares perdidos", "49 días → 4 min", "Sí", VERDE),
         ("LSA 256 dims", "67 % de los vecinos reales", "Vectores indexables", "No para P2", ROJO),
         ("IVF / HNSW", "1-5 % de recall", "80 a 420× más rápido", "Sí", VERDE),
         ("Bloom 8 bits/clave", "0,41 % de alertas", "100× menos memoria", "Sí (monitor)", VERDE),
         ("Count-Min 512 KB", "3 % en el top 100", "170× menos memoria", "Solo para el top", TINTA2),
         ("DGIM r=5", "4 % de error", "2 % de la memoria", "A gran escala", TINTA2)]
tbl = sl.shapes.add_table(len(filas) + 1, 4, Inches(0.6), Inches(1.55), Inches(8.2), Inches(4.6)).table
for j, (c, a) in enumerate(zip(["Método", "Pérdida medida", "Ganancia", "¿Vale?"], [2.2, 2.3, 2.2, 1.5])):
    tbl.columns[j].width = Inches(a)
    tbl.cell(0, j).text = c
for i, f in enumerate(filas, start=1):
    for j in range(4):
        tbl.cell(i, j).text = f[j]
for i in range(len(filas) + 1):
    for j in range(4):
        cell = tbl.cell(i, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = TINTA if i == 0 else (GRIS if i % 2 else BLANCO)
        r = cell.text_frame.paragraphs[0].runs[0]
        r.font.size, r.font.name = Pt(14), CUERPO_F
        r.font.bold = i == 0 or j == 3
        r.font.color.rgb = BLANCO if i == 0 else (filas[i - 1][4] if j == 3 else TINTA)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
caja(sl, 9.2, 1.6, 3.53, 5.1, fill=TINTA)
txt(sl, 9.5, 1.85, 3.0, 4.7, [
    [("La lección", {"bold": True, "size": 20, "font": TITULO_F, "color": BLANCO})],
    [("La aproximación del ", {"color": SUAVE}), ("algoritmo", {"bold": True, "color": BLANCO}),
     (" casi nunca fue el problema; la de la ", {"color": SUAVE}),
     ("representación", {"bold": True, "color": BLANCO}), (" sí.", {"color": SUAVE})],
    [("Medir contra la verdad exacta en cada paso fue lo que permitió verlo.", {"color": SUAVE})]],
    size=16, espacio=12)

# =================================================================== 17 VI: SPARK Y ESCALA
sl = diapositiva("Spark donde escala, local donde no; y a 10× o 100×", parte="VI",
                 expone=ALEK, notas=(
    "ALEKSANDER (≈1 min 30 s). Spark valió la pena en la ingesta, las representaciones con joins de 10 millones "
    "de filas, el EDA, el TF-IDF, el LSH a escala y FP-Growth. No hacía falta en los sketches —son secuenciales "
    "por definición y la idea es que quepan en una máquina—, en FAISS ni en las figuras. Y el overhead se notó: "
    "RDD 58× más lento, firmas MinHash en SQL 37 minutos, una ventana rowsBetween que era O(n·N). "
    "A 10× o 100×: la fuerza bruta pasa de 49 días a 13 o 1 300 años, LSH sigue lineal. HNSW deja de caber en "
    "una máquina: IVF-PQ. Y aquí está el argumento a favor de los sketches: el set exacto crece con los "
    "distintos, Count-Min y DGIM casi no cambian. A 100×, DGIM pasa de curiosidad a necesidad."))
cols = [("Sí valió Spark", ROJO, ["Ingesta: 17 GB en 5 min", "Joins de 10 M postulaciones",
                                   "TF-IDF: 12,4 M pares en 54 s", "LSH a escala y FP-Growth"]),
        ("Mejor en local", VERDE, ["Sketches: secuenciales por definición", "FAISS: ms desde memoria",
                                    "DGIM y figuras"]),
        ("A 10× / 100×", TINTA, ["Fuerza bruta: 13 / 1 300 años", "HNSW no cabe → IVF-PQ",
                                  "Sketches casi no crecen", "DGIM: de curiosidad a necesidad"])]
for i, (t, c, items) in enumerate(cols):
    x = 0.6 + i * 4.1
    caja(sl, x, 1.6, 3.85, 3.85)
    txt(sl, x + 0.3, 1.85, 3.3, 0.5, t, size=21, bold=True, font=TITULO_F, color=c)
    viñetas(sl, x + 0.3, 2.5, 3.3, 2.9, items, size=15)
caja(sl, 0.6, 5.65, 12.13, 1.05, fill=TINTA)
txt(sl, 0.95, 5.7, 11.5, 0.95, [[("Overhead medido: ", {"bold": True, "color": BLANCO}),
    ("RDD en Python 58× más lento · firmas MinHash en SQL 37 min · ventana rowsBetween O(n·N) hasta usar suma acumulada.",
     {"color": SUAVE})]], size=15, anchor=MSO_ANCHOR.MIDDLE)

# =================================================================== 18 ÉTICA
sl = diapositiva("Datos públicos: transparencia sin estigmatizar", parte="VI", expone=CESAR, notas=(
    "CÉSAR (≈1 min). Con datos abiertos y herramientas estándar, un ciudadano, un periodista o una oficina de "
    "control puede priorizar qué revisar entre millones de procesos. Pero los mismos resultados pueden "
    "estigmatizar: un RUC que empieza con 10 es una persona natural, y un falso positivo o una regla con lift "
    "alto puede tener explicación legítima. Por eso publicamos etiquetas anónimas, P0001, damos siempre la "
    "lectura alternativa y no calificamos conductas. Y la calidad: el quiebre de 2015 y los registros pasivos "
    "muestran que un dato público mal entendido produce conclusiones espectaculares y falsas. El SEACE además no "
    "cubre compras menores a 8 UIT."))
eti = [("Transparencia", "Cualquier ciudadano u oficina de control puede priorizar qué revisar entre millones de procesos.", VERDE),
       ("Uso indebido", "RUC 10… es una persona natural. Publicamos etiquetas anónimas (P0001) y la lectura alternativa de cada hallazgo.", ROJO),
       ("Calidad y cobertura", "Quiebre de 2015, registros pasivos y sin compras < 8 UIT: un dato mal entendido da conclusiones falsas.", TINTA),
       ("Indicios, no pruebas", "Las técnicas priorizan auditorías; no reemplazan el expediente ni el derecho de defensa.", TINTA2)]
for i, (t, d, c) in enumerate(eti):
    x = 0.6 + (i % 2) * 6.17
    y = 1.6 + (i // 2) * 2.6
    caja(sl, x, y, 5.96, 2.35)
    ficha(sl, x + 0.3, y + 0.3, str(i + 1), fill=c, d=0.6, size=18)
    txt(sl, x + 1.15, y + 0.33, 4.5, 0.5, t, size=20, bold=True, font=TITULO_F)
    txt(sl, x + 1.15, y + 0.9, 4.5, 1.35, d, size=15, color=TINTA2)

# =================================================================== 19 DEMO
sl = diapositiva("Demostración: el reporte interactivo y el código", expone=AMBOS, notas=(
    "AMBOS (≈2 min). CÉSAR maneja el reporte web: (1) curva S de LSH moviendo b y r; (2) Bloom variando bits "
    "por clave; (3) filtros de reglas por soporte, confianza y lift. Arquitectura 'calcular una vez, explorar "
    "muchas': Spark corre offline y la página solo lee artefactos; lo que se recalcula en vivo son las fórmulas "
    "analíticas. ALEKSANDER muestra el código: el MinHash en Spark SQL sin UDF (script 10), el Apriori por "
    "niveles con reduceByKey (script 14) y el Bloom propio (script 13). Cada script indica en su cabecera qué "
    "corre en Spark y qué en local, y por qué; todo se reproduce con ejecutar_todo.py."))
caja(sl, 0.6, 1.6, 6.0, 5.1, fill=TINTA)
txt(sl, 0.95, 1.85, 5.3, 0.5, "Reporte web", size=21, bold=True, font=TITULO_F, color=BLANCO)
txt(sl, 0.95, 2.4, 5.3, 0.5, "cesarpr30.github.io/Proyecto_DataMining", size=16, color=SUAVE)
viñetas(sl, 0.95, 3.1, 5.3, 2.4, ["Curva S de LSH: mover b y r", "Bloom: bits por clave vs. falsos positivos",
                                   "Reglas: filtrar por soporte, confianza y lift"], size=16, color=BLANCO)
txt(sl, 0.95, 5.5, 5.3, 1.0, "Spark calcula una vez offline; la página solo lee artefactos y recalcula en vivo las fórmulas.",
    size=14, color=SUAVE)
caja(sl, 7.0, 1.6, 5.73, 5.1)
txt(sl, 7.35, 1.85, 5.1, 0.5, "Código", size=21, bold=True, font=TITULO_F, color=ROJO)
cod = [("10_parte2_similitud.py", "MinHash en Spark SQL con funciones de orden superior, sin UDF"),
       ("14_parte5_reglas.py", "Apriori por niveles: flatMap + reduceByKey + broadcast"),
       ("13_parte4_flujos.py", "Bloom, Count-Min y DGIM desde cero, una pasada"),
       ("ejecutar_todo.py", "Reproduce el pipeline completo (pasos 04 a 15)")]
for i, (f, d) in enumerate(cod):
    y = 2.5 + i * 1.02
    txt(sl, 7.35, y, 5.1, 0.4, f, size=15, bold=True, font="Consolas")
    txt(sl, 7.35, y + 0.4, 5.1, 0.5, d, size=14, color=TINTA2)

# =================================================================== 20 CONCLUSIONES
sl = diapositiva("Respuestas", oscura=True, expone=CESAR, notas=(
    "CÉSAR (≈1 min). Cerramos con las respuestas. P1: sí, en dos escalas; LSH encuentra parejas pequeñas que "
    "nunca se separan y FP-Growth grupos grandes; la red del Poder Judicial gana 83 % frente a 36 % esperado. "
    "P2: el 98 % de los casi-duplicados son reconvocatorias, pero el texto casi idéntico anticipa al ganador: "
    "15 % frente a 0,02 %. P3: sí se puede vigilar con memoria acotada: Bloom 100 veces más chico pierde 0,41 % "
    "de alertas. Y la conclusión metodológica: los algoritmos aproximados casi nunca fueron el problema; la "
    "representación y la calidad del dato sí. Gracias; quedamos atentos a sus preguntas."))
resp = [("P1", "Sí, en dos escalas. Red del Poder Judicial: gana 83 % frente a 36 % esperado. Parejas que nunca ganan = registros pasivos."),
        ("P2", "98 % de los casi-duplicados son reconvocatorias. Texto casi idéntico comparte ganador: 15 % vs 0,02 % al azar."),
        ("P3", "Sí: Bloom 100× más chico pierde 0,41 % de alertas; Count-Min recupera el top 20 con 512 KB.")]
for i, (k, r) in enumerate(resp):
    y = 1.65 + i * 1.3
    ficha(sl, 0.6, y, k, d=0.8, size=18)
    txt(sl, 1.65, y - 0.02, 11.0, 0.9, r, size=19, color=BLANCO, anchor=MSO_ANCHOR.MIDDLE)
txt(sl, 0.6, 5.65, 12.1, 1.0, [[("Lo aproximado casi nunca fue el problema; la representación y la calidad del dato sí. ",
    {"bold": True, "color": BLANCO}), ("¿Preguntas?", {"color": ROJO, "bold": True})]], size=22, font=TITULO_F)

SALIDA.parent.mkdir(exist_ok=True)
prs.save(SALIDA)
print(f"OK -> {SALIDA}  ({len(prs.slides)} diapositivas)")
