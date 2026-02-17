# battle_sim.py
import math
import re
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# --------------- Mechanics (duplicated from sheet_tool / damage_lab) ---------------

ABILITY_MODS = {
    "core":  {"dmg": 1.50, "mana": 0.75},
    "inner": {"dmg": 1.00, "mana": 1.00},
    "outer": {"dmg": 0.75, "mana": 2.00},
}

STAT_ORDER = [
    ("melee_acc",  "Melee Acc"),
    ("ranged_acc", "Ranged Acc"),
    ("spellcraft", "Spellcraft"),
    ("pbd",        "PBD"),
    ("precision",  "Precision"),
    ("phys_def",   "Defense"),
    ("evasion",    "Evasion"),
    ("wis_def",    "Wisdom"),
    ("utility",    "Utility"),
    ("agility",    "Agility"),
    ("strength",   "Strength"),
]
STAT_KEYS = [k for k, _ in STAT_ORDER]

# Combat-relevant stats shown in the character panels
COMBAT_STATS = [
    ("melee_acc",  "Melee Acc"),
    ("ranged_acc", "Ranged Acc"),
    ("spellcraft", "Spellcraft"),
    ("pbd",        "PBD"),
    ("precision",  "Precision"),
    ("phys_def",   "Defense"),
    ("evasion",    "Evasion"),
    ("wis_def",    "Wisdom"),
]


def parse_damage_expr(expr: str):
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


def mana_density_multiplier(points: int) -> float:
    try:
        p = int(points)
    except Exception:
        p = 0
    p = max(0, p)
    if p <= 100:
        return 1.0 + (p / 100.0)
    return 2.0 + (math.log(p / 100.0) / math.log(100.0))


def hit_roll_multiplier(d20_roll: int) -> float:
    anchors = [(1, 0.05), (2, 0.20), (10, 1.00), (19, 2.00), (20, 5.00)]
    try:
        r = int(d20_roll)
    except Exception:
        r = 1
    r = max(1, min(20, r))
    if r <= anchors[0][0]:
        return anchors[0][1]
    if r >= anchors[-1][0]:
        return anchors[-1][1]
    for (r0, m0), (r1, m1) in zip(anchors, anchors[1:]):
        if r0 <= r <= r1:
            t = (r - r0) / (r1 - r0)
            return m0 + t * (m1 - m0)
    return 1.0


def evasion_damage_multiplier(effective_accuracy: float, evasion: float) -> float:
    if evasion <= 0:
        return 1.0
    ratio = effective_accuracy / evasion
    anchors = [(0.90, 0.0), (0.95, 0.25), (1.00, 0.50), (1.05, 0.75), (1.10, 1.0)]
    if ratio <= anchors[0][0]:
        return anchors[0][1]
    if ratio >= anchors[-1][0]:
        return anchors[-1][1]
    for (r0, m0), (r1, m1) in zip(anchors, anchors[1:]):
        if r0 <= ratio <= r1:
            t = (ratio - r0) / (r1 - r0)
            return m0 + t * (m1 - m0)
    return 1.0


