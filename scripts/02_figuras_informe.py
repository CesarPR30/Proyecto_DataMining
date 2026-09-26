# -*- coding: utf-8 -*-
"""
Genera las figuras del informe de seleccion del dataset (PNG, 200 dpi).

Salida: informe/figuras/*.png

Uso: python scripts/02_figuras_informe.py <raiz_datos_ocds> <dir_salida>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

# --- paleta validada (slot 1 = azul; superficie e ink del sistema de diseno) --
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#dedcd6"
S1 = "#2a78d6"   # categorical slot 1
S2 = "#eb6834"   # categorical slot 2

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "axes.edgecolor": GRID,
    "font.size": 9,
    "figure.dpi": 200,
})


def limpiar(ax):
    """Ejes y grilla recesivos: solo la linea base y una grilla horizontal tenue."""
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)


def cargar_main(raiz: Path) -> pd.DataFrame:
    """main.csv de todos los anios descargados, deduplicado por ocid."""
    cols = ["ocid", "buyer_name", "tender_datePublished", "tender_value_amount_PEN",
            "tender_numberOfTenderers", "tender_mainProcurementCategory"]
    partes = []
    for d in sorted(raiz.glob("[0-9][0-9][0-9][0-9]")):
        f = d / "main.csv"
        if f.exists():
            partes.append(pd.read_csv(f, usecols=cols, low_memory=False))
            print(f"  leido {f} ({len(partes[-1]):,} filas)")
    df = pd.concat(partes, ignore_index=True).drop_duplicates("ocid")
    df["fecha"] = pd.to_datetime(df["tender_datePublished"], errors="coerce", utc=True)
    print(f"  total deduplicado por ocid: {len(df):,}")
    return df


def fig_temporal(df, out: Path):
    """Fig 1: volumen mensual de procesos publicados (una sola serie)."""
    s = df.dropna(subset=["fecha"]).copy()
    s = s[(s["fecha"] >= "2019-01-01") & (s["fecha"] < "2026-09-01")]
    serie = s.set_index("fecha").resample("MS").size()

    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    ax.plot(serie.index, serie.values, color=S1, linewidth=2)
    limpiar(ax)
    ax.set_ylabel("procesos publicados / mes")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{int(v):,}"))
    # etiqueta directa selectiva: solo el maximo
    imax = serie.values.argmax()
    imin = serie.values[12:].argmin() + 12
    ax.set_ylim(0, serie.values.max() * 1.22)
    ax.annotate(f"pico {serie.values[imax]:,} ({serie.index[imax]:%b %Y})",
                (serie.index[imax], serie.values[imax]),
                textcoords="offset points", xytext=(9, -2),
                ha="left", fontsize=8, color=INK_2)
    ax.annotate("caida de enero:\nciclo presupuestal",
                (serie.index[imin], serie.values[imin]),
                textcoords="offset points", xytext=(26, 14),
                ha="left", fontsize=8, color=INK_2)
    ax.set_title("Procesos de contratacion publicados por mes (SEACE / OCDS)",
                 loc="left", fontsize=10, color=INK, pad=10)
    fig.tight_layout()
    fig.savefig(out / "fig1_volumen_temporal.png", bbox_inches="tight")
    plt.close(fig)
    return serie


def fig_canastas(raiz: Path, out: Path):
    """Fig 2: tamano de la canasta 'proceso -> postores' (una sola serie)."""
    t = pd.read_csv(raiz / "2025" / "tender_tenderers.csv",
                    usecols=["id", "main_ocid"], low_memory=False)
    tam = t.groupby("main_ocid")["id"].nunique()
    bins = [1, 2, 3, 5, 8, 13, 21, 34, 10 ** 6]
    etq = ["1", "2", "3-4", "5-7", "8-12", "13-20", "21-33", "34+"]
    cort = pd.cut(tam, bins=bins, labels=etq, right=False).value_counts()[etq]

    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    barras = ax.bar(etq, cort.values, color=S1, width=0.62)
    limpiar(ax)
    ax.set_xlabel("postores distintos por proceso (tamano de canasta)")
    ax.set_ylabel("procesos")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{int(v):,}"))
    for b, v in zip(barras, cort.values):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,}", ha="center",
                va="bottom", fontsize=7.5, color=INK_2)
    ax.set_title(f"Tamano de la canasta transaccional derivada, 2025 "
                 f"({len(tam):,} procesos)", loc="left", fontsize=10,
                 color=INK, pad=10)
    fig.tight_layout()
    fig.savefig(out / "fig2_tamano_canasta.png", bbox_inches="tight")
    plt.close(fig)
    return tam


def fig_concentracion(df, out: Path):
    """Fig 3: concentracion del monto convocado por entidad (curva acumulada)."""
    d = df.dropna(subset=["buyer_name"]).copy()
    d["monto"] = pd.to_numeric(d["tender_value_amount_PEN"], errors="coerce")
    d = d[d["monto"] > 0]
    por_ent = d.groupby("buyer_name")["monto"].sum().sort_values(ascending=False)
    acum = por_ent.cumsum() / por_ent.sum() * 100
    x = (pd.Series(range(1, len(acum) + 1)) / len(acum) * 100).values

    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    ax.plot(x, acum.values, color=S1, linewidth=2)
    ax.plot([0, 100], [0, 100], color=GRID, linewidth=1.5, linestyle="--")
    limpiar(ax)
    ax.set_xlabel("% de entidades compradoras (ordenadas por monto)")
    ax.set_ylabel("% del monto convocado")
    for p in (1, 5, 10):
        idx = max(int(len(acum) * p / 100) - 1, 0)
        ax.plot([p], [acum.values[idx]], "o", color=S2, markersize=6,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=5)
        ax.annotate(f"{p}% de entidades = {acum.values[idx]:.0f}% del monto",
                    (p, acum.values[idx]), textcoords="offset points",
                    xytext=(10, -4), fontsize=8, color=INK_2)
    ax.set_title(f"Concentracion del monto convocado por entidad "
                 f"({len(por_ent):,} entidades)", loc="left", fontsize=10,
                 color=INK, pad=10)
    fig.tight_layout()
    fig.savefig(out / "fig3_concentracion.png", bbox_inches="tight")
    plt.close(fig)
    return por_ent, acum


def main():
    raiz = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    print("Cargando main.csv...")
    df = cargar_main(raiz)

    serie = fig_temporal(df, out)
    tam = fig_canastas(raiz, out)
    por_ent, acum = fig_concentracion(df, out)

    print("\n--- CIFRAS PARA EL INFORME ---")
    print(f"procesos unicos (2019-2026 descargados): {len(df):,}")
    print(f"meses en la serie: {len(serie)}  media mensual: {serie.mean():,.0f}")
    print(f"pico mensual: {serie.max():,} en {serie.idxmax():%Y-%m}")
    print(f"canastas 2025: {len(tam):,}  media {tam.mean():.2f}  "
          f">=2 postores: {100*(tam>=2).mean():.1f}%")
    print(f"entidades: {len(por_ent):,}  top1%={acum.values[max(int(len(acum)*0.01)-1,0)]:.1f}%  "
          f"top5%={acum.values[max(int(len(acum)*0.05)-1,0)]:.1f}%  "
          f"top10%={acum.values[max(int(len(acum)*0.10)-1,0)]:.1f}%")
    print(f"monto total acumulado: S/ {por_ent.sum()/1e9:,.1f} mil millones")


if __name__ == "__main__":
    main()
