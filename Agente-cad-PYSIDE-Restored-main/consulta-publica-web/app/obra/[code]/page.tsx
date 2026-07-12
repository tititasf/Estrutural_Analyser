"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Search } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { PavimentoAccordion } from "@/components/obra/PavimentoAccordion";
import { buscarIndiceObra, type ObraData } from "@/lib/api/obra";
import styles from "./page.module.css";

type EstadoCarregamento = "loading" | "ok" | "not_found" | "network_error";

export default function IndiceObraPage({ params }: { params: { code: string } }) {
  const router = useRouter();
  const { code } = params;

  const [estado, setEstado] = useState<EstadoCarregamento>("loading");
  const [obra, setObra] = useState<ObraData | null>(null);
  const [filtro, setFiltro] = useState("");
  const [expandidos, setExpandidos] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelado = false;

    async function carregar() {
      const resultado = await buscarIndiceObra(code);
      if (cancelado) return;

      if (resultado.status === "ok") {
        setObra(resultado.data);
        setEstado("ok");
        // 1º pavimento com itens começa expandido, por conveniência.
        const primeiroComItens = resultado.data.pavimentos.find((p) => p.itens.length > 0);
        if (primeiroComItens) {
          setExpandidos(new Set([primeiroComItens.pavimento_label]));
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

  const pavimentosFiltrados = useMemo(() => {
    if (!obra) return [];
    const termo = filtro.trim().toLowerCase();
    if (!termo) return obra.pavimentos;
    // Filtro client-side por título/tipo — sem nova requisição (AC8).
    return obra.pavimentos.map((pav) => ({
      ...pav,
      itens: pav.itens.filter(
        (item) => item.titulo.toLowerCase().includes(termo) || item.tipo.toLowerCase().includes(termo),
      ),
    }));
  }, [obra, filtro]);

  function handleVoltar() {
    router.push("/");
  }

  function handleSelecionarItem(itemCode: string) {
    router.push(`/ficha/${itemCode}`);
  }

  function alternarPavimento(rotulo: string) {
    setExpandidos((atual) => {
      const novo = new Set(atual);
      if (novo.has(rotulo)) {
        novo.delete(rotulo);
      } else {
        novo.add(rotulo);
      }
      return novo;
    });
  }

  if (estado === "loading") {
    return (
      <main className={styles.container}>
        <div className={styles.skeletonWrapper} role="status" aria-live="polite">
          <Skeleton variant="line" rotulo="carregando obra" />
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

  if (!obra) return null;

  return (
    <main className={styles.container}>
      <header className={styles.header}>
        <button type="button" className={styles.voltar} onClick={handleVoltar} aria-label="Voltar">
          <ArrowLeft size={20} aria-hidden="true" /> Voltar
        </button>
        <span className={styles.obraRotulo}>{obra.obra_rotulo}</span>
      </header>

      <div className={styles.filtroWrapper}>
        <Search size={18} aria-hidden="true" className={styles.filtroIcone} />
        <input
          type="text"
          className={styles.filtroInput}
          placeholder="Buscar item..."
          value={filtro}
          onChange={(e) => setFiltro(e.target.value)}
          aria-label="Buscar item nesta obra"
        />
      </div>

      <div>
        {pavimentosFiltrados.map((pav) => (
          <PavimentoAccordion
            key={pav.pavimento_label}
            pavimento={pav}
            expandido={expandidos.has(pav.pavimento_label) || Boolean(filtro.trim())}
            onAlternar={() => alternarPavimento(pav.pavimento_label)}
            onSelecionarItem={handleSelecionarItem}
          />
        ))}
      </div>
    </main>
  );
}
