import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import re
import math

CHAR_PATH = Path("joe.json")

ROLL_TYPES = ["None", "Attack", "Save", "Check"]

ABILITY_MODS = {
    "core":  {"dmg": 1.50, "mana": 0.75},
    "inner": {"dmg": 1.00, "mana": 1.00},
    "outer": {"dmg": 0.75, "mana": 2.00},
}


# ---------------- Combat math helpers ----------------

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

    flat_bonus = 0
    rest = s[m.end():]
    for sign, num in re.findall(r'([+-])(\d+)', rest):
        flat_bonus += int(num) if sign == '+' else -int(num)

    return dice_count, die_size, flat_bonus


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def max_pbd_factor_for_die(die_size: int) -> float:
    """
    Piecewise linear mapping:
      d4  -> 0.50
      d10 -> 1.00
      d20 -> 2.111... (so 18/20 => 1.9x)

    For other dice, interpolate between anchors.
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


# ---------------- Persistence helpers ----------------

def load_character(path=CHAR_PATH):
    if not path.exists():
        messagebox.showerror("Error", f"Character file not found: {path}")
        raise SystemExit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_character(char, path=CHAR_PATH):
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
    if isinstance(x, str):
        return {"name": x, "favorite": False, "roll_type": "None", "damage": "", "notes": ""}
    if isinstance(x, dict):
        return {
            "name": x.get("name", ""),
            "favorite": bool(x.get("favorite", False)),
            "roll_type": x.get("roll_type", "None"),
            "damage": x.get("damage", ""),
            "notes": x.get("notes", ""),
        }
    return {"name": "", "favorite": False, "roll_type": "None", "damage": "", "notes": ""}


def ensure_ability_obj(x):
    if isinstance(x, str):
        return {"name": x, "favorite": False, "roll_type": "None", "damage": "", "mana_cost": 0, "notes": ""}
    if isinstance(x, dict):
        return {
            "name": x.get("name", ""),
            "favorite": bool(x.get("favorite", False)),
            "roll_type": x.get("roll_type", "None"),
            "damage": x.get("damage", ""),
            "mana_cost": int(x.get("mana_cost", 0) or 0),
            "notes": x.get("notes", ""),
        }
    return {"name": "", "favorite": False, "roll_type": "None", "damage": "", "mana_cost": 0, "notes": ""}


# ---------------- App ----------------

class CharacterApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Homebrew Character Sheet")
        self.geometry("1150x750")

        self.char = load_character()

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

        self.var_stats = {k: tk.StringVar() for k in ["str", "dex", "con", "int", "wis", "cha", "san", "hnr"]}

        self.var_growth_current = tk.StringVar()
        self.var_growth_max = tk.StringVar()

        self.var_show_used = tk.BooleanVar()

        # Inventory internal data
        self.inv_keys = ["equipment", "bag", "storage"]
        self.inv_data = {k: [] for k in self.inv_keys}
        self.inv_selected_obj = {k: None for k in self.inv_keys}
        self.inv_new_name = {k: tk.StringVar() for k in self.inv_keys}
        self.inv_roll_type = {k: tk.StringVar(value="None") for k in self.inv_keys}
        self.inv_damage = {k: tk.StringVar() for k in self.inv_keys}

        # Abilities
        self.ability_keys = ["core", "inner", "outer"]
        self.abilities_data = {k: [] for k in self.ability_keys}
        self.ability_selected_obj = {k: None for k in self.ability_keys}
        self.var_new_ability_name = {k: tk.StringVar() for k in self.ability_keys}
        self.ability_roll_type = {k: tk.StringVar(value="None") for k in self.ability_keys}
        self.ability_damage = {k: tk.StringVar() for k in self.ability_keys}
        self.ability_mana_cost = {k: tk.StringVar(value="0") for k in self.ability_keys}

        # Combat (Overview quick use)
        self.combat_actions = []  # list of dicts {kind, ref, slot?, display, favorite, name}
        self.combat_selected = None
        self.var_combat_roll_type = tk.StringVar(value="")
        self.var_combat_damage_expr = tk.StringVar(value="")
        self.var_combat_slot = tk.StringVar(value="")
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

        self.tabs.add(self.tab_overview, text="Overview")
        self.tabs.add(self.tab_talents, text="Talents")
        self.tabs.add(self.tab_inventory, text="Inventory")
        self.tabs.add(self.tab_abilities, text="Abilities")
        self.tabs.add(self.tab_notes, text="Notes")
        self.tabs.add(self.tab_world, text="World Info")

        self._build_overview_tab()
        self._build_talents_tab()
        self._build_inventory_tab()
        self._build_abilities_tab()
        self._build_notes_tab()
        self._build_world_tab()

    def _build_overview_tab(self):
        left = ttk.Frame(self.tab_overview)
        right = ttk.Frame(self.tab_overview)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=8)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)

        # Stats
        stats_frame = ttk.LabelFrame(left, text="Stats")
        stats_frame.pack(fill=tk.X, pady=6)

        for row, key in enumerate(["str", "dex", "con", "int", "wis", "cha", "san", "hnr"]):
            ttk.Label(stats_frame, text=key.upper() + ":").grid(row=row, column=0, sticky="w", padx=4, pady=2)
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
        combat = ttk.LabelFrame(right, text="Combat Quick Use (select equipment/ability)")
        combat.pack(fill=tk.BOTH, expand=True, pady=6)

        c_outer = ttk.Frame(combat)
        c_outer.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        c_left = ttk.Frame(c_outer)
        c_right = ttk.Frame(c_outer)
        c_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        c_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.combat_list = tk.Listbox(c_left, height=14, exportselection=False)
        self.combat_list.pack(fill=tk.BOTH, expand=True)
        self.combat_list.bind("<<ListboxSelect>>", lambda _e: self.on_combat_select())

        ttk.Button(c_left, text="Refresh list", command=self.refresh_combat_list).pack(fill=tk.X, pady=(6, 0))

        ttk.Label(c_right, text="Type/slot:").grid(row=0, column=0, sticky="w", padx=4, pady=(4, 2))
        ttk.Label(c_right, textvariable=self.var_combat_slot).grid(row=0, column=1, sticky="w", padx=4, pady=(4, 2))

        ttk.Label(c_right, text="Roll type:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(c_right, textvariable=self.var_combat_roll_type).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(c_right, text="Damage dice (what to roll):").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(c_right, textvariable=self.var_combat_damage_expr).grid(row=2, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(c_right, text="Enter rolled damage:").grid(row=3, column=0, sticky="w", padx=4, pady=(10, 2))
        ttk.Entry(c_right, textvariable=self.var_combat_roll_value, width=10).grid(row=3, column=1, sticky="w", padx=4, pady=(10, 2))

        ttk.Label(c_right, text="Mana to spend (abilities):").grid(row=4, column=0, sticky="w", padx=4, pady=2)
        self.combat_mana_entry = ttk.Entry(c_right, textvariable=self.var_combat_mana_spend, width=10)
        self.combat_mana_entry.grid(row=4, column=1, sticky="w", padx=4, pady=2)

        ttk.Button(c_right, text="Use / Cast", command=self.use_combat_action).grid(
            row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=(12, 6)
        )

        ttk.Label(c_right, textvariable=self.var_combat_result, foreground="gray").grid(
            row=6, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 2)
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

        lb = tk.Listbox(left, height=18, exportselection=False)
        lb.pack(fill=tk.BOTH, expand=True)
        lb.bind("<Double-Button-1>", lambda _e, k=key: self.inv_toggle_favorite(k))
        lb.bind("<<ListboxSelect>>", lambda _e, k=key: self.inv_on_select(k))

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

        ttk.Label(details, text="Damage dice (ex: 1d10+2):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.inv_damage[key], width=28).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Notes:").grid(row=2, column=0, sticky="nw", padx=6, pady=4)
        notes_box = tk.Text(details, wrap="word", height=10)
        notes_box.grid(row=2, column=1, sticky="nsew", padx=6, pady=4)
        setattr(self, f"inv_notes_box_{key}", notes_box)

        ttk.Button(details, text="Update Selected", command=lambda k=key: self.inv_update_selected(k)).grid(
            row=3, column=1, sticky="w", padx=6, pady=(6, 8)
        )

        details.grid_columnconfigure(1, weight=1)
        details.grid_rowconfigure(2, weight=1)

        setattr(self, f"inv_list_{key}", lb)

    def inv_render(self, key: str):
        selected = self.inv_selected_obj.get(key)
        self.inv_data[key] = sort_favorites_first(self.inv_data[key])

        lb: tk.Listbox = getattr(self, f"inv_list_{key}")
        lb.delete(0, tk.END)
        for it in self.inv_data[key]:
            star = "⭐ " if it.get("favorite", False) else ""
            lb.insert(tk.END, f"{star}{it.get('name','')}")

        # restore selection
        if selected in self.inv_data[key]:
            idx = self.inv_data[key].index(selected)
            lb.selection_set(idx)
            lb.activate(idx)

        self.refresh_combat_list()

    def inv_add(self, key: str):
        name = self.inv_new_name[key].get().strip()
        if not name:
            return
        it = {"name": name, "favorite": False, "roll_type": "None", "damage": "", "notes": ""}
        self.inv_data[key].append(it)
        self.inv_new_name[key].set("")
        self.inv_selected_obj[key] = it
        self.inv_render(key)
        self.inv_on_select(key)

    def inv_remove(self, key: str):
        lb: tk.Listbox = getattr(self, f"inv_list_{key}")
        sel = list(lb.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            if 0 <= idx < len(self.inv_data[key]):
                removed = self.inv_data[key].pop(idx)
                if self.inv_selected_obj.get(key) is removed:
                    self.inv_selected_obj[key] = None
        self.inv_render(key)

    def inv_toggle_favorite(self, key: str):
        lb: tk.Listbox = getattr(self, f"inv_list_{key}")
        sel = list(lb.curselection())
        if len(sel) != 1:
            return
        idx = sel[0]
        if 0 <= idx < len(self.inv_data[key]):
            self.inv_data[key][idx]["favorite"] = not bool(self.inv_data[key][idx].get("favorite", False))
            self.inv_selected_obj[key] = self.inv_data[key][idx]
        self.inv_render(key)
        self.inv_on_select(key)

    def inv_on_select(self, key: str):
        lb: tk.Listbox = getattr(self, f"inv_list_{key}")
        sel = list(lb.curselection())
        if len(sel) != 1:
            return
        idx = sel[0]
        if not (0 <= idx < len(self.inv_data[key])):
            return

        it = self.inv_data[key][idx]
        self.inv_selected_obj[key] = it

        self.inv_roll_type[key].set(it.get("roll_type", "None"))
        self.inv_damage[key].set(it.get("damage", ""))

        notes_box: tk.Text = getattr(self, f"inv_notes_box_{key}")
        notes_box.delete("1.0", tk.END)
        notes_box.insert(tk.END, it.get("notes", ""))

    def inv_update_selected(self, key: str):
        it = self.inv_selected_obj.get(key)
        if it is None:
            messagebox.showinfo("Update", "Select an item first.")
            return

        it["roll_type"] = self.inv_roll_type[key].get() or "None"
        it["damage"] = self.inv_damage[key].get().strip()

        notes_box: tk.Text = getattr(self, f"inv_notes_box_{key}")
        it["notes"] = notes_box.get("1.0", tk.END).rstrip("\n")

        self.inv_render(key)
        self.inv_on_select(key)

    # ---------------- Abilities ----------------

    def _build_abilities_tab(self):
        frame = ttk.Frame(self.tab_abilities)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        info = ttk.LabelFrame(frame, text="Slot Multipliers")
        info.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(info, text="Core: 150% damage, 75% mana    |    Inner: 100% damage, 100% mana    |    Outer: 75% damage, 200% mana").pack(
            anchor="w", padx=8, pady=6
        )

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

        controls = ttk.Frame(left)
        controls.pack(fill=tk.X, pady=(8, 0))

        ttk.Entry(controls, textvariable=self.var_new_ability_name[key]).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(controls, text="Add", command=lambda k=key: self.ability_add(k)).pack(side=tk.LEFT, padx=6)
        ttk.Button(controls, text="Remove", command=lambda k=key: self.ability_remove(k)).pack(side=tk.LEFT)
        ttk.Button(controls, text="Toggle ⭐", command=lambda k=key: self.ability_toggle_favorite(k)).pack(side=tk.LEFT, padx=6)

        details = ttk.LabelFrame(right, text=f"Selected Ability ({key.upper()} slot)")
        details.pack(fill=tk.BOTH, expand=True)

        ttk.Label(details, text="Roll type:").grid(row=0, column=0, sticky="w", padx=6, pady=(8, 4))
        ttk.Combobox(details, values=ROLL_TYPES, textvariable=self.ability_roll_type[key], state="readonly", width=18).grid(
            row=0, column=1, sticky="w", padx=6, pady=(8, 4)
        )

        ttk.Label(details, text="Damage dice (ex: 2d6+3):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.ability_damage[key], width=28).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Mana cost (base):").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.ability_mana_cost[key], width=10).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Notes:").grid(row=3, column=0, sticky="nw", padx=6, pady=4)
        notes_box = tk.Text(details, wrap="word", height=10)
        notes_box.grid(row=3, column=1, sticky="nsew", padx=6, pady=4)
        setattr(self, f"ability_notes_box_{key}", notes_box)

        ttk.Button(details, text="Update Selected", command=lambda k=key: self.ability_update_selected(k)).grid(
            row=4, column=1, sticky="w", padx=6, pady=(6, 8)
        )

        details.grid_columnconfigure(1, weight=1)
        details.grid_rowconfigure(3, weight=1)

        setattr(self, f"ability_list_{key}", lb)

    def ability_render(self, key: str):
        selected = self.ability_selected_obj.get(key)
        self.abilities_data[key] = sort_favorites_first(self.abilities_data[key])

        lb: tk.Listbox = getattr(self, f"ability_list_{key}")
        lb.delete(0, tk.END)
        for ab in self.abilities_data[key]:
            star = "⭐ " if ab.get("favorite", False) else ""
            lb.insert(tk.END, f"{star}{ab.get('name','')}")

        if selected in self.abilities_data[key]:
            idx = self.abilities_data[key].index(selected)
            lb.selection_set(idx)
            lb.activate(idx)

        self.refresh_combat_list()

    def ability_add(self, key: str):
        name = self.var_new_ability_name[key].get().strip()
        if not name:
            return
        ab = {"name": name, "favorite": False, "roll_type": "None", "damage": "", "mana_cost": 0, "notes": ""}
        self.abilities_data[key].append(ab)
        self.var_new_ability_name[key].set("")
        self.ability_selected_obj[key] = ab
        self.ability_render(key)
        self.ability_on_select(key)

    def ability_remove(self, key: str):
        lb: tk.Listbox = getattr(self, f"ability_list_{key}")
        sel = list(lb.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            if 0 <= idx < len(self.abilities_data[key]):
                removed = self.abilities_data[key].pop(idx)
                if self.ability_selected_obj.get(key) is removed:
                    self.ability_selected_obj[key] = None
        self.ability_render(key)

    def ability_toggle_favorite(self, key: str):
        lb: tk.Listbox = getattr(self, f"ability_list_{key}")
        sel = list(lb.curselection())
        if len(sel) != 1:
            return
        idx = sel[0]
        if 0 <= idx < len(self.abilities_data[key]):
            self.abilities_data[key][idx]["favorite"] = not bool(self.abilities_data[key][idx].get("favorite", False))
            self.ability_selected_obj[key] = self.abilities_data[key][idx]
        self.ability_render(key)
        self.ability_on_select(key)

    def ability_on_select(self, key: str):
        lb: tk.Listbox = getattr(self, f"ability_list_{key}")
        sel = list(lb.curselection())
        if len(sel) != 1:
            return
        idx = sel[0]
        if not (0 <= idx < len(self.abilities_data[key])):
            return

        ab = self.abilities_data[key][idx]
        self.ability_selected_obj[key] = ab

        self.ability_roll_type[key].set(ab.get("roll_type", "None"))
        self.ability_damage[key].set(ab.get("damage", ""))
        self.ability_mana_cost[key].set(str(ab.get("mana_cost", 0)))

        notes_box: tk.Text = getattr(self, f"ability_notes_box_{key}")
        notes_box.delete("1.0", tk.END)
        notes_box.insert(tk.END, ab.get("notes", ""))

    def ability_update_selected(self, key: str):
        ab = self.ability_selected_obj.get(key)
        if ab is None:
            messagebox.showinfo("Update", "Select an ability first.")
            return

        ab["roll_type"] = self.ability_roll_type[key].get() or "None"
        ab["damage"] = self.ability_damage[key].get().strip()

        try:
            ab["mana_cost"] = int(self.ability_mana_cost[key].get().strip() or "0")
        except ValueError:
            ab["mana_cost"] = 0

        notes_box: tk.Text = getattr(self, f"ability_notes_box_{key}")
        ab["notes"] = notes_box.get("1.0", tk.END).rstrip("\n")

        self.ability_render(key)
        self.ability_on_select(key)

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
        actions = []

        # Equipment only gets PBD
        for it in self.inv_data.get("equipment", []):
            actions.append({
                "kind": "item",
                "ref": it,
                "slot": "equipment",
                "favorite": bool(it.get("favorite", False)),
                "name": it.get("name", ""),
                "display": f"{'⭐ ' if it.get('favorite', False) else ''}{it.get('name','')}  (Equipment)",
            })

        # Abilities (core/inner/outer) — NO PBD
        for slot in ["core", "inner", "outer"]:
            for ab in self.abilities_data.get(slot, []):
                actions.append({
                    "kind": "ability",
                    "ref": ab,
                    "slot": slot,
                    "favorite": bool(ab.get("favorite", False)),
                    "name": ab.get("name", ""),
                    "display": f"{'⭐ ' if ab.get('favorite', False) else ''}{ab.get('name','')}  ({slot.title()} Ability)",
                })

        actions = sorted(actions, key=lambda a: (not a["favorite"], a["name"].lower(), a["kind"], a.get("slot", "")))
        self.combat_actions = actions

        self.combat_list.delete(0, tk.END)
        for a in actions:
            self.combat_list.insert(tk.END, a["display"])

    def on_combat_select(self):
        sel = list(self.combat_list.curselection())
        if len(sel) != 1:
            self.combat_selected = None
            return
        idx = sel[0]
        if not (0 <= idx < len(self.combat_actions)):
            self.combat_selected = None
            return

        self.combat_selected = idx
        a = self.combat_actions[idx]
        ref = a["ref"]

        self.var_combat_slot.set(a["display"].split("  (", 1)[-1].rstrip(")"))
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
        if self.combat_selected is None or not (0 <= self.combat_selected < len(self.combat_actions)):
            messagebox.showinfo("Combat", "Select equipment or an ability first.")
            return

        a = self.combat_actions[self.combat_selected]
        ref = a["ref"]

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

        # ---- Equipment: apply PBD scaling ----
        if a["kind"] == "item":
            try:
                pbd = int(self.var_pbd.get().strip())
            except ValueError:
                pbd = 0

            max_roll = max(1, dice_count * die_size)
            pct = clamp(rolled / max_roll, 0.0, 1.0)
            max_factor = max_pbd_factor_for_die(die_size)

            pbd_add = int(pbd * pct * max_factor)  # floor nerf
            total = rolled + flat_bonus + pbd_add

            pct_display = int(round(pct * 100))
            self.var_combat_result.set(
                f"Equipment: Rolled {rolled} ({pct_display}% of max {max_roll}) + flat {flat_bonus} "
                f"+ PBD add {pbd_add}  →  Total {total}"
            )
            return

        # ---- Ability: NO PBD, apply slot multipliers ----
        slot = a.get("slot", "inner")
        mods = ABILITY_MODS.get(slot, {"dmg": 1.0, "mana": 1.0})
        dmg_mult = mods["dmg"]
        mana_mult = mods["mana"]

        base = rolled + flat_bonus
        total = int(math.floor(base * dmg_mult))

        # mana spend (effective)
        try:
            spend_base = int((self.var_combat_mana_spend.get().strip() or str(ref.get("mana_cost", 0))).strip())
        except ValueError:
            spend_base = int(ref.get("mana_cost", 0) or 0)

        spend_eff = int(math.ceil(spend_base * mana_mult))

        try:
            cur_mana = int(self.var_mana_current.get())
        except ValueError:
            cur_mana = 0

        if spend_eff > cur_mana:
            messagebox.showwarning("Combat", f"Not enough mana. You have {cur_mana}, need {spend_eff} (slot-adjusted).")
            return

        self.var_mana_current.set(str(cur_mana - spend_eff))
        self.var_combat_result.set(
            f"{slot.title()} ability: (rolled {rolled} + flat {flat_bonus})={base} * {dmg_mult:.2f} → {total} damage. "
            f"Mana: base {spend_base} * {mana_mult:.2f} → {spend_eff} spent."
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
        for _, tier in talents.items():
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

        # Inventory migration/load
        inv = c.get("inventory")
        if not isinstance(inv, dict):
            inv = {"equipment": [], "bag": [], "storage": []}
            old_items = c.get("items", [])
            if isinstance(old_items, list):
                inv["bag"] = [ensure_item_obj(x) for x in old_items]
            c["inventory"] = inv

        for k in self.inv_keys:
            raw = inv.get(k, [])
            self.inv_data[k] = sort_favorites_first([ensure_item_obj(x) for x in (raw if isinstance(raw, list) else [])])
            self.inv_selected_obj[k] = None
            self.inv_render(k)

            self.inv_roll_type[k].set("None")
            self.inv_damage[k].set("")
            nb: tk.Text = getattr(self, f"inv_notes_box_{k}")
            nb.delete("1.0", tk.END)

        # Abilities migration/load (also migrates old "spells" into inner by default)
        abilities = c.get("abilities")
        if not isinstance(abilities, dict):
            abilities = {"core": [], "inner": [], "outer": []}

            old_spells = c.get("spells", [])
            if isinstance(old_spells, list) and old_spells:
                abilities["inner"] = [ensure_ability_obj(x) for x in old_spells]

            c["abilities"] = abilities

        for slot in self.ability_keys:
            raw = abilities.get(slot, [])
            self.abilities_data[slot] = sort_favorites_first([ensure_ability_obj(x) for x in (raw if isinstance(raw, list) else [])])
            self.ability_selected_obj[slot] = None
            self.ability_render(slot)

            self.ability_roll_type[slot].set("None")
            self.ability_damage[slot].set("")
            self.ability_mana_cost[slot].set("0")
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
                })
            inv[k] = cleaned

        # Abilities save
        abilities = c.setdefault("abilities", {"core": [], "inner": [], "outer": []})
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
                    "notes": ab.get("notes", ""),
                })
            abilities[slot] = cleaned

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
            lines.append(f"Trigger ({trig.get('type', '')}): {trig.get('text', '')}")
            lines.append("")
            lines.append("Effects:")

            for eff in t1.get("effects", []):
                lines.append(f"  • {eff.get('name', 'Unnamed')}")
                lines.append(f"    {eff.get('text', '')}")
                if eff.get("uses"):
                    u = eff["uses"]
                    lines.append(f"    Uses: {u.get('used', 0)}/{u.get('max', 1)} per {u.get('per', '')}")
                lines.append("")

            if t1.get("mana_flair"):
                mf = t1["mana_flair"]
                lines.append("Mana Flair:")
                lines.append(f"  Cost: {mf.get('cost', 0)} mana ({mf.get('timing', '')})")
                lines.append(f"  {mf.get('text', '')}")
                lines.append(f"  Limit: {mf.get('uses_per_round', 1)}/round")

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
        unspent = self._get_unspent()
        try:
            cur = int(self.var_mana_current.get())
            mx = int(self.var_mana_max.get())
        except ValueError:
            return

        # unchanged
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

        # NEW: soft cap 100, +2 before 100, +1 after
        gain = 2 if mx < 100 else 1

        self._set_unspent(unspent - 1)
        self.var_hp_max.set(str(mx + gain))
        self.var_hp_current.set(str(cur + gain))

    def spend_points_for_pbd_t1(self):
        unspent = self._get_unspent()
        try:
            pbd = int(self.var_pbd.get())
        except ValueError:
            return

        # NEW: 3 points -> +1 PBD, soft cap 15 (after: 6 -> +1)
        cost = 3 if pbd < 15 else 6
        gain = 1

        if unspent < cost:
            messagebox.showwarning("Not enough points", f"Need {cost} point(s) for PBD at this cap.")
            return

        self._set_unspent(unspent - cost)
        self.var_pbd.set(str(pbd + gain))

    # ---------------- Save ----------------

    def on_save(self):
        self.apply_to_model()
        save_character(self.char)
        messagebox.showinfo("Saved", f"Saved to {CHAR_PATH.name}")


if __name__ == "__main__":
    app = CharacterApp()
    app.mainloop()
