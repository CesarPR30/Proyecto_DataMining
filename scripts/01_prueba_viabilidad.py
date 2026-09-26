# -*- coding: utf-8 -*-
"""
Prueba de viabilidad (no es el pipeline final): comprueba en pequeno, sobre un
anio del dataset OCDS-OECE, que las seis tecnicas del curso encuentran senal
real en estos datos antes de comprometer el proyecto.

1. Shingling + Jaccard sobre tender_description -> pares casi-duplicados.
2. Proveedor como conjunto de procesos -> Jaccard alto = co-postulacion sistematica.
3. Canasta "proceso -> postores" -> pares frecuentes (insumo de Apriori/FP-Growth).
4. Serie temporal diaria -> viabilidad del stream (DGIM/Bloom/CMS).

Todo se hace aqui con pandas y muestreo pequeno; el proyecto lo reimplementa
en Spark (MinHash/LSH, FP-Growth) sobre el corpus completo.

Uso: python scripts/01_prueba_viabilidad.py <ruta_carpeta_anio>
"""
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd


def norm(txt: str) -> str:
    txt = str(txt).upper()
    txt = re.sub(r"[^A-ZÁÉÍÓÚÑ0-9 ]", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def shingles(txt: str, k: int = 5) -> set:
    t = norm(txt)
    return {t[i:i + k] for i in range(len(t) - k + 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main(base: Path):
    main_df = pd.read_csv(base / "main.csv", low_memory=False)
    tend = pd.read_csv(base / "tender_tenderers.csv", low_memory=False)

    print("=" * 78)
    print(f"PRUEBA DE VIABILIDAD - {base.name}  ({len(main_df):,} procesos)")
    print("=" * 78)

    # ------------------------------------------------------------------ (1)
    print("\n[1] SHINGLING + JACCARD sobre tender_description (muestra de 3000)")
    m = main_df.dropna(subset=["tender_description"]).sample(
        min(3000, len(main_df)), random_state=42)
    sh = {r.ocid: shingles(r.tender_description) for r in m.itertuples()}
    sh = {k: v for k, v in sh.items() if len(v) >= 20}
    ocids = list(sh)
    pares = []
    for i in range(len(ocids)):
        for j in range(i + 1, len(ocids)):
            s = jaccard(sh[ocids[i]], sh[ocids[j]])
            if s >= 0.6:
                pares.append((s, ocids[i], ocids[j]))
    pares.sort(reverse=True)
    n_pares = len(ocids) * (len(ocids) - 1) // 2
    print(f"    pares comparados por fuerza bruta: {n_pares:,}")
    print(f"    pares con Jaccard >= 0.6: {len(pares):,} "
          f"({100*len(pares)/max(n_pares,1):.4f}% -> LSH es necesario)")
    d = main_df.set_index("ocid")
    for s, a, b in pares[:3]:
        print(f"    J={s:.3f}")
        print(f"      {a} [{d.loc[a,'buyer_name'][:45]}]")
        print(f"        {str(d.loc[a,'tender_description'])[:110]}")
        print(f"      {b} [{d.loc[b,'buyer_name'][:45]}]")
        print(f"        {str(d.loc[b,'tender_description'])[:110]}")

    # ------------------------------------------------------------------ (2)
    print("\n[2] PROVEEDOR COMO CONJUNTO DE PROCESOS (Jaccard entre proveedores)")
    g = tend.groupby("id")["main_ocid"].apply(set)
    g = g[g.apply(len) >= 10]
    print(f"    proveedores con >=10 procesos: {len(g):,}")
    sub = g.sample(min(1200, len(g)), random_state=7)
    idx, sets = list(sub.index), list(sub.values)
    sim = []
    for i in range(len(idx)):
        for j in range(i + 1, len(idx)):
            s = jaccard(sets[i], sets[j])
            if s >= 0.5:
                sim.append((s, idx[i], idx[j], len(sets[i]), len(sets[j])))
    sim.sort(reverse=True)
    nombres = tend.drop_duplicates("id").set_index("id")["name"]
    print(f"    pares de proveedores con Jaccard >= 0.5: {len(sim):,}")
    for s, a, b, na, nb in sim[:5]:
        print(f"    J={s:.3f}  {nombres.get(a,'?')[:38]:38} ({na:3}) <-> "
              f"{nombres.get(b,'?')[:38]:38} ({nb:3})")

    # ------------------------------------------------------------------ (3)
    print("\n[3] CANASTAS 'proceso -> conjunto de postores' (insumo FP-Growth)")
    canastas = tend.groupby("main_ocid")["id"].apply(lambda s: sorted(set(s)))
    canastas = canastas[canastas.apply(len).between(2, 40)]
    print(f"    canastas utilizables (2..40 postores): {len(canastas):,}")
    conteo_item = Counter()
    conteo_par = Counter()
    for c in canastas:
        conteo_item.update(c)
        conteo_par.update(combinations(c, 2))
    n = len(canastas)
    print(f"    items (RUC) distintos: {len(conteo_item):,}")
    print(f"    pares distintos co-ocurrentes: {len(conteo_par):,}")
    print("    top pares por soporte / confianza / lift:")
    for (a, b), c in conteo_par.most_common(8):
        sup = c / n
        conf = c / conteo_item[a]
        lift = conf / (conteo_item[b] / n)
        print(f"      sup={sup:.4f} conf={conf:.3f} lift={lift:7.1f}  "
              f"{nombres.get(a,'?')[:32]:32} -> {nombres.get(b,'?')[:32]}")

    # ------------------------------------------------------------------ (4)
    print("\n[4] VIABILIDAD DEL STREAM (orden temporal)")
    f = pd.to_datetime(main_df["tender_datePublished"], errors="coerce", utc=True)
    dia = f.dt.date.value_counts().sort_index()
    dia = dia[dia.index >= pd.Timestamp(f"{base.name}-01-01").date()]
    print(f"    dias con actividad en {base.name}: {len(dia):,}")
    print(f"    procesos/dia -> media {dia.mean():.1f}  mediana {dia.median():.0f}  "
          f"max {dia.max():,}")
    print(f"    granularidad del timestamp: {main_df['tender_datePublished'].iloc[0]}")

    # postor unico: pregunta de interes candidata
    nt = pd.to_numeric(main_df["tender_numberOfTenderers"], errors="coerce")
    print(f"\n[5] PROCESOS CON POSTOR UNICO (bandera de interes)")
    print(f"    con numberOfTenderers == 1: {(nt == 1).sum():,} "
          f"({100*(nt == 1).sum()/nt.notna().sum():.1f}% de los declarados)")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
