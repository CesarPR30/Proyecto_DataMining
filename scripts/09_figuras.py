# -*- coding: utf-8 -*-
"""
Figuras del informe, construidas SOLO desde los artefactos exportados por el
EDA en Spark (derivados/artefactos/*.csv).

Es la arquitectura "calcular una vez, explorar muchas" que pide el enunciado:
Spark hace el trabajo pesado y deja agregados ligeros; este script -y mas
adelante la pagina web- solo los lee. Ninguna figura vuelve a tocar los 46
millones de filas.

Sustituye a 02_figuras_informe.py, que construia las figuras con pandas sobre
los CSV crudos cuando aun no habia entorno Spark.

Uso:  python scripts/09_figuras.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entorno

ARTEFACTOS = entorno.DERIVADOS / "artefactos"
SALIDA = Path(__file__).resolve().parent.parent / "informe" / "figuras"

# paleta validada: una sola serie por grafico, azul; naranja solo como acento
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#dedcd6"
S1, S2 = "#2a78d6", "#eb6834"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.edgecolor": GRID, "font.size": 9, "figure.dpi": 200,
})

MILES = mtick.FuncFormatter(lambda v, _: f"{int(v):,}")


def limpiar(ax, grid="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis=grid, color=GRID, linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)


def guardar(fig, nombre):
    SALIDA.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(SALIDA / nombre, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {nombre}")


# ----------------------------------------------------------------- figura 1
def fig_temporal():
    d = pd.read_csv(ARTEFACTOS / "eda_temporal_mensual.csv")
    d["fecha"] = pd.to_datetime(d["periodo"] + "-01")
    d = d.sort_values("fecha")

    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    ax.plot(d["fecha"], d["procesos"], color=S1, linewidth=1.6)
    limpiar(ax)
    ax.set_ylabel("procesos publicados / mes")
    ax.yaxis.set_major_formatter(MILES)
    ax.set_ylim(0, d["procesos"].max() * 1.2)
    pico = d.loc[d["procesos"].idxmax()]
    ax.annotate(f"pico {int(pico['procesos']):,}\n{pico['periodo']}",
                (pico["fecha"], pico["procesos"]),
                textcoords="offset points", xytext=(8, -6),
                fontsize=8, color=INK2)
    ax.set_title("Procesos de contratación publicados por mes, 2003-2026",
                 loc="left", fontsize=10, color=INK, pad=10)
    guardar(fig, "fig1_volumen_temporal.png")


# ----------------------------------------------------------------- figura 2
def fig_quiebre_postores():
    """El hallazgo central del EDA: el registro de postores cambia en 2015."""
    d = pd.read_csv(ARTEFACTOS / "eda_postores_por_anio.csv")
    d = d[d["anio"] >= 2004]

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 4.4), sharex=True)

    a1.plot(d["anio"], d["postores_medio"], color=S1, linewidth=2,
            marker="o", markersize=3.5)
    limpiar(a1)
    a1.set_ylabel("postores por proceso\n(media)")
    a1.set_title("Quiebre en el registro de postores: el dato cambia en 2015, "
                 "no el mercado", loc="left", fontsize=10, color=INK, pad=10)

    a2.plot(d["anio"], d["pct_postor_unico"], color=S1, linewidth=2,
            marker="o", markersize=3.5)
    limpiar(a2)
    a2.set_ylabel("procesos con un\núnico postor (%)")
    a2.set_xlabel("año de publicación")

    for ax in (a1, a2):
        ax.axvspan(2003.5, 2014.5, color=GRID, alpha=0.45, zorder=0)
    a1.annotate("2004-2014: solo se registra\n1,5-2,3 postores por proceso",
                (2008, d[d["anio"] == 2008]["postores_medio"].iloc[0]),
                textcoords="offset points", xytext=(6, 26),
                fontsize=8, color=INK2)
    a1.text(0.60, 0.10, "2015-2026: de 4 a 15 postores registrados",
            transform=a1.transAxes, fontsize=8, color=S2)
    guardar(fig, "fig2_quiebre_postores.png")


# ----------------------------------------------------------------- figura 3
def fig_concentracion():
    d = pd.read_csv(ARTEFACTOS / "eda_entidades.csv")
    d = d[d["monto_millones"] > 0].sort_values("monto_millones", ascending=False)
    acum = d["monto_millones"].cumsum() / d["monto_millones"].sum() * 100
    x = (pd.Series(range(1, len(d) + 1)) / len(d) * 100).values

    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    ax.plot(x, acum.values, color=S1, linewidth=2)
    ax.plot([0, 100], [0, 100], color=GRID, linewidth=1.5, linestyle="--")
    limpiar(ax)
    ax.set_xlabel("% de entidades compradoras (ordenadas por monto)")
    ax.set_ylabel("% del monto convocado")
    for pcte in (1, 5, 10):
        i = max(int(len(d) * pcte / 100) - 1, 0)
        ax.plot([pcte], [acum.iloc[i]], "o", color=S2, markersize=6,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=5)
        ax.annotate(f"{pcte} % de entidades = {acum.iloc[i]:.0f} % del monto",
                    (pcte, acum.iloc[i]), textcoords="offset points",
                    xytext=(10, -4), fontsize=8, color=INK2)
    ax.set_title(f"Concentración del monto convocado, 2015-2026 "
                 f"({len(d):,} entidades)", loc="left", fontsize=10,
                 color=INK, pad=10)
    guardar(fig, "fig3_concentracion.png")


# ----------------------------------------------------------------- figura 4
def fig_montos():
    d = pd.read_csv(ARTEFACTOS / "eda_montos_histograma_log.csv")
    d = d[d["log10"] >= 3].sort_values("log10")
    etq = [f"10^{int(v)}" for v in d["log10"]]

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 4.2), sharex=True)
    a1.bar(etq, d["procesos"], color=S1, width=0.62)
    limpiar(a1)
    a1.set_ylabel("procesos")
    a1.yaxis.set_major_formatter(MILES)
    a1.set_title("Dónde están los procesos y dónde está el dinero (2015-2026)",
                 loc="left", fontsize=10, color=INK, pad=10)
    for i, v in enumerate(d["procesos"]):
        a1.text(i, v, f"{int(v):,}", ha="center", va="bottom", fontsize=7,
                color=INK2)

    a2.bar(etq, d["monto_mil_millones"], color=S1, width=0.62)
    limpiar(a2)
    a2.set_ylabel("monto convocado\n(S/ mil millones)")
    a2.set_xlabel("banda de magnitud del monto convocado (soles)")
    for i, v in enumerate(d["monto_mil_millones"]):
        a2.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=7,
                color=INK2)
    guardar(fig, "fig4_montos_log.png")


# ----------------------------------------------------------------- figura 5
def fig_rdd_vs_df():
    datos = json.loads((ARTEFACTOS / "eda_tiempos_rdd_vs_df.json")
                       .read_text(encoding="utf8"))
    d = pd.DataFrame(datos).iloc[::-1]
    colores = [S2 if "RDD" in o else S1 for o in d["operacion"]]

    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    barras = ax.barh(d["operacion"], d["segundos"], color=colores, height=0.6)
    ax.set_xscale("log")
    limpiar(ax, grid="x")
    ax.set_xlabel("segundos (escala logarítmica, mejor de 3 corridas)")
    for b, v in zip(barras, d["segundos"]):
        ax.text(v * 1.15, b.get_y() + b.get_height() / 2, f"{v:.2f} s",
                va="center", fontsize=8, color=INK2)
    ax.set_xlim(0.05, 60)
    ax.set_title("Misma agregación, dos estilos: RDD frente a DataFrame/SQL",
                 loc="left", fontsize=10, color=INK, pad=10)
    guardar(fig, "fig5_rdd_vs_df.png")


# ----------------------------------------------------------------- figura 6
def fig_metodos():
    d = pd.read_csv(ARTEFACTOS / "eda_metodo.csv")
    d = d.dropna(subset=["metodo"]).nlargest(8, "monto_mil_millones")
    d = d.sort_values("monto_mil_millones")

    fig, ax = plt.subplots(figsize=(7.2, 3.1))
    barras = ax.barh(d["metodo"].str.slice(0, 34), d["monto_mil_millones"],
                     color=S1, height=0.62)
    limpiar(ax, grid="x")
    ax.set_xlabel("monto convocado 2015-2026 (S/ mil millones)")
    for b, (_, r) in zip(barras, d.iterrows()):
        ax.text(r["monto_mil_millones"] + 4, b.get_y() + b.get_height() / 2,
                f"{r['monto_mil_millones']:,.0f}  ({int(r['procesos']):,} proc.)",
                va="center", fontsize=7.5, color=INK2)
    ax.set_xlim(0, d["monto_mil_millones"].max() * 1.38)
    ax.set_title("Pocos procesos concentran el monto: licitación pública "
                 "frente a adjudicación simplificada",
                 loc="left", fontsize=10, color=INK, pad=10)
    guardar(fig, "fig6_metodos.png")


def main():
    print(f"artefactos: {ARTEFACTOS}")
    fig_temporal()
    fig_quiebre_postores()
    fig_concentracion()
    fig_montos()
    fig_rdd_vs_df()
    fig_metodos()
    print(f"\nfiguras en: {SALIDA}")


if __name__ == "__main__":
    main()
