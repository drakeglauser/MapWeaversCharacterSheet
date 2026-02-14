# damage_lab.py
import math
import re
import tkinter as tk
from tkinter import ttk


ABILITY_MODS = {
    "core":  {"dmg": 1.50, "mana": 0.75},
    "inner": {"dmg": 1.00, "mana": 1.00},
    "outer": {"dmg": 0.75, "mana": 2.00},
}

TARGET_MULTS = {
    "Normal (x1.0)": 1.0,
    "Resistant (x0.5)": 0.5,
    "Weak (x1.5)": 1.5,
    "Vulnerable (x2.0)": 2.0,
}

def parse_damage_expr(expr: str):
    """
    Parses: '1d10', '2d6+3', '3d8-2'
    Returns (dice_count, die_size, flat_bonus) or None if no dice found.
    """
    if not expr:
        return None
    s = expr.replace(" ", "").lower()
    m = re.search(r'(\d*)d(\d+)', s)
    if not m:
        return None
    dice_count = int(m.group(1)) if m.group(1) else 1
    die_size = int(m.group(2))
    flat_bonus = 0
    rest = s[m.end():]
    for sign, num in re.findall(r'([+-])(\d+)', rest):
        flat_bonus += int(num) if sign == '+' else -int(num)
    return dice_count, die_size, flat_bonus


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def mana_density_multiplier(points: int) -> float:
    try:
        p = int(points)
    except Exception:
        p = 0
    p = max(0, p)

    if p <= 100:
        return 1.0 + (p / 100.0)

    return 2.0 + (math.log(p / 100.0) / math.log(100.0))

def max_pbd_factor_for_die(die_size: int) -> float:
    """
    Piecewise mapping:
      d4  -> 0.50
      d10 -> 1.00
      d20 -> 2.111... (so 18/20 -> ~1.9x)
    Interpolates for others.
    """
    anchors = [(4, 0.50), (10, 1.00), (20, 2.1111111111)]
    if die_size <= anchors[0][0]:
        return anchors[0][1]
    if die_size >= anchors[-1][0]:
        return anchors[-1][1]
    for (d0, f0), (d1, f1) in zip(anchors, anchors[1:]):
        if d0 <= die_size <= d1:
            t = (die_size - d0) / (d1 - d0)
            return f0 + t * (f1 - f0)
    return 1.0


def compute_overcast_bonus(base_eff: int, spent_eff: int, over: dict) -> int:
    """
    log-ish scaling:
      bonus = floor(scale * (log2(spent/base))^power), capped
    """
    if base_eff <= 0 or spent_eff <= base_eff:
        return 0
    if not isinstance(over, dict) or not over.get("enabled", False):
        return 0

    try:
        scale = int(over.get("scale", 0) or 0)
    except Exception:
        scale = 0
    try:
        power = float(over.get("power", 0.85) or 0.85)
    except Exception:
        power = 0.85
    try:
        cap = int(over.get("cap", 999) or 999)
    except Exception:
        cap = 999

    if scale <= 0:
        return 0

    ratio = spent_eff / base_eff
    x = math.log(ratio, 2.0)  # 1 at 2x, 2 at 4x, etc.
    bonus = int(math.floor(scale * (x ** power)))
    if cap >= 0:
        bonus = min(bonus, cap)
    return max(0, bonus)


