"use client";

import { useEffect, useState, useMemo } from "react";
import { ArrowLeft, Building2, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ItemListRow } from "@/components/obra/ItemListRow";
import { EmptyState } from "@/components/ui/EmptyState";
import { QrCodePanel } from "@/components/ui/QrCodePanel";
import { buscarPavimento, type PavimentoData } from "@/lib/api/pavimento";
import styles from "./page.module.css";

type EstadoCarregamento = "loading" | "ok" | "not_found" | "network_error";

type TabPrincipal = "pilar" | "viga_fundo" | "viga_lateral" | "laje";
type SubTabModo = "param" | "passa";

export default function PavimentoPage({ params }: { params: { code: string } }) {
  const router = useRouter();
  const { code } = params;

  const [estado, setEstado] = useState<EstadoCarregamento>("loading");
  const [pavimento, setPavimento] = useState<PavimentoData | null>(null);
  const [filtro, setFiltro] = useState("");
  const [qrAberto, setQrAberto] = useState(false);
  const [origemAtual, setOrigemAtual] = useState("");

  const [aba, setAba] = useState<TabPrincipal>("pilar");
  const [subAba, setSubAba] = useState<SubTabModo>("param");

  useEffect(() => {
    setOrigemAtual(window.location.origin);
  }, []);

  useEffect(() => {
    let cancelado = false;

    async function carregar() {
      const resultado = await buscarPavimento(code);
      if (cancelado) return;

      if (resultado.status === "ok") {
        setPavimento(resultado.data);
        setEstado("ok");
        
        // Auto-selecionar primeira aba com itens
        const itens = resultado.data.itens;
        if (itens.length > 0) {
          if (itens.some(i => i.tipo === "pilar")) setAba("pilar");
          else if (itens.some(i => i.tipo === "viga_fundo")) setAba("viga_fundo");
          else if (itens.some(i => i.tipo === "viga_lateral")) setAba("viga_lateral");
          else if (itens.some(i => i.tipo === "laje")) setAba("laje");
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
  }, [code]);

  const itensFiltrados = useMemo(() => {
    if (!pavimento) return [];
    const termo = filtro.trim().toLowerCase();
    
    // 1. Filtrar por aba principal (tipo)
    let filtrados = pavimento.itens.filter(i => i.tipo === aba);

    // 2. Filtrar por subAba (param/passa) se aplicável
    if (aba === "pilar" || aba === "viga_lateral") {
      // Se tiver 'modo', filtra por ele. Senão, mostra todos (fallback p/ retrocompatibilidade)
      const temModo = filtrados.some(i => (i as any).modo);
      if (temModo) {
        filtrados = filtrados.filter(i => (i as any).modo === subAba);
      }
    }

    // 3. Filtrar por texto
    if (termo) {
      filtrados = filtrados.filter(
        (item) =>
          item.titulo.toLowerCase().includes(termo) ||
          item.code.toLowerCase().includes(termo)
      );
    }
    
    return filtrados;
  }, [pavimento, filtro, aba, subAba]);

  function handleVoltar() {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push("/");
    }
  }

  function handleSelecionarItem(itemCode: string) {
    router.push(`/ficha/${itemCode}`);
  }

  if (estado === "loading") {
    return (
      <main className={styles.container}>
        <div className={styles.skeletonContainer}>
          <div className={styles.skeletonHeader} />
          <div className={styles.skeletonBusca} />
          <div className={styles.skeletonItem} />
          <div className={styles.skeletonItem} />
          <div className={styles.skeletonItem} />
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
          cta={{ rotulo: "TENTAR DE NOVO", onClick: handleVoltar }}
        />
      </main>
    );
  }

  if (!pavimento) return null;

  return (
    <main className={styles.container}>
      <header className={styles.header}>
        <button type="button" className={styles.voltar} onClick={handleVoltar} aria-label="Sair">
          <ArrowLeft size={20} aria-hidden="true" /> Sair
        </button>
        <div className={styles.titulos}>
          <span className={styles.pavimentoLabel}>{pavimento.pavimento_label}</span>
          {pavimento.obra_rotulo && (
            pavimento.obra_code ? (
              <Link
                href={`/obra/${pavimento.obra_code}`}
                className={styles.obraRotulo}
                aria-label={`Abrir índice da obra ${pavimento.obra_rotulo}`}
              >
                <Building2 size={14} aria-hidden="true" /> {pavimento.obra_rotulo}
              </Link>
            ) : (
              <span className={styles.obraRotuloSemLink}>
                <Building2 size={14} aria-hidden="true" /> {pavimento.obra_rotulo}
              </span>
            )
          )}
        </div>
      </header>

      <div className={styles.abasPrincipais}>
        <button 
          className={`${styles.abaBtn} ${aba === 'pilar' ? styles.abaAtiva : ''}`}
          onClick={() => setAba('pilar')}
        >
          Pilares
        </button>
        <button 
          className={`${styles.abaBtn} ${aba === 'viga_fundo' ? styles.abaAtiva : ''}`}
          onClick={() => setAba('viga_fundo')}
        >
          Fundos de Vigas
        </button>
        <button 
          className={`${styles.abaBtn} ${aba === 'viga_lateral' ? styles.abaAtiva : ''}`}
          onClick={() => setAba('viga_lateral')}
        >
          Laterais de Vigas
        </button>
        <button 
          className={`${styles.abaBtn} ${aba === 'laje' ? styles.abaAtiva : ''}`}
          onClick={() => setAba('laje')}
        >
          Lajes
        </button>
      </div>

      {(aba === "pilar" || aba === "viga_lateral") && (
        <div className={styles.subAbasContainer}>
          <button 
            className={`${styles.subAbaBtn} ${subAba === 'param' ? styles.subAbaAtiva : ''}`}
            onClick={() => setSubAba('param')}
          >
            Vigas Param nos Pilares
          </button>
          <button 
            className={`${styles.subAbaBtn} ${subAba === 'passa' ? styles.subAbaAtiva : ''}`}
            onClick={() => setSubAba('passa')}
          >
            Vigas Passam pelos Pilares
          </button>
        </div>
      )}

      <div className={styles.buscaContainer}>
        <Search className={styles.iconeBusca} size={18} aria-hidden="true" />
        <input
          type="text"
          className={styles.filtroInput}
          placeholder={`Buscar ${aba.replace('_', ' ')}...`}
          value={filtro}
          onChange={(e) => setFiltro(e.target.value)}
          aria-label={`Buscar item nesta aba`}
        />
      </div>

      <div className={styles.listaContainer}>
        {itensFiltrados.length === 0 && (
          <p className={styles.vazio}>
            Nenhum item publicado para esta seleção.
            {aba === 'viga_lateral' && " (Se a lista estiver vazia, certifique-se de que o portal atualizou a publicação com o campo modo)"}
          </p>
        )}
        {itensFiltrados.map((item) => (
          <ItemListRow key={item.code} item={item} onSelecionar={handleSelecionarItem} />
        ))}
      </div>

      <div className={styles.qrSecao}>
        <button
          type="button"
          className={styles.toggleQr}
          onClick={() => setQrAberto((atual) => !atual)}
          aria-expanded={qrAberto}
        >
          {qrAberto ? "Ocultar QR" : "📷 Mostrar QR para imprimir"}
        </button>

        {qrAberto && origemAtual && (
          <QrCodePanel
            url={`${origemAtual}/pavimento/${code}`}
            titulo={pavimento.pavimento_label}
            code={code}
            rotuloTipo="Código de Pavimento"
            referencia={[pavimento.obra_rotulo, pavimento.pavimento_label].filter(Boolean).join(" › ")}
          />
        )}
      </div>
    </main>
  );
}
