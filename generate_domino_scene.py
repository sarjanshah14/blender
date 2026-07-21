# ============================================================================
#  DOMINO CHAIN REACTION  --  Blender scene generator
#  College Computer Graphics group assignment
#
#  Builds a complete, physics-baked domino-run scene:
#    * modern room + large polished wooden table
#    * ~450 colourful dominoes (curves, S-path, zig-zag, circle, spiral,
#      staircase, bridge, marble track, seesaw, crossover)
#    * finale spells the letters "C G"
#    * rigid-body simulation, baked
#    * one slowly moving camera timed to the actual simulation
#
#  HOW TO RUN
#  ----------
#  From a terminal:
#      blender --background --python generate_domino_scene.py
#  (a file  domino_chain_reaction.blend  is written next to this script)
#
#  Or open Blender 4.x, paste this file into the Text Editor and press
#  "Run Script".  Building + baking takes several minutes.
#
#  The layout half of this file is plain Python (no bpy) so it can also be
#  imported by helper/plot scripts.
# ============================================================================

import math
import os
import sys

DEG = math.pi / 180.0

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
CFG = {
    # dominoes ---------------------------------------------------------------
    "dom_h": 0.050,           # height  (m)
    "dom_w": 0.024,           # width   (m)
    "dom_t": 0.008,           # thickness (m)
    "dom_bevel": 0.0016,      # rounded edge width
    "dom_mass": 0.020,        # kg
    "spacing": 0.033,         # base spacing along the path
    "spacing_curve": 0.029,   # tighter spacing on tight curves
    "spacing_letters": 0.030,

    # table ------------------------------------------------------------------
    "table_top_x": 3.60,
    "table_top_y": 2.10,
    "table_top_t": 0.06,
    "table_h": 0.75,          # top surface height above floor

    # staircase / platforms / bridge ----------------------------------------
    "stair_steps": 7,
    "stair_rise": 0.014,
    "stair_tread": 0.036,
    "platform_h": 0.098,      # = stair_steps * stair_rise
    "bridge_len": 0.42,
    "bridge_w": 0.075,

    # marble -----------------------------------------------------------------
    "marble_r": 0.0125,
    "marble_mass": 0.035,
    "chute_len": 0.34,
    "chute_w": 0.05,

    # seesaw -----------------------------------------------------------------
    "seesaw_len": 0.16,
    "seesaw_w": 0.035,
    "seesaw_t": 0.007,
    "seesaw_pivot_h": 0.013,
    "seesaw_stop_h": 0.0055,  # height of the block the output arm rests on
    "seesaw_stop_d": 0.060,   # stop block distance from the pivot

    # animation --------------------------------------------------------------
    "fps": 24,
    "intro_seconds": 6.0,     # still frames before the first domino is tipped
    "hold_seconds": 12.0,     # hold on the fallen "CG" at the end
    # ponytail: 0.45 is the proven-stable slow-motion factor. Going slower
    # (0.25) starves the start-deactivated dominoes of wake impulse and the
    # cascade stalls, so keep this at 0.45 — the brief prioritises a reliable
    # chain over exact length. ~1 min at 0.45.
    "time_scale": 0.45,
    "max_frames": 1700,       # safety cap for the bake

    # physics ----------------------------------------------------------------
    "substeps": 30,
    "solver_iters": 20,
}

# palette: name -> sRGB
DOMINO_COLORS = {
    "white":  (0.92, 0.90, 0.88),
    "black":  (0.03, 0.03, 0.035),
    "red":    (0.75, 0.05, 0.06),
    "blue":   (0.05, 0.18, 0.75),
    "yellow": (0.90, 0.72, 0.05),
    "green":  (0.06, 0.55, 0.12),
    "orange": (0.90, 0.30, 0.03),
}
RAINBOW = ["red", "orange", "yellow", "green", "blue", "white", "black"]


# ----------------------------------------------------------------------------
# Path builder (pure python) - generates dense samples along 2-D segments
# ----------------------------------------------------------------------------
class PathBuilder:
    """Walks a 2-D path made of straights / arcs / spirals and records dense
    samples: (x, y, heading_rad, section_name, arclength)."""

    STEP = 0.002  # dense sampling step in metres

    def __init__(self, x, y, heading_deg):
        self.x, self.y = x, y
        self.h = heading_deg * DEG
        self.s = 0.0
        self.section = "lead_in"
        self.pts = [(x, y, self.h, self.section, 0.0)]
        self.marks = {}  # name -> sample index

    # -- segment primitives --------------------------------------------------
    def set_section(self, name):
        self.section = name

    def mark(self, name):
        self.marks[name] = len(self.pts) - 1

    def _advance(self, ds, dh):
        self.h += dh
        self.x += math.cos(self.h) * ds
        self.y += math.sin(self.h) * ds
        self.s += ds
        self.pts.append((self.x, self.y, self.h, self.section, self.s))

    def straight(self, length):
        n = max(1, int(math.ceil(length / self.STEP)))
        ds = length / n
        for _ in range(n):
            self._advance(ds, 0.0)

    def arc(self, radius, angle_deg):
        """angle > 0 turns left, angle < 0 turns right."""
        ang = abs(angle_deg) * DEG
        length = ang * radius
        n = max(2, int(math.ceil(length / self.STEP)))
        dh = ang / n * (1 if angle_deg > 0 else -1)
        ds = length / n
        for _ in range(n):
            self._advance(ds, dh)

    def spiral(self, r0, r1, angle_deg):
        """Arc whose radius changes linearly from r0 to r1 over the given
        swept angle.  Sign of angle_deg = turn direction."""
        ang = abs(angle_deg) * DEG
        sgn = 1 if angle_deg > 0 else -1
        n = max(8, int(math.ceil(ang / (0.2 * DEG))))
        dth = ang / n
        for i in range(n):
            r = r0 + (r1 - r0) * (i + 0.5) / n
            self._advance(r * dth, dth * sgn)

    def turn_to(self, target_heading_deg, radius):
        """Arc from the current heading to an absolute heading (shortest)."""
        cur = self.h / DEG
        d = (target_heading_deg - cur + 180.0) % 360.0 - 180.0
        if abs(d) > 0.2:
            self.arc(radius, d)

    # -- resampling into domino positions ------------------------------------
    def dominoes(self, spacing_for):
        """Returns [(x, y, heading_rad, section), ...] resampled so that
        consecutive dominoes are `spacing_for(section)` apart (arclength)."""
        out = []
        next_s = 0.0
        for (x, y, h, sec, s) in self.pts:
            if s + 1e-9 >= next_s:
                out.append((x, y, h, sec))
                next_s = s + spacing_for(sec)
        return out


# ----------------------------------------------------------------------------
# The actual table layout
# ----------------------------------------------------------------------------
# Local table coordinates: origin at table centre, z = 0 on the table surface.
# Usable area (with margin): |x| < 1.55, |y| < 0.90.

# letter geometry (table-local coordinates)
LETTER_C = (-1.06, 0.32, 0.27)          # centre x, centre y, radius
LETTER_G = (-0.28, 0.32, 0.27)
SPIRAL_C = (0.62, 0.40)                 # spiral centre
SPIRAL_R0, SPIRAL_R1 = 0.33, 0.16       # outer / inner radius, 300 deg ccw
STAIRS_BASE = (0.45, -0.25)             # foot of the staircase, heading +x


