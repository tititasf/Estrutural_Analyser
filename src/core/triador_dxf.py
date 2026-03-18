# -*- coding: utf-8 -*-
"""
Triador de DXFs - Fase 1 -> Fase 2
Classifica DXFs de forma estrutural e copia para pasta limpa.
"""
import os
import sys
import re
import shutil
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import ezdxf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resultado da classificacao
# ---------------------------------------------------------------------------

@dataclass
class ClassificacaoResult:
    """Resultado da classificacao de um arquivo DXF."""
    dxf_path: str
    tipo: str           # 'FORMA', 'PE', 'SECTION', 'OTHER', 'UNKNOWN'
    pavimento: str
    confianca: float
    razao: str


# ---------------------------------------------------------------------------
# Regex compiladas (reutilizadas em multiplas chamadas)
# ---------------------------------------------------------------------------

_RE_PAV_FORMA = re.compile(
    r'[-_](PLA|FOR|FORMA|LO)[-_]([A-Z0-9]+?)(?:[-_]R\d|$)',
    re.IGNORECASE,
)

_RE_PAV_NUM = re.compile(
    r'(\d+)\s*(PAV|PV|SS|SUB|PAVTO|SI)',
    re.IGNORECASE,
)

_RE_VERSION_SUFFIX = re.compile(
    r'_(R12|R2000|R2004|R2007|R2010|R2013|R2018)_(ASCII|BINARIO)$',
    re.IGNORECASE,
)

_RE_PE_INDICATOR = re.compile(r'[-_]PE[-_]', re.IGNORECASE)

_RE_PILAR = re.compile(r'^P\.?\d+[A-Z]?\b')
_RE_VIGA = re.compile(r'^(V|BA|VB|VT|VC)\.?\d+')

_RE_NON_ALNUM = re.compile(r'[^A-Za-z0-9_\-]')

# Preferencia de versao para dedup (maior = melhor)
_VERSION_RANK = {
    'R2018_ASCII': 100,
    'R2018_BINARIO': 95,
    'R2018': 90,
    'R2013_ASCII': 80,
    'R2013_BINARIO': 75,
    'R2013': 70,
    'R2010_ASCII': 60,
    'R2010_BINARIO': 55,
    'R2010': 50,
    'R2007_ASCII': 40,
    'R2007_BINARIO': 35,
    'R2007': 30,
    'R2004_ASCII': 20,
    'R2004_BINARIO': 15,
    'R2004': 10,
    'R2000_ASCII': 5,
    'R2000_BINARIO': 4,
    'R2000': 3,
    'R12_ASCII': 2,
    'R12_BINARIO': 1,
    'R12': 0,
}