def phys_dr_from_points(phys_def_points: int) -> int:
    try:
        p = int(phys_def_points)
    except Exception:
        p = 0
    return max(0, p // 5)


def compute_overcast_bonus(base_cost_eff: int, spent_eff: int, over: dict) -> int:
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
    x = math.log(ratio, 2.0)
    bonus = int(math.floor(scale * (x ** power)))
    if cap >= 0:
        bonus = min(bonus, cap)
    return max(0, bonus)


def _migrate_stats(char: dict):
    """Ensure character dict has all expected stat keys."""
    stats = char.get("stats")
    if not isinstance(stats, dict):
        char["stats"] = {k: 0 for k in STAT_KEYS}
        stats = char["stats"]
    for k in STAT_KEYS:
        if k not in stats:
            stats[k] = 0
        try:
            stats[k] = int(stats[k] or 0)
        except Exception:
            stats[k] = 0
    # Migrate PBD from resources if needed
    res = char.get("resources", {})
    if isinstance(res, dict) and "pbd" in res:
        try:
            old_pbd = int(res.get("pbd", 0) or 0)
        except Exception:
            old_pbd = 0
        if old_pbd > 0 and stats.get("pbd", 0) == 0:
            stats["pbd"] = old_pbd


def _ensure_item(x):
    if isinstance(x, str):
        return {"name": x, "favorite": False, "roll_type": "None",
                "damage": "", "notes": "", "apply_bonus": True, "is_ranged": False}
    if isinstance(x, dict):
        return {
            "name": x.get("name", ""),
            "favorite": bool(x.get("favorite", False)),
            "roll_type": x.get("roll_type", "None"),
            "damage": x.get("damage", ""),
            "notes": x.get("notes", ""),
            "apply_bonus": bool(x.get("apply_bonus", x.get("apply_pbd", True))),
            "is_ranged": bool(x.get("is_ranged", False)),
        }
    return {"name": "", "favorite": False, "roll_type": "None",
            "damage": "", "notes": "", "apply_bonus": True, "is_ranged": False}


def _ensure_ability(x):
    if isinstance(x, str):
        return {"name": x, "favorite": False, "roll_type": "None",
                "damage": "", "mana_cost": 0, "notes": "",
                "overcast": {"enabled": False, "scale": 0, "power": 0.85, "cap": 999}}
    if isinstance(x, dict):
        over = x.get("overcast", {})
        if not isinstance(over, dict):
            over = {}
        return {
            "name": x.get("name", ""),
            "favorite": bool(x.get("favorite", False)),
            "roll_type": x.get("roll_type", "None"),
            "damage": x.get("damage", ""),
            "mana_cost": int(x.get("mana_cost", 0) or 0),
            "notes": x.get("notes", ""),
            "overcast": {
                "enabled": bool(over.get("enabled", False)),
                "scale": int(over.get("scale", 0) or 0),
                "power": float(over.get("power", 0.85) or 0.85),
                "cap": int(over.get("cap", 999) or 999),
            },
        }
    return {"name": "", "favorite": False, "roll_type": "None",
            "damage": "", "mana_cost": 0, "notes": "",
            "overcast": {"enabled": False, "scale": 0, "power": 0.85, "cap": 999}}


# --------------- Sim character builder ---------------

def build_sim_character(char_dict: dict) -> dict:
    """Extract a lightweight sim-friendly character dict from a full character JSON."""
    _migrate_stats(char_dict)
    stats = char_dict.get("stats", {})
    res = char_dict.get("resources", {})
    hp = res.get("hp", {})
    mana = res.get("mana", {})

    # Build actions list
    actions = []
    inv = char_dict.get("inventory", {})
    for it in inv.get("equipment", []):
        it = _ensure_item(it)
        if not it.get("name"):
            continue
        rng = "Ranged" if it.get("is_ranged", False) else "Melee"
        actions.append({
            "kind": "item", "slot": None, "ref": it,
            "name": it["name"],
            "display": f"{it['name']}  (Item:{rng})",
        })
    for slot in ["core", "inner", "outer"]:
        for ab in char_dict.get("abilities", {}).get(slot, []):
            ab = _ensure_ability(ab)
            if not ab.get("name"):
                continue
            actions.append({
                "kind": "ability", "slot": slot, "ref": ab,
                "name": ab["name"],
                "display": f"{ab['name']}  (Ability:{slot})",
            })

    return {
        "name": char_dict.get("name", "Unknown"),
        "stats": {k: int(stats.get(k, 0) or 0) for k in STAT_KEYS},
        "hp_max": int(hp.get("max", 20) or 20),
        "hp_current": int(hp.get("current", hp.get("max", 20)) or 20),
        "mana_max": int(mana.get("max", 10) or 10),
        "mana_current": int(mana.get("current", mana.get("max", 10)) or 10),
        "mana_density": int(res.get("mana_density", 0) or 0),
        "actions": actions,
    }


# --------------- UI ---------------

class BattleSimTab(ttk.Frame):
    """Two-character combat simulator tab."""

    def __init__(self, parent, get_char_a_data, get_char_a_actions):
        super().__init__(parent)
        self.get_char_a_data = get_char_a_data
        self.get_char_a_actions = get_char_a_actions

        self.char_a = None  # sim dict
        self.char_b = None  # sim dict

        self._colors = None
        self._tk_widgets = []  # raw tk widgets for theme

        # UI vars
        self.var_attacker = tk.StringVar(value="A")
        self.var_d20 = tk.StringVar()
        self.var_damage_roll = tk.StringVar()
        self.var_mana_spend = tk.StringVar()
        self.var_status = tk.StringVar(value="Load both characters to begin.")

        self._build_ui()

    # ---- Build UI ----

    def _build_ui(self):
        outer = ttk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top: load controls
        load_frame = ttk.Frame(outer)
        load_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(load_frame, text="Refresh Character A (this sheet)",
                   command=self._refresh_char_a).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(load_frame, text="Load Character B from file...",
                   command=self._load_char_b).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(load_frame, text="Reset All HP/Mana",
                   command=self._reset_sim).pack(side=tk.RIGHT)

        # Middle: two character panels side by side
        panels = ttk.Frame(outer)
        panels.pack(fill=tk.BOTH, expand=True)
        panels.columnconfigure(0, weight=1)
        panels.columnconfigure(1, weight=0)
        panels.columnconfigure(2, weight=1)

        self.panel_a = self._build_char_panel(panels, "Character A")
        self.panel_a.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        sep = ttk.Separator(panels, orient=tk.VERTICAL)
        sep.grid(row=0, column=1, sticky="ns", padx=4)

        self.panel_b = self._build_char_panel(panels, "Character B")
        self.panel_b.grid(row=0, column=2, sticky="nsew", padx=(4, 0))

        # Action bar
        action_frame = ttk.LabelFrame(outer, text="Combat Action")
        action_frame.pack(fill=tk.X, pady=(8, 4))

        row0 = ttk.Frame(action_frame)
        row0.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Label(row0, text="Attacker:").pack(side=tk.LEFT, padx=(0, 4))
        self.attacker_combo = ttk.Combobox(row0, textvariable=self.var_attacker,
                                           values=["A", "B"], state="readonly", width=4)
        self.attacker_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.var_attacker.trace_add("write", lambda *_: self._on_attacker_changed())

        ttk.Label(row0, text="Action:").pack(side=tk.LEFT, padx=(0, 4))
        self.action_list = tk.Listbox(row0, height=4, width=40, exportselection=False)
        self.action_list.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self._tk_widgets.append(self.action_list)

        row1 = ttk.Frame(action_frame)
        row1.pack(fill=tk.X, padx=8, pady=(0, 4))

        ttk.Label(row1, text="d20 Roll:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(row1, textvariable=self.var_d20, width=6).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(row1, text="Damage Roll:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(row1, textvariable=self.var_damage_roll, width=8).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(row1, text="Mana Spend:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(row1, textvariable=self.var_mana_spend, width=8).pack(side=tk.LEFT, padx=(0, 12))

        row2 = ttk.Frame(action_frame)
        row2.pack(fill=tk.X, padx=8, pady=(0, 8))

        ttk.Button(row2, text="Attack!", command=self._do_attack).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row2, text="Check Accuracy", command=self._do_check_accuracy).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(row2, textvariable=self.var_status, foreground="gray").pack(side=tk.LEFT, padx=(8, 0))

        # Combat log
        log_frame = ttk.LabelFrame(outer, text="Combat Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD, state=tk.DISABLED,
                                font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._tk_widgets.append(self.log_text)

        log_scroll = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scroll.set)

    def _build_char_panel(self, parent, title) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text=title)

        # Name
        name_var = tk.StringVar(value="(not loaded)")
        ttk.Label(frame, textvariable=name_var, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 4))

        # HP bar
        hp_label = tk.StringVar(value="HP: --/--")
        ttk.Label(frame, textvariable=hp_label).grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=2)
        hp_bar = ttk.Progressbar(frame, length=150, mode="determinate")
        hp_bar.grid(row=1, column=2, columnspan=2, sticky="ew", padx=8, pady=2)

        # Mana bar
        mana_label = tk.StringVar(value="Mana: --/--")
        ttk.Label(frame, textvariable=mana_label).grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=2)
        mana_bar = ttk.Progressbar(frame, length=150, mode="determinate")
        mana_bar.grid(row=2, column=2, columnspan=2, sticky="ew", padx=8, pady=2)

        # Mana Density
        md_label = tk.StringVar(value="Mana Density: --")
        ttk.Label(frame, textvariable=md_label).grid(row=3, column=0, columnspan=4, sticky="w", padx=8, pady=2)

        # Stats (2 columns of key-value pairs)
        stats_frame = ttk.Frame(frame)
        stats_frame.grid(row=4, column=0, columnspan=4, sticky="ew", padx=8, pady=(4, 8))
        stat_vars = {}
        for i, (key, label) in enumerate(COMBAT_STATS):
            col = (i // 4) * 2
            row = i % 4
            sv = tk.StringVar(value="--")
            ttk.Label(stats_frame, text=f"{label}:").grid(row=row, column=col, sticky="w", padx=(0, 4), pady=1)
            ttk.Label(stats_frame, textvariable=sv, width=6).grid(row=row, column=col + 1, sticky="w", padx=(0, 12), pady=1)
            stat_vars[key] = sv

        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        # Store refs
        frame._name_var = name_var
        frame._hp_label = hp_label
        frame._hp_bar = hp_bar
        frame._mana_label = mana_label
        frame._mana_bar = mana_bar
        frame._md_label = md_label
        frame._stat_vars = stat_vars

        return frame

    def _update_panel(self, panel, char):
        if char is None:
            panel._name_var.set("(not loaded)")
            panel._hp_label.set("HP: --/--")
            panel._hp_bar["value"] = 0
            panel._mana_label.set("Mana: --/--")
            panel._mana_bar["value"] = 0
            panel._md_label.set("Mana Density: --")
            for sv in panel._stat_vars.values():
                sv.set("--")
            return

        panel._name_var.set(char["name"])

        hp_c, hp_m = char["hp_current"], char["hp_max"]
        panel._hp_label.set(f"HP: {hp_c}/{hp_m}")
        panel._hp_bar["maximum"] = max(1, hp_m)
        panel._hp_bar["value"] = max(0, hp_c)

        mn_c, mn_m = char["mana_current"], char["mana_max"]
        panel._mana_label.set(f"Mana: {mn_c}/{mn_m}")
        panel._mana_bar["maximum"] = max(1, mn_m)
        panel._mana_bar["value"] = max(0, mn_c)

        md = char["mana_density"]
        md_mult = mana_density_multiplier(md)
        panel._md_label.set(f"Mana Density: {md}  ({md_mult:.2f}x)")

        for key, sv in panel._stat_vars.items():
            sv.set(str(char["stats"].get(key, 0)))

    # ---- Character loading ----

    def _refresh_char_a(self):
        data = self.get_char_a_data()
        if data is None:
            self.char_a = None
        else:
            self.char_a = data
        self._update_panel(self.panel_a, self.char_a)
        if self.var_attacker.get() == "A":
            self._populate_action_list()
        self.var_status.set("Character A refreshed from sheet.")

    def _load_char_b(self):
        path = filedialog.askopenfilename(
            title="Select character file for Character B",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.char_b = build_sim_character(raw)
            self._update_panel(self.panel_b, self.char_b)
            if self.var_attacker.get() == "B":
                self._populate_action_list()
            self.var_status.set(f"Loaded Character B: {self.char_b['name']}")
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load character:\n{e}")

    def _reset_sim(self):
        if self.char_a:
            self.char_a["hp_current"] = self.char_a["hp_max"]
            self.char_a["mana_current"] = self.char_a["mana_max"]
            self._update_panel(self.panel_a, self.char_a)
        if self.char_b:
            self.char_b["hp_current"] = self.char_b["hp_max"]
            self.char_b["mana_current"] = self.char_b["mana_max"]
            self._update_panel(self.panel_b, self.char_b)
        self.var_status.set("HP and Mana reset to max.")

    # ---- Action list ----

    def _on_attacker_changed(self):
        self._populate_action_list()

    def _populate_action_list(self):
        self.action_list.delete(0, tk.END)
        attacker = self._get_attacker()
        if attacker is None:
            return
        for a in attacker.get("actions", []):
            self.action_list.insert(tk.END, a["display"])

    def _get_attacker(self):
        return self.char_a if self.var_attacker.get() == "A" else self.char_b

    def _get_defender(self):
        return self.char_b if self.var_attacker.get() == "A" else self.char_a

    def _get_selected_action(self):
        attacker = self._get_attacker()
        if attacker is None:
            return None
        sel = list(self.action_list.curselection())
        if len(sel) != 1:
            return None
        idx = sel[0]
        actions = attacker.get("actions", [])
        if 0 <= idx < len(actions):
            return actions[idx]
        return None

    # ---- Combat log ----

    def _log(self, msg: str):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ---- Accuracy check ----

    def _do_check_accuracy(self):
        attacker = self._get_attacker()
        defender = self._get_defender()
        action = self._get_selected_action()

        if attacker is None or defender is None:
            messagebox.showwarning("Battle Sim", "Load both characters first.")
            return
        if action is None:
            messagebox.showwarning("Battle Sim", "Select an action from the list.")
            return

        d20_str = self.var_d20.get().strip()
        if not d20_str:
            messagebox.showwarning("Battle Sim", "Enter a d20 roll value.")
            return

        try:
            d20 = int(d20_str)
        except ValueError:
            messagebox.showwarning("Battle Sim", "d20 roll must be a number.")
            return

        ref = action["ref"]
        kind = action["kind"]

        # Determine accuracy stat
        if kind == "ability":
            acc_stat = attacker["stats"].get("spellcraft", 0)
            acc_label = "Spellcraft"
        elif ref.get("is_ranged", False):
            acc_stat = attacker["stats"].get("ranged_acc", 0)
            acc_label = "Ranged Acc"
        else:
            acc_stat = attacker["stats"].get("melee_acc", 0)
            acc_label = "Melee Acc"

        roll_mult = hit_roll_multiplier(d20)
        effective_acc = acc_stat * roll_mult
        evasion = defender["stats"].get("evasion", 0)
        glance_mult = evasion_damage_multiplier(effective_acc, evasion)
        glance_pct = int(glance_mult * 100)

        a_name = attacker["name"]
        d_name = defender["name"]

        if glance_pct == 0:
            result = (f"{a_name} → {d_name}: {acc_label} {acc_stat} x{roll_mult:.2f} (d20={d20}) "
                      f"= Eff Acc {effective_acc:.1f} vs Evasion {evasion} → MISS")
        else:
            result = (f"{a_name} → {d_name}: {acc_label} {acc_stat} x{roll_mult:.2f} (d20={d20}) "
                      f"= Eff Acc {effective_acc:.1f} vs Evasion {evasion} → {glance_pct}% damage")

        self._log(result)
        self.var_status.set(f"Accuracy: {effective_acc:.1f} → {glance_pct}% damage")

    # ---- Attack ----

    def _do_attack(self):
        attacker = self._get_attacker()
        defender = self._get_defender()
        action = self._get_selected_action()

        if attacker is None or defender is None:
            messagebox.showwarning("Battle Sim", "Load both characters first.")
            return
        if action is None:
            messagebox.showwarning("Battle Sim", "Select an action from the list.")
            return

        ref = action["ref"]
        kind = action["kind"]
        slot = action.get("slot")
        a_name = attacker["name"]
        d_name = defender["name"]

        # Parse damage roll
        dmg_roll_str = self.var_damage_roll.get().strip()
        if not dmg_roll_str:
            messagebox.showwarning("Battle Sim", "Enter a Damage Roll value (dice result).")
            return
        try:
            dmg_roll = int(dmg_roll_str)
        except ValueError:
            messagebox.showwarning("Battle Sim", "Damage Roll must be a number.")
            return

        # Parse damage expression for flat bonus
        dmg_expr = (ref.get("damage") or "").strip()
        parsed = parse_damage_expr(dmg_expr)
        flat_bonus = 0
        if parsed:
            _, _, flat_bonus = parsed
        base_damage = dmg_roll + flat_bonus

        # ---- Accuracy + Glancing blow ----
        d20_str = self.var_d20.get().strip()
        effective_acc = None
        glance_mult = 1.0
        glance_pct = 100
        acc_info = ""

        if d20_str:
            try:
                d20 = int(d20_str)
            except ValueError:
                d20 = 10

            if kind == "ability":
                acc_stat = attacker["stats"].get("spellcraft", 0)
                acc_label = "Spellcraft"
            elif ref.get("is_ranged", False):
                acc_stat = attacker["stats"].get("ranged_acc", 0)
                acc_label = "Ranged Acc"
            else:
                acc_stat = attacker["stats"].get("melee_acc", 0)
                acc_label = "Melee Acc"

            roll_mult = hit_roll_multiplier(d20)
            effective_acc = acc_stat * roll_mult
            evasion = defender["stats"].get("evasion", 0)
            glance_mult = evasion_damage_multiplier(effective_acc, evasion)
            glance_pct = int(glance_mult * 100)

            acc_info = f"Acc {effective_acc:.1f} vs Eva {evasion} → {glance_pct}%"

            if glance_pct == 0:
                self._log(f"{a_name} attacks {d_name} with {ref['name']}: {acc_info} — MISS!")
                self.var_status.set("MISS — no damage dealt.")
                return

        # ---- Damage calculation ----
        log_parts = [f"{a_name} attacks {d_name} with {ref['name']}"]

        if kind == "item":
            # PBD / Precision multiplier
            total = base_damage
            mult_info = ""
            if ref.get("apply_bonus", True):
                is_ranged = ref.get("is_ranged", False)
                pts = attacker["stats"].get("precision" if is_ranged else "pbd", 0)
                mult = mana_density_multiplier(pts)
                total = int(math.floor(base_damage * mult))
                mult_label = "Precision" if is_ranged else "PBD"
                mult_info = f" * {mult_label} {mult:.2f}x"

            # Apply glancing blow
            after_glance = int(math.floor(total * glance_mult))

            # Apply DR
            dr = phys_dr_from_points(defender["stats"].get("phys_def", 0))
            final = max(0, after_glance - dr)

            detail = f"Base {base_damage} (roll {dmg_roll}+{flat_bonus}){mult_info}"
            if glance_pct < 100:
                detail += f" * Glancing {glance_pct}% = {after_glance}"
            if dr > 0:
                detail += f" - DR {dr}"
            detail += f" = {final} damage"

            log_parts.append(detail)
            if acc_info:
                log_parts.insert(1, acc_info)

            # Apply damage to defender
            defender["hp_current"] = max(0, defender["hp_current"] - final)
            log_parts.append(f"{d_name} HP: {defender['hp_current']}/{defender['hp_max']}")

        else:
            # Ability
            slot = slot or "inner"
            mods = ABILITY_MODS.get(slot, {"dmg": 1.0, "mana": 1.0})
            dmg_mult = float(mods["dmg"])
            mana_mult = float(mods["mana"])

            base_cost = int(ref.get("mana_cost", 0) or 0)

            # Mana spend
            mana_spend_str = self.var_mana_spend.get().strip()
            if mana_spend_str:
                try:
                    mana_spend = int(mana_spend_str)
                except ValueError:
                    mana_spend = base_cost
            else:
                mana_spend = base_cost

            if mana_spend < base_cost:
                mana_spend = base_cost

            base_eff = int(math.ceil(base_cost * mana_mult))
            spent_eff = int(math.ceil(mana_spend * mana_mult))

            # Mana Density
            md_pts = attacker["mana_density"]
            md_mult = mana_density_multiplier(md_pts)

            # Overcast
            over = ref.get("overcast", {})
            over_bonus = compute_overcast_bonus(base_eff, spent_eff, over)

            raw_total = int(math.floor((base_damage + over_bonus) * dmg_mult * md_mult))

            # Apply glancing blow
            after_glance = int(math.floor(raw_total * glance_mult))

            # Apply DR
            dr = phys_dr_from_points(defender["stats"].get("phys_def", 0))
            final = max(0, after_glance - dr)

            detail = f"Base {base_damage}"
            if over_bonus > 0:
                detail += f" + Overcast {over_bonus}"
            detail += f" * {slot} {dmg_mult:.2f}x * MD {md_mult:.2f}x = {raw_total}"
            if glance_pct < 100:
                detail += f" * Glancing {glance_pct}% = {after_glance}"
            if dr > 0:
                detail += f" - DR {dr}"
            detail += f" = {final} damage"

            log_parts.append(detail)
            if acc_info:
                log_parts.insert(1, acc_info)

            # Deduct mana from attacker
            attacker["mana_current"] = max(0, attacker["mana_current"] - spent_eff)
            log_parts.append(f"Mana spent: {spent_eff} (base {base_cost} * {mana_mult:.2f}x)")

            # Apply damage to defender
            defender["hp_current"] = max(0, defender["hp_current"] - final)
            log_parts.append(f"{d_name} HP: {defender['hp_current']}/{defender['hp_max']}")

        # Log and update
        self._log(" | ".join(log_parts))
        self.var_status.set(f"{d_name} took {final} damage. HP: {defender['hp_current']}/{defender['hp_max']}")

        # Update panels
        self._update_panel(self.panel_a, self.char_a)
        self._update_panel(self.panel_b, self.char_b)

    # ---- Refresh on tab switch ----

    def refresh(self):
        """Called when tab becomes visible to sync Character A."""
        self._refresh_char_a()

    # ---- Theme ----

    def apply_theme(self, colors: dict):
        self._colors = colors
        for w in self._tk_widgets:
            try:
                w.configure(bg=colors["entry_bg"], fg=colors["entry_fg"])
                if isinstance(w, tk.Listbox):
                    w.configure(selectbackground=colors["select_bg"],
                                selectforeground=colors["select_fg"])
            except Exception:
                pass
