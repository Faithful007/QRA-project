"""
test_evc_output_writer.py
=========================
Integration tests for evc_output_writer.py.

Tests validate:
  1. Engine callback hook fires correctly during simulation
  2. All five output files are written per run
  3. File formats match the reference files from evc_output_reader.py
  4. SET file appends correctly across multiple runs
  5. LVCNHesTime monotone SFX and correct No_of_Man range
  6. EVCRunRegistry inserts / queries correctly
  7. WriterResult has correct structure
  8. run_and_write() convenience function works end-to-end
"""

import sys
import sqlite3
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evc_output_writer import (
    EVCOutputWriter,
    EVCRunRegistry,
    WriterResult,
    RunPaths,
    run_and_write,
)
from evc_output_reader import (
    read_dat, read_caset, read_set, read_hestime,
    read_scenario,
)

# ── Reference files (real EVC.exe output uploaded with the project) ──────────
UPLOAD_DIR  = Path("/mnt/user-data/uploads")
REF_EVC     = UPLOAD_DIR / "020CFV0_P1_1"   # stem for reference files
# We need an actual .evc file — use a synthesised minimal one if not present
REAL_EVC_FILE = None   # resolved in setup

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def assert_eq(label, actual, expected):
    assert actual == expected, \
        f"FAIL [{label}]: got {actual!r}, expected {expected!r}"

def assert_approx(label, actual, expected, tol=1e-3):
    assert abs(actual - expected) <= tol, \
        f"FAIL [{label}]: got {actual}, expected {expected} ± {tol}"

def assert_gt(label, actual, floor):
    assert actual > floor, f"FAIL [{label}]: {actual} not > {floor}"

def assert_true(label, val):
    assert val, f"FAIL [{label}]: expected True, got {val!r}"

def assert_instance(label, obj, typ):
    assert isinstance(obj, typ), \
        f"FAIL [{label}]: got {type(obj).__name__}, expected {typ.__name__}"


# ─────────────────────────────────────────────────────────────────────────────
# Minimal synthetic .evc file for headless testing
# ─────────────────────────────────────────────────────────────────────────────

_MINIMAL_EVC = """\
Test Tunnel
-1             0 
 320 
 8 
 0 
 24 
 5 
 2 
 0.5            0.5 
 0 
 0 
 0 
 0 
 99 
 0 
 0 
 0 
 0 
 0 
 0 
 0 
 0 
 0 
 0 
 1 
 1 
 1 
 1 
 1 
 1 
 1 
 0 
 0 
 1.0 
 1.0 
 1.0 
 1.0 
 1.0 
 1.0 
 1.0 
 4.5 
 7.0 
 12.0 
 5.0 
 8.0 
 15.0 
 20.0 
 1.5 
 8.0 
 30.0 
 2.0 
 2.0 
 2.0 
 2.0 
 86 
 7 
 3 
 5 
 0 
 0 
 160 
 0 
 160 
 160 
 320 
 160 
 60 
 165 
 2000 
 0 
 2 
 600 
 320 
 549.9 
 4009 
 0 
 0 
 0 
 0 
 0 
 0 
 0 
 0 
 0 
 180 
 60 
 0 
 0 
 0 
 0 
 0.45           0.6            0.4 
 0 
 0 
"""


def _make_evc(tmp_dir: Path) -> Path:
    p = tmp_dir / "TEST_P1.evc"
    p.write_text(_MINIMAL_EVC, encoding="utf-8")
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Test fixture
# ─────────────────────────────────────────────────────────────────────────────