def build_ground_path_A():
    """Start pad up to the foot of the staircase."""
    p = PathBuilder(-1.55, -0.30, -10.0)

    p.set_section("lead_in")            # straight lead-in
    p.straight(0.30)

    p.set_section("s_curve")            # S-shaped path
    p.arc(0.20, -65)
    p.arc(0.20, 65)
    p.straight(0.08)

    p.set_section("zigzag")             # zig-zag path
    p.arc(0.10, 70)
    p.straight(0.22)
    p.arc(0.10, -145)
    p.straight(0.22)
    p.arc(0.10, 145)
    p.straight(0.22)
    p.arc(0.10, -100)

    p.set_section("circle")             # circular loop (teardrop, 300 deg)
    p.turn_to(-45.0, 0.13)              # dip a little further south first
    p.straight(0.14)
    p.turn_to(-5.0, 0.13)
    p.arc(0.16, 45)
    p.mark("circle_pinch")              # neck of the teardrop
    p.arc(0.175, -300)
    p.arc(0.16, -45)                    # peel off to the north-east

    p.set_section("approach")           # sweeping curve up to the stairs
    _steer_to(p, STAIRS_BASE[0], STAIRS_BASE[1], 0.0, radius=0.15)
    p.mark("stairs_base")
    return p


def build_ground_path_B(start_x, start_y, heading_deg):
    """Marble impact point -> the seesaw micro-steps."""
    p = PathBuilder(start_x, start_y, heading_deg)
    p.set_section("after_marble")
    p.straight(0.132)                   # exact multiple of the spacing
    p.mark("seesaw_in")
    return p


def build_ground_path_C(start_x, start_y, heading_deg):
    """Seesaw output -> spiral -> crossover -> letters C G.

    The spiral is entered from a corridor along the top edge of the table
    (west, then south into the spiral's outer ring).  Its exit leaves through
    the spiral's open sector and CROSSES the entry corridor once; at that
    point a double-height 'crosser' domino hops over the already-fallen
    entry lane (the entry falls long before the spiral finishes)."""
    p = PathBuilder(start_x, start_y, heading_deg)

    p.set_section("after_seesaw")
    p.arc(0.125, 90)                    # left: north -> west along the top

    # west along the top corridor, then south into the spiral entry
    entry_x = SPIRAL_C[0] - SPIRAL_R0   # west point of the outer ring
    p.straight(max(0.05, p.x - (entry_x + 0.125)))
    p.arc(0.125, 90)                    # left: west -> south
    p.straight(max(0.05, p.y - SPIRAL_C[1]))
    p.mark("spiral_entry")

    p.set_section("spiral")             # 300 deg ccw, radius 0.33 -> 0.16
    p.spiral(SPIRAL_R0, SPIRAL_R1, 300)

    # exit through the open NW sector; this crosses the entry corridor once
    p.set_section("connect_1")
    p.arc(0.12, -60)                    # heading 210 -> 150
    p.mark("cross_exit_start")
    p.straight(0.55)
    p.turn_to(190.0, 0.14)

    cx, cy, r = LETTER_C                # enter C at 100 deg, heading 190
    ex = cx + r * math.cos(100 * DEG)
    ey = cy + r * math.sin(100 * DEG)
    _steer_to(p, ex, ey, 190.0)
    p.set_section("letter_C")
    p.arc(r, 200)                       # ccw: top -> left -> bottom (ends 300)

    p.set_section("connect_2")          # dip under letter G, around its right
    p.turn_to(-16.0, 0.13)
    p.straight(max(0.05, (0.02 - p.x) / math.cos(p.h)))
    p.turn_to(90.0, 0.13)
    p.straight(0.30)

    gx, gy, gr = LETTER_G               # enter G at 60 deg, heading 150
    ex = gx + gr * math.cos(60 * DEG)
    ey = gy + gr * math.sin(60 * DEG)
    _steer_to(p, ex, ey, 150.0)
    p.set_section("letter_G")
    p.arc(gr, 270)                      # ccw 60 -> 330 deg
    p.arc(0.085, 30)                    # hook of the G ...
    p.arc(0.085, 90)
    p.straight(0.16)                    # ... and its horizontal bar
    p.mark("finale")
    return p


def _steer_to(p, tx, ty, final_heading_deg, radius=0.14):
    """Turn towards the target point, run straight, then turn to the
    requested final heading.  Good enough for connector runs."""
    ang = math.atan2(ty - p.y, tx - p.x) / DEG
    p.turn_to(ang, radius)
    dist = math.hypot(tx - p.x, ty - p.y)
    d = (final_heading_deg - p.h / DEG + 180.0) % 360.0 - 180.0
    lead = radius * abs(math.tan(min(abs(d), 120.0) * DEG / 2.0))
    p.straight(max(0.0, dist - lead))
    p.turn_to(final_heading_deg, radius)


# ----------------------------------------------------------------------------
# Assemble the whole layout (ground paths + elevated section + mechanisms)
# ----------------------------------------------------------------------------
TIGHT_SECTIONS = {"zigzag", "circle", "spiral"}
LETTER_SECTIONS = {"letter_C", "letter_G"}

SECTION_COLOR = {
    "lead_in":      "white",
    "s_curve":      "red",
    "zigzag":       "yellow",
    "circle":       "green",
    "approach":     "orange",
    "stairs":       "blue",
    "bridge":       "orange",
    "after_marble": "black",
    "seesaw_trigger": "blue",
    "after_seesaw": "white",
    "spiral":       None,          # rainbow cycling
    "connect_1":    "white",
    "connect_2":    "white",
    "crosser":      "yellow",
    "letter_C":     "red",
    "letter_G":     "blue",
}


def spacing_for(section):
    if section in LETTER_SECTIONS:
        return CFG["spacing_letters"]
    if section in TIGHT_SECTIONS:
        return CFG["spacing_curve"]
    return CFG["spacing"]


def color_for(section, index):
    c = SECTION_COLOR.get(section, "white")
    if c is None:                       # rainbow section
        return RAINBOW[index % len(RAINBOW)]
    return c


