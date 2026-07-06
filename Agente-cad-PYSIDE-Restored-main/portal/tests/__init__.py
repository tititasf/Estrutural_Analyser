"""Suíte de testes do portal (WS-B). Cobre poller, fila, HTTP, R6/R8/R9 e smoke.

Implementa a estratégia de docs/HANDOFF-QA-PORTAL.md contra o código REAL do portal
(portal/app/*, portal/db/*), não contra os módulos `scripts/portal/*` que o handoff
supôs — a implementação divergiu para portal/app/ e estes testes seguem o que existe.
"""
