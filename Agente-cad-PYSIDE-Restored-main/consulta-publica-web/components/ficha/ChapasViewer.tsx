"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import type { ChapaLayout, PainelMedido } from "@/lib/api/materiais";
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

/** Contorno do painel recortado na posição de corte da chapa (y p/ baixo).
 * Painel local: y p/ cima. Girado = rotação de 90° (largura ↔ altura). */
function pontosNaChapa(p: { x: number; y: number; girado: boolean }, painel: PainelMedido, anel: [number, number][]) {
  const h = painel.altura_cm;
  return anel
    .map(([lx, ly]) => (p.girado ? [p.x + ly, p.y + lx] : [p.x + lx, p.y + (h - ly)]))
    .map(([x, y]) => `${x},${y}`)
    .join(" ");
}

export function ChapasViewer({ layout, paineis = {} }: { layout: ChapaLayout[]; paineis?: Record<string, PainelMedido> }) {
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
            <pattern id="recorte" width="2.5" height="2.5" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
              <line x1="0" y1="0" x2="0" y2="2.5" className={styles.hachuraRecorte} />
            </pattern>
          </defs>
          <rect x={0} y={0} width={CHAPA_W} height={CHAPA_H} className={styles.chapaFundo} />
          {chapa.sobras.map((s) => {
            // Rótulo no maior retângulo útil (sobra em L/diagonal).
            const r = s.util ?? s;
            const menor = Math.min(r.largura_cm, r.altura_cm);
            // Recorte de painel (sozinho ou somado à sobra vizinha): vermelho.
            const cls = s.recorte_de ? styles.recorte : undefined;
            const fill = s.recorte_de ? "url(#recorte)" : "url(#sobra)";
            return (
              <g key={s.rotulo}>
                <title>{`Sobra ${s.id ?? s.rotulo} · ${fmt(s.largura_cm)} × ${fmt(s.altura_cm)} cm${s.util ? ` · útil ${fmt(s.util.largura_cm)} × ${fmt(s.util.altura_cm)}` : ""}${s.recorte_de ? ` · recorte de ${s.recorte_de.join(", ")}` : ""}`}</title>
                {s.contorno ? (
                  <polygon points={s.contorno.map(([x, y]) => `${x},${y}`).join(" ")} fill={fill} className={cls} />
                ) : (
                  <rect x={s.x} y={s.y} width={s.largura_cm} height={s.altura_cm} fill={fill} className={cls} />
                )}
                {menor >= 4 && (
                  <text
                    x={r.x + r.largura_cm / 2}
                    y={r.y + r.altura_cm / 2}
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
            const painel = p.id ? paineis[p.id] : undefined;
            const partes = painel?.partes;
            return (
              <g key={p.rotulo}>
                <title>{`Painel ${p.rotulo}${p.id ? ` · ${p.id}` : ""} · ${p.origem} · ${fmt(p.largura_cm)} × ${fmt(p.altura_cm)} cm${p.girado ? " (girado)" : ""}${partes ? " · recortado" : ""}${p.em_sobra ? " · cortado na sobra" : ""}`}</title>
                {partes && painel ? (
                  // Peças reais; o que sobra do retângulo (recorte) é desenhado
                  // como sobra, em vermelho, logo acima.
                  partes.map((pt, k) => (
                    <path
                      key={k}
                      d={[pt.contorno, ...(pt.furos ?? [])].map((a) => `M${pontosNaChapa(p, painel, a)}Z`).join(" ")}
                      fillRule="evenodd"
                      fill={cor(p.origem)}
                      stroke={cor(p.origem)}
                      strokeWidth={0.6}
                      className={styles.pecaRecortada}
                    />
                  ))
                ) : (
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
                )}
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
            <tr><th>Nº</th><th className={styles.esq}>ID</th><th className={styles.esq}>Painel de</th><th>Corte (cm)</th></tr>
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
                  <td className={`${styles.esq} ${styles.idPainel}`}>{p.id || "—"}</td>
                  <td className={styles.esq}>{p.origem}</td>
                  <td>
                    {fmt(p.largura_cm)} × {fmt(p.altura_cm)}
                    {p.girado && <span className={styles.sub}>girado 90°</span>}
                    {p.id && paineis[p.id.replace(/(-P\d+)[a-z]$/, "$1")]?.partes && (
                      <span className={styles.tag} title="Corta-se o retângulo; o recorte (vermelho) vira sobra com ID">recortado</span>
                    )}
                    {p.em_sobra && (
                      <span className={styles.tag} title="Cortado na sobra de outra chapa (recorte), sem abrir chapa nova">na sobra</span>
                    )}
                  </td>
                </tr>
              ))}
            {chapa.sobras.map((s) => (
              <tr key={s.rotulo} className={styles.linhaSobra}>
                <td>{s.rotulo}</td>
                <td className={`${styles.esq} ${styles.idPainel}`}>{s.id ?? "—"}</td>
                <td className={styles.esq}>
                  {s.recorte_de ? `Sobra · recorte de ${s.recorte_de.map((i) => i.split("-").pop()).join(", ")}` : "Sobra"}
                </td>
                <td>
                  {fmt(s.largura_cm)} × {fmt(s.altura_cm)}
                  {s.util && <span className={styles.sub}>útil {fmt(s.util.largura_cm)} × {fmt(s.util.altura_cm)}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