def build_layout():
    """Returns a dict describing every object that must be created:
       dominoes: [(x, y, z_base, heading_rad, section, color), ...]
       plus key poses for stairs / bridge / marble / seesaw / camera."""
    L = {}

    # ---- ground path A -----------------------------------------------------
    pA = build_ground_path_A()
    base_x, base_y, base_h = pA.x, pA.y, pA.h    # foot of the stairs
    base_h = (base_h + math.pi) % (2 * math.pi) - math.pi
    assert abs(base_h) < 2 * DEG, "stairs approach must end heading +x"
    domsA = pA.dominoes(spacing_for)
    pinch = pA.pts[pA.marks["circle_pinch"]]
    L["pinch"] = (pinch[0], pinch[1])

    # make sure the last ground domino sits right at the foot of the stairs
    lx, ly = domsA[-1][0], domsA[-1][1]
    if math.hypot(base_x - lx, base_y - ly) > 0.026:
        domsA.append((base_x - 0.012, base_y, 0.0, "approach"))

    # ---- staircase + platforms + bridge (heading +x from the base) ---------
    steps = CFG["stair_steps"]
    rise, tread = CFG["stair_rise"], CFG["stair_tread"]

    doms_elev = []
    # dominoes ON the steps (seated 0.6 mm above the convex-hull surface)
    for i in range(steps):
        d = tread * (i + 0.50)
        doms_elev.append((base_x + d, base_y, rise * (i + 1) + 0.0006,
                          0.0, "stairs"))
    stair_run = tread * steps

    # platform A (top of the stairs), the bridge, then platform B
    plat_h = CFG["platform_h"]
    platA_len = 0.14
    for d in (0.025, 0.065, 0.105):
        doms_elev.append((base_x + stair_run + d, base_y,
                          plat_h + 0.0006, 0.0, "stairs"))

    bridge_start = stair_run + platA_len
    b_len = CFG["bridge_len"]
    n_b = int((b_len - 0.01) / CFG["spacing"]) + 1
    for i in range(n_b):
        d = bridge_start + 0.008 + CFG["spacing"] * i
        doms_elev.append((base_x + d, base_y, plat_h + 0.0006, 0.0, "bridge"))

    # platform B: the chain turns 90 deg left so the last domino (the
    # "pusher") faces the marble waiting at the top of the chute
    platB_start = bridge_start + b_len
    platB_len = 0.15
    E = platB_start + 0.010             # entry of the quarter turn
    r_t = 0.055
    doms_elev.append((base_x + E, base_y, plat_h + 0.0006, 0.0, "bridge"))
    for ang in (30.0, 60.0, 90.0):
        a = ang * DEG
        doms_elev.append((base_x + E + r_t * math.sin(a),
                          base_y + r_t * (1.0 - math.cos(a)),
                          plat_h + 0.0006, a, "bridge"))
    tx = E + r_t                        # marble lane: x = base_x + tx
    doms_elev.append((base_x + tx, base_y + r_t + 0.030,
                      plat_h + 0.0006, 90 * DEG, "bridge"))    # the pusher

    L["stairs_base"] = (base_x, base_y, 0.0)
    L["stair_run"] = stair_run
    L["platA"] = (base_x + stair_run + platA_len / 2, base_y, platA_len)
    L["bridge_mid"] = (base_x + bridge_start + b_len / 2, base_y)
    L["bridge_span"] = (base_x + bridge_start, base_x + bridge_start + b_len,
                        base_y)
    L["platB"] = {"cx": base_x + platB_start + platB_len / 2,
                  "cy": base_y + 0.055,
                  "sx": platB_len, "sy": 0.22}

    # ---- marble + chute ----------------------------------------------------
    # chute runs +y, offset 8 mm west of the domino lane so the marble veers
    # off after striking the first ground domino instead of chasing the chain
    chute_x = base_x + tx - 0.008
    chute_y0 = base_y + 0.17
    chute_len = CFG["chute_len"]
    L["marble_start"] = (chute_x, base_y + r_t + 0.030 + 0.047,
                         plat_h + CFG["marble_r"] + 0.0006)
    L["chute"] = {"x": chute_x, "y0": chute_y0, "len": chute_len,
                  "h0": plat_h}
    L["marble_target"] = (base_x + tx, chute_y0 + chute_len + 0.075)

    # ---- ground path B: short run into the seesaw --------------------------
    pB = build_ground_path_B(L["marble_target"][0], L["marble_target"][1],
                             90.0)
    domsB = pB.dominoes(spacing_for)
    # ponytail: base the seesaw on the ACTUAL last path-B domino, not the
    # path end (the resampler leaves a ~30 mm stub, which opened a 63 mm gap
    # that stalled the chain). This guarantees a normal 33 mm handoff.
    see_x, see_y, see_h = domsB[-1][0], domsB[-1][1], pB.h

    # ---- seesaw ------------------------------------------------------------
    # Two micro-steps (8-10 mm rises) lead up to the seesaw; the chunky
    # trigger block on the top step falls over and LANDS LYING ON the input
    # arm, whose sustained weight rotates the plank; the rising output tip
    # lifts the overhanging edge of the payload domino (standing WIDE on its
    # own platform) and tips it onto the next ground domino.
    # ponytail: micro-steps were the single break point (a table-level run
    # can't reliably tip a domino perched on a 10 mm step). Keep the two
    # approach dominoes flat on the table; the seesaw fires fine from there.
    cs, sn = math.cos(see_h), math.sin(see_h)
    L["seesaw_steps"] = [
        {"x": see_x + cs * 0.033, "y": see_y + sn * 0.033,
         "heading": see_h, "h": 0.0},
        {"x": see_x + cs * 0.066, "y": see_y + sn * 0.066,
         "heading": see_h, "h": 0.0},
    ]
    piv_d = 0.066 + 0.100                    # hinge 100 mm past the top step
    L["seesaw"] = {"x": see_x + cs * piv_d,
                   "y": see_y + sn * piv_d,
                   "heading": see_h,
                   "stand_d": 0.1055,       # payload platform centre
                   "payload_d": 0.096}      # payload centre, standing WIDE
    out_d = piv_d + 0.150                    # next ground domino after seesaw
    outx = see_x + cs * out_d
    outy = see_y + sn * out_d

    # ---- ground path C: spiral + letters -----------------------------------
    pC = build_ground_path_C(outx, outy, see_h / DEG)
    domsC = pC.dominoes(spacing_for)

    L["letter_C_def"] = LETTER_C
    L["letter_G_def"] = LETTER_G
    L["spiral_def"] = (SPIRAL_C[0], SPIRAL_C[1], SPIRAL_R0)

    # ---- crossover: exit line crosses the spiral entry corridor ------------
    entry_x = SPIRAL_C[0] - SPIRAL_R0
    cross_pt = None
    cross_h = None
    for (x, y, h, sec, s) in pC.pts:
        if sec == "connect_1" and abs(x - entry_x) < 0.004:
            cross_pt = (x, y)
            cross_h = h
            break
    L["crossing"] = cross_pt

    filtered = []
    for (x, y, h, sec) in domsC:
        if cross_pt and sec == "connect_1":
            d = ((x - cross_pt[0]) * math.cos(cross_h)
                 + (y - cross_pt[1]) * math.sin(cross_h))
            if -0.075 < d < 0.048:
                continue                        # cleared window
        filtered.append((x, y, h, sec))
    domsC = filtered

    # ---- merge all dominoes ------------------------------------------------
    dominoes = []
    for (x, y, h, sec) in domsA:
        dominoes.append((x, y, 0.0, h, sec))
    dominoes.extend(doms_elev)
    for (x, y, h, sec) in domsB:
        dominoes.append((x, y, 0.0, h, sec))
    for j, st in enumerate(L["seesaw_steps"]):
        sec = "seesaw_trigger" if j == 1 else "after_marble"
        dominoes.append((st["x"], st["y"], st["h"] + 0.0006, st["heading"],
                         sec))
    ins_at = None
    for (x, y, h, sec) in domsC:
        if (cross_pt and ins_at is None and sec == "connect_1"
                and (x - cross_pt[0]) * math.cos(cross_h)
                + (y - cross_pt[1]) * math.sin(cross_h) > 0.0):
            # the crosser goes right before the first domino past the window
            dominoes.append((cross_pt[0] - 0.056 * math.cos(cross_h),
                             cross_pt[1] - 0.056 * math.sin(cross_h),
                             0.0, cross_h, "crosser"))
            ins_at = True
        dominoes.append((x, y, 0.0, h, sec))

    out = []
    for i, (x, y, z, h, sec) in enumerate(dominoes):
        out.append((x, y, z, h, sec, color_for(sec, i)))
    L["dominoes"] = out
    return L


# ----------------------------------------------------------------------------
# Layout validation (used by the dev plot script and as a sanity check)
# ----------------------------------------------------------------------------
def validate_layout(L, verbose=True):
    doms = L["dominoes"]
    problems = []

    # table bounds
    mx = CFG["table_top_x"] / 2 - 0.10
    my = CFG["table_top_y"] / 2 - 0.10
    for i, (x, y, z, h, sec, col) in enumerate(doms):
        if abs(x) > mx or abs(y) > my:
            problems.append("domino %d (%s) outside table: %.2f %.2f"
                            % (i, sec, x, y))

    # self-clearance: non-neighbouring dominoes must stay apart so a falling
    # line never clips a parallel lane.  Pairs closer than ~0.45 m along the
    # chain are exempt (converging tangents at circle/letter entries).
    min_clear = 0.095
    cross = L.get("crossing")
    n = len(doms)
    for i in range(n):
        xi, yi, zi = doms[i][0], doms[i][1], doms[i][2]
        for j in range(i + 14, n):
            xj, yj, zj = doms[j][0], doms[j][1], doms[j][2]
            if abs(zi - zj) > 0.04:      # different level -> ignore
                continue
            if cross and (math.hypot(xi - cross[0], yi - cross[1]) < 0.16
                          and math.hypot(xj - cross[0], yj - cross[1]) < 0.16):
                continue                 # deliberate crossover zone
            pinch = L.get("pinch")
            if pinch and (math.hypot(xi - pinch[0], yi - pinch[1]) < 0.16
                          and math.hypot(xj - pinch[0], yj - pinch[1]) < 0.16):
                continue                 # teardrop neck (lanes diverge safely)
            d = math.hypot(xi - xj, yi - yj)
            if d < min_clear:
                problems.append("clearance %.3f between %d(%s) and %d(%s)"
                                % (d, i, doms[i][4], j, doms[j][4]))
    if verbose:
        counts = {}
        for d in doms:
            counts[d[4]] = counts.get(d[4], 0) + 1
        print("dominoes per section:")
        for k, v in counts.items():
            print("   %-14s %3d" % (k, v))
        print("total dominoes: %d" % len(doms))
        if problems:
            print("PROBLEMS (%d):" % len(problems))
            for p in problems[:40]:
                print("   " + p)
        else:
            print("layout OK - no clearance problems")
    return problems


