"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Focus,
  Maximize2,
  Minimize2,
  Minus,
  Moon,
  Plus,
  RotateCcw,
  Sun,
} from "lucide-react";
import styles from "./CadViewer.module.css";

interface CadViewerProps {
  svgUrl?: string | null;
  rawSvg?: string | null;
  descricao: string;
  className?: string;
  initialTheme?: "dark" | "blueprint";
  onAmpliar?: () => void;
  onErro?: () => void;
  showFullscreenButton?: boolean;
  isFullscreen?: boolean;
  onToggleFullscreen?: () => void;
}

interface ViewBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function CadViewer({
  svgUrl,
  rawSvg,
  descricao,
  className,
  initialTheme = "dark",
  onAmpliar,
  onErro,
  showFullscreenButton = true,
  isFullscreen = false,
  onToggleFullscreen,
}: CadViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const svgWrapperRef = useRef<HTMLDivElement>(null);

  const [theme, setTheme] = useState<"dark" | "blueprint">(initialTheme);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(false);

  // viewBox State
  const [homeVb, setHomeVb] = useState<ViewBox | null>(null);
  const [currentVb, setCurrentVb] = useState<ViewBox | null>(null);
  const [zoomPercent, setZoomPercent] = useState<number>(100);

  // Drag & Touch interaction refs
  const dragRef = useRef<{
    active: boolean;
    startX: number;
    startY: number;
    startVb: ViewBox;
  }>({
    active: false,
    startX: 0,
    startY: 0,
    startVb: { x: 0, y: 0, w: 0, h: 0 },
  });

  const pinchRef = useRef<{
    active: boolean;
    initialDistance: number;
    initialVb: ViewBox;
    centerSvg: { x: number; y: number };
  }>({
    active: false,
    initialDistance: 0,
    initialVb: { x: 0, y: 0, w: 0, h: 0 },
    centerSvg: { x: 0, y: 0 },
  });

  // 1. Fetch & Prepare SVG
  useEffect(() => {
    let cancelado = false;
    setLoading(true);
    setErro(false);

    async function carregarSvg() {
      try {
        let markup = rawSvg || "";
        if (!markup && svgUrl) {
          const resp = await fetch(svgUrl);
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          markup = await resp.text();
        }

        if (cancelado) return;
        if (!markup) {
          setLoading(false);
          return;
        }

        // Parse and clean SVG
        const parser = new DOMParser();
        const doc = parser.parseFromString(markup, "image/svg+xml");
        const svgEl = doc.querySelector("svg");

        if (!svgEl) {
          throw new Error("SVG element not found in response");
        }

        // Clean potentially insecure nodes
        svgEl.querySelectorAll("script, foreignObject").forEach((n) => n.remove());

        // Extract or compute viewBox
        let vbAttr = svgEl.getAttribute("viewBox");
        if (!vbAttr) {
          const w = parseFloat(svgEl.getAttribute("width") || "1000") || 1000;
          const h = parseFloat(svgEl.getAttribute("height") || "600") || 600;
          vbAttr = `0 0 ${w} ${h}`;
          svgEl.setAttribute("viewBox", vbAttr);
        }

        const parts = vbAttr.split(/[\s,]+/).map(parseFloat);
        const parsedHome: ViewBox = {
          x: parts[0] || 0,
          y: parts[1] || 0,
          w: parts[2] || 1000,
          h: parts[3] || 600,
        };

        // Prepare styles according to CAD standard
        svgEl.setAttribute("preserveAspectRatio", "xMidYMid meet");
        svgEl.removeAttribute("width");
        svgEl.removeAttribute("height");
        svgEl.style.width = "100%";
        svgEl.style.height = "100%";
        svgEl.style.display = "block";
        svgEl.setAttribute("role", "img");
        svgEl.setAttribute("aria-label", descricao);

        // Force non-scaling-stroke for fine vector fidelity on all lines & paths
        svgEl.querySelectorAll("path, line, polygon, polyline, rect, circle").forEach((el) => {
          el.setAttribute("vector-effect", "non-scaling-stroke");
        });

        if (svgWrapperRef.current) {
          svgWrapperRef.current.innerHTML = "";
          svgWrapperRef.current.appendChild(svgEl);
        }

        setHomeVb(parsedHome);
        setCurrentVb(parsedHome);
        setZoomPercent(100);
        setLoading(false);
      } catch {
        if (!cancelado) {
          setLoading(false);
          // Let the probe img handle error propagation if resource fails
        }
      }
    }

    carregarSvg();
    return () => {
      cancelado = true;
    };
  }, [svgUrl, rawSvg, descricao, onErro]);

  // Apply currentVb to the mounted SVG element
  const applyViewBox = useCallback((vb: ViewBox) => {
    const svgEl = svgWrapperRef.current?.querySelector("svg");
    if (!svgEl) return;
    svgEl.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
    setCurrentVb(vb);

    if (homeVb && homeVb.w > 0) {
      const pct = Math.round((homeVb.w / vb.w) * 100);
      setZoomPercent(pct);
    }
  }, [homeVb]);

  // Convert client coordinates to SVG space
  const clientToSvg = useCallback((clientX: number, clientY: number): { x: number; y: number } => {
    const svgEl = svgWrapperRef.current?.querySelector("svg");
    if (!svgEl) return { x: 0, y: 0 };
    const ctm = svgEl.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const pt = svgEl.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const transformed = pt.matrixTransform(ctm.inverse());
    return { x: transformed.x, y: transformed.y };
  }, []);

  // Zoom centered on anchor
  const zoomAtPoint = useCallback(
    (factor: number, anchorClientX?: number, anchorClientY?: number) => {
      if (!currentVb || !homeVb) return;

      const minW = homeVb.w * 0.005; // Maximum zoom-in (~200×)
      const maxW = homeVb.w * 1.5;   // Maximum zoom-out

      let newW = currentVb.w * factor;
      let newH = currentVb.h * factor;

      if (newW < minW) {
        newW = minW;
        newH = homeVb.h * (minW / homeVb.w);
      }
      if (newW > maxW) {
        newW = maxW;
        newH = homeVb.h * (maxW / homeVb.w);
      }

      // If no anchor coordinates provided, use viewport center
      let anchor = { x: currentVb.x + currentVb.w / 2, y: currentVb.y + currentVb.h / 2 };
      if (anchorClientX !== undefined && anchorClientY !== undefined) {
        anchor = clientToSvg(anchorClientX, anchorClientY);
      }

      const ratio = newW / currentVb.w;
      const newX = anchor.x - (anchor.x - currentVb.x) * ratio;
      const newY = anchor.y - (anchor.y - currentVb.y) * ratio;

      applyViewBox({ x: newX, y: newY, w: newW, h: newH });
    },
    [currentVb, homeVb, clientToSvg, applyViewBox]
  );

  // Reset Zoom
  const resetZoom = useCallback(() => {
    if (homeVb) {
      applyViewBox({ ...homeVb });
    }
  }, [homeVb, applyViewBox]);

  // Wheel zoom handler
  useEffect(() => {
    const vp = viewportRef.current;
    if (!vp) return;

    function handleWheel(e: WheelEvent) {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 0.88 : 1.14;
      zoomAtPoint(factor, e.clientX, e.clientY);
    }

    vp.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      vp.removeEventListener("wheel", handleWheel);
    };
  }, [zoomAtPoint]);

  // Mouse Drag Handlers
  function handleMouseDown(e: React.MouseEvent) {
    if (e.button !== 0 && e.button !== 1) return;
    if (!currentVb) return;

    dragRef.current = {
      active: true,
      startX: e.clientX,
      startY: e.clientY,
      startVb: { ...currentVb },
    };

    viewportRef.current?.classList.add(styles.dragging);
    e.preventDefault();
  }

  // Pointer/Touch Drag and Pinch Handlers
  function handleTouchStart(e: React.TouchEvent) {
    if (e.touches.length === 1 && currentVb) {
      dragRef.current = {
        active: true,
        startX: e.touches[0].clientX,
        startY: e.touches[0].clientY,
        startVb: { ...currentVb },
      };
    } else if (e.touches.length === 2 && currentVb) {
      dragRef.current.active = false;
      const t1 = e.touches[0];
      const t2 = e.touches[1];
      const dist = Math.hypot(t1.clientX - t2.clientX, t1.clientY - t2.clientY);
      const midX = (t1.clientX + t2.clientX) / 2;
      const midY = (t1.clientY + t2.clientY) / 2;

      pinchRef.current = {
        active: true,
        initialDistance: dist,
        initialVb: { ...currentVb },
        centerSvg: clientToSvg(midX, midY),
      };
    }
  }

  function handleTouchMove(e: React.TouchEvent) {
    if (pinchRef.current.active && e.touches.length === 2) {
      const t1 = e.touches[0];
      const t2 = e.touches[1];
      const dist = Math.hypot(t1.clientX - t2.clientX, t1.clientY - t2.clientY);
      if (pinchRef.current.initialDistance > 0) {
        const factor = pinchRef.current.initialDistance / dist;
        const initial = pinchRef.current.initialVb;
        const anchor = pinchRef.current.centerSvg;

        const newW = initial.w * factor;
        const newH = initial.h * factor;
        const newX = anchor.x - (anchor.x - initial.x) * factor;
        const newY = anchor.y - (anchor.y - initial.y) * factor;

        applyViewBox({ x: newX, y: newY, w: newW, h: newH });
      }
    } else if (dragRef.current.active && e.touches.length === 1 && currentVb) {
      const touch = e.touches[0];
      const svgEl = svgWrapperRef.current?.querySelector("svg");
      if (!svgEl) return;
      const rect = svgEl.getBoundingClientRect();
      const dx = ((touch.clientX - dragRef.current.startX) / rect.width) * currentVb.w;
      const dy = ((touch.clientY - dragRef.current.startY) / rect.height) * currentVb.h;

      applyViewBox({
        ...currentVb,
        x: dragRef.current.startVb.x - dx,
        y: dragRef.current.startVb.y - dy,
      });
    }
  }

  function handleTouchEnd() {
    dragRef.current.active = false;
    pinchRef.current.active = false;
  }

  useEffect(() => {
    function handleMouseMove(e: MouseEvent) {
      if (!dragRef.current.active || !currentVb) return;
      const svgEl = svgWrapperRef.current?.querySelector("svg");
      if (!svgEl) return;
      const rect = svgEl.getBoundingClientRect();
      const dx = ((e.clientX - dragRef.current.startX) / rect.width) * currentVb.w;
      const dy = ((e.clientY - dragRef.current.startY) / rect.height) * currentVb.h;

      applyViewBox({
        ...currentVb,
        x: dragRef.current.startVb.x - dx,
        y: dragRef.current.startVb.y - dy,
      });
    }

    function handleMouseUp() {
      if (dragRef.current.active) {
        dragRef.current.active = false;
        viewportRef.current?.classList.remove(styles.dragging);
      }
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [currentVb, applyViewBox]);

  return (
    <div
      ref={containerRef}
      className={`${styles.cadContainer} ${theme === "blueprint" ? styles.blueprintTheme : ""} ${className || ""}`}
    >
      <div className={styles.gridPattern} />

      {/* Top Indicators */}
      <div className={styles.topOverlay}>
        <span className={styles.badgeQuality}>CAD Hi-Fi · viewBox</span>
        <span className={styles.instructionHint}>Roda do mouse aproxima · Arraste para mover · Duplo clique reseta</span>
      </div>

      {/* Interactive Viewport */}
      {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
      <div
        ref={viewportRef}
        className={styles.viewport}
        onMouseDown={handleMouseDown}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onDoubleClick={resetZoom}
      >
        {svgUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={svgUrl}
            alt={descricao}
            style={{ position: "absolute", width: 1, height: 1, opacity: 0, pointerEvents: "none" }}
            onError={onErro}
          />
        )}
        {loading && (
          <div className={styles.loadingSpinner}>
            <div className={styles.spinner} />
            <span>Renderizando desenho CAD…</span>
          </div>
        )}

        {erro && !loading && (
          <div className={styles.loadingSpinner}>
            <span>Não foi possível carregar o desenho vetorial.</span>
          </div>
        )}

        <div
          ref={svgWrapperRef}
          className={styles.svgWrapper}
          style={{ opacity: loading || erro ? 0 : 1 }}
        />
      </div>

      {/* Floating HUD Controls */}
      <div className={styles.hudBar}>
        <button
          type="button"
          className={styles.hudButton}
          onClick={() => zoomAtPoint(0.8)}
          title="Aproximar (+)"
          aria-label="Aumentar zoom"
        >
          <Plus size={18} />
        </button>

        <span className={styles.zoomIndicator} aria-label="Nível de zoom">
          {zoomPercent}%
        </span>

        <button
          type="button"
          className={styles.hudButton}
          onClick={() => zoomAtPoint(1.25)}
          title="Afastar (-)"
          aria-label="Diminuir zoom"
        >
          <Minus size={18} />
        </button>

        <button
          type="button"
          className={styles.hudButton}
          onClick={resetZoom}
          title="Ajustar à tela (Duplo clique)"
          aria-label="Ajustar à tela"
        >
          <Focus size={18} />
        </button>

        <button
          type="button"
          className={styles.hudButton}
          onClick={() => setTheme((t) => (t === "dark" ? "blueprint" : "dark"))}
          title={theme === "dark" ? "Fundo Claro / Blueprint" : "Fundo Escuro / CAD Dark"}
          aria-label="Alternar tema do visualizador"
        >
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </button>

        {showFullscreenButton && (
          <button
            type="button"
            className={styles.hudButton}
            onClick={() => {
              if (onToggleFullscreen) {
                onToggleFullscreen();
              } else if (onAmpliar) {
                onAmpliar();
              }
            }}
            title={isFullscreen ? "Sair da Tela Cheia" : "Tela Cheia"}
            aria-label="Tela cheia"
          >
            {isFullscreen ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
          </button>
        )}
      </div>
    </div>
  );
}
