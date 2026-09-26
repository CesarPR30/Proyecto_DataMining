# -*- coding: utf-8 -*-
"""
Figuras de la Parte II a partir de los artefactos del script 10.

Uso:  python scripts/11_figuras_parte2.py
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

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#dedcd6"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"

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


def cargar(nombre):
    return json.loads((ARTEFACTOS / nombre).read_text(encoding="utf8"))


# ---------------------------------------------------------------- figura 7
def fig_error_minhash():
    d = pd.DataFrame(cargar("p2_error_minhash_vs_T.json"))
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    ax.plot(d["T"], d["mae"], color=S1, linewidth=2, marker="o", markersize=4,
            label="error absoluto medio observado")
    ax.plot(d["T"], d["cota_teorica"], color=INK2, linewidth=1.5,
            linestyle="--", label="cota teórica  0,5 / √T")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    limpiar(ax)
    ax.set_xlabel("T: número de funciones hash de la firma MinHash")
    ax.set_ylabel("error de estimación\ndel Jaccard")
    ax.set_xticks(d["T"])
    ax.get_xaxis().set_major_formatter(mtick.ScalarFormatter())
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    for _, r in d.iterrows():
        if r["T"] in (8, 256):
            ax.annotate(f"{r['mae']:.3f}", (r["T"], r["mae"]),
                        textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=8, color=INK2)
    ax.set_title("MinHash: más funciones hash, menos error, con rendimientos "
                 "decrecientes", loc="left", fontsize=10, color=INK, pad=10)
    guardar(fig, "fig7_minhash_error.png")


# ---------------------------------------------------------------- figura 8
def fig_curva_s():
    d = pd.DataFrame(cargar("p2_curva_s.json"))
    bandas = cargar("p2_lsh_bandas.json")
    combos = [("b64_r4", 64, 4, S3), ("b32_r8", 32, 8, S1), ("b16_r16", 16, 16, S2)]

    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for col, b, r, color in combos:
        ax.plot(d["s"], d[col], color=color, linewidth=2,
                label=f"b={b}, r={r}  (umbral ≈ {(1/b)**(1/r):.2f})")
    ax.axvline(0.6, color=INK2, linewidth=1.2, linestyle=":")
    ax.annotate("umbral de interés\nJaccard = 0,6", (0.6, 0.5),
                textcoords="offset points", xytext=(8, 0), fontsize=8,
                color=INK2)
    limpiar(ax)
    ax.set_xlabel("similitud real de Jaccard entre dos documentos")
    ax.set_ylabel("probabilidad de que\nel par sea candidato")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title("La curva S de LSH: (b, r) fija dónde se corta entre "
                 "encontrar y descartar", loc="left", fontsize=10, color=INK,
                 pad=10)
    guardar(fig, "fig8_curva_s.png")


# ---------------------------------------------------------------- figura 9
def fig_tradeoff():
    d = pd.DataFrame(cargar("p2_lsh_bandas.json"))
    d["etq"] = d.apply(lambda r: f"b={int(r['b'])}\nr={int(r['r'])}", axis=1)

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 4.4), sharex=True)

    a1.bar(d["etq"], d["candidatos"], color=S1, width=0.6)
    a1.set_yscale("log")
    limpiar(a1)
    a1.set_ylabel("pares candidatos\n(escala log)")
    for i, v in enumerate(d["candidatos"]):
        a1.text(i, v * 1.3, f"{int(v):,}", ha="center", fontsize=7.5, color=INK2)
    a1.set_ylim(0.5, d["candidatos"].max() * 12)
    a1.set_title("Coste y calidad de LSH según el número de bandas "
                 "(20 pares realmente similares)",
                 loc="left", fontsize=10, color=INK, pad=10)

    x = range(len(d))
    ancho = 0.38
    a2.bar([i - ancho/2 for i in x], d["precision"], width=ancho, color=S1,
           label="precisión")
    a2.bar([i + ancho/2 for i in x], d["recall"], width=ancho, color=S2,
           label="recall")
    limpiar(a2)
    a2.set_xticks(list(x))
    a2.set_xticklabels(d["etq"])
    a2.set_ylabel("precisión y recall")
    a2.set_ylim(0, 1.15)
    fig.legend(*a2.get_legend_handles_labels(), frameon=False,
               fontsize=8, ncol=2, loc="lower center",
               bbox_to_anchor=(0.5, -0.04))
    for i, (p, r) in enumerate(zip(d["precision"], d["recall"])):
        a2.text(i - ancho/2, p + 0.03, f"{p:.2f}", ha="center", fontsize=7,
                color=INK2)
        a2.text(i + ancho/2, r + 0.03, f"{r:.2f}", ha="center", fontsize=7,
                color=INK2)
    guardar(fig, "fig9_lsh_tradeoff.png")


# --------------------------------------------------------------- figura 10
def fig_distribuciones():
    """Que encontro LSH a escala: procesos casi identicos y proveedores
    que postulan exactamente a lo mismo."""
    pr = pd.read_csv(ARTEFACTOS / "p2_distribucion_jaccard.csv")
    pv = pd.read_csv(ARTEFACTOS / "p2_distribucion_jaccard_proveedores.csv")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.4, 3.0))

    a1.bar(pr["banda"], pr["count"], width=0.008, color=S1)
    limpiar(a1)
    a1.set_xlabel("Jaccard entre descripciones")
    a1.set_ylabel("pares de procesos")
    a1.yaxis.set_major_formatter(MILES)
    idx = pr["banda"].sub(1.0).abs().idxmin()
    a1.set_ylim(0, pr["count"].max() * 1.15)
    a1.text(0.50, 0.76, f"{int(pr.loc[idx, 'count']):,} pares\nidénticos",
            transform=a1.transAxes, fontsize=8, color=S2)
    a1.set_title(f"Procesos: {int(pr['count'].sum()):,} pares con J ≥ 0,8",
                 loc="left", fontsize=9.5, color=INK, pad=8)

    a2.bar(pv["banda"], pv["count"], width=0.008, color=S1)
    limpiar(a2)
    a2.set_xlabel("Jaccard entre conjuntos de procesos")
    a2.set_ylabel("pares de proveedores")
    idx = pv["banda"].sub(1.0).abs().idxmin()
    a2.annotate(f"{int(pv.loc[idx, 'count']):,} pares con\nel MISMO conjunto",
                (1.0, pv.loc[idx, "count"]), textcoords="offset points",
                xytext=(-12, 2), ha="right", fontsize=8, color=S2)
    a2.set_title(f"Proveedores: {int(pv['count'].sum()):,} pares con J ≥ 0,5",
                 loc="left", fontsize=9.5, color=INK, pad=8)
    guardar(fig, "fig10_distribuciones_jaccard.png")


def main():
    fig_error_minhash()
    fig_curva_s()
    fig_tradeoff()
    fig_distribuciones()
    print(f"\nfiguras en: {SALIDA}")


if __name__ == "__main__":
    main()