class TriadorDXF:
    """Classifica e copia DXFs de Fase-1 (bruto) para Fase-2 (limpo)."""

    def __init__(self, dados_obras_dir: str = 'DADOS-OBRAS') -> None:
        self.dados_obras_dir = dados_obras_dir

    # ------------------------------------------------------------------
    # Deteccao de pavimento a partir do nome do arquivo
    # ------------------------------------------------------------------

    def _detectar_pavimento_filename(self, filename: str) -> Tuple[str, float]:
        """Detecta o pavimento a partir do nome do arquivo DXF.

        Returns:
            (pavimento, confianca) onde confianca e 0.0-1.0.
        """
        upper = filename.upper()

        # Tentativa 1: padrao FORMA / PLA / LO
        m = _RE_PAV_FORMA.search(upper)
        if m:
            return m.group(2).strip('_- '), 0.9

        # Tentativa 2: padrao numerico (2PAV, 1SS, etc.)
        m = _RE_PAV_NUM.search(upper)
        if m:
            pav = f"{m.group(1)}{m.group(2).upper()}"
            return pav, 0.8

        # Tentativa 3: prefixo SUBSOLO_
        if 'SUBSOLO_' in upper or '_SUBSOLO' in upper:
            return 'SUBSOLO', 0.7

        return 'DESCONHECIDO', 0.0

    # ------------------------------------------------------------------
    # Classificacao por nome do arquivo
    # ------------------------------------------------------------------

    def _classificar_filename(self, filename: str) -> Tuple[str, float, str]:
        """Classifica tipo do DXF pelo nome do arquivo.

        Returns:
            (tipo, confianca, razao)
        """
        # Strip version suffix para analise do nome base
        clean = _RE_VERSION_SUFFIX.sub('', filename)

        # Detectar PE (planta de esgoto / nao-estrutural)
        if _RE_PE_INDICATOR.search(clean):
            return 'PE', 0.85, f'Indicador nao-estrutural: PE encontrado em {filename}'

        # Se contem FORMA ou FOR no nome, provavel forma estrutural
        upper = clean.upper()
        if 'FORMA' in upper or '-FOR-' in upper or '_FOR_' in upper:
            return 'FORMA', 0.7, f'Indicador estrutural por nome: {filename}'

        if 'SECTION' in upper or 'CORTE' in upper:
            return 'SECTION', 0.6, f'Indicador de secao/corte: {filename}'

        return 'UNKNOWN', 0.0, f'Sem indicador claro no nome: {filename}'

    # ------------------------------------------------------------------
    # Analise de conteudo DXF (entidades)
    # ------------------------------------------------------------------

    def _analisar_conteudo_dxf(self, dxf_path: str) -> dict:
        """Abre o DXF com ezdxf e conta entidades estruturais.

        Returns:
            dict com n_pilares, n_vigas, n_entities e outros contadores.
        """
        result = {
            'n_pilares': 0,
            'n_vigas': 0,
            'n_entities': 0,
            'n_texts': 0,
            'n_polylines': 0,
            'n_hatches': 0,
            'erro': None,
        }

        try:
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()

            for entity in msp:
                result['n_entities'] += 1
                dxftype = entity.dxftype()

                if dxftype in ('TEXT', 'MTEXT'):
                    result['n_texts'] += 1
                    text_val = ''
                    if dxftype == 'TEXT':
                        text_val = entity.dxf.text or ''
                    else:
                        text_val = entity.text or ''

                    text_upper = text_val.strip().upper()
                    if _RE_PILAR.match(text_upper):
                        result['n_pilares'] += 1
                    elif _RE_VIGA.match(text_upper):
                        result['n_vigas'] += 1

                elif dxftype in ('LWPOLYLINE', 'POLYLINE'):
                    result['n_polylines'] += 1

                elif dxftype == 'HATCH':
                    result['n_hatches'] += 1

        except Exception as exc:
            msg = f'Erro lendo {dxf_path}: {exc}'
            logger.warning(msg)
            result['erro'] = msg

        return result

    # ------------------------------------------------------------------
    # Classificacao principal
    # ------------------------------------------------------------------

    def classificar(self, dxf_path: str) -> ClassificacaoResult:
        """Classifica um unico arquivo DXF.

        Combina analise de nome + conteudo para determinar tipo e confianca.
        """
        filename = Path(dxf_path).name
        pav, pav_conf = self._detectar_pavimento_filename(filename)
        tipo_fn, conf_fn, razao_fn = self._classificar_filename(filename)

        try:
            conteudo = self._analisar_conteudo_dxf(dxf_path)

            if conteudo.get('erro'):
                return ClassificacaoResult(
                    dxf_path=dxf_path,
                    tipo='UNKNOWN',
                    pavimento=pav,
                    confianca=0.0,
                    razao=f'Erro: {conteudo["erro"]}',
                )

            n_pilares = conteudo['n_pilares']
            n_vigas = conteudo['n_vigas']

            # Classificar como FORMA se ha conteudo estrutural
            if n_pilares > 0 or n_vigas > 0:
                conf_conteudo = min(1.0, 0.5 + (n_pilares + n_vigas) * 0.02)
                confianca_final = max(conf_fn, conf_conteudo)
                razao = (
                    f'Conteudo estrutural: {n_pilares} pilares, {n_vigas} vigas '
                    f'({conteudo["n_entities"]} entidades totais)'
                )
                return ClassificacaoResult(
                    dxf_path=dxf_path,
                    tipo='FORMA',
                    pavimento=pav,
                    confianca=confianca_final,
                    razao=razao,
                )

            # Sem conteudo estrutural: usar classificacao por nome
            return ClassificacaoResult(
                dxf_path=dxf_path,
                tipo=tipo_fn if tipo_fn != 'UNKNOWN' else 'OTHER',
                pavimento=pav,
                confianca=conf_fn,
                razao=razao_fn,
            )

        except Exception as exc:
            return ClassificacaoResult(
                dxf_path=dxf_path,
                tipo='UNKNOWN',
                pavimento=pav,
                confianca=0.0,
                razao=f'Erro: {exc}',
            )

    # ------------------------------------------------------------------
    # Nome base (sem sufixo de versao/formato)
    # ------------------------------------------------------------------

    def _base_name(self, filename: str) -> str:
        """Strips version/format suffixes to get base drawing name for dedup.

        Exemplo: 'FORMA-1PAV_R2018_ASCII.dxf' -> 'FORMA-1PAV'
        """
        stem = Path(filename).stem
        return _RE_VERSION_SUFFIX.sub('', stem)

    # ------------------------------------------------------------------
    # Deduplicacao de versoes DXF
    # ------------------------------------------------------------------

    def _dedup_dxfs(self, dxf_files: List[Path]) -> List[Path]:
        """Deduplica versoes de DXF, preferindo R2018_ASCII > R2018 > newest.

        Agrupa por _base_name e seleciona o melhor de cada grupo.
        """
        if not dxf_files:
            return []

        groups: dict[str, List[Path]] = {}
        for f in dxf_files:
            base = self._base_name(f.name)
            groups.setdefault(base, []).append(f)

        selected: List[Path] = []
        for base, versions in groups.items():
            if len(versions) == 1:
                selected.append(versions[0])
                continue

            # Ordenar por rank de versao (descendente)
            def _rank(p: Path) -> int:
                stem = p.stem
                base_clean = self._base_name(p.name)
                suffix = stem[len(base_clean):].lstrip('_').upper()
                return _VERSION_RANK.get(suffix, -1)

            versions.sort(key=_rank, reverse=True)
            best = versions[0]
            n = len(versions)
            logger.info(f'  DEDUP {n} versions -> {best.name}')
            selected.append(best)

        return selected

    # ------------------------------------------------------------------
    # Triagem de uma obra
    # ------------------------------------------------------------------

    def triar_obra(self, obra: str) -> List[ClassificacaoResult]:
        """Tria todos os DXFs de Fase-1 de uma obra.

        Path: DADOS-OBRAS/{obra}/Fase-1_Ingestao/Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF/
        """
        fase1_dir = Path(
            self.dados_obras_dir,
            obra,
            'Fase-1_Ingestao',
            'Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF',
        )

        if not fase1_dir.exists():
            logger.warning(f'Fase-1 nao encontrada: {fase1_dir}')
            return []

        # Listar e deduplicar DXFs
        all_dxfs = sorted(fase1_dir.glob('*.dxf'))
        if not all_dxfs:
            all_dxfs = sorted(fase1_dir.glob('*.DXF'))

        dxf_files = self._dedup_dxfs(all_dxfs)
        logger.info(f'Triando {len(dxf_files)} DXFs de {obra} (pos-dedup de {len(all_dxfs)})')

        resultados: List[ClassificacaoResult] = []
        for dxf_path in dxf_files:
            resultado = self.classificar(str(dxf_path))
            resultados.append(resultado)

        return resultados

    # ------------------------------------------------------------------
    # Limpeza de nome de pavimento
    # ------------------------------------------------------------------

    def _nome_limpo(self, pavimento: str) -> str:
        """Remove caracteres invalidos para nome de diretorio."""
        return _RE_NON_ALNUM.sub('_', pavimento)

    # ------------------------------------------------------------------
    # Execucao da triagem (com copia para Fase-2)
    # ------------------------------------------------------------------

    def executar_triagem(
        self,
        obra: str,
        dry_run: bool = False,
        min_confianca: float = 0.7,
    ) -> List[ClassificacaoResult]:
        """Executa triagem de uma obra, copiando DXFs qualificados para Fase-2.

        Output path: DADOS-OBRAS/{obra}/Fase-2_Triagem/Estruturais_Pavimentos_Limpos/

        Args:
            obra: Nome da obra (subpasta de DADOS-OBRAS).
            dry_run: Se True, nao copia arquivos (apenas classifica).
            min_confianca: Confianca minima para copiar (default 0.7).

        Returns:
            Lista completa de ClassificacaoResult (incluindo nao-copiados).
        """
        resultados = self.triar_obra(obra)

        fase2_dir = Path(
            self.dados_obras_dir,
            obra,
            'Fase-2_Triagem',
            'Estruturais_Pavimentos_Limpos',
        )

        copiados = 0
        skipped = 0

        for r in resultados:
            qualifica = r.tipo == 'FORMA' and r.confianca >= min_confianca

            if not qualifica:
                logger.info(f'  SKIP  {Path(r.dxf_path).name}  ({r.tipo} conf={r.confianca:.2f})')
                skipped += 1
                continue

            if dry_run:
                logger.info(f'  [DRY] COPY {Path(r.dxf_path).name} -> Fase-2')
                copiados += 1
                continue

            # Criar subpasta por pavimento
            pav_dir = fase2_dir / self._nome_limpo(r.pavimento)
            pav_dir.mkdir(parents=True, exist_ok=True)

            destino = pav_dir / Path(r.dxf_path).name
            shutil.copy2(r.dxf_path, destino)
            logger.info(f'  COPY  {Path(r.dxf_path).name} -> {destino}')
            copiados += 1

        logger.info(
            f'Triagem {obra}: {copiados} copiados, {skipped} ignorados '
            f'(total {len(resultados)} DXFs)'
        )

        return resultados


# ---------------------------------------------------------------------------
# CLI de teste rapido
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    obra = sys.argv[1] if len(sys.argv) > 1 else 'Obra_TREINO_1'
    triador = TriadorDXF()
    resultados = triador.executar_triagem(obra, dry_run=True)
    for r in resultados:
        print(f"  {r.tipo:10} {r.confianca:.2f}  {Path(r.dxf_path).name}")
