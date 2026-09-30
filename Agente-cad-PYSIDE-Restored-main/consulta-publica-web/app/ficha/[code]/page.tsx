"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Copy, Printer, QrCode, Share2 } from "lucide-react";
import { DrawingFullscreen } from "@/components/ficha/DrawingFullscreen";
import { FichaHeader } from "@/components/ficha/FichaHeader";
import { FichaTabs, type FichaTabValue } from "@/components/ficha/FichaTabs";
import { MateriaisTab, type MateriaisSubAba } from "@/components/ficha/MateriaisTab";
import { PaineisLvTab } from "@/components/ficha/PaineisLvTab";
import { SpecFieldList } from "@/components/ficha/SpecFieldList";
import { CadViewer } from "@/components/viewer/CadViewer";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { QrCodePanel } from "@/components/ui/QrCodePanel";
import { buscarFicha, buscarViewsFicha, tituloFicha, urlAbsolutaSvg, type FichaData } from "@/lib/api/ficha";
import { rotuloCodigoItem } from "@/lib/tipoElementoLabels";
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
  const [subAba, setSubAba] = useState<string>("geral");
  const [subMateriais, setSubMateriais] = useState<MateriaisSubAba>("pecas");
  const [svgErro, setSvgErro] = useState(false);
  const [svgTentativa, setSvgTentativa] = useState(0);
  const [fullscreenAberto, setFullscreenAberto] = useState(false);
  const [qrAberto, setQrAberto] = useState(false);
  const [origemAtual, setOrigemAtual] = useState("");
  const [linkCopiado, setLinkCopiado] = useState(false);

  const [viewsData, setViewsData] = useState<import("@/lib/api/ficha").ViewsData | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  // SVG que vem embutido em /views (Estrutural Limpo e sub-vistas N3). O
  // viewer principal recebe o markup direto; a tela cheia precisa de URL
  // (<img>), então o mesmo markup vira blob: URL.
  const viewKeyAtivo =
    aba === "estrutural"
      ? "estrutural_limpo"
      : (ficha?.tipo === "viga_fundo" || ficha?.tipo === "laje") && subAba === "geral"
        ? "n3"
        : subAba;
  const rawSvgParaBlob: string | null =
    aba === "n3" || aba === "estrutural" ? viewsData?.views?.[viewKeyAtivo]?.svg ?? null : null;

  useEffect(() => {
    if (!rawSvgParaBlob) {
      setBlobUrl(null);
      return;
    }
    const url = URL.createObjectURL(new Blob([rawSvgParaBlob], { type: "image/svg+xml" }));
    setBlobUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [rawSvgParaBlob]);





  useEffect(() => {
    setOrigemAtual(window.location.origin);
  }, []);

  useEffect(() => {
    let cancelado = false;

    async function carregar() {
      setViewsData(null);
      const resultado = await buscarFicha(code);
      if (cancelado) return;

      if (resultado.status === "ok") {
        setFicha(resultado.data);
        
        // Fetch rich views non-blocking
        buscarViewsFicha(code).then((vRes) => {
          if (cancelado) return;
          // Falha em /views vira "sem vistas" (mostra o erro), não
          // carregamento eterno.
          setViewsData(vRes.status === "ok" ? vRes.data : { tipo: resultado.data.tipo, classe: "", views: {} });
        });

        setEstado("ok");
        setSvgErro(false);
        const inicial = "estrutural";
        setAba(inicial);

        // Sub-aba default de acordo com o tipo
        if (resultado.data.tipo === "pilar") {
          setSubAba("cima");
        } else if (resultado.data.tipo === "viga_lateral") {
          setSubAba("para");
        } else {
          setSubAba("geral");
        }

        adicionarAoHistorico({
          code: resultado.data.code,
          titulo: tituloFicha(resultado.data),
          tipo: resultado.data.tipo,
          obra_rotulo: resultado.data.obra_rotulo,
          cached_offline: false,
        });

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

  async function handleCompartilhar() {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({
          title: `Ficha ${(ficha && tituloFicha(ficha)) || "CAD"}`,
          text: `Consulta técnica da peça ${(ficha && tituloFicha(ficha))} (${code})`,
          url,
        });
      } catch {
        // Usuário cancelou
      }
    } else {
      try {
        await navigator.clipboard.writeText(url);
        setLinkCopiado(true);
        setTimeout(() => setLinkCopiado(false), 2000);
      } catch {
        // Ignora se não houver permissão
      }
    }
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

  // Se viewsData estiver carregado, verifica se há algo no N3
  const hasRichN3 = viewsData && Object.values(viewsData.views).some((v: any) => v?.available && v?.svg);
  const temN3Real = Boolean(ficha.svg.n3) || Boolean(hasRichN3);

  const rawSvgAtivo = rawSvgParaBlob;
  const svgUrlAtivo = rawSvgAtivo ? blobUrl : (aba === "n1" ? ficha.svg.n1 : aba === "n3" ? ficha.svg.n3 : null);
  const isBlob = !!rawSvgAtivo && !!blobUrl;
  // Estrutural Limpo só existe via /views: enquanto ele não chega, é
  // carregamento, não erro.
  const aguardandoViews = aba === "estrutural" && viewsData === null;
  // Materiais usa a largura toda (a Especificação não entra na lista).
  const semLateral = aba === "materiais" && !qrAberto;

  return (
    <main className={styles.container}>
      {!online && (
        <p className={styles.offlineBanner} role="status">
          📴 Offline — última versão salva
        </p>
      )}

      {/* Identificação da peça (obra › pavimento › item + código) acima do
          visualizador, em qualquer largura de tela. */}
      <FichaHeader
        obraRotulo={ficha.obra_rotulo}
        pavimentoLabel={ficha.pavimento_label}
        pavimentoCode={ficha.pavimento_code}
        tipo={ficha.tipo}
        titulo={tituloFicha(ficha)}
        code={ficha.code}
        onVoltar={handleVoltar}
        acoes={
          <>
            <button
              type="button"
              className={styles.btnAcao}
              onClick={handleCompartilhar}
              title="Compartilhar ou copiar link direto"
            >
              {linkCopiado ? <Check size={15} /> : <Share2 size={15} />}
              <span>{linkCopiado ? "Link copiado" : "Compartilhar"}</span>
            </button>
            <button
              type="button"
              className={styles.btnAcao}
              onClick={() => setQrAberto((atual) => !atual)}
              title="QR Code para imprimir"
              aria-expanded={qrAberto}
            >
              <QrCode size={15} />
              <span>{qrAberto ? "Ocultar QR" : "QR Code"}</span>
            </button>
          </>
        }
      />

      {/* Grid Principal Adaptativo (Split View Desktop) */}
      <div className={`${styles.splitGrid} ${semLateral ? styles.splitGridUnica : ""}`}>
        {/* Coluna Esquerda: Visualizador CAD e Abas Técnicas */}
        <section className={styles.viewerColumn} aria-label="Visualizador do desenho técnico">
          <FichaTabs
            temN1={Boolean(ficha.svg.n1)}
            temN3={temN3Real}
            temLv={ficha.tem_lv}
            aba={aba}
            tipo={ficha.tipo}
            modo={ficha.modo}
            subAba={subAba}
            onSelecionar={(novaAba) => {
              setAba(novaAba);
              setSvgErro(false);
            }}
            onSelecionarSubAba={(novaSub) => {
              setSubAba(novaSub);
            }}
            subMateriais={subMateriais}
            onSelecionarMateriais={setSubMateriais}
          />

          {(aba === "estrutural" || aba === "n1" || aba === "n3") && (
            <div role="tabpanel" className={styles.viewerCard}>
              {aguardandoViews ? (
                <Skeleton variant="drawing" rotulo="carregando desenho" />
              ) : (rawSvgAtivo || svgUrlAtivo) && !svgErro ? (
                <CadViewer
                  rawSvg={rawSvgAtivo}
                  svgUrl={rawSvgAtivo ? null : urlAbsolutaSvg(svgUrlAtivo!)}
                  descricao={`Desenho ${aba.toUpperCase()} de ${tituloFicha(ficha)} — leitura por CAD`}
                  onErro={() => setSvgErro(true)}
                  onAmpliar={() => setFullscreenAberto(true)}
                />
              ) : (
                <EmptyState
                  variante="svg-error"
                  titulo="Não foi possível carregar o desenho"
                  descricao={
                    aba === "n3"
                      ? "A fôrma N3 detalhada desta peça está em estágio de cálculo pelo robô STOG."
                      : "O desenho CAD original não pôde ser renderizado."
                  }
                  cta={{ rotulo: "Recarregar desenho", onClick: () => setSvgTentativa((n) => n + 1) }}
                />
              )}
            </div>
          )}

          {aba === "materiais" && (
            <div role="tabpanel" className={styles.viewerCard} style={{ overflowY: "auto", height: "auto" }}>
              <MateriaisTab code={ficha.code} ativo={aba === "materiais"} sub={subMateriais} />
            </div>
          )}

          {aba === "paineis" && (
            <div role="tabpanel" className={styles.viewerCard} style={{ overflowY: "auto", height: "auto" }}>
              {ficha.tem_lv ? (
                <PaineisLvTab code={ficha.code} ativo={aba === "paineis"} />
              ) : (
                <EmptyState variante="lv-absent" titulo="Lista de painéis não disponível para este item." />
              )}
            </div>
          )}
        </section>

        {/* Coluna Direita: Cabeçalho, Metadados e Ações */}
        {!semLateral && (
        <aside className={styles.sidebarColumn} aria-label="Especificação e Ações">
          {aba !== "materiais" && <SpecFieldList campos={ficha.campos} atencao={ficha.atencao} />}

          {qrAberto && origemAtual && (
            <QrCodePanel
              url={`${origemAtual}/ficha/${ficha.code}`}
              titulo={tituloFicha(ficha)}
              code={ficha.code}
              rotuloTipo={rotuloCodigoItem(ficha.tipo)}
              referencia={[ficha.obra_rotulo, ficha.pavimento_label, tituloFicha(ficha)].filter(Boolean).join(" › ")}
            />
          )}
        </aside>
        )}
      </div>

      <DrawingFullscreen
        aberto={fullscreenAberto && (aba === "estrutural" || aba === "n1" || aba === "n3")}
        svgUrl={svgUrlAtivo ? (isBlob ? svgUrlAtivo : urlAbsolutaSvg(svgUrlAtivo)) : null}
        descricao={`Desenho ${aba.toUpperCase()} de ${tituloFicha(ficha)} — leitura por CAD`}
        nivelAtivo={aba === "n3" ? "n3" : "n1"}
        temN1={Boolean(ficha.svg.n1)}
        temN3={temN3Real}
        onFechar={() => setFullscreenAberto(false)}
        onAlternarNivel={(nivel) => setAba(nivel)}
      />
    </main>
  );
}
