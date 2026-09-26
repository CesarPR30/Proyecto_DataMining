# -*- coding: utf-8 -*-
"""
Genera el Informe Inicial: Seleccion y Justificacion del Dataset (.docx).

Todas las cifras citadas provienen de los scripts 00, 01 y 02 de esta carpeta,
ejecutados sobre los datos descargados. El documento se regenera con:

    python scripts/03_generar_informe_docx.py

Salida: informe/Informe_Inicial_Seleccion_Dataset.docx
"""
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parent.parent
FIG = RAIZ / "informe" / "figuras"
SALIDA = RAIZ / "informe" / "Informe_Inicial_Seleccion_Dataset.docx"

AZUL = RGBColor(0x1F, 0x4E, 0x79)
GRIS = RGBColor(0x52, 0x51, 0x4E)


# --------------------------------------------------------------------- helpers
def estilo_base(doc):
    n = doc.styles["Normal"]
    n.font.name = "Calibri"
    n.font.size = Pt(10.5)
    n.paragraph_format.space_after = Pt(6)
    n.paragraph_format.line_spacing = 1.12
    for i, tam in ((1, 15), (2, 12.5), (3, 11)):
        h = doc.styles[f"Heading {i}"]
        h.font.name = "Calibri"
        h.font.size = Pt(tam)
        h.font.color.rgb = AZUL
        h.font.bold = True
        h.paragraph_format.space_before = Pt(14 if i == 1 else 10)
        h.paragraph_format.space_after = Pt(5)


def p(doc, texto="", *, bold=False, italic=False, size=None, color=None,
      align=None, space_after=None, style=None):
    par = doc.add_paragraph(style=style)
    run = par.add_run(texto)
    run.bold = bold
    run.italic = italic
    if size:
        run.font.size = Pt(size)
    if color:
        run.font.color.rgb = color
    if align:
        par.alignment = align
    if space_after is not None:
        par.paragraph_format.space_after = Pt(space_after)
    return par


def rico(doc, partes, *, style=None, size=None, align=None):
    """Parrafo con tramos (texto, negrita) para resaltar cifras."""
    par = doc.add_paragraph(style=style)
    for texto, bold in partes:
        r = par.add_run(texto)
        r.bold = bold
        if size:
            r.font.size = Pt(size)
    if align:
        par.alignment = align
    return par


def vinetas(doc, items, style="List Bullet"):
    for it in items:
        if isinstance(it, str):
            doc.add_paragraph(it, style=style)
        else:
            par = doc.add_paragraph(style=style)
            for texto, bold in it:
                par.add_run(texto).bold = bold


def sombrear(celda, hexcolor):
    tc = celda._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hexcolor)
    tc.append(shd)


def tabla(doc, cabecera, filas, anchos=None, size=8.5):
    t = doc.add_table(rows=1, cols=len(cabecera))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, txt in enumerate(cabecera):
        hdr[i].text = ""
        run = hdr[i].paragraphs[0].add_run(txt)
        run.bold = True
        run.font.size = Pt(size)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        sombrear(hdr[i], "1F4E79")
    for fila in filas:
        celdas = t.add_row().cells
        for i, txt in enumerate(fila):
            celdas[i].text = ""
            run = celdas[i].paragraphs[0].add_run(str(txt))
            run.font.size = Pt(size)
    if anchos:
        for fila in t.rows:
            for i, w in enumerate(anchos):
                fila.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def figura(doc, archivo, caption, ancho=16.0):
    doc.add_picture(str(FIG / archivo), width=Cm(ancho))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = p(doc, caption, size=8.5, italic=True, color=GRIS,
            align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10)
    return cap


def codigo(doc, texto):
    par = doc.add_paragraph()
    par.paragraph_format.left_indent = Cm(0.6)
    par.paragraph_format.space_after = Pt(8)
    run = par.add_run(texto)
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    run.font.color.rgb = GRIS
    return par