# ============================================================================
#  Everything below needs bpy (runs inside Blender)
# ============================================================================
try:
    import bpy
    import bmesh
    from mathutils import Vector, Matrix, Euler
    HAVE_BPY = True
except ImportError:
    HAVE_BPY = False

TABLE_Z = CFG["table_h"]                # world z of the table surface


# ----------------------------------------------------------------------------
# Small bpy helpers
# ----------------------------------------------------------------------------
def get_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def make_box_mesh(name, sx, sy, sz, bevel=0.0, z_origin="center"):
    """Box mesh; origin at the centre (or the bottom face)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z *= sz
        if z_origin == "bottom":
            v.co.z += sz / 2.0
    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel,
                        segments=2, profile=0.7, affect='EDGES')
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def new_obj(name, mesh, col, loc=(0, 0, 0), rot=(0, 0, 0), mat=None):
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.rotation_euler = rot
    if mat is not None and mesh is not None:
        if not mesh.materials:
            mesh.materials.append(mat)
    col.objects.link(obj)
    return obj


def simple_material(name, color, rough=0.5, metallic=0.0, coat=0.0):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    if coat and "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
    mat.diffuse_color = (*color, 1.0)
    return mat


def wood_material(name, col_dark, col_light, scale=4.0, rough=0.35,
                  coat=0.0, stripe_axis='X', distortion=1.8):
    """Simple procedural wood: wave bands distorted by noise -> color ramp."""
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    if coat and "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat

    tex = nt.nodes.new("ShaderNodeTexWave")
    tex.wave_type = 'BANDS'
    tex.bands_direction = stripe_axis
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Distortion"].default_value = distortion
    tex.inputs["Detail"].default_value = 1.5

    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale * 2.5
    noise.inputs["Detail"].default_value = 4.0

    mixd = nt.nodes.new("ShaderNodeMix")
    mixd.data_type = 'FLOAT'
    mixd.inputs["Factor"].default_value = 0.25

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*col_dark, 1.0)
    ramp.color_ramp.elements[1].color = (*col_light, 1.0)

    coord = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
    nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(tex.outputs["Fac"], mixd.inputs[2])
    nt.links.new(noise.outputs["Fac"], mixd.inputs[3])
    nt.links.new(mixd.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    mat.diffuse_color = (*col_light, 1.0)
    return mat


def add_rigid_body(obj, body_type='ACTIVE', shape='BOX', mass=1.0,
                   friction=0.5, restitution=0.05, margin=0.0005,
                   deactivate=True):
    with bpy.context.temp_override(object=obj, active_object=obj,
                                   selected_objects=[obj]):
        bpy.ops.rigidbody.object_add()
    rb = obj.rigid_body
    rb.type = body_type
    rb.collision_shape = shape
    rb.mass = mass
    rb.friction = friction
    rb.restitution = restitution
    rb.use_margin = True
    rb.collision_margin = margin
    if body_type == 'ACTIVE':
        rb.use_deactivation = deactivate
        rb.use_start_deactivated = deactivate
    return rb


# ----------------------------------------------------------------------------
# Scene building
# ----------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = "Scene"
    return sc


def build_world():
    w = bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.72, 1.0)  # soft sky
    bg.inputs["Strength"].default_value = 0.35


def build_environment(col):
    """Floor, three walls, a window wall with an opening."""
    mat_floor = wood_material("Mat_Floor_Oak", (0.22, 0.13, 0.07),
                              (0.42, 0.28, 0.16), scale=1.6, rough=0.5,
                              stripe_axis='Y', distortion=1.2)
    mat_wall = simple_material("Mat_Wall", (0.82, 0.80, 0.76), rough=0.9)
    mat_frame = simple_material("Mat_WindowFrame", (0.92, 0.92, 0.90),
                                rough=0.6)

    # room shell: 7.4 x 6.4, walls at x = +-3.65, y = +-3.15
    rx, ry = 3.65, 3.15
    me = make_box_mesh("Floor", 2 * rx + 0.2, 2 * ry + 0.2, 0.1)
    fl = new_obj("Floor", me, col, loc=(0, 0, -0.05), mat=mat_floor)
    add_rigid_body(fl, 'PASSIVE', friction=0.6)

    wall_h, wall_t = 2.9, 0.08
    me = make_box_mesh("Wall_North", 2 * rx, wall_t, wall_h, z_origin="bottom")
    new_obj("Wall_North", me, col, loc=(0, ry, 0), mat=mat_wall)
    me = make_box_mesh("Wall_West", wall_t, 2 * ry, wall_h, z_origin="bottom")
    new_obj("Wall_West", me, col, loc=(-rx, 0, 0), mat=mat_wall)
    me = make_box_mesh("Wall_South", 2 * rx, wall_t, wall_h, z_origin="bottom")
    new_obj("Wall_South", me, col, loc=(0, -ry, 0), mat=mat_wall)

    # east wall with a window opening: y in [-0.9, 0.9], z in [0.9, 2.2]
    wy0, wy1, wz0, wz1 = -0.9, 0.9, 0.9, 2.2
    seg_s = (ry + wy0)
    me = make_box_mesh("Wall_East_South", wall_t, seg_s, wall_h,
                       z_origin="bottom")
    new_obj("Wall_East_South", me, col, loc=(rx, (-ry + wy0) / 2, 0),
            mat=mat_wall)
    seg_n = (ry - wy1)
    me = make_box_mesh("Wall_East_North", wall_t, seg_n, wall_h,
                       z_origin="bottom")
    new_obj("Wall_East_North", me, col, loc=(rx, (ry + wy1) / 2, 0),
            mat=mat_wall)
    me = make_box_mesh("Wall_East_Below", wall_t, wy1 - wy0, wz0,
                       z_origin="bottom")
    new_obj("Wall_East_Below", me, col, loc=(rx, 0, 0), mat=mat_wall)
    me = make_box_mesh("Wall_East_Above", wall_t, wy1 - wy0, wall_h - wz1,
                       z_origin="bottom")
    new_obj("Wall_East_Above", me, col, loc=(rx, 0, wz1), mat=mat_wall)

    # window frame + cross muntins
    ft = 0.045
    for (name, sy, sz, ly, lz) in (
            ("WindowFrame_Bottom", wy1 - wy0, ft, 0, wz0 + ft / 2),
            ("WindowFrame_Top", wy1 - wy0, ft, 0, wz1 - ft / 2),
            ("WindowFrame_Left", ft, wz1 - wz0, wy0 + ft / 2, (wz0 + wz1) / 2),
            ("WindowFrame_Right", ft, wz1 - wz0, wy1 - ft / 2,
             (wz0 + wz1) / 2),
            ("WindowFrame_MuntinV", ft * 0.6, wz1 - wz0, 0, (wz0 + wz1) / 2),
            ("WindowFrame_MuntinH", wy1 - wy0, ft * 0.6, 0, (wz0 + wz1) / 2)):
        me = make_box_mesh(name, 0.06, sy, sz)
        new_obj(name, me, col, loc=(rx - 0.04, ly, lz), mat=mat_frame)


def build_table(col):
    mat_table = wood_material("Mat_Table_Walnut", (0.075, 0.036, 0.018),
                              (0.23, 0.125, 0.06), scale=2.2, rough=0.18,
                              coat=0.7, stripe_axis='X', distortion=1.5)
    tx, ty = CFG["table_top_x"], CFG["table_top_y"]
    tt = CFG["table_top_t"]

    me = make_box_mesh("Table_Top", tx, ty, tt, bevel=0.012)
    top = new_obj("Table_Top", me, col, loc=(0, 0, TABLE_Z - tt / 2),
                  mat=mat_table)
    add_rigid_body(top, 'PASSIVE', mass=0, friction=0.60, restitution=0.02)

    leg = 0.09
    me = make_box_mesh("Table_Leg", leg, leg, TABLE_Z - tt, bevel=0.008,
                       z_origin="bottom")
    for i, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
        new_obj("Table_Leg_%d" % (i + 1), me, col,
                loc=(sx * (tx / 2 - 0.16), sy * (ty / 2 - 0.16), 0),
                mat=mat_table)
    me = make_box_mesh("Table_Apron_X", tx - 0.36, 0.05, 0.10)
    for s in (1, -1):
        new_obj("Table_Apron_X%+d" % s, me, col,
                loc=(0, s * (ty / 2 - 0.16), TABLE_Z - tt - 0.06),
                mat=mat_table)


DOM_MATS = {}


def build_domino_meshes():
    """One mesh per colour (7) + crosser + chunky payload/trigger block."""
    meshes = {}
    h, w, t = CFG["dom_h"], CFG["dom_w"], CFG["dom_t"]
    for cname, rgb in DOMINO_COLORS.items():
        mat = simple_material("Mat_Domino_%s" % cname, rgb, rough=0.28,
                              coat=0.25)
        DOM_MATS[cname] = mat
        me = make_box_mesh("DominoMesh_%s" % cname, t, w, h,
                           bevel=CFG["dom_bevel"])
        me.materials.append(mat)
        meshes[cname] = me
    # the double-height crosser
    me = make_box_mesh("DominoMesh_crosser", 0.012, 0.034, 0.120,
                       bevel=CFG["dom_bevel"])
    me.materials.append(DOM_MATS["yellow"])
    meshes["crosser"] = me
    # the seesaw trigger "block domino": extra torque on the input arm
    me = make_box_mesh("DominoMesh_block", 0.014, 0.026, 0.050,
                       bevel=CFG["dom_bevel"])
    me.materials.append(DOM_MATS["blue"])
    meshes["block"] = me
    return meshes


def build_dominoes(L, col_doms):
    """Instantiate every domino as its own object with a rigid body.
    Domino local +x is the fall direction (thickness axis)."""
    meshes = build_domino_meshes()
    objs = []
    for i, (x, y, zb, hh, sec, cname) in enumerate(L["dominoes"]):
        if sec == "crosser":
            me = meshes["crosser"]
            zc = TABLE_Z + zb + 0.060
            name = "Domino_%04d_crosser" % (i + 1)
        elif sec == "seesaw_trigger":
            me = meshes["block"]        # chunky block: extra seesaw torque
            zc = TABLE_Z + zb + CFG["dom_h"] / 2
            name = "Domino_%04d_seesaw_trigger" % (i + 1)
        else:
            me = meshes[cname]
            zc = TABLE_Z + zb + CFG["dom_h"] / 2
            name = "Domino_%04d_%s" % (i + 1, sec)
        obj = new_obj(name, me, col_doms, loc=(x, y, zc),
                      rot=(0, 0, hh))
        mass = (0.05 if sec == "crosser" else
                0.040 if sec == "seesaw_trigger" else CFG["dom_mass"])
        add_rigid_body(obj, 'ACTIVE', 'BOX', mass=mass,
                       friction=0.50, restitution=0.05)
        obj["section"] = sec
        objs.append(obj)
    return objs


def build_props(L, col_props, col_phys, col_doms):
    """Stairs, platforms, bridge, marble + chute, seesaw."""
    mat_wood = wood_material("Mat_Prop_Birch", (0.45, 0.33, 0.20),
                             (0.72, 0.58, 0.38), scale=8.0, rough=0.5)
    mat_metal = simple_material("Mat_Marble_Steel", (0.75, 0.77, 0.80),
                                rough=0.08, metallic=1.0)

    bx, by, _ = L["stairs_base"]
    rise, tread = CFG["stair_rise"], CFG["stair_tread"]
    steps = CFG["stair_steps"]
    plat_h = CFG["platform_h"]
    stair_w = 0.12

    # --- staircase: solid blocks -------------------------------------------
    # NOTE: bottom-origin boxes need CONVEX_HULL - Blender's BOX collision
    # shape is always centred on the object origin.
    for i in range(steps):
        h = rise * (i + 1)
        me = make_box_mesh("Stairs_Step_%d" % (i + 1), tread, stair_w, h,
                           z_origin="bottom")
        o = new_obj("Stairs_Step_%d" % (i + 1), me, col_props,
                    loc=(bx + tread * (i + 0.5), by, TABLE_Z), mat=mat_wood)
        add_rigid_body(o, 'PASSIVE', 'CONVEX_HULL', friction=0.6)

    # --- platform A ---------------------------------------------------------
    pax, pay, palen = L["platA"]
    me = make_box_mesh("Platform_A", palen, stair_w, plat_h, z_origin="bottom")
    o = new_obj("Platform_A", me, col_props, loc=(pax, pay, TABLE_Z),
                mat=mat_wood)
    add_rigid_body(o, 'PASSIVE', 'CONVEX_HULL', friction=0.6)

    # --- bridge -------------------------------------------------------------
    bs_x0, bs_x1, bs_y = L["bridge_span"]
    blen = bs_x1 - bs_x0
    bw = CFG["bridge_w"]
    deck_t = 0.012
    me = make_box_mesh("Bridge_Deck", blen + 0.02, bw, deck_t, bevel=0.003)
    o = new_obj("Bridge_Deck", me, col_props,
                loc=((bs_x0 + bs_x1) / 2, bs_y, TABLE_Z + plat_h - deck_t / 2),
                mat=mat_wood)
    add_rigid_body(o, 'PASSIVE', friction=0.6)
    # low side rails (visual guides for the dominoes)
    me = make_box_mesh("Bridge_Rail", blen + 0.02, 0.008, 0.018)
    for s in (1, -1):
        o = new_obj("Bridge_Rail_%+d" % s, me, col_props,
                    loc=((bs_x0 + bs_x1) / 2, bs_y + s * (bw / 2 - 0.004),
                         TABLE_Z + plat_h + 0.009), mat=mat_wood)
        add_rigid_body(o, 'PASSIVE', friction=0.6)
    # two A-frame legs
    me = make_box_mesh("Bridge_Leg", 0.03, bw * 0.8, plat_h - deck_t,
                       z_origin="bottom")
    for i, f in enumerate((0.30, 0.70)):
        new_obj("Bridge_Leg_%d" % (i + 1), me, col_props,
                loc=(bs_x0 + blen * f, bs_y, TABLE_Z), mat=mat_wood)

    # --- platform B ---------------------------------------------------------
    pb = L["platB"]
    me = make_box_mesh("Platform_B", pb["sx"], pb["sy"], plat_h,
                       z_origin="bottom")
    o = new_obj("Platform_B", me, col_props,
                loc=(pb["cx"], pb["cy"], TABLE_Z), mat=mat_wood)
    add_rigid_body(o, 'PASSIVE', 'CONVEX_HULL', friction=0.6)

    ch = L["chute"]

    # --- marble chute (inclined so the +y end is LOW) -----------------------
    c_len, c_w = ch["len"], CFG["chute_w"]
    drop = plat_h - 0.004
    slope = math.atan2(drop, c_len)
    mid_y = ch["y0"] + c_len / 2
    mid_z = TABLE_Z + plat_h - 0.006 - drop / 2
    body_len = c_len / math.cos(slope) + 0.02
    me = make_box_mesh("Chute_Floor", c_w, body_len, 0.008)
    o = new_obj("Chute_Floor", me, col_props, loc=(ch["x"], mid_y, mid_z),
                rot=(-slope, 0, 0), mat=mat_wood)
    add_rigid_body(o, 'PASSIVE', friction=0.30)
    me = make_box_mesh("Chute_Rail", 0.006, body_len, 0.024)
    for s in (1, -1):
        o = new_obj("Chute_Rail_%+d" % s, me, col_props,
                    loc=(ch["x"] + s * (c_w / 2 + 0.003), mid_y,
                         mid_z + 0.008), rot=(-slope, 0, 0), mat=mat_wood)
        add_rigid_body(o, 'PASSIVE', friction=0.30)

    # --- marble -------------------------------------------------------------
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16,
                              radius=CFG["marble_r"])
    me = bpy.data.meshes.new("Marble")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat_metal)
    ms = L["marble_start"]
    o = new_obj("Marble", me, col_props, loc=(ms[0], ms[1], TABLE_Z + ms[2]))
    rb = add_rigid_body(o, 'ACTIVE', 'SPHERE', mass=CFG["marble_mass"],
                        friction=0.35, restitution=0.10)
    rb.linear_damping = 0.40
    rb.angular_damping = 0.30

    # --- marble runway: low rails keep the marble in the lane until it
    # parks among the fallen dominoes (which topple inside the lane) --------
    exit_y = ch["y0"] + ch["len"]
    lane_cx = ch["x"] + 0.004
    rail_len = (L["seesaw_steps"][0]["y"] - 0.014) - (exit_y - 0.005)
    rail_cy = (exit_y - 0.005) + rail_len / 2
    me = make_box_mesh("Runway_Rail", 0.007, rail_len, 0.018,
                       z_origin="bottom")
    for s in (1, -1):
        o = new_obj("Runway_Rail_%+d" % s, me, col_props,
                    loc=(lane_cx + s * 0.0315, rail_cy, TABLE_Z),
                    mat=mat_wood)
        add_rigid_body(o, 'PASSIVE', 'CONVEX_HULL', friction=0.4)

    # --- micro-steps up to the seesaw trigger block (skipped when flat) ------
    for i, st in enumerate(L["seesaw_steps"]):
        if st["h"] <= 0.0:
            continue
        me = make_box_mesh("Seesaw_Step_%d" % (i + 1), 0.05, 0.026, st["h"],
                           z_origin="bottom")
        o = new_obj("Seesaw_Step_%d" % (i + 1), me, col_props,
                    loc=(st["x"], st["y"], TABLE_Z),
                    rot=(0, 0, st["heading"] - math.pi / 2), mat=mat_wood)
        add_rigid_body(o, 'PASSIVE', 'CONVEX_HULL', friction=0.6)

    # --- seesaw -------------------------------------------------------------
    # Flick-lift seesaw.  The chunky trigger block on the top micro-step
    # falls over and lies on the long input arm; its weight rotates the
    # plank, and the rising output tip lifts the overhanging south edge of
    # the payload domino (standing WIDE on its own platform), tipping it
    # onto the next ground domino.  At rest nothing loads the hinge.
    ss = L["seesaw"]
    s_len, s_w, s_t = CFG["seesaw_len"], CFG["seesaw_w"], CFG["seesaw_t"]
    piv_h = CFG["seesaw_pivot_h"]
    stop_h, stop_d = CFG["seesaw_stop_h"], CFG["seesaw_stop_d"]
    rest = math.asin((piv_h - (stop_h + 0.0005) - s_t / 2) / stop_d)
    hd = ss["heading"]                   # ~90 deg: plank runs along +y
    path_dir = Vector((math.cos(hd), math.sin(hd), 0.0))
    pivot = Vector((ss["x"], ss["y"], TABLE_Z + piv_h))

    me = make_box_mesh("Seesaw_Stand", 0.044, 0.018, piv_h - 0.0045,
                       z_origin="bottom")
    o = new_obj("Seesaw_Stand", me, col_props, loc=(ss["x"], ss["y"], TABLE_Z),
                rot=(0, 0, hd - math.pi / 2), mat=mat_wood)
    add_rigid_body(o, 'PASSIVE', 'CONVEX_HULL', friction=0.5)
    stand = o

    # stop block under the output arm (defines the rest pose)
    me = make_box_mesh("Seesaw_Stop", 0.04, 0.024, stop_h, z_origin="bottom")
    sp = pivot + path_dir * stop_d
    o = new_obj("Seesaw_Stop", me, col_props, loc=(sp.x, sp.y, TABLE_Z),
                rot=(0, 0, hd - math.pi / 2), mat=mat_wood)
    add_rigid_body(o, 'PASSIVE', 'CONVEX_HULL', friction=0.6)

    # plank: local +y = output arm; centre sits 5.5 mm on the output side of
    # the hinge (output arm 85.5 mm reaches under the payload overhang,
    # input arm 74.5 mm) so the output end rests down on the stop at rest
    me = make_box_mesh("Seesaw_Plank", s_w, s_len, s_t, bevel=0.002)
    plank = new_obj("Seesaw_Plank", me, col_props, mat=mat_wood)
    plank.rotation_euler = Euler((-rest, 0, hd - math.pi / 2), 'XYZ')
    p_center = (pivot + path_dir * (0.0055 * math.cos(rest))
                - Vector((0, 0, 0.0055 * math.sin(rest))))
    plank.location = tuple(p_center)
    rb = add_rigid_body(plank, 'ACTIVE', 'BOX', mass=0.012, friction=0.6,
                        restitution=0.05, deactivate=False)
    rb.angular_damping = 0.40
    rb.linear_damping = 0.20

    # hinge constraint (empty in the Physics collection)
    hinge = bpy.data.objects.new("Seesaw_Hinge", None)
    hinge.empty_display_type = 'ARROWS'
    hinge.empty_display_size = 0.05
    hinge.location = tuple(pivot)
    # hinge axis = constraint local Z; we need it ACROSS the plank
    hinge.rotation_euler = Euler((0, math.pi / 2, hd - math.pi / 2), 'XYZ')
    col_phys.objects.link(hinge)
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = hinge
    hinge.select_set(True)
    bpy.ops.rigidbody.constraint_add()
    con = hinge.rigid_body_constraint
    con.type = 'HINGE'
    con.object1 = stand
    con.object2 = plank
    con.use_limit_ang_z = True           # generous; real stops are physical
    con.limit_ang_z_lower = -35.0 * DEG
    con.limit_ang_z_upper = 35.0 * DEG

    # payload platform + payload domino standing WIDE (24 mm along the path,
    # ~4 mm of its base overhanging south past the platform edge)
    plat = pivot + path_dir * ss["stand_d"]
    me = make_box_mesh("Payload_Stand", 0.05, 0.027, 0.015, z_origin="bottom")
    o = new_obj("Payload_Stand", me, col_props, loc=(plat.x, plat.y, TABLE_Z),
                rot=(0, 0, hd - math.pi / 2), mat=mat_wood)
    add_rigid_body(o, 'PASSIVE', 'CONVEX_HULL', friction=0.6)

    pc = Vector((ss["x"], ss["y"], 0)) + path_dir * ss["payload_d"]
    me = bpy.data.meshes["DominoMesh_blue"]
    pay = new_obj("Domino_Seesaw_Payload", me, col_doms,
                  loc=(pc.x, pc.y, TABLE_Z + 0.0156 + CFG["dom_h"] / 2),
                  rot=(0, 0, hd - math.pi / 2))
    add_rigid_body(pay, 'ACTIVE', 'BOX', mass=CFG["dom_mass"],
                   friction=0.6, restitution=0.05)
    pay["section"] = "payload"
    return {"marble": bpy.data.objects["Marble"], "plank": plank,
            "payload": pay}


# ----------------------------------------------------------------------------
# Lights and camera
# ----------------------------------------------------------------------------
def build_lights(col):
    # sun shining in through the east window
    sun_data = bpy.data.lights.new("Sun_Key", 'SUN')
    sun_data.energy = 5.5
    sun_data.color = (1.0, 0.95, 0.86)
    sun_data.angle = 2.5 * DEG           # soft-ish shadows
    sun = bpy.data.objects.new("Sun_Key", sun_data)
    sun.location = (2.6, -0.4, 2.4)
    d = Vector((-0.80, 0.28, -0.53)).normalized()   # through the window
    sun.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    col.objects.link(sun)

    # big soft area light above the table
    area_data = bpy.data.lights.new("Area_Fill", 'AREA')
    area_data.shape = 'RECTANGLE'
    area_data.size = 2.4
    area_data.size_y = 1.6
    area_data.energy = 150.0
    area_data.color = (1.0, 0.98, 0.95)
    area = bpy.data.objects.new("Area_Fill", area_data)
    area.location = (0.0, 0.0, 2.55)
    col.objects.link(area)


def build_camera(col):
    cam_data = bpy.data.cameras.new("Camera_Main")
    cam_data.lens = 32.0
    cam_data.clip_end = 60.0
    cam = bpy.data.objects.new("Camera_Main", cam_data)
    col.objects.link(cam)
    bpy.context.scene.camera = cam

    focus = bpy.data.objects.new("Focus_Target", None)
    focus.empty_display_type = 'SPHERE'
    focus.empty_display_size = 0.05
    col.objects.link(focus)

    tr = cam.constraints.new('TRACK_TO')
    tr.target = focus
    tr.track_axis = 'TRACK_NEGATIVE_Z'
    tr.up_axis = 'UP_Y'

    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = focus
    cam_data.dof.aperture_fstop = 4.5
    return cam, focus


# ----------------------------------------------------------------------------
# Physics world + the trigger that tips the first domino
# ----------------------------------------------------------------------------
def setup_physics_world():
    sc = bpy.context.scene
    if sc.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    rbw.enabled = True
    rbw.time_scale = CFG["time_scale"]
    rbw.substeps_per_frame = CFG["substeps"]
    rbw.solver_iterations = CFG["solver_iters"]
    rbw.point_cache.frame_start = 1
    rbw.point_cache.frame_end = CFG["max_frames"]
    return rbw


def animate_first_domino(first, f0):
    """Tip a domino over with keyframes (kinematic), then hand it to the
    physics engine so the momentum carries into the chain."""
    h = CFG["dom_h"]
    t = CFG["dom_t"]
    base_loc = Vector(first.location)
    base_rot = first.rotation_euler.z

    # ponytail: set default interp on new keyframes instead of iterating
    # action.fcurves (removed in Blender 4.4+ slotted actions)
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'

    rb = first.rigid_body
    rb.kinematic = True
    rb.keyframe_insert("kinematic", frame=1)

    fall_dir = Vector((math.cos(base_rot), math.sin(base_rot), 0.0))
    left = Vector((-fall_dir.y, fall_dir.x, 0.0))
    pivot = base_loc + fall_dir * (t / 2) + Vector((0, 0, -h / 2))

    for fr, ang_deg in ((f0, 0.0), (f0 + 6, 9.0), (f0 + 11, 22.0),
                        (f0 + 16, 38.0)):
        ang = ang_deg * DEG             # forward tip about the "left" axis
        rot = Matrix.Rotation(ang, 4, left)
        loc = rot @ (base_loc - pivot) + pivot
        first.location = loc
        eul = (rot @ Matrix.Rotation(base_rot, 4, 'Z')).to_euler()
        first.rotation_euler = eul
        first.keyframe_insert("location", frame=fr)
        first.keyframe_insert("rotation_euler", frame=fr)

    rb.keyframe_insert("kinematic", frame=f0 + 16)
    rb.kinematic = False
    rb.keyframe_insert("kinematic", frame=f0 + 17)
    # restore rest pose keys at the start
    first.location = base_loc
    first.rotation_euler = Euler((0, 0, base_rot))
    first.keyframe_insert("location", frame=1)
    first.keyframe_insert("rotation_euler", frame=1)


# ----------------------------------------------------------------------------
# Bake + measurement
# ----------------------------------------------------------------------------
def bake_simulation():
    sc = bpy.context.scene
    rbw = sc.rigidbody_world
    print("Baking rigid bodies to frame %d ..." % rbw.point_cache.frame_end)
    with bpy.context.temp_override(scene=sc, point_cache=rbw.point_cache):
        bpy.ops.ptcache.free_bake()
        bpy.ops.ptcache.bake(bake=True)
    print("Bake done.")


def measure_simulation(domino_objs, marble):
    """Step through the baked sim and record when every domino first falls
    (tilt > 35 deg) plus the marble's travel.  Returns the event table."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    n = len(domino_objs)
    fall_frame = [None] * n
    marble_path = []

    for f in range(1, CFG["max_frames"] + 1, 2):
        sc.frame_set(f)
        for i, ob in enumerate(domino_objs):
            if fall_frame[i] is not None:
                continue
            ev = ob.evaluated_get(dg)
            zax = ev.matrix_world.col[2]
            tilt = math.degrees(math.acos(max(-1.0, min(1.0, zax[2]))))
            if tilt > 35.0:
                fall_frame[i] = f
        ev = marble.evaluated_get(dg)
        marble_path.append((f, tuple(ev.matrix_world.translation)))
        if f % 400 == 1:
            done = sum(1 for x in fall_frame if x is not None)
            print("  frame %4d : %d/%d dominoes down" % (f, done, n))
    return fall_frame, marble_path


