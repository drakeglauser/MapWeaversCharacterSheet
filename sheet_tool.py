import json
from pathlib import Path
import tkinter as tk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from damage_lab import DamageLabTab
import re
import math

CHAR_PATH = Path("joe.json")

ROLL_TYPES = ["None", "Attack", "Save", "Check"]

ABILITY_MODS = {
    "core":  {"dmg": 1.50, "mana": 0.75},
    "inner": {"dmg": 1.00, "mana": 1.00},
    "outer": {"dmg": 0.75, "mana": 2.00},
}

# ---------- Tier 1 tuning ----------
T1_HP_SOFT_CAP = 100
T1_HP_GAIN_BEFORE_CAP = 2
T1_HP_GAIN_AFTER_CAP = 1  # tweak if you want a different post-cap rate

T1_PBD_SOFT_CAP = 15
T1_PBD_COST_BEFORE_CAP = 3
T1_PBD_GAIN_BEFORE_CAP = 1
T1_PBD_COST_AFTER_CAP = 5   # tweak if you want harsher/softer beyond cap
T1_PBD_GAIN_AFTER_CAP = 1

def parse_damage_expr(expr: str):
    """
    Parses basic forms like:
      '1d10'
      '2d6+3'
      '3d8-2'
    Returns (dice_count, die_size, flat_bonus) or None if no dice found.
    """
    if not expr:
        return None
    s = expr.replace(" ", "").lower()

    m = re.search(r'(\d*)d(\d+)', s)
    if not m:
        return None

    count_str, die_str = m.group(1), m.group(2)
    dice_count = int(count_str) if count_str else 1
    die_size = int(die_str)

    # Sum all +N/-N after the dice part (simple but effective)
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


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_overcast_bonus(base_cost_eff: int, spent_eff: int, over: dict) -> int:
    """
    Log-ish overcast bonus:
      bonus = floor(scale * (log2(spent/base))^power), capped.
    """
    if base_cost_eff <= 0 or spent_eff <= base_cost_eff:
        return 0
    if not isinstance(over, dict):
        return 0
    if not over.get("enabled", False):
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

ROLL_TYPES = ["None", "Attack", "Save", "Check"]


def default_character_template(name="New Hero"):
    return {
        "name": name,
        "tier": "T1",
        "resources": {
            "hp": {"current": 20, "max": 20},
            "mana": {"current": 10, "max": 10},
            "pbd": 0,
            "unspent_points": 0
        },
        "stats": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10, "san": 10, "hnr": 10},
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


def pick_character_file():
    """
    Returns Path or None (if user cancels / exits).
    """
    # Needs a root for dialogs, but we don't want a blank window yet.
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
            # write a starter file immediately
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



def find_show_must_go_on(char):
    t1 = char.get("talents", {}).get("T1")
    if not t1:
        return None
    for eff in t1.get("effects", []):
        if eff.get("id") == "show_must_go_on":
            return eff
    return None


def sort_favorites_first(items):
    return sorted(items, key=lambda it: (not bool(it.get("favorite", False)), it.get("name", "").lower()))


def ensure_item_obj(x):
    """
    Items are assumed to be melee by default for PBD purposes.
    If you add a ranged weapon later, set "apply_pbd": false on that item.
    """
    if isinstance(x, str):
        return {
            "name": x,
            "favorite": False,
            "roll_type": "None",
            "damage": "",
            "notes": "",
            "apply_pbd": True
        }
    if isinstance(x, dict):
        return {
            "name": x.get("name", ""),
            "favorite": bool(x.get("favorite", False)),
            "roll_type": x.get("roll_type", "None"),
            "damage": x.get("damage", ""),
            "notes": x.get("notes", ""),
            "apply_pbd": bool(x.get("apply_pbd", True)),
        }
    return {"name": "", "favorite": False, "roll_type": "None", "damage": "", "notes": "", "apply_pbd": True}


