"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Moon,
  Sun,
  SunMedium,
  Layers,
  ShieldCheck,
  Cpu,
  Building2,
  CheckCircle2,
  Phone,
  Mail,
  Clock,
  MessageSquare,
  Send,
  ArrowRight,
  ExternalLink,
  Box,
  Sparkles,
  HardHat,
  FileText,
  ChevronRight,
  Check,
  QrCode,
  Ruler,
  Compass,
  Search,
} from "lucide-react";
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

const MENSAGEM_NAO_ENCONTRADO = "Código não encontrado";

const EXEMPLOS_CODIGO = [
  { codigo: "6gMvsbSEsD", rotulo: "Pilar P1 (Exemplo)", desc: "Seções N1 e N3 Cima/ABCD" },
];

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

  // Form de contato
  const [formContato, setFormContato] = useState({
    nome: "",
    obra: "",
    contato: "",
    mensagem: "",
  });
  const [contatoEnviado, setContatoEnviado] = useState(false);

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

  function handleEnviarContato(e: React.FormEvent) {
    e.preventDefault();
    if (!formContato.nome.trim() || !formContato.mensagem.trim()) return;
    setContatoEnviado(true);
    setFormContato({ nome: "", obra: "", contato: "", mensagem: "" });
    setTimeout(() => setContatoEnviado(false), 6000);
  }

  return (
    <div className={styles.pageWrapper}>
      {/* Top Navbar */}
      <header className={styles.appBar}>
        <div className={styles.appBarBrand}>
          <div className={styles.brandIconBox}>
            <Compass size={22} className={styles.brandIcon} aria-hidden="true" />
          </div>
          <div className={styles.brandInfo}>
            <span className={styles.appBarTitle}>CAD-ANALYZER</span>
            <span className={styles.appBarSubtitle}>Consulta de Fôrmas</span>
          </div>
        </div>

        <nav className={styles.navLinks} aria-label="Navegação rápida">
          <a href="#consulta" className={styles.navLink}>
            Consulta
          </a>
          <a href="#plataforma" className={styles.navLink}>
            Plataforma
          </a>
          <a href="#classes" className={styles.navLink}>
            Classes
          </a>
          <a href="#qualidade" className={styles.navLink}>
            Engenharia
          </a>
          <a href="#contato" className={styles.navLink}>
            Suporte
          </a>
        </nav>

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

      {/* Hero Section */}
      <section className={styles.heroSection} id="consulta">
        <div className={styles.heroContainer}>
          <div className={styles.heroTextContent}>
            <div className={styles.heroBadge}>
              <Sparkles size={14} aria-hidden="true" />
              <span>SISTEMA DE INTELIGÊNCIA ESTRUTURAL & FÔRMAS • v2.4</span>
            </div>
            <h1 className={styles.heroHeadline}>
              CONSULTA DE ESPECIFICAÇÃO
              <span className={styles.heroHeadlineHighlight}> & FÔRMAS TÉCNICAS</span>
            </h1>
            <p className={styles.heroDescription}>
              Visualize instantaneamente desenhos vetoriais de precisão milimétrica, especificações
              estruturais e desdobramentos de fôrma (Pilares, Vigas e Lajes) com conformidade ABNT NBR 6118 / 15696.
            </p>

            <div className={styles.heroPillGroup}>
              <span className={styles.heroPill}>
                <CheckCircle2 size={15} aria-hidden="true" /> Motor Vetorial SVG Nativo
              </span>
              <span className={styles.heroPill}>
                <CheckCircle2 size={15} aria-hidden="true" /> Validação Arete N1 a N4
              </span>
              <span className={styles.heroPill}>
                <CheckCircle2 size={15} aria-hidden="true" /> Rastreabilidade QR Code
              </span>
              <span className={styles.heroPill}>
                <CheckCircle2 size={15} aria-hidden="true" /> PWA Canteiro Offline
              </span>
            </div>
          </div>

          {/* Search Card / Console */}
          <div className={styles.searchCard}>
            <div className={styles.searchCardHeader}>
              <div className={styles.searchCardTitleGroup}>
                <h2 className={styles.searchCardTitle}>Localizar Elemento</h2>
                <p className={styles.instrucao}>Cole ou escaneie o código do item</p>
              </div>
              <span className={styles.secureBadge}>
                <ShieldCheck size={14} aria-hidden="true" /> Privado por Código
              </span>
            </div>

            <div className={styles.searchCardBody}>
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
                <EmptyState
                  variante="blocked"
                  titulo="Muitas tentativas"
                  descricao={`Aguarde ${contagem}s e tente novamente.`}
                />
              )}

              {/* Exemplos Rápidos */}
              <div className={styles.exemplosContainer}>
                <span className={styles.exemplosTitulo}>Código de demonstração:</span>
                {EXEMPLOS_CODIGO.map((ex) => (
                  <button
                    key={ex.codigo}
                    type="button"
                    className={styles.exemploBtn}
                    onClick={() => {
                      setCodigo(ex.codigo);
                      setSugerirConsulta(true);
                    }}
                    title={ex.desc}
                  >
                    <code>{ex.codigo}</code>
                    <span className={styles.exemploRotulo}>{ex.rotulo}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Histórico Recente */}
      <section className={styles.historicoSecao} aria-label="Histórico de consultas">
        <div className={styles.historicoHeader}>
          <Clock size={16} aria-hidden="true" />
          <h2 className={styles.historicoTitulo}>Consultados recentemente</h2>
        </div>
        {historico.length === 0 ? (
          <p className={styles.historicoVazio}>Nenhuma consulta ainda.</p>
        ) : (
          <div className={styles.historicoChips}>
            {historico.map((entry) => (
              <HistoryChip
                key={entry.code}
                entry={entry}
                onSelect={handleSelecionarHistorico}
                onRemove={handleRemoverHistorico}
              />
            ))}
          </div>
        )}
      </section>

      {/* Plataforma & Recursos */}
      <section className={styles.featuresSection} id="plataforma">
        <div className={styles.sectionHeader}>
          <span className={styles.sectionCategory}>TECNOLOGIA AVANÇADA</span>
          <h2 className={styles.sectionTitle}>Motor de Visualização e Inteligência Estrutural</h2>
          <p className={styles.sectionDescription}>
            Construído para engenheiros de estruturas, técnicos de fôrma e mestres de obras que exigem
            precisão absoluta e velocidade no canteiro.
          </p>
        </div>

        <div className={styles.featuresGrid}>
          <div className={styles.featureCard}>
            <div className={styles.featureIconBox}>
              <Ruler size={24} className={styles.featureIcon} />
            </div>
            <h3 className={styles.featureTitle}>Motor Vetorial viewBox</h3>
            <p className={styles.featureText}>
              Renderização SVG contínua sem pixelização ou borrão de linhas. Navegação dinâmica com
              zoom ancorado no cursor e suporte completo a toque e gestos.
            </p>
            <ul className={styles.featureCheckList}>
              <li><Check size={14} /> Traço com espessura proporcional (non-scaling-stroke)</li>
              <li><Check size={14} /> Alternância de fundo Studio Dark e Blueprint</li>
              <li><Check size={14} /> Modo Tela Cheia imersivo para conferência</li>
            </ul>
          </div>

          <div className={styles.featureCard}>
            <div className={styles.featureIconBox}>
              <Layers size={24} className={styles.featureIcon} />
            </div>
            <h3 className={styles.featureTitle}>Hierarquia Arete (N1 a N4)</h3>
            <p className={styles.featureText}>
              Navegação estruturada entre o contexto global da peça (N1) e seus desdobramentos de fôrma
              (N3) com abas especializadas para cada face geométrica.
            </p>
            <ul className={styles.featureCheckList}>
              <li><Check size={14} /> Pilares: Cima, ABCD Para, ABCD Passa e Grades</li>
              <li><Check size={14} /> Vigas: Fundos e Laterais de escoramento</li>
              <li><Check size={14} /> Lajes: Fôrma N3 e Modulação de Painéis N4</li>
            </ul>
          </div>

          <div className={styles.featureCard}>
            <div className={styles.featureIconBox}>
              <QrCode size={24} className={styles.featureIcon} />
            </div>
            <h3 className={styles.featureTitle}>Rastreabilidade em Campo</h3>
            <p className={styles.featureText}>
              Identificação unívoca por item com QR codes otimizados para impressão térmica e A4.
              Consulta em segundos diretamente na fôrma montada.
            </p>
            <ul className={styles.featureCheckList}>
              <li><Check size={14} /> Cache offline automático de itens consultados (PWA)</li>
              <li><Check size={14} /> Modal de impressão rápida para etiquetagem</li>
              <li><Check size={14} /> Compartilhamento direto de links de engenharia</li>
            </ul>
          </div>

          <div className={styles.featureCard}>
            <div className={styles.featureIconBox}>
              <ShieldCheck size={24} className={styles.featureIcon} />
            </div>
            <h3 className={styles.featureTitle}>Conformidade & Segurança</h3>
            <p className={styles.featureText}>
              Validação estrita de cotas e tolerâncias conforme as normas NBR 6118 (Concreto Armado) e
              NBR 15696 (Fôrmas e Escoramentos).
            </p>
            <ul className={styles.featureCheckList}>
              <li><Check size={14} /> Princípio de silêncio seguro contra enumeração</li>
              <li><Check size={14} /> Sanitização estrita de dicionários técnicos</li>
              <li><Check size={14} /> Taxa de rate-limit e proteção anti-varredura</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Classes Estruturais */}
      <section className={styles.classesSection} id="classes">
        <div className={styles.sectionHeader}>
          <span className={styles.sectionCategory}>CLASSES ESTRUTURAIS</span>
          <h2 className={styles.sectionTitle}>Detalhamento Especializado por Elemento</h2>
          <p className={styles.sectionDescription}>
            Cada elemento estrutural possui visão técnica adaptada às suas características de montagem.
          </p>
        </div>

        <div className={styles.classesGrid}>
          <div className={styles.classCard}>
            <div className={styles.classBadgePilar}>PILARES (P)</div>
            <h3 className={styles.classCardTitle}>Pilares de Concreto</h3>
            <p className={styles.classCardText}>
              Detalhamento de topo de pilar, alinhamento de sarrafos e seções desdobradas ABCD para montagem
              dos painéis das 4 faces.
            </p>
            <div className={styles.classCardTags}>
              <span>Vista Cima</span>
              <span>ABCD Para</span>
              <span>ABCD Passa</span>
              <span>Grades N3</span>
            </div>
          </div>

          <div className={styles.classCard}>
            <div className={styles.classBadgeViga}>VIGAS (FV / LV)</div>
            <h3 className={styles.classCardTitle}>Vigas & Travessas</h3>
            <p className={styles.classCardText}>
              Separação precisa entre Fundos de Viga (FV) para suporte de escoramento e Laterais de Viga
              (LV Para / Passa) para fechamento lateral.
            </p>
            <div className={styles.classCardTags}>
              <span>Fundo de Viga (FV)</span>
              <span>Lateral Para</span>
              <span>Lateral Passa</span>
              <span>Painéis Modulados</span>
            </div>
          </div>

          <div className={styles.classCard}>
            <div className={styles.classBadgeLaje}>LAJES (L)</div>
            <h3 className={styles.classCardTitle}>Lajes & Painéis</h3>
            <p className={styles.classCardText}>
              Mapeamento de fôrma de laje, marcação de rebaixos, aberturas para instalações hidráulicas e
              quantitativo de compensados.
            </p>
            <div className={styles.classCardTags}>
              <span>Fôrma N3</span>
              <span>Painéis de Compensado</span>
              <span>Rebaixos & Cotas</span>
              <span>Vigas de Apoio</span>
            </div>
          </div>
        </div>
      </section>

      {/* Pipeline Arete */}
      <section className={styles.pipelineSection} id="qualidade">
        <div className={styles.sectionHeader}>
          <span className={styles.sectionCategory}>PIPELINE ARETE</span>
          <h2 className={styles.sectionTitle}>Do Arquivo CAD ao Canteiro de Obras</h2>
          <p className={styles.sectionDescription}>
            Processamento automatizado ponta a ponta com gates de qualidade rigorosos.
          </p>
        </div>

        <div className={styles.pipelineSteps}>
          <div className={styles.pipelineStep}>
            <div className={styles.stepNumber}>01</div>
            <h4 className={styles.stepTitle}>Ingestão DXF</h4>
            <p className={styles.stepDesc}>Extração de camadas geométricas, textos e cotas do projeto estrutural.</p>
          </div>
          <div className={styles.pipelineStepArrow} aria-hidden="true">
            <ArrowRight size={20} />
          </div>

          <div className={styles.pipelineStep}>
            <div className={styles.stepNumber}>02</div>
            <h4 className={styles.stepTitle}>Interpretação IA</h4>
            <p className={styles.stepDesc}>Classificação semântica de elementos e agrupamento de faces e seções.</p>
          </div>
          <div className={styles.pipelineStepArrow} aria-hidden="true">
            <ArrowRight size={20} />
          </div>

          <div className={styles.pipelineStep}>
            <div className={styles.stepNumber}>03</div>
            <h4 className={styles.stepTitle}>Validação Arete</h4>
            <p className={styles.stepDesc}>Checagem dimensional, tolerâncias de fôrma e conformidade normativa.</p>
          </div>
          <div className={styles.pipelineStepArrow} aria-hidden="true">
            <ArrowRight size={20} />
          </div>

          <div className={styles.pipelineStep}>
            <div className={styles.stepNumber}>04</div>
            <h4 className={styles.stepTitle}>Ficha & QR</h4>
            <p className={styles.stepDesc}>Geração de código único criptográfico e visualização vetorial instantânea.</p>
          </div>
        </div>
      </section>

      {/* Contato & Suporte Técnico */}
      <section className={styles.contatoSection} id="contato">
        <div className={styles.sectionHeader}>
          <span className={styles.sectionCategory}>SUPORTE & ATENDIMENTO</span>
          <h2 className={styles.sectionTitle}>Suporte de Engenharia & Contato</h2>
          <p className={styles.sectionDescription}>
            Nossa equipe técnica apoia o seu canteiro de obras e equipe de projetos.
          </p>
        </div>

        <div className={styles.contatoGrid}>
          {/* Informações de Contato */}
          <div className={styles.contatoInfoCard}>
            <h3 className={styles.contatoInfoTitle}>Canais de Atendimento</h3>
            <p className={styles.contatoInfoSub}>
              Para esclarecimento de dúvidas sobre desdobramento de peças, liberação de novos códigos ou
              integração de obras completas:
            </p>

            <div className={styles.contatoItens}>
              <div className={styles.contatoItem}>
                <div className={styles.contatoIconBox}>
                  <Phone size={20} />
                </div>
                <div>
                  <h4 className={styles.contatoItemTitulo}>Plantão de Obras & Concretagem</h4>
                  <p className={styles.contatoItemValor}>Segunda a Sexta: 07h às 18h</p>
                  <a
                    href="https://wa.me/5511999999999"
                    target="_blank"
                    rel="noreferrer"
                    className={styles.contatoLink}
                  >
                    Atendimento via WhatsApp <ExternalLink size={14} />
                  </a>
                </div>
              </div>

              <div className={styles.contatoItem}>
                <div className={styles.contatoIconBox}>
                  <Mail size={20} />
                </div>
                <div>
                  <h4 className={styles.contatoItemTitulo}>E-mail de Engenharia</h4>
                  <p className={styles.contatoItemValor}>suporte@cad-analyzer.com.br</p>
                  <a href="mailto:suporte@cad-analyzer.com.br" className={styles.contatoLink}>
                    Enviar mensagem técnica <ArrowRight size={14} />
                  </a>
                </div>
              </div>

              <div className={styles.contatoItem}>
                <div className={styles.contatoIconBox}>
                  <HardHat size={20} />
                </div>
                <div>
                  <h4 className={styles.contatoItemTitulo}>Central do Portal CAD-ANALYZER</h4>
                  <p className={styles.contatoItemValor}>Acesso restrito para engenheiros credenciados</p>
                  <span className={styles.portalTag}>Ambiente de Processamento Central</span>
                </div>
              </div>
            </div>
          </div>

          {/* Formulário de Suporte Rápido */}
          <div className={styles.contatoFormCard}>
            <h3 className={styles.contatoFormTitle}>Solicitar Suporte Técnico</h3>
            <p className={styles.contatoFormSub}>
              Envie sua dúvida ou solicitação referente a itens de fôrma:
            </p>

            {contatoEnviado ? (
              <div className={styles.contatoSucessoBox} role="status">
                <CheckCircle2 size={32} className={styles.contatoSucessoIcon} />
                <h4>Mensagem Enviada!</h4>
                <p>Nossa equipe de engenharia responderá o seu contato com prioridade.</p>
              </div>
            ) : (
              <form onSubmit={handleEnviarContato} className={styles.contatoForm}>
                <div className={styles.formGroup}>
                  <label htmlFor="form-nome" className={styles.formLabel}>
                    Nome Completo
                  </label>
                  <input
                    id="form-nome"
                    type="text"
                    required
                    value={formContato.nome}
                    onChange={(e) => setFormContato({ ...formContato, nome: e.target.value })}
                    placeholder="Engenheiro(a) ou Encarregado(a)"
                    className={styles.formInput}
                  />
                </div>

                <div className={styles.formRow}>
                  <div className={styles.formGroup}>
                    <label htmlFor="form-obra" className={styles.formLabel}>
                      Obra / Construtora
                    </label>
                    <input
                      id="form-obra"
                      type="text"
                      value={formContato.obra}
                      onChange={(e) => setFormContato({ ...formContato, obra: e.target.value })}
                      placeholder="Ex: Edifício Horizonte"
                      className={styles.formInput}
                    />
                  </div>

                  <div className={styles.formGroup}>
                    <label htmlFor="form-contato" className={styles.formLabel}>
                      E-mail ou Telefone
                    </label>
                    <input
                      id="form-contato"
                      type="text"
                      required
                      value={formContato.contato}
                      onChange={(e) => setFormContato({ ...formContato, contato: e.target.value })}
                      placeholder="seu.email@exemplo.com"
                      className={styles.formInput}
                    />
                  </div>
                </div>

                <div className={styles.formGroup}>
                  <label htmlFor="form-mensagem" className={styles.formLabel}>
                    Mensagem / Dúvida do Item
                  </label>
                  <textarea
                    id="form-mensagem"
                    rows={4}
                    required
                    value={formContato.mensagem}
                    onChange={(e) => setFormContato({ ...formContato, mensagem: e.target.value })}
                    placeholder="Descreva o elemento, código do item ou a dúvida de montagem..."
                    className={styles.formTextarea}
                  />
                </div>

                <button type="submit" className={styles.submitBtn}>
                  <Send size={16} /> Enviar Mensagem Técnica
                </button>
              </form>
            )}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className={styles.footer}>
        <div className={styles.footerContainer}>
          <div className={styles.footerColBrand}>
            <div className={styles.footerBrand}>
              <Compass size={20} aria-hidden="true" />
              <span>CAD-ANALYZER</span>
            </div>
            <p className={styles.footerDesc}>
              Plataforma de inteligência geométrica e consulta pública de especificações de fôrma para
              concreto armado.
            </p>
            <span className={styles.footerNormas}>
              Conforme normas ABNT NBR 6118:2023 & NBR 15696:2020.
            </span>
          </div>

          <div className={styles.footerColLinks}>
            <span className={styles.footerSectionTitle}>Navegação</span>
            <a href="#consulta">Consulta de Fôrmas</a>
            <a href="#plataforma">Motor de Visualização</a>
            <a href="#classes">Classes Estruturais</a>
            <a href="#qualidade">Pipeline Arete</a>
            <a href="#contato">Suporte de Engenharia</a>
          </div>

          <div className={styles.footerColLegal}>
            <span className={styles.footerSectionTitle}>Segurança & Rastreabilidade</span>
            <p className={styles.footerTextMuted}>
              Acesso protegido por código unívoco. Não indexável por mecanismos de busca públicos.
            </p>
            <div className={styles.footerBadgeSecure}>
              <ShieldCheck size={16} /> Sistema Privado e Criptografado
            </div>
          </div>
        </div>

        <div className={styles.footerBottom}>
          <p>© {new Date().getFullYear()} CAD-ANALYZER. Todos os direitos reservados.</p>
          <p className={styles.footerVersion}>Versão 2.4.0 • Build de Produção</p>
        </div>
      </footer>
    </div>
  );
}