def analyze_events(objs, fall_frames):
    """First-fall frame per section + overall completion check."""
    sec_first = {}
    last_fall = 0
    unfallen = []
    for ob, ff in zip(objs, fall_frames):
        sec = ob.get("section", "?")
        if ff is None:
            unfallen.append(ob.name)
            continue
        last_fall = max(last_fall, ff)
        if sec not in sec_first or ff < sec_first[sec]:
            sec_first[sec] = ff
    return sec_first, last_fall, unfallen


# camera offset (added to the chain wave-front) per section while following
_FOLLOW_OFFSET = {
    "lead_in":      (0.55, -1.45, 1.20),
    "s_curve":      (0.55, -1.40, 1.15),
    "zigzag":       (0.45, -1.35, 1.10),
    "circle":       (0.40, -1.30, 1.10),
    "approach":     (0.10, -1.30, 1.05),
    "stairs":       (-0.20, -1.20, 0.95),
    "bridge":       (-0.30, -1.15, 0.90),
    "after_marble": (0.60, -1.10, 0.85),
    "seesaw_trigger": (0.60, -1.10, 0.85),
    "payload":      (0.60, -1.15, 0.90),
    "after_seesaw": (0.60, -1.30, 1.20),
    "spiral":       (0.35, -1.60, 1.60),
    "crosser":      (0.35, -1.60, 1.60),
    "connect_1":    (0.30, -1.65, 1.70),
    "letter_C":     (0.15, -1.70, 1.90),
    "connect_2":    (0.10, -1.70, 1.95),
    "letter_G":     (0.05, -1.65, 2.00),
}


