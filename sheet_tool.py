# character_sheet.py
import json
import math
import re
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from damage_lab import DamageLabTab

# ---------------- File picking ----------------

def pick_character_file():
    """
    Returns Path or None (if user cancels / exits).
    """
    root = tk.Tk()
    root.withdraw()

    choice = messagebox.askyesnocancel(
        "Open Character",
        "Yes = Open existing character JSON\nNo = Create a new character JSON\nCancel = Exit"
    )

    path = None

    if choice is True:
        p = filedialog.askopenfilename(
            title="Open character JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if p:
            path = Path(p)

    elif choice is False:
        p = filedialog.asksaveasfilename(
            title="Create new character JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if p:
            path = Path(p)
            save_character(default_character_template(), path)

    root.destroy()
    return path


def load_character(path: Path):
    if not path or not path.exists():
        messagebox.showerror("Error", f"Character file not found: {path}")
        raise SystemExit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_character(char, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(char, f, indent=2)


# ---------------- Mechanics helpers ----------------

ROLL_TYPES = ["None", "Attack", "Save", "Check"]

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

# ---------- Tier 1 tuning ----------
T1_HP_SOFT_CAP = 100
T1_HP_GAIN_BEFORE_CAP = 2
T1_HP_GAIN_AFTER_CAP = 1  # tweak if you want a different post-cap rate

T1_PBD_SOFT_CAP = 15
T1_PBD_COST_BEFORE_CAP = 3
T1_PBD_GAIN_BEFORE_CAP = 1
T1_PBD_COST_AFTER_CAP = 5
T1_PBD_GAIN_AFTER_CAP = 1


# ---------- New Stats (your list) ----------
STAT_ORDER = [
    ("melee_acc",  "Melee Accuracy"),
    ("ranged_acc", "Ranged Weapon Accuracy"),
    ("precision",  "Precision"),
    ("spellcraft", "Spellcraft"),

    ("phys_def",   "Defense"),
    ("evasion",    "Evasion"),
    ("wis_def",    "Wisdom"),

    ("utility",    "Utility"),
    ("agility",    "Agility"),
    ("strength",   "Strength"),
]
STAT_KEYS = [k for k, _ in STAT_ORDER]


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


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


def max_pbd_factor_for_die(die_size: int) -> float:
    """
    Piecewise linear mapping:
      d4  -> 0.50
      d10 -> 1.00
      d20 -> 2.111... (so 18/20 => ~1.9x)
    For other dice, interpolate.
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


def mana_density_multiplier(points: int) -> float:
    """
    Smooth scaling that matches:
      0 -> 1.00x
      71 -> 1.71x
      100 -> 2.00x
      10,000 -> 3.00x
      1,000,000 -> 4.00x
    """
    try:
        p = int(points)
    except Exception:
        p = 0
    p = max(0, p)

    if p <= 100:
        return 1.0 + (p / 100.0)

    return 2.0 + (math.log(p / 100.0) / math.log(100.0))


def compute_overcast_bonus(base_cost_eff: int, spent_eff: int, over: dict) -> int:
    """
    Log-ish overcast bonus:
      bonus = floor(scale * (log2(spent/base))^power), capped.
    """
    if base_cost_eff <= 0 or spent_eff <= base_cost_eff:
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

    ratio = spent_eff / base_cost_eff
    x = math.log(ratio, 2)  # 1 at 2x, 2 at 4x, etc.
    bonus = int(math.floor(scale * (x ** power)))
    if cap >= 0:
        bonus = min(bonus, cap)
    return max(0, bonus)


def phys_dr_from_points(phys_def_points: int) -> int:
    """
    Physical Defense gives flat DR:
      every 5 points => 1 damage reduction.
    """
    try:
        p = int(phys_def_points)
    except Exception:
        p = 0
    return max(0, p // 5)


# ---------------- Data schema helpers ----------------

def default_character_template(name="New Hero"):
    return {
        "name": name,
        "tier": "T1",
        "resources": {
            "hp": {"current": 20, "max": 20},
            "mana": {"current": 10, "max": 10},
            "pbd": 0,
            "mana_density": 0,
            "unspent_points": 0
        },
        "stats": {k: 5 for k in STAT_KEYS},
        "skills": {
            "core": {"current": 0, "max": 2},
            "inner": {"current": 0, "max": 5},
            "outer": {"current": 0, "max": 9},
        },
        "growth_items": {"bound_current": 0, "bound_max": 4},
        "inventory": {"equipment": [], "bag": [], "storage": []},
        "abilities": {"core": [], "inner": [], "outer": []},
        "notes": "",
        "world_info": "",
        "talents": {}
    }


def _migrate_stats_schema(char: dict):
    """
    Ensures char["stats"] contains the new stat keys.
    Best-effort mapping from older schemas if they exist.
    """
    if not isinstance(char, dict):
        return

    stats = char.get("stats")
    if not isinstance(stats, dict):
        char["stats"] = {k: 0 for k in STAT_KEYS}
        return

    has_any_new = any(k in stats for k in STAT_KEYS)

    def _get_int(d, key, default=0):
        try:
            return int(d.get(key, default) or default)
        except Exception:
            return default

    if not has_any_new:
        mapped = {k: 0 for k in STAT_KEYS}

        # common old RPG keys best-effort
        mapped["strength"] = _get_int(stats, "strength", _get_int(stats, "str", 0))
        mapped["agility"] = _get_int(stats, "agility", _get_int(stats, "dex", 0))
        mapped["precision"] = _get_int(stats, "precision", _get_int(stats, "prc", 0))

        # if you had "wis"
        mapped["wis_def"] = _get_int(stats, "wis_def", _get_int(stats, "wis", 0))

        char["stats"] = mapped
    else:
        for k in STAT_KEYS:
            if k not in stats:
                stats[k] = 0
            try:
                stats[k] = int(stats[k] or 0)
            except Exception:
                stats[k] = 0


def sort_favorites_first(items):
    return sorted(items, key=lambda it: (not bool(it.get("favorite", False)), it.get("name", "").lower()))


def ensure_item_obj(x):
    """
    Items:
      - apply_bonus: whether to apply PBD (melee) or Precision (ranged)
      - is_ranged: whether to treat this as a ranged item (use Precision)
    Back-compat:
      - older files may have apply_pbd
    """
    if isinstance(x, str):
        return {
            "name": x,
            "favorite": False,
            "roll_type": "None",
            "damage": "",
            "notes": "",
            "apply_bonus": True,
            "apply_pbd": True,     # back-compat
            "is_ranged": False
        }
    if isinstance(x, dict):
        apply_bonus = bool(x.get("apply_bonus", x.get("apply_pbd", True)))
        is_ranged = bool(x.get("is_ranged", False))
        return {
            "name": x.get("name", ""),
            "favorite": bool(x.get("favorite", False)),
            "roll_type": x.get("roll_type", "None"),
            "damage": x.get("damage", ""),
            "notes": x.get("notes", ""),
            "apply_bonus": apply_bonus,
            "apply_pbd": apply_bonus,   # keep synced for damage_lab back-compat
            "is_ranged": is_ranged,
        }
    return {"name": "", "favorite": False, "roll_type": "None", "damage": "", "notes": "",
            "apply_bonus": True, "apply_pbd": True, "is_ranged": False}


def ensure_ability_obj(x):
    """
    Abilities NEVER use PBD/Precision. They can optionally have overcast scaling.
    """
    if isinstance(x, str):
        return {
            "name": x, "favorite": False, "roll_type": "None",
            "damage": "", "mana_cost": 0, "notes": "",
            "overcast": {"enabled": False, "scale": 0, "power": 0.85, "cap": 999}
        }

    if isinstance(x, dict):
        over = x.get("overcast", {})
        if not isinstance(over, dict):
            over = {}

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
        enabled = bool(over.get("enabled", False))

        return {
            "name": x.get("name", ""),
            "favorite": bool(x.get("favorite", False)),
            "roll_type": x.get("roll_type", "None"),
            "damage": x.get("damage", ""),
            "mana_cost": int(x.get("mana_cost", 0) or 0),
            "notes": x.get("notes", ""),
            "overcast": {"enabled": enabled, "scale": scale, "power": power, "cap": cap},
        }

    return {
        "name": "", "favorite": False, "roll_type": "None",
        "damage": "", "mana_cost": 0, "notes": "",
        "overcast": {"enabled": False, "scale": 0, "power": 0.85, "cap": 999}
    }


def find_show_must_go_on(char):
    t1 = char.get("talents", {}).get("T1")
    if not t1:
        return None
    for eff in t1.get("effects", []):
        if eff.get("id") == "show_must_go_on":
            return eff
    return None


# ---------------- App ----------------

class CharacterApp(tk.Tk):
    def __init__(self, char_path: Path):
        super().__init__()

        self.char_path = char_path
        self.title(f"Homebrew Character Sheet — {self.char_path.name}")
        self.geometry("1150x780")

        self.char = load_character(self.char_path)
        _migrate_stats_schema(self.char)

        # ----- Vars -----
        self.var_name = tk.StringVar()
        self.var_tier = tk.StringVar()

        self.var_hp_current = tk.StringVar()
        self.var_hp_max = tk.StringVar()
        self.var_mana_current = tk.StringVar()
        self.var_mana_max = tk.StringVar()
        self.var_pbd = tk.StringVar()
        self.var_mana_density = tk.StringVar()
        self.var_mana_density_mult = tk.StringVar()
        self.var_unspent = tk.StringVar()

        self.var_hp_dmg = tk.StringVar()
        self.var_hp_heal = tk.StringVar()

        # NEW: incoming hit reduced by Physical Defense
        self.var_hit_incoming = tk.StringVar()
        self.var_hit_result = tk.StringVar(value="")

        self.var_core_current = tk.StringVar()
        self.var_core_max = tk.StringVar()
        self.var_inner_current = tk.StringVar()
        self.var_inner_max = tk.StringVar()
        self.var_outer_current = tk.StringVar()
        self.var_outer_max = tk.StringVar()

        self.var_stats = {k: tk.StringVar() for k in STAT_KEYS}

        self.var_growth_current = tk.StringVar()
        self.var_growth_max = tk.StringVar()

        self.var_show_used = tk.BooleanVar()

        # Inventory internal data (sub-tabs)
        self.inv_keys = ["equipment", "bag", "storage"]
        self.inv_data = {k: [] for k in self.inv_keys}
        self.inv_selected_ref = {k: None for k in self.inv_keys}

        self.inv_new_name = {k: tk.StringVar() for k in self.inv_keys}
        self.inv_roll_type = {k: tk.StringVar(value="None") for k in self.inv_keys}
        self.inv_damage = {k: tk.StringVar() for k in self.inv_keys}
        self.inv_apply_bonus = {k: tk.BooleanVar(value=True) for k in self.inv_keys}
        self.inv_is_ranged = {k: tk.BooleanVar(value=False) for k in self.inv_keys}
        self.inv_move_target = {
            k: tk.StringVar(value=("bag" if k != "bag" else "equipment"))
            for k in self.inv_keys
        }


        # Abilities
        self.ability_keys = ["core", "inner", "outer"]
        self.abilities_data = {k: [] for k in self.ability_keys}
        self.ability_selected_ref = {k: None for k in self.ability_keys}

        self.var_new_ability_name = {k: tk.StringVar() for k in self.ability_keys}
        self.ability_roll_type = {k: tk.StringVar(value="None") for k in self.ability_keys}
        self.ability_damage = {k: tk.StringVar() for k in self.ability_keys}
        self.ability_mana_cost = {k: tk.StringVar(value="0") for k in self.ability_keys}

        self.ability_overcast_enabled = {k: tk.BooleanVar(value=False) for k in self.ability_keys}
        self.ability_overcast_scale   = {k: tk.StringVar(value="0") for k in self.ability_keys}
        self.ability_overcast_power   = {k: tk.StringVar(value="0.85") for k in self.ability_keys}
        self.ability_overcast_cap     = {k: tk.StringVar(value="999") for k in self.ability_keys}
        self.ability_move_target = {
            s: tk.StringVar(value=("inner" if s != "inner" else "core"))
            for s in self.ability_keys
        }

        # Combat (Overview quick use)
        self.combat_actions = []  # list of dicts {kind, ref, display, slot?}
        self.combat_selected_ref = None
        self.combat_selected_kind = None

        self.var_combat_roll_type = tk.StringVar(value="")
        self.var_combat_damage_expr = tk.StringVar(value="")
        self.var_combat_roll_value = tk.StringVar()
        self.var_combat_mana_spend = tk.StringVar()
        self.var_combat_result = tk.StringVar(value="")

        self._build_ui()
        self.refresh_from_model()
                # --- Close / dirty tracking ---
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Normalize current UI -> model once, then snapshot as "last saved"
        # (prevents "prompt to save" immediately after opening due to sorting/canonicalization)
        self.apply_to_model()
        self._last_saved_state = self._serialize_char(self.char)


    # ---------------- UI ----------------

    def _build_ui(self):
        # Top bar
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=8)

        ttk.Label(top, text="Name:").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.var_name, width=22).pack(side=tk.LEFT, padx=5)

        ttk.Label(top, text="Tier:").pack(side=tk.LEFT, padx=(15, 0))
        ttk.Entry(top, textvariable=self.var_tier, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Button(top, text="Save", command=self.on_save).pack(side=tk.RIGHT)

        # Tabs
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.tab_overview = ttk.Frame(self.tabs)
        self.tab_inventory = ttk.Frame(self.tabs)
        self.tab_abilities = ttk.Frame(self.tabs)
        self.tab_notes = ttk.Frame(self.tabs)
        self.tab_world = ttk.Frame(self.tabs)
        self.tab_damage_lab = ttk.Frame(self.tabs)

        self.tabs.add(self.tab_overview, text="Overview")
        self.tabs.add(self.tab_inventory, text="Inventory")
        self.tabs.add(self.tab_abilities, text="Abilities")
        self.tabs.add(self.tab_notes, text="Notes")
        self.tabs.add(self.tab_world, text="World Info")
        self.tabs.add(self.tab_damage_lab, text="Damage Lab")

        self._build_overview_tab()
        self._build_inventory_tab()
        self._build_abilities_tab()
        self._build_notes_tab()
        self._build_world_tab()
        self._build_damage_lab_tab()

    def _build_overview_tab(self):
        left = ttk.Frame(self.tab_overview)
        right = ttk.Frame(self.tab_overview)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=8)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)

        # Stats
        stats_frame = ttk.LabelFrame(left, text="Stats")
        stats_frame.pack(fill=tk.X, pady=6)

        for row, (key, label) in enumerate(STAT_ORDER):
            ttk.Label(stats_frame, text=label + ":").grid(row=row, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(stats_frame, textvariable=self.var_stats[key], width=7).grid(row=row, column=1, sticky="w", padx=4, pady=2)

        # Resources
        res_frame = ttk.LabelFrame(left, text="Resources")
        res_frame.pack(fill=tk.X, pady=6)

        ttk.Label(res_frame, text="HP:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_hp_current, width=6).grid(row=0, column=1)
        ttk.Label(res_frame, text="/").grid(row=0, column=2)
        ttk.Entry(res_frame, textvariable=self.var_hp_max, width=6).grid(row=0, column=3)

        ttk.Label(res_frame, text="Take dmg:").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_hp_dmg, width=8).grid(row=1, column=1, sticky="w")
        ttk.Button(res_frame, text="Apply", command=self.apply_hp_damage).grid(row=1, column=3, sticky="w", padx=4)

        ttk.Label(res_frame, text="Heal:").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_hp_heal, width=8).grid(row=2, column=1, sticky="w")
        ttk.Button(res_frame, text="Apply", command=self.apply_hp_heal).grid(row=2, column=3, sticky="w", padx=4)

        # NEW: Incoming hit (Physical Defense DR)
        ttk.Separator(res_frame, orient="horizontal").grid(row=3, column=0, columnspan=4, sticky="ew", padx=4, pady=6)

        ttk.Label(res_frame, text="Incoming hit:").grid(row=4, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_hit_incoming, width=8).grid(row=4, column=1, sticky="w")
        ttk.Button(res_frame, text="Apply (uses Phys Def DR)", command=self.apply_incoming_hit).grid(
            row=4, column=2, columnspan=2, sticky="ew", padx=4
        )
        ttk.Label(res_frame, textvariable=self.var_hit_result, foreground="gray").grid(
            row=5, column=0, columnspan=4, sticky="w", padx=4, pady=(2, 4)
        )

        ttk.Separator(res_frame, orient="horizontal").grid(row=6, column=0, columnspan=4, sticky="ew", padx=4, pady=6)

        ttk.Label(res_frame, text="Mana:").grid(row=7, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_mana_current, width=6).grid(row=7, column=1)
        ttk.Label(res_frame, text="/").grid(row=7, column=2)
        ttk.Entry(res_frame, textvariable=self.var_mana_max, width=6).grid(row=7, column=3)

        ttk.Label(res_frame, text="Mana Density:").grid(row=8, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_mana_density, width=6).grid(row=8, column=1)
        ttk.Label(res_frame, textvariable=self.var_mana_density_mult, foreground="gray").grid(row=8, column=3, sticky="w", padx=4)

        ttk.Label(res_frame, text="PBD:").grid(row=9, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_pbd, width=6).grid(row=9, column=1)

        ttk.Label(res_frame, text="Unspent pts:").grid(row=10, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_unspent, width=6).grid(row=10, column=1)

        ttk.Button(res_frame, text="Spend Points…", command=self.open_spend_points_popup).grid(
            row=11, column=0, columnspan=4, sticky="ew", padx=4, pady=(8, 4)
        )

        ttk.Button(res_frame, text="Long Rest (full HP/Mana)", command=self.apply_long_rest).grid(
            row=12, column=0, columnspan=4, sticky="ew", padx=4, pady=(6, 4)
        )

        # Combat quick use
        combat = ttk.LabelFrame(right, text="Combat Quick Use (select equipment / ability)")
        combat.pack(fill=tk.BOTH, expand=True, pady=6)

        c_outer = ttk.Frame(combat)
        c_outer.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        c_left = ttk.Frame(c_outer)
        c_right = ttk.Frame(c_outer)
        c_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        c_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.combat_list = tk.Listbox(c_left, height=14)
        self.combat_list.pack(fill=tk.BOTH, expand=True)
        self.combat_list.bind("<<ListboxSelect>>", lambda _e: self.on_combat_select())

        ttk.Button(c_left, text="Refresh list", command=self.refresh_combat_list).pack(fill=tk.X, pady=(6, 0))

        ttk.Label(c_right, text="Roll type:").grid(row=0, column=0, sticky="w", padx=4, pady=(4, 2))
        ttk.Label(c_right, textvariable=self.var_combat_roll_type).grid(row=0, column=1, sticky="w", padx=4, pady=(4, 2))

        ttk.Label(c_right, text="Damage dice:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(c_right, textvariable=self.var_combat_damage_expr).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(c_right, text="Enter rolled damage:").grid(row=2, column=0, sticky="w", padx=4, pady=(10, 2))
        ttk.Entry(c_right, textvariable=self.var_combat_roll_value, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=(10, 2))

        ttk.Label(c_right, text="Mana to spend (abilities):").grid(row=3, column=0, sticky="w", padx=4, pady=2)
        self.combat_mana_entry = ttk.Entry(c_right, textvariable=self.var_combat_mana_spend, width=10)
        self.combat_mana_entry.grid(row=3, column=1, sticky="w", padx=4, pady=2)

        ttk.Button(c_right, text="Use / Cast", command=self.use_combat_action).grid(
            row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=(12, 6)
        )

        ttk.Label(c_right, textvariable=self.var_combat_result, foreground="gray").grid(
            row=5, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 2)
        )

        for col in range(2):
            c_right.grid_columnconfigure(col, weight=1)

    
    def _clipboard_set(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()  # helps ensure clipboard updates on some systems

    def _clipboard_get(self) -> str:
        try:
            return self.clipboard_get()
        except Exception:
            return ""

    def _safe_json_loads(self, s: str):
        try:
            return json.loads(s)
        except Exception as e:
            raise ValueError(f"Invalid JSON: {e}")

    def _clean_item_for_json(self, it: dict) -> dict:
        # Minimal canonical schema for items
        return {
            "name": it.get("name", ""),
            "favorite": bool(it.get("favorite", False)),
            "roll_type": it.get("roll_type", "None"),
            "damage": it.get("damage", ""),
            "notes": it.get("notes", ""),
            "apply_bonus": bool(it.get("apply_bonus", it.get("apply_pbd", True))),
            "is_ranged": bool(it.get("is_ranged", False)),
        }

    def _clean_ability_for_json(self, ab: dict) -> dict:
        over = ab.get("overcast", {})
        if not isinstance(over, dict):
            over = {}
        return {
            "name": ab.get("name", ""),
            "favorite": bool(ab.get("favorite", False)),
            "roll_type": ab.get("roll_type", "None"),
            "damage": ab.get("damage", ""),
            "mana_cost": int(ab.get("mana_cost", 0) or 0),
            "notes": ab.get("notes", ""),
            "overcast": {
                "enabled": bool(over.get("enabled", False)),
                "scale": int(over.get("scale", 0) or 0),
                "power": float(over.get("power", 0.85) or 0.85),
                "cap": int(over.get("cap", 999) or 999),
            },
        }

    def _serialize_char(self, char_obj) -> str:
        """Stable-ish snapshot for dirty checking."""
        try:
            return json.dumps(char_obj, sort_keys=True, ensure_ascii=False)
        except Exception:
            # Fallback: at least something comparable
            return str(char_obj)

    def _save_to_disk(self, show_popup: bool = True) -> bool:
        """Save current UI state to disk. Returns True if successful."""
        try:
            self.apply_to_model()
            save_character(self.char, self.char_path)
            self._last_saved_state = self._serialize_char(self.char)
            if show_popup:
                messagebox.showinfo("Saved", f"Saved to {self.char_path.name}")
            return True
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save:\n{e}")
            return False

    def on_close(self):
        """
        Prompt to save on exit if there are unsaved changes:
          Yes = save then exit
          No  = exit without saving
          Cancel = do nothing
        """
        # Update model from UI so we compare the *actual* current state
        self.apply_to_model()
        current_state = self._serialize_char(self.char)

        if current_state != getattr(self, "_last_saved_state", ""):
            choice = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes.\n\nSave before exiting?"
            )
            if choice is True:
                # Save silently; if it fails, don't exit.
                if not self._save_to_disk(show_popup=False):
                    return
                self.destroy()
            elif choice is False:
                self.destroy()
            else:
                # Cancel / X
                return
        else:
            self.destroy()


    # ---------------- Inventory ----------------

    def _build_inventory_tab(self):
        frame = ttk.Frame(self.tab_inventory)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        growth_frame = ttk.LabelFrame(frame, text="Growth Items Bound")
        growth_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Entry(growth_frame, textvariable=self.var_growth_current, width=6).grid(row=0, column=0, padx=4, pady=6)
        ttk.Label(growth_frame, text="/").grid(row=0, column=1)
        ttk.Entry(growth_frame, textvariable=self.var_growth_max, width=6).grid(row=0, column=2, padx=4, pady=6)

        self.inv_tabs = ttk.Notebook(frame)
        self.inv_tabs.pack(fill=tk.BOTH, expand=True)

        for key, label in [("equipment", "Equipment"), ("bag", "Bag"), ("storage", "Storage")]:
            f = ttk.Frame(self.inv_tabs)
            self.inv_tabs.add(f, text=label)
            self._build_inventory_category(f, key)

    def _build_inventory_category(self, parent, key: str):
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(outer)
        right = ttk.Frame(outer)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lb = tk.Listbox(left, height=18, exportselection=False)
        lb.pack(fill=tk.BOTH, expand=True)
        lb.bind("<Double-Button-1>", lambda _e, k=key: self.inv_toggle_favorite(k))
        lb.bind("<<ListboxSelect>>", lambda _e, k=key: self.inv_on_select(k))
        setattr(self, f"inv_list_{key}", lb)

        controls = ttk.Frame(left)
        controls.pack(fill=tk.X, pady=(8, 0))

        ttk.Entry(controls, textvariable=self.inv_new_name[key]).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(controls, text="Add", command=lambda k=key: self.inv_add(k)).pack(side=tk.LEFT, padx=6)
        ttk.Button(controls, text="Remove", command=lambda k=key: self.inv_remove(k)).pack(side=tk.LEFT)
        ttk.Button(controls, text="Toggle ⭐", command=lambda k=key: self.inv_toggle_favorite(k)).pack(side=tk.LEFT, padx=6)

        details = ttk.LabelFrame(right, text="Selected Item (combat info)")
        details.pack(fill=tk.BOTH, expand=True)

        ttk.Label(details, text="Roll type:").grid(row=0, column=0, sticky="w", padx=6, pady=(8, 4))
        ttk.Combobox(details, values=ROLL_TYPES, textvariable=self.inv_roll_type[key], state="readonly", width=18).grid(
            row=0, column=1, sticky="w", padx=6, pady=(8, 4)
        )

        ttk.Label(details, text="Damage dice (ex: 1d10+3):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.inv_damage[key], width=28).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Checkbutton(details, text="Ranged item (use Precision)", variable=self.inv_is_ranged[key]).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 2)
        )

        ttk.Checkbutton(details, text="Apply bonus (PBD melee / Precision ranged)", variable=self.inv_apply_bonus[key]).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 6)
        )

        ttk.Label(details, text="Notes:").grid(row=4, column=0, sticky="nw", padx=6, pady=4)
        notes_box = tk.Text(details, wrap="word", height=10)
        notes_box.grid(row=4, column=1, sticky="nsew", padx=6, pady=4)
        setattr(self, f"inv_notes_box_{key}", notes_box)

        ttk.Button(details, text="Update Selected", command=lambda k=key: self.inv_update_selected(k)).grid(
            row=5, column=1, sticky="w", padx=6, pady=(6, 8)
        )

        move_box = ttk.LabelFrame(details, text="Transfer")
        move_box.grid(row=5, column=1, sticky="ew", padx=6, pady=(6, 8))

        ttk.Label(move_box, text="Move to:").pack(side=tk.LEFT, padx=(6, 4), pady=6)

        ttk.Combobox(
            move_box,
            values=[k for k in self.inv_keys if k != key],
            textvariable=self.inv_move_target[key],
            state="readonly",
            width=12
        ).pack(side=tk.LEFT, padx=6, pady=6)

        ttk.Button(
            move_box,
            text="Move Selected",
            command=lambda fk=key: self.inv_move_selected(fk, self.inv_move_target[fk].get())
        ).pack(side=tk.LEFT, padx=(6, 6), pady=6)

        json_row = ttk.Frame(details)
        json_row.grid(row=6, column=1, sticky="w", padx=6, pady=(0, 8))

        ttk.Button(json_row, text="Copy JSON", command=lambda k=key: self.inv_copy_json_selected(k)).pack(side=tk.LEFT)
        ttk.Button(json_row, text="Import JSON…", command=lambda k=key: self.inv_import_json_dialog(k)).pack(side=tk.LEFT, padx=8)

        details.grid_columnconfigure(1, weight=1)
        details.grid_rowconfigure(4, weight=1)

    def _select_ref_in_listbox(self, lb: tk.Listbox, data_list: list, ref_obj):
        lb.selection_clear(0, tk.END)
        if ref_obj is None:
            return
        for idx, obj in enumerate(data_list):
            if obj is ref_obj:
                lb.selection_set(idx)
                lb.see(idx)
                break

    def inv_render(self, key: str):
        selected_ref = self.inv_selected_ref.get(key)
        self.inv_data[key] = sort_favorites_first(self.inv_data[key])

        lb: tk.Listbox = getattr(self, f"inv_list_{key}")
        lb.delete(0, tk.END)
        for it in self.inv_data[key]:
            star = "⭐ " if it.get("favorite", False) else ""
            rng = " (R)" if it.get("is_ranged", False) else ""
            lb.insert(tk.END, f"{star}{it.get('name','')}{rng}")

        self._select_ref_in_listbox(lb, self.inv_data[key], selected_ref)
        self.refresh_combat_list()

    def inv_add(self, key: str):
        name = self.inv_new_name[key].get().strip()
        if not name:
            return
        self.inv_data[key].append({
            "name": name,
            "favorite": False,
            "roll_type": "None",
            "damage": "",
            "notes": "",
            "apply_bonus": True,
            "apply_pbd": True,   # back-compat for damage_lab
            "is_ranged": False
        })
        self.inv_new_name[key].set("")
        self.inv_render(key)

    def inv_remove(self, key: str):
        lb: tk.Listbox = getattr(self, f"inv_list_{key}")
        sel = list(lb.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            if 0 <= idx < len(self.inv_data[key]):
                removed = self.inv_data[key].pop(idx)
                if removed is self.inv_selected_ref.get(key):
                    self.inv_selected_ref[key] = None
        self.inv_render(key)

    def inv_toggle_favorite(self, key: str):
        lb: tk.Listbox = getattr(self, f"inv_list_{key}")
        sel = list(lb.curselection())
        if len(sel) != 1:
            return
        idx = sel[0]
        if 0 <= idx < len(self.inv_data[key]):
            self.inv_data[key][idx]["favorite"] = not bool(self.inv_data[key][idx].get("favorite", False))
            self.inv_selected_ref[key] = self.inv_data[key][idx]
        self.inv_render(key)

    def inv_on_select(self, key: str):
        lb: tk.Listbox = getattr(self, f"inv_list_{key}")
        sel = list(lb.curselection())
        if len(sel) != 1:
            return
        idx = sel[0]
        it = self.inv_data[key][idx]
        self.inv_selected_ref[key] = it

        self.inv_roll_type[key].set(it.get("roll_type", "None"))
        self.inv_damage[key].set(it.get("damage", ""))

        # prefer apply_bonus, but fall back to apply_pbd
        apply_bonus = bool(it.get("apply_bonus", it.get("apply_pbd", True)))
        self.inv_apply_bonus[key].set(apply_bonus)

        self.inv_is_ranged[key].set(bool(it.get("is_ranged", False)))

        notes_box: tk.Text = getattr(self, f"inv_notes_box_{key}")
        notes_box.delete("1.0", tk.END)
        notes_box.insert(tk.END, it.get("notes", ""))

    def inv_update_selected(self, key: str):
        it = self.inv_selected_ref.get(key)
        if it is None:
            messagebox.showinfo("Update", "Select an item first.")
            return

        it["roll_type"] = self.inv_roll_type[key].get() or "None"
        it["damage"] = self.inv_damage[key].get().strip()

        apply_bonus = bool(self.inv_apply_bonus[key].get())
        it["apply_bonus"] = apply_bonus
        it["apply_pbd"] = apply_bonus  # keep synced for damage_lab

        it["is_ranged"] = bool(self.inv_is_ranged[key].get())

        notes_box: tk.Text = getattr(self, f"inv_notes_box_{key}")
        it["notes"] = notes_box.get("1.0", tk.END).rstrip("\n")

        self.inv_render(key)
    
    def inv_copy_json_selected(self, key: str):
        it = self.inv_selected_ref.get(key)
        if it is None:
            messagebox.showinfo("Copy JSON", "Select an item first.")
            return
        payload = self._clean_item_for_json(it)
        self._clipboard_set(json.dumps(payload, indent=2))
        messagebox.showinfo("Copy JSON", "Item JSON copied to clipboard.")

    def inv_import_json_dialog(self, key: str):
        win = tk.Toplevel(self)
        win.title(f"Import Item JSON → {key}")
        win.geometry("520x620")
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="Paste JSON for an item OR a list of items:").pack(anchor="w", padx=10, pady=(10, 4))

        txt = tk.Text(win, wrap="none")
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # helpful: prefill with clipboard
        clip = self._clipboard_get()
        if clip.strip():
            txt.insert("1.0", clip)

        status = tk.StringVar(value="")
        ttk.Label(win, textvariable=status, foreground="gray").pack(anchor="w", padx=10, pady=(0, 8))

        def parse_items():
            raw = txt.get("1.0", tk.END).strip()
            data = self._safe_json_loads(raw)
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                raise ValueError("JSON must be an object or a list of objects.")
            items = [ensure_item_obj(d) for d in data]  # your existing normalizer
            # ensure apply_bonus synced
            for it in items:
                ab = bool(it.get("apply_bonus", it.get("apply_pbd", True)))
                it["apply_bonus"] = ab
                it["apply_pbd"] = ab
            return items

        def add_items():
            try:
                items = parse_items()
            except Exception as e:
                status.set(str(e))
                return
            for it in items:
                if (it.get("name") or "").strip():
                    self.inv_data[key].append(it)
            self.inv_render(key)
            self.refresh_combat_list()
            status.set(f"Added {len(items)} item(s).")

        def replace_selected():
            target = self.inv_selected_ref.get(key)
            if target is None:
                status.set("Select an item first (or use Add).")
                return
            try:
                items = parse_items()
            except Exception as e:
                status.set(str(e))
                return
            if len(items) != 1:
                status.set("Replace requires exactly 1 item object (not a list).")
                return
            new_it = items[0]
            # replace in-place to preserve object identity (refs)
            target.clear()
            target.update(new_it)
            self.inv_render(key)
            self.refresh_combat_list()
            status.set("Replaced selected item.")

        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btns, text="Add", command=add_items).pack(side=tk.LEFT)
        ttk.Button(btns, text="Replace Selected", command=replace_selected).pack(side=tk.LEFT, padx=8)
        ttk.Button(btns, text="Close", command=win.destroy).pack(side=tk.RIGHT)
    def inv_move_selected(self, from_key: str, to_key: str):
        if to_key not in self.inv_keys or from_key not in self.inv_keys:
            return
        if from_key == to_key:
            return

        it = self.inv_selected_ref.get(from_key)
        if it is None:
            messagebox.showinfo("Move Item", "Select an item first.")
            return

        try:
            self.inv_data[from_key].remove(it)
        except ValueError:
            self.inv_selected_ref[from_key] = None
            return

        self.inv_data[to_key].append(it)
        self.inv_selected_ref[from_key] = None

        self.inv_render(from_key)
        self.inv_render(to_key)



    # ---------------- Abilities ----------------

    def _build_abilities_tab(self):
        frame = ttk.Frame(self.tab_abilities)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.ability_tabs = ttk.Notebook(frame)
        self.ability_tabs.pack(fill=tk.BOTH, expand=True)

        for key, label in [("core", "Core"), ("inner", "Inner"), ("outer", "Outer")]:
            f = ttk.Frame(self.ability_tabs)
            self.ability_tabs.add(f, text=label)
            self._build_ability_category(f, key)

    def _build_ability_category(self, parent, key: str):
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(outer)
        right = ttk.Frame(outer)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lb = tk.Listbox(left, height=18, exportselection=False)
        lb.pack(fill=tk.BOTH, expand=True)
        lb.bind("<Double-Button-1>", lambda _e, k=key: self.ability_toggle_favorite(k))
        lb.bind("<<ListboxSelect>>", lambda _e, k=key: self.ability_on_select(k))
        setattr(self, f"ability_list_{key}", lb)

        controls = ttk.Frame(left)
        controls.pack(fill=tk.X, pady=(8, 0))

        ttk.Entry(controls, textvariable=self.var_new_ability_name[key]).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(controls, text="Add", command=lambda k=key: self.ability_add(k)).pack(side=tk.LEFT, padx=6)
        ttk.Button(controls, text="Remove", command=lambda k=key: self.ability_remove(k)).pack(side=tk.LEFT)
        ttk.Button(controls, text="Toggle ⭐", command=lambda k=key: self.ability_toggle_favorite(k)).pack(side=tk.LEFT, padx=6)

        details = ttk.LabelFrame(right, text="Selected Ability (combat info)")
        details.pack(fill=tk.BOTH, expand=True)

        ttk.Label(details, text="Roll type:").grid(row=0, column=0, sticky="w", padx=6, pady=(8, 4))
        ttk.Combobox(details, values=ROLL_TYPES, textvariable=self.ability_roll_type[key], state="readonly", width=18).grid(
            row=0, column=1, sticky="w", padx=6, pady=(8, 4)
        )

        ttk.Label(details, text="Damage dice (ex: 2d6+3):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.ability_damage[key], width=28).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Mana cost (base):").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.ability_mana_cost[key], width=10).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Separator(details, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 8))

        ttk.Checkbutton(
            details,
            text="Enable Overcast (log scaling)",
            variable=self.ability_overcast_enabled[key]
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Bonus @2x mana (scale):").grid(row=5, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.ability_overcast_scale[key], width=10).grid(row=5, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Diminishing power:").grid(row=6, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.ability_overcast_power[key], width=10).grid(row=6, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Max bonus (cap):").grid(row=7, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.ability_overcast_cap[key], width=10).grid(row=7, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Notes:").grid(row=8, column=0, sticky="nw", padx=6, pady=4)
        notes_box = tk.Text(details, wrap="word", height=10)
        notes_box.grid(row=8, column=1, sticky="nsew", padx=6, pady=4)
        setattr(self, f"ability_notes_box_{key}", notes_box)

        ttk.Button(details, text="Update Selected", command=lambda k=key: self.ability_update_selected(k)).grid(
            row=9, column=1, sticky="w", padx=6, pady=(6, 8)
        )

        move_box = ttk.LabelFrame(details, text="Transfer")
        move_box.grid(row=11, column=1, sticky="ew", padx=6, pady=(6, 8))

        ttk.Label(move_box, text="Move to:").pack(side=tk.LEFT, padx=(6, 4), pady=6)

        ttk.Combobox(
            move_box,
            values=[s for s in self.ability_keys if s != key],
            textvariable=self.ability_move_target[key],
            state="readonly",
            width=12
        ).pack(side=tk.LEFT, padx=6, pady=6)

        ttk.Button(
            move_box,
            text="Move Selected",
            command=lambda fs=key: self.ability_move_selected(fs, self.ability_move_target[fs].get())
        ).pack(side=tk.LEFT, padx=(6, 6), pady=6)


        json_row = ttk.Frame(details)
        json_row.grid(row=10, column=1, sticky="w", padx=6, pady=(0, 8))

        ttk.Button(json_row, text="Copy JSON", command=lambda s=key: self.ability_copy_json_selected(s)).pack(side=tk.LEFT)
        ttk.Button(json_row, text="Import JSON…", command=lambda s=key: self.ability_import_json_dialog(s)).pack(side=tk.LEFT, padx=8)


        details.grid_columnconfigure(1, weight=1)
        details.grid_rowconfigure(8, weight=1)

    def ability_render(self, key: str):
        selected_ref = self.ability_selected_ref.get(key)
        self.abilities_data[key] = sort_favorites_first(self.abilities_data[key])

        lb: tk.Listbox = getattr(self, f"ability_list_{key}")
        lb.delete(0, tk.END)
        for ab in self.abilities_data[key]:
            star = "⭐ " if ab.get("favorite", False) else ""
            lb.insert(tk.END, f"{star}{ab.get('name','')}")

        self._select_ref_in_listbox(lb, self.abilities_data[key], selected_ref)
        self.refresh_combat_list()

    def ability_add(self, key: str):
        name = self.var_new_ability_name[key].get().strip()
        if not name:
            return
        self.abilities_data[key].append(ensure_ability_obj({"name": name}))
        self.var_new_ability_name[key].set("")
        self.ability_render(key)

    def ability_remove(self, key: str):
        lb: tk.Listbox = getattr(self, f"ability_list_{key}")
        sel = list(lb.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            if 0 <= idx < len(self.abilities_data[key]):
                removed = self.abilities_data[key].pop(idx)
                if removed is self.ability_selected_ref.get(key):
                    self.ability_selected_ref[key] = None
        self.ability_render(key)

    def ability_toggle_favorite(self, key: str):
        lb: tk.Listbox = getattr(self, f"ability_list_{key}")
        sel = list(lb.curselection())
        if len(sel) != 1:
            return
        idx = sel[0]
        if 0 <= idx < len(self.abilities_data[key]):
            self.abilities_data[key][idx]["favorite"] = not bool(self.abilities_data[key][idx].get("favorite", False))
            self.ability_selected_ref[key] = self.abilities_data[key][idx]
        self.ability_render(key)

    def ability_on_select(self, key: str):
        lb: tk.Listbox = getattr(self, f"ability_list_{key}")
        sel = list(lb.curselection())
        if len(sel) != 1:
            return

        idx = sel[0]
        ab = self.abilities_data[key][idx]
        self.ability_selected_ref[key] = ab

        self.ability_roll_type[key].set(ab.get("roll_type", "None"))
        self.ability_damage[key].set(ab.get("damage", ""))
        self.ability_mana_cost[key].set(str(ab.get("mana_cost", 0)))

        over = ab.get("overcast", {}) if isinstance(ab.get("overcast", {}), dict) else {}
        self.ability_overcast_enabled[key].set(bool(over.get("enabled", False)))
        self.ability_overcast_scale[key].set(str(over.get("scale", 0)))
        self.ability_overcast_power[key].set(str(over.get("power", 0.85)))
        self.ability_overcast_cap[key].set(str(over.get("cap", 999)))

        notes_box: tk.Text = getattr(self, f"ability_notes_box_{key}")
        notes_box.delete("1.0", tk.END)
        notes_box.insert(tk.END, ab.get("notes", ""))

    def ability_update_selected(self, key: str):
        ab = self.ability_selected_ref.get(key)
        if ab is None:
            messagebox.showinfo("Update", "Select an ability first.")
            return

        ab["roll_type"] = self.ability_roll_type[key].get() or "None"
        ab["damage"] = self.ability_damage[key].get().strip()
        try:
            ab["mana_cost"] = int(self.ability_mana_cost[key].get().strip() or "0")
        except ValueError:
            ab["mana_cost"] = 0

        enabled = bool(self.ability_overcast_enabled[key].get())
        try:
            scale = int(self.ability_overcast_scale[key].get().strip() or "0")
        except ValueError:
            scale = 0
        try:
            power = float(self.ability_overcast_power[key].get().strip() or "0.85")
        except ValueError:
            power = 0.85
        try:
            cap = int(self.ability_overcast_cap[key].get().strip() or "999")
        except ValueError:
            cap = 999

        ab["overcast"] = {
            "enabled": enabled,
            "scale": max(0, scale),
            "power": max(0.1, power),
            "cap": max(0, cap),
        }

        notes_box: tk.Text = getattr(self, f"ability_notes_box_{key}")
        ab["notes"] = notes_box.get("1.0", tk.END).rstrip("\n")

        self.ability_render(key)
    def ability_copy_json_selected(self, slot: str):
        ab = self.ability_selected_ref.get(slot)
        if ab is None:
            messagebox.showinfo("Copy JSON", "Select an ability first.")
            return
        payload = self._clean_ability_for_json(ab)
        self._clipboard_set(json.dumps(payload, indent=2))
        messagebox.showinfo("Copy JSON", "Ability JSON copied to clipboard.")

    def ability_import_json_dialog(self, slot: str):
        win = tk.Toplevel(self)
        win.title(f"Import Ability JSON → {slot}")
        win.geometry("520x620")
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="Paste JSON for an ability OR a list of abilities:").pack(anchor="w", padx=10, pady=(10, 4))

        txt = tk.Text(win, wrap="none")
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        clip = self._clipboard_get()
        if clip.strip():
            txt.insert("1.0", clip)

        status = tk.StringVar(value="")
        ttk.Label(win, textvariable=status, foreground="gray").pack(anchor="w", padx=10, pady=(0, 8))

        def parse_abs():
            raw = txt.get("1.0", tk.END).strip()
            data = self._safe_json_loads(raw)
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                raise ValueError("JSON must be an object or a list of objects.")
            abs_ = [ensure_ability_obj(d) for d in data]  # your existing normalizer
            return abs_

        def add_abs():
            try:
                abs_ = parse_abs()
            except Exception as e:
                status.set(str(e))
                return
            for ab in abs_:
                if (ab.get("name") or "").strip():
                    self.abilities_data[slot].append(ab)
            self.ability_render(slot)
            self.refresh_combat_list()
            status.set(f"Added {len(abs_)} ability(s).")

        def replace_selected():
            target = self.ability_selected_ref.get(slot)
            if target is None:
                status.set("Select an ability first (or use Add).")
                return
            try:
                abs_ = parse_abs()
            except Exception as e:
                status.set(str(e))
                return
            if len(abs_) != 1:
                status.set("Replace requires exactly 1 ability object (not a list).")
                return
            new_ab = abs_[0]
            target.clear()
            target.update(new_ab)
            self.ability_render(slot)
            self.refresh_combat_list()
            status.set("Replaced selected ability.")

        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btns, text="Add", command=add_abs).pack(side=tk.LEFT)
        ttk.Button(btns, text="Replace Selected", command=replace_selected).pack(side=tk.LEFT, padx=8)
        ttk.Button(btns, text="Close", command=win.destroy).pack(side=tk.RIGHT)
    
    def ability_move_selected(self, from_slot: str, to_slot: str):
        if from_slot not in self.ability_keys or to_slot not in self.ability_keys:
            return
        if from_slot == to_slot:
            return

        ab = self.ability_selected_ref.get(from_slot)
        if ab is None:
            messagebox.showinfo("Move Ability", "Select an ability first.")
            return

        try:
            self.abilities_data[from_slot].remove(ab)
        except ValueError:
            self.ability_selected_ref[from_slot] = None
            return

        self.abilities_data[to_slot].append(ab)

        # Clear selection in old slot (since it moved)
        self.ability_selected_ref[from_slot] = None

        # Re-render both lists and refresh combat list
        self.ability_render(from_slot)
        self.ability_render(to_slot)
        self.refresh_combat_list()


    # ---------------- Notes / World ----------------

    def _build_notes_tab(self):
        frame = ttk.Frame(self.tab_notes)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(frame, text="Character Notes").pack(anchor="w")
        self.notes_text = tk.Text(frame, wrap="word")
        self.notes_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def _build_world_tab(self):
        frame = ttk.Frame(self.tab_world)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(frame, text="World & Campaign Rules (DM-provided)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Examples: point spending rules, tier changes, combat mechanics, death rules, etc.", foreground="gray").pack(anchor="w", pady=(0, 5))
        self.world_text = tk.Text(frame, wrap="word")
        self.world_text.pack(fill=tk.BOTH, expand=True)

    # ---------------- Damage Lab ----------------

    def _build_damage_lab_tab(self):
        self.damage_lab = DamageLabTab(
            self.tab_damage_lab,
            get_actions=self._damage_lab_get_actions,
            get_pbd=self._damage_lab_get_pbd,
            get_mana_density=self._damage_lab_get_mana_density,
        )
        self.damage_lab.pack(fill=tk.BOTH, expand=True)

    def _damage_lab_get_actions(self):
        self.refresh_combat_list()
        return self.combat_actions

    def _damage_lab_get_pbd(self):
        try:
            return int(self.var_pbd.get().strip())
        except ValueError:
            return 0

    def _damage_lab_get_mana_density(self):
        try:
            return int(self.var_mana_density.get().strip() or "0")
        except ValueError:
            return 0

    # ---------------- Combat Quick Use ----------------

    def refresh_combat_list(self):
        keep_ref = self.combat_selected_ref
        keep_kind = self.combat_selected_kind

        actions = []

        for it in self.inv_data.get("equipment", []):
            rng = "Ranged" if it.get("is_ranged", False) else "Melee"
            actions.append({
                "kind": "item",
                "slot": None,
                "ref": it,
                "favorite": bool(it.get("favorite", False)),
                "name": it.get("name", ""),
                "display": f"{'⭐ ' if it.get('favorite', False) else ''}{it.get('name','')}  (Item:{rng})",
            })

        for slot in ["core", "inner", "outer"]:
            for ab in self.abilities_data.get(slot, []):
                actions.append({
                    "kind": "ability",
                    "slot": slot,
                    "ref": ab,
                    "favorite": bool(ab.get("favorite", False)),
                    "name": ab.get("name", ""),
                    "display": f"{'⭐ ' if ab.get('favorite', False) else ''}{ab.get('name','')}  (Ability:{slot})",
                })

        actions = sorted(actions, key=lambda a: (not a["favorite"], a["name"].lower(), a["kind"], a.get("slot") or ""))
        self.combat_actions = actions

        self.combat_list.delete(0, tk.END)
        for a in actions:
            self.combat_list.insert(tk.END, a["display"])

        if keep_ref is not None:
            for idx, a in enumerate(self.combat_actions):
                if a["ref"] is keep_ref and a["kind"] == keep_kind:
                    self.combat_list.selection_set(idx)
                    self.combat_list.see(idx)
                    break

    def on_combat_select(self):
        sel = list(self.combat_list.curselection())
        if len(sel) != 1:
            self.combat_selected_ref = None
            self.combat_selected_kind = None
            return
        idx = sel[0]
        if not (0 <= idx < len(self.combat_actions)):
            self.combat_selected_ref = None
            self.combat_selected_kind = None
            return

        a = self.combat_actions[idx]
        ref = a["ref"]

        self.combat_selected_ref = ref
        self.combat_selected_kind = a["kind"]

        self.var_combat_roll_type.set(ref.get("roll_type", "None"))
        self.var_combat_damage_expr.set(ref.get("damage", ""))

        if a["kind"] == "ability":
            self.combat_mana_entry.configure(state="normal")
            self.var_combat_mana_spend.set(str(ref.get("mana_cost", 0)))
        else:
            self.var_combat_mana_spend.set("")
            self.combat_mana_entry.configure(state="disabled")

        self.var_combat_result.set("")
        self.var_combat_roll_value.set("")

    def use_combat_action(self):
        if self.combat_selected_ref is None:
            messagebox.showinfo("Combat", "Select an item or ability first.")
            return

        chosen = None
        for a in self.combat_actions:
            if a["ref"] is self.combat_selected_ref and a["kind"] == self.combat_selected_kind:
                chosen = a
                break
        if chosen is None:
            messagebox.showinfo("Combat", "Selection is out of date. Hit Refresh list and re-select.")
            return

        ref = chosen["ref"]

        try:
            rolled = int(self.var_combat_roll_value.get().strip())
        except ValueError:
            messagebox.showwarning("Combat", "Enter the rolled dice total (ex: 7).")
            return

        dmg_expr = (ref.get("damage", "") or "").strip()
        parsed = parse_damage_expr(dmg_expr)
        if parsed is None:
            dice_count, die_size, flat_bonus = (1, 10, 0)
        else:
            dice_count, die_size, flat_bonus = parsed

        base = rolled + flat_bonus

        # -------- Items: apply PBD (melee) or Precision (ranged) --------
        if chosen["kind"] == "item":
            apply_bonus = bool(ref.get("apply_bonus", ref.get("apply_pbd", True)))
            is_ranged = bool(ref.get("is_ranged", False))

            if not apply_bonus:
                self.var_combat_result.set(f"Item: base {base} (rolled {rolled} + flat {flat_bonus}) → Total {base} (no bonus)")
                return

            max_roll = max(1, dice_count * die_size)
            pct = clamp(rolled / max_roll, 0.0, 1.0)
            max_factor = max_pbd_factor_for_die(die_size)

            if is_ranged:
                # Precision bonus for ranged
                try:
                    precision = int(self.var_stats["precision"].get().strip() or "0")
                except Exception:
                    precision = 0
                add = int(precision * pct * max_factor)
                label = "Precision"
            else:
                # PBD bonus for melee
                try:
                    pbd = int(self.var_pbd.get().strip() or "0")
                except Exception:
                    pbd = 0
                add = int(pbd * pct * max_factor)
                label = "PBD"

            total = base + add
            pct_display = int(round(pct * 100))
            self.var_combat_result.set(
                f"Item: base {base} (rolled {rolled} + flat {flat_bonus}) "
                f"+ {label} add {add} ({pct_display}% of max {max_roll}, die d{die_size}, factor {max_factor:.2f}) "
                f"→ Total {total}"
            )
            return

        # -------- Abilities: NO PBD/Precision, slot multipliers + overcast + mana density --------
        slot = chosen.get("slot", "inner")
        mods = ABILITY_MODS.get(slot, {"dmg": 1.0, "mana": 1.0})
        dmg_mult = float(mods["dmg"])
        mana_mult = float(mods["mana"])

        base_cost = int(ref.get("mana_cost", 0) or 0)
        if base_cost <= 0:
            messagebox.showwarning("Combat", "This ability has no mana_cost set (or it's 0). Set a base mana cost.")
            return

        try:
            spend_base = int((self.var_combat_mana_spend.get().strip() or str(base_cost)).strip())
        except ValueError:
            spend_base = base_cost

        if spend_base < base_cost:
            messagebox.showwarning("Combat", f"Not enough mana allocated. Base cost is {base_cost}.")
            return

        base_eff = int(math.ceil(base_cost * mana_mult))
        spent_eff = int(math.ceil(spend_base * mana_mult))

        try:
            cur_mana = int(self.var_mana_current.get())
        except ValueError:
            cur_mana = 0

        if spent_eff > cur_mana:
            messagebox.showwarning("Combat", f"Not enough mana. You have {cur_mana}, need {spent_eff} (slot-adjusted).")
            return

        try:
            md_pts = int(self.var_mana_density.get().strip() or "0")
        except ValueError:
            md_pts = 0
        md_mult = mana_density_multiplier(md_pts)

        over_bonus = compute_overcast_bonus(base_eff, spent_eff, ref.get("overcast", {}))
        total = int(math.floor((base + over_bonus) * dmg_mult * md_mult))

        self.var_mana_current.set(str(cur_mana - spent_eff))

        ratio = spent_eff / base_eff if base_eff > 0 else 1.0
        self.var_combat_result.set(
            f"{slot.title()} ability: base {base} (rolled {rolled} + flat {flat_bonus}), "
            f"overcast +{over_bonus} (spent {spent_eff}/{base_eff}={ratio:.2f}x), "
            f"*{dmg_mult:.2f} slot *{md_mult:.2f} mana density → {total}. Mana spent: {spent_eff}."
        )

    # ---------------- HP / Rest ----------------

    def apply_hp_damage(self):
        try:
            dmg = int(self.var_hp_dmg.get().strip())
        except ValueError:
            messagebox.showwarning("HP", "Enter a damage number.")
            return

        try:
            cur = int(self.var_hp_current.get())
            mx = int(self.var_hp_max.get())
        except ValueError:
            return

        cur = max(0, min(mx, cur - dmg))
        self.var_hp_current.set(str(cur))
        self.var_hp_dmg.set("")

    def apply_hp_heal(self):
        try:
            heal = int(self.var_hp_heal.get().strip())
        except ValueError:
            messagebox.showwarning("HP", "Enter a heal number.")
            return

        try:
            cur = int(self.var_hp_current.get())
            mx = int(self.var_hp_max.get())
        except ValueError:
            return

        cur = max(0, min(mx, cur + heal))
        self.var_hp_current.set(str(cur))
        self.var_hp_heal.set("")

    def apply_incoming_hit(self):
        """
        Apply an incoming hit to HP after flat DR from Physical Defense.
        DR = floor(phys_def / 5).
        """
        try:
            incoming = int(self.var_hit_incoming.get().strip())
        except ValueError:
            messagebox.showwarning("Hit", "Enter an incoming hit damage number.")
            return

        try:
            cur = int(self.var_hp_current.get())
            mx = int(self.var_hp_max.get())
        except ValueError:
            return

        try:
            phys_def_pts = int(self.var_stats["phys_def"].get().strip() or "0")
        except Exception:
            phys_def_pts = 0

        dr = phys_dr_from_points(phys_def_pts)
        final = max(0, incoming - dr)

        new_hp = max(0, min(mx, cur - final))
        self.var_hp_current.set(str(new_hp))
        self.var_hit_incoming.set("")
        self.var_hit_result.set(f"Hit {incoming} - DR {dr} = {final} → HP {new_hp}/{mx}")

    def _reset_long_rest_uses(self):
        self.var_show_used.set(False)

    def apply_long_rest(self):
        try:
            hp_mx = int(self.var_hp_max.get())
        except ValueError:
            hp_mx = 0
        try:
            mana_mx = int(self.var_mana_max.get())
        except ValueError:
            mana_mx = 0

        self.var_hp_current.set(str(hp_mx))
        self.var_mana_current.set(str(mana_mx))
        self._reset_long_rest_uses()
        messagebox.showinfo("Long Rest", "HP and Mana restored to full. Long-rest uses reset.")

    # ---------------- Mana density label ----------------

    def _refresh_mana_density_display(self):
        try:
            pts = int(self.var_mana_density.get().strip() or "0")
        except ValueError:
            pts = 0
        self.var_mana_density_mult.set(f"x{mana_density_multiplier(pts):.2f}")

    # ---------------- Spend Points Popup ----------------

    def open_spend_points_popup(self):
        win = tk.Toplevel(self)
        win.title("Spend Points")
        win.geometry("600x580")
        win.transient(self)
        win.grab_set()

        # Current points
        top = ttk.Frame(win)
        top.pack(fill=tk.X, padx=10, pady=10)

        lbl_unspent = ttk.Label(top, text="")
        lbl_unspent.pack(anchor="w")

        def refresh_unspent_label():
            try:
                u = int(self.var_unspent.get().strip() or "0")
            except ValueError:
                u = 0
            lbl_unspent.config(text=f"Unspent points: {u}")

        refresh_unspent_label()

        # Target picker
        mid = ttk.LabelFrame(win, text="Choose where to spend")
        mid.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        target_var = tk.StringVar(value="hp")

        targets = [
            ("HP (Tier 1 rule)", "hp"),
            ("Mana (Tier 1 rule)", "mana"),
            ("PBD (Tier 1 rule)", "pbd"),
            ("Mana Density (+1 per point)", "mana_density"),
            ("", "sep"),
        ]
        for k, lab in STAT_ORDER:
            targets.append((f"{lab} (+1 per point)", f"stat:{k}"))

        # Use listbox
        lb = tk.Listbox(mid, height=18, exportselection=False)
        lb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        index_to_id = []
        for label, tid in targets:
            if tid == "sep":
                lb.insert(tk.END, "— Stats —")
                index_to_id.append("sep")
            else:
                lb.insert(tk.END, label)
                index_to_id.append(tid)

        # default selection first item
        lb.selection_set(0)
        lb.see(0)

        # Amount controls
        amt = ttk.LabelFrame(win, text="Amount to allocate (in unspent points)")
        amt.pack(fill=tk.X, padx=10, pady=(0, 10))

        amount_entry_var = tk.StringVar(value="1")

        row1 = ttk.Frame(amt)
        row1.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(row1, text="Amount:").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=amount_entry_var, width=8).pack(side=tk.LEFT, padx=(6, 0))
        info = ttk.Label(row1, text="(You can also use the quick buttons)", foreground="gray")
        info.pack(side=tk.LEFT, padx=10)

        row2 = ttk.Frame(amt)
        row2.pack(fill=tk.X, padx=8, pady=(0, 8))

        def set_amt(v: int):
            amount_entry_var.set(str(max(0, int(v))))

        def set_pct(pct: float):
            try:
                u = int(self.var_unspent.get().strip() or "0")
            except ValueError:
                u = 0
            set_amt(int(math.floor(u * pct)))

        ttk.Button(row2, text="1", command=lambda: set_amt(1)).pack(side=tk.LEFT)
        ttk.Button(row2, text="5", command=lambda: set_amt(5)).pack(side=tk.LEFT, padx=4)
        ttk.Button(row2, text="10", command=lambda: set_amt(10)).pack(side=tk.LEFT, padx=4)
        ttk.Button(row2, text="10%", command=lambda: set_pct(0.10)).pack(side=tk.LEFT, padx=4)
        ttk.Button(row2, text="25%", command=lambda: set_pct(0.25)).pack(side=tk.LEFT, padx=4)
        ttk.Button(row2, text="50%", command=lambda: set_pct(0.50)).pack(side=tk.LEFT, padx=4)
        ttk.Button(row2, text="Max", command=lambda: set_pct(1.00)).pack(side=tk.RIGHT)

        # Apply button
        bottom = ttk.Frame(win)
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))

        result_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=result_var, foreground="gray").pack(anchor="w")

        def get_selected_target_id():
            sel = list(lb.curselection())
            if len(sel) != 1:
                return None
            tid = index_to_id[sel[0]]
            if tid == "sep":
                return None
            return tid

        def apply_spend():
            tid = get_selected_target_id()
            if not tid:
                result_var.set("Pick a valid target (not the separator).")
                return

            try:
                budget = int(amount_entry_var.get().strip() or "0")
            except ValueError:
                budget = 0
            if budget <= 0:
                result_var.set("Amount must be > 0.")
                return

            try:
                unspent = int(self.var_unspent.get().strip() or "0")
            except ValueError:
                unspent = 0
            if unspent <= 0:
                result_var.set("You have 0 unspent points.")
                return

            budget = min(budget, unspent)

            spent, gained_text = self._spend_points_to_target(tid, budget)

            if spent <= 0:
                result_var.set("No points spent (possibly not enough to meet costs).")
                return

            self.var_unspent.set(str(unspent - spent))
            self._refresh_mana_density_display()
            refresh_unspent_label()
            result_var.set(f"Spent {spent}. {gained_text}")

        ttk.Button(bottom, text="Spend", command=apply_spend).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Close", command=win.destroy).pack(side=tk.RIGHT)

    def _spend_points_to_target(self, target_id: str, budget: int):
        """
        Spends up to `budget` unspent points into the chosen target.
        Returns (points_spent, gained_text)
        """
        spent = 0

        def to_int(s, default=0):
            try:
                return int(s)
            except Exception:
                return default

        # HP: 1 point each, gain depends on current max
        if target_id == "hp":
            cur = to_int(self.var_hp_current.get(), 0)
            mx = to_int(self.var_hp_max.get(), 0)
            gained = 0
            for _ in range(budget):
                gain = T1_HP_GAIN_BEFORE_CAP if mx < T1_HP_SOFT_CAP else T1_HP_GAIN_AFTER_CAP
                mx += gain
                cur += gain
                gained += gain
                spent += 1
            self.var_hp_max.set(str(mx))
            self.var_hp_current.set(str(cur))
            return spent, f"HP +{gained} (max/current)."

        # Mana: cost/gain depends on current max
        if target_id == "mana":
            cur = to_int(self.var_mana_current.get(), 0)
            mx = to_int(self.var_mana_max.get(), 0)
            gained = 0
            while True:
                cost, gain = (1, 1) if mx < 50 else (3, 2)
                if spent + cost > budget:
                    break
                spent += cost
                mx += gain
                cur += gain
                gained += gain
            self.var_mana_max.set(str(mx))
            self.var_mana_current.set(str(cur))
            return spent, f"Mana +{gained} (max/current)."

        # PBD: cost varies by current PBD
        if target_id == "pbd":
            pbd = to_int(self.var_pbd.get(), 0)
            gained = 0
            while True:
                if pbd < T1_PBD_SOFT_CAP:
                    cost, gain = (T1_PBD_COST_BEFORE_CAP, T1_PBD_GAIN_BEFORE_CAP)
                else:
                    cost, gain = (T1_PBD_COST_AFTER_CAP, T1_PBD_GAIN_AFTER_CAP)

                if spent + cost > budget:
                    break

                spent += cost
                pbd += gain
                gained += gain
            self.var_pbd.set(str(pbd))
            return spent, f"PBD +{gained}."

        # Mana density: 1 point each => +1
        if target_id == "mana_density":
            md = to_int(self.var_mana_density.get(), 0)
            md += budget
            spent = budget
            self.var_mana_density.set(str(md))
            return spent, f"Mana Density +{budget}."

        # Stats: 1 point each => +1
        if target_id.startswith("stat:"):
            k = target_id.split(":", 1)[1]
            if k not in self.var_stats:
                return 0, "Unknown stat."
            cur = to_int(self.var_stats[k].get(), 0)
            cur += budget
            spent = budget
            self.var_stats[k].set(str(cur))
            return spent, f"{dict(STAT_ORDER).get(k, k)} +{budget}."

        return 0, "Unknown target."

    # ---------------- Sync ----------------

    def refresh_from_model(self):
        c = self.char
        _migrate_stats_schema(c)

        self.var_name.set(c.get("name", ""))
        self.var_tier.set(c.get("tier", ""))

        res = c.get("resources", {})
        hp = res.get("hp", {})
        mana = res.get("mana", {})
        self.var_hp_current.set(str(hp.get("current", 0)))
        self.var_hp_max.set(str(hp.get("max", 0)))
        self.var_mana_current.set(str(mana.get("current", 0)))
        self.var_mana_max.set(str(mana.get("max", 0)))
        self.var_pbd.set(str(res.get("pbd", 0)))
        self.var_mana_density.set(str(res.get("mana_density", 0)))
        self._refresh_mana_density_display()
        self.var_unspent.set(str(res.get("unspent_points", 0)))

        stats = c.get("stats", {})
        for k in STAT_KEYS:
            self.var_stats[k].set(str(stats.get(k, 0)))

        growth = c.get("growth_items", {})
        self.var_growth_current.set(str(growth.get("bound_current", 0)))
        self.var_growth_max.set(str(growth.get("bound_max", 0)))

        inv = c.get("inventory")
        if not isinstance(inv, dict):
            inv = {"equipment": [], "bag": [], "storage": []}
            c["inventory"] = inv

        for k in self.inv_keys:
            raw = inv.get(k, [])
            self.inv_data[k] = sort_favorites_first([ensure_item_obj(x) for x in (raw if isinstance(raw, list) else [])])
            self.inv_selected_ref[k] = None
            self.inv_render(k)

            self.inv_roll_type[k].set("None")
            self.inv_damage[k].set("")
            self.inv_apply_bonus[k].set(True)
            self.inv_is_ranged[k].set(False)
            nb: tk.Text = getattr(self, f"inv_notes_box_{k}")
            nb.delete("1.0", tk.END)

        ab_all = c.get("abilities")
        if not isinstance(ab_all, dict):
            ab_all = {"core": [], "inner": [], "outer": []}
            c["abilities"] = ab_all

        for slot in self.ability_keys:
            raw = ab_all.get(slot, [])
            self.abilities_data[slot] = sort_favorites_first([ensure_ability_obj(x) for x in (raw if isinstance(raw, list) else [])])
            self.ability_selected_ref[slot] = None
            self.ability_render(slot)

            self.ability_roll_type[slot].set("None")
            self.ability_damage[slot].set("")
            self.ability_mana_cost[slot].set("0")
            self.ability_overcast_enabled[slot].set(False)
            self.ability_overcast_scale[slot].set("0")
            self.ability_overcast_power[slot].set("0.85")
            self.ability_overcast_cap[slot].set("999")

            nb: tk.Text = getattr(self, f"ability_notes_box_{slot}")
            nb.delete("1.0", tk.END)

        eff = find_show_must_go_on(c)
        if eff and "uses" in eff:
            uses = eff["uses"]
            self.var_show_used.set(uses.get("used", 0) >= uses.get("max", 1))
        else:
            self.var_show_used.set(False)

        self.notes_text.delete("1.0", tk.END)
        self.notes_text.insert(tk.END, self.char.get("notes", ""))

        self.world_text.delete("1.0", tk.END)
        self.world_text.insert(tk.END, self.char.get("world_info", ""))

        self.refresh_combat_list()
        self.combat_mana_entry.configure(state="disabled")

        self.var_hit_result.set("")

    def apply_to_model(self):
        c = self.char
        c["name"] = self.var_name.get()
        c["tier"] = self.var_tier.get()

        def to_int_var(var, default=0):
            try:
                return int(var.get())
            except ValueError:
                return default

        res = c.setdefault("resources", {})
        hp = res.setdefault("hp", {})
        mana = res.setdefault("mana", {})

        hp["current"] = to_int_var(self.var_hp_current)
        hp["max"] = to_int_var(self.var_hp_max)
        mana["current"] = to_int_var(self.var_mana_current)
        mana["max"] = to_int_var(self.var_mana_max)

        try:
            res["mana_density"] = int(self.var_mana_density.get().strip() or "0")
        except ValueError:
            res["mana_density"] = 0

        res["pbd"] = to_int_var(self.var_pbd)
        res["unspent_points"] = to_int_var(self.var_unspent)

        stats = c.setdefault("stats", {})
        for k in STAT_KEYS:
            try:
                stats[k] = int(self.var_stats[k].get().strip() or "0")
            except Exception:
                stats[k] = 0

        growth = c.setdefault("growth_items", {})
        growth["bound_current"] = to_int_var(self.var_growth_current)
        growth["bound_max"] = to_int_var(self.var_growth_max)

        # Inventory save
        inv = c.setdefault("inventory", {"equipment": [], "bag": [], "storage": []})
        for k in self.inv_keys:
            cleaned = []
            for it in self.inv_data[k]:
                name = (it.get("name") or "").strip()
                if not name:
                    continue
                apply_bonus = bool(it.get("apply_bonus", it.get("apply_pbd", True)))
                cleaned.append({
                    "name": name,
                    "favorite": bool(it.get("favorite", False)),
                    "roll_type": it.get("roll_type", "None"),
                    "damage": it.get("damage", ""),
                    "notes": it.get("notes", ""),
                    "apply_bonus": apply_bonus,
                    "apply_pbd": apply_bonus,       # back-compat
                    "is_ranged": bool(it.get("is_ranged", False)),
                })
            inv[k] = cleaned

        # Abilities save
        ab_all = c.setdefault("abilities", {"core": [], "inner": [], "outer": []})
        for slot in self.ability_keys:
            cleaned = []
            for ab in self.abilities_data[slot]:
                name = (ab.get("name") or "").strip()
                if not name:
                    continue
                cleaned.append({
                    "name": name,
                    "favorite": bool(ab.get("favorite", False)),
                    "roll_type": ab.get("roll_type", "None"),
                    "damage": ab.get("damage", ""),
                    "mana_cost": int(ab.get("mana_cost", 0) or 0),
                    "overcast": ab.get("overcast", {"enabled": False, "scale": 0, "power": 0.85, "cap": 999}),
                    "notes": ab.get("notes", ""),
                })
            ab_all[slot] = cleaned

        c["notes"] = self.notes_text.get("1.0", tk.END).rstrip("\n")
        c["world_info"] = self.world_text.get("1.0", tk.END).rstrip("\n")


    # ---------------- Save ----------------

    def on_save(self):
        self._save_to_disk(show_popup=True)



if __name__ == "__main__":
    path = pick_character_file()
    if not path:
        sys.exit(0)

    app = CharacterApp(path)
    app.mainloop()
