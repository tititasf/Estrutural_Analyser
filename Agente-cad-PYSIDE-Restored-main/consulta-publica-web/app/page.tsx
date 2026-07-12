"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Moon, Sun, SunMedium } from "lucide-react";
import { CodeInput } from "@/components/CodeInput";
import { HistoryChip } from "@/components/HistoryChip";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { resolverCodigo } from "@/lib/api/resolve";
import { normalizarCodigo, pareceCodigoValido } from "@/lib/codeFormat";
import { useOnlineStatus } from "@/lib/hooks/useOnlineStatus";
import { useTheme } from "@/lib/theme/ThemeProvider";
import { listarHistorico, removerDoHistorico, type HistoryEntry } from "@/lib/storage/history";
import styles from "./page.module.css";

type TelaEstado =
  | { tipo: "idle" }
  | { tipo: "loading" }
  | { tipo: "not_found" }
  | { tipo: "offline_sem_cache" }
  | { tipo: "blocked"; retryAfterSeconds: number };

// Mensagem ÚNICA para todo cenário de "não encontrado" — princípio de
// design "Silêncio seguro" (front-end-spec §1.2): nunca revelar se um
// código existe-mas-é-de-outro-tipo, foi revogado, ou é só malformado.
const MENSAGEM_NAO_ENCONTRADO = "Código não encontrado";

