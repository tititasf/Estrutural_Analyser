"""Retention safety checks using temporary directories and a temporary DB."""
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from scripts.maintenance.retain_html_packs import inventory, published_plan, referenced, busy, plan, run, resolve_html_root


class RetentionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old = time.time() - 10 * 86400

    def pack(self, stamp, files, suffix="pilares_abcd", floor="13_PAV"):
        p = self.root / "obra" / f"{floor}_{stamp}_{suffix}"
        for rel in files:
            target = p / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("test evidence", encoding="utf-8")
        age = self.old + int(stamp[6:8])
        for target in sorted(p.rglob("*"), key=lambda x: len(x.parts), reverse=True):
            os.utime(target, (age, age))
        os.utime(p, (age, age))
        return p

    def removable(self, packs):
        return {p['path'] for p in published_plan([inventory(p) for p in packs], 2, time.time() - 86400)}

    def test_partial_runs_keep_each_item(self):
        first = self.pack("20260801_000000", ["pilares/P1.html", "pilares/P2.html"])
        second = self.pack("20260802_000000", ["pilares/P1.html"])
        third = self.pack("20260803_000000", ["pilares/P1.html"])
        self.assertEqual(self.removable([first, second, third]), set())
        fourth = self.pack("20260804_000000", ["pilares/P2.html"])
        fifth = self.pack("20260805_000000", ["pilares/P2.html"])
        self.assertEqual(self.removable([first, second, third, fourth, fifth]), {first})

    def test_unique_review_asset_pins_pack(self):
        old = self.pack("20260801_000000", ["pilares/P1.html", "propostas/P1_qa_L1.svg"])
        newer = [self.pack(f"2026080{i}_000000", ["pilares/P1.html"]) for i in (2, 3)]
        self.assertEqual(self.removable([old, *newer]), set())

    def test_recent_files_and_distinct_floor_are_preserved(self):
        old = self.pack("20260801_000000", ["pilares/P1.html"])
        newer = [self.pack(f"2026080{i}_000000", ["pilares/P1.html"]) for i in (2, 3)]
        os.utime(old / "pilares/P1.html", None)
        self.assertEqual(self.removable([old, *newer]), set())
        other = self.pack("20260801_000000", ["pilares/P1.html"], floor="14_PAV")
        self.assertNotIn(other, self.removable([old, other, *newer]))

    def test_reader_mtime_order_is_preserved(self):
        old = self.pack("20260801_000000", ["pilares/P1.html"])
        newer = [self.pack(f"2026080{i}_000000", ["pilares/P1.html"]) for i in (2, 3)]
        os.utime(old, (self.old + 100, self.old + 100))
        self.assertNotIn(old, self.removable([old, *newer]))

    def test_qa_reference_and_jobs(self):
        p = self.pack("20260801_000000", ["pilares/P1.html"])
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("CREATE TABLE portal_qa_items(evidence TEXT)")
        conn.execute("CREATE TABLE portal_jobs(status TEXT)")
        conn.execute("INSERT INTO portal_qa_items VALUES(?)", (str(p / 'pilares/P1.html'),))
        self.assertEqual(referenced(conn, [inventory(p)], []), {p})
        conn.execute("INSERT INTO portal_jobs VALUES('concluido')")
        self.assertFalse(busy(conn))
        conn.execute("INSERT INTO portal_jobs VALUES('executando')")
        self.assertTrue(busy(conn))

    def test_failed_expiry_never_includes_original_data(self):
        failed = self.root / ".parity_failed/obra/13_PAV_20260801_000000_pilares_abcd"
        failed.mkdir(parents=True)
        f = failed / 'P1.html'
        f.write_text('failed', encoding='utf-8')
        for p in [f, failed]:
            os.utime(p, (self.old, self.old))
        original = self.root / 'obra/Fase-4_Sincronizacao'
        original.mkdir(parents=True)
        (original / 'original.json').write_text('{}')
        result = plan(self.root, 2, 24, 7)
        self.assertEqual([r['path'] for r in result], [failed])
        self.assertTrue((original / 'original.json').exists())

    def test_equal_mtime_boundary_is_preserved(self):
        packs = [self.pack(f"2026080{i}_000000", ['pilares/P1.html']) for i in (1, 2, 3)]
        for p in packs:
            os.utime(p, (self.old, self.old))
        self.assertEqual(self.removable(packs), set())

    def test_apply_defers_jobs_and_is_idempotent(self):
        repo = self.root
        self.root = repo / 'scripts/arete/html_fichas'
        packs = [self.pack(f"2026080{i}_000000", ['pilares/P1.html']) for i in (1, 2, 3)]
        conn = sqlite3.connect(repo / 'portal_data.db')
        conn.executescript("CREATE TABLE portal_jobs(status TEXT); CREATE TABLE portal_obras(local_path TEXT); INSERT INTO portal_jobs VALUES('executando');")
        conn.commit()
        args = SimpleNamespace(repo_root=repo, db=None, apply=True, keep=2, min_hours=24, discarded_days=7)
        with patch('scripts.arete.single_instance.acquire_lock', return_value=(object(), None)), \
             patch('scripts.arete.single_instance.release_lock'), \
             patch('scripts.maintenance.retain_html_packs.open_paths', return_value=[]):
            self.assertEqual(run(args)['status'], 'deferred_active_jobs')
            self.assertTrue(all(p.exists() for p in packs))
            conn.execute("UPDATE portal_jobs SET status='concluido'")
            conn.commit()
            first = run(args)
            self.assertEqual(first['deleted'], [str(packs[0].resolve())])
            self.assertTrue(all(p.exists() for p in packs[1:]))
            self.assertEqual(run(args)['deleted'], [])
        conn.close()

    def test_symlink_pack_is_never_a_candidate(self):
        packs = [self.pack(f"2026080{i}_000000", ['pilares/P1.html']) for i in (1, 2, 3)]
        target = self.root / 'do_not_touch.txt'
        target.write_text('original')
        try:
            (packs[0] / 'external.txt').symlink_to(target)
        except OSError:
            self.skipTest('symlink creation unavailable')
        self.assertNotIn(packs[0], self.removable(packs))

    def relocated_root(self):
        repo = self.root / 'repo'
        logical = repo / 'scripts/arete/html_fichas'
        logical.parent.mkdir(parents=True)
        physical = self.root / 'volume/html_fichas'
        physical.mkdir(parents=True)
        try:
            logical.symlink_to(physical, target_is_directory=True)
        except OSError:
            self.skipTest('symlink creation unavailable')
        return repo, logical, physical

    def test_relocated_root_requires_explicit_matching_physical_path(self):
        repo, logical, physical = self.relocated_root()
        with self.assertRaises(RuntimeError):
            resolve_html_root(repo)
        self.assertEqual(resolve_html_root(repo, physical), physical)
        with self.assertRaises(RuntimeError):
            resolve_html_root(repo, logical)
        other = self.root / 'other'
        other.mkdir()
        with self.assertRaises(RuntimeError):
            resolve_html_root(repo, other)
        logical.unlink()
        logical.symlink_to(other, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            resolve_html_root(repo, physical)

    def test_apply_on_pinned_volume_preserves_links_and_live_assets(self):
        repo, logical, physical = self.relocated_root()
        self.root = physical
        packs = [self.pack(f'2026080{i}_000000', ['pilares/P1.html']) for i in (1, 2, 3)]
        outside = repo / 'original'
        outside.mkdir()
        (outside / 'P1.html').write_text('preserve')
        (physical / 'obra/13_PAV_20260701_000000_pilares_abcd').symlink_to(outside, target_is_directory=True)
        with sqlite3.connect(repo / 'portal_data.db') as conn:
            conn.executescript('CREATE TABLE portal_jobs(status TEXT); CREATE TABLE portal_obras(local_path TEXT);')
        args = SimpleNamespace(repo_root=repo, html_root=physical, db=None, apply=True,
                               keep=2, min_hours=24, discarded_days=7)
        with patch('scripts.arete.single_instance.acquire_lock', return_value=(object(), None)), \
             patch('scripts.arete.single_instance.release_lock'), \
             patch('scripts.maintenance.retain_html_packs.open_paths', return_value=[]):
            result = run(args)
        self.assertEqual(result['deleted'], [str(packs[0])])
        self.assertTrue(logical.is_symlink())
        self.assertTrue(all(p.exists() for p in packs[1:]))
        self.assertEqual((outside / 'P1.html').read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
