"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { GrupoMateriais, PainelMedido, SarrafoMontagem } from "@/lib/api/materiais";
import type { BufferGeometry, Material, MeshStandardMaterial } from "three";
import styles from "./MontagemPaineis.module.css";

/** Espessura da chapa de compensado (cm) — só visual. */
const CHAPA_ESP = 1.8;
/** Tempos da animação (s, na velocidade 1×). */
const T_PAINEL = 0.9;
const T_PECA = 0.75;
const QUEDA_CM = 70;

const COR = { painel: 0x8f4f25, borda: 0x3d2a14, sarrafo: 0xf0dcaa, pressao: 0xf2a93b, destaque: 0x2f7de1 };

interface Item {
  painel: PainelMedido;
  grupo: string;
}

const fmt = (n: number) => n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
const nomePeca = (s: SarrafoMontagem) =>
  (/press/i.test(s.bitola) ? "Pressão " : "") +
  s.bitola.replace(/^Sarrafo( de pressão)?\s*/i, "").replace(/\s*cm$/i, "").replace(/\./g, ",");
const ease = (t: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);

/** Viewer 3D (three.js) de 1 painel: a chapa já cortada entra na bancada e
 * os sarrafos descem um a um até a posição medida no N3. */
function Cena({ painel, velocidade, rodada, onPasso }: {
  painel: PainelMedido;
  velocidade: number;
  rodada: number;
  onPasso: (i: number) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const vel = useRef(velocidade);
  vel.current = velocidade;
  const passo = useRef(onPasso);
  passo.current = onPasso;

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let vivo = true;
    let limpar = () => {};
    (async () => {
      const THREE = await import("three");
      const { OrbitControls } = await import("three/examples/jsm/controls/OrbitControls.js");
      if (!vivo) return;
      const W = painel.largura_cm;
      const H = painel.altura_cm;
      const pecas = painel.montagem ?? [];

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      el.appendChild(renderer.domElement);
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(40, 1, 1, 5000);
      const maior = Math.max(W, H, 60);
      camera.position.set(W / 2 + maior * 0.25, maior * 0.72, maior * 0.55);
      const controls = new OrbitControls(camera, renderer.domElement);
      controls.target.set(W / 2, 0, -H / 2);
      controls.enableDamping = true;
      controls.update();

      scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7a66, 1.6));
      const sol = new THREE.DirectionalLight(0xffffff, 1.6);
      sol.position.set(W * 0.2 - maior, maior * 2, maior);
      scene.add(sol);
      const grade = new THREE.GridHelper(maior * 2.4, 24, 0x999999, 0xcccccc);
      grade.position.set(W / 2, -6, -H / 2);
      (grade.material as Material).transparent = true;
      (grade.material as Material).opacity = 0.35;
      scene.add(grade);

      const descartar: { dispose: () => void }[] = [renderer, controls];
      const caixa = (w: number, h: number, e: number, cor: number, forma?: BufferGeometry) => {
        const geo = forma ?? new THREE.BoxGeometry(w, e, h);
        const mat = new THREE.MeshStandardMaterial({ color: cor, roughness: 0.85, transparent: true });
        const mesh = new THREE.Mesh(geo, mat);
        const eg = new THREE.EdgesGeometry(geo);
        const lm = new THREE.LineBasicMaterial({ color: COR.borda, transparent: true });
        mesh.add(new THREE.LineSegments(eg, lm));
        descartar.push(geo, mat, eg, lm);
        scene.add(mesh);
        return { mesh, mats: [mat, lm] };
      };

      // Desenho: x p/ direita, y p/ cima → bancada: X = x, Z = -y, Y = espessura.
      // Painel recortado: extrusão do contorno real (com furos) — a abertura
      // aparece vazada. Shape no plano (x, y); girar -90° em X leva y → -Z e a
      // extrusão → +Y, com a base da chapa em Y = 0.
      let forma: BufferGeometry | undefined;
      const partes = (painel.partes ?? []).filter((p) => p.contorno.length >= 3);
      if (partes.length) {
        const anel = (pts: [number, number][], alvo: InstanceType<typeof THREE.Path>) => {
          pts.forEach(([x, y], i) => (i ? alvo.lineTo(x, y) : alvo.moveTo(x, y)));
          alvo.closePath();
          return alvo;
        };
        // 1 Shape por parte (viga cruzando a face = 2 peças), mesma extrusão.
        const shapes = partes.map((pt) => {
          const shape = anel(pt.contorno, new THREE.Shape()) as InstanceType<typeof THREE.Shape>;
          (pt.furos ?? []).forEach((f) => shape.holes.push(anel(f, new THREE.Path())));
          return shape;
        });
        forma = new THREE.ExtrudeGeometry(shapes, { depth: CHAPA_ESP, bevelEnabled: false });
        forma.rotateX(-Math.PI / 2);
      }
      const chapa = caixa(W, H, CHAPA_ESP, COR.painel, forma);
      const pChapa = forma ? new THREE.Vector3(0, 0, 0) : new THREE.Vector3(W / 2, CHAPA_ESP / 2, -H / 2);
      const sarr = pecas.map((s) => {
        const c = caixa(s.w, s.h, s.espessura_cm, /press/i.test(s.bitola) ? COR.pressao : COR.sarrafo);
        // Pressão vai na face de trás (linha HIDDEN): embaixo da chapa, sobe.
        const tras = s.face === "tras";
        const y = tras ? -s.espessura_cm / 2 : CHAPA_ESP + s.espessura_cm / 2;
        const destino = new THREE.Vector3(s.x + s.w / 2, y, -(s.y + s.h / 2));
        return { ...c, destino, dir: tras ? -1 : 1 };
      });

      let t = 0;
      let ultimo = performance.now();
      let passoAtual = -2;
      let quadro = 0;
      const tick = (agora: number) => {
        t += ((agora - ultimo) / 1000) * vel.current;
        ultimo = agora;
        const kc = ease(t / T_PAINEL);
        chapa.mesh.position.copy(pChapa).setY(pChapa.y + (1 - kc) * 25);
        let atual = t < T_PAINEL ? -1 : pecas.length;
        let tras = false;
        sarr.forEach((s, i) => {
          const t0 = T_PAINEL + i * T_PECA;
          const k = ease((t - t0) / (T_PECA * 0.8));
          s.mesh.visible = t >= t0;
          s.mesh.position.copy(s.destino).setY(s.destino.y + s.dir * (1 - k) * QUEDA_CM);
          s.mats.forEach((m) => (m.opacity = Math.min(1, k * 1.5)));
          const emCena = t >= t0 && t < t0 + T_PECA;
          (s.mats[0] as MeshStandardMaterial).emissive.setHex(emCena ? COR.destaque : 0);
          (s.mats[0] as MeshStandardMaterial).emissiveIntensity = emCena ? 0.35 : 0;
          if (emCena) atual = i;
          if (emCena && s.dir < 0) tras = true;
        });
        chapa.mats.forEach((m) => (m.opacity = kc * (tras ? 0.45 : 1)));
        if (atual !== passoAtual) {
          passoAtual = atual;
          passo.current(atual);
        }
        controls.update();
        renderer.render(scene, camera);
        quadro = requestAnimationFrame(tick);
      };

      const ajustar = () => {
        const w = el.clientWidth || 600;
        const h = Math.round(Math.min(520, Math.max(300, w * 0.6)));
        renderer.setSize(w, h);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      };
      ajustar();
      const ro = new ResizeObserver(ajustar);
      ro.observe(el);
      quadro = requestAnimationFrame(tick);

      limpar = () => {
        cancelAnimationFrame(quadro);
        ro.disconnect();
        descartar.forEach((d) => d.dispose());
        renderer.domElement.remove();
      };
    })().catch(() => {
      if (vivo) el.textContent = "Visualização 3D indisponível neste navegador (WebGL).";
    });
    return () => {
      vivo = false;
      limpar();
    };
  }, [painel, rodada]);

  return <div ref={host} className={styles.canvas} aria-label="Animação 3D da montagem do painel" />;
}