def ensure_ability_obj(x):
    """
    Abilities NEVER use PBD. They can optionally have overcast scaling.
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


class CharacterApp(tk.Tk):
    
    def __init__(self, char_path: Path):
        super().__init__()

        self.char_path = char_path
        self.title(f"Homebrew Character Sheet — {self.char_path.name}")
        self.geometry("1150x750")

        self.char = load_character(self.char_path)


        # ----- Vars -----
        self.var_name = tk.StringVar()
        self.var_tier = tk.StringVar()

        self.var_hp_current = tk.StringVar()
        self.var_hp_max = tk.StringVar()
        self.var_mana_current = tk.StringVar()
        self.var_mana_max = tk.StringVar()
        self.var_pbd = tk.StringVar()
        self.var_unspent = tk.StringVar()

        self.var_hp_dmg = tk.StringVar()
        self.var_hp_heal = tk.StringVar()

        self.var_core_current = tk.StringVar()
        self.var_core_max = tk.StringVar()
        self.var_inner_current = tk.StringVar()
        self.var_inner_max = tk.StringVar()
        self.var_outer_current = tk.StringVar()
        self.var_outer_max = tk.StringVar()

        self.var_stats = {k: tk.StringVar() for k in ["str","dex","con","int","wis","cha","san","hnr"]}

        self.var_growth_current = tk.StringVar()
        self.var_growth_max = tk.StringVar()

        self.var_show_used = tk.BooleanVar()

        # Inventory internal data (sub-tabs)
        self.inv_keys = ["equipment", "bag", "storage"]
        self.inv_data = {k: [] for k in self.inv_keys}

        # IMPORTANT: store selected object ref (not index) so re-renders don't break selection
        self.inv_selected_ref = {k: None for k in self.inv_keys}

        self.inv_new_name = {k: tk.StringVar() for k in self.inv_keys}
        self.inv_roll_type = {k: tk.StringVar(value="None") for k in self.inv_keys}
        self.inv_damage = {k: tk.StringVar() for k in self.inv_keys}
        self.inv_apply_pbd = {k: tk.BooleanVar(value=True) for k in self.inv_keys}

        # ---- Abilities ----
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
        self.tab_talents = ttk.Frame(self.tabs)
        self.tab_inventory = ttk.Frame(self.tabs)
        self.tab_abilities = ttk.Frame(self.tabs)
        self.tab_notes = ttk.Frame(self.tabs)
        self.tab_world = ttk.Frame(self.tabs)
        self.tab_damage_lab = ttk.Frame(self.tabs)


        self.tabs.add(self.tab_overview, text="Overview")
        self.tabs.add(self.tab_talents, text="Talents")
        self.tabs.add(self.tab_inventory, text="Inventory")
        self.tabs.add(self.tab_abilities, text="Abilities")
        self.tabs.add(self.tab_notes, text="Notes")
        self.tabs.add(self.tab_world, text="World Info")
        self.tabs.add(self.tab_damage_lab, text="Damage Lab")

        self._build_overview_tab()
        self._build_talents_tab()
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

        for row, key in enumerate(["str","dex","con","int","wis","cha","san","hnr"]):
            ttk.Label(stats_frame, text=key.upper()+":").grid(row=row, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(stats_frame, textvariable=self.var_stats[key], width=6).grid(row=row, column=1, sticky="w", padx=4, pady=2)

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

        ttk.Separator(res_frame, orient="horizontal").grid(row=3, column=0, columnspan=4, sticky="ew", padx=4, pady=6)

        ttk.Label(res_frame, text="Mana:").grid(row=4, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_mana_current, width=6).grid(row=4, column=1)
        ttk.Label(res_frame, text="/").grid(row=4, column=2)
        ttk.Entry(res_frame, textvariable=self.var_mana_max, width=6).grid(row=4, column=3)

        ttk.Label(res_frame, text="PBD:").grid(row=5, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_pbd, width=6).grid(row=5, column=1)

        ttk.Label(res_frame, text="Unspent pts:").grid(row=6, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_unspent, width=6).grid(row=6, column=1)

        ttk.Button(res_frame, text="Long Rest (full HP/Mana)", command=self.apply_long_rest).grid(
            row=7, column=0, columnspan=4, sticky="ew", padx=4, pady=(8, 4)
        )

        # Spend Points (Tier 1)
        spend_frame = ttk.LabelFrame(left, text="Spend Points (Tier 1)")
        spend_frame.pack(fill=tk.X, pady=6)

        ttk.Button(spend_frame, text="Spend → HP", command=self.spend_points_for_hp_t1).grid(row=0, column=0, padx=4, pady=6, sticky="ew")
        ttk.Button(spend_frame, text="Spend → Mana", command=self.spend_points_for_mana_t1).grid(row=0, column=1, padx=4, pady=6, sticky="ew")
        ttk.Button(spend_frame, text="Spend → PBD", command=self.spend_points_for_pbd_t1).grid(row=0, column=2, padx=4, pady=6, sticky="ew")
        for i in range(3):
            spend_frame.grid_columnconfigure(i, weight=1)

        # Skills
        skills_frame = ttk.LabelFrame(right, text="Skills")
        skills_frame.pack(fill=tk.X, pady=6)

        def skill_row(r, label, cur, mx):
            ttk.Label(skills_frame, text=label).grid(row=r, column=0, sticky="w", padx=4, pady=4)
            ttk.Entry(skills_frame, textvariable=cur, width=6).grid(row=r, column=1)
            ttk.Label(skills_frame, text="/").grid(row=r, column=2)
            ttk.Entry(skills_frame, textvariable=mx, width=6).grid(row=r, column=3)

        skill_row(0, "Core:", self.var_core_current, self.var_core_max)
        skill_row(1, "Inner:", self.var_inner_current, self.var_inner_max)
        skill_row(2, "Outer:", self.var_outer_current, self.var_outer_max)

        # Growth items
        growth_frame = ttk.LabelFrame(right, text="Growth Items Bound")
        growth_frame.pack(fill=tk.X, pady=6)

        ttk.Entry(growth_frame, textvariable=self.var_growth_current, width=6).grid(row=0, column=0, padx=4, pady=6)
        ttk.Label(growth_frame, text="/").grid(row=0, column=1)
        ttk.Entry(growth_frame, textvariable=self.var_growth_max, width=6).grid(row=0, column=2, padx=4, pady=6)

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

    def _build_talents_tab(self):
        frame = ttk.Frame(self.tab_talents)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.talent_text = tk.Text(frame, wrap="word")
        self.talent_text.pack(fill=tk.BOTH, expand=True)
        self.talent_text.configure(state="disabled")

        bottom = ttk.Frame(frame)
        bottom.pack(fill=tk.X, pady=(8, 0))

        ttk.Checkbutton(
            bottom,
            text="The Show Must Go On used (per long rest)",
            variable=self.var_show_used,
            command=self.on_toggle_show_used,
        ).pack(side=tk.LEFT)

        ttk.Button(bottom, text="Refresh", command=self._refresh_talent_text).pack(side=tk.RIGHT)

    # ---------------- Inventory ----------------

    def _build_inventory_tab(self):
        frame = ttk.Frame(self.tab_inventory)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

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

        lb = tk.Listbox(left, height=18)
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

        ttk.Checkbutton(details, text="Apply PBD (melee)", variable=self.inv_apply_pbd[key]).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 6)
        )

        ttk.Label(details, text="Notes:").grid(row=3, column=0, sticky="nw", padx=6, pady=4)
        notes_box = tk.Text(details, wrap="word", height=10)
        notes_box.grid(row=3, column=1, sticky="nsew", padx=6, pady=4)
        setattr(self, f"inv_notes_box_{key}", notes_box)

        ttk.Button(details, text="Update Selected", command=lambda k=key: self.inv_update_selected(k)).grid(
            row=4, column=1, sticky="w", padx=6, pady=(6, 8)
        )

        details.grid_columnconfigure(1, weight=1)
        details.grid_rowconfigure(3, weight=1)

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
            lb.insert(tk.END, f"{star}{it.get('name','')}")

        # restore selection after re-render
        self._select_ref_in_listbox(lb, self.inv_data[key], selected_ref)
        self.refresh_combat_list()

    def inv_add(self, key: str):
        name = self.inv_new_name[key].get().strip()
        if not name:
            return
        self.inv_data[key].append({
            "name": name, "favorite": False, "roll_type": "None",
            "damage": "", "notes": "", "apply_pbd": True
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
            self.inv_selected_ref[key] = None
            return
        idx = sel[0]
        it = self.inv_data[key][idx]
        self.inv_selected_ref[key] = it

        self.inv_roll_type[key].set(it.get("roll_type", "None"))
        self.inv_damage[key].set(it.get("damage", ""))
        self.inv_apply_pbd[key].set(bool(it.get("apply_pbd", True)))

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
        it["apply_pbd"] = bool(self.inv_apply_pbd[key].get())

        notes_box: tk.Text = getattr(self, f"inv_notes_box_{key}")
        it["notes"] = notes_box.get("1.0", tk.END).rstrip("\n")

        self.inv_render(key)

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

    # ---------------- Combat Quick Use ----------------

    def refresh_combat_list(self):
        # Keep old selection by ref
        keep_ref = self.combat_selected_ref
        keep_kind = self.combat_selected_kind

        actions = []

        # Equipment (usually where weapons live)
        for it in self.inv_data.get("equipment", []):
            actions.append({
                "kind": "item",
                "slot": None,
                "ref": it,
                "favorite": bool(it.get("favorite", False)),
                "name": it.get("name", ""),
                "display": f"{'⭐ ' if it.get('favorite', False) else ''}{it.get('name','')}  (Item)",
            })

        # Abilities: core/inner/outer
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

        # restore selection
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

        # find current selected action wrapper (because list can change)
        chosen = None
        for a in self.combat_actions:
            if a["ref"] is self.combat_selected_ref and a["kind"] == self.combat_selected_kind:
                chosen = a
                break
        if chosen is None:
            messagebox.showinfo("Combat", "Selection is out of date. Hit Refresh list and re-select.")
            return

        ref = chosen["ref"]

        # rolled dice total (sum of dice results)
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

        # -------- Items: use PBD scaling (if enabled on the item) --------
        if chosen["kind"] == "item":
            apply_pbd = bool(ref.get("apply_pbd", True))
            pbd_add = 0

            if apply_pbd:
                try:
                    pbd = int(self.var_pbd.get().strip())
                except ValueError:
                    pbd = 0

                max_roll = max(1, dice_count * die_size)
                pct = clamp(rolled / max_roll, 0.0, 1.0)
                max_factor = max_pbd_factor_for_die(die_size)
                pbd_add = int(pbd * pct * max_factor)

                pct_display = int(round(pct * 100))
                total = base + pbd_add
                self.var_combat_result.set(
                    f"Item: base {base} (rolled {rolled} + flat {flat_bonus}) "
                    f"+ PBD add {pbd_add} ({pct_display}% of max {max_roll}, die d{die_size}, factor {max_factor:.2f}) "
                    f"→ Total {total}"
                )
            else:
                self.var_combat_result.set(f"Item: base {base} (rolled {rolled} + flat {flat_bonus}) → Total {base} (no PBD)")

            return

        # -------- Abilities: NO PBD, slot multipliers + overcast --------
        slot = chosen.get("slot", "inner")
        mods = ABILITY_MODS.get(slot, {"dmg": 1.0, "mana": 1.0})
        dmg_mult = mods["dmg"]
        mana_mult = mods["mana"]

        # Base mana cost (required)
        base_cost = int(ref.get("mana_cost", 0) or 0)
        if base_cost <= 0:
            messagebox.showwarning("Combat", "This ability has no mana_cost set (or it's 0). Set a base mana cost.")
            return

        # Spend input is BASE (pre-slot) spend
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

        over_bonus = compute_overcast_bonus(base_eff, spent_eff, ref.get("overcast", {}))
        total = int(math.floor((base + over_bonus) * dmg_mult))

        # spend mana
        self.var_mana_current.set(str(cur_mana - spent_eff))

        ratio = spent_eff / base_eff if base_eff > 0 else 1.0
        self.var_combat_result.set(
            f"{slot.title()} ability: base {base} (rolled {rolled} + flat {flat_bonus}), "
            f"overcast +{over_bonus} (spent {spent_eff}/{base_eff}={ratio:.2f}x), "
            f"*{dmg_mult:.2f} → {total}. Mana spent: {spent_eff}."
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

    def _reset_long_rest_uses(self):
        talents = self.char.get("talents", {})
        if not isinstance(talents, dict):
            return
        for tier_key, tier in talents.items():
            if not isinstance(tier, dict):
                continue
            effects = tier.get("effects", [])
            if not isinstance(effects, list):
                continue
            for eff in effects:
                if not isinstance(eff, dict):
                    continue
                uses = eff.get("uses")
                if isinstance(uses, dict) and uses.get("per") == "long_rest":
                    uses["used"] = 0
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
        self._refresh_talent_text()
        messagebox.showinfo("Long Rest", "HP and Mana restored to full. Long-rest uses reset.")

    # ---------------- Sync ----------------

    def refresh_from_model(self):
        c = self.char

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
        self.var_unspent.set(str(res.get("unspent_points", 0)))

        skills = c.get("skills", {})
        self.var_core_current.set(str(skills.get("core", {}).get("current", 0)))
        self.var_core_max.set(str(skills.get("core", {}).get("max", 0)))
        self.var_inner_current.set(str(skills.get("inner", {}).get("current", 0)))
        self.var_inner_max.set(str(skills.get("inner", {}).get("max", 0)))
        self.var_outer_current.set(str(skills.get("outer", {}).get("current", 0)))
        self.var_outer_max.set(str(skills.get("outer", {}).get("max", 0)))

        stats = c.get("stats", {})
        for k in self.var_stats:
            self.var_stats[k].set(str(stats.get(k, 0)))

        growth = c.get("growth_items", {})
        self.var_growth_current.set(str(growth.get("bound_current", 0)))
        self.var_growth_max.set(str(growth.get("bound_max", 0)))

        # Inventory
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
            self.inv_apply_pbd[k].set(True)
            nb: tk.Text = getattr(self, f"inv_notes_box_{k}")
            nb.delete("1.0", tk.END)

        # Abilities
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

        # Talents
        self._refresh_talent_text()
        eff = find_show_must_go_on(c)
        if eff and "uses" in eff:
            uses = eff["uses"]
            self.var_show_used.set(uses.get("used", 0) >= uses.get("max", 1))
        else:
            self.var_show_used.set(False)

        # Notes / world
        self.notes_text.delete("1.0", tk.END)
        self.notes_text.insert(tk.END, self.char.get("notes", ""))

        self.world_text.delete("1.0", tk.END)
        self.world_text.insert(tk.END, self.char.get("world_info", ""))

        # Combat list
        self.refresh_combat_list()
        self.combat_mana_entry.configure(state="disabled")

    def apply_to_model(self):
        c = self.char
        c["name"] = self.var_name.get()
        c["tier"] = self.var_tier.get()

        def to_int(var, default=0):
            try:
                return int(var.get())
            except ValueError:
                return default

        res = c.setdefault("resources", {})
        hp = res.setdefault("hp", {})
        mana = res.setdefault("mana", {})

        hp["current"] = to_int(self.var_hp_current)
        hp["max"] = to_int(self.var_hp_max)
        mana["current"] = to_int(self.var_mana_current)
        mana["max"] = to_int(self.var_mana_max)

        res["pbd"] = to_int(self.var_pbd)
        res["unspent_points"] = to_int(self.var_unspent)

        skills = c.setdefault("skills", {})
        skills.setdefault("core", {})["current"] = to_int(self.var_core_current)
        skills.setdefault("core", {})["max"] = to_int(self.var_core_max)
        skills.setdefault("inner", {})["current"] = to_int(self.var_inner_current)
        skills.setdefault("inner", {})["max"] = to_int(self.var_inner_max)
        skills.setdefault("outer", {})["current"] = to_int(self.var_outer_current)
        skills.setdefault("outer", {})["max"] = to_int(self.var_outer_max)

        stats = c.setdefault("stats", {})
        for k in self.var_stats:
            stats[k] = to_int(self.var_stats[k])

        growth = c.setdefault("growth_items", {})
        growth["bound_current"] = to_int(self.var_growth_current)
        growth["bound_max"] = to_int(self.var_growth_max)

        # Inventory save
        inv = c.setdefault("inventory", {"equipment": [], "bag": [], "storage": []})
        for k in self.inv_keys:
            cleaned = []
            for it in self.inv_data[k]:
                name = (it.get("name") or "").strip()
                if not name:
                    continue
                cleaned.append({
                    "name": name,
                    "favorite": bool(it.get("favorite", False)),
                    "roll_type": it.get("roll_type", "None"),
                    "damage": it.get("damage", ""),
                    "notes": it.get("notes", ""),
                    "apply_pbd": bool(it.get("apply_pbd", True)),
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

        # Notes / world
        c["notes"] = self.notes_text.get("1.0", tk.END).rstrip("\n")
        c["world_info"] = self.world_text.get("1.0", tk.END).rstrip("\n")

    # ---------------- Talents ----------------

    def _refresh_talent_text(self):
        t1 = self.char.get("talents", {}).get("T1")

        self.talent_text.configure(state="normal")
        self.talent_text.delete("1.0", tk.END)

        if not t1 or t1.get("locked"):
            self.talent_text.insert(tk.END, "T1 talent is locked.")
        else:
            lines = []
            lines.append(t1.get("name", "Unnamed Talent"))
            if t1.get("tagline"):
                lines.append(t1["tagline"])
            lines.append("")

            trig = t1.get("trigger", {})
            lines.append(f"Trigger ({trig.get('type','')}): {trig.get('text','')}")
            lines.append("")
            lines.append("Effects:")

            for eff in t1.get("effects", []):
                lines.append(f"  • {eff.get('name','Unnamed')}")
                lines.append(f"    {eff.get('text','')}")
                if eff.get("uses"):
                    u = eff["uses"]
                    lines.append(f"    Uses: {u.get('used',0)}/{u.get('max',1)} per {u.get('per','')}")
                lines.append("")

            if t1.get("mana_flair"):
                mf = t1["mana_flair"]
                lines.append("Mana Flair:")
                lines.append(f"  Cost: {mf.get('cost',0)} mana ({mf.get('timing','')})")
                lines.append(f"  {mf.get('text','')}")
                lines.append(f"  Limit: {mf.get('uses_per_round',1)}/round")

            self.talent_text.insert(tk.END, "\n".join(lines))

        self.talent_text.configure(state="disabled")

    def on_toggle_show_used(self):
        eff = find_show_must_go_on(self.char)
        if not eff:
            return
        uses = eff.setdefault("uses", {"per": "long_rest", "max": 1, "used": 0})
        uses["used"] = uses.get("max", 1) if self.var_show_used.get() else 0
        self._refresh_talent_text()

    # ---------------- Tier 1 spend logic ----------------

    def _get_unspent(self):
        try:
            return int(self.var_unspent.get())
        except ValueError:
            return 0

    def _set_unspent(self, v):
        self.var_unspent.set(str(max(0, v)))

    def spend_points_for_mana_t1(self):
        # unchanged: 1->1 under 50, else 3->2
        unspent = self._get_unspent()
        try:
            cur = int(self.var_mana_current.get())
            mx = int(self.var_mana_max.get())
        except ValueError:
            return

        cost, gain = (1, 1) if mx < 50 else (3, 2)
        if unspent < cost:
            messagebox.showwarning("Not enough points", f"Need {cost} point(s) for Mana at this cap.")
            return

        self._set_unspent(unspent - cost)
        self.var_mana_max.set(str(mx + gain))
        self.var_mana_current.set(str(cur + gain))

    def spend_points_for_hp_t1(self):
        unspent = self._get_unspent()
        if unspent < 1:
            messagebox.showwarning("Not enough points", "You have no unspent points.")
            return

        try:
            cur = int(self.var_hp_current.get())
            mx = int(self.var_hp_max.get())
        except ValueError:
            return

        gain = T1_HP_GAIN_BEFORE_CAP if mx < T1_HP_SOFT_CAP else T1_HP_GAIN_AFTER_CAP
        self._set_unspent(unspent - 1)
        self.var_hp_max.set(str(mx + gain))
        self.var_hp_current.set(str(cur + gain))

    def spend_points_for_pbd_t1(self):
        unspent = self._get_unspent()
        try:
            pbd = int(self.var_pbd.get())
        except ValueError:
            return

        if pbd < T1_PBD_SOFT_CAP:
            cost, gain = (T1_PBD_COST_BEFORE_CAP, T1_PBD_GAIN_BEFORE_CAP)
        else:
            cost, gain = (T1_PBD_COST_AFTER_CAP, T1_PBD_GAIN_AFTER_CAP)

        if unspent < cost:
            messagebox.showwarning("Not enough points", f"Need {cost} point(s) for PBD at this cap.")
            return

        self._set_unspent(unspent - cost)
        self.var_pbd.set(str(pbd + gain))

    def _build_damage_lab_tab(self):
        self.damage_lab = DamageLabTab(
            self.tab_damage_lab,
            get_actions=self._damage_lab_get_actions,
            get_pbd=self._damage_lab_get_pbd,
        )
        self.damage_lab.pack(fill=tk.BOTH, expand=True)

    def _damage_lab_get_actions(self):
        # ensure it's always fresh + sorted
        self.refresh_combat_list()
        return self.combat_actions

    def _damage_lab_get_pbd(self):
        try:
            return int(self.var_pbd.get().strip())
        except ValueError:
            return 0



    # ---------------- Save ----------------

    def on_save(self):
        self.apply_to_model()
        save_character(self.char, self.char_path)
        messagebox.showinfo("Saved", f"Saved to {self.char_path.name}")



if __name__ == "__main__":
    path = pick_character_file()
    if not path:
        sys.exit(0)

    app = CharacterApp(path)
    app.mainloop()
