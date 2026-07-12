"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DrawingFullscreen } from "@/components/ficha/DrawingFullscreen";
import { FichaHeader } from "@/components/ficha/FichaHeader";
import { FichaTabs, type FichaTabValue } from "@/components/ficha/FichaTabs";
import { PaineisLvTab } from "@/components/ficha/PaineisLvTab";
import { SpecFieldList } from "@/components/ficha/SpecFieldList";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { SvgViewer } from "@/components/ui/SvgViewer";
import { QrCodePanel } from "@/components/ui/QrCodePanel";
import { buscarFicha, urlAbsolutaSvg, type FichaData } from "@/lib/api/ficha";
import { useOnlineStatus } from "@/lib/hooks/useOnlineStatus";
import { cachearUltimoItem } from "@/lib/pwa/cacheUltimoItem";
import { adicionarAoHistorico } from "@/lib/storage/history";
import styles from "./page.module.css";

type EstadoCarregamento = "loading" | "ok" | "not_found" | "network_error";

export default function FichaPage({ params }: { params: { code: string } }) {
  const router = useRouter();
  const online = useOnlineStatus();
  const { code } = params;

  const [estado, setEstado] = useState<EstadoCarregamento>("loading");
  const [ficha, setFicha] = useState<FichaData | null>(null);
  const [aba, setAba] = useState<FichaTabValue>("n1");
  const [svgErro, setSvgErro] = useState(false);
  const [svgTentativa, setSvgTentativa] = useState(0);
  const [fullscreenAberto, setFullscreenAberto] = useState(false);
  const [qrAberto, setQrAberto] = useState(false);
  const [origemAtual, setOrigemAtual] = useState("");

  useEffect(() => {
    setOrigemAtual(window.location.origin);
  }, []);

  useEffect(() => {
    let cancelado = false;

    async function carregar() {
      const resultado = await buscarFicha(code);
      if (cancelado) return;

      if (resultado.status === "ok") {
        setFicha(resultado.data);
        setEstado("ok");
        setSvgErro(false);
        setAba(resultado.data.svg.n1 ? "n1" : resultado.data.svg.n3 ? "n3" : "paineis");
        // Só aqui temos titulo/tipo/obra_rotulo reais — a Tela de Busca
        // (STORY-08) só conhecia {kind, code} via /resolve.
        adicionarAoHistorico({
          code: resultado.data.code,
          titulo: resultado.data.titulo,
          tipo: resultado.data.tipo,
          obra_rotulo: resultado.data.obra_rotulo,
          cached_offline: false,
        });
        // Cacheia como "último item offline" só quando online (dado veio
        // da rede de verdade) — se já estamos offline, o que carregou veio
        // do próprio cache do SW (fallback), recachear seria redundante.
        if (navigator.onLine) {
          cachearUltimoItem(resultado.data);
        }
      } else if (resultado.status === "not_found") {
        setEstado("not_found");
      } else {
        setEstado("network_error");
      }
    }

    carregar();
    return () => {
      cancelado = true;
    };
  }, [code, svgTentativa]);

  function handleVoltar() {
    router.push("/");
  }

  if (estado === "loading") {
    return (
      <main className={styles.container}>
        <div className={styles.skeletonWrapper} role="status" aria-live="polite">
          <Skeleton variant="line" rotulo="carregando ficha" />
          <Skeleton variant="drawing" />
          <Skeleton variant="block" />
          <Skeleton variant="block" />
        </div>
      </main>
    );
  }

  if (estado === "not_found") {
    return (
      <main className={styles.container}>
        <EmptyState
          variante="not-found"
          titulo="Código não encontrado"
          descricao="Verifique se copiou o código completo, ou escaneie o QR da peça."
          cta={{ rotulo: "TENTAR OUTRO", onClick: handleVoltar }}
        />
      </main>
    );
  }

  if (estado === "network_error") {
    return (
      <main className={styles.container}>
        <EmptyState
          variante="offline"
          titulo="Sem conexão"
          descricao="Conecte para consultar este código."
          cta={{ rotulo: "TENTAR DE NOVO", onClick: () => setSvgTentativa((n) => n + 1) }}
        />
      </main>
    );
  }

  if (!ficha) return null;

  const svgUrlAtivo = aba === "n1" ? ficha.svg.n1 : aba === "n3" ? ficha.svg.n3 : null;

  return (
    <main className={styles.container}>
      <FichaHeader
        obraRotulo={ficha.obra_rotulo}
        pavimentoLabel={ficha.pavimento_label}
        tipo={ficha.tipo}
        titulo={ficha.titulo}
        code={ficha.code}
        onVoltar={handleVoltar}
      />

      <div className={styles.corpo}>
        {!online && (
          <p className={styles.offlineBanner} role="status">
            📴 Offline — última versão salva
          </p>
        )}

        <FichaTabs
          temN1={Boolean(ficha.svg.n1)}
          temN3={Boolean(ficha.svg.n3)}
          temLv={ficha.tem_lv}
          aba={aba}
          onSelecionar={(novaAba) => {
            setAba(novaAba);
            setSvgErro(false);
          }}
        />

        {(aba === "n1" || aba === "n3") && (
          <div role="tabpanel">
            {svgUrlAtivo && !svgErro ? (
              <SvgViewer
                status="loaded"
                svgUrl={urlAbsolutaSvg(svgUrlAtivo)}
                descricao={`Desenho ${aba.toUpperCase()} de ${ficha.titulo} — leitura por CAD`}
                onErro={() => setSvgErro(true)}
                onAmpliar={() => setFullscreenAberto(true)}
              />
            ) : (
              <EmptyState
                variante="svg-error"
                titulo="Não foi possível carregar o desenho"
                cta={{ rotulo: "Tentar de novo", onClick: () => setSvgTentativa((n) => n + 1) }}
              />
            )}
          </div>
        )}

        {aba === "paineis" && (
          <div role="tabpanel">
            {ficha.tem_lv ? (
              <PaineisLvTab code={ficha.code} ativo={aba === "paineis"} />
            ) : (
              <EmptyState variante="lv-absent" titulo="Lista de painéis não disponível para este item." />
            )}
          </div>
        )}

        <SpecFieldList campos={ficha.campos} atencao={ficha.atencao} />

        <button
          type="button"
          className={styles.toggleQr}
          onClick={() => setQrAberto((atual) => !atual)}
          aria-expanded={qrAberto}
        >
          {qrAberto ? "Ocultar QR" : "📱 Mostrar QR para imprimir"}
        </button>

        {qrAberto && origemAtual && (
          <QrCodePanel
            url={`${origemAtual}/ficha/${ficha.code}`}
            titulo={ficha.titulo}
            code={ficha.code}
          />
        )}
      </div>

      <DrawingFullscreen
        aberto={fullscreenAberto && (aba === "n1" || aba === "n3")}
        svgUrl={svgUrlAtivo ? urlAbsolutaSvg(svgUrlAtivo) : null}
        descricao={`Desenho ${aba.toUpperCase()} de ${ficha.titulo} — leitura por CAD`}
        nivelAtivo={aba === "n3" ? "n3" : "n1"}
        temN1={Boolean(ficha.svg.n1)}
        temN3={Boolean(ficha.svg.n3)}
        onFechar={() => setFullscreenAberto(false)}
        onAlternarNivel={(nivel) => setAba(nivel)}
      />
    </main>
  );
}