/** Sub-aba "Montagem painéis" [2026-09-28]: uma aba por painel medido; cada
 * uma anima a montagem daquele painel (chapa cortada + sarrafos um a um). */
export function MontagemPaineis({ grupos }: { grupos: GrupoMateriais[] }) {
  const itens: Item[] = useMemo(
    () =>
      grupos.flatMap((g) =>
        g.disponivel ? (g.paineis ?? []).filter((p) => p.numero != null).map((p) => ({ painel: p, grupo: g.titulo })) : [],
      ),
    [grupos],
  );
  const [sel, setSel] = useState(0);
  const [velocidade, setVelocidade] = useState(1);
  const [rodada, setRodada] = useState(0);
  const [passo, setPasso] = useState(-1);

  if (itens.length === 0) return <p className={styles.nota}>Nenhum painel medido para montar.</p>;
  const { painel, grupo } = itens[Math.min(sel, itens.length - 1)];
  const pecas = painel.montagem ?? [];
  const legenda =
    passo < 0
      ? "Chapa cortada entrando na bancada"
      : passo >= pecas.length
        ? pecas.length ? "Painel montado" : "Painel sem sarrafos no desenho"
        : `Sarrafo ${passo + 1} de ${pecas.length}: ${nomePeca(pecas[passo])} · ${fmt(pecas[passo].comprimento_cm)} cm${pecas[passo].face === "tras" ? " · face de trás" : ""}`;

  return (
    <div className={styles.wrap}>
      <div className={styles.abas} role="tablist" aria-label="Painéis">
        {itens.map((it, i) => (
          <button
            key={it.painel.id ?? i}
            role="tab"
            aria-selected={i === sel}
            className={`${styles.aba} ${i === sel ? styles.abaAtiva : ""}`}
            title={`${it.grupo} · ${it.painel.id ?? ""}`}
            onClick={() => {
              setSel(i);
              setPasso(-1);
            }}
          >
            {it.painel.face ? `${it.painel.face}·` : ""}P{String(it.painel.numero).padStart(2, "0")}
          </button>
        ))}
      </div>

      <div className={styles.cabecalho}>
        <div>
          <strong className={styles.id}>{painel.id ?? `Painel ${painel.numero}`}</strong>
          <span className={styles.sub}>
            {grupo}
            {painel.face ? ` · face ${painel.face}` : ""} · {fmt(painel.largura_cm)} × {fmt(painel.altura_cm)} cm ·{" "}
            {pecas.length} sarrafos
          </span>
        </div>
        <div className={styles.controles}>
          <button className={styles.botao} onClick={() => setRodada((r) => r + 1)}>Montar de novo</button>
          {[0.5, 1, 2].map((v) => (
            <button
              key={v}
              className={`${styles.botao} ${velocidade === v ? styles.botaoAtivo : ""}`}
              aria-pressed={velocidade === v}
              onClick={() => setVelocidade(v)}
            >
              {v.toLocaleString("pt-BR")}×
            </button>
          ))}
        </div>
      </div>

      <div className={styles.palco}>
        <Cena key={`${sel}-${rodada}`} painel={painel} velocidade={velocidade} rodada={rodada} onPasso={setPasso} />
        <p className={styles.legenda} aria-live="polite">{legenda}</p>
      </div>

      {pecas.length > 0 && (
        <ol className={styles.passos}>
          {pecas.map((s, i) => (
            <li key={i} className={i === passo ? styles.passoAtual : i < passo ? styles.passoFeito : ""}>
              {nomePeca(s)} · {fmt(s.comprimento_cm)} cm{s.face === "tras" ? " · face de trás" : ""}
              <span className={styles.sub}> em x {fmt(s.x)} · y {fmt(s.y)}</span>
            </li>
          ))}
        </ol>
      )}
      <p className={styles.nota}>
        Posições medidas no desenho técnico (N3). Arraste para girar, role para aproximar. Cada sarrafo é o par de linhas
        do desenho (ou a linha e a borda do painel); o de pressão (linha tracejada) vai na face de trás.
      </p>
    </div>
  );
}
