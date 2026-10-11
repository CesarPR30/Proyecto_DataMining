/* Capa delgada sobre Chart.js con las convenciones del reporte:
   - colores por rol leidos de los tokens CSS (cambian con el tema);
   - lineas de 2px, barras finas con extremo redondeado, grilla en hairline;
   - tooltip con crosshair en lineas y por marca en barras/puntos;
   - cada grafico se registra para redibujarse al cambiar de tema. */
(function () {
  const registro = new Map();   // canvas id -> funcion que construye la config

  function css(nombre) {
    return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
  }
  const serie = (i) => css(`--s${(i % 8) + 1}`);

  function base(opc) {
    const ink2 = css('--ink-2'), muted = css('--muted'), grid = css('--grid');
    const ejes = (titulo, tipo, extra = {}) => Object.assign({
      type: tipo || 'linear',
      title: { display: !!titulo, text: titulo || '', color: ink2, font: { size: 12 } },
      grid: { color: grid, lineWidth: 1, drawTicks: false },
      border: { color: css('--axis') },
      ticks: { color: muted, font: { size: 11 }, padding: 6, maxRotation: 0, autoSkipPadding: 12 },
    }, extra);
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      interaction: { mode: opc.modo || 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: css('--surface'), titleColor: ink2, bodyColor: css('--ink'),
          borderColor: css('--border'), borderWidth: 1, padding: 10,
          boxWidth: 12, boxHeight: 2, usePointStyle: false,
          titleFont: { weight: '500', size: 12 }, bodyFont: { weight: '600', size: 13 },
          callbacks: opc.tooltip || {},
        },
      },
      scales: {
        x: ejes(opc.xTitulo, opc.xTipo, opc.x || {}),
        y: ejes(opc.yTitulo, opc.yTipo, Object.assign({ beginAtZero: opc.yTipo !== 'logarithmic' }, opc.y || {})),
      },
    };
  }

  function dibujar(id, construir) {
    registro.set(id, construir);
    const lienzo = document.getElementById(id);
    if (!lienzo) return null;
    if (lienzo._chart) lienzo._chart.destroy();
    lienzo._chart = new Chart(lienzo, construir());
    return lienzo._chart;
  }

  /* Serie de lineas. series: [{nombre, datos:[{x,y}] | [y...], color?, punteada?, relleno?}] */
  function lineas(id, opc) {
    opc = Object.assign({ xTipo: 'category' }, opc);   // etiquetas -> eje categorico
    return dibujar(id, () => ({
      type: 'line',
      data: {
        labels: opc.etiquetas,
        datasets: opc.series.map((s, i) => ({
          label: s.nombre,
          data: s.datos,
          borderColor: s.color ? css(s.color) : serie(s.slot ?? i),
          backgroundColor: s.relleno ? (s.color ? css(s.color) : serie(s.slot ?? i)) + '1a' : 'transparent',
          fill: !!s.relleno,
          borderWidth: s.ancho || 2,
          borderDash: s.punteada ? [5, 4] : [],
          pointRadius: s.puntos ? 4 : 0,
          pointHoverRadius: 5,
          pointBackgroundColor: s.color ? css(s.color) : serie(s.slot ?? i),
          pointBorderColor: css('--surface'), pointBorderWidth: 2,
          tension: 0, stepped: s.escalon || false,
          showLine: s.sinLinea ? false : true,
          order: s.orden ?? i,
        })),
      },
      options: base(opc),
    }));
  }

  /* Barras (verticales u horizontales). series como en lineas, datos = valores. */
  function barras(id, opc) {
    if (!opc.horizontal) opc = Object.assign({ xTipo: 'category' }, opc);
    return dibujar(id, () => {
      const o = base(Object.assign({ modo: 'index' }, opc));
      if (opc.horizontal) {
        o.indexAxis = 'y';
        const t = o.scales.x; o.scales.x = o.scales.y; o.scales.y = t;
        o.scales.x.title.text = opc.yTitulo || ''; o.scales.x.title.display = !!opc.yTitulo;
        o.scales.y.title.text = opc.xTitulo || ''; o.scales.y.title.display = !!opc.xTitulo;
        o.scales.x.type = opc.yTipo || 'linear';
        o.scales.y.type = 'category';
        o.scales.y.grid = { display: false };
        o.scales.y.ticks.autoSkip = false;
      } else {
        o.scales.x.grid = { display: false };
      }
      if (opc.apiladas) { o.scales.x.stacked = true; o.scales.y.stacked = true; }
      return {
        type: 'bar',
        data: {
          labels: opc.etiquetas,
          datasets: opc.series.map((s, i) => ({
            label: s.nombre, data: s.datos,
            backgroundColor: s.colores ? s.colores.map(css) : (s.color ? css(s.color) : serie(s.slot ?? i)),
            borderRadius: 4,   // el borde de la base (borderSkipped) queda recto
            borderSkipped: 'start',
            borderColor: css('--surface'), borderWidth: opc.apiladas ? { top: 2 } : 0,
            maxBarThickness: 24, categoryPercentage: 0.8, barPercentage: 0.9,
          })),
        },
        options: o,
      };
    });
  }

  /* Dispersion con lineas opcionales: series [{nombre, datos:[{x,y,...}], linea?}] */
  function puntos(id, opc) {
    return dibujar(id, () => {
      const o = base(Object.assign({ modo: 'nearest' }, opc));
      o.interaction = { mode: 'nearest', intersect: false, axis: 'xy' };
      return {
        type: 'scatter',
        data: {
          datasets: opc.series.map((s, i) => ({
            label: s.nombre, data: s.datos,
            showLine: !!s.linea, borderWidth: 2,
            borderColor: s.color ? css(s.color) : serie(s.slot ?? i),
            backgroundColor: s.color ? css(s.color) : serie(s.slot ?? i),
            pointRadius: s.radio ?? 4, pointHoverRadius: (s.radio ?? 4) + 2,
            pointHitRadius: 12,
            // anillo de superficie de 2px; en nubes densas (borde: 0) se omite
            pointBorderColor: css('--surface'), pointBorderWidth: s.borde ?? 2,
            borderDash: s.punteada ? [5, 4] : [],
            pointStyle: s.estilo || 'circle',
            order: s.orden ?? i,
          })),
        },
        options: o,
      };
    });
  }

  function redibujarTodo() {
    for (const [id, construir] of registro) {
      const lienzo = document.getElementById(id);
      if (!lienzo) continue;
      if (lienzo._chart) lienzo._chart.destroy();
      lienzo._chart = new Chart(lienzo, construir());
    }
  }

  /* Leyenda HTML (texto con textContent; el color va en la marca, no en el texto) */
  function leyenda(idCont, items) {
    const cont = document.getElementById(idCont);
    if (!cont) return;
    cont.replaceChildren();
    items.forEach((it, i) => {
      const span = document.createElement('span');
      const b = document.createElement('b');
      b.style.background = it.color ? css(it.color) : serie(it.slot ?? i);
      if (it.punteada) { b.style.background = 'transparent'; b.style.borderTop = `2px dashed ${it.color ? css(it.color) : serie(it.slot ?? i)}`; }
      span.append(b, document.createTextNode(it.nombre));
      cont.append(span);
    });
  }

  /* Tabla a partir de filas; columnas: [{clave, titulo, num?, fmt?}] */
  function tabla(idCont, filas, columnas, opc = {}) {
    const cont = document.getElementById(idCont);
    if (!cont) return;
    const t = document.createElement('table');
    const thead = t.createTHead().insertRow();
    columnas.forEach((c) => {
      const th = document.createElement('th');
      th.textContent = c.titulo; if (c.num) th.className = 'n';
      thead.append(th);
    });
    const tb = t.createTBody();
    filas.forEach((f) => {
      const tr = tb.insertRow();
      if (opc.resaltar && opc.resaltar(f)) tr.className = 'sel';
      columnas.forEach((c) => {
        const td = tr.insertCell();
        const v = f[c.clave];
        td.textContent = c.fmt ? c.fmt(v, f) : (v ?? '—');
        if (c.num) td.className = 'n';
      });
    });
    cont.replaceChildren(t);
  }

  // Formato del informe: coma decimal y espacio fino de miles (2 760 591; 40,6).
  // 'fr-FR' produce exactamente esa convencion; es-PE usaria punto decimal.
  const LOC = 'fr-FR';
  const fmt = {
    ent: (v) => v == null ? '—' : Math.round(v).toLocaleString(LOC),
    dec: (d) => (v) => v == null ? '—' : Number(v).toLocaleString(LOC, { minimumFractionDigits: d, maximumFractionDigits: d }),
    pct: (d = 1) => (v) => v == null ? '—' : (100 * v).toLocaleString(LOC, { minimumFractionDigits: d, maximumFractionDigits: d }) + ' %',
    compacto: (v) => {
      if (v == null) return '—';
      const a = Math.abs(v);
      if (a >= 1e9) return (v / 1e9).toLocaleString(LOC, { maximumFractionDigits: 1 }) + ' mil M';
      if (a >= 1e6) return (v / 1e6).toLocaleString(LOC, { maximumFractionDigits: 1 }) + ' M';
      if (a >= 1e3) return (v / 1e3).toLocaleString(LOC, { maximumFractionDigits: 1 }) + ' mil';
      return v.toLocaleString(LOC, { maximumFractionDigits: 2 });
    },
  };

  window.G = { LOC, lineas, barras, puntos, leyenda, tabla, fmt, css, serie, redibujarTodo };
})();
