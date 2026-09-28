"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import type { ChapaLayout } from "@/lib/api/materiais";
import styles from "./MateriaisTab.module.css";

const CHAPA_W = 244;
const CHAPA_H = 122;
const MARGEM = 10;

/** Cores por origem (Lado A, Lado B, face A...): translúcidas p/ tema claro e escuro. */
const PALETA = ["#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"];

const fmt = (n: number) => n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });

/** Plano de corte das chapas 244 x 122 [2026-09-28]: uma mini-aba por chapa,
 * cada peça desenhada na posição de corte com o número do painel da lista. */
const VB0 = { x: -MARGEM, y: -MARGEM, w: CHAPA_W + 2 * MARGEM, h: CHAPA_H + 2 * MARGEM };

export function ChapasViewer({ layout }: { layout: ChapaLayout[] }) {
  const [ativa, setAtiva] = useState(0);
  // Pan/zoom só por viewBox (PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md): roda = zoom
  // no cursor, arrastar = mover, duplo clique = enquadrar a chapa.
  const [vb, setVb] = useState(VB0);
  const svgRef = useRef<SVGSVGElement>(null);
  const arrasto = useRef<{ x: number; y: number; vb: typeof VB0 } | null>(null);

  const noSvg = (clientX: number, clientY: number) => {
    const r = svgRef.current!.getBoundingClientRect();
    return { fx: (clientX - r.left) / r.width, fy: (clientY - r.top) / r.height, r };
  };
  // Listener nativo não-passivo: o onWheel do React é passivo e a página rolaria junto.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const { fx, fy } = noSvg(e.clientX, e.clientY);
      const k = e.deltaY > 0 ? 1.2 : 1 / 1.2;
      setVb((v) => {
        const w = Math.min(VB0.w * 1.5, Math.max(8, v.w * k));
        const h = (w * VB0.h) / VB0.w;
        return { x: v.x + fx * (v.w - w), y: v.y + fy * (v.h - h), w, h };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });
  const onDown = (e: PointerEvent<SVGSVGElement>) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    arrasto.current = { x: e.clientX, y: e.clientY, vb };
  };
  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const a = arrasto.current;
    if (!a) return;
    const { r } = noSvg(e.clientX, e.clientY);
    setVb({ ...a.vb, x: a.vb.x - ((e.clientX - a.x) * a.vb.w) / r.width, y: a.vb.y - ((e.clientY - a.y) * a.vb.h) / r.height });
  };
  const onUp = () => {
    arrasto.current = null;
  };
  if (layout.length === 0) return null;
  const chapa = layout[Math.min(ativa, layout.length - 1)];
  const origens = Array.from(new Set(layout.flatMap((c) => c.pecas.map((p) => p.origem))));
  const cor = (o: string) => PALETA[origens.indexOf(o) % PALETA.length];

  return (
    <div className={styles.viewer}>
      <div className={styles.miniAbas} role="tablist" aria-label="Chapas do plano de corte">
        {layout.map((c, i) => (
          <button
            key={c.chapa}
            role="tab"
            aria-selected={i === ativa}
            className={`${styles.miniAba} ${i === ativa ? styles.miniAbaAtiva : ""}`}
            onClick={() => {
              setAtiva(i);
              setVb(VB0);
            }}
          >
            Chapa {c.chapa}
          </button>
        ))}
      </div>

      <div className={styles.svgWrap}>
        <svg
          ref={svgRef}
          viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
          className={styles.svgChapa}
          onPointerDown={onDown}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerLeave={onUp}
          onDoubleClick={() => setVb(VB0)}
          role="img"
          aria-label={`Chapa ${chapa.chapa}: ${chapa.pecas.length} peças`}
        >
          <defs>
            <pattern id="sobra" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="4" className={styles.hachura} />
            </pattern>
          </defs>
          <rect x={0} y={0} width={CHAPA_W} height={CHAPA_H} className={styles.chapaFundo} />
          {chapa.sobras.map((s) => {
            const menor = Math.min(s.largura_cm, s.altura_cm);
            return (
              <g key={s.rotulo}>
                <title>{`Sobra ${s.rotulo} · ${fmt(s.largura_cm)} × ${fmt(s.altura_cm)} cm`}</title>
                <rect x={s.x} y={s.y} width={s.largura_cm} height={s.altura_cm} fill="url(#sobra)" />
                {menor >= 4 && (
                  <text
                    x={s.x + s.largura_cm / 2}
                    y={s.y + s.altura_cm / 2}
                    fontSize={Math.max(2.5, Math.min(9, menor * 0.3))}
                    textAnchor="middle"
                    dominantBaseline="central"
                    className={styles.medidaPeca}
                  >
                    {s.rotulo}
                  </text>
                )}
              </g>
            );
          })}
          {chapa.pecas.map((p) => {
            const cx = p.x + p.largura_cm / 2;
            const cy = p.y + p.altura_cm / 2;
            const menor = Math.min(p.largura_cm, p.altura_cm);
            const fs = Math.max(3, Math.min(14, menor * 0.35));
            return (
              <g key={p.rotulo}>
                <title>{`Painel ${p.rotulo} · ${p.origem} · ${fmt(p.largura_cm)} × ${fmt(p.altura_cm)} cm${p.girado ? " (girado)" : ""}`}</title>
                <rect
                  x={p.x}
                  y={p.y}
                  width={p.largura_cm}
                  height={p.altura_cm}
                  fill={cor(p.origem)}
                  fillOpacity={0.35}
                  stroke={cor(p.origem)}
                  strokeWidth={0.6}
                />
                <text x={cx} y={cy} fontSize={fs} textAnchor="middle" dominantBaseline="central" className={styles.rotuloPeca}>
                  {p.rotulo}
                </text>
                {menor >= 18 && (
                  <text x={cx} y={cy + fs * 0.9} fontSize={fs * 0.45} textAnchor="middle" dominantBaseline="hanging" className={styles.medidaPeca}>
                    {fmt(p.largura_cm)} × {fmt(p.altura_cm)}
                  </text>
                )}
              </g>
            );
          })}
          <text x={CHAPA_W / 2} y={-3} fontSize={5} textAnchor="middle" className={styles.medidaPeca}>244</text>
          <text x={-3} y={CHAPA_H / 2} fontSize={5} textAnchor="middle" transform={`rotate(-90 -3 ${CHAPA_H / 2})`} className={styles.medidaPeca}>122</text>
        </svg>
      </div>

      <p className={`${styles.resumo} tabular-nums`}>Aproveitamento {Math.round(chapa.aproveitamento * 100)}%</p>

      <div className={styles.tabelaWrap}>
        <table className={`${styles.tabela} tabular-nums`}>
          <thead>
            <tr><th>Nº</th><th className={styles.esq}>Painel de</th><th>Corte (cm)</th></tr>
          </thead>
          <tbody>
            {[...chapa.pecas]
              .sort((a, b) => a.rotulo.localeCompare(b.rotulo, "pt-BR", { numeric: true }))
              .map((p) => (
                <tr key={p.rotulo}>
                  <td>
                    <span className={styles.bolinha} style={{ background: cor(p.origem) }} />
                    {p.rotulo}
                  </td>
                  <td className={styles.esq}>{p.origem}</td>
                  <td>
                    {fmt(p.largura_cm)} × {fmt(p.altura_cm)}
                    {p.girado && <span className={styles.sub}>girado 90°</span>}
                  </td>
                </tr>
              ))}
            {chapa.sobras.map((s) => (
              <tr key={s.rotulo} className={styles.linhaSobra}>
                <td>{s.rotulo}</td>
                <td className={styles.esq}>Sobra</td>
                <td>{fmt(s.largura_cm)} × {fmt(s.altura_cm)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
