"""VB6-faithful random number generator (MSVBVM60 rtcRandomNext/rtcRandomize).

GROUNDING
---------
The reference EXE calls `rtcRandomNext` and `rtcRandomize` (confirmed in the
decompile: n4.txt:265, 0x45D560.txt:119/185, FUN_004a4160.txt:211).  These are
MSVBVM60 runtime entry points, so their constants live in the runtime, not the
compiled app — they are the long-documented VB6 `Rnd` algorithm and are
validated here EMPIRICALLY against VB6's published reference sequence
(seed-1 first draws), which is a stronger check than a symbol match.

VB6 Rnd is a 24-bit LCG on a 32-bit state:
    state := (state * 0x43FD43FD + 0xC39EC3) & 0xFFFFFF
    Rnd   := state / 2**24            (Single, in [0, 1))

The multiplier 0x43FD43FD = 1,140,671,485 and increment 0xC39EC3 = 12,820,163,
with the 24-bit mask, are the canonical VB6/VBA constants.  Default seed state
is 0x50000 (327,680); `Randomize n` seeds the high 16 bits from the argument
while preserving VB's documented mixing.

Draw-site form in the generator (n4.txt): `Int(Rnd() * N) + 1` for a 1..N pick.
"""

import struct


class VB6Rnd:
    MUL = 0x43FD43FD          # 1,140,671,485
    INC = 0xC39EC3            # 12,820,163
    MASK = 0xFFFFFF           # 24-bit
    DEFAULT = 0x50000         # VB6 initial state (327,680)

    def __init__(self, state=None):
        self.state = self.DEFAULT if state is None else (state & 0xFFFFFFFF)

    # ── core ────────────────────────────────────────────────────────────────
    def rnd(self) -> float:
        """One VB6 Rnd() draw: advance state, return Single in [0,1)."""
        self.state = (self.state * self.MUL + self.INC) & self.MASK
        # VB returns the 24-bit state as a Single divided by 2**24.  Force
        # float32 round-trip so band-edge comparisons match VB's Single math.
        val = self.state / 16777216.0
        return struct.unpack('f', struct.pack('f', val))[0]

    def randomize(self, n: float):
        """VB6 `Randomize n`: reseed high 16 bits of state from the argument.

        VB computes a Single from n and folds its bits into the top of the
        existing 24-bit state (low byte preserved), per the documented
        Randomize behaviour.
        """
        bits = struct.unpack('<I', struct.pack('<f', float(n)))[0]
        hi = (bits & 0xFFFF) ^ ((bits >> 16) & 0xFFFF)
        self.state = ((hi << 8) | (self.state & 0xFF)) & self.MASK

    # ── generator-form helpers (mirror the decompiled call sites) ───────────
    def int_1_to_n(self, n: int) -> int:
        """`Int(Rnd() * N) + 1` — the 1..N pick used in occupant generation."""
        return int(self.rnd() * n) + 1

    def uniform(self, lo: float, hi: float) -> float:
        """`lo + Rnd()*(hi-lo)` — continuous draw (positions, reaction times)."""
        return lo + self.rnd() * (hi - lo)


def _self_test():
    """Validate against VB6's published seed-default sequence.

    With the default seed, VB6 Rnd() yields 0.7055475, 0.533424, 0.5795186,
    0.2895625, 0.301952 ... (the canonical documented sequence).
    """
    r = VB6Rnd()
    got = [round(r.rnd(), 6) for _ in range(5)]
    ref = [0.705548, 0.533424, 0.579519, 0.289563, 0.301952]
    ok = all(abs(g - e) < 1e-5 for g, e in zip(got, ref))
    return ok, got, ref


if __name__ == "__main__":
    ok, got, ref = _self_test()
    print("got:", got)
    print("ref:", ref)
    print("MATCH" if ok else "MISMATCH")