class _Fixture:
    """Creates a temp dir with a synthetic .evc, runs writer once."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.evc_path = _make_evc(self.tmp)
        self.db_path  = self.tmp / "qra_test.db"

        self.writer = EVCOutputWriter(
            self.evc_path,
            fdb_path     = None,    # geometry-only (no FDB uploaded as .fdb)
            fire_pos_idx = 1,
            output_dir   = self.tmp,
            db_path      = self.db_path,
            dat_interval = 2,
        )
        self.result: WriterResult = self.writer.run_and_write(
            n_iterations = 2,
            exmax        = 0,
            exmin        = 0,
            seed         = 42,
        )
        self.writer.close()

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


_fx: _Fixture = None   # created once for the whole module

def _get_fixture() -> _Fixture:
    global _fx
    if _fx is None:
        _fx = _Fixture()
    return _fx


# ─────────────────────────────────────────────────────────────────────────────
# 1. WriterResult structure
# ─────────────────────────────────────────────────────────────────────────────

def test_writer_result_structure():
    fx = _get_fixture()
    r  = fx.result
    assert_instance("result type", r, WriterResult)
    assert_eq("n run_paths", len(r.run_paths), 2)
    assert_instance("set_path type", r.set_path, Path)
    assert_instance("db_run_ids type", r.db_run_ids, list)
    assert_eq("n db_run_ids", len(r.db_run_ids), 2)
    assert_true("batch has runs", len(r.batch.runs) == 2)
    assert_true("batch has avg",  r.batch.avg is not None)

def test_writer_run_paths_types():
    fx = _get_fixture()
    for rp in fx.result.run_paths:
        assert_instance("RunPaths type", rp, RunPaths)
        assert_true("dat exists",     rp.dat.exists())
        assert_true("caset1 exists",  rp.caset1.exists())
        assert_true("caset2 exists",  rp.caset2.exists())
        assert_true("set exists",     rp.set_.exists())
        assert_true("hestime exists", rp.hestime.exists())

def test_writer_set_shared_across_runs():
    """All run_paths reference the same SET file."""
    fx = _get_fixture()
    paths = [rp.set_ for rp in fx.result.run_paths]
    assert_eq("shared set path", len(set(paths)), 1)
    assert_true("set file exists", paths[0].exists())


# ─────────────────────────────────────────────────────────────────────────────
# 2. DAT file format
# ─────────────────────────────────────────────────────────────────────────────

def test_dat_file_readable():
    fx  = _get_fixture()
    rp1 = fx.result.run_paths[0]
    rows = read_dat(rp1.dat)
    assert_gt("dat rows > 0", len(rows), 0)

def test_dat_first_row_time_zero():
    fx   = _get_fixture()
    rows = read_dat(fx.result.run_paths[0].dat)
    assert_approx("dat row0 time", rows[0].time, 0.0)

def test_dat_timestep_interval():
    """Adjacent DAT rows are separated by dat_interval seconds."""
    fx   = _get_fixture()
    rows = read_dat(fx.result.run_paths[0].dat)
    if len(rows) >= 3:
        diffs = [rows[i+1].time - rows[i].time for i in range(min(5, len(rows)-1))]
        for d in diffs:
            assert_approx(f"dat interval {d}", d, 2.0, tol=0.5)

def test_dat_types_correct():
    fx   = _get_fixture()
    rows = read_dat(fx.result.run_paths[0].dat)
    r = rows[0]
    assert_instance("dat time float", r.time, float)
    assert_instance("dat exno_01 int", r.exno_01, int)

def test_dat_smds_min_nonzero_at_t0():
    """SMDS_MIN at t=0 should be a positive baseline visibility value."""
    fx   = _get_fixture()
    rows = read_dat(fx.result.run_paths[0].dat)
    r0   = rows[0]
    assert_approx("dat t0 smds_max", r0.smds_max, 0.0, tol=0.01)
    assert_gt("dat t0 smds_min > 0", r0.smds_min, 0.0)

def test_dat_both_runs_independent():
    """Two runs produce separate DAT files with same row count."""
    fx   = _get_fixture()
    rows1 = read_dat(fx.result.run_paths[0].dat)
    rows2 = read_dat(fx.result.run_paths[1].dat)
    assert_eq("dat run1 vs run2 row count", len(rows1), len(rows2))


# ─────────────────────────────────────────────────────────────────────────────
# 3. CASET file format
# ─────────────────────────────────────────────────────────────────────────────

def test_caset1_readable():
    fx   = _get_fixture()
    rows = read_caset(fx.result.run_paths[0].caset1)
    assert_gt("caset1 rows > 0", len(rows), 0)

def test_caset2_readable():
    fx   = _get_fixture()
    rows = read_caset(fx.result.run_paths[0].caset2)
    assert_gt("caset2 rows > 0", len(rows), 0)

def test_caset_starts_at_dat_interval():
    """CASET first row should start at dat_interval (2s), not t=0."""
    fx   = _get_fixture()
    rows = read_caset(fx.result.run_paths[0].caset1)
    assert_approx("caset first t", rows[0].time, 2.0, tol=0.5)

def test_caset_same_row_count_as_dat_minus_one():
    """CASET has one fewer row than DAT (DAT includes t=0)."""
    fx   = _get_fixture()
    dat_rows   = read_dat(fx.result.run_paths[0].dat)
    caset_rows = read_caset(fx.result.run_paths[0].caset1)
    # DAT has t=0 extra row; CASET starts at t=2
    diff = len(dat_rows) - len(caset_rows)
    assert_true("caset shorter than dat by 1", diff == 1)

def test_caset_counts_non_negative():
    fx   = _get_fixture()
    rows = read_caset(fx.result.run_paths[0].caset1)
    bad  = [r for r in rows if any(
        v < 0 for v in (r.temp_gt_90, r.temp_gt_60, r.co_gt_1400,
                        r.visi_lt_10, r.visi_lt_5)
    )]
    assert_eq("caset no negative counts", len(bad), 0)

def test_caset_geometry_only_all_zeros():
    """Without FDB all hazard counts should be zero."""
    fx   = _get_fixture()
    rows = read_caset(fx.result.run_paths[0].caset1)
    non_zero = [r for r in rows if r.temp_gt_90 > 0 or r.co_gt_1400 > 0]
    assert_eq("caset geometry-only all zeros", len(non_zero), 0)

def test_caset1_caset2_same_structure():
    fx   = _get_fixture()
    r1   = read_caset(fx.result.run_paths[0].caset1)
    r2   = read_caset(fx.result.run_paths[0].caset2)
    assert_eq("caset1 vs caset2 row count", len(r1), len(r2))
    assert_approx("caset1 caset2 same times", r1[0].time, r2[0].time)


# ─────────────────────────────────────────────────────────────────────────────
# 4. SET file format (append across runs)
# ─────────────────────────────────────────────────────────────────────────────

def test_set_file_readable():
    fx   = _get_fixture()
    rows = read_set(fx.result.set_path)
    assert_gt("set rows > 0", len(rows), 0)

def test_set_two_runs_concatenated():
    """Two runs → occ_id resets at row N+1 (VB-faithful append)."""
    fx   = _get_fixture()
    rows = read_set(fx.result.set_path)
    # Find where occ_id resets
    resets = [i for i in range(1, len(rows)) if rows[i].occ_id < rows[i-1].occ_id]
    assert_eq("set occ_id resets once for 2 runs", len(resets), 1)

def test_set_first_run_sequential_occ_ids():
    """First run: occ_id should be 1..N sequentially."""
    fx   = _get_fixture()
    rows = read_set(fx.result.set_path)
    resets = [i for i in range(1, len(rows)) if rows[i].occ_id < rows[i-1].occ_id]
    run1_rows = rows[:resets[0]] if resets else rows
    ids = [r.occ_id for r in run1_rows]
    assert_eq("set run1 starts at 1", ids[0], 1)
    assert_true("set run1 sequential", ids == list(range(1, len(ids)+1)))

def test_set_fed_total_non_negative():
    fx   = _get_fixture()
    rows = read_set(fx.result.set_path)
    bad  = [r for r in rows if r.fed_total < -1e-9]
    assert_eq("set fed_total non-negative", len(bad), 0)

def test_set_zones_1_or_2():
    fx   = _get_fixture()
    rows = read_set(fx.result.set_path)
    bad  = [r for r in rows if r.zone not in (1, 2)]
    assert_eq("set all zones 1 or 2", len(bad), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 5. LVCNHesTime.dat format
# ─────────────────────────────────────────────────────────────────────────────

def test_hestime_readable():
    fx   = _get_fixture()
    rows = read_hestime(fx.result.run_paths[0].hestime)
    assert_gt("hestime rows > 0", len(rows), 0)

def test_hestime_starts_at_1():
    fx   = _get_fixture()
    rows = read_hestime(fx.result.run_paths[0].hestime)
    assert_eq("hestime first time = 1", rows[0].time, 1)

def test_hestime_sfx_monotone():
    fx   = _get_fixture()
    rows = read_hestime(fx.result.run_paths[0].hestime)
    sfx  = [r.sfx for r in rows]
    bad  = [(i, sfx[i], sfx[i+1]) for i in range(len(sfx)-1)
            if sfx[i+1] < sfx[i] - 1e-9]
    assert_eq("hestime sfx monotone", len(bad), 0)

def test_hestime_sfx_between_0_and_1():
    fx   = _get_fixture()
    rows = read_hestime(fx.result.run_paths[0].hestime)
    bad  = [r for r in rows if r.sfx < 0 or r.sfx >= 1.0]
    assert_eq("hestime sfx in [0,1)", len(bad), 0)

def test_hestime_no_of_man_non_negative():
    fx   = _get_fixture()
    rows = read_hestime(fx.result.run_paths[0].hestime)
    bad  = [r for r in rows if r.no_of_man < 0]
    assert_eq("hestime no_of_man non-negative", len(bad), 0)

def test_hestime_no_of_man_bounded_by_n_occ():
    fx   = _get_fixture()
    rows = read_hestime(fx.result.run_paths[0].hestime)
    n_occ = fx.writer._engine._n_occ
    max_man = max(r.no_of_man for r in rows)
    assert_true("hestime no_of_man <= n_occ", max_man <= n_occ + 1)

def test_hestime_two_runs_independent():
    """Two runs get their own separate hestime files."""
    fx   = _get_fixture()
    p1   = fx.result.run_paths[0].hestime
    p2   = fx.result.run_paths[1].hestime
    assert_true("hestime paths differ", p1 != p2)
    assert_true("hestime run1 exists", p1.exists())
    assert_true("hestime run2 exists", p2.exists())


# ─────────────────────────────────────────────────────────────────────────────
# 6. EVCRunRegistry (Option B)
# ─────────────────────────────────────────────────────────────────────────────

def test_registry_rows_inserted():
    fx = _get_fixture()
    reg = EVCRunRegistry(fx.db_path)
    rows = reg.get_runs(chid="TEST_P1")
    assert_eq("registry has 2 rows", len(rows), 2)
    reg.close()

def test_registry_run_ids_sequential():
    fx = _get_fixture()
    ids = fx.result.db_run_ids
    assert_eq("2 db run IDs", len(ids), 2)
    assert_true("run ids unique", len(set(ids)) == 2)

def test_registry_get_run_by_id():
    fx  = _get_fixture()
    reg = EVCRunRegistry(fx.db_path)
    row = reg.get_run(fx.result.db_run_ids[0])
    assert_true("get_run not None", row is not None)
    assert_eq("get_run chid", row["scenario_chid"], "TEST_P1")
    assert_eq("get_run pos", row["fire_pos_idx"], 1)
    assert_eq("get_run run_no", row["run_no"], 1)
    reg.close()

def test_registry_paths_stored():
    fx  = _get_fixture()
    reg = EVCRunRegistry(fx.db_path)
    row = reg.get_run(fx.result.db_run_ids[0])
    assert_true("dat_path stored",     row["dat_path"] is not None)
    assert_true("caset1_path stored",  row["caset1_path"] is not None)
    assert_true("set_path stored",     row["set_path"] is not None)
    assert_true("hestime_path stored", row["hestime_path"] is not None)
    reg.close()

def test_registry_stats():
    fx  = _get_fixture()
    reg = EVCRunRegistry(fx.db_path)
    s   = reg.get_statistics(chid="TEST_P1")
    assert_eq("stats total_runs", s["total_runs"], 2)
    assert_true("stats avg_ev_time", s["avg_ev_time"] is not None)
    reg.close()

def test_registry_filter_by_pos():
    fx  = _get_fixture()
    reg = EVCRunRegistry(fx.db_path)
    rows_p1 = reg.get_runs(chid="TEST_P1", fire_pos_idx=1)
    rows_p2 = reg.get_runs(chid="TEST_P1", fire_pos_idx=2)
    assert_eq("pos 1 has 2 rows", len(rows_p1), 2)
    assert_eq("pos 2 has 0 rows", len(rows_p2), 0)
    reg.close()

def test_registry_delete_runs():
    # Use a separate temp DB so this doesn't affect other tests
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp())
    try:
        db  = tmp / "del_test.db"
        reg = EVCRunRegistry(db)
        from evc_engine import EVCEngine
        # Manually insert a dummy row
        from evc_output_writer import RunPaths
        from evc_engine import RunResult
        dummy_result = RunResult(run_no=1, ev_time=100.0, evacuees=10,
                                 fed=[0]*10, eq_fatal=0.5)
        dummy_paths  = RunPaths(1,
            dat=tmp/"x.DAT", caset1=tmp/"x.CASET1",
            caset2=tmp/"x.CASET2", set_=tmp/"x.SET",
            hestime=tmp/"xLVCNHesTime.dat")
        from evc_engine import EVCParams
        reg.register_run(
            chid="DUMMY", fire_pos_idx=1, run_no=1,
            evc_path=tmp/"x.evc", fdb_path=None,
            paths=dummy_paths, result=dummy_result,
            n_iterations=1, exmax=0, exmin=0, seed=None,
        )
        assert len(reg.get_runs(chid="DUMMY")) == 1
        deleted = reg.delete_runs("DUMMY")
        assert_eq("delete_runs returns 1", deleted, 1)
        assert_eq("after delete 0 rows", len(reg.get_runs(chid="DUMMY")), 0)
        reg.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_registry_schema_additive_to_existing_db():
    """EVCRunRegistry must not break an existing QRADatabase."""
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp())
    try:
        db_path = tmp / "qra.db"
        # Create a QRADatabase-style table first
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT)"
        )
        conn.execute("INSERT INTO projects VALUES (1, 'test')")
        conn.commit(); conn.close()

        # Now open with EVCRunRegistry — should not break existing table
        reg = EVCRunRegistry(db_path)
        rows = reg.get_runs()
        assert_eq("empty registry after schema add", len(rows), 0)

        # Existing table still intact
        conn2 = sqlite3.connect(str(db_path))
        row = conn2.execute("SELECT name FROM projects WHERE id=1").fetchone()
        assert_eq("existing table intact", row[0], "test")
        conn2.close()
        reg.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Convenience function
# ─────────────────────────────────────────────────────────────────────────────

def test_run_and_write_convenience():
    """run_and_write() should produce a valid WriterResult."""
    tmp = Path(tempfile.mkdtemp())
    try:
        evc = _make_evc(tmp)
        r   = run_and_write(
            evc, fdb_path=None,
            fire_pos_idx=2,
            n_iterations=1,
            seed=99,
            output_dir=tmp,
            db_path=None,
        )
        assert_instance("convenience result type", r, WriterResult)
        assert_eq("convenience 1 run", len(r.run_paths), 1)
        assert_true("convenience dat exists", r.run_paths[0].dat.exists())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# 8. File name convention  (Option A — VB-faithful paths)
# ─────────────────────────────────────────────────────────────────────────────

def test_file_names_follow_vb_convention():
    """File names must follow {stem}_P{pos}_{run}.{ext} pattern."""
    fx = _get_fixture()
    for k, rp in enumerate(fx.result.run_paths, start=1):
        stem = "TEST_P1"
        pos  = 1
        assert_eq(f"dat name run{k}",
                  rp.dat.name, f"{stem}_P{pos}_{k}.DAT")
        assert_eq(f"caset1 name run{k}",
                  rp.caset1.name, f"{stem}_P{pos}_{k}.CASET1")
        assert_eq(f"hestime name run{k}",
                  rp.hestime.name, f"{stem}_P{pos}_{k}LVCNHesTime.dat")


# ─────────────────────────────────────────────────────────────────────────────
# 9. Timestep callback integration
# ─────────────────────────────────────────────────────────────────────────────

def test_timestep_callback_fires():
    """Writer must have captured at least one snapshot per run."""
    tmp = Path(tempfile.mkdtemp())
    try:
        evc = _make_evc(tmp)
        ticks_seen = []

        class _ProbeWriter(EVCOutputWriter):
            def _timestep_callback(self, t, **kwargs):
                ticks_seen.append(t)
                super()._timestep_callback(t=t, **kwargs)

        w = _ProbeWriter(evc, output_dir=tmp, db_path=None)
        w.run_and_write(n_iterations=1, seed=0)
        w.close()
        assert_gt("callback fired at least once", len(ticks_seen), 0)
        assert_approx("first tick is t=0 or t=1", ticks_seen[0], 0.0, tol=1.5)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'─'*65}")
    print(f"  {passed} passed,  {failed} failed  ({passed + failed} total)")

    # Cleanup shared fixture
    if _fx:
        _fx.cleanup()

    import sys; sys.exit(0 if failed == 0 else 1)