export default function TelaDeBusca() {
  const router = useRouter();
  const online = useOnlineStatus();
  const { tema, solForte, alternarTema, alternarSolForte } = useTheme();

  const [codigo, setCodigo] = useState("");
  const [estado, setEstado] = useState<TelaEstado>({ tipo: "idle" });
  const [sugerirConsulta, setSugerirConsulta] = useState(false);
  const [mensagemColar, setMensagemColar] = useState<string | null>(null);
  const [historico, setHistorico] = useState<HistoryEntry[]>([]);
  const [contagem, setContagem] = useState(0);

  useEffect(() => {
    setHistorico(listarHistorico());
  }, []);

  useEffect(() => {
    if (estado.tipo !== "blocked") return;
    setContagem(estado.retryAfterSeconds);
    const intervalo = setInterval(() => {
      setContagem((atual) => {
        if (atual <= 1) {
          clearInterval(intervalo);
          setEstado({ tipo: "idle" });
          return 0;
        }
        return atual - 1;
      });
    }, 1000);
    return () => clearInterval(intervalo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estado.tipo]);

  function handleChangeCodigo(valor: string) {
    setCodigo(valor);
    setSugerirConsulta(false);
  }

  async function handleColar() {
    setMensagemColar(null);
    try {
      const texto = await navigator.clipboard.readText();
      const normalizado = normalizarCodigo(texto);
      setCodigo(normalizado);
      // Nunca auto-submete — um paste acidental não pode queimar tentativa
      // de rate-limit (front-end-spec §7, [AUTO-DECISION]).
      setSugerirConsulta(pareceCodigoValido(normalizado));
    } catch {
      setMensagemColar("Não foi possível acessar a área de transferência — cole com o teclado.");
    }
  }

  async function handleConsultar() {
    const alvo = normalizarCodigo(codigo);
    if (!alvo) return;

    if (!online) {
      const noHistorico = historico.find((e) => e.code === alvo && e.cached_offline);
      if (noHistorico) {
        router.push(`/ficha/${alvo}`);
        return;
      }
      setEstado({ tipo: "offline_sem_cache" });
      return;
    }

    setEstado({ tipo: "loading" });
    const resultado = await resolverCodigo(alvo);

    switch (resultado.status) {
      case "ok":
        if (resultado.kind === "obra") {
          router.push(`/obra/${resultado.code}`);
        } else if (resultado.kind === "pavimento") {
          router.push(`/pavimento/${resultado.code}`);
        } else {
          router.push(`/ficha/${resultado.code}`);
        }
        setEstado({ tipo: "idle" });
        return;
      case "not_found":
        setEstado({ tipo: "not_found" });
        return;
      case "blocked":
        setEstado({ tipo: "blocked", retryAfterSeconds: resultado.retryAfterSeconds });
        return;
      case "network_error":
        setEstado({ tipo: "offline_sem_cache" });
        return;
    }
  }

  function handleSelecionarHistorico(code: string) {
    setCodigo(code);
    setEstado({ tipo: "idle" });
    router.push(`/ficha/${code}`);
  }

  function handleRemoverHistorico(code: string) {
    removerDoHistorico(code);
    setHistorico(listarHistorico());
  }

  return (
    <main className={styles.container}>
      <header className={styles.appBar}>
        <span className={styles.appBarTitle}>Consulta de Fôrma</span>
        <div className={styles.appBarAcoes}>
          <StatusBadge online={online} />
          <button
            type="button"
            className={styles.iconButton}
            onClick={alternarSolForte}
            aria-pressed={solForte}
            aria-label="Alternar modo Sol forte"
            title="Sol forte"
          >
            <SunMedium size={20} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={styles.iconButton}
            onClick={alternarTema}
            aria-label={tema === "light" ? "Ativar modo escuro" : "Ativar modo claro"}
            title="Alternar tema"
          >
            {tema === "light" ? <Moon size={20} aria-hidden="true" /> : <Sun size={20} aria-hidden="true" />}
          </button>
        </div>
      </header>

      <section className={styles.hero}>
        <h1 className={styles.titulo}>CONSULTA DE ESPECIFICAÇÃO</h1>
        <p className={styles.instrucao}>Cole ou escaneie o código do item</p>

        <CodeInput
          value={codigo}
          onChange={handleChangeCodigo}
          onSubmit={handleConsultar}
          label="Código do item ou da obra"
        />

        {sugerirConsulta && (
          <p className={styles.sugestao} role="status">
            Código parece válido — Consultar agora?
          </p>
        )}
        {mensagemColar && (
          <p className={styles.avisoColar} role="alert">
            {mensagemColar}
          </p>
        )}

        <div className={styles.botoesSecundarios}>
          <Button variant="secondary" onClick={handleColar}>
            📋 Colar
          </Button>
          <Button variant="secondary" disabled aria-disabled="true">
            📷 Escanear QR
            <span className={styles.emBreve}>Em breve</span>
          </Button>
        </div>

        <Button
          variant="primary"
          onClick={handleConsultar}
          loading={estado.tipo === "loading"}
          disabled={codigo.trim().length === 0}
        >
          🔍 Consultar
        </Button>

        {estado.tipo === "loading" && (
          <p className={styles.statusTexto} role="status" aria-live="polite">
            resolvendo código…
          </p>
        )}

        {estado.tipo === "not_found" && (
          <EmptyState
            variante="not-found"
            titulo={MENSAGEM_NAO_ENCONTRADO}
            descricao="Verifique se copiou o código completo, ou escaneie o QR da peça."
            cta={{ rotulo: "TENTAR OUTRO", onClick: () => setEstado({ tipo: "idle" }) }}
          />
        )}

        {estado.tipo === "offline_sem_cache" && (
          <EmptyState
            variante="offline"
            titulo="Sem conexão"
            descricao="Conecte para consultar este código."
            cta={{ rotulo: "TENTAR DE NOVO", onClick: handleConsultar }}
          />
        )}

        {estado.tipo === "blocked" && (
          <EmptyState variante="blocked" titulo="Muitas tentativas" descricao={`Aguarde ${contagem}s e tente novamente.`} />
        )}
      </section>

      <section className={styles.historicoSecao}>
        <h2 className={styles.historicoTitulo}>Consultados recentemente</h2>
        {historico.length === 0 && <p className={styles.historicoVazio}>Nenhuma consulta ainda.</p>}
        {historico.map((entry) => (
          <HistoryChip
            key={entry.code}
            entry={entry}
            onSelect={handleSelecionarHistorico}
            onRemove={handleRemoverHistorico}
          />
        ))}
      </section>
    </main>
  );
}
