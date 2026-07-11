"""Hook único de download sob demanda (Masterplan OBRAS DRIVE).

Compartilhado entre os 3 lugares que abrem arquivo físico de uma obra
(`diagnostic_hub.py`, `main.py`'s Structural Analyzer, `diagnostic_reverse_hub.py`)
— antes de cada um deles verificar se o path existe em disco, chama
`garantir_drive_download` primeiro. Pra obra local normal é sempre um no-op
(2 checagens rápidas: `obra_e_drive` e o path já existir).

Resolve 2 formas de mapeamento, tentando as duas:
  - `drive_obras` (obra_nome, bruto_id, item_id) — recortes (torre_1 etc),
    onde bruto_id/item_id vêm da CONVENÇÃO de path (pasta-pai/stem).
  - `drive_documentos` (obra_nome, arquivo_local) — documentos inteiros
    (bruto .dwg/.dxf, PDF, etc), casados pelo path exato.

Cache/expiração (Masterplan OBRAS DRIVE Fase 13): quando o arquivo já existe
localmente, NUNCA expira por tempo — só por versão. Faz 1 HEAD leve (sem
baixar corpo) comparando com o `Last-Modified` guardado no último download;
só re-baixa se a web realmente mudou. Se a obra já tem qualquer item validado
(selo verde), a atualização é pulada e só logada — nunca sobrescreve trabalho
de validação em andamento silenciosamente.
"""

from __future__ import annotations

from pathlib import Path


def garantir_drive_download(db, obra_nome: str, raw_path: str) -> bool:
    """Retorna True se baixou/atualizou algo agora, False se não precisou
    (obra não é Drive, não achou mapeamento, ou já está na versão mais
    recente conhecida) — nesse caso o chamador segue com o fluxo de sempre."""
    if not raw_path or not obra_nome:
        return False
    p = Path(raw_path)

    try:
        if not db.obra_e_drive(obra_nome):
            return False

        mapping = db.obter_drive_item(obra_nome, p.parent.name, p.stem)
        doc_mapping = None if mapping else db.obter_drive_documento(obra_nome, str(p))
        if not mapping and not doc_mapping:
            return False

        from src.core.drive_client import obter_cliente_padrao
        client = obter_cliente_padrao()

        try:
            existe_local = p.exists()
        except OSError:
            existe_local = False

        if not existe_local:
            if mapping:
                client.baixar_recorte(
                    mapping["portal_obra_id"], mapping["portal_bruto_id"], mapping["portal_item_id"], p
                )
                db.atualizar_drive_item_versao(
                    obra_nome, p.parent.name, p.stem, client.ultimo_last_modified
                )
            else:
                client.baixar_documento(doc_mapping["portal_obra_id"], doc_mapping["portal_doc_id"], p)
                db.atualizar_drive_documento_versao(obra_nome, str(p), client.ultimo_last_modified)
            return True

        # Arquivo já existe localmente — checagem barata de versão (HEAD, sem
        # baixar corpo). Sem `Last-Modified` conhecido dos dois lados, não dá
        # pra comparar com segurança: mantém a cópia local (nunca expira por
        # tempo/adivinhação).
        url = (
            client.url_recorte(mapping["portal_obra_id"], mapping["portal_bruto_id"], mapping["portal_item_id"])
            if mapping else client.url_documento(doc_mapping["portal_obra_id"], doc_mapping["portal_doc_id"])
        )
        versao_conhecida = (mapping or doc_mapping).get("remoto_versao")
        versao_atual = client.obter_last_modified(url)
        if not versao_atual or versao_atual == versao_conhecida:
            return False

        if db.tem_item_validado_para_obra(obra_nome):
            print(
                f"[DriveDownloadHook] {obra_nome}: versão remota de {p.name} mudou, "
                "mas há item(ns) já validado(s) localmente nesta obra — mantendo "
                "cópia local (não sobrescreve validação em andamento).",
                flush=True,
            )
            return False

        if mapping:
            client.baixar_recorte(
                mapping["portal_obra_id"], mapping["portal_bruto_id"], mapping["portal_item_id"], p
            )
            db.atualizar_drive_item_versao(obra_nome, p.parent.name, p.stem, versao_atual)
        else:
            client.baixar_documento(doc_mapping["portal_obra_id"], doc_mapping["portal_doc_id"], p)
            db.atualizar_drive_documento_versao(obra_nome, str(p), versao_atual)
        print(
            f"[DriveDownloadHook] {obra_nome}: {p.name} atualizado (versão remota mais nova).",
            flush=True,
        )
        return True
    except Exception as e:
        print(f"[DriveDownloadHook] Falha ao baixar/atualizar do Drive ({obra_nome}/{raw_path}): {e}", flush=True)

    return False
