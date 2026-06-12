"""
diag_occupants.py — pin the congested occupant over-count to its root cause.

Run against ONE tunnel's EVC file (congested case). It reports, side by side:
  (1) the stochastic VB-queue count (what VB actually places), and
  (2) the deterministic density-fallback count (theoretical max),
plus the EVC inputs that drive each, so the ~7-14% gap vs VB's ~331 can be
attributed unambiguously to ONE of:
    A. builder throwing  -> engine silently uses the inflated fallback
    B. jam-density basis  -> builder K (L65) vs fallback 1000/(clavg+2.17)
    C. occupancy basis    -> L52-58 occ/veh, or an occ_override mismatch

Usage:
    python diag_occupants.py path/to/Tunnel_congested.EVC   [VB_target]
e.g. python diag_occupants.py Gopo_Upper_020CFV0P1.EVC 331
"""
import sys, numpy as np
from evc_engine import EVCEngine, EVCParams, build_vb_vehicle_queue, vb_cint

def main(evc_path, vb_target=None):
    eng = EVCEngine(evc_path)              # use_vb_queue defaults True
    p   = eng.params
    L_km = max(1.0, p.tunnel_length) / 1000.0
    K    = p.max_congestion_vehicles      # EVC L65 jam density (veh/km/lane)
    lanes = p.num_lanes
    occ  = p.veh_occ                      # L52-58 occupants per vehicle type
    mix  = [p._float(r, default=0.0) for r in range(24, 31)]  # L24-30 mix %
    lens = p.veh_lengths                  # L45-51

    print(f"\nEVC: {evc_path}")
    print(f"  tunnel_length = {p.tunnel_length:.1f} m   lanes(L8) = {lanes}   "
          f"two_way = {getattr(p,'is_two_way',False)}")
    print(f"  jam density K (L65)       = {K:g} veh/km/lane")
    print(f"  occ/veh   (L52-58)        = {[round(float(x),3) for x in occ]}")
    print(f"  mix %     (L24-30)        = {[round(float(x),2) for x in mix]}")
    print(f"  veh len   (L45-51)        = {[round(float(x),2) for x in lens]}")

    # --- (2) deterministic density fallback (engine's self._n_occ) -----------
    det = int(eng._n_occ)
    det_f = float(getattr(p, '_n_occ_float_computed', det))
    print(f"\n  [fallback]  deterministic n_occ = {det}  (float {det_f:.2f})")

    # --- (1) stochastic VB queue, congested (5 draws to show variance) -------
    print("  [vb_queue]  stochastic placement, 5 draws:")
    ns = []
    err = None
    for s in range(5):
        try:
            q = build_vb_vehicle_queue(
                p, is_normal_traffic=False,
                fire_x=float(np.clip(p.fire_pt_x, 0.0, max(1.0, p.tunnel_length))),
                rng=np.random.default_rng(1000 + s),
                jam_density=K,
                occ_override=None)
        except Exception as e:
            err = repr(e); break
        if q is None:
            print("              -> build returned None (no usable L10-23/len/occ)")
            break
        ns.append(q["n_occ"])
        if s == 0:
            tv = vb_cint(float(K) * (max(1.0,p.tunnel_length)/1000.0) * lanes)
            print(f"              total_veh = {tv}   n_veh placed = {q['n_veh']}")
    if err:
        print(f"              -> THREW: {err}")
        print("              ROOT CAUSE = A (builder throws -> inflated fallback)")
    elif ns:
        print(f"              n_occ draws = {ns}   mean = {np.mean(ns):.1f}")

    # --- attribution ---------------------------------------------------------
    if vb_target:
        vb = float(vb_target)
        print(f"\n  VB target = {vb:.1f}")
        print(f"    fallback / VB = {det/vb:.3f}x")
        if ns:
            print(f"    vb_queue / VB = {np.mean(ns)/vb:.3f}x  "
                  f"(should be ~1.0 if builder basis matches VB)")
        # diagnostic K implied by VB target, holding lanes/length/occ fixed
        avg_occ = (sum(float(mix[i])*float(occ[i]) for i in range(7)) / (sum(mix) or 1)
                   if sum(mix) > 0 else (np.mean([float(o) for o in occ if float(o)>0]) or 1.5))
        K_implied = vb / (L_km * lanes * avg_occ) if (L_km*lanes*avg_occ) else float('nan')
        print(f"    avg_occ (mix-weighted)    = {avg_occ:.3f}")
        print(f"    K implied by VB target    = {K_implied:.1f} veh/km/lane "
              f"(compare to L65={K:g})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)