# ----------------------------------------------------------------------- build
def construir():
    doc = Document()
    estilo_base(doc)
    sec = doc.sections[0]
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.3)
    sec.right_margin = Cm(2.3)

    # =================================================================== PORTADA
    for _ in range(4):
        doc.add_paragraph()
    p(doc, "PROYECTO INTEGRADOR 1", bold=True, size=13, color=GRIS,
      align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    p(doc, "Minería de Datos Masivos y Flujos de Datos", size=12, color=GRIS,
      align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)
    p(doc, "Informe de Avance 1", bold=True, size=24, color=AZUL,
      align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    p(doc, "Selección del dataset, KDD y EDA (Parte I) y similitud (Parte II)",
      size=13, color=AZUL, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    p(doc, "Contrataciones Abiertas del Estado Peruano (OCDS - OECE/SEACE)",
      size=13, color=GRIS, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=40)

    tabla(doc, ["Campo", "Detalle"], [
        ["Curso", "Minería de Datos Masivos y Flujos de Datos"],
        ["Docente", "Prof. Heider Sanchez"],
        ["Entregable", "Semanas 1-2 - Dataset, Parte I y Parte II"],
        ["Equipo", "[Integrante 1]  -  [Integrante 2]  -  [Integrante 3]"],
        ["Fecha", "14 de setiembre de 2026"],
        ["Fuente de datos", "OECE / SEACE, vía OCP Data Registry (CC BY 4.0)"],
    ], anchos=[4.0, 12.0], size=10)

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ========================================================== RESUMEN EJECUTIVO
    doc.add_heading("1. Resumen ejecutivo", level=1)
    rico(doc, [
        ("El equipo selecciona como dataset del proyecto las ", False),
        ("contrataciones públicas del Estado peruano publicadas en estándar "
         "OCDS por el OECE", True),
        (" (ex OSCE) a partir del Sistema Electrónico de Contrataciones del "
         "Estado (SEACE), accedidas mediante la descarga masiva del ", False),
        ("OCP Data Registry", True),
        (". El corpus completo abarca ", False),
        ("enero 2003 - setiembre 2026", True),
        (" y contiene ", False),
        ("2 753 905 procesos de contratación, 2 011 059 adjudicaciones, "
         "1 320 800 contratos y 12 765 637 registros de partes", True),
        (", con actualización diaria y licencia CC BY 4.0.", False),
    ])
    p(doc, "La elección no se apoya en el prestigio de la fuente sino en "
           "verificación empírica: se descargó el corpus histórico completo "
           "(25 particiones anuales, 2,3 GB comprimidos) y se comprobó que "
           "contiene exactamente los 2 753 905 procesos que declara el "
           "publicador, sin un solo OCID duplicado entre particiones. Sobre ese "
           "corpus se perfilaron ocho particiones en detalle y se ejecutó una "
           "prueba de viabilidad que confirma que las seis técnicas del curso "
           "encuentran señal real en estos datos, y no solo que el dataset "
           "'cabe' en el enunciado.")
    p(doc, "Hallazgos que sostienen la decisión:", bold=True, space_after=3)
    vinetas(doc, [
        [("Volumen: ", True),
         ("17 GB en CSV sin comprimir para el histórico completo, con tablas "
          "de hasta 12,7 millones de filas. No es manejable cómodamente en "
          "pandas sobre 16 GB de RAM, pero sí en Spark con Parquet particionado.", False)],
        [("Conjuntos y vectores: ", True),
         ("cada proceso tiene una descripción libre de ~27 palabras (apta para "
          "shingling) y cada proveedor se representa naturalmente como el "
          "conjunto de procesos a los que postuló (76 638 proveedores solo en 2023).", False)],
        [("Dimensión temporal: ", True),
         ("marca de tiempo al minuto, sin nulos, con ~134 procesos publicados "
          "por día hábil: un flujo real, no una fecha decorativa.", False)],
        [("Estructura transaccional: ", True),
         ("la canasta 'proceso -> conjunto de postores' promedia 10,8-11,9 ítems "
          "y el 84 % de los procesos tiene dos o más postores; es una canasta "
          "densa y con significado, no un artificio.", False)],
        [("Señal verificada: ", True),
         ("en la prueba de viabilidad aparecen pares de proveedores con "
          "Jaccard 0,96 sobre sus conjuntos de procesos y reglas de asociación "
          "con confianza 0,92 y lift 20,6.", False)],
    ])
    p(doc, "El EDA posterior sobre Spark obligó además a acotar la ventana "
           "de análisis. Entre 2004 y 2014 el dataset registra 1,5 a 2,3 "
           "postores por proceso; desde 2015 salta a entre 4 y 15. El salto no "
           "describe un mercado que se volvió competitivo sino un cambio en lo "
           "que el SEACE registra, de modo que las preguntas sobre competencia "
           "se resuelven sobre 2015-2026 (810 872 canastas, 700 740 "
           "proveedores), y el corpus completo se reserva para la narrativa de "
           "volumen.")
    p(doc, "La Parte II ya está ejecutada y entrega el primer hallazgo con "
           "valor propio: sobre los 876 211 procesos de 2015-2026, LSH "
           "exploró el 0,001 % de los pares posibles y encontró 584 848 "
           "pares de descripciones casi idénticas, de las cuales el 98 % "
           "pertenece a la misma entidad -son reconvocatorias, no copias "
           "entre entidades-. Sobre los proveedores apareció un grupo de "
           "cuatro que concurre a exactamente los mismos 37 procesos, con "
           "Jaccard 1,000 en los seis pares posibles.")
    p(doc, "El informe documenta además las limitaciones detectadas (la "
           "partición anual no corresponde al año de publicación del proceso, "
           "7,7 % de montos no positivos, cobertura territorial de solo 9,2 %) "
           "y deja el corpus completo ya descargado y verificado en local, de "
           "modo que la Semana 1 puede dedicarse íntegramente al KDD y al EDA "
           "en Spark.")

    # ============================================================ 2. OBJETIVO
    doc.add_heading("2. Objetivo y alcance de este informe", level=1)
    p(doc, "Este documento corresponde al entregable parcial de la Semana 1 del "
           "cronograma sugerido: elección y justificación del dataset, y "
           "formulación de las preguntas de interés. No incluye todavía el KDD "
           "completo, el EDA en Spark ni los resultados de las Partes II a V; "
           "su propósito es dejar cerrada, con evidencia medida, la decisión de "
           "la que dependen todas las etapas siguientes.")
    p(doc, "El alcance cubre: (i) los criterios de selección aplicados, "
           "(ii) la comparación de las fuentes evaluadas, (iii) la verificación "
           "empírica de que el dataset elegido cumple los cuatro requisitos "
           "mínimos del enunciado, (iv) una prueba de viabilidad técnica, "
           "(v) las preguntas de interés y su mapeo a las técnicas del curso, "
           "(vi) las limitaciones de calidad detectadas, (vii) el estado de la "
           "descarga, el entorno instalado y la ingesta ya ejecutada, y "
           "(viii) los resultados del EDA de la Parte I sobre Spark, que se "
           "incorporaron porque cambiaron una decisión de diseño del "
           "proyecto, y (ix) los resultados de la Parte II: Jaccard exacto, "
           "MinHash, LSH y los primeros hallazgos sobre co-postulación.")

    # ============================================================ 3. CRITERIOS
    doc.add_heading("3. Criterios de selección aplicados", level=1)
    p(doc, "Se partió de los cuatro mínimos exigibles del enunciado y se "
           "agregaron tres criterios propios de viabilidad, porque un dataset "
           "que cumple los cuatro primeros pero no se puede descargar de forma "
           "reproducible bloquea el proyecto en la Semana 1.")
    tabla(doc, ["#", "Criterio", "Origen", "Cómo se verificó"], [
        ["C1", "Volumen suficiente para justificar procesamiento distribuido",
         "Enunciado", "Conteo de filas y peso en disco por partición anual"],
        ["C2", "Campos que permitan representar registros o entidades como "
               "conjuntos o vectores comparables",
         "Enunciado", "Longitud y duplicidad del texto libre; cardinalidad de "
                      "los conjuntos proveedor-proceso"],
        ["C3", "Dimensión temporal que permita simular llegada secuencial",
         "Enunciado", "Granularidad, nulos y densidad diaria de la marca de tiempo"],
        ["C4", "Estructura transaccional natural o derivable (canasta de ítems)",
         "Enunciado", "Tres canastas candidatas medidas: tamaño medio y % con "
                      ">= 2 ítems"],
        ["C5", "Descarga masiva programable y licencia abierta",
         "Propio", "Prueba real de descarga por HTTP y revisión de licencia"],
        ["C6", "Esquema documentado y estable en el tiempo",
         "Propio", "Estándar OCDS 1.1 con extensiones publicadas y política "
                   "de publicación"],
        ["C7", "Relevancia pública de los hallazgos en el contexto peruano",
         "Propio", "Pertinencia de las preguntas de interés formuladas"],
    ], anchos=[0.9, 5.0, 1.9, 8.2])

    # =============================================================== 4. FUENTES
    doc.add_heading("4. Fuentes evaluadas y descarte razonado", level=1)
    p(doc, "Se revisaron las seis fuentes sugeridas por el enunciado más el "
           "portal de órdenes de compra del propio OECE. La tabla resume la "
           "evaluación contra los criterios C1-C4; el detalle del descarte va "
           "a continuación.")
    tabla(doc, ["Fuente", "C1 Volumen", "C2 Conjuntos", "C3 Temporal",
                "C4 Canasta", "Decisión"], [
        ["Contrataciones Abiertas OCDS - OECE/SEACE",
         "Sí (17 GB CSV)", "Sí (texto + RUC)", "Sí (al minuto)",
         "Sí (proceso -> postores)", "ELEGIDA"],
        ["Órdenes de compra y servicio - CONOSCE/OECE",
         "Sí (mensual 2018-2025)", "Parcial", "Sí (fecha de orden)",
         "Parcial", "Descartada (complementaria)"],
        ["Plataforma Nacional de Datos Abiertos (PNDA)",
         "Heterogéneo", "Variable", "Variable", "Variable",
         "Catálogo, no dataset"],
        ["INEI - Microdatos (ENAHO, ENDES)",
         "Medio", "Sí (vectores)", "Débil (anual)", "Débil",
         "Descartada"],
        ["MEF - Transparencia Económica",
         "Sí (agregado)", "Débil", "Sí (mensual)", "Débil", "Descartada"],
        ["PERÚ COMPRAS - Catálogos electrónicos",
         "Medio", "Sí", "Sí", "Sí", "Descartada (subconjunto de OCDS)"],
    ], anchos=[4.6, 2.3, 2.2, 2.0, 2.6, 2.9], size=8)

    doc.add_heading("4.1 Por qué se descartaron las alternativas", level=2)
    vinetas(doc, [
        [("INEI - Microdatos (ENAHO/ENDES). ", True),
         ("Es la fuente más rica del país en variables socioeconómicas y "
          "encaja bien en vectores para ANN, pero su unidad de análisis es el "
          "hogar encuestado una vez al año. La dimensión temporal es anual y "
          "muestral, no un flujo de eventos: simular la llegada secuencial de "
          "los datos sería un artificio, y DGIM sobre una ventana de años no "
          "tiene sentido práctico. Además no existe una canasta natural de "
          "ítems por registro.", False)],
        [("MEF - Transparencia Económica / Consulta Amigable. ", True),
         ("Cubre la ejecución del gasto con actualización frecuente, pero se "
          "publica agregada por clasificador presupuestal (entidad, genérica, "
          "fuente de financiamiento). Al no haber registro individual con texto "
          "libre ni contrapartes identificadas, C2 y C4 quedan débiles: no hay "
          "entidades comparables como conjuntos ni transacciones que canastear.", False)],
        [("Plataforma Nacional de Datos Abiertos (PNDA). ", True),
         ("Es un catálogo de más de 4 700 datasets, no un dataset. Se usó como "
          "punto de partida para la búsqueda, pero elegirla como fuente "
          "obligaría igualmente a escoger uno de sus conjuntos; los de mayor "
          "volumen que cumplian los criterios resultaron ser, precisamente, los "
          "de contrataciones públicas.", False)],
        [("Órdenes de compra y servicio (CONOSCE). ", True),
         ("Es la alternativa más cercana y proviene de la misma entidad. Se "
          "descartó como fuente principal por dos razones operativas: se "
          "publica en archivos Excel mensuales separados (2018-2025), lo que "
          "encarece la ingesta reproducible, y cubre solo la compra directa por "
          "debajo de los umbrales, sin la sección de postores que es la que "
          "habilita la canasta más interesante del proyecto. Queda identificada "
          "como fuente complementaria para la discusión de la Parte VI.", False)],
        [("PERÚ COMPRAS - catálogos electrónicos. ", True),
         ("Sus procedimientos se registran también en SEACE, por lo que ya "
          "están contenidos en el dataset elegido; usarla por separado "
          "duplicaría el trabajo sobre un subconjunto.", False)],
    ])

    p(doc, "Nota sobre el enlace del enunciado: el dominio "
           "contratacionesabiertas.osce.gob.pe ya no resuelve. El portal "
           "vigente es contratacionesabiertas.oece.gob.pe/descargas, tras el "
           "cambio de OSCE a OECE. Se verificó la disponibilidad de ambos "
           "el 14/09/2026.", italic=True, size=9, color=GRIS)

    # ========================================================== 5. EL DATASET
    doc.add_heading("5. Dataset seleccionado", level=1)
    doc.add_heading("5.1 Identificación y procedencia", level=2)
    tabla(doc, ["Atributo", "Valor"], [
        ["Nombre", "Contrataciones Abiertas del Peru - estándar OCDS"],
        ["Entidad publicadora",
         "Organismo Especializado para las Contrataciones Públicas Eficientes "
         "(OECE), ex OSCE"],
        ["Sistema de origen",
         "Sistema Electrónico de Contrataciones del Estado (SEACE v3)"],
        ["Punto de acceso usado",
         "OCP Data Registry - publicación 135 (descarga masiva por año)"],
        ["Portal oficial del publicador",
         "https://contratacionesabiertas.oece.gob.pe/descargas"],
        ["Estándar", "Open Contracting Data Standard (OCDS) 1.1 + extensiones"],
        ["Prefijo OCID", "ocds-dgv273"],
        ["Rango temporal", "enero 2003 - setiembre 2026"],
        ["Frecuencia de actualización", "Diaria (recolección mensual del registro)"],
        ["Última recolección verificada", "4 de setiembre de 2026"],
        ["Licencia", "Creative Commons Attribution 4.0 International (CC BY 4.0)"],
        ["Formatos disponibles", "JSON Lines (.jsonl.gz), CSV (.tar.gz), Excel (.xlsx)"],
    ], anchos=[4.2, 11.8], size=9)

    p(doc, "Se trabaja con la variante CSV porque entrega el dataset ya "
           "normalizado en tablas relacionales, lo que evita una etapa de "
           "aplanado de JSON anidado antes de poder usar Spark SQL. La variante "
           "Excel se descarta por el límite de 1 048 576 filas, que deja fuera "
           "varios años.")

    doc.add_heading("5.2 Estructura del dataset", level=2)
    p(doc, "Cada partición anual entrega 21 archivos CSV relacionados. La tabla "
           "muestra los principales y su rol en el proyecto, con el conteo de "
           "filas medido en la partición 2025.")
    tabla(doc, ["Archivo", "Grano", "Filas (2025)", "Rol en el proyecto"], [
        ["main.csv", "Proceso de contratación", "125 451",
         "Tabla base del EDA: entidad, fecha, monto, método, descripción"],
        ["tender_tenderers.csv", "Proceso x postor", "1 391 680",
         "Canasta de la Parte V y conjuntos de la Parte II"],
        ["parties.csv", "Proceso x actor", "1 517 135",
         "Roles, identificadores y ubicación geográfica"],
        ["tender_items.csv", "Ítem licitado", "150 403",
         "Código CUBSO y descripción del bien o servicio"],
        ["awards.csv / awards_suppliers.csv", "Adjudicación", "~37 000 / ~37 000",
         "Ganador y monto adjudicado"],
        ["contracts.csv", "Contrato firmado", "~38 500",
         "Monto final y plazos de ejecución"],
        ["tender_items_additionalClassifications.csv", "Ítem x clasificación",
         "-", "Códigos UNSPSC, vocabulario alternativo de ítems"],
    ], anchos=[4.6, 3.0, 2.3, 6.1], size=8.5)

    p(doc, "Campos clave de main.csv usados en este informe:", bold=True,
      space_after=3)
    codigo(doc,
           "ocid, tender_datePublished, buyer_name, tender_title,\n"
           "tender_description, tender_mainProcurementCategory,\n"
           "tender_procurementMethodDetails, tender_value_amount_PEN,\n"
           "tender_numberOfTenderers, planning_budget_projectID")

    # ================================================== 6. VERIFICACION C1..C4
    doc.add_heading("6. Verificación empírica de los criterios del enunciado", level=1)
    p(doc, "Todas las cifras de esta sección se obtuvieron ejecutando los "
           "scripts 00 y 01 sobre los datos efectivamente descargados. No son "
           "cifras tomadas de la documentación del publicador.")

    # ---- C1
    doc.add_heading("6.1 C1 - Volumen suficiente para procesamiento distribuido", level=2)
    tabla(doc, ["Partición", "Procesos", "Ítems", "Filas de postores",
                "Filas de partes", "CSV sin comprimir"], [
        ["2023", "46 289", "53 602", "455 341", "501 631", "447 MB"],
        ["2024", "109 722", "132 236", "1 039 854", "1 149 577", "1 070 MB"],
        ["2025", "125 451", "150 403", "1 391 680", "1 517 135", "1 321 MB"],
        ["Histórico completo (25 particiones, medido en local)",
         "2 753 905", "5 138 329", "10 011 706", "12 765 637", "17 GB"],
    ], anchos=[4.4, 2.3, 2.3, 2.7, 2.5, 2.8], size=8.5)
    p(doc, "La fila del histórico se verificó contando las 25 particiones "
           "descargadas: la suma de filas de main.csv da 2 753 905 y el número "
           "de OCID distintos es idéntico, es decir que no hay ningún proceso "
           "repetido entre particiones y el corpus local coincide exactamente "
           "con lo que declara el publicador. El rango efectivo de "
           "tender_datePublished va del 26/01/2003 al 03/09/2026.",
      size=9, color=GRIS)

    rico(doc, [
        ("Los 17 GB se midieron tras descomprimir las 25 particiones: la "
         "descarga pesa ", False),
        ("2,3 GB comprimidos", True),
        (" y se expande unas 7 veces al descomprimirse. Con ", False),
        ("16 GB de RAM", True),
        (", cargar la tabla de partes (12,7 millones de filas) junto con la de "
         "postores en un único proceso pandas no es viable de forma cómoda, "
         "mientras que en Spark el mismo trabajo se resuelve por particiones y, "
         "convertido a Parquet con compresión Snappy, el corpus baja al orden "
         "de 1,5-2 GB.", False),
    ])
    p(doc, "El argumento del volumen no descansa solo en el tamaño en disco. "
           "Las operaciones que el proyecto necesita son las que realmente "
           "escalan mal: la comparación de todos los pares de procesos es "
           "O(n^2) y sobre 2,7 millones de procesos implica del orden de 3,8 "
           "billones de pares, lo que hace obligatorio el enfoque "
           "MinHash + LSH de la Parte II en lugar de la fuerza bruta.")
    figura(doc, "fig1_volumen_temporal.png",
           "Figura 1. Volumen mensual de procesos publicados, 2003-2026 "
           "(2 753 905 procesos; agregado calculado en Spark). El pico "
           "histórico es diciembre de 2008 con 37 413 procesos en un solo mes; "
           "desde 2016 el flujo se estabiliza entre 5 000 y 8 000 mensuales. "
           "La caída de cada enero es sistemática: enero promedia 3 370 "
           "procesos frente a 10 692 del resto de meses, un 68 % menos, "
           "coherente con el ciclo presupuestal del sector público.")

    # ---- C2
    doc.add_heading("6.2 C2 - Registros y entidades representables como conjuntos "
                    "o vectores", level=2)
    p(doc, "El dataset admite dos representaciones distintas y complementarias, "
           "que es justamente lo que permite reutilizar el trabajo entre las "
           "Partes II, III y V.")
    p(doc, "(a) El proceso como conjunto de shingles de su descripción.",
      bold=True, space_after=3)
    tabla(doc, ["Métrica sobre tender_description", "2023", "2024", "2025"], [
        ["Registros con descripción no nula", "100,0 %", "100,0 %", "100,0 %"],
        ["Longitud media (caracteres)", "178,7", "173,9", "182,0"],
        ["Longitud media (palabras)", "27,1", "-", "-"],
        ["Descripciones exactamente duplicadas", "9,95 %", "10,25 %", "12,48 %"],
    ], anchos=[7.5, 2.8, 2.8, 2.8], size=8.5)
    p(doc, "Una descripción de ~27 palabras es suficiente para shingles de "
           "k = 5 caracteres o de 2-3 palabras. El dato relevante es el último: "
           "entre el 10 % y el 12 % de las descripciones se repite de forma "
           "exacta, lo que anticipa una masa mucho mayor de casi-duplicados que "
           "solo la similitud aproximada puede encontrar.")
    p(doc, "(b) El proveedor como conjunto de procesos a los que postuló.",
      bold=True, space_after=3)
    tabla(doc, ["Métrica sobre tender_tenderers (2023)", "Valor"], [
        ["Proveedores distintos (RUC)", "76 638"],
        ["Procesos promedio por proveedor", "5,94"],
        ["Mediana", "1"],
        ["Percentil 95", "22"],
        ["Máximo", "1 759"],
        ["Proveedores con 5 o más procesos", "16 602 (21,7 %)"],
    ], anchos=[9.0, 7.0], size=8.5)
    p(doc, "Esta segunda representación es la que da sentido a la similitud de "
           "Jaccard entre entidades: dos proveedores cuyos conjuntos de "
           "procesos coinciden casi por completo están postulando "
           "sistemáticamente a lo mismo. Además, la descripción y los códigos "
           "CUBSO (9 519 códigos distintos en 2023, 20 571 en 2025, con 84,5 % "
           "de cobertura) proveen el vocabulario para la vectorización TF-IDF "
           "de la Parte III.")

    # ---- C3
    doc.add_heading("6.3 C3 - Dimensión temporal apta para simular un flujo", level=2)
    tabla(doc, ["Propiedad del campo tender_datePublished", "Valor medido (2023)"], [
        ["Nulos", "0,00 %"],
        ["Granularidad", "Fecha y hora al minuto (ej. 2015-04-24T11:27:00-05:00)"],
        ["Días con actividad en el año", "302"],
        ["Procesos por día - media", "133,7"],
        ["Procesos por día - mediana", "132"],
        ["Procesos por día - máximo", "316"],
    ], anchos=[8.5, 7.5], size=8.5)
    p(doc, "El campo no tiene nulos y llega al minuto, de modo que el orden de "
           "llegada es un orden real y no una reconstrucción. Con ~134 eventos "
           "por día hábil, una ventana deslizante de 30 días contiene del orden "
           "de 4 000 eventos: suficiente para que DGIM sobre una ventana "
           "reciente tenga un conteo exacto contra el cual compararse, y para "
           "que el Bloom Filter enfrente reapariciones genuinas de proveedores.")

    # ---- C4
    doc.add_heading("6.4 C4 - Estructura transaccional: elección de la canasta", level=2)
    p(doc, "Este fue el criterio que exigió más análisis, porque la canasta "
           "aparentemente obvia resulta ser la peor. Se midieron tres "
           "definiciones candidatas:")
    tabla(doc, ["Canasta candidata", "N.º de canastas (2025)",
                "Ítems promedio", "% con >= 2 ítems", "Veredicto"], [
        ["A. Proceso -> conjunto de postores (RUC)", "116 848", "11,91", "84,3 %",
         "Elegida como principal"],
        ["B. Proceso -> conjunto de códigos de ítem", "125 451", "0,91", "3,7 %",
         "Descartada"],
        ["C. Entidad -> códigos de ítem comprados en el año", "2 992", "24,31",
         "82,2 %", "Elegida como secundaria"],
    ], anchos=[5.6, 2.7, 2.2, 2.3, 3.2], size=8.5)
    p(doc, "Las cifras anteriores corresponden a 2025. Al construir la canasta "
           "sobre el corpus completo aparece una diferencia que obligó a acotar "
           "la ventana de análisis: sobre 2003-2026 la canasta A promedia solo "
           "4,93 ítems y el 50,9 % llega a dos o más, mientras que restringida "
           "a 2015-2026 vuelve a 9,74 ítems y 82,7 %. El motivo no es que la "
           "competencia haya cambiado, sino que antes de 2015 el registro de "
           "postores era incompleto; se documenta en la sección 12.2. La "
           "ventana de trabajo para las Partes II y V queda fijada en "
           "2015-2026: 810 872 canastas y 700 740 RUC distintos, volumen más "
           "que suficiente.", size=9, color=GRIS)
    rico(doc, [
        ("La canasta B se descarta con dato en mano: en el Perú la gran mayoría "
         "de los procesos SEACE registra ", False),
        ("un solo ítem", True),
        (" (0,91 códigos distintos por proceso, y solo 3,7 % con dos o más). "
         "Aplicar Apriori o FP-Growth sobre canastas de tamaño 1 no produciría "
         "ningún conjunto frecuente de tamaño 2: la técnica correría pero no "
         "diría nada. Este es exactamente el tipo de verificación que justifica "
         "haber perfilado el dataset antes de comprometer el proyecto.", False),
    ])
    p(doc, "La canasta A, en cambio, es densa y tiene lectura directa: cada "
           "proceso es una 'transacción' y los postores que se presentaron son "
           "los 'ítems'. Un conjunto frecuente de dos o tres RUC significa que "
           "esas empresas concurren juntas a los mismos procesos con una "
           "frecuencia muy superior a la esperable por azar, que es precisamente "
           "el patrón que interesa investigar. La canasta C aporta la lectura "
           "complementaria del lado de la demanda: que categorías de bienes y "
           "servicios compra junta una misma entidad.")

    # ================================================== 7. PRUEBA DE VIABILIDAD
    doc.add_heading("7. Prueba de viabilidad técnica", level=1)
    p(doc, "Cumplir los criterios formales no garantiza que las técnicas "
           "encuentren algo. Antes de fijar el dataset se ejecutó una prueba en "
           "pequeño sobre la partición 2023 (script 01), con muestreo y fuerza "
           "bruta, para comprobar que hay señal. Los resultados se resumen a "
           "continuación.")

    doc.add_heading("7.1 Shingling y Jaccard sobre las descripciones", level=2)
    tabla(doc, ["Medición", "Resultado"], [
        ["Muestra", "3 000 procesos con descripción no nula"],
        ["Pares comparados por fuerza bruta", "4 453 620"],
        ["Pares con Jaccard >= 0,6 (shingles de 5 caracteres)", "162"],
        ["Proporción de pares similares", "0,0036 %"],
    ], anchos=[9.0, 7.0], size=8.5)
    p(doc, "La conclusión es doble. Primero, existen casi-duplicados reales: se "
           "encontraron procesos con Jaccard 1,0 entre distintos OCID de la "
           "misma entidad, lo que sugiere reconvocatorias o procesos declarados "
           "desiertos y vueltos a publicar. Segundo, la densidad de pares "
           "similares es de 36 por millón; sobre el corpus completo la fuerza "
           "bruta sería inviable y LSH deja de ser un ejercicio académico para "
           "ser la única vía práctica.")

    doc.add_heading("7.2 Jaccard entre proveedores", level=2)
    p(doc, "Tomando cada proveedor como el conjunto de procesos a los que "
           "postulo en 2023, y limitando a los 9 024 proveedores con 10 o más "
           "procesos, una muestra de 1 200 arrojó 43 pares con Jaccard >= 0,5. "
           "Los cinco más altos:")
    tabla(doc, ["Jaccard", "Proveedor A (n.º procesos)", "Proveedor B (n.º procesos)"], [
        ["0,962", "Empresa constructora (26)", "Empresa constructora (25)"],
        ["0,947", "Empresa de distribución y obras (18)", "Empresa vial (19)"],
        ["0,909", "Consorcio de obras (22)", "Empresa de servicios (20)"],
        ["0,868", "Contratista general (35)", "Contratista general (36)"],
        ["0,860", "Persona natural (39)", "Persona natural (41)"],
    ], anchos=[1.8, 7.1, 7.1], size=8)
    p(doc, "Un Jaccard de 0,96 significa que de los ~26 procesos a los que "
           "postuló cada empresa, prácticamente todos son los mismos. Es el "
           "patrón que el proyecto quiere poder detectar a escala, y aparece ya "
           "en una muestra pequeña de un solo año.")

    doc.add_heading("7.3 Reglas de asociación sobre la canasta elegida", level=2)
    p(doc, "Sobre 33 951 canastas de entre 2 y 40 postores (65 327 RUC "
           "distintos, 1 745 153 pares co-ocurrentes) se calcularon los pares "
           "más frecuentes y sus métricas:")
    tabla(doc, ["Soporte", "Confianza", "Lift", "Regla (A -> B)"], [
        ["0,0329", "0,915", "20,6", "Proveedor P1 -> Proveedor P2"],
        ["0,0114", "0,395", "13,9", "Proveedor P3 -> Proveedor P4"],
        ["0,0109", "0,892", "20,1", "Proveedor P5 -> Proveedor P2"],
        ["0,0097", "0,334", "18,7", "Proveedor P3 -> Proveedor P6"],
        ["0,0094", "0,261", "21,3", "Proveedor P1 -> Proveedor P5"],
    ], anchos=[1.9, 2.0, 1.4, 10.7], size=8)
    rico(doc, [
        ("Una confianza de ", False), ("0,915", True),
        (" con lift ", False), ("20,6", True),
        (" se lee así: cuando el primer proveedor se presenta a un proceso, el "
         "segundo lo acompaña en el 91,5 % de los casos, veinte veces más de lo "
         "que cabría esperar si ambos eligieran procesos de forma independiente. "
         "El corpus produce reglas interpretables sin necesidad de forzar los "
         "umbrales.", False),
    ])
    p(doc, "El número de pares co-ocurrentes (1,7 millones) sobre solo 34 mil "
           "canastas de un único año anticipa además por qué Apriori se limitará "
           "a un subconjunto y FP-Growth correrá sobre el corpus mayor, tal como "
           "pide la Parte V.")

    doc.add_heading("7.4 Síntesis de la prueba", level=2)
    tabla(doc, ["Parte del proyecto", "Técnica", "Evidencia de viabilidad"], [
        ["I", "Spark, EDA, KDD",
         "2 753 905 procesos, 21 tablas relacionadas, 17 GB en el histórico"],
        ["II", "Shingling, MinHash, LSH",
         "0,0036 % de pares similares: la fuerza bruta no escala; hay "
         "casi-duplicados reales"],
        ["III", "ANN (IVF / HNSW)",
         "Descripciones de ~27 palabras y 20 571 códigos CUBSO para TF-IDF"],
        ["IV", "DGIM, Bloom, Count-Min",
         "Marca de tiempo al minuto sin nulos; ~134 eventos/día; reapariciones "
         "frecuentes de RUC"],
        ["V", "Apriori / FP-Growth",
         "Canasta de 11,9 ítems promedio; reglas con confianza 0,92 y lift 20,6"],
        ["VI", "Análisis y discusión",
         "Concentración del gasto y co-postulación: hallazgos con lectura "
         "pública directa"],
    ], anchos=[1.8, 3.6, 10.6], size=8.5)

    # ================================================ 8. PREGUNTAS DE Interés
    doc.add_heading("8. Preguntas de interés del equipo", level=1)
    p(doc, "Las tres preguntas se formularon después del perfilado, no antes, "
           "para que fueran respondibles con los campos que el dataset "
           "realmente tiene y con las técnicas del curso.")

    doc.add_heading("P1. ¿Existen grupos de proveedores que concurren "
                    "sistemáticamente a los mismos procesos, y dónde se "
                    "concentran?", level=2)
    vinetas(doc, [
        [("Por qué importa: ", True),
         ("la competencia efectiva es el mecanismo por el que el Estado obtiene "
          "mejores precios. Si un grupo de empresas se presenta siempre en "
          "bloque a los mismos procesos de la misma entidad, la competencia "
          "puede ser aparente. En 2023, el 15,5 % de los procesos con número de "
          "postores declarado tuvo un único postor.", False)],
        [("Cómo se responde: ", True),
         ("canasta 'proceso -> postores' con FP-Growth (Parte V) para los "
          "conjuntos frecuentes, y Jaccard/MinHash/LSH sobre 'proveedor -> "
          "conjunto de procesos' (Parte II) para los pares de alta coincidencia. "
          "La agregación por entidad y departamento sale del EDA en Spark "
          "(Parte I).", False)],
        [("Qué sería un hallazgo: ", True),
         ("un conjunto de tres o más RUC con soporte y lift altos concentrado en "
          "pocas entidades compradoras y en un rubro específico.", False)],
    ])

    doc.add_heading("P2. ¿Qué tan reutilizadas son las especificaciones de los "
                    "procesos, y los procesos casi idénticos terminan con los "
                    "mismos postores?", level=2)
    vinetas(doc, [
        [("Por qué importa: ", True),
         ("la reutilización de especificaciones puede indicar buenas prácticas "
          "de estandarización o, al contrario, términos de referencia copiados "
          "que reproducen un sesgo. Distinguir un caso del otro exige cruzar la "
          "similitud del texto con quién se presenta y quién gana.", False)],
        [("Cómo se responde: ", True),
         ("shingling sobre tender_description, firmas MinHash y LSH por bandas "
          "para obtener los pares candidatos a escala (Parte II); luego "
          "TF-IDF + ANN (Parte III) para consultar, dado un proceso, sus "
          "vecinos más cercanos y comparar contra la búsqueda exacta.", False)],
        [("Qué sería un hallazgo: ", True),
         ("familias de procesos con similitud alta que comparten ganador, frente "
          "a familias igual de similares con ganadores rotativos: el contraste "
          "es lo informativo, no la similitud sola.", False)],
    ])

    doc.add_heading("P3. ¿Es posible vigilar el flujo de contrataciones en una "
                    "sola pasada y con memoria acotada, sin perder las alertas "
                    "que daría el conteo exacto?", level=2)
    vinetas(doc, [
        [("Por qué importa: ", True),
         ("un órgano de control no puede reprocesar el histórico cada día. La "
          "pregunta práctica es cuánta precisión se sacrifica al monitorear el "
          "flujo con estructuras de resumen, y si ese sacrificio cambia alguna "
          "decisión.", False)],
        [("Cómo se responde: ", True),
         ("simulación del flujo ordenado por tender_datePublished; Bloom Filter "
          "para detectar la reaparición de un RUC en la ventana reciente; "
          "Count-Min Sketch para estimar las frecuencias de entidades y "
          "proveedores; DGIM para contar, sobre la ventana de los últimos N "
          "días, cuántos procesos superaron un umbral de monto (Parte IV). Cada "
          "estimación se contrasta con el valor exacto calculado en Spark.", False)],
        [("Qué sería un hallazgo: ", True),
         ("el punto en que reducir la memoria empieza a producir falsos "
          "positivos que cambiarían una alerta, expresado en MB y no solo en "
          "tasa de error.", False)],
    ])

    p(doc, "Como soporte descriptivo de las tres, el EDA de la Parte I "
           "caracteriza la concentración del gasto (Figura 2). Los resultados "
           "completos del EDA se presentan en la sección 12.")
    figura(doc, "fig3_concentracion.png",
           "Figura 2. Concentración del monto convocado por entidad compradora, "
           "2015-2026 (S/ 984,2 mil millones sobre 825 003 procesos con monto "
           "declarado). El 1 % de las 3 163 entidades concentra el 40,6 % del "
           "monto, el 5 % concentra el 66,9 % y el 10 % llega al 76,9 %. La "
           "línea punteada marca la distribución perfectamente igualitaria.")

    # ============================================================ 9. MAPEO
    doc.add_heading("9. Mapeo del dataset a las partes del proyecto", level=1)
    tabla(doc, ["Parte", "Qué se usará del dataset", "Representación"], [
        ["I. KDD, EDA y Spark",
         "main.csv + parties.csv de todas las particiones anuales",
         "DataFrame particionado por año y mes de tender_datePublished, en Parquet"],
        ["II. Jaccard, MinHash, LSH",
         "tender_description; tender_tenderers",
         "Conjunto de shingles de 5 caracteres; conjunto de OCID por RUC"],
        ["III. ANN (IVF / HNSW)",
         "tender_description + tender_items.classification_description",
         "Vector TF-IDF por proceso"],
        ["IV. DGIM, Bloom, CMS",
         "main.csv ordenado por tender_datePublished",
         "Flujo de eventos (ocid, buyer, ruc, monto, timestamp)"],
        ["V. Apriori / FP-Growth",
         "tender_tenderers (canasta A); tender_items por entidad (canasta C)",
         "Lista de RUC por proceso; lista de códigos CUBSO por entidad-año"],
        ["VI. Análisis y reporte",
         "Artefactos agregados exportados desde Spark",
         "Parquet/CSV/JSON ligeros que alimentan la página web"],
    ], anchos=[3.0, 6.0, 7.0], size=8.5)

    # =================================================== 10. CALIDAD Y LIMITES
    doc.add_heading("10. Calidad de los datos y limitaciones detectadas", level=1)
    p(doc, "El perfilado dejó a la vista varios problemas que condicionan el "
           "preprocesamiento de la Parte I. Se documentan aquí porque afectan "
           "la interpretación de los resultados, no solo la limpieza.")
    tabla(doc, ["Hallazgo", "Magnitud medida", "Tratamiento previsto"], [
        ["La partición anual del archivo no corresponde al año de publicación "
         "del proceso",
         "El archivo 2023 trae 46 289 procesos, pero los publicados realmente "
         "en 2023 son 76 572 (sin OCID repetidos entre particiones)",
         "Reparticionar en Spark por año y mes de tender_datePublished; no "
         "asumir que el nombre del archivo indica el periodo. Ya aplicado en "
         "la ingesta"],
        ["El esquema cambia entre años: main.csv tiene 5 juegos de columnas "
         "distintos entre 2003 y 2026",
         "Verificado comparando los encabezados de las 25 particiones",
         "Leer partición por partición y unir con unionByName(allowMissing"
         "Columns=True). Un lector único con glob infiere el esquema del primer "
         "archivo y desalinea las columnas del resto en silencio"],
        ["El monto normalizado a soles (tender_value_amount_PEN) solo existe "
         "desde 2015",
         "100 % nulo de 2003 a 2012; 97,9 % en 2013; 64,1 % en 2014; 0 % desde "
         "2017. El monto original (tender_value_amount) está presente en el "
         "100 % de las filas de todos los años",
         "Para series largas usar tender_value_amount con su moneda, o acotar "
         "el análisis monetario a 2015-2026. Es el riesgo más serio de este "
         "dataset: usar la columna PEN sin filtrar el periodo daría por "
         "inexistente el gasto anterior a 2015"],
        ["El registro de postores cambia radicalmente en 2015",
         "1,5-2,3 postores por proceso y 56-81 % de postor único entre 2004 y "
         "2014, frente a 4-15 postores y 11-14 % de postor único desde 2015",
         "Acotar a 2015-2026 todo análisis de competencia y co-postulación. "
         "Es un cambio en lo que el sistema registra, no en el mercado; ver "
         "sección 12.2"],
        ["Montos no positivos", "3 551 de 46 289 procesos en 2023 (7,7 %)",
         "Excluir de los análisis de monto y reportar el volumen excluido"],
        ["Número de postores declarado ausente",
         "9,19 % (2023), 6,86 % (2025)",
         "Recalcular desde tender_tenderers en lugar de confiar en el campo"],
        ["Identificador de proyecto de inversión ausente",
         "64,81 % (2023)",
         "No usar como clave de análisis; solo como atributo opcional"],
        ["Cobertura geográfica pobre en parties.address_department",
         "Solo 9,23 % de las filas (2023), 25 departamentos",
         "Derivar la ubicación desde el nombre de la entidad compradora o "
         "acotar el análisis territorial a la submuestra con dato"],
        ["Identificadores duplicados entre tenderer y parties",
         "Documentado por el publicador",
         "Normalizar por RUC y deduplicar antes de construir los conjuntos"],
        ["Cobertura del universo de compras",
         "Excluye contrataciones por debajo de 3, 8 y 9 UIT",
         "Declarar explícitamente el alcance al interpretar montos agregados"],
    ], anchos=[5.2, 4.4, 6.4], size=8)

    p(doc, "La última limitación es la más importante para no sobreinterpretar "
           "los resultados: el dataset cubre los procedimientos de selección "
           "registrados en SEACE, de modo que las conclusiones son sobre la "
           "contratación formal por procedimiento y no sobre el gasto público "
           "total.")

    # ======================================== 11. ESTADO DE DESCARGA Y PLAN
    doc.add_heading("11. Estado de la descarga y plan de ingesta", level=1)
    p(doc, "La descarga masiva se automatizó contra el endpoint por año del OCP "
           "Data Registry, evitando la descarga manual archivo por archivo:")
    codigo(doc,
           "https://data.open-contracting.org/en/publication/135/"
           "download?name=<AÑO>.csv.tar.gz")
    tabla(doc, ["Tramo", "Estado al 14/09/2026", "Observación"], [
        ["2003-2026 (24 particiones anuales)", "Descargado y verificado",
         "Integridad del archivo comprobada una por una; 2,3 GB comprimidos"],
        ["Partición 1900", "Descargada",
         "Contiene 1 proceso sin fecha válida; junto con otros 12 del "
         "resto del corpus queda aislado en la partición anio=0"],
        ["Descompresión", "Completa",
         "21 archivos CSV por partición, 17 GB medidos en disco"],
        ["Histórico completo (all-time)", "No necesario",
         "La unión de las particiones anuales reproduce exactamente el conteo "
         "del publicador"],
    ], anchos=[3.6, 3.8, 8.6], size=8.5)

    doc.add_heading("11.1 Entorno de ejecución instalado y verificado", level=2)
    p(doc, "El entorno ya está montado y probado sobre datos reales del corpus. "
           "Se instaló sin privilegios de administrador, en el perfil del "
           "usuario, para que sea replicable por cualquier integrante del "
           "equipo:")
    tabla(doc, ["Componente", "Versión", "Ubicación / nota"], [
        ["Python", "3.14.6", "Intérprete del sistema"],
        ["PySpark", "4.2.0", "pip; incluye Apache Spark y Hadoop client 3.5.0"],
        ["JDK (Temurin)", "17.0.20.1+1",
         "ZIP portable en ~/tools/jdk-17.0.20.1+1; JAVA_HOME de usuario"],
        ["winutils.exe + hadoop.dll", "build Hadoop 3.4.0 para Windows",
         "~/tools/hadoop-3.4.0/bin; Apache no publica binarios nativos para "
         "Windows y Spark los necesita para escribir Parquet en disco local"],
        ["PyArrow", "25.0.1", "Conversión Spark <-> pandas"],
    ], anchos=[4.0, 4.0, 8.0], size=8.5)
    p(doc, "La verificación (script 04) confirma sobre la partición 2025: "
           "lectura de CSV con Spark (125 451 filas), escritura y relectura de "
           "Parquet, FP-Growth sobre 92 940 canastas (315 conjuntos frecuentes, "
           "197 reglas, lift máximo 102,3) y MinHashLSH sobre los conjuntos de "
           "procesos por proveedor (5 183 pares candidatos, el más similar con "
           "Jaccard 1,000). Es decir, las dos piezas de MLlib de las que "
           "dependen las Partes II y V ya corren sobre el dataset elegido.")
    p(doc, "Advertencia registrada: PySpark 4.2 avisa que aún no soporta "
           "plenamente pandas 3.0. Las conversiones usadas hasta ahora "
           "funcionan; si apareciera un fallo en la interoperabilidad, la "
           "solución es fijar pandas < 3.0 en un entorno virtual del proyecto.",
      size=9, color=GRIS)

    doc.add_heading("11.2 Ingesta a Parquet: ejecutada y verificada", level=2)
    p(doc, "La conversión de los CSV crudos a Parquet ya se ejecutó (script 05). "
           "Se convirtieron las 12 tablas que el proyecto usa, omitiendo a "
           "propósito las de documentos adjuntos, la tabla sources (constante) "
           "y las de tipo de cambio, que no intervienen en ninguna pregunta de "
           "interés.")
    tabla(doc, ["Tabla", "Filas", "Parquet"], [
        ["main", "2 753 905", "431 MB"],
        ["tender_tenderers", "10 011 706", "314 MB"],
        ["tender_items", "5 138 329", "355 MB"],
        ["parties", "12 765 637", "711 MB"],
        ["awards / awards_items / awards_suppliers",
         "2 011 059 / 2 953 782 / 2 001 831", "80 / 203 / 108 MB"],
        ["contracts / contracts_items", "1 320 800 / 1 606 559", "148 / 119 MB"],
        ["Clasificaciones adicionales e identificadores",
         "5 757 123", "181 MB"],
        ["TOTAL (12 tablas)", "46 320 731", "2,59 GB"],
    ], anchos=[6.6, 5.4, 4.0], size=8.5)
    rico(doc, [
        ("El corpus pasa de ", False), ("16,0 GB en CSV a 2,59 GB en Parquet", True),
        (" (factor 6,2) en ", False), ("2,7 minutos", True),
        (" sobre la máquina de trabajo. Cada tabla se verificó dos veces: "
         "contra el número de líneas de sus CSV de origen y contra los conteos "
         "que publica el OCP Data Registry. ", False),
        ("Las nueve tablas comparables coinciden exactamente con lo declarado "
         "por el publicador", True),
        (", de modo que el corpus local está completo y la conversión no perdió "
         "ni duplicó ninguna fila.", False),
    ])
    p(doc, "Además se comprobó que solo 13 de los 2 753 905 procesos carecen de "
           "fecha válida, que el particionado por año habilita la poda de "
           "particiones, y que el año de publicación se propagó correctamente a "
           "las tablas hijas (1 fila sin resolver en tender_tenderers, 14 en "
           "parties). El monto convocado acumulado del histórico completo "
           "asciende a S/ 1 006,8 mil millones.", size=9, color=GRIS)

    p(doc, "Pendiente para cerrar la Semana 1:", bold=True, space_after=3)
    vinetas(doc, [
        "Construir y persistir las dos representaciones reutilizables: el "
        "conjunto de shingles por proceso y el conjunto de procesos por RUC.",
        "Completar el EDA de la Parte I sobre el Parquet ya generado.",
    ])
    p(doc, "Nota operativa: los datos se almacenan fuera de la carpeta "
           "sincronizada por OneDrive (C:\\Users\\cesar\\Proyecto-DataMining-data) "
           "para evitar la sincronización de decenas de GB. El repositorio del "
           "proyecto contiene solo el código y los artefactos ligeros.",
      italic=True, size=9, color=GRIS)

    # ===================================================== 12. ETICA
    # ============================================ 12. EDA PARTE I EN SPARK
    doc.add_heading("12. Primeros resultados del EDA en Spark (Parte I)", level=1)
    p(doc, "Con el corpus ya en Parquet se ejecutó el EDA de la Parte I "
           "íntegramente en Spark (script 08). Todo el cálculo pesado corre "
           "offline y se exporta como agregados ligeros en CSV y JSON, que son "
           "los que alimentan estas figuras y alimentarán después el reporte "
           "web interactivo. Ninguna figura vuelve a recorrer los 46 millones "
           "de filas: es la arquitectura 'calcular una vez, explorar muchas' "
           "que pide el enunciado.")

    doc.add_heading("12.1 Distribución temporal y estacionalidad", level=2)
    p(doc, "La serie mensual completa (Figura 1) muestra un corpus muy "
           "desigual en el tiempo: 2008 fue el año más activo con 314 598 "
           "procesos, más de cuatro veces el volumen de 2025, y desde 2016 la "
           "publicación se estabiliza entre 5 000 y 8 000 procesos mensuales. "
           "El patrón más regular es la caída de enero, un 68 % por debajo del "
           "resto de meses, que responde al ciclo presupuestal: las entidades "
           "recién aprueban su plan anual de contrataciones en el primer "
           "trimestre. Para la Parte IV esto importa: un flujo con "
           "estacionalidad fuerte es un mejor banco de pruebas para DGIM que "
           "uno uniforme, porque la ventana reciente sí cambia de "
           "comportamiento.")

    doc.add_heading("12.2 El hallazgo principal: el registro de postores "
                    "cambia en 2015", level=2)
    rico(doc, [
        ("El EDA dejó al descubierto un ", False),
        ("quiebre estructural", True),
        (" que condiciona todo el proyecto. Entre 2004 y 2014 el dataset "
         "registra en promedio ", False),
        ("1,5 a 2,3 postores por proceso", True),
        (" y entre el 56 % y el 81 % de los procesos aparecen con un único "
         "postor. A partir de 2015 la media salta a 4,03 y sigue subiendo "
         "hasta ", False),
        ("14,56 postores en 2024", True),
        (", mientras el porcentaje de postor único se desploma al 11-14 %.", False),
    ])
    p(doc, "La interpretación importa más que la cifra. Un cambio de esta "
           "magnitud en un solo año no describe un mercado que de pronto se "
           "volvió competitivo: describe un cambio en lo que el sistema "
           "registra. Antes de 2015 el SEACE publicaba principalmente al "
           "ganador y no la relación completa de participantes. Tomar esos "
           "datos al pie de la letra llevaría a concluir que la competencia en "
           "las compras públicas peruanas se multiplicó por siete en una "
           "década, que sería un hallazgo espectacular y falso.")
    p(doc, "Consecuencia metodológica adoptada: la ventana analítica para las "
           "preguntas sobre competencia y montos queda fijada en 2015-2026. El "
           "corpus 2003-2026 completo se conserva para la narrativa de volumen "
           "y para sostener el uso de procesamiento distribuido, pero ninguna "
           "comparación de co-postulación cruzará el quiebre. Es, además, el "
           "mismo corte a partir del cual existe el monto normalizado en soles "
           "(sección 10), lo que simplifica el diseño.", bold=False)
    figura(doc, "fig2_quiebre_postores.png",
           "Figura 3. Quiebre en el registro de postores. Arriba, postores "
           "promedio por proceso; abajo, porcentaje de procesos con un único "
           "postor. La banda gris marca el periodo 2004-2014, descartado para "
           "el análisis de competencia. El salto de 2015 es un artefacto del "
           "registro, no un cambio del mercado.")

    doc.add_heading("12.3 Montos: dónde están los procesos y dónde el dinero", level=2)
    p(doc, "Sobre 825 003 procesos con monto declarado positivo entre 2015 y "
           "2026 (se excluyó un 5,9 % con monto cero o negativo), la mediana "
           "es de S/ 143 650 y el percentil 99 llega a S/ 14,6 millones, con "
           "un máximo de S/ 3 034 millones. La distribución abarca nueve "
           "órdenes de magnitud, de modo que cualquier gráfico en escala "
           "lineal resulta ilegible y el promedio simple engaña.")
    p(doc, "El contraste entre las dos mitades de la Figura 4 es el hallazgo: "
           "la banda de los cien mil soles concentra la mayor cantidad de "
           "procesos (397 385), pero solo S/ 120 mil millones; la banda de los "
           "diez millones agrupa apenas 12 174 procesos y moviliza S/ 304 mil "
           "millones. Dicho de otro modo, el 1,7 % de los procesos mueve más "
           "de la mitad del dinero. Esto orienta las preguntas de interés: un "
           "patrón de co-postulación en la banda alta tiene consecuencias "
           "económicas de otro orden que el mismo patrón en compras menores.")
    figura(doc, "fig4_montos_log.png",
           "Figura 4. Distribución de los montos convocados por banda de "
           "magnitud, 2015-2026. Arriba, número de procesos; abajo, monto "
           "acumulado. Las dos distribuciones están desplazadas: donde hay más "
           "procesos no está el dinero.")
    p(doc, "La misma asimetría aparece por método de contratación (Figura 5). "
           "La adjudicación simplificada domina en número (362 497 procesos) "
           "pero la licitación pública, con solo 50 793 procesos, concentra "
           "S/ 383 mil millones: siete veces menos procesos y dos veces y "
           "media más dinero.")
    figura(doc, "fig6_metodos.png",
           "Figura 5. Monto convocado por método de contratación, 2015-2026, "
           "con el número de procesos de cada método como etiqueta.")

    doc.add_heading("12.4 MapReduce (RDD) frente a DataFrames y Spark SQL", level=2)
    p(doc, "El enunciado pide implementar al menos dos agregaciones en ambos "
           "estilos y medir el tiempo. Se eligieron dos agregaciones que "
           "responden a las preguntas de interés: el monto total convocado por "
           "entidad, y el número de procesos y monto medio por año y "
           "categoría. Ambas se implementaron con RDDs al estilo MapReduce "
           "(map + reduceByKey), con la API de DataFrames y con Spark SQL. "
           "Para que la comparación mida la agregación y no la lectura, los "
           "825 003 registros se cachearon en memoria antes de cronometrar, y "
           "se reporta el mejor de tres corridas.")
    tabla(doc, ["Agregación", "Estilo", "Tiempo", "Factor"], [
        ["A. Monto por entidad", "RDD (map + reduceByKey)", "21,94 s", "78x"],
        ["A. Monto por entidad", "DataFrame (groupBy + sum)", "0,28 s", "1,1x"],
        ["A. Monto por entidad", "Spark SQL (GROUP BY)", "0,26 s", "1x"],
        ["B. Procesos y monto medio por año y categoría",
         "RDD (map + reduceByKey + mapValues)", "22,56 s", "183x"],
        ["B. Procesos y monto medio por año y categoría",
         "DataFrame (groupBy + count/avg)", "0,12 s", "1x"],
    ], anchos=[6.2, 5.4, 2.2, 2.2], size=8.5)
    p(doc, "Los tres caminos producen el mismo resultado (se verificó que "
           "coinciden en el primer puesto del ranking: MTC - PROVÍAS "
           "Descentralizado con S/ 68 413 millones), pero el costo difiere en "
           "casi dos órdenes de magnitud. La explicación no es que los RDD "
           "sean 'lentos' en abstracto, sino que en PySpark cada fila debe "
           "serializarse de la JVM a un proceso Python y volver, mientras que "
           "la ruta de DataFrames se queda dentro de la JVM: Catalyst reordena "
           "el plan, aplica agregación parcial antes del shuffle y opera sobre "
           "memoria columnar con generación de código. El RDD paga, por cada "
           "una de los 825 003 filas, un peaje que el DataFrame no paga nunca.")
    p(doc, "La lectura práctica para el proyecto es que los RDD se usarán "
           "donde aportan expresividad -algoritmos que no se expresan bien en "
           "SQL, como el MinHash artesanal de la Parte II- y no como estilo "
           "por defecto. En claridad, además, la versión SQL es la más legible "
           "de las tres para un lector que no programa.")
    figura(doc, "fig5_rdd_vs_df.png",
           "Figura 6. Tiempo de las mismas agregaciones en los tres estilos "
           "(escala logarítmica, mejor de tres corridas, datos cacheados en "
           "memoria).")

    doc.add_heading("12.5 Particionado y plan de ejecución", level=2)
    p(doc, "El Parquet quedó particionado por año de publicación: 25 "
           "directorios anio=YYYY con un archivo por año. Cuando una consulta "
           "filtra por año, Spark aplica poda de particiones y no abre los "
           "archivos de los demás años; el mismo agregado por categoría baja "
           "de 0,29 s sobre el corpus completo a 0,08 s al restringirlo a "
           "2025. El filtro aparece en el plan físico como PartitionFilters "
           "sobre el FileScan, es decir que se empuja hasta el lector de "
           "archivos y no se evalúa después de leer.")
    p(doc, "Esta decisión de particionado es la que justifica el trabajo de "
           "la ingesta: particionar por el año del archivo de origen habría "
           "sido gratis, pero no habría podado nada, porque ese año no "
           "corresponde al de publicación del proceso. La ventana analítica "
           "2015-2026 que adopta el proyecto se traduce directamente en leer "
           "12 de los 25 directorios.")

    # ======================================= 13. PARTE II: SIMILITUD
    doc.add_heading("13. Resultados de la Parte II: similitud, MinHash y LSH",
                    level=1)
    p(doc, "La Parte II se ejecutó completa sobre Spark (script 10) siguiendo "
           "cuatro pasos encadenados: se construyó una verdad de terreno "
           "exacta, se implementó MinHash desde cero para medir cuánto se "
           "pierde al aproximar, se estudió el efecto de los parámetros de LSH "
           "sobre los falsos positivos y negativos, y recién entonces se "
           "aplicó al corpus completo.")

    doc.add_heading("13.1 Representación elegida y verdad de terreno", level=2)
    p(doc, "Cada proceso se representa como el conjunto de sus k-shingles de "
           "5 caracteres sobre el título y la descripción normalizados "
           "(mayúsculas, sin tildes ni puntuación, espacios colapsados). Se "
           "eligió shingling de caracteres y no de palabras porque las "
           "descripciones del SEACE mezclan códigos de procedimiento, siglas y "
           "texto libre, y los shingles de caracteres toleran mejor las "
           "variaciones menores de redacción. Sobre 2015-2026 el promedio es "
           "de 174 shingles por proceso.")
    p(doc, "Sobre una muestra de 2 000 procesos se calculó el Jaccard exacto "
           "de los 1 999 000 pares por fuerza bruta en Spark:")
    tabla(doc, ["Medición sobre la muestra de 2 000 procesos", "Resultado"], [
        ["Pares comparados", "1 999 000"],
        ["Pares con intersección no vacía", "1 951 282"],
        ["Pares con Jaccard >= 0,6", "20 (0,0010 % del total)"],
        ["Tiempo de la fuerza bruta en Spark", "13,1 s"],
        ["Extrapolación a los 876 211 procesos de 2015-2026",
         "508 horas (21 días)"],
    ], anchos=[9.5, 6.5], size=8.5)
    p(doc, "La extrapolación es la justificación cuantitativa de toda la "
           "Parte II: el coste crece con el cuadrado del número de documentos, "
           "de modo que multiplicar el corpus por 438 multiplica el tiempo por "
           "192 000. Veintiún días de cómputo para una sola consulta de "
           "similitud no es una opción; la similitud aproximada no es un atajo "
           "sino la única vía.", size=9, color=GRIS)

    doc.add_heading("13.2 MinHash: cuánto cuesta aproximar", level=2)
    p(doc, "Se implementaron T funciones hash universales "
           "h(x) = (a·x + b) mod p con p = 2^31 - 1, como en la sesión 03. "
           "Un detalle de implementación resultó decisivo: con el primo de "
           "Mersenne 2^61 - 1, que es el habitual en la literatura, el "
           "producto a·x desborda el entero de 64 bits de Spark y el hashing "
           "deja de ser uniforme; con 2^31 - 1 el producto cabe holgadamente. "
           "Las firmas se calculan con funciones de orden superior de Spark "
           "SQL, sin UDF de Python, para que todo el trabajo quede dentro de "
           "la JVM.")
    tabla(doc, ["T (funciones hash)", "Error absoluto medio", "RMSE",
                "Error máximo", "Cota teórica 0,5/√T"], [
        ["8", "0,0539", "0,0645", "0,4921", "0,1768"],
        ["16", "0,0425", "0,0523", "0,3072", "0,1250"],
        ["32", "0,0289", "0,0371", "0,2415", "0,0884"],
        ["64", "0,0209", "0,0268", "0,1640", "0,0625"],
        ["128", "0,0158", "0,0202", "0,1277", "0,0442"],
        ["256", "0,0110", "0,0141", "0,0859", "0,0312"],
    ], anchos=[3.4, 3.6, 2.6, 3.0, 3.4], size=8.5)
    p(doc, "El error observado sigue el comportamiento 1/√T que predice la "
           "teoría y se mantiene siempre por debajo de la cota. La lectura "
           "práctica es de rendimientos decrecientes: pasar de 8 a 64 "
           "funciones reduce el error a la mitad larga, pero pasar de 128 a "
           "256 apenas lo baja de 0,016 a 0,011 al precio de duplicar el "
           "cómputo y el almacenamiento de las firmas. Para este proyecto, "
           "T = 128 es el punto razonable.")
    figura(doc, "fig7_minhash_error.png",
           "Figura 7. Error de estimación del Jaccard frente al número de "
           "funciones hash, en escala logarítmica, medido sobre 200 000 pares "
           "con Jaccard exacto conocido.")

    doc.add_heading("13.3 LSH: el parámetro (b, r) decide qué se pierde", level=2)
    p(doc, "Con la firma de 256 posiciones se probaron seis particiones en "
           "b bandas de r filas, contrastando los pares candidatos contra los "
           "20 pares realmente similares de la muestra:")
    tabla(doc, ["b", "r", "Umbral efectivo", "Candidatos", "Falsos positivos",
                "Falsos negativos", "Precisión", "Recall"], [
        ["128", "2", "0,09", "572 963", "572 943", "0", "0,000", "1,00"],
        ["64", "4", "0,35", "8 809", "8 789", "0", "0,002", "1,00"],
        ["32", "8", "0,65", "37", "20", "3", "0,459", "0,85"],
        ["16", "16", "0,84", "2", "0", "18", "1,000", "0,10"],
        ["8", "32", "0,94", "1", "0", "19", "1,000", "0,05"],
        ["4", "64", "0,98", "1", "0", "19", "1,000", "0,05"],
    ], anchos=[1.3, 1.3, 2.6, 2.6, 2.8, 2.8, 1.8, 1.4], size=8.5)
    rico(doc, [
        ("La tabla es la curva S vista desde los datos. Con b = 128 y r = 2 el "
         "umbral efectivo cae a 0,09: LSH recupera los 20 pares pero arrastra "
         "572 943 falsos positivos, es decir el ", False),
        ("29 % de todos los pares posibles", True),
        (", con lo que no ahorra nada. En el extremo contrario, con r = 32 la "
         "precisión es perfecta pero se pierden 19 de los 20 pares. El punto "
         "de operación es ", False),
        ("b = 32, r = 8", True),
        (", cuyo umbral efectivo de 0,65 queda justo por encima del umbral de "
         "interés de 0,6: 37 candidatos, 85 % de recall y un filtrado exacto "
         "posterior que elimina los 20 falsos positivos restantes a coste "
         "despreciable.", False),
    ])
    p(doc, "Advertencia sobre estas cifras: la muestra contiene solo 20 pares "
           "realmente similares, de modo que cada par vale 5 puntos de recall "
           "y los valores son granulares. La tendencia es sólida y coincide "
           "con la teoría, pero no debe leerse como una estimación de "
           "precisión al 1 %.", size=9, color=GRIS)
    figura(doc, "fig8_curva_s.png",
           "Figura 8. Curva S teórica 1-(1-s^r)^b para tres configuraciones. "
           "La línea punteada marca el umbral de interés del proyecto.")
    figura(doc, "fig9_lsh_tradeoff.png",
           "Figura 9. Coste y calidad medidos: número de pares candidatos "
           "(escala logarítmica) y precisión/recall para cada (b, r).")

    doc.add_heading("13.4 Por qué no se usó MinHashLSH de MLlib a escala",
                    level=2)
    rico(doc, [
        ("Se intentó primero con ", False),
        ("MinHashLSH de Spark MLlib", True),
        (" y no funcionó, por una razón de diseño que vale la pena dejar "
         "documentada: MLlib construye ", False),
        ("una tabla hash por función", True),
        (", es decir b = numHashTables y ", False),
        ("r = 1 siempre", True),
        (". Su umbral efectivo es entonces 1/b, de modo que con 8 tablas "
         "cualquier par con Jaccard 0,125 ya entra como candidato. Es la "
         "primera fila de la tabla anterior llevada al corpus completo: la "
         "ejecución volcó más de 11 GB a disco y no terminó. La "
         "implementación propia por bandas, con r = 8, resolvió el mismo "
         "problema sin un solo byte de volcado.", False),
    ])
    p(doc, "Es un resultado útil para la discusión de la Parte VI: la "
           "biblioteca no siempre domina a la implementación propia. MLlib es "
           "más rápida generando firmas, pero no expresa el compromiso "
           "banda-fila que es justamente el parámetro que hay que ajustar.",
      size=9, color=GRIS)

    doc.add_heading("13.5 LSH sobre el corpus completo", level=2)
    tabla(doc, ["Medición", "Resultado"], [
        ["Procesos analizados (2015-2026)", "876 211"],
        ["Configuración", "b = 16, r = 8 (T = 128), umbral efectivo 0,71"],
        ["Cálculo de las firmas MinHash", "1 396 s (23 min)"],
        ["Pares candidatos generados", "4 146 092, en 43,1 s"],
        ["Pares confirmados con Jaccard >= 0,8", "584 848"],
        ["Pares que habría comparado la fuerza bruta", "383 872 420 155"],
        ["Proporción explorada", "0,00108 % del total"],
        ["Volcado a disco", "0 MB"],
    ], anchos=[7.0, 9.0], size=8.5)
    p(doc, "El coste se concentra donde no se esperaba. El LSH propiamente "
           "dicho -bandear, agrupar y verificar de forma exacta los 4,1 "
           "millones de candidatos- tomó 72 segundos. Generar las firmas tomó "
           "23 minutos, veinte veces más. La causa es que la expresión SQL "
           "reconstruye el arreglo de 128 coeficientes en cada fila; una "
           "implementación que los difunda una sola vez, o MLlib para este "
           "paso concreto, sería mucho más rápida. Se documenta porque es "
           "exactamente el tipo de compromiso que pide discutir la Parte VI: "
           "la elegancia de expresar el algoritmo en SQL puro se paga.")

    doc.add_heading("13.6 Interpretación: qué son los pares que aparecen",
                    level=2)
    rico(doc, [
        ("El hallazgo más contundente no es el número de pares sino su "
         "composición: ", False),
        ("el 98,1 % de los 584 848 pares casi idénticos corresponde a la misma "
         "entidad compradora", True),
        (". Y 66 014 pares tienen descripciones exactamente iguales.", False),
    ])
    p(doc, "La interpretación correcta no es el plagio entre entidades sino la "
           "reconvocatoria: un procedimiento que queda desierto o se declara "
           "nulo se vuelve a publicar con la misma descripción y un OCID "
           "nuevo. Los tres casos de mayor similitud lo muestran con claridad "
           "-el Gobierno Regional de Ucayali con una obra de transitabilidad, "
           "el Gobierno Regional de Cusco con una adquisición de carretillas y "
           "la Municipalidad Distrital de Majes con un alquiler de camioneta-, "
           "en los tres casos con dos OCID distintos del mismo año y la misma "
           "entidad.")
    p(doc, "Esto tiene una consecuencia metodológica inmediata para las partes "
           "siguientes: si no se colapsan las reconvocatorias, cualquier "
           "conteo de procesos por entidad sobreestima su actividad, y las "
           "reglas de asociación de la Parte V contarían varias veces la misma "
           "convocatoria. LSH, que se planteó como técnica de búsqueda, "
           "termina siendo también una herramienta de limpieza.")
    figura(doc, "fig10_distribuciones_jaccard.png",
           "Figura 10. Distribución de la similitud de los pares encontrados. "
           "A la izquierda, pares de procesos: el pico en 1,0 son las "
           "descripciones idénticas. A la derecha, pares de proveedores.")

    doc.add_heading("13.7 El caso concreto: proveedores que postulan a lo "
                    "mismo (pregunta P1)", level=2)
    p(doc, "Aplicando la misma maquinaria a la segunda representación -cada "
           "RUC como el conjunto de procesos a los que postuló- sobre los "
           "68 049 proveedores con 10 o más procesos en 2015-2026, LSH "
           "devolvió 2 281 pares con Jaccard >= 0,5 en 26 segundos, frente a "
           "los 2 315 299 176 pares que habría comparado la fuerza bruta.")
    rico(doc, [
        ("Entre ellos hay ", False), ("62 pares con Jaccard exactamente 1,000", True),
        (": proveedores cuyo conjunto de procesos coincide por completo. El "
         "caso más llamativo es un grupo de ", False),
        ("cuatro proveedores de la región Apurímac", True),
        (" -tres empresas y una persona natural- que aparecen en ", False),
        ("exactamente los mismos 37 procesos", True),
        (", los seis pares posibles entre ellos con Jaccard 1,000. No es que "
         "se parezcan: es que nunca se presentan por separado.", False),
    ])
    p(doc, "Qué significa y qué no. Que cuatro proveedores concurran siempre "
           "juntos a los mismos 37 procedimientos es un patrón que no se "
           "explica por azar, y es precisamente la señal que la pregunta P1 "
           "buscaba poder detectar a escala. Pero admite lecturas legítimas: "
           "pueden ser empresas vinculadas que se presentan en consorcio, o un "
           "mercado local tan reducido que los mismos cuatro actores son los "
           "únicos habilitados para ese rubro en esa provincia. El dato aquí "
           "es una pista que justifica mirar, no una conclusión. Los "
           "identificadores quedan en los artefactos reproducibles; en este "
           "informe se describen de forma agregada, conforme a la regla de la "
           "sección 14.")
    p(doc, "La Parte V retomará este mismo grupo desde el otro ángulo: si "
           "cuatro RUC forman un conjunto frecuente con soporte y lift altos "
           "en la canasta 'proceso -> postores', las dos técnicas estarán "
           "señalando el mismo fenómeno por caminos independientes, lo que "
           "refuerza el hallazgo.")

    # ===================================================== 14. ETICA
    doc.add_heading("14. Consideraciones éticas", level=1)
    p(doc, "El dataset nombra empresas y personas naturales identificadas por "
           "RUC. Las técnicas del proyecto producen indicios estadísticos de "
           "co-ocurrencia y similitud, no pruebas de irregularidad. Un conjunto "
           "frecuente de proveedores puede explicarse por especialización en un "
           "rubro, por concentración geográfica de la oferta o por el tamaño "
           "reducido del mercado local, y no únicamente por concertación.")
    p(doc, "En consecuencia, el equipo adopta tres reglas para el reporte final: "
           "presentar siempre la métrica junto a su interpretación alternativa; "
           "no calificar a ningún proveedor con términos que imputen conducta "
           "ilícita; y anonimizar o agregar los ejemplos individuales en la "
           "presentación pública, conservando los identificadores solo en el "
           "código reproducible. Los nombres que aparecen en la sección 7 de "
           "este informe se incluyen únicamente como evidencia de que la técnica "
           "produce resultados, y se trataran bajo esta regla en el entregable "
           "final.")
    p(doc, "El uso de los datos se ajusta a la licencia CC BY 4.0, que exige "
           "atribución e indicar si se hicieron cambios; el proyecto cita la "
           "fuente en el informe, en el reporte web y en el README del código.")

    # ===================================================== 14. FUENTES
    doc.add_heading("15. Fuentes de datos citadas", level=1)
    vinetas(doc, [
        "OECE - Organismo Especializado para las Contrataciones Públicas "
        "Eficientes (ex OSCE). Contrataciones Abiertas de la Compra Pública "
        "(OCDS). Portal oficial de descargas: "
        "https://contratacionesabiertas.oece.gob.pe/descargas (consultado el "
        "14/09/2026). Licencia CC BY 4.0.",
        "Open Contracting Partnership. OCP Data Registry, publicación 135: "
        "Peru - OECE. https://data.open-contracting.org/es/publication/135 "
        "(datos recolectados el 04/09/2026; descargas masivas por año en "
        "formato CSV utilizadas en este informe).",
        "OECE. Portal de Datos Abiertos del OECE (órdenes de compra y servicio, "
        "proveedores, entidades). https://www.gob.pe/14272-acceder-al-portal-"
        "de-datos-abiertos-del-oece (fuente complementaria, evaluada y no "
        "utilizada como principal).",
        "PCM. Plataforma Nacional de Datos Abiertos. "
        "https://www.datosabiertos.gob.pe/ (catálogo usado para la búsqueda de "
        "fuentes).",
        "INEI. Sistema de Microdatos. https://proyectos.inei.gob.pe/microdatos/ "
        "(fuente evaluada y descartada).",
        "MEF. Transparencia Económica / Consulta Amigable. "
        "https://www.mef.gob.pe/es/ (fuente evaluada y descartada).",
        "Open Contracting Data Standard 1.1 - documentación del estándar y sus "
        "extensiones. https://standard.open-contracting.org/",
    ])
    p(doc, "Atribución requerida por la licencia: los datos de contrataciones "
           "provienen del OECE (Perú) y se obtuvieron a través del OCP Data "
           "Registry; el equipo los transformó (descompresión, deduplicación por "
           "OCID, agregación) para los fines académicos de este proyecto.",
      italic=True, size=9, color=GRIS)

    # ===================================================== 15. ANEXO
    doc.add_heading("16. Anexo: reproducibilidad", level=1)
    p(doc, "Todas las cifras de este informe se regeneran ejecutando, en orden, "
           "los siguientes scripts del repositorio:")
    tabla(doc, ["Script", "Qué hace", "Salida"], [
        ["scripts/00_perfilado_dataset.py",
         "Perfila una partición anual contra los criterios C1-C4",
         "JSON con todas las métricas de la sección 6"],
        ["scripts/01_prueba_viabilidad.py",
         "Shingling+Jaccard, Jaccard entre proveedores, pares frecuentes y "
         "densidad del flujo",
         "Reporte por consola con los resultados de la sección 7"],
        ["scripts/02_figuras_informe.py",
         "Primera versión de las figuras con pandas, previa al entorno Spark. "
         "Sustituida por 09_figuras.py; se conserva como referencia",
         "(sin uso en la versión actual del informe)"],
        ["scripts/03_generar_informe_docx.py",
         "Ensambla este documento",
         "informe/Informe_Inicial_Seleccion_Dataset.docx"],
        ["scripts/entorno.py",
         "Localiza el JDK y winutils y crea la SparkSession del proyecto; se "
         "importa desde cualquier script que use Spark",
         "Entorno configurado sin depender de la terminal"],
        ["scripts/04_verificar_entorno.py",
         "Comprueba Java, Spark, escritura de Parquet, FP-Growth, MinHashLSH "
         "y el inventario de particiones",
         "Reporte por consola de la sección 11.1"],
        ["scripts/05_ingesta_parquet.py",
         "Convierte los 498 CSV a Parquet particionado por año de publicación "
         "y propaga ese año a las tablas hijas",
         "derivados/parquet/<tabla>/anio=YYYY/ + manifiesto JSON"],
        ["scripts/06_verificar_ingesta.py",
         "Contrasta el Parquet con los conteos del publicador y comprueba "
         "tipos, particionado y poda",
         "Reporte por consola de la sección 11.2"],
        ["scripts/07_representaciones.py",
         "Construye las representaciones reutilizables: shingles por proceso, "
         "conjunto de procesos por RUC y las dos canastas",
         "derivados/parquet/repr_* y canasta_*"],
        ["scripts/08_eda_parte1.py",
         "EDA de la Parte I en Spark y comparación RDD vs DataFrame/SQL",
         "derivados/artefactos/*.csv y *.json"],
        ["scripts/09_figuras.py",
         "Figuras del informe a partir de los artefactos (sustituye a "
         "02_figuras_informe.py, que trabajaba sobre los CSV crudos)",
         "informe/figuras/*.png"],
        ["scripts/10_parte2_similitud.py",
         "Parte II completa: Jaccard exacto, MinHash propio, LSH por bandas "
         "y aplicación al corpus. Admite ejecutar etapas sueltas (A..E)",
         "derivados/artefactos/p2_*"],
        ["scripts/11_figuras_parte2.py",
         "Figuras 7 a 10 desde los artefactos de la Parte II",
         "informe/figuras/fig7..fig10"],
    ], anchos=[5.0, 6.5, 4.5], size=8.5)
    p(doc, "Dependencias usadas en esta etapa: Python 3.14, PySpark 4.2, "
           "pandas 3.0, PyArrow 25.0, matplotlib 3.11, python-docx 1.2. Los "
           "scripts 00 y 01 corren en local con pandas y quedan como "
           "verificación independiente del pipeline en Spark, útil también "
           "para la comparación Spark vs. local que pide la Parte VI.",
      size=9, color=GRIS)

    doc.save(SALIDA)
    print(f"Generado: {SALIDA}")


if __name__ == "__main__":
    construir()
