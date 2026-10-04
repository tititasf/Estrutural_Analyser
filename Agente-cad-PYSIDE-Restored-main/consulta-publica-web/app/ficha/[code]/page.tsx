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
import { CadViewer } from "@/components/viewer/CadViewer";
import { QrCodePanel } from "@/components/ui/QrCodePanel";
import { buscarFicha, buscarViewsFicha, urlAbsolutaSvg, type FichaData } from "@/lib/api/ficha";
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
  const [svgErro, setSvgErro] = useState(false);
  const [svgTentativa, setSvgTentativa] = useState(0);
  const [viewsData, setViewsData] = useState<import("@/lib/api/ficha").ViewsData | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [subAba, setSubAba] = useState<string>("geral");

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
        
        buscarViewsFicha(code).then((vRes) => {
          if (!cancelado && vRes.status === "ok") {
            setViewsData(vRes.data);
          }
        });

        setEstado("ok");
        setSvgErro(false);
        const inicial = resultado.data.svg.n1 ? "n1" : resultado.data.svg.n3 ? "n3" : "paineis";
        setAba(inicial);
        
        if (resultado.data.tipo === "pilar") {
          setSubAba("cima");
        } else if (resultado.data.tipo === "viga_lateral") {
          setSubAba("para");
        } else {
          setSubAba("geral");
        }

        // SÃ³ aqui temos titulo/tipo/obra_rotulo reais â€” a Tela de Busca
        // (STORY-08) sÃ³ conhecia {kind, code} via /resolve.
        adicionarAoHistorico({
          code: resultado.data.code,
          titulo: resultado.data.titulo,
          tipo: resultado.data.tipo,
          obra_rotulo: resultado.data.obra_rotulo,
          cached_offline: false,
        });
        // Cacheia como "Ãºltimo item offline" sÃ³ quando online (dado veio
        // da rede de verdade) â€” se jÃ¡ estamos offline, o que carregou veio
        // do prÃ³prio cache do SW (fallback), recachear seria redundante.
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
          titulo="CÃ³digo nÃ£o encontrado"
          descricao="Verifique se copiou o cÃ³digo completo, ou escaneie o QR da peÃ§a."
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
          titulo="Sem conexÃ£o"
          descricao="Conecte para consultar este cÃ³digo."
          cta={{ rotulo: "TENTAR DE NOVO", onClick: () => setSvgTentativa((n) => n + 1) }}
        />
      </main>
    );
  }

  if (!ficha) return null;

  const hasRichN3 = viewsData && Object.values(viewsData.views).some((v: any) => v?.available && v?.svg);
  const temN3Real = Boolean(ficha.svg.n3) || Boolean(hasRichN3);

  let viewKey = subAba;
  if (aba === "estrutural") {
    viewKey = subAba === "ativado" ? "estrutural_destaque" : "estrutural_limpo";
  } else if (ficha.tipo === "viga_fundo" || ficha.tipo === "laje") {
    if (subAba === "geral") viewKey = "n3";
  }

  const rawSvgAtivo = (aba === "n3" || aba === "estrutural") && viewsData?.views?.[viewKey]?.svg 
    ? viewsData.views[viewKey].svg 
    : (aba === "estrutural" && viewsData?.views?.["estrutural_limpo"]?.svg ? viewsData.views["estrutural_limpo"].svg : null);

  const svgUrlAtivo = rawSvgAtivo ? null : (aba === "n1" ? ficha.svg.n1 : aba === "n3" ? ficha.svg.n3 : null);

  const classificacao = ficha.campos["ClassificaÃ§Ã£o"] || ficha.campos["Classificacao"] || "";
  const nivel = ficha.campos["NÃ­vel Relativo"] || ficha.campos["NÃ­vel"] || ficha.campos["Laje B #1 â€” NÃ­vel"] || Object.entries(ficha.campos).find(e => e[0].toLowerCase().includes("nÃ­vel") || e[0].toLowerCase().includes("nivel"))?.[1] || "";

  return (
    <main className={styles.container}>
      <FichaHeader
        obraRotulo={ficha.obra_rotulo}
        obraCode={ficha.obra_code}
        pavimentoLabel={ficha.pavimento_label}
        pavimentoCode={ficha.pavimento_code}
        tipo={ficha.tipo}
        titulo={ficha.titulo}
        code={ficha.code}
        onVoltar={handleVoltar}
        classificacao={classificacao}
        nivel={nivel}
      />

      <div className={styles.corpo}>
        {!online && (
          <p className={styles.offlineBanner} role="status">
            ðŸ“´ Offline â€” Ãºltima versÃ£o salva
          </p>
        )}

        <FichaTabs
          temN1={Boolean(ficha.svg.n1)}
          temN3={temN3Real}
          temLv={ficha.tem_lv}
          aba={aba}
          tipo={ficha.tipo}
          subAba={subAba}
          onSelecionar={(novaAba) => {
            setAba(novaAba);
            setSvgErro(false);
            if (novaAba === "estrutural") {
              setSubAba("desativado");
            } else if (novaAba === "n3") {
              if (ficha.tipo === "pilar") setSubAba("cima");
              else if (ficha.tipo === "viga_lateral") setSubAba("para");
              else setSubAba("geral");
            }
          }}
          onSelecionarSubAba={(novaSub) => {
            setSubAba(novaSub);
          }}
        />

        {(aba === "n1" || aba === "n3" || aba === "estrutural") && (
          <div role="tabpanel">
            {(svgUrlAtivo || rawSvgAtivo) && !svgErro ? (
              <CadViewer
                svgUrl={svgUrlAtivo ? urlAbsolutaSvg(svgUrlAtivo) : undefined}
                rawSvg={rawSvgAtivo || undefined}
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
              <EmptyState variante="lv-absent" titulo="Lista de painÃ©is nÃ£o disponÃ­vel para este item." />
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
          {qrAberto ? "Ocultar QR" : "ðŸ“± Mostrar QR para imprimir"}
        </button>

        {qrAberto && origemAtual && (
          <QrCodePanel
            url={`${origemAtual}/ficha/${ficha.code}`}
            titulo={ficha.titulo}
            code={ficha.code}
            rotuloTipo={rotuloCodigoItem(ficha.tipo)}
            referencia={[ficha.obra_rotulo, ficha.pavimento_label, ficha.titulo].filter(Boolean).join(" â€º ")}
          />
        )}
      </div>

      <DrawingFullscreen
        aberto={fullscreenAberto && (aba === "n1" || aba === "n3" || aba === "estrutural")}
        svgUrl={svgUrlAtivo ? urlAbsolutaSvg(svgUrlAtivo) : null}
        
        descricao={`Desenho ${aba.toUpperCase()} de ${ficha.titulo} â€” leitura por CAD`}
        nivelAtivo={aba === "n3" ? "n3" : "n1"}
        temN1={Boolean(ficha.svg.n1)}
        temN3={Boolean(ficha.svg.n3)}
        onFechar={() => setFullscreenAberto(false)}
        onAlternarNivel={(nivel) => setAba(nivel)}
      />
    </main>
  );
}




