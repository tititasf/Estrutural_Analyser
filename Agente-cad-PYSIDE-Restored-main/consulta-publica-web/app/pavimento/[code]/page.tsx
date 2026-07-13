"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Building2, Search } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ItemListRow } from "@/components/obra/ItemListRow";
import { QrCodePanel } from "@/components/ui/QrCodePanel";
import { buscarPavimento, type PavimentoData } from "@/lib/api/pavimento";
import styles from "./page.module.css";

type EstadoCarregamento = "loading" | "ok" | "not_found" | "network_error";

/** "Ficha do pavimento"/recorte limpo da torre [2026-07-12] — lista os
 * itens de 1 pavimento específico, resolvido direto pelo código próprio
 * do pavimento (sem precisar do código da obra inteira). Mesmo padrão de
 * `/obra/[code]`, mas sem acordeão (só 1 pavimento). */
export default function PavimentoPage({ params }: { params: { code: string } }) {
  const router = useRouter();
  const { code } = params;

  const [estado, setEstado] = useState<EstadoCarregamento>("loading");
  const [pavimento, setPavimento] = useState<PavimentoData | null>(null);
  const [filtro, setFiltro] = useState("");
  const [qrAberto, setQrAberto] = useState(false);
  const [origemAtual, setOrigemAtual] = useState("");

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
    if (!termo) return pavimento.itens;
    return pavimento.itens.filter(
      (item) => item.titulo.toLowerCase().includes(termo) || item.tipo.toLowerCase().includes(termo),
    );
  }, [pavimento, filtro]);

  function handleVoltar() {
    router.push("/");
  }

  function handleSelecionarItem(itemCode: string) {
    router.push(`/ficha/${itemCode}`);
  }

  if (estado === "loading") {
    return (
      <main className={styles.container}>
        <div className={styles.skeletonWrapper} role="status" aria-live="polite">
          <Skeleton variant="line" rotulo="carregando pavimento" />
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
          cta={{ rotulo: "TENTAR DE NOVO", onClick: handleVoltar }}
        />
      </main>
    );
  }

  if (!pavimento) return null;

  return (
    <main className={styles.container}>
      <header className={styles.header}>
        <button type="button" className={styles.voltar} onClick={handleVoltar} aria-label="Voltar">
          <ArrowLeft size={20} aria-hidden="true" /> Voltar
        </button>
        <div className={styles.titulos}>
          <span className={styles.pavimentoLabel}>{pavimento.pavimento_label}</span>
          {pavimento.obra_rotulo && (
            pavimento.obra_code ? (
              <Link
                href={`/obra/${pavimento.obra_code}`}
                className={styles.obraRotulo}
                aria-label={`Abrir índice da obra ${pavimento.obra_rotulo} (código ${pavimento.obra_code})`}
              >
                <Building2 size={14} aria-hidden="true" /> {pavimento.obra_rotulo}
              </Link>
            ) : (
              <span className={styles.obraRotulo}>{pavimento.obra_rotulo}</span>
            )
          )}
        </div>
      </header>

      <div className={styles.filtroWrapper}>
        <Search size={18} aria-hidden="true" className={styles.filtroIcone} />
        <input
          type="text"
          className={styles.filtroInput}
          placeholder="Buscar item..."
          value={filtro}
          onChange={(e) => setFiltro(e.target.value)}
          aria-label="Buscar item neste pavimento"
        />
      </div>

      <div>
        {itensFiltrados.length === 0 && (
          <p className={styles.vazio}>Nenhum item publicado neste pavimento.</p>
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
          {qrAberto ? "Ocultar QR" : "📱 Mostrar QR para imprimir"}
        </button>

        {qrAberto && origemAtual && (
          <QrCodePanel
            url={`${origemAtual}/pavimento/${code}`}
            titulo={pavimento.pavimento_label}
            code={code}
          />
        )}
      </div>
    </main>
  );
}