class DamageLabTab(ttk.Frame):
    """
    A Tkinter tab that graphs damage for a selected action.
    Expects:
      get_actions(): returns list of dicts like your combat_actions
         each action dict must include: kind ('item' or 'ability'), ref (dict), display, slot (for abilities)
      get_pbd(): returns current PBD int from app
      get_precision(): returns current Precision int from app
    """
    def __init__(self, parent, get_actions, get_pbd, get_mana_density, get_precision=None):
        super().__init__(parent)
        self.get_actions = get_actions
        self.get_pbd = get_pbd
        self.get_mana_density = get_mana_density
        self.get_precision = get_precision or (lambda: 0)

        self.actions = []
        self.selected_ref = None
        self.selected_kind = None
        self.selected_slot = None

        # UI vars
        self.var_mode = tk.StringVar(value="Damage vs Roll")
        self.var_target_mult = tk.StringVar(value="Normal (x1.0)")
        self.var_crit = tk.BooleanVar(value=False)

        self.var_roll_custom = tk.StringVar(value="")      # used in some modes
        self.var_mana_spend = tk.StringVar(value="")       # for abilities
        self.var_pbd_override = tk.StringVar(value="")     # optional

        self.var_mana_max_x = tk.StringVar(value="4")      # mana plot: up to base*X
        self.var_roll_profile = tk.StringVar(value="Average")  # mana plot uses Average/Max/Custom roll

        self.var_info = tk.StringVar(value="Select an item/ability.")

        # Theme colors (set by parent via apply_theme)
        self._colors = None

        self._build_ui()
        self.refresh_actions()

    def _build_ui(self):
        outer = ttk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left = ttk.Frame(outer)
        right = ttk.Frame(outer)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ---- Left list ----
        ttk.Label(left, text="Pick an Item / Ability").pack(anchor="w")
        self.lb = tk.Listbox(left, height=22, width=38)
        self.lb.pack(fill=tk.BOTH, expand=True)
        self.lb.bind("<<ListboxSelect>>", lambda _e: self.on_select())

        ttk.Button(left, text="Refresh list", command=self.refresh_actions).pack(fill=tk.X, pady=(8, 0))

        # ---- Right controls + canvas ----
        controls = ttk.LabelFrame(right, text="Test & Plot Controls")
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="Plot mode:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Combobox(
            controls,
            textvariable=self.var_mode,
            values=["Damage vs Roll", "Damage vs Mana"],
            state="readonly",
            width=18
        ).grid(row=0, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(controls, text="Target modifier:").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        ttk.Combobox(
            controls,
            textvariable=self.var_target_mult,
            values=list(TARGET_MULTS.keys()),
            state="readonly",
            width=18
        ).grid(row=0, column=3, sticky="w", padx=6, pady=6)

        ttk.Checkbutton(controls, text="Crit (x2 total)", variable=self.var_crit).grid(
            row=0, column=4, sticky="w", padx=6, pady=6
        )

        ttk.Separator(controls, orient="horizontal").grid(
            row=1, column=0, columnspan=5, sticky="ew", padx=6, pady=(2, 8)
        )

        # Row: roll + mana + overrides
        ttk.Label(controls, text="Rolled damage (custom):").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(controls, textvariable=self.var_roll_custom, width=10).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(controls, text="Mana spend (abilities):").grid(row=2, column=2, sticky="w", padx=6, pady=4)
        ttk.Entry(controls, textvariable=self.var_mana_spend, width=10).grid(row=2, column=3, sticky="w", padx=6, pady=4)

        ttk.Label(controls, text="PBD/Precision override (blank=use sheet):").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(controls, textvariable=self.var_pbd_override, width=10).grid(row=3, column=1, sticky="w", padx=6, pady=4)

        # Mana plot extras
        ttk.Label(controls, text="Mana plot: max = base *").grid(row=3, column=2, sticky="w", padx=6, pady=4)
        ttk.Entry(controls, textvariable=self.var_mana_max_x, width=10).grid(row=3, column=3, sticky="w", padx=6, pady=4)

        ttk.Label(controls, text="Mana plot roll:").grid(row=2, column=4, sticky="w", padx=6, pady=4)
        ttk.Combobox(
            controls,
            textvariable=self.var_roll_profile,
            values=["Average", "Max", "Custom"],
            state="readonly",
            width=10
        ).grid(row=3, column=4, sticky="w", padx=6, pady=4)

        btns = ttk.Frame(controls)
        btns.grid(row=4, column=0, columnspan=5, sticky="ew", padx=6, pady=(8, 8))
        ttk.Button(btns, text="Plot", command=self.plot).pack(side=tk.LEFT)
        ttk.Button(btns, text="Compute 1 test", command=self.compute_one).pack(side=tk.LEFT, padx=8)
        ttk.Label(btns, textvariable=self.var_info, foreground="gray").pack(side=tk.LEFT, padx=8)

        # ---- Canvas ----
        canvas_frame = ttk.LabelFrame(right, text="Damage Graph")
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.canvas = tk.Canvas(canvas_frame, height=320)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    # ---------- Theme ----------
    def apply_theme(self, colors: dict):
        """Apply theme colors to raw tk widgets in this tab."""
        self._colors = colors
        self.lb.configure(
            bg=colors["entry_bg"], fg=colors["entry_fg"],
            selectbackground=colors["select_bg"],
            selectforeground=colors["select_fg"],
        )
        self.canvas.configure(bg=colors["canvas_bg"])
        # Re-draw the canvas with new colors if we have data
        if self.selected_ref is not None:
            self.plot()

    # ---------- Action list ----------
    def refresh_actions(self):
        actions = self.get_actions() or []
        self.actions = actions

        self.lb.delete(0, tk.END)
        for a in self.actions:
            self.lb.insert(tk.END, a.get("display", a.get("name", "")))

        # try to keep selection
        if self.selected_ref is not None:
            for i, a in enumerate(self.actions):
                if a.get("ref") is self.selected_ref and a.get("kind") == self.selected_kind:
                    self.lb.selection_set(i)
                    self.lb.see(i)
                    break

    def on_select(self):
        sel = list(self.lb.curselection())
        if len(sel) != 1:
            self.selected_ref = None
            self.selected_kind = None
            self.selected_slot = None
            self.var_info.set("Select an item/ability.")
            return

        a = self.actions[sel[0]]
        self.selected_ref = a.get("ref")
        self.selected_kind = a.get("kind")
        self.selected_slot = a.get("slot")

        ref = self.selected_ref or {}
        dmg = ref.get("damage", "")
        rt = ref.get("roll_type", "None")
        extra = ""

        if self.selected_kind == "ability":
            extra = f" | base mana: {ref.get('mana_cost', 0)} | slot: {self.selected_slot}"
            if self.var_mana_spend.get().strip() == "":
                self.var_mana_spend.set(str(ref.get("mana_cost", 0)))

        self.var_info.set(f"{rt} | dmg: {dmg}{extra}")
        self.plot()

    # ---------- Core compute ----------
    def _get_target_mult(self) -> float:
        return float(TARGET_MULTS.get(self.var_target_mult.get(), 1.0))

    def _get_pbd_value(self) -> int:
        s = self.var_pbd_override.get().strip()
        if s:
            try:
                return int(s)
            except ValueError:
                return self.get_pbd()
        return self.get_pbd()

    def _get_precision_value(self) -> int:
        s = self.var_pbd_override.get().strip()
        if s:
            try:
                return int(s)
            except ValueError:
                return self.get_precision()
        return self.get_precision()

    def _compute_damage(self, rolled_total: int, mana_spend_base: int) -> int:
        """Returns final damage after modifiers."""
        if self.selected_ref is None:
            return 0

        ref = self.selected_ref
        dmg_expr = (ref.get("damage") or "").strip()
        parsed = parse_damage_expr(dmg_expr)
        if parsed is None:
            dice_count, die_size, flat_bonus = (1, 10, 0)
        else:
            dice_count, die_size, flat_bonus = parsed

        base = int(rolled_total) + int(flat_bonus)

        # Items: apply PBD/Precision as multiplier (same formula as mana density)
        if self.selected_kind == "item":
            total = base
            if bool(ref.get("apply_bonus", ref.get("apply_pbd", True))):
                is_ranged = bool(ref.get("is_ranged", False))
                pts = self._get_precision_value() if is_ranged else self._get_pbd_value()
                mult = mana_density_multiplier(pts)
                total = int(math.floor(base * mult))
        else:
            # Abilities: NO PBD. Apply slot multipliers + overcast
            slot = self.selected_slot or "inner"
            mods = ABILITY_MODS.get(slot, {"dmg": 1.0, "mana": 1.0})
            dmg_mult = float(mods["dmg"])
            mana_mult = float(mods["mana"])

            base_cost = int(ref.get("mana_cost", 0) or 0)
            if base_cost <= 0:
                return 0

            if mana_spend_base < base_cost:
                mana_spend_base = base_cost

            base_eff = int(math.ceil(base_cost * mana_mult))
            spent_eff = int(math.ceil(mana_spend_base * mana_mult))
            md_pts = 0
            try:
                md_pts = int(self.get_mana_density() or 0)
            except Exception:
                md_pts = 0
            md_mult = mana_density_multiplier(md_pts)


            over = ref.get("overcast", {}) if isinstance(ref.get("overcast", {}), dict) else {}
            over_bonus = compute_overcast_bonus(base_eff, spent_eff, over)

            total = int(math.floor((base + over_bonus) * dmg_mult * md_mult))


        # Target multiplier (resist/weak/vuln)
        total = int(math.floor(total * self._get_target_mult()))

        # Crit doubles total
        if self.var_crit.get():
            total *= 2

        return max(0, total)

    # ---------- Plot helpers ----------
    def _canvas_plot_line(self, xs, ys, title: str, xlabel: str, ylabel: str):
        c = self.canvas
        c.delete("all")

        # Theme-aware colors
        fg = self._colors["canvas_fg"] if self._colors else "black"
        line_color = self._colors["canvas_line"] if self._colors else "black"

        w = max(300, c.winfo_width())
        h = max(240, c.winfo_height())

        # margins
        ml, mr, mt, mb = 60, 20, 30, 45
        plot_w = max(1, w - ml - mr)
        plot_h = max(1, h - mt - mb)

        if not xs or not ys or len(xs) != len(ys):
            c.create_text(w // 2, h // 2, text="No data to plot.", fill=fg)
            return

        x_min, x_max = min(xs), max(xs)
        y_min, y_max = 0, max(ys)

        if x_max == x_min:
            x_max = x_min + 1
        if y_max <= 0:
            y_max = 1

        # padding
        y_max = int(math.ceil(y_max * 1.10))

        def x_to_px(x):
            return ml + (x - x_min) * plot_w / (x_max - x_min)

        def y_to_px(y):
            return mt + (y_max - y) * plot_h / (y_max - y_min)

        # axes
        c.create_line(ml, mt, ml, mt + plot_h, fill=fg)                  # y-axis
        c.create_line(ml, mt + plot_h, ml + plot_w, mt + plot_h, fill=fg) # x-axis

        # ticks
        for i in range(6):
            tx = x_min + (x_max - x_min) * i / 5
            px = x_to_px(tx)
            c.create_line(px, mt + plot_h, px, mt + plot_h + 5, fill=fg)
            c.create_text(px, mt + plot_h + 18, text=str(int(round(tx))), font=("Segoe UI", 9), fill=fg)

        for i in range(6):
            ty = y_min + (y_max - y_min) * i / 5
            py = y_to_px(ty)
            c.create_line(ml - 5, py, ml, py, fill=fg)
            c.create_text(ml - 12, py, text=str(int(round(ty))), anchor="e", font=("Segoe UI", 9), fill=fg)

        # labels
        c.create_text(w // 2, 14, text=title, font=("Segoe UI", 11, "bold"), fill=fg)
        c.create_text(w // 2, h - 18, text=xlabel, font=("Segoe UI", 10), fill=fg)
        c.create_text(18, h // 2, text=ylabel, angle=90, font=("Segoe UI", 10), fill=fg)

        # polyline
        pts = []
        for x, y in zip(xs, ys):
            pts.extend([x_to_px(x), y_to_px(y)])
        c.create_line(*pts, width=2, fill=line_color)

    def compute_one(self):
        if self.selected_ref is None:
            self.var_info.set("Select something first.")
            return

        # pick roll
        try:
            rolled = int(self.var_roll_custom.get().strip())
        except ValueError:
            rolled = None

        # if no custom roll, use average
        ref = self.selected_ref
        parsed = parse_damage_expr((ref.get("damage") or "").strip())
        if parsed is None:
            dice_count, die_size, flat_bonus = (1, 10, 0)
        else:
            dice_count, die_size, flat_bonus = parsed

        if rolled is None:
            rolled = int(round(dice_count * (die_size + 1) / 2.0))

        # mana
        try:
            mana_spend = int(self.var_mana_spend.get().strip() or "0")
        except ValueError:
            mana_spend = 0

        dmg = self._compute_damage(rolled, mana_spend)
        self.var_info.set(f"Test: rolled={rolled}, mana={mana_spend} → damage={dmg}")

    def plot(self):
        if self.selected_ref is None:
            return

        ref = self.selected_ref
        dmg_expr = (ref.get("damage") or "").strip()
        parsed = parse_damage_expr(dmg_expr)
        if parsed is None:
            dice_count, die_size, flat_bonus = (1, 10, 0)
        else:
            dice_count, die_size, flat_bonus = parsed

        mode = self.var_mode.get()

        if mode == "Damage vs Roll":
            # Need mana spend for abilities; use entry or base cost
            mana_spend = 0
            if self.selected_kind == "ability":
                try:
                    mana_spend = int(self.var_mana_spend.get().strip() or str(ref.get("mana_cost", 0)))
                except ValueError:
                    mana_spend = int(ref.get("mana_cost", 0) or 0)

            max_roll = max(1, dice_count * die_size)
            xs = list(range(0, max_roll + 1))
            ys = [self._compute_damage(x + flat_bonus, mana_spend) for x in xs]  # note: rolled_total is dice sum; flat already added inside compute via expr parse, so pass dice sum only
            # Actually compute expects rolled_total as dice sum; it adds flat_bonus internally.
            ys = [self._compute_damage(x, mana_spend) for x in xs]

            title = f"{ref.get('name','(unnamed)')} — vs Roll"
            self._canvas_plot_line(xs, ys, title, "Dice Sum (rolled)", "Damage")

        else:
            # Damage vs Mana (abilities only)
            if self.selected_kind != "ability":
                self.canvas.delete("all")
                _fg = self._colors["canvas_fg"] if self._colors else "black"
                self.canvas.create_text(
                    10, 10, anchor="nw", fill=_fg,
                    text="Damage vs Mana only applies to abilities.\nPick an ability, or switch to Damage vs Roll."
                )
                return

            base_cost = int(ref.get("mana_cost", 0) or 0)
            if base_cost <= 0:
                return

            try:
                mx = int(self.var_mana_max_x.get().strip() or "4")
            except ValueError:
                mx = 4
            mx = max(1, mx)

            # choose roll profile
            roll_profile = self.var_roll_profile.get()
            if roll_profile == "Max":
                rolled = dice_count * die_size
            elif roll_profile == "Custom":
                try:
                    rolled = int(self.var_roll_custom.get().strip())
                except ValueError:
                    rolled = int(round(dice_count * (die_size + 1) / 2.0))
            else:
                rolled = int(round(dice_count * (die_size + 1) / 2.0))

            xs = []
            ys = []
            for spend in range(base_cost, base_cost * mx + 1):
                xs.append(spend)
                ys.append(self._compute_damage(rolled, spend))

            title = f"{ref.get('name','(unnamed)')} — vs Mana (roll={roll_profile})"
            self._canvas_plot_line(xs, ys, title, "Mana Spend (base)", "Damage")
