/* Logica del reporte: cada funcion pinta un hallazgo a partir de window.DATOS
   (artefactos exportados por Spark) y, cuando corresponde, recalcula en vivo
   las formulas analiticas de los compromisos (curva S, Bloom, etc.). */
(function () {
  const D = window.DATOS || {};
  const { fmt } = G;
  const $ = (id) => document.getElementById(id);
  const txt = (id, v) => { const e = $(id); if (e) e.textContent = v; };
  const hay = (k) => Array.isArray(D[k]) ? D[k].length > 0 : !!D[k];

  function enlazar(ids, fn) {
    ids.forEach((id) => { const e = $(id); if (e) e.addEventListener('input', fn); });
    fn();
  }
  function lecturas(id, pares) {
    const cont = $(id); if (!cont) return;
    cont.replaceChildren();
    pares.forEach(([k, v]) => {
      const d = document.createElement('div');
      const a = document.createElement('div'); a.className = 'k'; a.textContent = k;
      const b = document.createElement('div'); b.className = 'v'; b.textContent = v;
      d.append(a, b); cont.append(d);
    });
  }

  /* ================================================================ PARTE I */
  function eda() {
    if (hay('eda_temporal_mensual')) {
      const m = D.eda_temporal_mensual.filter((r) => r.anio >= 2003);
      const dibujar = () => {
        const met = $('ctl-temporal').value;
        const desde = met === 'monto_pen' ? 2015 : 2003;
        const filas = m.filter((r) => r.anio >= desde);
        G.lineas('ch-temporal', {
          etiquetas: filas.map((r) => r.periodo),
          series: [{ nombre: met === 'monto_pen' ? 'Monto convocado (S/)' : 'Procesos publicados',
                     datos: filas.map((r) => met === 'monto_pen' ? r.monto_pen : r.procesos), relleno: true }],
          yTitulo: met === 'monto_pen' ? 'Soles por mes' : 'Procesos por mes',
          y: { ticks: { callback: (v) => fmt.compacto(v) } },
          tooltip: { label: (c) => ' ' + fmt.compacto(c.parsed.y) },
        });
      };
      enlazar(['ctl-temporal'], dibujar);
    }
    if (hay('eda_postores_por_anio')) {
      const p = D.eda_postores_por_anio.filter((r) => r.anio >= 2004);
      G.barras('ch-postores', {
        etiquetas: p.map((r) => r.anio),
        series: [{ nombre: 'Postores promedio', datos: p.map((r) => r.postores_medio),
                   colores: p.map((r) => (r.anio < 2015 ? '--muted' : '--s1')) }],
        yTitulo: 'Postores por proceso',
      });
      G.lineas('ch-unico', {
        etiquetas: p.map((r) => r.anio),
        series: [{ nombre: '% con un único postor', datos: p.map((r) => r.pct_postor_unico), puntos: true, slot: 1 }],
        yTitulo: '% de procesos con un solo postor',
        tooltip: { label: (c) => ' ' + fmt.dec(1)(c.parsed.y) + ' %' },
      });
    }
    if (hay('eda_montos_histograma_log')) {
      const h = D.eda_montos_histograma_log.filter((r) => r.log10 >= 2 && r.log10 <= 9);
      const bandas = { 2: '100 – 1 mil', 3: '1 mil – 10 mil', 4: '10 mil – 100 mil', 5: '100 mil – 1 M',
        6: '1 M – 10 M', 7: '10 M – 100 M', 8: '100 M – 1 000 M', 9: '≥ 1 000 M' };
      const et = h.map((r) => bandas[r.log10]);
      G.barras('ch-montos-n', { etiquetas: et, xTitulo: 'Monto convocado (S/)', series: [{ nombre: 'Procesos', datos: h.map((r) => r.procesos) }],
        yTitulo: 'Procesos', y: { ticks: { callback: (v) => fmt.compacto(v) } } });
      G.barras('ch-montos-s', { etiquetas: et, xTitulo: 'Monto convocado (S/)', series: [{ nombre: 'Monto (miles de millones S/)', datos: h.map((r) => r.monto_mil_millones), slot: 1 }],
        yTitulo: 'Miles de millones de S/' });
    }
    if (hay('eda_metodo')) {
      const top = [...D.eda_metodo].filter((r) => r.monto_mil_millones != null)
        .sort((a, b) => b.monto_mil_millones - a.monto_mil_millones).slice(0, 8);
      G.barras('ch-metodo', {
        horizontal: true, etiquetas: top.map((r) => String(r.metodo).slice(0, 38)),
        series: [{ nombre: 'Monto convocado (miles de millones S/)', datos: top.map((r) => r.monto_mil_millones) }],
        yTitulo: 'Miles de millones de S/',
        tooltip: { afterLabel: (c) => '  ' + fmt.ent(top[c.dataIndex].procesos) + ' procesos' },
      });
    }
    if (hay('eda_entidades')) {
      const e = D.eda_entidades.filter((r) => r.monto_millones > 0)
        .sort((a, b) => b.monto_millones - a.monto_millones);
      const total = e.reduce((s, r) => s + r.monto_millones, 0);
      let acum = 0;
      const pts = [{ x: 0, y: 0 }];
      e.forEach((r, i) => { acum += r.monto_millones; pts.push({ x: (i + 1) / e.length * 100, y: acum / total * 100 }); });
      const sub = pts.filter((_, i) => i % Math.max(1, Math.floor(pts.length / 400)) === 0 || i === pts.length - 1);
      G.puntos('ch-lorenz', {
        series: [
          { nombre: 'Monto acumulado', datos: sub, linea: true, radio: 0 },
          { nombre: 'Reparto igualitario', datos: [{ x: 0, y: 0 }, { x: 100, y: 100 }], linea: true, radio: 0, color: '--axis', punteada: true },
        ],
        xTitulo: '% de entidades (de mayor a menor monto)', yTitulo: '% del monto convocado',
        x: { max: 100 }, y: { max: 100 },
        tooltip: { label: (c) => ` ${fmt.dec(1)(c.parsed.x)} % de entidades → ${fmt.dec(1)(c.parsed.y)} % del monto` },
      });
      // mismo criterio que el EDA en Spark: los primeros floor(n·p) entes
      const cuota = (p) => pts[Math.max(1, Math.floor(e.length * p / 100))].y;
      lecturas('lec-lorenz', [['1 % de entidades', fmt.dec(1)(cuota(1)) + ' %'],
        ['5 % de entidades', fmt.dec(1)(cuota(5)) + ' %'], ['10 % de entidades', fmt.dec(1)(cuota(10)) + ' %'],
        ['Entidades', fmt.ent(e.length)]]);
      G.tabla('tb-entidades', e.slice(0, 10), [
        { clave: 'buyer_name', titulo: 'Entidad' },
        { clave: 'procesos', titulo: 'Procesos', num: true, fmt: fmt.ent },
        { clave: 'monto_millones', titulo: 'Monto (millones S/)', num: true, fmt: fmt.ent },
      ]);
    }
    if (hay('eda_tiempos_rdd_vs_df')) {
      const t = D.eda_tiempos_rdd_vs_df;
      G.barras('ch-rdd', {
        horizontal: true, etiquetas: t.map((r) => r.operacion),
        series: [{ nombre: 'Segundos (mejor de 3)', datos: t.map((r) => r.segundos),
                   colores: t.map((r) => (r.operacion.includes('RDD') ? '--s2' : '--s1')) }],
        yTitulo: 'Segundos (escala logarítmica)', yTipo: 'logarithmic', y: { min: 0.1 },
        tooltip: { label: (c) => ' ' + fmt.dec(3)(c.parsed.x) + ' s' },
      });
    }
  }

  /* =============================================================== PARTE II */
  function similitud() {
    // ---- MinHash: error vs T (en vivo: cota teorica; puntos: medido en Spark)
    if (hay('p2_error_minhash_vs_T')) {
      const med = D.p2_error_minhash_vs_T;
      const dibujar = () => {
        const T = 2 ** Number($('ctl-T').value);
        txt('out-T', T);
        const teor = [];
        for (let t = 4; t <= 512; t *= Math.SQRT2) teor.push({ x: t, y: 0.5 / Math.sqrt(t) });
        G.puntos('ch-minhash', {
          series: [
            { nombre: 'Cota teórica 0,5/√T', datos: teor, linea: true, radio: 0, color: '--axis', punteada: true },
            { nombre: 'RMSE medido', datos: med.map((r) => ({ x: r.T, y: r.rmse })), linea: true, slot: 0 },
            { nombre: 'Error absoluto medio medido', datos: med.map((r) => ({ x: r.T, y: r.mae })), linea: true, slot: 1 },
            { nombre: 'T elegido', datos: [{ x: T, y: 0.5 / Math.sqrt(T) }], radio: 7, color: '--ink' },
          ],
          xTitulo: 'Funciones hash T (escala log)', xTipo: 'logarithmic', yTitulo: 'Error de estimación del Jaccard',
          yTipo: 'logarithmic',
          x: { min: 4, max: 512, afterBuildTicks: (ax) => { ax.ticks = [4, 8, 16, 32, 64, 128, 256, 512].map((v) => ({ value: v })); }, ticks: { callback: (v) => v } },
          tooltip: { label: (c) => ` ${c.dataset.label}: ${fmt.dec(4)(c.parsed.y)} (T=${Math.round(c.parsed.x)})` },
        });
        const cerca = med.reduce((a, b) => (Math.abs(Math.log(b.T / T)) < Math.abs(Math.log(a.T / T)) ? b : a));
        const n = (D.p2_lsh_escala && D.p2_lsh_escala.procesos) || 876000;
        lecturas('lec-minhash', [
          ['Desv. típica máxima', fmt.dec(3)(0.5 / Math.sqrt(T))],
          [`RMSE medido (T=${cerca.T})`, fmt.dec(4)(cerca.rmse)],
          ['Firmas del corpus', fmt.compacto(T * 4 * n / 1024 ** 2) + ' MB'],
          ['Costo relativo vs T=128', fmt.dec(2)(T / 128) + '×'],
        ]);
      };
      enlazar(['ctl-T'], dibujar);
    }
    // ---- LSH: (b, r) -> curva S en vivo + tabla medida
    if (hay('p2_lsh_bandas')) {
      const med = D.p2_lsh_bandas;
      const dibujar = () => {
        const b = Number($('ctl-b').value), r = Number($('ctl-r').value);
        txt('out-b', b); txt('out-r', r); txt('out-br', b * r);
        const S = (s, bb, rr) => 1 - (1 - s ** rr) ** bb;
        const xs = Array.from({ length: 101 }, (_, i) => i / 100);
        G.puntos('ch-curva-s', {
          series: [
            { nombre: `b=${b}, r=${r}`, datos: xs.map((s) => ({ x: s, y: S(s, b, r) })), linea: true, radio: 0, slot: 0 },
            { nombre: 'Referencia b=32, r=8', datos: xs.map((s) => ({ x: s, y: S(s, 32, 8) })), linea: true, radio: 0, color: '--axis', punteada: true },
            { nombre: 'Umbral de interés 0,6', datos: [{ x: 0.6, y: 0 }, { x: 0.6, y: 1 }], linea: true, radio: 0, color: '--s2', punteada: true },
          ],
          xTitulo: 'Jaccard real del par (s)', yTitulo: 'P(el par es candidato)', x: { min: 0, max: 1 }, y: { max: 1 },
          tooltip: { label: (c) => ` ${c.dataset.label}: P=${fmt.dec(3)(c.parsed.y)} en s=${fmt.dec(2)(c.parsed.x)}` },
        });
        const umbral = (1 / b) ** (1 / r);
        lecturas('lec-lsh', [
          ['Umbral efectivo (1/b)^(1/r)', fmt.dec(2)(umbral)],
          ['P(candidato | s=0,8)', fmt.pct(1)(S(0.8, b, r))],
          ['P(candidato | s=0,6)', fmt.pct(1)(S(0.6, b, r))],
          ['P(candidato | s=0,3)', fmt.pct(2)(S(0.3, b, r))],
        ]);
        G.tabla('tb-lsh', med, [
          { clave: 'b', titulo: 'b', num: true }, { clave: 'r', titulo: 'r', num: true },
          { clave: 'umbral_efectivo', titulo: 'Umbral', num: true, fmt: fmt.dec(2) },
          { clave: 'candidatos', titulo: 'Candidatos', num: true, fmt: fmt.ent },
          { clave: 'falsos_positivos', titulo: 'Falsos +', num: true, fmt: fmt.ent },
          { clave: 'falsos_negativos', titulo: 'Falsos −', num: true, fmt: fmt.ent },
          { clave: 'precision', titulo: 'Precisión', num: true, fmt: fmt.pct(1) },
          { clave: 'recall', titulo: 'Recall', num: true, fmt: fmt.pct(0) },
        ], { resaltar: (f) => f.b === b && f.r === r });
      };
      enlazar(['ctl-b', 'ctl-r'], dibujar);
    }
    if (hay('p2_distribucion_jaccard')) {
      const d = D.p2_distribucion_jaccard;
      const k = Object.keys(d[0]);
      const xk = k.find((c) => /bin|jac|tramo|cubeta/i.test(c)) || k[0];
      const yk = k.find((c) => /pares|count|n$/i.test(c) && c !== xk) || k[1];
      G.barras('ch-dist-jac', { etiquetas: d.map((r) => fmt.dec(2)(r[xk])), series: [{ nombre: 'Pares', datos: d.map((r) => r[yk]) }],
        xTitulo: 'Jaccard del par de procesos', yTitulo: 'Pares', yTipo: 'logarithmic' });
    }
  }

  /* ============================================================== PARTE III */
  function ann() {
    if (!hay('p3_ann_curvas')) return;
    const c = D.p3_ann_curvas;
    const exacta = c.find((r) => r.familia === 'exacta');
    const configs = [...new Set(c.filter((r) => r.familia !== 'exacta').map((r) => r.familia + '|' + r.config))];
    const sel = $('ctl-ann-config');
    configs.forEach((k) => { const o = document.createElement('option'); o.value = k; o.textContent = k.replace('|', ' · '); sel.append(o); });
    sel.value = configs.find((k) => k === 'IVF|nlist=4096') || configs[0];
    const dibujar = (desdeSelect) => {
      const filas = c.filter((r) => r.familia + '|' + r.config === sel.value);
      const sl = $('ctl-ann-param');
      sl.max = filas.length - 1;
      if (desdeSelect === true) sl.value = Math.floor(filas.length / 2);
      const f = filas[Math.min(Number(sl.value), filas.length - 1)];
      txt('out-ann-param', `${f.param} = ${f.valor}`);
      // Enfasis: el indice elegido en color, el resto en gris (no 7 colores)
      const series = configs.filter((k) => k !== sel.value).map((k) => ({
        nombre: k.replace('|', ' · '),
        datos: c.filter((r) => r.familia + '|' + r.config === k).map((r) => ({ x: r.ms_consulta, y: r.recall, v: r.param + '=' + r.valor })),
        linea: true, radio: 2, color: '--axis', orden: 5,
      }));
      series.push({ nombre: sel.value.replace('|', ' · '), datos: filas.map((r) => ({ x: r.ms_consulta, y: r.recall, v: r.param + '=' + r.valor })),
        linea: true, radio: 4, slot: 0, orden: 1 });
      series.push({ nombre: 'Exacta (fuerza bruta)', datos: [{ x: exacta.ms_consulta, y: 1, v: 'Flat' }], radio: 7, color: '--ink', estilo: 'rectRot', orden: 0 });
      series.push({ nombre: 'Selección', datos: [{ x: f.ms_consulta, y: f.recall, v: f.param + '=' + f.valor }], radio: 9, color: '--s2', estilo: 'circle', orden: -1 });
      G.puntos('ch-ann', {
        series, xTitulo: 'ms por consulta, 1 hilo (escala log)', xTipo: 'logarithmic', yTitulo: 'Recall@10 frente a la búsqueda exacta',
        y: { min: Math.max(0, Math.min(...c.map((r) => r.recall)) - 0.05), max: 1.005 },
        tooltip: { label: (ctx) => ` ${ctx.dataset.label} (${ctx.raw.v}): recall ${fmt.dec(3)(ctx.parsed.y)}, ${fmt.dec(3)(ctx.parsed.x)} ms` },
      });
      G.leyenda('ley-ann', [{ nombre: sel.value.replace('|', ' · ') + ' (elegido)', slot: 0 },
        { nombre: 'Parámetro seleccionado', slot: 1 }, { nombre: 'Otros índices', color: '--axis' },
        { nombre: 'Exacta (fuerza bruta)', color: '--ink' }]);
      lecturas('lec-ann', [
        ['Recall@10', fmt.dec(3)(f.recall)],
        ['ms por consulta', fmt.dec(3)(f.ms_consulta)],
        ['Aceleración vs exacta', fmt.dec(0)(exacta.ms_consulta / f.ms_consulta) + '×'],
        ['Memoria del índice', fmt.ent(f.mb) + ' MB'],
        ['Construcción', fmt.dec(0)(f.construccion_s) + ' s'],
      ]);
    };
    sel.addEventListener('input', () => dibujar(true));
    $('ctl-ann-param').addEventListener('input', () => dibujar(false));
    dibujar(true);
    if (hay('p3_curva_dimensiones')) {
      const cd = D.p3_curva_dimensiones;
      G.puntos('ch-dims', {
        series: [
          { nombre: 'Recall@10 frente al TF-IDF completo', datos: cd.map((r) => ({ x: r.dim, y: r.recall_top10 })), linea: true, slot: 0 },
          { nombre: 'Casi-duplicados (coseno ≥ 0,8) recuperados', datos: cd.map((r) => ({ x: r.dim, y: r.recall_casi_duplicados })), linea: true, slot: 1 },
          { nombre: 'Varianza explicada por la SVD', datos: cd.map((r) => ({ x: r.dim, y: r.varianza_explicada })), linea: true, color: '--axis', punteada: true },
        ],
        xTitulo: 'Dimensiones LSA (escala log₂)', xTipo: 'logarithmic', yTitulo: 'Proporción', y: { min: 0, max: 1 },
        x: { min: 12, max: 340, afterBuildTicks: (ax) => { ax.ticks = [16, 32, 64, 128, 256].map((v) => ({ value: v })); }, ticks: { callback: (v) => v } },
        tooltip: { label: (c) => ` ${c.dataset.label}: ${fmt.pct(1)(c.parsed.y)} con ${c.parsed.x} dims` },
      });
      G.leyenda('ley-dims', [{ nombre: 'Recall@10 frente al TF-IDF completo', slot: 0 },
        { nombre: 'Casi-duplicados (coseno ≥ 0,8) recuperados', slot: 1 },
        { nombre: 'Varianza explicada por la SVD', color: '--axis', punteada: true }]);
    }
    if (hay('p3_p2_vecinos_postores')) {
      const orden = ['>= 0,95', '0,80 - 0,95', '0,60 - 0,80', '< 0,60', 'azar (misma categoria)'];
      const t = [...D.p3_p2_vecinos_postores].sort((a, b) => orden.indexOf(a.tramo) - orden.indexOf(b.tramo))
        .map((r) => ({ ...r, tramo: r.tramo.replace('>=', '≥').replace('< ', '< ').replace('azar (misma categoria)', 'Azar (misma categoría)') }));
      G.tabla('tb-p2-vecinos', t, [
        { clave: 'tramo', titulo: 'Similitud de texto (coseno)' },
        { clave: 'pares', titulo: 'Pares', num: true, fmt: fmt.ent },
        { clave: 'pct_misma_entidad', titulo: 'Misma entidad', num: true, fmt: fmt.pct(1) },
        { clave: 'jac_postores_medio', titulo: 'Jaccard de postores', num: true, fmt: fmt.dec(3) },
        { clave: 'pct_mismo_ganador', titulo: 'Mismo ganador', num: true, fmt: fmt.pct(2) },
      ]);
    }
    if (hay('p3_p2_contraste_entidad')) {
      G.tabla('tb-p2-contraste', D.p3_p2_contraste_entidad.map((r) => ({ ...r, grupo: r.misma_entidad ? 'Misma entidad' : 'Distinta entidad' })), [
        { clave: 'grupo', titulo: 'Vecinos con coseno ≥ 0,80' },
        { clave: 'pares', titulo: 'Pares', num: true, fmt: fmt.ent },
        { clave: 'jac_postores_medio', titulo: 'Jaccard de postores', num: true, fmt: fmt.dec(3) },
        { clave: 'pct_mismo_ganador', titulo: 'Mismo ganador', num: true, fmt: fmt.pct(1) },
      ]);
    }
    const ej = D.p3_resumen && D.p3_resumen.ejemplos;
    if (ej && $('ann-ejemplos')) {
      const cont = $('ann-ejemplos'); cont.replaceChildren();
      ej.slice(0, 3).forEach((e) => {
        const det = document.createElement('details');
        const s = document.createElement('summary'); s.textContent = e.consulta.slice(0, 110) + '…';
        det.append(s);
        const ul = document.createElement('ul'); ul.className = 'lista';
        e.vecinos.forEach((v) => { const li = document.createElement('li'); li.textContent = `coseno ${fmt.dec(3)(v.coseno)} · ${v.entidad} — ${v.texto.slice(0, 120)}`; ul.append(li); });
        det.append(ul); cont.append(det);
      });
    }
  }

  /* =============================================================== PARTE IV */
  function flujos() {
    if (hay('p4_bloom')) {
      const b = D.p4_bloom;
      const res = (D.p4_resumen && D.p4_resumen.bloom) || [];
      const dibujar = () => {
        const tarea = $('ctl-bloom-tarea').value;
        const bpc = Number($('ctl-bloom-m').value), k = Number($('ctl-bloom-k').value);
        txt('out-bloom-m', bpc); txt('out-bloom-k', k);
        const filas = b.filter((r) => r.tarea === tarea);
        const n = res[tarea === 'ruc' ? 0 : 1] ? res[tarea === 'ruc' ? 0 : 1].distintos : 700000;
        const teor = (bb, kk) => (1 - Math.exp(-kk / bb)) ** kk;
        const kopt = Math.max(1, Math.round(bpc * Math.LN2));
        const medida = filas.find((r) => r.bits_por_clave === bpc && r.k === k);
        const xs = Array.from({ length: 40 }, (_, i) => 0.5 + i * 0.5);
        G.puntos('ch-bloom', {
          series: [
            { nombre: `Teórica, k=${k}`, datos: xs.map((x) => ({ x, y: Math.max(teor(x, k), 1e-7) })), linea: true, radio: 0, slot: 0 },
            { nombre: 'Teórica con k óptimo', datos: xs.map((x) => ({ x, y: Math.max(teor(x, Math.max(1, Math.round(x * Math.LN2))), 1e-7) })), linea: true, radio: 0, color: '--axis', punteada: true },
            { nombre: `Medida en el flujo, k=${k}`, datos: filas.filter((r) => r.k === k).map((r) => ({ x: r.bits_por_clave, y: Math.max(r.tasa_fp, 1e-7) })), radio: 5, slot: 1 },
            { nombre: 'Selección', datos: [{ x: bpc, y: Math.max(medida ? medida.tasa_fp : teor(bpc, k), 1e-7) }], radio: 9, color: '--ink', estilo: 'circle', orden: -1 },
          ],
          xTitulo: 'Bits por clave distinta (m / n)', yTitulo: 'Tasa de falsos positivos (log)', yTipo: 'logarithmic',
          x: { min: 0, max: 20 }, y: { min: 1e-6, max: 1, ticks: { callback: (v) => ([1, 0.1, 0.01, 0.001, 1e-4, 1e-5, 1e-6].includes(v) ? (100 * v).toLocaleString(G.LOC, { maximumSignificantDigits: 1 }) + ' %' : '') } },
          tooltip: { label: (c) => ` ${c.dataset.label}: ${fmt.pct(3)(c.parsed.y)} con ${fmt.dec(1)(c.parsed.x)} bits/clave` },
        });
        lecturas('lec-bloom', [
          ['FP teórico (filtro lleno)', fmt.pct(3)(teor(bpc, k))],
          ['FP medido en el flujo', medida ? fmt.pct(3)(medida.tasa_fp) : 'no medido'],
          [tarea === 'ruc' ? 'Proveedores nuevos no alertados' : 'Textos nuevos tomados por reconvocatoria', medida ? fmt.ent(medida.fp) : '—'],
          ['Memoria', fmt.dec(2)(bpc * n / 8 / 1024 ** 2) + ' MB'],
          ['k óptimo = (m/n)·ln 2', String(kopt)],
        ]);
      };
      enlazar(['ctl-bloom-tarea', 'ctl-bloom-m', 'ctl-bloom-k'], dibujar);
    }
    if (hay('p4_cms')) {
      const c = D.p4_cms;
      const res = (D.p4_resumen && D.p4_resumen.cms) || [];
      const dibujar = () => {
        const tarea = $('ctl-cms-tarea').value;
        const w = 2 ** Number($('ctl-cms-w').value), d = Number($('ctl-cms-d').value);
        txt('out-cms-w', w.toLocaleString(G.LOC)); txt('out-cms-d', d);
        const filas = c.filter((r) => r.tarea === tarea);
        const ds = [1, 2, 4, 8];
        G.puntos('ch-cms', {
          series: ds.map((dd, i) => ({ nombre: `d = ${dd}`, datos: filas.filter((r) => r.d === dd).map((r) => ({ x: r.kb, y: Math.max(r.error_rel_top100, 1e-6) })), linea: true, radio: 3, slot: i }))
            .concat([{ nombre: 'Selección', datos: (() => { const f = filas.find((r) => r.w === w && r.d === d); return f ? [{ x: f.kb, y: Math.max(f.error_rel_top100, 1e-6) }] : []; })(), radio: 9, color: '--ink', estilo: 'circle', orden: -1 }]),
          xTitulo: 'Memoria del sketch (KB, escala log)', xTipo: 'logarithmic', yTitulo: 'Error relativo medio en el top 100 (log)', yTipo: 'logarithmic',
          x: { ticks: { callback: (v) => ([1, 10, 100, 1000, 10000].includes(v) ? fmt.ent(v) : '') } },
          y: { ticks: { callback: (v) => ([10, 1, 0.1, 0.01, 0.001, 1e-4].includes(v) ? (100 * v).toLocaleString(G.LOC, { maximumSignificantDigits: 1 }) + ' %' : '') } },
          tooltip: { label: (ctx) => ` ${ctx.dataset.label}: ${fmt.pct(2)(ctx.parsed.y)} con ${fmt.dec(1)(ctx.parsed.x)} KB` },
        });
        G.leyenda('ley-cms', ds.map((dd, i) => ({ nombre: `d = ${dd}`, slot: i })));
        const f = filas.find((r) => r.w === w && r.d === d);
        const r0 = res.find((r) => r.tarea === tarea) || {};
        if (f) lecturas('lec-cms', [
          ['ε = e/w → cota εN', fmt.ent(f.cota_eps_N) + ' eventos'],
          ['δ = e^−d', fmt.pct(2)(f.delta)],
          ['Claves dentro de la cota', fmt.pct(2)(f.pct_dentro_cota)],
          ['Error medio (sobreconteo)', fmt.dec(1)(f.error_medio)],
          ['Error rel. top 100', fmt.pct(2)(f.error_rel_top100)],
          ['Top 20 recuperado', fmt.pct(0)(f.recall_top20)],
          ['Memoria sketch / exacto', `${fmt.dec(0)(f.kb)} KB / ${fmt.dec(0)(r0.memoria_dict_exacto_mb)} MB`],
        ]);
      };
      enlazar(['ctl-cms-tarea', 'ctl-cms-w', 'ctl-cms-d'], dibujar);
    }
    if (hay('p4_dgim_series')) {
      const s = D.p4_dgim_series;
      const tabla = D.p4_dgim || [];
      const dibujar = () => {
        const N = Number($('ctl-dgim-n').value), r = Number($('ctl-dgim-r').value);
        const se = s.series.find((x) => x.N === N && x.r === r);
        if (!se) return;
        const fechas = se.pos.map((p) => s.fechas[Math.floor(p / s.paso)] || '');
        G.lineas('ch-dgim', {
          etiquetas: fechas,
          series: [{ nombre: 'Conteo exacto (Spark)', datos: se.exacto, slot: 0 },
                   { nombre: 'Estimación DGIM', datos: se.estimado, slot: 1 }],
          yTitulo: `Procesos ≥ S/ 1 M en los últimos ${N.toLocaleString(G.LOC)}`,
          x: { ticks: { maxTicksLimit: 8, callback: function (v) { return String(this.getLabelForValue(v)).slice(0, 7); } } },
        });
        G.leyenda('ley-dgim', [{ nombre: 'Conteo exacto (Spark)', slot: 0 }, { nombre: 'Estimación DGIM', slot: 1 }]);
        const f = tabla.find((x) => x.N === N && x.r === r);
        if (f) lecturas('lec-dgim', [
          ['Error relativo medio', fmt.pct(1)(f.error_rel_medio)],
          ['Error relativo máximo', fmt.pct(1)(f.error_rel_max)],
          ['Cota teórica', fmt.pct(0)(f.cota_teorica)],
          ['Memoria DGIM', fmt.ent(f.bits_memoria) + ' bits'],
          ['Memoria exacta (ventana)', fmt.ent(f.bits_exacto) + ' bits'],
        ]);
      };
      enlazar(['ctl-dgim-n', 'ctl-dgim-r'], dibujar);
    }
  }

  /* ================================================================ PARTE V */
  const RUBRO = { works: 'obras', goods: 'bienes', services: 'servicios' };
  const lista = (v) => [].concat(v).join(' + ');

  function reglas() {
    const res = D.p5_resumen || {};
    // ---- Apriori vs FP-Growth y explosion combinatoria
    if (res.apriori_vs_fpgrowth) {
      const a = res.apriori_vs_fpgrowth;
      const ks = Object.keys(a.por_nivel_apriori);
      G.tabla('tb-apriori', ks.map((k) => ({ k, ap: a.por_nivel_apriori[k], fp: a.por_tamanio_fpgrowth[k] })), [
        { clave: 'k', titulo: 'Tamaño del conjunto', num: true },
        { clave: 'ap', titulo: 'Apriori (RDD propio)', num: true, fmt: fmt.ent },
        { clave: 'fp', titulo: 'FP-Growth (MLlib)', num: true, fmt: fmt.ent },
      ]);
      lecturas('lec-apriori', [
        ['Canastas del subconjunto', fmt.ent(a.canastas) + ` (${a.anio})`],
        ['Umbral', `≥ ${a.min_conteo} procesos`],
        ['Apriori, k ≤ ' + a.k_max_apriori, fmt.dec(0)(a.segundos_apriori) + ' s'],
        ['FP-Growth, sin tope', fmt.dec(1)(a.segundos_fpgrowth) + ' s'],
        ['¿Mismos conjuntos y soportes?', a.identicos_hasta_kmax ? 'Sí, todos' : 'No'],
        ['FP-Growth: conjuntos totales', fmt.ent(a.conjuntos_fpgrowth)],
      ]);
    }
    if (hay('p5_conjuntos_por_tamanio')) {
      const t = D.p5_conjuntos_por_tamanio;
      G.barras('ch-tamanios', {
        etiquetas: t.map((r) => r.k),
        series: [{ nombre: 'Conjuntos frecuentes', datos: t.map((r) => r.conjuntos), slot: 0 },
                 { nombre: 'Maximales', datos: t.map((r) => r.maximales), slot: 1 }],
        xTitulo: 'Número de RUC en el conjunto', yTitulo: 'Conjuntos (escala log)', yTipo: 'logarithmic', y: { min: 0.5 },
        tooltip: { label: (c) => ` ${c.dataset.label}: ${fmt.ent(c.parsed.y)}` },
      });
      G.leyenda('ley-tamanios', [{ nombre: 'Conjuntos frecuentes', slot: 0 }, { nombre: 'Maximales (sin superconjunto frecuente)', slot: 1 }]);
    }
    // ---- Camarillas: conjuntos maximales con contexto
    if (hay('p5_camarillas')) {
      const C = D.p5_camarillas.map((r) => ({ ...r, exceso: (r.pct_gana_grupo ?? 0) - (r.pct_gana_esperado ?? 0) }));
      const dibujar = () => {
        const orden = $('ctl-cam-orden').value, alcance = $('ctl-cam-alcance').value;
        let f = C.filter((r) => alcance === 'todas' || (alcance === 'una' ? r.entidades === 1 : r.entidades > 1));
        f = [...f].sort(orden === 'exceso' ? (a, b) => b.exceso - a.exceso
          : orden === 'procesos' ? (a, b) => b.procesos_grupo - a.procesos_grupo
            : (a, b) => b.k - a.k || b.procesos_grupo - a.procesos_grupo);
        txt('out-cam-n', `${fmt.ent(f.length)} camarillas`);
        G.tabla('tb-camarillas', f.slice(0, 15), [
          { clave: 'k', titulo: 'RUC', num: true },
          { clave: 'tipos', titulo: 'Composición', fmt: (v) => String(v)
            .replace(/(\d+) empresa/g, (m, n) => (n === '1' ? m : `${n} empresas`))
            .replace(/(\d+) persona natural/g, (m, n) => (n === '1' ? m : `${n} personas naturales`)) },
          { clave: 'procesos_grupo', titulo: 'Procesos juntos', num: true, fmt: fmt.ent },
          { clave: 'postores_medio', titulo: 'Postores por proceso', num: true, fmt: fmt.dec(1) },
          { clave: 'entidades', titulo: 'Entidades', num: true },
          { clave: 'entidad_principal', titulo: 'Entidad principal', fmt: (v, r) => `${v} (${fmt.pct(0)(r.pct_entidad_principal)})` },
          { clave: 'rubro_principal', titulo: 'Rubro', fmt: (v) => RUBRO[v] || v },
          { clave: 'desde', titulo: 'Años', fmt: (v, r) => (v === r.hasta ? String(v) : `${v}-${r.hasta}`) },
          { clave: 'pct_gana_grupo', titulo: 'Gana el grupo', num: true, fmt: fmt.pct(0) },
          { clave: 'pct_gana_esperado', titulo: 'Esperado al azar', num: true, fmt: fmt.pct(0) },
        ]);
        const n1 = C.filter((r) => r.entidades === 1).length;
        lecturas('lec-cam', [
          ['Camarillas de ≥ 3 RUC analizadas', fmt.ent(C.length)],
          ['En una sola entidad', `${fmt.ent(n1)} (${fmt.pct(0)(n1 / C.length)})`],
          ['Ganan más que el azar', fmt.pct(0)(C.filter((r) => r.exceso > 0).length / C.length)],
        ]);
      };
      enlazar(['ctl-cam-orden', 'ctl-cam-alcance'], dibujar);
    }
    // ---- Reglas con filtros en vivo
    if (hay('p5_reglas_postores')) {
      const R = D.p5_reglas_postores;
      const dibujar = () => {
        const sop = Number($('ctl-r-sop').value), conf = Number($('ctl-r-conf').value) / 100,
          lift = 10 ** Number($('ctl-r-lift').value), tam = Number($('ctl-r-tam').value);
        txt('out-r-sop', fmt.ent(sop)); txt('out-r-conf', fmt.pct(0)(conf)); txt('out-r-lift', fmt.ent(lift)); txt('out-r-tam', tam);
        const f = R.filter((r) => r.procesos_grupo >= sop && r.confianza >= conf && r.lift >= lift && r.n_grupo >= tam)
          .sort((a, b) => b.soporte - a.soporte || b.confianza - a.confianza);
        txt('out-r-n', `${fmt.ent(f.length)} de ${fmt.ent(R.length)} reglas`);
        G.puntos('ch-reglas', {
          series: [
            { nombre: 'Fuera del filtro', datos: R.map((r) => ({ x: r.confianza, y: r.lift, r })), radio: 2, color: '--axis', borde: 0 },
            { nombre: 'Dentro del filtro', datos: f.map((r) => ({ x: r.confianza, y: r.lift, r })), radio: 2.5, slot: 0, borde: 0 },
          ],
          xTitulo: 'Confianza', yTitulo: 'Lift (escala log)', yTipo: 'logarithmic', x: { min: 0.5, max: 1 },
          tooltip: { label: (c) => ` ${lista(c.raw.r.antecedente)} → ${lista(c.raw.r.consecuente)} · conf ${fmt.pct(0)(c.raw.r.confianza)} · lift ${fmt.ent(c.raw.r.lift)} · ${fmt.ent(c.raw.r.procesos_grupo)} procesos` },
        });
        G.leyenda('ley-reglas', [{ nombre: 'Reglas dentro del filtro', slot: 0 }, { nombre: 'Resto de las reglas exportadas', color: '--axis' }]);
        G.tabla('tb-reglas', f.slice(0, 20), [
          { clave: 'antecedente', titulo: 'Si postula…', fmt: lista },
          { clave: 'consecuente', titulo: '…también postula', fmt: lista },
          { clave: 'procesos_grupo', titulo: 'Procesos juntos', num: true, fmt: fmt.ent },
          { clave: 'soporte', titulo: 'Soporte', num: true, fmt: fmt.pct(2) },
          { clave: 'confianza', titulo: 'Confianza', num: true, fmt: fmt.pct(0) },
          { clave: 'lift', titulo: 'Lift', num: true, fmt: fmt.ent },
          { clave: 'entidades', titulo: 'Entidades', num: true, fmt: fmt.ent },
          { clave: 'rubro_principal', titulo: 'Rubro', fmt: (v) => RUBRO[v] || v },
          { clave: 'pct_gana_grupo', titulo: 'Gana el grupo', num: true, fmt: fmt.pct(0) },
          { clave: 'pct_gana_esperado', titulo: 'Esperado', num: true, fmt: fmt.pct(0) },
        ]);
      };
      enlazar(['ctl-r-sop', 'ctl-r-conf', 'ctl-r-lift', 'ctl-r-tam'], dibujar);
    }
    // ---- Canasta C: entidad -> clases CUBSO
    if (hay('p5_reglas_cubso')) {
      const C = D.p5_reglas_cubso;
      const dibujar = () => {
        const lift = Number($('ctl-c-lift').value) / 10;
        txt('out-c-lift', fmt.dec(1)(lift));
        const f = C.filter((r) => r.lift >= lift).sort((a, b) => b.lift - a.lift);
        txt('out-c-n', `${fmt.ent(f.length)} de ${fmt.ent(C.length)} reglas`);
        G.tabla('tb-cubso', f.slice(0, 12), [
          { clave: 'antecedente', titulo: 'La entidad compra…', fmt: lista },
          { clave: 'consecuente', titulo: '…y también compra', fmt: lista },
          { clave: 'soporte', titulo: 'Soporte', num: true, fmt: fmt.pct(1) },
          { clave: 'confianza', titulo: 'Confianza', num: true, fmt: fmt.pct(0) },
          { clave: 'lift', titulo: 'Lift', num: true, fmt: fmt.dec(2) },
        ]);
      };
      enlazar(['ctl-c-lift'], dibujar);
    }
  }

  /* --------------------------------------------------- navegacion y tema */
  function navegacion() {
    const enlaces = [...document.querySelectorAll('.barra nav a')];
    const obs = new IntersectionObserver((ents) => {
      ents.forEach((e) => {
        if (e.isIntersecting) enlaces.forEach((a) => a.classList.toggle('activo', a.getAttribute('href') === '#' + e.target.id));
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    document.querySelectorAll('section[id]').forEach((s) => obs.observe(s));
    const btn = $('btn-tema');
    btn.addEventListener('click', () => {
      const oscuro = getComputedStyle(document.documentElement).getPropertyValue('--surface').trim() === '#1a1a19';
      document.documentElement.setAttribute('data-theme', oscuro ? 'light' : 'dark');
      try { localStorage.setItem('tema', oscuro ? 'light' : 'dark'); } catch (e) { /* sin almacenamiento */ }
      G.redibujarTodo();
    });
  }

  try { const t = localStorage.getItem('tema'); if (t) document.documentElement.setAttribute('data-theme', t); } catch (e) { /* nada */ }
  Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  Chart.defaults.locale = G.LOC;   // coma decimal tambien en ejes y tooltips
  [eda, similitud, ann, flujos, reglas, navegacion].forEach((f) => {
    try { f(); } catch (e) { console.error(f.name, e); }
  });
})();
