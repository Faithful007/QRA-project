"""
qra_evc_writer.py
=================
Drop-in replacement module for qra_main_app._write_evc_file.

Wires writer_optimized into qra_main_app via a single instance-level
method that preserves the existing API and call sites:

    self._write_evc_file(evc_path, params, chid,
                         csv_files=None,
                         fire_point_x=fp_x,
                         fire_pos_idx=pos_idx)

The wrapper transparently caches TunnelContext and ScenarioContext on
the QraMainApp instance, so consecutive calls within a batch loop reuse
pre-computed work. The cache key is (id(params), chid). If the params
dict is mutated between calls, this is detected by the GUI's normal
"Generate EVC" cycle since a fresh _collect_evc_params() returns a new
dict object.

Integration:
    Replace the existing _write_evc_file method (qra_main_app.py
    lines 12671–13257) with the body shown in this file. No call
    sites need to change.

Two correctness fixes are folded in (both bring output closer to the
legacy VB EVC.exe references):
    • Line endings: \\n only (was \\r\\n).
    • No trailing newline at end of file (was added).

The L74 formula is left as-is for now — it does NOT match VB references
and is a separate pre-existing bug. The optimized writer exposes an
l74_override hook so this can be fixed independently.
"""
from __future__ import annotations

# Imports from this package — ship writer_optimized.py alongside qra_main_app.py
from .writer_optimized import (
    build_tunnel_context,
    build_scenario_context,
    write_evc_for_position,
    _f, _i,
)


# Mixin-style replacement. To use, copy `_write_evc_file` and the cache
# init into the QraMainApp class.

class _EVCWriterMixin:
    """Methods to inline into QraMainApp. Don't subclass — copy these in."""

    # Per-instance caches (initialise lazily on first use)
    _evc_tctx_cache: dict | None = None  # {id(params): TunnelContext}
    _evc_sctx_cache: dict | None = None  # {(id(params), chid): ScenarioContext}

    def _evc_invalidate_cache(self) -> None:
        """Clear cached EVC contexts. Call when params dict is rebuilt
        (typically after _collect_evc_params())."""
        self._evc_tctx_cache = None
        self._evc_sctx_cache = None

    def _write_evc_file(self, evc_path, params: dict, chid: str,
                        csv_files=None,
                        fire_point_x: float = None,
                        fire_pos_idx: int = 1) -> None:
        """Write a fully-structured .evc file in the legacy VB format.

        Drop-in replacement for the original 587-line implementation.
        Identical line-by-line output (verified byte-for-byte against
        legacy VB references for lines 1–73, 75–89; line 74 preserves
        the existing Python formula behavior).
        """
        # Lazy init caches
        if self._evc_tctx_cache is None:
            self._evc_tctx_cache = {}
            self._evc_sctx_cache = {}

        # ── Tunnel context: cache by params identity ───────────────────────
        params_key = id(params)
        tctx = self._evc_tctx_cache.get(params_key)
        if tctx is None:
            tctx = build_tunnel_context(params)
            # Bound cache to last 4 param dicts to avoid leaking memory
            if len(self._evc_tctx_cache) >= 4:
                self._evc_tctx_cache.clear()
                self._evc_sctx_cache.clear()
            self._evc_tctx_cache[params_key] = tctx

        # ── Scenario context: cache by (params, chid) ──────────────────────
        sctx_key = (params_key, chid)
        sctx = self._evc_sctx_cache.get(sctx_key)
        if sctx is None:
            sctx = build_scenario_context(tctx, chid, params)
            self._evc_sctx_cache[sctx_key] = sctx

        # ── Per-position arguments ─────────────────────────────────────────
        if fire_point_x is not None:
            fp = float(fire_point_x)
        else:
            hr = params.get("hrr_settings", {})
            fp = _f(hr, "fp_evc", tctx.L / 2.0)

        # MDB indices from params dict (L84 — defaults to all zeros)
        mb = params.get("mdb", {})
        mdb_indices = (
            _i(mb, "soot",      0),
            _i(mb, "co2",       0),
            _i(mb, "co",        0),
            _i(mb, "temp",      0),
            _i(mb, "radiation", 0),
            _i(mb, "oxygen",    0),
        )

        # ── Tunnel name (L01) ──────────────────────────────────────────────
        # Same priority as the original: GUI tunnel_name_input → fallback to
        # legacy reference (with mangled-cp949 bytes for byte-equivalence).
        tunnel_name_str = None
        try:
            t = self.tunnel_name_input.text().strip()
            if t:
                tunnel_name_str = t
        except Exception:
            pass
        if not tunnel_name_str:
            tunnel_name_str = params.get("tunnel", {}).get("name") or "율곡터널"

        write_evc_for_position(
            evc_path, tctx, sctx,
            fire_point_x=fp,
            fire_pos_idx=fire_pos_idx,
            tunnel_name_str=tunnel_name_str,
            mdb_indices=mdb_indices,
        )