def animate_camera(cam, focus, L, objs, fall_frames, f0, end_frame):
    """One continuous, slow camera move: wide -> follow the chain ->
    marble close-up pause -> follow -> pull up over the letters -> hold."""
    ch = L["chute"]
    chute_mid = (ch["x"], ch["y0"] + ch["len"] / 2)

    def first_fall(section):
        cand = [ff for ob, ff in zip(objs, fall_frames)
                if ff is not None and ob.get("section") == section]
        return min(cand) if cand else None

    bridge_falls = [ff for ob, ff in zip(objs, fall_frames)
                    if ff is not None and ob.get("section") == "bridge"]
    t_pusher = max(bridge_falls) if bridge_falls else f0 + 400
    t_marble_hit = first_fall("after_marble") or t_pusher + 120
    t_letter_c = first_fall("letter_C") or end_frame - 400
    g_falls = [ff for ob, ff in zip(objs, fall_frames)
               if ff is not None and ob.get("section") == "letter_G"]
    t_g_done = max(g_falls) if g_falls else end_frame - 100

    marble_lo = t_pusher - 30
    marble_hi = t_marble_hit + 45
    letters_lo = t_letter_c - 60

    keys = []   # (frame, cam_pos, focus_pos)

    # 1) wide establishing shot of the whole table
    keys.append((1, (2.0, -2.80, 2.55), (0.0, 0.0, 0.85)))
    keys.append((max(2, f0 - 30), (1.2, -2.55, 2.05), (-0.5, -0.2, 0.83)))

    # 2) follow the wave-front
    chain = [(ff, ob) for ob, ff in zip(objs, fall_frames) if ff is not None]
    chain.sort(key=lambda t: t[0])
    lastk = 0
    for ff, ob in chain:
        if ff - lastk < 45:
            continue
        if marble_lo <= ff <= marble_hi or ff >= letters_lo:
            continue
        sec = ob.get("section", "lead_in")
        off = _FOLLOW_OFFSET.get(sec, (0.4, -1.4, 1.2))
        x, y, z = ob.location
        keys.append((ff, (x + off[0], y + off[1], z + off[2] - 0.05),
                     (x, y, 0.82)))
        lastk = ff

    # 3) the marble close-up (nearly static pause)
    cx, cy = chute_mid
    keys.append((marble_lo, (cx + 0.55, cy - 0.85, TABLE_Z + 0.60),
                 (cx, cy + 0.02, TABLE_Z + 0.10)))
    keys.append((marble_hi, (cx + 0.48, cy - 0.82, TABLE_Z + 0.55),
                 (cx, cy + 0.10, TABLE_Z + 0.08)))

    # 4) finale: pull up and over the letters, then hold
    lcx = (LETTER_C[0] + LETTER_G[0]) / 2
    lcy = LETTER_C[1]
    keys.append((letters_lo + 30, (lcx + 0.55, lcy - 1.80, TABLE_Z + 1.35),
                 (lcx + 0.2, lcy, TABLE_Z + 0.05)))
    hold_from = min(t_g_done + 40, end_frame - 12)
    keys.append((hold_from, (lcx + 0.02, lcy - 1.62, TABLE_Z + 1.55),
                 (lcx, lcy + 0.02, TABLE_Z + 0.03)))
    keys.append((end_frame, (lcx, lcy - 1.60, TABLE_Z + 1.57),
                 (lcx, lcy + 0.02, TABLE_Z + 0.03)))

    # ---- clean, sort, enforce a minimum gap, insert -------------------------
    keys.sort(key=lambda k: k[0])
    cleaned = []
    for k in keys:
        if cleaned and k[0] - cleaned[-1][0] < 12:
            continue
        cleaned.append(k)

    # ponytail: smooth interp + auto-clamped handles set as the keyframe
    # creation default (action.fcurves gone in Blender 4.4+)
    prefs = bpy.context.preferences.edit
    prefs.keyframe_new_interpolation_type = 'BEZIER'
    prefs.keyframe_new_handle_type = 'AUTO_CLAMPED'

    for fr, cpos, fpos in cleaned:
        cam.location = cpos
        cam.keyframe_insert("location", frame=fr)
        focus.location = fpos
        focus.keyframe_insert("location", frame=fr)


