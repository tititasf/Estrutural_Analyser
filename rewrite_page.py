import json
import os
import re

file_path = 'd:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/consulta-publica-web/app/ficha/[code]/page.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Imports
content = content.replace(
    'import { buscarFicha, urlAbsolutaSvg, type FichaData } from "@/lib/api/ficha";',
    'import { buscarFicha, buscarViewsFicha, urlAbsolutaSvg, type FichaData } from "@/lib/api/ficha";'
)
content = content.replace(
    'import { SvgViewer } from "@/components/ui/SvgViewer";',
    'import { CadViewer } from "@/components/viewer/CadViewer";'
)

# 2. Add State for Views
state_block = '''  const [viewsData, setViewsData] = useState<import("@/lib/api/ficha").ViewsData | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [subAba, setSubAba] = useState<string>("geral");
'''
content = content.replace(
    'const [svgTentativa, setSvgTentativa] = useState(0);',
    'const [svgTentativa, setSvgTentativa] = useState(0);\n' + state_block
)

# 3. Add viewsData fetch in useEffect
old_use_effect = '''      if (resultado.status === "ok") {
        setFicha(resultado.data);
        setEstado("ok");
        setSvgErro(false);
        setAba(resultado.data.svg.n1 ? "n1" : resultado.data.svg.n3 ? "n3" : "paineis");'''

new_use_effect = '''      if (resultado.status === "ok") {
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
'''
content = content.replace(old_use_effect, new_use_effect)

# 4. Handle rendering logic
old_render_logic = '''  if (!ficha) return null;

  const svgUrlAtivo = aba === "n1" ? ficha.svg.n1 : aba === "n3" ? ficha.svg.n3 : null;

  return ('''

new_render_logic = '''  if (!ficha) return null;

  const hasRichN3 = viewsData && Object.values(viewsData.views).some((v: any) => v?.available && v?.svg);
  const temN3Real = Boolean(ficha.svg.n3) || Boolean(hasRichN3);

  let viewKey = subAba;
  if (aba === "estrutural") {
    viewKey = "estrutural_limpo";
  } else if (ficha.tipo === "viga_fundo" || ficha.tipo === "laje") {
    if (subAba === "geral") viewKey = "n3";
  }

  const rawSvgAtivo = (aba === "n3" || aba === "estrutural") && viewsData?.views?.[viewKey]?.svg 
    ? viewsData.views[viewKey].svg 
    : null;

  const svgUrlAtivo = rawSvgAtivo ? null : (aba === "n1" ? ficha.svg.n1 : aba === "n3" ? ficha.svg.n3 : null);

  const classificacao = ficha.campos["Classificação"] || ficha.campos["Classificacao"] || "";
  const nivel = ficha.campos["Nível Relativo"] || ficha.campos["Nível"] || ficha.campos["Laje B #1 — Nível"] || Object.entries(ficha.campos).find(e => e[0].toLowerCase().includes("nível") || e[0].toLowerCase().includes("nivel"))?.[1] || "";

  return ('''
content = content.replace(old_render_logic, new_render_logic)

# 5. Header updates
old_header = '''      <FichaHeader
        obraRotulo={ficha.obra_rotulo}
        pavimentoLabel={ficha.pavimento_label}
        pavimentoCode={ficha.pavimento_code}
        tipo={ficha.tipo}
        titulo={ficha.titulo}
        code={ficha.code}
        onVoltar={handleVoltar}
      />'''

new_header = '''      <FichaHeader
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
      />'''
content = content.replace(old_header, new_header)

# 6. FichaTabs updates
old_tabs = '''        <FichaTabs
          temN1={Boolean(ficha.svg.n1)}
          temN3={Boolean(ficha.svg.n3)}
          temLv={ficha.tem_lv}
          aba={aba}
          onSelecionar={(novaAba) => {
            setAba(novaAba);
            setSvgErro(false);
          }}
        />'''

new_tabs = '''        <FichaTabs
          temN1={Boolean(ficha.svg.n1)}
          temN3={temN3Real}
          temLv={ficha.tem_lv}
          aba={aba}
          tipo={ficha.tipo}
          subAba={subAba}
          onSelecionar={(novaAba) => {
            setAba(novaAba);
            setSvgErro(false);
          }}
          onSelecionarSubAba={(novaSub) => {
            setSubAba(novaSub);
          }}
        />'''
content = content.replace(old_tabs, new_tabs)

# 7. SvgViewer -> CadViewer and remove SpecFieldList
old_viewer_and_spec = '''        {(aba === "n1" || aba === "n3") && (
          <div role="tabpanel">
            {svgUrlAtivo && !svgErro ? (
              <SvgViewer
                status="loaded"
                svgUrl={urlAbsolutaSvg(svgUrlAtivo)}
                descricao={Desenho  de  — leitura por CAD}
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

        <SpecFieldList campos={ficha.campos} atencao={ficha.atencao} />'''

new_viewer_and_spec = '''        {(aba === "n1" || aba === "n3" || aba === "estrutural") && (
          <div role="tabpanel">
            {(svgUrlAtivo || rawSvgAtivo) && !svgErro ? (
              <CadViewer
                svgUrl={svgUrlAtivo ? urlAbsolutaSvg(svgUrlAtivo) : undefined}
                rawSvg={rawSvgAtivo || undefined}
                descricao={Desenho  de  — leitura por CAD}
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
        )}'''
content = content.replace(old_viewer_and_spec, new_viewer_and_spec)

# 8. DrawingFullscreen
old_fullscreen = '''        aberto={fullscreenAberto && (aba === "n1" || aba === "n3")}
        svgUrl={svgUrlAtivo ? urlAbsolutaSvg(svgUrlAtivo) : null}'''

new_fullscreen = '''        aberto={fullscreenAberto && (aba === "n1" || aba === "n3" || aba === "estrutural")}
        svgUrl={svgUrlAtivo ? urlAbsolutaSvg(svgUrlAtivo) : null}
        rawSvg={rawSvgAtivo || undefined}'''
content = content.replace(old_fullscreen, new_fullscreen)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
