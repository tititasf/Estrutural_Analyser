/* Tags de segmento (fundos e laterais de viga) fora das linhas destacadas.
 *
 * Pedido do dono (2026-09-27): a tag nunca fica sobre uma linha destacada;
 * vai para o vazio mais proximo, afastada um pouco da viga, com uma linha
 * fina e discreta na cor do destaque ligando a tag ao seu segmento.
 * Usado no "Destacar no estrutural" (obra_detalhe.html) e na ficha SA de
 * laterais (lv_ficha.js) — um algoritmo so', mesmas regras nos dois.
 *
 * TagLeader.place(doc, parent, items, opts)
 *   items: [{pts: [[x,y],...], lines: ['V301', 'SEG 1-A'], color: '#f00',
 *            place: true|false}]  — place:false = so' obstaculo (ex.: pilar).
 *   opts:  {fontSize, halo, bounds: [x0,y0,x1,y1] opcional}
 * Coordenadas no espaco do SVG (as mesmas dos poligonos desenhados).
 */
(function (global) {
  'use strict';
  var SVGNS = 'http://www.w3.org/2000/svg';

  function lightTextColor(color) {
    var hex = String(color || '').replace(/^#/, '');
    if (hex.length === 3) hex = hex.split('').map(function (c) { return c + c; }).join('');
    if (!/^[0-9a-f]{6}$/i.test(hex)) return color;
    return '#' + [0, 2, 4].map(function (i) {
      var channel = parseInt(hex.slice(i, i + 2), 16);
      return Math.round(channel + (255 - channel) * 0.45).toString(16).padStart(2, '0');
    }).join('');
  }

  function geom(pts) {
    var p = pts.slice();
    if (p.length > 1 && p[0][0] === p[p.length - 1][0] && p[0][1] === p[p.length - 1][1]) p.pop();
    var cx = 0, cy = 0;
    p.forEach(function (q) { cx += q[0]; cy += q[1]; });
    cx /= p.length; cy /= p.length;
    var ux = 1, uy = 0, best = -1;
    for (var i = 0; i < p.length; i++) {
      var a = p[i], b = p[(i + 1) % p.length];
      var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy);
      if (len > best) { best = len; ux = len ? dx / len : 1; uy = len ? dy / len : 0; }
    }
    var nx = -uy, ny = ux, lmin = Infinity, lmax = -Infinity, tmin = Infinity, tmax = -Infinity;
    p.forEach(function (q) {
      var l = (q[0] - cx) * ux + (q[1] - cy) * uy, t = (q[0] - cx) * nx + (q[1] - cy) * ny;
      lmin = Math.min(lmin, l); lmax = Math.max(lmax, l);
      tmin = Math.min(tmin, t); tmax = Math.max(tmax, t);
    });
    // Centro real da faixa (o poligono pode nao ser simetrico em torno da media).
    var lc = (lmin + lmax) / 2, tc = (tmin + tmax) / 2;
    return {
      pts: p, ux: ux, uy: uy, nx: nx, ny: ny,
      cx: cx + ux * lc + nx * tc, cy: cy + uy * lc + ny * tc,
      L: Math.max((lmax - lmin) / 2, 0), T: Math.max((tmax - tmin) / 2, 0),
      vertical: Math.abs(uy) > Math.abs(ux) * 1.1,
    };
  }

  function segHitsBox(ax, ay, bx, by, b) {
    // Liang-Barsky: o segmento AB cruza o retangulo b?
    var t0 = 0, t1 = 1, dx = bx - ax, dy = by - ay;
    var p = [-dx, dx, -dy, dy], q = [ax - b.x0, b.x1 - ax, ay - b.y0, b.y1 - ay];
    for (var i = 0; i < 4; i++) {
      if (p[i] === 0) { if (q[i] < 0) return false; continue; }
      var r = q[i] / p[i];
      if (p[i] < 0) { if (r > t1) return false; if (r > t0) t0 = r; }
      else { if (r < t0) return false; if (r < t1) t1 = r; }
    }
    return true;
  }

  function inside(x, y, pts) {
    var c = false;
    for (var i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      var a = pts[i], b = pts[j];
      if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) c = !c;
    }
    return c;
  }

  function Grid(cell) {
    this.cell = cell; this.map = {};
  }
  Grid.prototype.keys = function (x0, y0, x1, y1) {
    var c = this.cell, out = [];
    for (var i = Math.floor(x0 / c); i <= Math.floor(x1 / c); i++)
      for (var j = Math.floor(y0 / c); j <= Math.floor(y1 / c); j++) out.push(i + ':' + j);
    return out;
  };
  Grid.prototype.add = function (obj, x0, y0, x1, y1) {
    var m = this.map;
    this.keys(x0, y0, x1, y1).forEach(function (k) { (m[k] = m[k] || []).push(obj); });
  };
  Grid.prototype.query = function (b) {
    var m = this.map, seen = [], out = [];
    this.keys(b.x0, b.y0, b.x1, b.y1).forEach(function (k) {
      (m[k] || []).forEach(function (o) { if (seen.indexOf(o) < 0) { seen.push(o); out.push(o); } });
    });
    return out;
  };

  function place(doc, parent, items, opts) {
    opts = opts || {};
    var fs = +opts.fontSize || 3.25;
    var gap = fs * 0.45;                 // folga tag x linha destacada
    var charW = fs * 0.68, lineH = fs * 1.2;
    var gs = items.map(function (it) {
      var g = (it.pts && it.pts.length >= 2) ? geom(it.pts) : null;
      return g ? {it: it, g: g} : null;
    }).filter(Boolean);
    var grid = new Grid(fs * 8);
    gs.forEach(function (e) {
      if (e.it.anchor) return; // Endpoint tags reuse their segment obstacle.
      var p = e.g.pts;
      for (var i = 0; i < p.length; i++) {
        var a = p[i], b = p[(i + 1) % p.length];
        grid.add({kind: 'edge', a: a, b: b},
          Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1]));
      }
      var xs = p.map(function (q) { return q[0]; }), ys = p.map(function (q) { return q[1]; });
      grid.add({kind: 'poly', pts: p}, Math.min.apply(null, xs), Math.min.apply(null, ys),
        Math.max.apply(null, xs), Math.max.apply(null, ys));
    });

    function conflicts(b) {
      var pad = {x0: b.x0 - gap, y0: b.y0 - gap, x1: b.x1 + gap, y1: b.y1 + gap};
      var n = 0, cx = (b.x0 + b.x1) / 2, cy = (b.y0 + b.y1) / 2;
      grid.query(pad).forEach(function (o) {
        if (o.kind === 'edge') { if (segHitsBox(o.a[0], o.a[1], o.b[0], o.b[1], pad)) n++; }
        else if (o.kind === 'poly') { if (inside(cx, cy, o.pts)) n++; }
        else if (o.kind === 'tag') {
          if (!(o.b.x1 < pad.x0 || o.b.x0 > pad.x1 || o.b.y1 < pad.y0 || o.b.y0 > pad.y1)) n += 2;
        }
      });
      var bd = opts.bounds;
      if (bd && (b.x0 < bd[0] || b.y0 < bd[1] || b.x1 > bd[2] || b.y1 > bd[3])) n += 1;
      return n;
    }

    var out = [], segmentLabels = {};
    // Place names first: adjustment tags share their segment name's row.
    gs.sort(function (a, b) { return Number(!!a.it.endpoint) - Number(!!b.it.endpoint); });
    gs.forEach(function (e) {
      var it = e.it, g = e.g;
      if (it.place === false) return;
      var fs = (+opts.fontSize || 3.25) * (it.fontScale || 1);
      var gap = fs * 0.45, charW = fs * 0.68, lineH = fs * 1.2;
      if (it.anchor) {
        // Keep the leader on this exact endpoint while sharing normal placement.
        g = Object.assign({}, g, {cx: it.anchor[0], cy: it.anchor[1], L: 0, T: 0});
      }
      var lines = (it.lines && it.lines.length) ? it.lines : [''];
      var chars = Math.max.apply(null, lines.map(function (s) { return String(s).length; })) || 1;
      var w = chars * charW + fs * 0.3, h = lines.length * lineH;
      if (it.roundedBox) { w += fs * 0.7; h += fs * 0.7; }
      var hw = (g.vertical ? h : w) / 2, hh = (g.vertical ? w : h) / 2;
      // meia-extensao da caixa na direcao normal a' viga
      var hn = Math.abs(g.nx) * hw + Math.abs(g.ny) * hh;
      var shifts = [0, -0.3, 0.3, -0.6, 0.6, -0.85, 0.85];
      var cands = [];
      shifts.forEach(function (s) {
        for (var k = 0; k < 14; k++) {
          [1, -1].forEach(function (side) {
            var d = g.T + gap * (it.endpoint ? 1 : 3.5) + hn + k * fs * 0.8;
            var ax = g.cx + g.ux * s * g.L, ay = g.cy + g.uy * s * g.L;
            cands.push({
              cost: d + Math.abs(s) * g.L * 0.6 + (side < 0 ? fs * 0.05 : 0),
              x: ax + g.nx * side * d, y: ay + g.ny * side * d,
              ax: ax + g.nx * side * g.T, ay: ay + g.ny * side * g.T,
            });
          });
        }
      });
      // Segmento curto entre vigas paralelas: a normal fica bloqueada. Anel
      // em 16 direcoes, raio crescente — o vazio mais proximo em qualquer lado.
      var r0 = Math.hypot(g.L, g.T) + gap * 2 + Math.max(hw, hh);
      for (var ring = 0; ring < 30; ring++) {
        var r = r0 + ring * fs * 0.8;
        for (var ang = 0; ang < 16; ang++) {
          var th = ang * Math.PI / 8, dx = Math.cos(th), dy = Math.sin(th);
          var ax = g.cx + g.ux * Math.max(-g.L, Math.min(g.L, (dx * g.ux + dy * g.uy) * r));
          var ay = g.cy + g.uy * Math.max(-g.L, Math.min(g.L, (dx * g.ux + dy * g.uy) * r));
          var sn = (dx * g.nx + dy * g.ny) >= 0 ? 1 : -1;
          cands.push({
            cost: r + fs * 1.5, x: g.cx + dx * r, y: g.cy + dy * r,
            ax: ax + g.nx * sn * g.T, ay: ay + g.ny * sn * g.T,
          });
        }
      }
      if (it.fixedPlacement && !it.endpoint) {
        // Lateral labels stay at the segment midpoint and on their own face.
        // Obstacles must not shift them along the beam or swap A/B sides.
        var face = String(it.lateralSide || '').trim().toUpperCase();
        var direction = face === 'B' ? 1 : -1;
        // Keep the requested normal offset independent from the label font size.
        var distance = g.T + (gap * 3.5 + hn) * (it.nameOffsetScale || 1) + (it.nameOffsetCm || 0);
        var dx = g.vertical ? direction : 0;
        var dy = g.vertical ? 0 : -direction;
        cands = [{cost: 0, x: g.cx + dx * distance, y: g.cy + dy * distance,
          ax: g.cx + dx * g.T, ay: g.cy + dy * g.T}];
      }
      var name = it.endpoint && segmentLabels[it.itemId];
      if (name && it.anchor) {
        // Compact pair beside the name, on the requested normal for side A/B.
        var side = it.endpoint === 'esquerda' ? -1 : 1;
        var halfNameHeight = g.vertical ? (name.box.x1 - name.box.x0) / 2 : (name.box.y1 - name.box.y0) / 2;
        var halfTagHeight = g.vertical ? hw : hh;
        var halfTagWidth = g.vertical ? hh : hw;
        var lateralSide = String(it.lateralSide || '').trim().toUpperCase();
        // Vertical A: follow the actual endpoint in SVG coordinates, where
        // smaller y is above. The rotated label axis runs in the opposite order.
        if (g.vertical && lateralSide === 'A') side = it.anchor[1] < name.y ? 1 : -1;
        var reverseNormal = (!g.vertical && lateralSide === 'A') || (g.vertical && lateralSide === 'B');
        var above = (halfNameHeight + halfTagHeight + gap) * (reverseNormal ? -1 : 1);
        var along = side * (halfTagWidth + gap / 2);
        cands = [{cost: 0, x: name.x + (g.vertical ? -above : along),
          y: name.y + (g.vertical ? -along : -above), ax: it.anchor[0], ay: it.anchor[1]}];
      }
      cands.sort(function (a, b) { return a.cost - b.cost; });
      var best = null, bestN = Infinity;
      for (var i = 0; i < cands.length; i++) {
        var c = cands[i];
        var box = {x0: c.x - hw, y0: c.y - hh, x1: c.x + hw, y1: c.y + hh};
        var n = conflicts(box);
        if (n < bestN) { best = {c: c, box: box}; bestN = n; if (!n) break; }
      }
      if (!best) return;
      var tag = {kind: 'tag', b: best.box};
      grid.add(tag, best.box.x0, best.box.y0, best.box.x1, best.box.y1);
      var c = best.c, color = it.color || '#fff';
      if (!it.endpoint && it.itemId) segmentLabels[it.itemId] = {x: c.x, y: c.y, box: best.box};
      // Hidden names still anchor independently visible adjustment/support tags.
      if (it.render === false) return;

      // Linha fina e discreta, na cor do destaque: da borda do segmento ate'
      // o ponto mais proximo da caixa da tag.
      var ex = Math.max(best.box.x0, Math.min(c.ax, best.box.x1));
      var ey = Math.max(best.box.y0, Math.min(c.ay, best.box.y1));
      if (name) {
        // A diagonal connector from the exact endpoint to the text's corner.
        ex = c.ax < c.x ? best.box.x0 : best.box.x1;
        ey = c.ay < c.y ? best.box.y0 : best.box.y1;
      }
      var leader = doc.createElementNS(SVGNS, 'line');
      leader.setAttribute('x1', c.ax); leader.setAttribute('y1', c.ay);
      leader.setAttribute('x2', ex); leader.setAttribute('y2', ey);
      leader.setAttribute('stroke', color);
      leader.setAttribute('stroke-width', '1');
      leader.setAttribute('stroke-opacity', '0.75');
      leader.setAttribute('vector-effect', 'non-scaling-stroke');
      leader.setAttribute('class', 'tag-leader');
      if (!it.endpoint) parent.appendChild(leader);

      if (it.roundedBox) {
        var background = doc.createElementNS(SVGNS, 'rect');
        background.setAttribute('x', best.box.x0); background.setAttribute('y', best.box.y0);
        background.setAttribute('width', hw * 2); background.setAttribute('height', hh * 2);
        background.setAttribute('rx', fs * 0.6); background.setAttribute('ry', fs * 0.6);
        background.setAttribute('fill', '#0b1220');
        background.setAttribute('fill-opacity', '0.65');
        background.setAttribute('stroke', color); background.setAttribute('stroke-opacity', '0.65');
        background.setAttribute('stroke-width', '0.5');
        background.setAttribute('vector-effect', 'non-scaling-stroke');
        background.setAttribute('class', 'tag-label-box');
        background._geometryItem = it.geometryItem;
        parent.appendChild(background);
      }

      var txt = doc.createElementNS(SVGNS, 'text');
      txt.setAttribute('x', c.x); txt.setAttribute('y', c.y);
      txt.setAttribute('fill', lightTextColor(color));
      txt.setAttribute('font-size', String(fs));
      txt.setAttribute('text-anchor', 'middle');
      txt.setAttribute('dominant-baseline', 'middle');
      txt.setAttribute('paint-order', 'stroke');
      txt.setAttribute('stroke', '#000');
      txt.setAttribute('stroke-width', String(opts.halo ? opts.halo * (it.fontScale || 1) : fs * 0.22));
      txt.setAttribute('class', 'tag-leader-text' + (it.endpoint ? ' tag-ajuste-ponta' : ''));
      txt._geometryItem = it.geometryItem;
      txt.setAttribute('data-item-id', it.itemId || '');
      if (it.endpoint) {
        txt.setAttribute('opacity', '0.85');
        if (name) {
          txt.setAttribute('data-layout', 'compact-pair');
          txt.setAttribute('data-lateral-side', it.lateralSide || '');
          txt.setAttribute('data-name-x', name.x);
          txt.setAttribute('data-name-y', name.y);
        }
        txt.setAttribute('data-ponta', it.endpoint);
        txt.setAttribute('data-item-id', it.itemId || '');
        txt.setAttribute('data-ajuste-cm', it.value == null ? 'unknown' : String(it.value));
      }
      if (g.vertical) txt.setAttribute('transform', 'rotate(-90 ' + c.x + ' ' + c.y + ')');
      lines.forEach(function (line, li) {
        var ts = doc.createElementNS(SVGNS, 'tspan');
        ts.setAttribute('x', c.x);
        ts.setAttribute('dy', li === 0 ? (lines.length > 1 ? (-0.55 * (lines.length - 1)) + 'em' : '0') : '1.15em');
        ts.textContent = line;
        txt.appendChild(ts);
      });
      if (it.title) {
        var t = doc.createElementNS(SVGNS, 'title'); t.textContent = it.title; txt.appendChild(t);
      }
      parent.appendChild(txt);
      out.push({item: it, box: best.box, conflitos: bestN});
    });
    return out;
  }

  global.TagLeader = {place: place, _geom: geom};
})(window);