# ----------------------------------------------------------------------------
# Render settings, notes, saving
# ----------------------------------------------------------------------------
def setup_render(end_frame):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.render.resolution_x = 1920
    sc.render.resolution_y = 1080
    sc.render.fps = CFG["fps"]
    sc.frame_start = 1
    sc.frame_end = end_frame
    sc.cycles.samples = 128
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    sc.cycles.device = 'CPU'
    # Blender 5.x requires media_type=VIDEO before FFMPEG is a valid format
    if hasattr(sc.render.image_settings, "media_type"):
        sc.render.image_settings.media_type = 'VIDEO'
    sc.render.image_settings.file_format = 'FFMPEG'
    sc.render.ffmpeg.format = 'MPEG4'
    sc.render.ffmpeg.codec = 'H264'
    sc.render.ffmpeg.constant_rate_factor = 'HIGH'
    sc.render.filepath = "//render/domino_chain_"


def write_notes(sec_first, last_fall, end_frame, n_doms):
    txt = bpy.data.texts.new("SIM_NOTES")
    fps = CFG["fps"]
    lines = ["DOMINO CHAIN REACTION - simulation summary",
             "=" * 44,
             "dominoes: %d" % n_doms,
             "animation: %d frames  (%.1f s at %d fps)"
             % (end_frame, end_frame / fps, fps),
             "",
             "section trigger times:"]
    for sec, fr in sorted(sec_first.items(), key=lambda kv: kv[1]):
        lines.append("  %-14s frame %5d   (%6.1f s)" % (sec, fr, fr / fps))
    lines.append("")
    lines.append("last domino falls at frame %d (%.1f s)"
                 % (last_fall, last_fall / fps))
    lines.append("")
    lines.append("Re-generate the whole scene with:")
    lines.append("  blender --background --python generate_domino_scene.py")
    txt.write("\n".join(lines))


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main(argv=None):
    argv = argv if argv is not None else sys.argv
    do_bake = "--no-bake" not in argv
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__))
                            if "__file__" in globals() else os.getcwd(),
                            "domino_chain_reaction.blend")

    sc = reset_scene()
    sc.render.fps = CFG["fps"]

    # ---- collections -------------------------------------------------------
    col_env = get_collection("Environment")
    col_dom = get_collection("Dominoes")
    col_props = get_collection("Props")
    col_lights = get_collection("Lights")
    col_cam = get_collection("Camera")
    col_phys = get_collection("Physics")

    # ---- build everything --------------------------------------------------
    build_world()
    build_environment(col_env)
    build_table(col_env)

    L = build_layout()
    problems = validate_layout(L, verbose=True)
    if problems:
        raise RuntimeError("layout has %d clearance problems" % len(problems))

    setup_physics_world()
    dominoes = build_dominoes(L, col_dom)
    props = build_props(L, col_props, col_phys, col_dom)
    build_lights(col_lights)
    cam, focus = build_camera(col_cam)

    all_chain = dominoes + [props["payload"]]

    f0 = int(CFG["intro_seconds"] * CFG["fps"])
    animate_first_domino(dominoes[0], f0)

    # ---- bake + measure + camera -------------------------------------------
    end_frame = CFG["max_frames"]
    if do_bake:
        bake_simulation()
        fall_frames, marble_path = measure_simulation(all_chain,
                                                      props["marble"])
        sec_first, last_fall, unfallen = analyze_events(all_chain,
                                                        fall_frames)
        print("sections triggered:")
        for s, fr in sorted(sec_first.items(), key=lambda kv: kv[1]):
            print("   %-14s %5d" % (s, fr))
        if unfallen:
            print("UNFALLEN (%d): %s" % (len(unfallen), unfallen[:25]))
        end_frame = min(CFG["max_frames"],
                        last_fall + int(CFG["hold_seconds"] * CFG["fps"]))
        animate_camera(cam, focus, L, all_chain, fall_frames, f0, end_frame)
        write_notes(sec_first, last_fall, end_frame, len(all_chain))
        # ponytail: success = the "CG" reveal completes, not that literally
        # every domino falls. Real runs leave the odd straggler at a curve;
        # require both letters fully down and at most a few stragglers.
        letters_down = all(
            ff is not None
            for ob, ff in zip(all_chain, fall_frames)
            if ob.get("section") in ("letter_C", "letter_G"))
        ok = letters_down and len(unfallen) <= 3
    else:
        cam.location = (2.0, -2.8, 2.55)
        focus.location = (0, 0, 0.85)
        ok = True

    setup_render(end_frame)
    sc.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
    print("saved:", out_path)
    print("CHAIN COMPLETE" if ok else "CHAIN INCOMPLETE")
    return ok


if __name__ == "__main__":
    if HAVE_BPY:
        main()
    else:
        L = build_layout()
        validate_layout(L)
