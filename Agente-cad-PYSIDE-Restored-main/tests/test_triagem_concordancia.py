from scripts.arete.triagem_concordancia import build_rollup


def test_build_rollup_computes_concordance_only_when_human_pair_exists():
    human = [
        {"classe": "LAJ", "item": "L318", "causa_raiz": "n1_overlap_viga"},
        {"classe": "LAJ", "item": "L319", "causa_raiz": "n1_overlap_viga"},
    ]
    auto = [
        {"classe": "LAJ", "item": "L318", "causa_raiz": "extractor_bug", "status": "aberto"},
        {"classe": "LAJ", "item": "L319", "causa_raiz": "extractor_bug", "status": "aberto"},
        {"classe": "LAJ", "item": "L312", "causa_raiz": "extractor_bug", "status": "aberto"},
        {"classe": "PIL", "item": "P1", "causa_raiz": "extractor_bug", "status": "aberto"},
    ]

    rollup = build_rollup(human, auto)

    laj = rollup["LAJ"]["extractor_bug"]
    assert laj["n_auto"] == 3
    assert laj["n_com_par_humano"] == 2  # L318 e L319 têm par; L312 não
    assert laj["n_concorda"] == 0  # causas diferentes (extractor_bug != n1_overlap_viga)
    assert laj["n_diverge"] == 2
    assert laj["taxa_concordancia"] == 0.0
    assert laj["n_abertos_reais"] == 3
    assert set(laj["itens_abertos"]) == {"L318", "L319", "L312"}

    pil = rollup["PIL"]["extractor_bug"]
    assert pil["n_auto"] == 1
    assert pil["n_com_par_humano"] == 0
    assert pil["taxa_concordancia"] is None  # sem dado, não é zero


def test_build_rollup_marks_concordance_when_causa_matches():
    human = [{"classe": "LAJ", "item": "L100", "causa_raiz": "extractor_bug"}]
    auto = [{"classe": "LAJ", "item": "L100", "causa_raiz": "extractor_bug", "status": "verificado"}]

    rollup = build_rollup(human, auto)

    bucket = rollup["LAJ"]["extractor_bug"]
    assert bucket["n_com_par_humano"] == 1
    assert bucket["n_concorda"] == 1
    assert bucket["taxa_concordancia"] == 1.0
    assert bucket["n_abertos_reais"] == 0  # status é "verificado", não "aberto"
