# character_sheet.py
import json
import math
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path

# When running as a frozen PyInstaller GUI app (console=False),
# stdout/stderr are None which causes print() to crash.
# Redirect them to devnull to prevent errors and stray console windows.
if getattr(sys, 'frozen', False):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')

import tkinter as tk
import tkinter.font as tkFont
from tkinter import ttk, messagebox, filedialog

# ---------------- Theme / Dark Mode ----------------

DARK_COLORS = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
    "entry_bg": "#2d2d2d",
    "entry_fg": "#d4d4d4",
    "select_bg": "#264f78",
    "select_fg": "#ffffff",
    "accent": "#569cd6",
    "gray": "#808080",
    "red": "#f44747",
    "frame_bg": "#252526",
    "button_bg": "#3c3c3c",
    "canvas_bg": "#1e1e1e",
    "canvas_fg": "#d4d4d4",
    "canvas_line": "#569cd6",
    "tab_bg": "#2d2d2d",
    "tab_selected": "#1e1e1e",
    "labelframe_bg": "#252526",
}

LIGHT_COLORS = {
    "bg": "#f0f0f0",
    "fg": "#000000",
    "entry_bg": "#ffffff",
    "entry_fg": "#000000",
    "select_bg": "#0078d7",
    "select_fg": "#ffffff",
    "accent": "#0078d7",
    "gray": "gray",
    "red": "red",
    "frame_bg": "#f0f0f0",
    "button_bg": "#e1e1e1",
    "canvas_bg": "#ffffff",
    "canvas_fg": "#000000",
    "canvas_line": "#0078d7",
    "tab_bg": "#e1e1e1",
    "tab_selected": "#f0f0f0",
    "labelframe_bg": "#f0f0f0",
}

PREFS_PATH = Path(os.path.expanduser("~")) / ".homebrew_sheet_prefs.json"


def load_prefs() -> dict:
    """Load all preferences from disk. Returns dict with defaults for missing keys."""
    defaults = {"dark_mode": False, "ui_scale": 1.0}
    try:
        with open(PREFS_PATH, "r") as f:
            saved = json.load(f)
        for k, v in defaults.items():
            if k not in saved:
                saved[k] = v
        return saved
    except Exception:
        return dict(defaults)


def save_prefs(prefs: dict):
    try:
        with open(PREFS_PATH, "w") as f:
            json.dump(prefs, f)
    except Exception:
        pass


def load_theme_pref() -> bool:
    return load_prefs().get("dark_mode", False)


def save_theme_pref(dark: bool):
    prefs = load_prefs()
    prefs["dark_mode"] = dark
    save_prefs(prefs)


def apply_ttk_theme(style: ttk.Style, colors: dict):
    """Configure the ttk Style object for all widget types."""
    style.theme_use("clam")

    style.configure("TFrame", background=colors["bg"])
    style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
    style.configure("TLabelframe", background=colors["labelframe_bg"],
                     foreground=colors["fg"])
    style.configure("TLabelframe.Label", background=colors["labelframe_bg"],
                     foreground=colors["fg"])
    style.configure("TButton", background=colors["button_bg"],
                     foreground=colors["fg"])
    style.map("TButton",
              background=[("active", colors["accent"])],
              foreground=[("active", colors["select_fg"])])
    style.configure("TEntry", fieldbackground=colors["entry_bg"],
                     foreground=colors["entry_fg"],
                     insertcolor=colors["fg"])
    style.configure("TCombobox", fieldbackground=colors["entry_bg"],
                     foreground=colors["entry_fg"],
                     selectbackground=colors["select_bg"],
                     selectforeground=colors["select_fg"])
    style.map("TCombobox",
              fieldbackground=[("readonly", colors["entry_bg"])],
              foreground=[("readonly", colors["entry_fg"])])
    style.configure("TCheckbutton", background=colors["bg"],
                     foreground=colors["fg"])
    style.map("TCheckbutton",
              background=[("active", colors["bg"])])
    style.configure("TNotebook", background=colors["bg"])
    style.configure("TNotebook.Tab", background=colors["tab_bg"],
                     foreground=colors["fg"], padding=[8, 4])
    style.map("TNotebook.Tab",
              background=[("selected", colors["tab_selected"])],
              foreground=[("selected", colors["fg"])])
    style.configure("TSeparator", background=colors["gray"])
    style.configure("TScrollbar", background=colors["button_bg"],
                     troughcolor=colors["bg"])

    # Special named styles for gray/red info labels
    style.configure("Gray.TLabel", background=colors["bg"],
                     foreground=colors["gray"])
    style.configure("Red.TLabel", background=colors["bg"],
                     foreground=colors["red"])


def style_tk_widget(widget, colors: dict):
    """Apply theme colors to a raw tk widget (Text, Listbox, Canvas)."""
    wclass = widget.winfo_class()
    if wclass == "Text":
        widget.configure(
            bg=colors["entry_bg"], fg=colors["entry_fg"],
            insertbackground=colors["fg"],
            selectbackground=colors["select_bg"],
            selectforeground=colors["select_fg"],
        )
    elif wclass == "Listbox":
        widget.configure(
            bg=colors["entry_bg"], fg=colors["entry_fg"],
            selectbackground=colors["select_bg"],
            selectforeground=colors["select_fg"],
        )
    elif wclass == "Canvas":
        widget.configure(bg=colors["canvas_bg"])


def style_toplevel(win, colors: dict):
    """Apply theme background to a Toplevel window."""
    win.configure(bg=colors["bg"])

# Ollama for AI-powered spell generation
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Warning: ollama package not found. Spell generation will use template-based fallback.")

from damage_lab import DamageLabTab
from battle_sim import BattleSimTab, build_sim_character

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

# -------- Spell Generation System --------

SPELL_ARCHETYPES = {
    "offensive": {
        "roll_types": ["Attack", "Save"],
        "power_weight": 1.0,
        "mana_weight": 1.0,
    },
    "defensive": {
        "roll_types": ["None"],
        "power_weight": 0.6,
        "mana_weight": 0.8,
    },
    "utility": {
        "roll_types": ["None", "Check"],
        "power_weight": 0.4,
        "mana_weight": 0.7,
    },
    "buff": {
        "roll_types": ["None"],
        "power_weight": 0.7,
        "mana_weight": 1.2,
    },
    "debuff": {
        "roll_types": ["Save", "Check"],
        "power_weight": 0.8,
        "mana_weight": 0.9,
    },
}

SPELL_ELEMENTS = {
    "fire": {"adjectives": ["Blazing", "Scorching", "Infernal", "Searing"], "nouns": ["Flame", "Ember", "Conflagration", "Pyre"]},
    "ice": {"adjectives": ["Frozen", "Chilling", "Glacial", "Arctic"], "nouns": ["Frost", "Shard", "Blizzard", "Crystal"]},
    "lightning": {"adjectives": ["Electric", "Thunderous", "Crackling", "Shocking"], "nouns": ["Bolt", "Storm", "Arc", "Spark"]},
    "arcane": {"adjectives": ["Mystical", "Ethereal", "Eldritch", "Runic"], "nouns": ["Missile", "Orb", "Beam", "Pulse"]},
    "shadow": {"adjectives": ["Dark", "Umbral", "Void", "Tenebrous"], "nouns": ["Shroud", "Tendril", "Veil", "Curse"]},
    "light": {"adjectives": ["Radiant", "Holy", "Brilliant", "Sacred"], "nouns": ["Ray", "Lance", "Blessing", "Aura"]},
    "nature": {"adjectives": ["Verdant", "Primal", "Wild", "Living"], "nouns": ["Vine", "Thorn", "Growth", "Wrath"]},
    "force": {"adjectives": ["Telekinetic", "Kinetic", "Crushing", "Pushing"], "nouns": ["Blast", "Wave", "Hammer", "Shield"]},
    "healing": {"adjectives": ["Soothing", "Regenerative", "Vital", "Mending"], "nouns": ["Touch", "Word", "Light", "Spring"]},
    "psychic": {"adjectives": ["Mental", "Psionic", "Mind", "Cerebral"], "nouns": ["Blast", "Spike", "Whisper", "Scream"]},
}

SPELL_ACTIONS = {
    "offensive": ["Strike", "Blast", "Bolt", "Lance", "Storm", "Barrage", "Burst"],
    "defensive": ["Shield", "Ward", "Barrier", "Wall", "Aegis", "Protection"],
    "utility": ["Sense", "Detection", "Vision", "Manipulation", "Channel"],
    "buff": ["Enhancement", "Empowerment", "Blessing", "Invigoration", "Fortification"],
    "debuff": ["Curse", "Hex", "Bane", "Weakness", "Drain"],
}

TIER_DICE = {
    "T1": {"min": 4, "max": 6, "count_range": (1, 2)},
    "T2": {"min": 6, "max": 8, "count_range": (1, 3)},
    "T3": {"min": 8, "max": 12, "count_range": (2, 4)},
    "T4": {"min": 10, "max": 20, "count_range": (2, 5)},
}

DEFAULT_TIER_DICE = {"min": 4, "max": 6, "count_range": (1, 2)}

KEYWORD_TO_ELEMENT = {
    # Fire family
    "fire": "fire", "flame": "fire", "burn": "fire", "heat": "fire", "inferno": "fire",
    "ignite": "fire", "scorch": "fire", "blaze": "fire",
    # Ice family
    "ice": "ice", "frost": "ice", "cold": "ice", "freeze": "ice", "chill": "ice",
    "snow": "ice", "winter": "ice", "glacial": "ice",
    # Lightning family
    "lightning": "lightning", "thunder": "lightning", "electric": "lightning",
    "shock": "lightning", "storm": "lightning", "spark": "lightning",
    # Arcane family
    "magic": "arcane", "arcane": "arcane", "mystical": "arcane", "ethereal": "arcane",
    "mana": "arcane", "spell": "arcane", "rune": "arcane",
    # Shadow family
    "shadow": "shadow", "dark": "shadow", "darkness": "shadow", "void": "shadow",
    "curse": "shadow", "necrotic": "shadow", "death": "shadow",
    # Light family
    "light": "light", "holy": "light", "radiant": "light", "divine": "light",
    "sacred": "light", "celestial": "light", "sun": "light",
    # Nature family
    "nature": "nature", "plant": "nature", "earth": "nature", "wood": "nature",
    "vine": "nature", "thorn": "nature", "druid": "nature", "wild": "nature",
    # Force family
    "force": "force", "kinetic": "force", "telekinetic": "force", "push": "force",
    "pull": "force", "gravity": "force",
    # Healing family
    "heal": "healing", "cure": "healing", "restore": "healing", "mend": "healing",
    "regenerate": "healing", "recovery": "healing", "life": "healing",
    # Psychic family
    "mind": "psychic", "psychic": "psychic", "mental": "psychic", "telepathy": "psychic",
    "illusion": "psychic", "thought": "psychic",
}

KEYWORD_TO_ARCHETYPE = {
    # Offensive
    "attack": "offensive", "damage": "offensive", "hurt": "offensive", "kill": "offensive",
    "blast": "offensive", "strike": "offensive", "offensive": "offensive", "combat": "offensive",
    # Defensive
    "defense": "defensive", "defend": "defensive", "protect": "defensive", "shield": "defensive",
    "block": "defensive", "ward": "defensive", "barrier": "defensive", "armor": "defensive",
    # Utility
    "utility": "utility", "detect": "utility", "sense": "utility", "explore": "utility",
    "manipulate": "utility", "tool": "utility", "skill": "utility",
    # Buff
    "buff": "buff", "enhance": "buff", "strengthen": "buff", "empower": "buff",
    "boost": "buff", "improve": "buff", "augment": "buff",
    # Debuff
    "debuff": "debuff", "weaken": "debuff", "hinder": "debuff", "slow": "debuff",
    "curse": "debuff", "hex": "debuff", "impair": "debuff",
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

# -------- Mob Generator Constants --------

MOB_STAT_RANGES = {
    "T1": (10, 30),
    "T2": (30, 60),
    "T3": (60, 110),
    "T4": (110, 200),
}

MOB_HP_RANGES = {
    "T1": (40, 200),
    "T2": (160, 500),
    "T3": (400, 1000),
    "T4": (800, 2000),
}

MOB_MANA_RANGES = {
    "T1": (20, 100),
    "T2": (80, 240),
    "T3": (200, 600),
    "T4": (500, 1200),
}

# NPC ranges -- human-level (1x), roughly half of monster ranges
NPC_STAT_RANGES = {
    "T1": (5, 15),
    "T2": (15, 30),
    "T3": (30, 55),
    "T4": (55, 100),
}

NPC_HP_RANGES = {
    "T1": (20, 100),
    "T2": (80, 250),
    "T3": (200, 500),
    "T4": (400, 1000),
}

NPC_MANA_RANGES = {
    "T1": (10, 50),
    "T2": (40, 120),
    "T3": (100, 300),
    "T4": (250, 600),
}

MOB_POSITION_RANGES = {
    "Bottom": (0.0, 0.15),
    "Low":    (0.15, 0.35),
    "Mid":    (0.35, 0.55),
    "High":   (0.55, 0.75),
    "Peak":   (0.75, 1.0),
}

MOB_POWER_MULTIPLIERS = {
    "Swarm":          0.3,
    "Extremely Weak": 0.5,
    "Weak":           0.65,
    "Adept":          0.8,
    "Average":        1.0,
    "Above Average":  1.15,
    "Strong":         1.3,
    "Elite":          1.5,
    "Scion":          1.75,
    "Best in World":  2.0,
}

MOB_TAG_WEIGHTS = {
    "Melee": {
        "melee_acc": 1.3, "pbd": 1.3, "strength": 1.2, "phys_def": 1.2,
        "ranged_acc": 0.7, "spellcraft": 0.7, "mana_density": 0.7,
        "precision": 0.7, "evasion": 0.7, "wis_def": 0.7,
        "utility": 0.7, "agility": 0.7,
    },
    "Ranged": {
        "ranged_acc": 1.3, "precision": 1.3, "agility": 1.2, "evasion": 1.2,
        "melee_acc": 0.7, "pbd": 0.7, "strength": 0.7, "spellcraft": 0.7,
        "mana_density": 0.7, "phys_def": 0.7, "wis_def": 0.7, "utility": 0.7,
    },
    "Magic": {
        "spellcraft": 1.3, "mana_density": 1.4, "wis_def": 1.1,
        "melee_acc": 0.6, "ranged_acc": 0.6, "pbd": 0.6, "strength": 0.6,
        "precision": 0.6, "phys_def": 0.6, "evasion": 0.6,
        "utility": 0.6, "agility": 0.6,
        "mana_pool_mult": 1.5,
    },
    "Support": {
        "wis_def": 1.3, "utility": 1.3, "mana_density": 1.1,
        "melee_acc": 0.9, "ranged_acc": 0.9, "spellcraft": 0.9,
        "pbd": 0.9, "precision": 0.9, "phys_def": 0.9,
        "evasion": 0.9, "strength": 0.9, "agility": 0.9,
    },
}

MOB_NAME_PREFIXES = [
    "Shadow", "Iron", "Crimson", "Stone", "Frost", "Dark", "Wild", "Storm",
    "Ancient", "Rogue", "Fell", "Dread", "Ember", "Thorn", "Pale", "Grim",
    "Hollow", "Dire", "Silent", "Ashen", "Blighted", "Rusted", "Scarred",
]

MOB_NAME_BASES = [
    "Wolf", "Skeleton", "Golem", "Drake", "Bandit", "Spider", "Wraith",
    "Troll", "Cultist", "Serpent", "Guardian", "Knight", "Mage", "Scout",
    "Brute", "Archer", "Sentinel", "Prowler", "Shade", "Beast", "Elemental",
    "Warden", "Reaver", "Stalker", "Fiend", "Construct", "Phantasm",
]

MOB_COMBAT_TAGS = ["Melee", "Ranged", "Magic", "Support"]

# ---------- New Stats (your list) ----------
STAT_ORDER = [
    ("melee_acc",     "Melee Accuracy"),
    ("ranged_acc",    "Ranged Weapon Accuracy"),
    ("spellcraft",    "Spellcraft"),
    ("pbd",           "PBD"),
    ("mana_density",  "Mana Density"),
    ("precision",     "Precision"),

    ("phys_def",      "Defense"),
    ("evasion",       "Evasion"),
    ("wis_def",       "Wisdom"),

    ("utility",       "Utility"),
    ("agility",       "Agility"),
    ("strength",      "Strength"),
]
STAT_KEYS = [k for k, _ in STAT_ORDER]

ARMOR_SLOTS = [
    "Head",
    "Shoulders",
    "Chest",
    "Back",
    "Upper Arms",
    "Bracers/Forearms",
    "Gauntlets/Hands",
    "Belt/Waist",
    "Legs/Greaves",
    "Boots/Feet",
    "Necklace",
    "Left Thumb",
    "Left Index",
    "Left Middle",
    "Left Ring",
    "Left Pinky",
    "Right Thumb",
    "Right Index",
    "Right Middle",
    "Right Ring",
    "Right Pinky",
]


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


def hit_roll_multiplier(d20_roll: int) -> float:
    """
    Piecewise linear mapping from a d20 roll to an accuracy multiplier:
      1  -> 0.05
      2  -> 0.20
      10 -> 1.00
      19 -> 2.00
      20 -> 5.00
    Linearly interpolates between these anchors.
    """
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
    """
    Glancing blow system: damage multiplier based on accuracy-to-evasion ratio.
    Uses piecewise linear interpolation between these anchors:
      ratio <= 0.90  ->  0.00  (miss / no damage)
      ratio  = 0.95  ->  0.25  (25% damage)
      ratio  = 1.00  ->  0.50  (50% damage)
      ratio  = 1.05  ->  0.75  (75% damage)
      ratio >= 1.10  ->  1.00  (full damage)
    """
    if evasion <= 0:
        return 1.0  # no evasion = full damage
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
            "unspent_points": 0
        },
        "stats": {k: (0 if k == "mana_density" else 5) for k in STAT_KEYS},
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
    Also migrates PBD from resources into stats (old saves stored it there).
    """
    if not isinstance(char, dict):
        return

    stats = char.get("stats")
    if not isinstance(stats, dict):
        char["stats"] = {k: 0 for k in STAT_KEYS}
        stats = char["stats"]

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
        stats = char["stats"]
    else:
        for k in STAT_KEYS:
            if k not in stats:
                stats[k] = 0
            try:
                stats[k] = int(stats[k] or 0)
            except Exception:
                stats[k] = 0

    # Migrate PBD from resources to stats (old saves stored pbd under resources)
    res = char.get("resources", {})
    if "pbd" in res and isinstance(res, dict):
        old_pbd = _get_int(res, "pbd", 0)
        if old_pbd > 0 and stats.get("pbd", 0) == 0:
            stats["pbd"] = old_pbd
        del res["pbd"]

    # Migrate Mana Density from resources to stats (old saves stored it under resources)
    if isinstance(res, dict) and "mana_density" in res:
        old_md = _get_int(res, "mana_density", 0)
        if old_md > 0 and stats.get("mana_density", 0) == 0:
            stats["mana_density"] = old_md
        del res["mana_density"]


def sort_favorites_first(items):
    return sorted(items, key=lambda it: (not bool(it.get("favorite", False)), it.get("name", "").lower()))


BOOST_TARGETS = STAT_KEYS + ["hp_max", "mana_max"]
BOOST_TARGET_LABELS = [(k, lbl) for k, lbl in STAT_ORDER] + [("hp_max", "HP Max"), ("mana_max", "Mana Max")]


def _normalize_stat_boosts(raw) -> list:
    """Normalize stat_boosts list from saved data. Each boost is {stat, value, mode}."""
    if not isinstance(raw, list):
        return []
    boosts = []
    for b in raw:
        if not isinstance(b, dict):
            continue
        stat = b.get("stat", "")
        if stat not in BOOST_TARGETS:
            continue
        try:
            value = float(b.get("value", 0) or 0)
        except (ValueError, TypeError):
            value = 0
        mode = b.get("mode", "flat")
        if mode not in ("flat", "percent"):
            mode = "flat"
        if value != 0:
            boosts.append({"stat": stat, "value": value, "mode": mode})
    return boosts


def _safe_int(v, default=0):
    try:
        return int(v or default)
    except (ValueError, TypeError):
        return default


def ensure_item_obj(x):
    """
    Items:
      - apply_bonus: whether to apply PBD (melee) or Precision (ranged)
      - is_ranged: whether to treat this as a ranged item (use Precision)
      - stat_boosts: list of passive stat boosts [{stat, value, mode}]
      - consumable: if True, item is removed on use
      - consume_heal_hp / consume_heal_mana: instant heal on consume
      - consume_turns: if >0, stat_boosts become a temporary buff for N turns
    Back-compat:
      - older files may have apply_pbd
    """
    defaults = {
        "name": "", "favorite": False, "roll_type": "None", "damage": "",
        "notes": "", "apply_bonus": True, "apply_pbd": True, "is_ranged": False,
        "stat_boosts": [], "consumable": False,
        "consume_heal_hp": 0, "consume_heal_mana": 0, "consume_turns": 0,
        "consume_perm_stat": "", "consume_perm_value": 0,
        "is_growth_item": False, "weight": 0.0, "armor_slot": "",
    }
    if isinstance(x, str):
        d = dict(defaults)
        d["name"] = x
        return d
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
            "stat_boosts": _normalize_stat_boosts(x.get("stat_boosts")),
            "consumable": bool(x.get("consumable", False)),
            "consume_heal_hp": _safe_int(x.get("consume_heal_hp"), 0),
            "consume_heal_mana": _safe_int(x.get("consume_heal_mana"), 0),
            "consume_turns": _safe_int(x.get("consume_turns"), 0),
            "consume_perm_stat": x.get("consume_perm_stat", ""),
            "consume_perm_value": _safe_int(x.get("consume_perm_value"), 0),
            "is_growth_item": bool(x.get("is_growth_item", False)),
            "weight": float(x.get("weight", 0) or 0),
            "armor_slot": x.get("armor_slot", ""),
        }
    return dict(defaults)


def ensure_ability_obj(x):
    """
    Abilities NEVER use PBD/Precision. They can optionally have overcast scaling.
    """
    if isinstance(x, str):
        return {
            "name": x, "favorite": False, "roll_type": "None",
            "damage": "", "mana_cost": 0, "notes": "",
            "overcast": {"enabled": False, "scale": 0, "power": 0.85, "cap": 999},
            "stat_boosts": [], "buff_turns": 0,
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
            "stat_boosts": _normalize_stat_boosts(x.get("stat_boosts")),
            "buff_turns": _safe_int(x.get("buff_turns"), 0),
        }

    return {
        "name": "", "favorite": False, "roll_type": "None",
        "damage": "", "mana_cost": 0, "notes": "",
        "overcast": {"enabled": False, "scale": 0, "power": 0.85, "cap": 999},
        "stat_boosts": [], "buff_turns": 0,
    }


def find_show_must_go_on(char):
    t1 = char.get("talents", {}).get("T1")
    if not t1:
        return None
    for eff in t1.get("effects", []):
        if eff.get("id") == "show_must_go_on":
            return eff
    return None


# ---------------- Spell Generation Functions ----------------

def parse_research_prompt(prompt: str) -> dict:
    """
    Extract spell generation hints from user prompt.

    Returns dict with:
        - elements: list of matching elements (default ["arcane"])
        - archetypes: list of matching archetypes (default ["offensive", "utility"])
        - keywords: raw words from prompt
    """
    prompt_lower = prompt.lower()
    words = re.findall(r'\w+', prompt_lower)

    elements = []
    archetypes = []

    for word in words:
        if word in KEYWORD_TO_ELEMENT:
            elem = KEYWORD_TO_ELEMENT[word]
            if elem not in elements:
                elements.append(elem)

        if word in KEYWORD_TO_ARCHETYPE:
            arch = KEYWORD_TO_ARCHETYPE[word]
            if arch not in archetypes:
                archetypes.append(arch)

    # Defaults if nothing detected
    if not elements:
        elements = ["arcane", "force"]
    if not archetypes:
        archetypes = ["offensive", "utility"]

    return {
        "elements": elements,
        "archetypes": archetypes,
        "keywords": words,
    }


def generate_spell_name(element: str, archetype: str) -> str:
    """
    Generate creative spell name from element + archetype.

    Patterns:
        1. [Adjective] [Action]
        2. [Element Noun] [Action]
        3. [Adjective] [Element Noun]
    """
    elem_data = SPELL_ELEMENTS.get(element, SPELL_ELEMENTS["arcane"])
    actions = SPELL_ACTIONS.get(archetype, SPELL_ACTIONS["offensive"])

    pattern = random.choice([1, 2, 3])

    if pattern == 1:
        # "Blazing Strike", "Frozen Shield"
        adj = random.choice(elem_data["adjectives"])
        action = random.choice(actions)
        return f"{adj} {action}"

    elif pattern == 2:
        # "Flame Bolt", "Frost Ward"
        noun = random.choice(elem_data["nouns"])
        action = random.choice(actions)
        return f"{noun} {action}"

    else:  # pattern == 3
        # "Searing Flame", "Chilling Frost"
        adj = random.choice(elem_data["adjectives"])
        noun = random.choice(elem_data["nouns"])
        return f"{adj} {noun}"


def calculate_spell_stats(archetype: str, tier: str, category: str, mana_density: int) -> dict:
    """
    Calculate balanced spell stats.

    Returns dict with:
        - damage: dice expression string
        - mana_cost: int
        - roll_type: str
        - overcast: dict (optional)
    """
    # Get tier dice info
    tier_info = TIER_DICE.get(tier, DEFAULT_TIER_DICE)
    archetype_data = SPELL_ARCHETYPES.get(archetype, SPELL_ARCHETYPES["offensive"])

    # Get category modifiers
    cat_mods = ABILITY_MODS.get(category, ABILITY_MODS["inner"])

    # Calculate dice
    dice_count = random.randint(*tier_info["count_range"])
    dice_size = random.choice([d for d in [4, 6, 8, 10, 12, 20]
                                if tier_info["min"] <= d <= tier_info["max"]])

    # Flat bonus based on tier
    flat_bonus = random.randint(0, dice_count)

    # Apply archetype power scaling
    if archetype_data["power_weight"] < 1.0:
        # Reduce dice for defensive/utility
        if random.random() > archetype_data["power_weight"]:
            dice_count = max(1, dice_count - 1)

    # Build damage expression
    damage = f"{dice_count}d{dice_size}"
    if flat_bonus > 0:
        damage += f"+{flat_bonus}"

    # Calculate mana cost
    # Base: avg damage * category mana mod * archetype mana weight
    avg_dmg = dice_count * (dice_size / 2 + 0.5) + flat_bonus
    base_mana = int(avg_dmg * cat_mods["mana"] * archetype_data["mana_weight"])

    # Add randomness (±20%)
    mana_variance = int(base_mana * 0.2)
    mana_cost = max(1, base_mana + random.randint(-mana_variance, mana_variance))

    # Roll type
    roll_type = random.choice(archetype_data["roll_types"])

    # Overcast (30% chance for offensive spells)
    overcast = {"enabled": False, "scale": 0, "power": 0.85, "cap": 999}
    if archetype == "offensive" and random.random() < 0.3:
        overcast["enabled"] = True
        overcast["scale"] = random.randint(2, 5)
        overcast["cap"] = dice_count * dice_size * 2  # reasonable cap

    return {
        "damage": damage if roll_type in ["Attack", "Save"] else "",
        "mana_cost": mana_cost,
        "roll_type": roll_type,
        "overcast": overcast,
    }


def generate_spell_description(name: str, element: str, archetype: str, stats: dict) -> str:
    """
    Generate flavorful but concise spell description.
    """
    # Templates by archetype
    templates = {
        "offensive": [
            f"Channel {element} energy into a devastating attack.",
            f"Unleash a {element}-infused strike against your foes.",
            f"Project destructive {element} force at your target.",
        ],
        "defensive": [
            f"Conjure a protective {element} barrier around yourself or an ally.",
            f"Summon {element} energy to deflect incoming harm.",
            f"Create a defensive shield woven from {element} magic.",
        ],
        "utility": [
            f"Manipulate {element} to achieve practical effects.",
            f"Harness {element} magic for problem-solving.",
            f"Channel {element} energy in a focused, controlled manner.",
        ],
        "buff": [
            f"Infuse yourself or an ally with empowering {element} energy.",
            f"Enhance capabilities through {element} magic.",
            f"Bestow a blessing of {element} upon your target.",
        ],
        "debuff": [
            f"Afflict your enemy with weakening {element} magic.",
            f"Curse your foe with the power of {element}.",
            f"Sap your target's strength using {element} energy.",
        ],
    }

    base = random.choice(templates.get(archetype, templates["offensive"]))

    # Add stat hint
    if stats["damage"]:
        base += f" Deals {stats['damage']} damage."

    if stats["mana_cost"] > 0:
        base += f" Costs {stats['mana_cost']} mana."

    return base


# ======================== Mob Generator Logic ========================

def _generate_fallback_items(tags: list, tier: str) -> list:
    """Generate basic weapons when the item library has nothing suitable."""
    tier_info = TIER_DICE.get(tier, DEFAULT_TIER_DICE)
    valid_dice = [d for d in [4, 6, 8, 10, 12, 20]
                  if tier_info["min"] <= d <= tier_info["max"]]
    items = []

    if "Melee" in tags or (not tags):
        ds = random.choice(valid_dice)
        dc = random.randint(*tier_info["count_range"])
        bonus = random.randint(0, dc)
        dmg = f"{dc}d{ds}" + (f"+{bonus}" if bonus else "")
        items.append(ensure_item_obj({
            "name": f"Basic {random.choice(['Sword', 'Axe', 'Mace', 'Spear', 'Hammer', 'Glaive'])}",
            "roll_type": "Attack", "damage": dmg,
            "is_ranged": False, "apply_bonus": True,
        }))

    if "Ranged" in tags:
        ds = random.choice(valid_dice)
        dc = random.randint(*tier_info["count_range"])
        bonus = random.randint(0, dc)
        dmg = f"{dc}d{ds}" + (f"+{bonus}" if bonus else "")
        items.append(ensure_item_obj({
            "name": f"Basic {random.choice(['Bow', 'Crossbow', 'Sling', 'Javelin', 'Throwing Knife'])}",
            "roll_type": "Attack", "damage": dmg,
            "is_ranged": True, "apply_bonus": True,
        }))

    if not items:
        items.append(ensure_item_obj({
            "name": "Improvised Weapon", "roll_type": "Attack",
            "damage": "1d4", "is_ranged": False, "apply_bonus": True,
        }))
    return items


def _select_mob_items(tags: list, tier: str) -> list:
    """Select 2-4 appropriate items from the item library based on tags."""
    all_items = get_library_items()
    candidates = []
    for entry in all_items:
        item = entry.get("item", {})
        item_obj = ensure_item_obj(item)
        score = 0
        for tag in tags:
            if tag == "Melee" and not item_obj.get("is_ranged") and item_obj.get("roll_type") in ("Attack", "None"):
                score += 2
            elif tag == "Ranged" and item_obj.get("is_ranged"):
                score += 2
            elif tag == "Magic":
                score += 1
            elif tag == "Support" and (item_obj.get("consumable") or item_obj.get("roll_type") == "None"):
                score += 1
        if not tags:
            score = 1
        if score > 0:
            candidates.append((score, item_obj))

    candidates.sort(key=lambda x: (-x[0], random.random()))
    count = min(random.randint(2, 4), len(candidates))
    selected = [item for _, item in candidates[:count]]

    if not selected:
        selected = _generate_fallback_items(tags, tier)
    return selected


def _generate_fallback_spells(tags: list, tier: str, count: int) -> list:
    """Generate basic spells using the existing spell generation system."""
    spells = []
    has_magic = "Magic" in tags
    for i in range(count):
        if has_magic:
            archetype = random.choice(["offensive", "offensive", "debuff", "defensive", "buff"])
        else:
            archetype = random.choice(["utility", "buff", "defensive"])
        element = random.choice(list(SPELL_ELEMENTS.keys()))
        category = ["core", "inner", "outer"][i % 3]
        name = generate_spell_name(element, archetype)
        stats = calculate_spell_stats(archetype, tier, category, 0)
        description = generate_spell_description(name, element, archetype, stats)
        spell = {
            "name": name, "favorite": False,
            "roll_type": stats["roll_type"], "damage": stats["damage"],
            "mana_cost": stats["mana_cost"], "notes": description,
            "overcast": stats["overcast"], "stat_boosts": [], "buff_turns": 0,
        }
        spells.append(ensure_ability_obj(spell))
    return spells


def _select_mob_spells(tags: list, tier: str) -> dict:
    """Select and distribute spells across ability slots based on tags."""
    has_magic = "Magic" in tags
    has_support = "Support" in tags

    if has_magic:
        spell_count = random.randint(3, 5)
    elif has_support:
        spell_count = random.randint(2, 3)
    else:
        spell_count = random.randint(0, 1)

    if spell_count == 0:
        return {"core": [], "inner": [], "outer": []}

    all_spells = get_library_spells()
    candidates = []
    for entry in all_spells:
        spell = entry.get("spell", {})
        metadata = entry.get("metadata", {})
        spell_tier = metadata.get("tier", "T1")
        archetype = metadata.get("archetype", "unknown")
        score = 0
        if spell_tier == tier:
            score += 2
        if has_magic and archetype in ("offensive", "debuff", "unknown"):
            score += 2
        if has_support and archetype in ("defensive", "buff", "healing", "unknown"):
            score += 2
        if not has_magic and not has_support and archetype in ("utility", "unknown"):
            score += 1
        if score > 0:
            candidates.append((score, ensure_ability_obj(spell)))

    candidates.sort(key=lambda x: (-x[0], random.random()))
    actual_count = min(spell_count, len(candidates))
    selected = [spell for _, spell in candidates[:actual_count]]

    if not selected and spell_count > 0:
        selected = _generate_fallback_spells(tags, tier, spell_count)

    result = {"core": [], "inner": [], "outer": []}
    slots = ["core", "inner", "outer"]
    for i, spell in enumerate(selected):
        result[slots[i % 3]].append(spell)
    return result


def generate_mob_character(name: str, tier: str, position: str,
                           power_level: str, tags: list,
                           creature_type: str = "Monster") -> dict:
    """Generate a complete character dict for a mob/NPC.

    creature_type: "Monster" (2x human stats) or "NPC" (human-level stats).
    Returns a dict matching default_character_template() schema.
    """
    if not name.strip():
        name = random.choice(MOB_NAME_PREFIXES) + " " + random.choice(MOB_NAME_BASES)

    # Pick stat tables based on creature type
    if creature_type == "NPC":
        stat_ranges = NPC_STAT_RANGES
        hp_ranges = NPC_HP_RANGES
        mana_ranges = NPC_MANA_RANGES
    else:
        stat_ranges = MOB_STAT_RANGES
        hp_ranges = MOB_HP_RANGES
        mana_ranges = MOB_MANA_RANGES

    # Base stat calculation
    stat_lo, stat_hi = stat_ranges.get(tier, (5, 15))
    pos_lo, pos_hi = MOB_POSITION_RANGES.get(position, (0.35, 0.55))
    power_mult = MOB_POWER_MULTIPLIERS.get(power_level, 1.0)
    pos_factor = random.uniform(pos_lo, pos_hi)
    base_stat = stat_lo + (stat_hi - stat_lo) * pos_factor
    base_stat *= power_mult

    # Merge tag weights
    if not tags:
        merged_weights = {k: 1.0 for k in STAT_KEYS}
        mana_pool_mult = 1.0
    else:
        merged_weights = {}
        for k in STAT_KEYS:
            total = sum(MOB_TAG_WEIGHTS.get(tag, {}).get(k, 1.0) for tag in tags)
            merged_weights[k] = total / len(tags)
        mana_pool_mult = sum(
            MOB_TAG_WEIGHTS.get(tag, {}).get("mana_pool_mult", 1.0) for tag in tags
        ) / len(tags)

    # Generate per-stat values
    stats = {}
    for k in STAT_KEYS:
        val = base_stat * merged_weights[k]
        val *= random.uniform(0.9, 1.1)
        stats[k] = max(0, int(round(val)))

    # Generate HP and Mana
    hp_lo, hp_hi = hp_ranges.get(tier, (20, 100))
    mana_lo, mana_hi = mana_ranges.get(tier, (10, 50))
    hp_max = max(1, int(round(
        (hp_lo + (hp_hi - hp_lo) * pos_factor) * power_mult * random.uniform(0.9, 1.1)
    )))
    mana_max = max(1, int(round(
        (mana_lo + (mana_hi - mana_lo) * pos_factor) * power_mult * mana_pool_mult * random.uniform(0.9, 1.1)
    )))

    # Select items and spells from libraries (with fallbacks)
    equipment = _select_mob_items(tags, tier)
    abilities = _select_mob_spells(tags, tier)

    # Assemble character
    char = default_character_template(name)
    char["tier"] = tier
    char["resources"]["hp"] = {"current": hp_max, "max": hp_max}
    char["resources"]["mana"] = {"current": mana_max, "max": mana_max}
    char["stats"] = stats
    char["inventory"]["equipment"] = equipment
    char["abilities"] = abilities
    tag_str = ", ".join(tags) if tags else "none"
    char["notes"] = f"Generated {creature_type}: {power_level} {position} {tier}, tags: {tag_str}"
    return char


def generate_spell_options(prompt_data: dict, category: str, tier: str,
                          mana_density: int, char_stats: dict, original_prompt: str = "") -> list:
    """
    Generate 5 varied spell options using Ollama AI (with template fallback).

    Args:
        prompt_data: from parse_research_prompt()
        category: "core", "inner", or "outer"
        tier: "T1", "T2", etc.
        mana_density: character's mana density value
        char_stats: character's stats dict (for future enhancements)
        original_prompt: the original user prompt for Ollama

    Returns:
        List of 5 spell dicts ready to pass to ensure_ability_obj()
    """
    # Try Ollama first if available
    if OLLAMA_AVAILABLE and original_prompt:
        try:
            return generate_spell_options_with_ollama(
                original_prompt, prompt_data, category, tier, mana_density, char_stats
            )
        except Exception as e:
            print(f"Ollama generation failed, using template fallback: {e}")

    # Template-based fallback
    elements = prompt_data["elements"]
    archetypes = prompt_data["archetypes"]

    spells = []

    # Strategy: ensure variety
    # Expand archetype pool to ensure variety
    all_archetypes = list(SPELL_ARCHETYPES.keys())
    archetype_pool = archetypes.copy()

    # Add some random archetypes for variety
    while len(archetype_pool) < 5:
        extra = random.choice(all_archetypes)
        if extra not in archetype_pool:
            archetype_pool.append(extra)

    # Generate 5 spells
    for i in range(5):
        # Pick element and archetype
        element = random.choice(elements)
        archetype = archetype_pool[i % len(archetype_pool)]

        # Generate name
        name = generate_spell_name(element, archetype)

        # Calculate stats
        stats = calculate_spell_stats(archetype, tier, category, mana_density)

        # Generate description
        description = generate_spell_description(name, element, archetype, stats)

        # Build spell dict
        spell = {
            "name": name,
            "favorite": False,
            "roll_type": stats["roll_type"],
            "damage": stats["damage"],
            "mana_cost": stats["mana_cost"],
            "notes": description,
            "overcast": stats["overcast"],
        }

        spells.append(spell)

    return spells


def generate_spell_options_with_ollama(prompt: str, prompt_data: dict, category: str,
                                       tier: str, mana_density: int, char_stats: dict) -> list:
    """
    Generate 5 spell options using Ollama LLM (gemma3:4b).
    Calls Ollama once per spell for reliable single-object JSON output.

    Returns list of spell dicts or raises exception if Ollama fails.
    """
    elements = ', '.join(prompt_data.get('elements', ['arcane']))

    # 5 different creative directions for variety
    spell_styles = [
        f"Create an offensive attack spell. {prompt}",
        f"Create a defensive or utility spell. {prompt}",
        f"Create a powerful area-of-effect spell. {prompt}",
        f"Create a unique or unusual spell. {prompt}",
        f"Create a versatile combat spell. {prompt}",
    ]

    spells = []
    for i, style in enumerate(spell_styles):
        try:
            spell_prompt = f"""Create one magic spell as a JSON object.

Request: {style}
Elements: {elements}
Tier: {tier}

Return ONE JSON object like this example:
{{"name": "Arcane Blast", "roll_type": "Attack", "damage": "2d6", "mana_cost": 8, "notes": "Fire magical energy at target", "overcast_enabled": false}}

roll_type must be "Attack", "Save", or "None".
damage should use dice notation like "2d6" or "3d8+1". Use "" for no damage.
mana_cost should be a number between 1 and 30."""

            response = ollama.generate(
                model='gemma3:4b',
                prompt=spell_prompt,
                format='json',
                options={'temperature': 0.8}
            )

            response_text = response.get('response', '').strip()
            if not response_text:
                raise Exception("Empty response")

            spell_data = json.loads(response_text)

            # If we got a wrapped dict, extract it
            if isinstance(spell_data, dict) and 'name' not in spell_data:
                for key in spell_data:
                    val = spell_data[key]
                    if isinstance(val, dict) and 'name' in val:
                        spell_data = val
                        break
                    elif isinstance(val, list) and len(val) > 0:
                        spell_data = val[0]
                        break

            # Validate and build spell
            name = spell_data.get('name', f"Unnamed Spell {i+1}")
            damage = spell_data.get('damage', "1d6") or "1d6"
            mana_cost = spell_data.get('mana_cost', 5)
            try:
                mana_cost = int(mana_cost)
            except (ValueError, TypeError):
                mana_cost = 5
            roll_type = spell_data.get('roll_type', "Attack")
            notes = spell_data.get('notes', "A magical spell.")

            overcast_enabled = spell_data.get("overcast_enabled", False)
            overcast = {
                "enabled": overcast_enabled,
                "scale": 3 if overcast_enabled else 0,
                "power": 0.85,
                "cap": 999
            }

            spells.append({
                "name": str(name),
                "favorite": False,
                "roll_type": str(roll_type),
                "damage": str(damage),
                "mana_cost": mana_cost,
                "notes": str(notes),
                "overcast": overcast,
            })
        except Exception as e:
            print(f"Warning: Spell {i+1} generation failed: {e}. Using template fallback for this spell.")
            spells.append({
                "name": f"Arcane Spell {i+1}",
                "favorite": False,
                "roll_type": "Attack",
                "damage": "1d6",
                "mana_cost": 5,
                "notes": "A basic magical spell.",
                "overcast": {"enabled": False, "scale": 0, "power": 0.85, "cap": 999},
            })

    return spells[:5]


# ---------------- Spell Library Functions ----------------

LIBRARY_PATH = Path("spell_library.json")


def load_spell_library() -> dict:
    """
    Load spell library from spell_library.json.
    Returns {"spells": [...]} structure.
    """
    if not LIBRARY_PATH.exists():
        return {"spells": []}

    try:
        with open(LIBRARY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and "spells" in data:
                return data
            return {"spells": []}
    except Exception:
        return {"spells": []}


def save_spell_library(library: dict) -> None:
    """
    Save spell library to spell_library.json.
    """
    try:
        with open(LIBRARY_PATH, 'w', encoding='utf-8') as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def add_spell_to_library(spell: dict, metadata: dict) -> str:
    """
    Add spell to library with metadata.
    Returns unique spell ID.
    """
    library = load_spell_library()

    # Generate unique ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = ''.join(random.choices('0123456789abcdef', k=6))
    spell_id = f"{timestamp}_{random_suffix}"

    entry = {
        "id": spell_id,
        "spell": spell.copy(),
        "metadata": metadata.copy()
    }

    library["spells"].append(entry)
    save_spell_library(library)

    return spell_id


def get_library_spells(filters: dict = None) -> list:
    """
    Get spells from library, optionally filtered.
    """
    library = load_spell_library()
    spells = library.get("spells", [])

    if not filters:
        return spells

    filtered = []
    for entry in spells:
        metadata = entry.get("metadata", {})
        match = True

        for key, value in filters.items():
            if metadata.get(key) != value:
                match = False
                break

        if match:
            filtered.append(entry)

    return filtered


def remove_from_library(spell_id: str) -> bool:
    """
    Remove spell from library by ID.
    Returns True if removed, False if not found.
    """
    library = load_spell_library()
    spells = library.get("spells", [])

    for i, entry in enumerate(spells):
        if entry.get("id") == spell_id:
            spells.pop(i)
            library["spells"] = spells
            save_spell_library(library)
            return True

    return False


def import_spell_from_library(spell_id: str) -> dict:
    """
    Get spell dict from library by ID (without metadata).
    Returns None if not found.
    """
    library = load_spell_library()

    for entry in library.get("spells", []):
        if entry.get("id") == spell_id:
            return entry.get("spell", {}).copy()

    return None


# ---------------- Item Library ----------------

ITEM_LIBRARY_PATH = Path("item_library.json")


def load_item_library() -> dict:
    if not ITEM_LIBRARY_PATH.exists():
        return {"items": []}
    try:
        with open(ITEM_LIBRARY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and "items" in data:
                return data
            return {"items": []}
    except Exception:
        return {"items": []}


def save_item_library(library: dict) -> None:
    try:
        with open(ITEM_LIBRARY_PATH, 'w', encoding='utf-8') as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def add_item_to_library(item: dict, metadata: dict) -> str:
    library = load_item_library()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = ''.join(random.choices('0123456789abcdef', k=6))
    item_id = f"{timestamp}_{random_suffix}"
    entry = {
        "id": item_id,
        "item": item.copy(),
        "metadata": metadata.copy(),
    }
    library["items"].append(entry)
    save_item_library(library)
    return item_id


def get_library_items(filters: dict = None) -> list:
    library = load_item_library()
    items = library.get("items", [])
    if not filters:
        return items
    filtered = []
    for entry in items:
        metadata = entry.get("metadata", {})
        if all(metadata.get(k) == v for k, v in filters.items()):
            filtered.append(entry)
    return filtered


def remove_item_from_library(item_id: str) -> bool:
    library = load_item_library()
    items = library.get("items", [])
    for i, entry in enumerate(items):
        if entry.get("id") == item_id:
            items.pop(i)
            library["items"] = items
            save_item_library(library)
            return True
    return False


def import_item_from_library(item_id: str) -> dict:
    library = load_item_library()
    for entry in library.get("items", []):
        if entry.get("id") == item_id:
            return entry.get("item", {}).copy()
    return None


# ---------------- Spell Upgrade Functions ----------------

def parse_damage_expr(expr: str) -> tuple:
    """
    Parse dice expression like "2d6+3" into (count, size, bonus).
    Returns (0, 0, 0) if invalid.
    """
    expr = expr.strip()
    if not expr:
        return (0, 0, 0)

    # Pattern: XdY or XdY+Z or XdY-Z
    match = re.match(r'(\d+)d(\d+)([+-]\d+)?', expr)
    if not match:
        return (0, 0, 0)

    count = int(match.group(1))
    size = int(match.group(2))
    bonus = int(match.group(3)) if match.group(3) else 0

    return (count, size, bonus)


def build_damage_expr(count: int, size: int, bonus: int) -> str:
    """
    Build dice expression from components.
    """
    expr = f"{count}d{size}"
    if bonus > 0:
        expr += f"+{bonus}"
    elif bonus < 0:
        expr += str(bonus)
    return expr


def generate_spell_upgrades_with_ollama(base_spell: dict, category: str, tier: str, training_prompt: str = "") -> list:
    """
    Generate 5 spell upgrade options using Ollama LLM (gemma3:4b).
    Calls Ollama once per upgrade for reliable single-object JSON output.

    Returns list of 5 upgraded spell dicts or raises exception if Ollama fails.
    """
    # Extract current spell details
    name = base_spell.get("name", "Unknown Spell")
    damage = base_spell.get("damage", "1d6")
    mana_cost = base_spell.get("mana_cost", 1)
    roll_type = base_spell.get("roll_type", "None")
    notes = base_spell.get("notes", "")
    overcast = base_spell.get("overcast", {})

    training_context = f" The caster trained by: {training_prompt}." if training_prompt else ""

    # Define 5 different upgrade focuses
    upgrade_focuses = [
        f"Increase the damage of the spell significantly. Make it hit harder.{training_context}",
        f"Reduce the mana cost to make it more efficient.{training_context}",
        f"Add a unique twist or secondary effect. Be creative with the upgrade.{training_context}",
        f"Balance both damage and mana cost improvements.{training_context}",
        f"Create a powerful but expensive version with a new name.{training_context}",
    ]

    upgrades = []
    for i, focus in enumerate(upgrade_focuses):
        try:
            prompt = f"""Create one upgraded version of this spell as a JSON object.

Original: {name} | Damage: {damage} | Mana: {mana_cost} | Type: {roll_type} | Notes: {notes}

Upgrade focus: {focus}

Return ONE JSON object like this example:
{{"name": "Improved {name}", "roll_type": "{roll_type}", "damage": "2d8", "mana_cost": {mana_cost}, "notes": "A stronger version", "overcast_enabled": false}}"""

            response = ollama.generate(
                model='gemma3:4b',
                prompt=prompt,
                format='json',
                options={'temperature': 0.8}
            )

            response_text = response.get('response', '').strip()
            if not response_text:
                raise Exception("Empty response")

            upgrade_data = json.loads(response_text)

            # If we got a wrapped dict, extract it
            if isinstance(upgrade_data, dict) and 'name' not in upgrade_data:
                for key in upgrade_data:
                    val = upgrade_data[key]
                    if isinstance(val, dict) and 'name' in val:
                        upgrade_data = val
                        break
                    elif isinstance(val, list) and len(val) > 0:
                        upgrade_data = val[0]
                        break

            # Validate and build upgrade
            upgrade_name = upgrade_data.get('name', f"Upgraded {name} {i+1}")
            upgrade_damage = upgrade_data.get('damage', damage) or damage
            upgrade_mana = upgrade_data.get('mana_cost', mana_cost)
            try:
                upgrade_mana = int(upgrade_mana)
            except (ValueError, TypeError):
                upgrade_mana = mana_cost
            upgrade_roll_type = upgrade_data.get('roll_type', roll_type)
            upgrade_notes = upgrade_data.get('notes', notes)

            # Build overcast
            overcast_enabled = upgrade_data.get("overcast_enabled", False)
            new_overcast = overcast.copy() if isinstance(overcast, dict) else {}
            if overcast_enabled and not new_overcast.get("enabled"):
                new_overcast["enabled"] = True
                new_overcast["scale"] = 3
                new_overcast["power"] = 0.85
                new_overcast["cap"] = 999
            elif overcast_enabled and new_overcast.get("enabled"):
                new_overcast["scale"] = new_overcast.get("scale", 3) + 1

            upgrades.append({
                "name": str(upgrade_name),
                "favorite": False,
                "roll_type": str(upgrade_roll_type),
                "damage": str(upgrade_damage),
                "mana_cost": upgrade_mana,
                "notes": str(upgrade_notes),
                "overcast": new_overcast,
            })
        except Exception as e:
            print(f"Warning: Upgrade {i+1} generation failed: {e}. Using template fallback for this upgrade.")
            upgrades.append({
                "name": f"Improved {name} {i+1}",
                "favorite": False,
                "roll_type": roll_type,
                "damage": damage if damage else "1d6",
                "mana_cost": max(1, int(mana_cost * 0.9)),
                "notes": notes + " [Minor upgrade]",
                "overcast": overcast.copy() if isinstance(overcast, dict) else {},
            })

    return upgrades[:5]


def generate_spell_upgrades(base_spell: dict, category: str, tier: str, training_prompt: str = "") -> list:
    """
    Generate 5 upgrade options for a spell using Ollama AI (with template fallback).

    Returns list of 5 upgraded spell dicts.
    """
    # Try Ollama first if available
    if OLLAMA_AVAILABLE:
        try:
            return generate_spell_upgrades_with_ollama(base_spell, category, tier, training_prompt)
        except Exception as e:
            print(f"Ollama upgrade generation failed, using template fallback: {e}")

    # Template-based fallback
    upgrades = []

    # Parse current spell stats
    name = base_spell.get("name", "Unknown Spell")
    damage = base_spell.get("damage", "")
    mana_cost = base_spell.get("mana_cost", 1)
    roll_type = base_spell.get("roll_type", "None")
    notes = base_spell.get("notes", "")
    overcast = base_spell.get("overcast", {}).copy()

    count, size, bonus = parse_damage_expr(damage)

    # Upgrade 1: Damage Boost - Increase dice count or size
    up1 = base_spell.copy()
    up1["name"] = f"Enhanced {name}"
    if count > 0 and size > 0:
        # Increase dice count by 1, or upgrade dice size
        if random.random() < 0.5 and count < 5:
            new_count = count + 1
            new_size = size
        else:
            new_count = count
            # Upgrade dice size: d4->d6, d6->d8, d8->d10, d10->d12, d12->d20
            size_progression = {4: 6, 6: 8, 8: 10, 10: 12, 12: 20, 20: 20}
            new_size = size_progression.get(size, size)
        up1["damage"] = build_damage_expr(new_count, new_size, bonus)
    up1["notes"] = notes + " [Upgraded: Increased damage]"
    up1["overcast"] = overcast.copy()
    upgrades.append(up1)

    # Upgrade 2: Efficiency - Reduce mana cost
    up2 = base_spell.copy()
    up2["name"] = f"Efficient {name}"
    reduction = random.uniform(0.15, 0.25)
    up2["mana_cost"] = max(1, int(mana_cost * (1 - reduction)))
    up2["damage"] = damage
    up2["notes"] = notes + " [Upgraded: Reduced mana cost]"
    up2["overcast"] = overcast.copy()
    upgrades.append(up2)

    # Upgrade 3: Overcast Enhancement
    up3 = base_spell.copy()
    up3["name"] = f"Empowered {name}"
    up3["damage"] = damage
    up3["mana_cost"] = mana_cost
    up3_overcast = overcast.copy()
    if not up3_overcast.get("enabled", False):
        # Enable overcast
        up3_overcast["enabled"] = True
        up3_overcast["scale"] = random.randint(2, 4)
        up3_overcast["power"] = 0.85
        up3_overcast["cap"] = 999
        up3["notes"] = notes + " [Upgraded: Overcast enabled]"
    else:
        # Enhance existing overcast
        up3_overcast["scale"] = up3_overcast.get("scale", 0) + random.randint(1, 2)
        up3["notes"] = notes + " [Upgraded: Enhanced overcast scaling]"
    up3["overcast"] = up3_overcast
    upgrades.append(up3)

    # Upgrade 4: Balanced - Small improvements to both
    up4 = base_spell.copy()
    up4["name"] = f"Improved {name}"
    if count > 0 and size > 0:
        # Small damage increase (add +1 to bonus or increase count slightly)
        new_bonus = bonus + 1
        up4["damage"] = build_damage_expr(count, size, new_bonus)
    else:
        up4["damage"] = damage
    up4["mana_cost"] = max(1, int(mana_cost * 0.9))
    up4["notes"] = notes + " [Upgraded: Balanced improvements]"
    up4["overcast"] = overcast.copy()
    upgrades.append(up4)

    # Upgrade 5: Power Spike - Big damage, slight mana increase
    up5 = base_spell.copy()
    up5["name"] = f"Superior {name}"
    if count > 0 and size > 0:
        # Increase both dice count and size or add significant bonus
        if count < 4:
            new_count = count + 1
            new_bonus = bonus + 2
        else:
            new_count = count
            new_bonus = bonus + 3
        size_progression = {4: 6, 6: 8, 8: 10, 10: 12, 12: 20, 20: 20}
        new_size = size_progression.get(size, size)
        up5["damage"] = build_damage_expr(new_count, new_size, new_bonus)
    else:
        up5["damage"] = damage
    up5["mana_cost"] = int(mana_cost * 1.1)
    up5["notes"] = notes + " [Upgraded: Major power increase]"
    up5["overcast"] = overcast.copy()
    upgrades.append(up5)

    return upgrades


# ---------------- App ----------------

class CharacterSheet(ttk.Frame):
    def __init__(self, parent, char_path: Path, is_dm: bool = False):
        super().__init__(parent)

        self.is_dm = is_dm
        self.char_path = char_path

        self.char = load_character(self.char_path)
        _migrate_stats_schema(self.char)

        # ----- Vars -----
        self.var_name = tk.StringVar()
        self.var_tier = tk.StringVar()

        self.var_hp_current = tk.StringVar()
        self.var_hp_max = tk.StringVar()
        self.var_mana_current = tk.StringVar()
        self.var_mana_max = tk.StringVar()
        self.var_mana_density_mult = tk.StringVar()  # display-only label for MD multiplier
        self.var_unspent = tk.StringVar()

        self.var_hp_dmg = tk.StringVar()
        self.var_hp_heal = tk.StringVar()

        # NEW: incoming hit reduced by Physical Defense + glancing blow
        self.var_hit_incoming = tk.StringVar()
        self.var_hit_attacker_accuracy = tk.StringVar()
        self.var_hit_result = tk.StringVar(value="")

        self.var_core_current = tk.StringVar()
        self.var_core_max = tk.StringVar()
        self.var_inner_current = tk.StringVar()
        self.var_inner_max = tk.StringVar()
        self.var_outer_current = tk.StringVar()
        self.var_outer_max = tk.StringVar()

        self.var_stats = {k: tk.StringVar() for k in STAT_KEYS}
        self.var_equip_bonus = {k: tk.StringVar() for k in STAT_KEYS}  # display equipment boost text
        self.var_equip_bonus_res = {"hp_max": tk.StringVar(), "mana_max": tk.StringVar()}

        self.var_growth_current = tk.StringVar()
        self.var_growth_max = tk.StringVar()

        self.var_show_used = tk.BooleanVar()

        # Mana Stone currency (T1 through T15)
        self.MAX_MANA_STONE_TIER = 15
        self.var_mana_stones = {t: tk.StringVar(value="0") for t in range(1, 16)}

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

        # Stat boost editor vars (per inventory category)
        self.inv_boost_stat = {k: tk.StringVar(value=STAT_KEYS[0]) for k in self.inv_keys}
        self.inv_boost_value = {k: tk.StringVar(value="0") for k in self.inv_keys}
        self.inv_boost_mode = {k: tk.StringVar(value="flat") for k in self.inv_keys}
        self.inv_boost_data = {k: [] for k in self.inv_keys}  # mirrors selected item's stat_boosts

        # Consumable editor vars (per inventory category)
        self.inv_consumable = {k: tk.BooleanVar(value=False) for k in self.inv_keys}
        self.inv_consume_heal_hp = {k: tk.StringVar(value="0") for k in self.inv_keys}
        self.inv_consume_heal_mana = {k: tk.StringVar(value="0") for k in self.inv_keys}
        self.inv_consume_turns = {k: tk.StringVar(value="0") for k in self.inv_keys}
        self.inv_consume_perm_stat = {k: tk.StringVar(value="") for k in self.inv_keys}
        self.inv_consume_perm_value = {k: tk.StringVar(value="0") for k in self.inv_keys}

        # Growth item flag (per inventory category)
        self.inv_is_growth_item = {k: tk.BooleanVar(value=False) for k in self.inv_keys}

        # Weight (per inventory category)
        self.inv_weight = {k: tk.StringVar(value="0") for k in self.inv_keys}
        self.var_carry_display = tk.StringVar(value="")
        self.var_currency_display = tk.StringVar(value="")

        # Armor slot assignment (per inventory category)
        self.inv_armor_slot = {k: tk.StringVar(value="(none)") for k in self.inv_keys}

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

        # Ability stat boost editor vars
        self.ability_boost_stat = {k: tk.StringVar(value=BOOST_TARGETS[0]) for k in self.ability_keys}
        self.ability_boost_value = {k: tk.StringVar(value="0") for k in self.ability_keys}
        self.ability_boost_mode = {k: tk.StringVar(value="flat") for k in self.ability_keys}
        self.ability_boost_data = {k: [] for k in self.ability_keys}
        self.ability_buff_turns = {k: tk.StringVar(value="0") for k in self.ability_keys}

        # Combat (Overview quick use)
        self.combat_actions = []  # list of dicts {kind, ref, display, slot?}
        self.combat_selected_ref = None
        self.combat_selected_kind = None

        self.var_combat_roll_type = tk.StringVar(value="")
        self.var_combat_damage_expr = tk.StringVar(value="")
        self.var_combat_hit_roll = tk.StringVar()
        self.var_combat_roll_value = tk.StringVar()
        self.var_combat_mana_spend = tk.StringVar()
        self.var_combat_enemy_evasion = tk.StringVar()
        self.var_combat_result = tk.StringVar(value="")

        # Active consumable buffs (runtime only, not saved)
        self.active_buffs = []  # [{name, stat_boosts, turns_remaining}]

        # Track raw tk widgets that need manual theme styling
        self._tk_widgets = []  # list of tk.Text / tk.Listbox / tk.Canvas

        self._build_ui()
        self.refresh_from_model()

        # Normalize current UI -> model once, then snapshot as "last saved"
        # (prevents "prompt to save" immediately after opening due to sorting/canonicalization)
        self.apply_to_model()
        self._last_saved_state = self._serialize_char(self.char)

        # Update tab label when name changes
        self.var_name.trace_add("write", self._on_name_changed)


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
        self.tab_battle_sim = ttk.Frame(self.tabs)
        self.tab_settings = ttk.Frame(self.tabs)
        self.tab_spell_library = ttk.Frame(self.tabs)
        self.tab_item_library = ttk.Frame(self.tabs)
        self.tab_mob_generator = ttk.Frame(self.tabs)

        self.tabs.add(self.tab_overview, text="Overview")
        self.tabs.add(self.tab_inventory, text="Inventory")
        self.tabs.add(self.tab_abilities, text="Abilities")
        self.tabs.add(self.tab_notes, text="Notes")
        self.tabs.add(self.tab_world, text="World Info")
        self.tabs.add(self.tab_damage_lab, text="Damage Lab")
        self.tabs.add(self.tab_battle_sim, text="Battle Sim")
        self.tabs.add(self.tab_settings, text="Settings")
        if self.is_dm:
            self.tabs.add(self.tab_spell_library, text="Spell Library (DM)")
            self.tabs.add(self.tab_item_library, text="Item Library (DM)")
            self.tabs.add(self.tab_mob_generator, text="Mob Generator (DM)")

        self._build_overview_tab()
        self._build_inventory_tab()
        self._build_abilities_tab()
        self._build_notes_tab()
        self._build_world_tab()
        self._build_damage_lab_tab()
        self._build_battle_sim_tab()
        self._build_settings_tab()
        self._build_spell_library_tab()
        self._build_item_library_tab()
        self._build_mob_generator_tab()

    def _make_scrollable_frame(self, parent):
        """Create a vertically scrollable frame inside *parent*.

        Returns the inner ttk.Frame that should be used as the parent for
        child widgets.  The canvas + scrollbar handle resizing and mousewheel
        scrolling automatically.
        """
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind(
            "<Configure>",
            lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all"))
        )
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_canvas_configure(event, c=canvas, w=win_id):
            c.itemconfig(w, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event, c=canvas):
            c.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mw(event, c=canvas):
            c.bind_all("<MouseWheel>", lambda e, c2=c: c2.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        def _unbind_mw(event, c=canvas):
            c.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_mw)
        canvas.bind("<Leave>", _unbind_mw)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._tk_widgets.append(canvas)

        return inner

    def _build_overview_tab(self):
        # Scrollable wrapper for the overview tab
        overview_canvas = tk.Canvas(self.tab_overview, highlightthickness=0)
        overview_scrollbar = ttk.Scrollbar(self.tab_overview, orient="vertical", command=overview_canvas.yview)
        overview_inner = ttk.Frame(overview_canvas)

        overview_inner.bind(
            "<Configure>",
            lambda e: overview_canvas.configure(scrollregion=overview_canvas.bbox("all"))
        )
        self._overview_canvas_window = overview_canvas.create_window((0, 0), window=overview_inner, anchor="nw")
        overview_canvas.configure(yscrollcommand=overview_scrollbar.set)

        # Resize inner frame width to match canvas
        def _on_overview_canvas_configure(event):
            overview_canvas.itemconfig(self._overview_canvas_window, width=event.width)
        overview_canvas.bind("<Configure>", _on_overview_canvas_configure)

        # Mousewheel scrolling
        def _on_mousewheel(event):
            overview_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(event):
            overview_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            overview_canvas.unbind_all("<MouseWheel>")

        overview_canvas.bind("<Enter>", _bind_mousewheel)
        overview_canvas.bind("<Leave>", _unbind_mousewheel)

        overview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        overview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._tk_widgets.append(overview_canvas)

        left = ttk.Frame(overview_inner)
        right = ttk.Frame(overview_inner)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=8)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)

        # Stats
        stats_frame = ttk.LabelFrame(left, text="Stats")
        stats_frame.pack(fill=tk.X, pady=6)

        for row, (key, label) in enumerate(STAT_ORDER):
            ttk.Label(stats_frame, text=label + ":").grid(row=row, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(stats_frame, textvariable=self.var_stats[key], width=7).grid(row=row, column=1, sticky="w", padx=4, pady=2)
            if key == "mana_density":
                ttk.Label(stats_frame, textvariable=self.var_mana_density_mult, foreground="gray").grid(
                    row=row, column=2, sticky="w", padx=(4, 0), pady=2)
            ttk.Label(stats_frame, textvariable=self.var_equip_bonus[key],
                      foreground="gray").grid(row=row, column=3, sticky="w", padx=(4, 0), pady=2)

        # Currency summary
        currency_frame = ttk.LabelFrame(left, text="Currency")
        currency_frame.pack(fill=tk.X, pady=6)
        ttk.Label(currency_frame, textvariable=self.var_currency_display, wraplength=250,
                  justify="left").pack(padx=6, pady=6, anchor="w")

        # Resources
        res_frame = ttk.LabelFrame(left, text="Resources")
        res_frame.pack(fill=tk.X, pady=6)

        ttk.Label(res_frame, text="HP:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_hp_current, width=6).grid(row=0, column=1)
        ttk.Label(res_frame, text="/").grid(row=0, column=2)
        ttk.Entry(res_frame, textvariable=self.var_hp_max, width=6).grid(row=0, column=3)
        ttk.Label(res_frame, textvariable=self.var_equip_bonus_res["hp_max"],
                  foreground="gray").grid(row=0, column=4, sticky="w", padx=(4, 0), pady=3)

        ttk.Label(res_frame, text="Mana:").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_mana_current, width=6).grid(row=1, column=1)
        ttk.Label(res_frame, text="/").grid(row=1, column=2)
        ttk.Entry(res_frame, textvariable=self.var_mana_max, width=6).grid(row=1, column=3)
        ttk.Label(res_frame, textvariable=self.var_equip_bonus_res["mana_max"],
                  foreground="gray").grid(row=1, column=4, sticky="w", padx=(4, 0), pady=3)

        ttk.Label(res_frame, text="Heal:").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_hp_heal, width=8).grid(row=2, column=1, sticky="w")
        ttk.Button(res_frame, text="Apply", command=self.apply_hp_heal).grid(row=2, column=3, sticky="w", padx=4)

        # Incoming hit (Glancing Blow + Physical Defense DR)
        ttk.Separator(res_frame, orient="horizontal").grid(row=3, column=0, columnspan=4, sticky="ew", padx=4, pady=6)

        ttk.Label(res_frame, text="Attacker Accuracy:").grid(row=4, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_hit_attacker_accuracy, width=8).grid(row=4, column=1, sticky="w")

        ttk.Label(res_frame, text="Incoming hit:").grid(row=5, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_hit_incoming, width=8).grid(row=5, column=1, sticky="w")
        ttk.Button(res_frame, text="Apply (Glancing + DR)", command=self.apply_incoming_hit).grid(
            row=5, column=2, columnspan=2, sticky="ew", padx=4
        )
        ttk.Label(res_frame, textvariable=self.var_hit_result, foreground="gray").grid(
            row=6, column=0, columnspan=4, sticky="w", padx=4, pady=(2, 4)
        )

        ttk.Separator(res_frame, orient="horizontal").grid(row=7, column=0, columnspan=4, sticky="ew", padx=4, pady=6)

        ttk.Label(res_frame, text="Unspent pts:").grid(row=8, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(res_frame, textvariable=self.var_unspent, width=6).grid(row=8, column=1)

        ttk.Button(res_frame, text="Spend Points…", command=self.open_spend_points_popup).grid(
            row=9, column=0, columnspan=4, sticky="ew", padx=4, pady=(8, 4)
        )

        ttk.Button(res_frame, text="Long Rest (full HP/Mana)", command=self.apply_long_rest).grid(
            row=10, column=0, columnspan=4, sticky="ew", padx=4, pady=(6, 4)
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

        self.combat_list = tk.Listbox(c_left, height=14, exportselection=False)
        self.combat_list.pack(fill=tk.BOTH, expand=True)
        self.combat_list.bind("<<ListboxSelect>>", lambda _e: self.on_combat_select())
        self._tk_widgets.append(self.combat_list)

        ttk.Button(c_left, text="Refresh list", command=self.refresh_combat_list).pack(fill=tk.X, pady=(6, 0))

        ttk.Label(c_right, text="Roll type:").grid(row=0, column=0, sticky="w", padx=4, pady=(4, 2))
        ttk.Label(c_right, textvariable=self.var_combat_roll_type).grid(row=0, column=1, sticky="w", padx=4, pady=(4, 2))

        ttk.Label(c_right, text="Damage dice:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(c_right, textvariable=self.var_combat_damage_expr).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(c_right, text="Hit roll (d20):").grid(row=2, column=0, sticky="w", padx=4, pady=(10, 2))
        hit_row = ttk.Frame(c_right)
        hit_row.grid(row=2, column=1, sticky="w", padx=4, pady=(10, 2))
        ttk.Entry(hit_row, textvariable=self.var_combat_hit_roll, width=10).pack(side=tk.LEFT)
        ttk.Button(hit_row, text="Check Accuracy", command=self.check_accuracy).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(c_right, text="Enemy Evasion:").grid(row=3, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(c_right, textvariable=self.var_combat_enemy_evasion, width=10).grid(row=3, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(c_right, text="Enter rolled damage:").grid(row=4, column=0, sticky="w", padx=4, pady=(10, 2))
        ttk.Entry(c_right, textvariable=self.var_combat_roll_value, width=10).grid(row=4, column=1, sticky="w", padx=4, pady=(10, 2))

        ttk.Label(c_right, text="Mana to spend (abilities):").grid(row=5, column=0, sticky="w", padx=4, pady=2)
        self.combat_mana_entry = ttk.Entry(c_right, textvariable=self.var_combat_mana_spend, width=10)
        self.combat_mana_entry.grid(row=5, column=1, sticky="w", padx=4, pady=2)

        action_row = ttk.Frame(c_right)
        action_row.grid(row=6, column=0, columnspan=2, sticky="ew", padx=4, pady=(12, 6))
        ttk.Button(action_row, text="Use / Cast", command=self.use_combat_action).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(action_row, text="Consume", command=self.consume_combat_item).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

        ttk.Label(c_right, textvariable=self.var_combat_result, foreground="gray").grid(
            row=7, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 2)
        )

        # Active Buffs panel (shown only when consumable buffs with turns are active)
        buff_frame = ttk.LabelFrame(c_right, text="Active Buffs")
        buff_frame.grid(row=8, column=0, columnspan=2, sticky="ew", padx=4, pady=(6, 2))
        self._buff_frame = buff_frame

        self.active_buffs_list = tk.Listbox(buff_frame, height=4, exportselection=False)
        self.active_buffs_list.pack(fill=tk.X, padx=6, pady=(4, 2))
        self._tk_widgets.append(self.active_buffs_list)

        ttk.Button(buff_frame, text="Remove Buff", command=self._remove_active_buff).pack(
            anchor="w", padx=6, pady=(2, 6))

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
        d = {
            "name": it.get("name", ""),
            "favorite": bool(it.get("favorite", False)),
            "roll_type": it.get("roll_type", "None"),
            "damage": it.get("damage", ""),
            "notes": it.get("notes", ""),
            "apply_bonus": bool(it.get("apply_bonus", it.get("apply_pbd", True))),
            "is_ranged": bool(it.get("is_ranged", False)),
        }
        boosts = _normalize_stat_boosts(it.get("stat_boosts"))
        if boosts:
            d["stat_boosts"] = boosts
        if it.get("consumable"):
            d["consumable"] = True
            d["consume_heal_hp"] = _safe_int(it.get("consume_heal_hp"), 0)
            d["consume_heal_mana"] = _safe_int(it.get("consume_heal_mana"), 0)
            d["consume_turns"] = _safe_int(it.get("consume_turns"), 0)
            perm_stat = it.get("consume_perm_stat", "")
            perm_val = _safe_int(it.get("consume_perm_value"), 0)
            if perm_stat and perm_val:
                d["consume_perm_stat"] = perm_stat
                d["consume_perm_value"] = perm_val
        if it.get("is_growth_item"):
            d["is_growth_item"] = True
        w = float(it.get("weight", 0) or 0)
        if w:
            d["weight"] = w
        slot = it.get("armor_slot", "")
        if slot:
            d["armor_slot"] = slot
        return d

    def _clean_ability_for_json(self, ab: dict) -> dict:
        over = ab.get("overcast", {})
        if not isinstance(over, dict):
            over = {}
        d = {
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
        boosts = _normalize_stat_boosts(ab.get("stat_boosts"))
        if boosts:
            d["stat_boosts"] = boosts
        bt = _safe_int(ab.get("buff_turns"), 0)
        if bt > 0:
            d["buff_turns"] = bt
        return d

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

    def get_display_name(self) -> str:
        name = self.var_name.get().strip()
        return name if name else self.char_path.stem

    def is_dirty(self) -> bool:
        self.apply_to_model()
        current_state = self._serialize_char(self.char)
        return current_state != getattr(self, "_last_saved_state", "")

    def prompt_save_if_dirty(self) -> str:
        """
        If dirty, prompt user. Returns:
          'saved'       - user chose to save (and save succeeded)
          'discarded'   - user chose not to save
          'cancelled'   - user cancelled
          'clean'       - no unsaved changes
          'save_failed' - user chose to save but it failed
        """
        if not self.is_dirty():
            return "clean"

        char_name = self.get_display_name()
        choice = messagebox.askyesnocancel(
            "Unsaved Changes",
            f"'{char_name}' has unsaved changes.\n\nSave before closing?"
        )
        if choice is True:
            if self._save_to_disk(show_popup=False):
                return "saved"
            return "save_failed"
        elif choice is False:
            return "discarded"
        else:
            return "cancelled"

    def _on_name_changed(self, *args):
        app = self.winfo_toplevel()
        if hasattr(app, 'master_notebook') and hasattr(app, '_update_title'):
            try:
                app.master_notebook.tab(self, text=self.get_display_name())
                app._update_title()
            except Exception:
                pass
        elif hasattr(app, '_update_title'):
            try:
                app._update_title()
            except Exception:
                pass


    # ---------------- Theme ----------------

    def apply_theme(self, colors: dict):
        """Apply dark/light theme to all raw tk widgets in this sheet."""
        for w in self._tk_widgets:
            try:
                style_tk_widget(w, colors)
            except Exception:
                pass
        # Also theme the damage lab and battle sim
        if hasattr(self, "damage_lab"):
            self.damage_lab.apply_theme(colors)
        if hasattr(self, "battle_sim"):
            self.battle_sim.apply_theme(colors)
        # Re-color stat calculations markdown tags
        if hasattr(self, "stat_calc_text"):
            tw = self.stat_calc_text
            fg = colors["entry_fg"]
            code_bg = "#3c3c3c" if colors is DARK_COLORS else "#f0f0f0"
            accent = colors["accent"]
            tw.tag_configure("h1", foreground=accent)
            tw.tag_configure("h2", foreground=accent)
            tw.tag_configure("h3", foreground=accent)
            tw.tag_configure("body", foreground=fg)
            tw.tag_configure("bold", foreground=fg)
            tw.tag_configure("code_inline", foreground=fg, background=code_bg)
            tw.tag_configure("code_block", foreground=fg, background=code_bg)
            tw.tag_configure("table", foreground=fg)
            tw.tag_configure("bullet", foreground=fg)
        # Re-draw body map with new theme colors
        if hasattr(self, "body_canvas"):
            self._draw_body_model()
            self._refresh_body_map()

    def _get_current_colors(self):
        """Get the current theme colors from the app."""
        app = self.winfo_toplevel()
        if hasattr(app, "_current_colors"):
            return app._current_colors
        return LIGHT_COLORS

    # ---------------- Inventory ----------------

    def _build_inventory_tab(self):
        frame = ttk.Frame(self.tab_inventory)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top bar: Growth Items + Carry Capacity side by side
        top_bar = ttk.Frame(frame)
        top_bar.pack(fill=tk.X, pady=(0, 10))

        growth_frame = ttk.LabelFrame(top_bar, text="Growth Items Bound")
        growth_frame.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Entry(growth_frame, textvariable=self.var_growth_current, width=6).grid(row=0, column=0, padx=4, pady=6)
        ttk.Label(growth_frame, text="/").grid(row=0, column=1)
        ttk.Entry(growth_frame, textvariable=self.var_growth_max, width=6).grid(row=0, column=2, padx=4, pady=6)

        carry_frame = ttk.LabelFrame(top_bar, text="Carry Capacity")
        carry_frame.pack(side=tk.LEFT)
        ttk.Label(carry_frame, textvariable=self.var_carry_display, font=("", 10)).pack(padx=6, pady=6)

        self.inv_tabs = ttk.Notebook(frame)
        self.inv_tabs.pack(fill=tk.BOTH, expand=True)

        for key, label in [("equipment", "Equipment"), ("bag", "Bag"), ("storage", "Storage")]:
            f = ttk.Frame(self.inv_tabs)
            self.inv_tabs.add(f, text=label)
            self._build_inventory_category(f, key)

        # Currency sub-tab
        currency_frame = ttk.Frame(self.inv_tabs)
        self.inv_tabs.add(currency_frame, text="Currency")
        self._build_currency_tab(currency_frame)

        # Body Map sub-tab
        body_map_frame = ttk.Frame(self.inv_tabs)
        self.inv_tabs.add(body_map_frame, text="Body Map")
        self._build_body_map_tab(body_map_frame)

    def _build_currency_tab(self, parent):
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(outer, text="Mana Stones", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 8))

        # Current totals display
        totals_frame = ttk.LabelFrame(outer, text="Current Holdings")
        totals_frame.pack(fill=tk.X, pady=(0, 10))
        self._currency_totals_label = ttk.Label(totals_frame, textvariable=self.var_currency_display,
                                                 wraplength=500, justify="left")
        self._currency_totals_label.pack(padx=10, pady=8, anchor="w")

        # Add / Remove stones
        add_frame = ttk.LabelFrame(outer, text="Add / Remove Mana Stones")
        add_frame.pack(fill=tk.X, pady=(0, 10))

        add_inner = ttk.Frame(add_frame)
        add_inner.pack(fill=tk.X, padx=12, pady=10)

        ttk.Label(add_inner, text="Tier:").pack(side=tk.LEFT, padx=(0, 4))
        self._currency_tier_var = tk.StringVar(value="T1")
        tier_values = [f"T{t}" for t in range(1, self.MAX_MANA_STONE_TIER + 1)]
        ttk.Combobox(add_inner, textvariable=self._currency_tier_var,
                     values=tier_values, state="readonly", width=6).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(add_inner, text="Amount:").pack(side=tk.LEFT, padx=(0, 4))
        self._currency_amount_var = tk.StringVar(value="1")
        ttk.Entry(add_inner, textvariable=self._currency_amount_var, width=8).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(add_inner, text="Add", command=self._currency_add).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(add_inner, text="Remove", command=self._currency_remove).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(add_inner, text="Set", command=self._currency_set).pack(side=tk.LEFT, padx=(0, 12))

        self._currency_result_var = tk.StringVar(value="")
        ttk.Label(add_inner, textvariable=self._currency_result_var, foreground="gray").pack(side=tk.LEFT, padx=(8, 0))

        # Conversion section
        conv_frame = ttk.LabelFrame(outer, text="Convert (100 lower = 1 higher)")
        conv_frame.pack(fill=tk.X, pady=(0, 10))

        conv_inner = ttk.Frame(conv_frame)
        conv_inner.pack(fill=tk.X, padx=12, pady=10)

        ttk.Label(conv_inner, text="Tier to upgrade:").pack(side=tk.LEFT, padx=(0, 4))
        self._conv_tier_var = tk.StringVar(value="T1")
        conv_tier_values = [f"T{t}" for t in range(1, self.MAX_MANA_STONE_TIER)]
        self._conv_combo = ttk.Combobox(conv_inner, textvariable=self._conv_tier_var,
                                        values=conv_tier_values, state="readonly", width=6)
        self._conv_combo.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(conv_inner, text="Amount:").pack(side=tk.LEFT, padx=(0, 4))
        self._conv_amount_var = tk.StringVar(value="1")
        ttk.Entry(conv_inner, textvariable=self._conv_amount_var, width=6).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(conv_inner, text="Upgrade", command=self._convert_stones_up).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(conv_inner, text="Downgrade", command=self._convert_stones_down).pack(side=tk.LEFT, padx=(0, 8))

        self._conv_result_var = tk.StringVar(value="")
        ttk.Label(conv_inner, textvariable=self._conv_result_var, foreground="gray").pack(side=tk.LEFT, padx=(8, 0))

        self._refresh_currency_display()

    def _get_stone_count(self, tier: int) -> int:
        try:
            return max(0, int(self.var_mana_stones[tier].get().strip() or "0"))
        except (ValueError, KeyError):
            return 0

    def _convert_stones_up(self):
        """Convert 100 lower-tier stones into 1 higher-tier stone."""
        tier_str = self._conv_tier_var.get()
        try:
            from_tier = int(tier_str.replace("T", "").replace("t", ""))
        except ValueError:
            self._conv_result_var.set("Invalid tier.")
            return
        to_tier = from_tier + 1
        if to_tier > self.MAX_MANA_STONE_TIER:
            self._conv_result_var.set("Already at max tier.")
            return

        try:
            amount = max(1, int(self._conv_amount_var.get().strip() or "1"))
        except ValueError:
            amount = 1

        have = self._get_stone_count(from_tier)
        cost = amount * 100
        if have < cost:
            amount = have // 100
            cost = amount * 100
        if amount <= 0:
            self._conv_result_var.set(f"Need at least 100 T{from_tier} MS to upgrade.")
            return

        self.var_mana_stones[from_tier].set(str(have - cost))
        cur_high = self._get_stone_count(to_tier)
        self.var_mana_stones[to_tier].set(str(cur_high + amount))
        self._conv_result_var.set(f"Converted {cost} T{from_tier} → {amount} T{to_tier}")
        self._refresh_currency_display()

    def _convert_stones_down(self):
        """Convert 1 higher-tier stone into 100 lower-tier stones."""
        tier_str = self._conv_tier_var.get()
        try:
            from_tier = int(tier_str.replace("T", "").replace("t", ""))
        except ValueError:
            self._conv_result_var.set("Invalid tier.")
            return
        to_tier = from_tier + 1
        if to_tier > self.MAX_MANA_STONE_TIER:
            self._conv_result_var.set("Already at max tier.")
            return

        try:
            amount = max(1, int(self._conv_amount_var.get().strip() or "1"))
        except ValueError:
            amount = 1

        have_high = self._get_stone_count(to_tier)
        if have_high < amount:
            amount = have_high
        if amount <= 0:
            self._conv_result_var.set(f"No T{to_tier} MS to downgrade.")
            return

        self.var_mana_stones[to_tier].set(str(have_high - amount))
        cur_low = self._get_stone_count(from_tier)
        self.var_mana_stones[from_tier].set(str(cur_low + amount * 100))
        self._conv_result_var.set(f"Converted {amount} T{to_tier} → {amount * 100} T{from_tier}")
        self._refresh_currency_display()

    def _currency_add(self):
        """Add mana stones of a given tier."""
        tier_str = self._currency_tier_var.get()
        try:
            tier = int(tier_str.replace("T", "").replace("t", ""))
        except ValueError:
            self._currency_result_var.set("Invalid tier.")
            return
        if tier < 1 or tier > self.MAX_MANA_STONE_TIER:
            self._currency_result_var.set("Invalid tier.")
            return
        try:
            amount = max(1, int(self._currency_amount_var.get().strip() or "1"))
        except ValueError:
            amount = 1
        cur = self._get_stone_count(tier)
        self.var_mana_stones[tier].set(str(cur + amount))
        self._currency_result_var.set(f"Added {amount} T{tier} MS")
        self._refresh_currency_display()

    def _currency_remove(self):
        """Remove mana stones of a given tier."""
        tier_str = self._currency_tier_var.get()
        try:
            tier = int(tier_str.replace("T", "").replace("t", ""))
        except ValueError:
            self._currency_result_var.set("Invalid tier.")
            return
        if tier < 1 or tier > self.MAX_MANA_STONE_TIER:
            self._currency_result_var.set("Invalid tier.")
            return
        try:
            amount = max(1, int(self._currency_amount_var.get().strip() or "1"))
        except ValueError:
            amount = 1
        cur = self._get_stone_count(tier)
        removed = min(amount, cur)
        self.var_mana_stones[tier].set(str(cur - removed))
        self._currency_result_var.set(f"Removed {removed} T{tier} MS")
        self._refresh_currency_display()

    def _currency_set(self):
        """Set mana stones of a given tier to an exact amount."""
        tier_str = self._currency_tier_var.get()
        try:
            tier = int(tier_str.replace("T", "").replace("t", ""))
        except ValueError:
            self._currency_result_var.set("Invalid tier.")
            return
        if tier < 1 or tier > self.MAX_MANA_STONE_TIER:
            self._currency_result_var.set("Invalid tier.")
            return
        try:
            amount = max(0, int(self._currency_amount_var.get().strip() or "0"))
        except ValueError:
            amount = 0
        self.var_mana_stones[tier].set(str(amount))
        self._currency_result_var.set(f"Set T{tier} MS to {amount}")
        self._refresh_currency_display()

    def _refresh_currency_display(self):
        """Update the currency summary label showing non-zero tiers."""
        parts = []
        for t in range(1, self.MAX_MANA_STONE_TIER + 1):
            count = self._get_stone_count(t)
            if count > 0:
                parts.append(f"T{t}: {count}")
        self.var_currency_display.set(", ".join(parts) if parts else "No mana stones")

    # ======================== Body Map ========================

    def _build_body_map_tab(self, parent):
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left: Canvas with body model
        canvas_frame = ttk.Frame(outer)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.body_canvas = tk.Canvas(canvas_frame, width=420, height=600, highlightthickness=1)
        self.body_canvas.pack(fill=tk.BOTH, expand=True)
        self._tk_widgets.append(self.body_canvas)

        # Right: Slot detail panel
        detail_frame = ttk.LabelFrame(outer, text="Slot Details")
        detail_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        self.body_map_slot_name = tk.StringVar(value="Click a body part")
        self.body_map_item_name = tk.StringVar(value="")
        self._body_map_selected_slot = None

        ttk.Label(detail_frame, textvariable=self.body_map_slot_name,
                  font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 4))
        ttk.Label(detail_frame, textvariable=self.body_map_item_name,
                  wraplength=250).pack(anchor="w", padx=10, pady=4)

        self.body_map_details_text = tk.Text(detail_frame, wrap="word", height=10, state="disabled")
        self.body_map_details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))
        self._tk_widgets.append(self.body_map_details_text)

        ttk.Button(detail_frame, text="Unequip Slot",
                   command=self._body_map_unequip).pack(padx=10, pady=(0, 10))

        # Draw the body and bind clicks
        self._draw_body_model()
        self.body_canvas.bind("<Button-1>", self._body_map_click)

    def _draw_body_model(self):
        """Draw a front-view humanoid silhouette with clickable slot regions."""
        c = self.body_canvas
        c.delete("all")
        colors = self._get_current_colors()
        empty_fill = colors.get("entry_bg", "#3c3c3c")
        outline_color = colors.get("fg", "#cccccc")
        text_color = colors.get("fg", "#cccccc")

        # Store regions for hit-testing: slot_name -> (x1, y1, x2, y2)
        self._body_slot_regions = {}

        def draw_slot(slot_name, x1, y1, x2, y2, shape="rect", label=None):
            """Draw a slot region on the canvas."""
            tag = f"slot_{slot_name}"
            if shape == "oval":
                c.create_oval(x1, y1, x2, y2, fill=empty_fill, outline=outline_color,
                              width=2, tags=("slot", tag, "body_shape"))
            else:
                c.create_rectangle(x1, y1, x2, y2, fill=empty_fill, outline=outline_color,
                                   width=2, tags=("slot", tag, "body_shape"))
            # Label text
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            display_label = label if label else slot_name
            font_size = 7 if len(display_label) > 8 else 8
            c.create_text(cx, cy, text=display_label, fill=text_color,
                         font=("TkDefaultFont", font_size), tags=("slot", tag, "body_text"))
            self._body_slot_regions[slot_name] = (x1, y1, x2, y2)

        def draw_ring(slot_name, cx, cy, label=""):
            """Draw a small ring circle."""
            r = 8
            tag = f"slot_{slot_name}"
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=empty_fill,
                         outline=outline_color, width=2, tags=("slot", tag, "body_shape"))
            c.create_text(cx, cy, text=label, fill=text_color,
                         font=("TkDefaultFont", 6, "bold"), tags=("slot", tag, "body_text"))
            self._body_slot_regions[slot_name] = (cx - r, cy - r, cx + r, cy + r)

        # --- Head ---
        draw_slot("Head", 175, 20, 245, 80, shape="oval")

        # --- Necklace ---
        draw_slot("Necklace", 190, 85, 230, 105, shape="oval", label="Neck")

        # --- Shoulders ---
        draw_slot("Shoulders", 115, 110, 175, 150)
        # Mirror right shoulder (same slot)
        tag_sh = "slot_Shoulders"
        c.create_rectangle(245, 110, 305, 150, fill=empty_fill, outline=outline_color,
                          width=2, tags=("slot", tag_sh, "body_shape"))
        c.create_text(275, 130, text="Shoulders", fill=text_color,
                     font=("TkDefaultFont", 7), tags=("slot", tag_sh, "body_text"))

        # --- Upper Arms ---
        draw_slot("Upper Arms", 85, 155, 120, 230, label="U.Arm")
        # Mirror right
        tag_ua = "slot_Upper Arms"
        c.create_rectangle(300, 155, 335, 230, fill=empty_fill, outline=outline_color,
                          width=2, tags=("slot", tag_ua, "body_shape"))
        c.create_text(317, 192, text="U.Arm", fill=text_color,
                     font=("TkDefaultFont", 7), tags=("slot", tag_ua, "body_text"))
        self._body_slot_regions["Upper Arms"] = (85, 155, 335, 230)

        # --- Chest ---
        draw_slot("Chest", 140, 110, 280, 240)

        # --- Back ---
        draw_slot("Back", 282, 140, 340, 200, label="Back")

        # --- Bracers/Forearms ---
        draw_slot("Bracers/Forearms", 65, 235, 115, 310, label="Bracer")
        tag_bf = "slot_Bracers/Forearms"
        c.create_rectangle(305, 235, 355, 310, fill=empty_fill, outline=outline_color,
                          width=2, tags=("slot", tag_bf, "body_shape"))
        c.create_text(330, 272, text="Bracer", fill=text_color,
                     font=("TkDefaultFont", 7), tags=("slot", tag_bf, "body_text"))

        # --- Gauntlets/Hands ---
        draw_slot("Gauntlets/Hands", 50, 315, 110, 360, label="Gauntlet")
        tag_gh = "slot_Gauntlets/Hands"
        c.create_rectangle(310, 315, 370, 360, fill=empty_fill, outline=outline_color,
                          width=2, tags=("slot", tag_gh, "body_shape"))
        c.create_text(340, 337, text="Gauntlet", fill=text_color,
                     font=("TkDefaultFont", 7), tags=("slot", tag_gh, "body_text"))

        # --- Belt/Waist ---
        draw_slot("Belt/Waist", 140, 245, 280, 270, label="Belt")

        # --- Legs/Greaves ---
        draw_slot("Legs/Greaves", 140, 275, 205, 430, label="L.Leg")
        tag_lg = "slot_Legs/Greaves"
        c.create_rectangle(215, 275, 280, 430, fill=empty_fill, outline=outline_color,
                          width=2, tags=("slot", tag_lg, "body_shape"))
        c.create_text(247, 352, text="R.Leg", fill=text_color,
                     font=("TkDefaultFont", 7), tags=("slot", tag_lg, "body_text"))

        # --- Boots/Feet ---
        draw_slot("Boots/Feet", 130, 435, 205, 475, label="L.Boot")
        tag_bt = "slot_Boots/Feet"
        c.create_rectangle(215, 435, 290, 475, fill=empty_fill, outline=outline_color,
                          width=2, tags=("slot", tag_bt, "body_shape"))
        c.create_text(252, 455, text="R.Boot", fill=text_color,
                     font=("TkDefaultFont", 7), tags=("slot", tag_bt, "body_text"))

        # --- Ring slots (Left hand) ---
        left_ring_x = 35
        ring_start_y = 370
        ring_spacing = 20
        left_rings = [
            ("Left Thumb",  "T"),
            ("Left Index",  "I"),
            ("Left Middle", "M"),
            ("Left Ring",   "R"),
            ("Left Pinky",  "P"),
        ]
        for i, (slot_name, label) in enumerate(left_rings):
            draw_ring(slot_name, left_ring_x, ring_start_y + i * ring_spacing, label)

        # --- Ring slots (Right hand) ---
        right_ring_x = 385
        right_rings = [
            ("Right Thumb",  "T"),
            ("Right Index",  "I"),
            ("Right Middle", "M"),
            ("Right Ring",   "R"),
            ("Right Pinky",  "P"),
        ]
        for i, (slot_name, label) in enumerate(right_rings):
            draw_ring(slot_name, right_ring_x, ring_start_y + i * ring_spacing, label)

        # Ring column labels
        c.create_text(left_ring_x, ring_start_y - 15, text="L Rings", fill=text_color,
                     font=("TkDefaultFont", 7), tags=("body_text",))
        c.create_text(right_ring_x, ring_start_y - 15, text="R Rings", fill=text_color,
                     font=("TkDefaultFont", 7), tags=("body_text",))

    def _body_map_click(self, event):
        """Handle click on the body map canvas - find which slot was clicked."""
        items = self.body_canvas.find_overlapping(
            event.x - 4, event.y - 4, event.x + 4, event.y + 4
        )
        clicked_slot = None
        for item_id in items:
            tags = self.body_canvas.gettags(item_id)
            for tag in tags:
                if tag.startswith("slot_"):
                    clicked_slot = tag[5:]
                    break
            if clicked_slot:
                break

        if not clicked_slot or clicked_slot not in ARMOR_SLOTS:
            return

        # Find equipped item for this slot
        equipped_item = None
        for it in self.inv_data.get("equipment", []):
            if it.get("armor_slot", "") == clicked_slot:
                equipped_item = it
                break

        self._body_map_selected_slot = clicked_slot
        self.body_map_slot_name.set(clicked_slot)

        if equipped_item:
            self.body_map_item_name.set(f"Equipped: {equipped_item.get('name', '?')}")
            details_parts = []
            if equipped_item.get("roll_type", "None") != "None":
                details_parts.append(f"Roll: {equipped_item['roll_type']}")
            if equipped_item.get("damage"):
                details_parts.append(f"Damage: {equipped_item['damage']}")
            boosts = equipped_item.get("stat_boosts", [])
            if boosts:
                details_parts.append("\nStat Boosts:")
                stat_label_map = dict(BOOST_TARGET_LABELS)
                for b in boosts:
                    stat_name = stat_label_map.get(b["stat"], b["stat"])
                    if b["mode"] == "percent":
                        details_parts.append(f"  {stat_name}: {b['value']:+g}%")
                    else:
                        details_parts.append(f"  {stat_name}: {b['value']:+g}")
            w = float(equipped_item.get("weight", 0) or 0)
            if w:
                details_parts.append(f"\nWeight: {w} lbs")
            if equipped_item.get("notes"):
                details_parts.append(f"\nNotes:\n{equipped_item['notes']}")
            details_text = "\n".join(details_parts) if details_parts else "(no combat stats)"
        else:
            self.body_map_item_name.set("Empty")
            details_text = "No item equipped in this slot."

        txt = self.body_map_details_text
        txt.configure(state="normal")
        txt.delete("1.0", tk.END)
        txt.insert("1.0", details_text)
        txt.configure(state="disabled")

    def _body_map_unequip(self):
        """Clear the armor_slot on the item in the selected body map slot."""
        slot = self._body_map_selected_slot
        if not slot:
            return
        for it in self.inv_data.get("equipment", []):
            if it.get("armor_slot", "") == slot:
                it["armor_slot"] = ""
                self.inv_render("equipment")
                self._refresh_body_map()
                self.body_map_slot_name.set(slot)
                self.body_map_item_name.set("Empty")
                txt = self.body_map_details_text
                txt.configure(state="normal")
                txt.delete("1.0", tk.END)
                txt.insert("1.0", "No item equipped in this slot.")
                txt.configure(state="disabled")
                return
        messagebox.showinfo("Unequip", "This slot is already empty.")

    def _refresh_body_map(self):
        """Recolor body map slots based on current equipment assignments."""
        if not hasattr(self, "body_canvas"):
            return
        colors = self._get_current_colors()
        accent = colors.get("accent", "#569cd6")
        empty_fill = colors.get("entry_bg", "#3c3c3c")
        text_color = colors.get("fg", "#cccccc")

        occupied_slots = set()
        for it in self.inv_data.get("equipment", []):
            slot = it.get("armor_slot", "")
            if slot:
                occupied_slots.add(slot)

        for slot_name in ARMOR_SLOTS:
            tag = f"slot_{slot_name}"
            fill = accent if slot_name in occupied_slots else empty_fill
            # Update shape fill colors
            for item_id in self.body_canvas.find_withtag(tag):
                item_type = self.body_canvas.type(item_id)
                if item_type in ("rectangle", "oval"):
                    self.body_canvas.itemconfigure(item_id, fill=fill)
                elif item_type == "text":
                    self.body_canvas.itemconfigure(item_id, fill=text_color)

        # Update non-slot text labels
        for item_id in self.body_canvas.find_withtag("body_text"):
            self.body_canvas.itemconfigure(item_id, fill=text_color)

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
        self._tk_widgets.append(lb)

        controls = ttk.Frame(left)
        controls.pack(fill=tk.X, pady=(8, 0))

        ttk.Entry(controls, textvariable=self.inv_new_name[key]).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(controls, text="Add", command=lambda k=key: self.inv_add(k)).pack(side=tk.LEFT, padx=6)
        ttk.Button(controls, text="Remove", command=lambda k=key: self.inv_remove(k)).pack(side=tk.LEFT)
        ttk.Button(controls, text="Toggle ⭐", command=lambda k=key: self.inv_toggle_favorite(k)).pack(side=tk.LEFT, padx=6)

        scroll_inner = self._make_scrollable_frame(right)

        details = ttk.LabelFrame(scroll_inner, text="Selected Item (combat info)")
        details.pack(fill=tk.BOTH, expand=True)

        ttk.Label(details, text="Roll type:").grid(row=0, column=0, sticky="w", padx=6, pady=(8, 4))
        ttk.Combobox(details, values=ROLL_TYPES, textvariable=self.inv_roll_type[key], state="readonly", width=18).grid(
            row=0, column=1, sticky="w", padx=6, pady=(8, 4)
        )

        ttk.Label(details, text="Damage dice (ex: 1d10+3):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.inv_damage[key], width=28).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Weight (lbs):").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.inv_weight[key], width=10).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        r = 3  # next row counter

        # Armor Slot selector (equipment category only)
        if key == "equipment":
            ttk.Label(details, text="Armor Slot:").grid(row=r, column=0, sticky="w", padx=6, pady=4)
            slot_values = ["(none)"] + ARMOR_SLOTS
            ttk.Combobox(details, values=slot_values,
                         textvariable=self.inv_armor_slot[key],
                         state="readonly", width=20).grid(row=r, column=1, sticky="w", padx=6, pady=4)
            r += 1

        ttk.Checkbutton(details, text="Ranged item (use Precision)", variable=self.inv_is_ranged[key]).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 2)
        )
        r += 1

        ttk.Checkbutton(details, text="Apply bonus (PBD melee / Precision ranged)", variable=self.inv_apply_bonus[key]).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 2)
        )
        r += 1

        ttk.Checkbutton(details, text="Growth Item", variable=self.inv_is_growth_item[key]).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 6)
        )
        r += 1

        # ---- Passive Stat Boosts section ----
        boost_frame = ttk.LabelFrame(details, text="Passive Stat Boosts (equipment only)")
        boost_frame.grid(row=r, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 6))
        r += 1

        boost_list = tk.Listbox(boost_frame, height=4, exportselection=False)
        boost_list.pack(fill=tk.X, padx=6, pady=(6, 2))
        setattr(self, f"inv_boost_list_{key}", boost_list)
        self._tk_widgets.append(boost_list)

        boost_controls = ttk.Frame(boost_frame)
        boost_controls.pack(fill=tk.X, padx=6, pady=(2, 6))

        stat_display_values = [lbl for _, lbl in BOOST_TARGET_LABELS]
        boost_stat_combo = ttk.Combobox(boost_controls, values=stat_display_values,
                                         textvariable=self.inv_boost_stat[key], state="readonly", width=16)
        boost_stat_combo.pack(side=tk.LEFT, padx=(0, 4))
        self.inv_boost_stat[key].set(stat_display_values[0])

        ttk.Entry(boost_controls, textvariable=self.inv_boost_value[key], width=6).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Combobox(boost_controls, values=["flat", "percent"], textvariable=self.inv_boost_mode[key],
                      state="readonly", width=8).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(boost_controls, text="+", width=3,
                   command=lambda k=key: self.inv_boost_add(k)).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(boost_controls, text="-", width=3,
                   command=lambda k=key: self.inv_boost_remove(k)).pack(side=tk.LEFT)

        # ---- Consumable section ----
        cons_frame = ttk.LabelFrame(details, text="Consumable")
        cons_frame.grid(row=r, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 6))
        r += 1

        ttk.Checkbutton(cons_frame, text="Consumable (removed on use)",
                         variable=self.inv_consumable[key]).grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=(4, 2))

        ttk.Label(cons_frame, text="Heal HP:").grid(row=1, column=0, sticky="w", padx=(6, 2), pady=2)
        ttk.Entry(cons_frame, textvariable=self.inv_consume_heal_hp[key], width=6).grid(row=1, column=1, sticky="w", padx=(0, 8), pady=2)

        ttk.Label(cons_frame, text="Heal Mana:").grid(row=1, column=2, sticky="w", padx=(0, 2), pady=2)
        ttk.Entry(cons_frame, textvariable=self.inv_consume_heal_mana[key], width=6).grid(row=1, column=3, sticky="w", padx=(0, 6), pady=2)

        ttk.Label(cons_frame, text="Buff turns (0=instant):").grid(row=2, column=0, columnspan=2, sticky="w", padx=(6, 2), pady=(2, 4))
        ttk.Entry(cons_frame, textvariable=self.inv_consume_turns[key], width=6).grid(row=2, column=2, sticky="w", padx=(0, 6), pady=(2, 4))

        ttk.Label(cons_frame, text="Perm stat:").grid(row=3, column=0, sticky="w", padx=(6, 2), pady=(2, 4))
        perm_stat_values = ["(none)"] + [lbl for _, lbl in BOOST_TARGET_LABELS]
        ttk.Combobox(cons_frame, values=perm_stat_values,
                     textvariable=self.inv_consume_perm_stat[key], state="readonly", width=16).grid(
            row=3, column=1, sticky="w", padx=(0, 8), pady=(2, 4))
        ttk.Label(cons_frame, text="Value:").grid(row=3, column=2, sticky="w", padx=(0, 2), pady=(2, 4))
        ttk.Entry(cons_frame, textvariable=self.inv_consume_perm_value[key], width=6).grid(
            row=3, column=3, sticky="w", padx=(0, 6), pady=(2, 4))

        ttk.Label(details, text="Notes:").grid(row=r, column=0, sticky="nw", padx=6, pady=4)
        notes_box = tk.Text(details, wrap="word", height=4)
        notes_box.grid(row=r, column=1, sticky="nsew", padx=6, pady=4)
        setattr(self, f"inv_notes_box_{key}", notes_box)
        self._tk_widgets.append(notes_box)
        notes_row = r
        r += 1

        ttk.Button(details, text="Update Selected", command=lambda k=key: self.inv_update_selected(k)).grid(
            row=r, column=1, sticky="w", padx=6, pady=(6, 8)
        )
        r += 1

        move_box = ttk.LabelFrame(details, text="Transfer")
        move_box.grid(row=r, column=1, sticky="ew", padx=6, pady=(6, 8))
        r += 1

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
        json_row.grid(row=r, column=1, sticky="w", padx=6, pady=(0, 8))

        ttk.Button(json_row, text="Copy JSON", command=lambda k=key: self.inv_copy_json_selected(k)).pack(side=tk.LEFT)
        ttk.Button(json_row, text="Import JSON…", command=lambda k=key: self.inv_import_json_dialog(k)).pack(side=tk.LEFT, padx=8)
        if self.is_dm:
            ttk.Button(json_row, text="Save to Library", command=lambda k=key: self.item_library_save_selected(k)).pack(side=tk.LEFT, padx=8)

        details.grid_columnconfigure(1, weight=1)
        details.grid_rowconfigure(notes_row, weight=1)

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
            cons = " [C]" if it.get("consumable", False) else ""
            growth = " [G]" if it.get("is_growth_item", False) else ""
            slot = f" [{it['armor_slot']}]" if it.get("armor_slot", "") else ""
            lb.insert(tk.END, f"{star}{it.get('name','')}{rng}{cons}{growth}{slot}")

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
            "is_ranged": False,
            "stat_boosts": [],
            "is_growth_item": False,
            "weight": 0.0,
            "armor_slot": "",
        })
        self.inv_new_name[key].set("")
        self.inv_render(key)
        self._refresh_carry_display()

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
        self._refresh_equipment_boosts_display()
        self._recount_growth_items()
        self._refresh_body_map()

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

        # Load stat boosts for this item
        self.inv_boost_data[key] = list(it.get("stat_boosts", []))
        self.inv_boost_render(key)

        # Load consumable fields
        self.inv_consumable[key].set(bool(it.get("consumable", False)))
        self.inv_consume_heal_hp[key].set(str(it.get("consume_heal_hp", 0)))
        self.inv_consume_heal_mana[key].set(str(it.get("consume_heal_mana", 0)))
        self.inv_consume_turns[key].set(str(it.get("consume_turns", 0)))

        # Load perm stat consume fields
        perm_stat_key = it.get("consume_perm_stat", "")
        stat_label_map = dict(BOOST_TARGET_LABELS)
        perm_display = stat_label_map.get(perm_stat_key, "(none)") if perm_stat_key else "(none)"
        self.inv_consume_perm_stat[key].set(perm_display)
        self.inv_consume_perm_value[key].set(str(_safe_int(it.get("consume_perm_value"), 0)))

        # Load growth item flag
        self.inv_is_growth_item[key].set(bool(it.get("is_growth_item", False)))

        # Load weight
        self.inv_weight[key].set(str(it.get("weight", 0)))

        # Load armor slot
        slot = it.get("armor_slot", "")
        self.inv_armor_slot[key].set(slot if slot else "(none)")

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

        # Save stat boosts
        it["stat_boosts"] = list(self.inv_boost_data[key])

        # Save consumable fields
        it["consumable"] = bool(self.inv_consumable[key].get())
        it["consume_heal_hp"] = _safe_int(self.inv_consume_heal_hp[key].get(), 0)
        it["consume_heal_mana"] = _safe_int(self.inv_consume_heal_mana[key].get(), 0)
        it["consume_turns"] = _safe_int(self.inv_consume_turns[key].get(), 0)

        # Save perm stat consume fields
        perm_display = self.inv_consume_perm_stat[key].get()
        reverse_label_map = {lbl: k for k, lbl in BOOST_TARGET_LABELS}
        it["consume_perm_stat"] = reverse_label_map.get(perm_display, "")
        it["consume_perm_value"] = _safe_int(self.inv_consume_perm_value[key].get(), 0)

        # Save growth item flag
        it["is_growth_item"] = bool(self.inv_is_growth_item[key].get())

        # Save weight
        try:
            it["weight"] = float(self.inv_weight[key].get() or 0)
        except (ValueError, TypeError):
            it["weight"] = 0.0

        # Save armor slot (with validation)
        slot_display = self.inv_armor_slot[key].get()
        new_slot = "" if slot_display == "(none)" else slot_display
        if new_slot and key == "equipment":
            for other_it in self.inv_data["equipment"]:
                if other_it is not it and other_it.get("armor_slot", "") == new_slot:
                    messagebox.showwarning(
                        "Slot Occupied",
                        f'The "{new_slot}" slot is already occupied by '
                        f'"{other_it.get("name", "?")}". Unequip that item first.'
                    )
                    return
        it["armor_slot"] = new_slot

        notes_box: tk.Text = getattr(self, f"inv_notes_box_{key}")
        it["notes"] = notes_box.get("1.0", tk.END).rstrip("\n")

        self.inv_render(key)
        self._refresh_equipment_boosts_display()
        self._recount_growth_items()
        self._refresh_carry_display()
        self._refresh_body_map()

    def inv_boost_render(self, key: str):
        """Refresh the boost listbox for the given inventory category."""
        lb: tk.Listbox = getattr(self, f"inv_boost_list_{key}")
        lb.delete(0, tk.END)
        stat_label_map = {k: lbl for k, lbl in BOOST_TARGET_LABELS}
        for b in self.inv_boost_data[key]:
            stat_name = stat_label_map.get(b["stat"], b["stat"])
            if b["mode"] == "percent":
                display = f"{stat_name}: {b['value']:+g}%"
            else:
                display = f"{stat_name}: {b['value']:+g}"
            lb.insert(tk.END, display)

    def inv_boost_add(self, key: str):
        """Add a stat boost to the currently selected item."""
        if self.inv_selected_ref.get(key) is None:
            messagebox.showinfo("Boost", "Select an item first.")
            return
        # Map display label back to stat key
        display_label = self.inv_boost_stat[key].get()
        stat_key = None
        for k, lbl in BOOST_TARGET_LABELS:
            if lbl == display_label:
                stat_key = k
                break
        if not stat_key:
            return
        try:
            value = float(self.inv_boost_value[key].get().strip() or "0")
        except ValueError:
            return
        if value == 0:
            return
        mode = self.inv_boost_mode[key].get() or "flat"
        self.inv_boost_data[key].append({"stat": stat_key, "value": value, "mode": mode})
        # Live-save to item dict
        self.inv_selected_ref[key]["stat_boosts"] = list(self.inv_boost_data[key])
        self.inv_boost_render(key)
        self._refresh_equipment_boosts_display()

    def inv_boost_remove(self, key: str):
        """Remove the selected stat boost from the current item."""
        lb: tk.Listbox = getattr(self, f"inv_boost_list_{key}")
        sel = list(lb.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            if 0 <= idx < len(self.inv_boost_data[key]):
                self.inv_boost_data[key].pop(idx)
        # Live-save to item dict
        it = self.inv_selected_ref.get(key)
        if it is not None:
            it["stat_boosts"] = list(self.inv_boost_data[key])
        self.inv_boost_render(key)
        self._refresh_equipment_boosts_display()

    def inv_copy_json_selected(self, key: str):
        it = self.inv_selected_ref.get(key)
        if it is None:
            messagebox.showinfo("Copy JSON", "Select an item first.")
            return
        payload = self._clean_item_for_json(it)
        self._clipboard_set(json.dumps(payload, indent=2))
        messagebox.showinfo("Copy JSON", "Item JSON copied to clipboard.")

    def inv_import_json_dialog(self, key: str):
        win = tk.Toplevel(self.winfo_toplevel())
        win.title(f"Import Item JSON → {key}")
        win.geometry("520x620")
        win.transient(self)
        win.grab_set()
        colors = self._get_current_colors()
        style_toplevel(win, colors)

        ttk.Label(win, text="Paste JSON for an item OR a list of items:").pack(anchor="w", padx=10, pady=(10, 4))

        txt = tk.Text(win, wrap="none")
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        style_tk_widget(txt, colors)

        # helpful: prefill with clipboard
        clip = self._clipboard_get()
        if clip.strip():
            txt.insert("1.0", clip)

        status = tk.StringVar(value="")
        ttk.Label(win, textvariable=status, foreground=colors["gray"]).pack(anchor="w", padx=10, pady=(0, 8))

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

        # Clear armor slot when moving out of equipment
        if from_key == "equipment" and to_key != "equipment":
            it["armor_slot"] = ""

        self.inv_data[to_key].append(it)
        self.inv_selected_ref[from_key] = None

        self.inv_render(from_key)
        self.inv_render(to_key)
        self._refresh_equipment_boosts_display()
        self._recount_growth_items()
        self._refresh_body_map()

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
        self._tk_widgets.append(lb)

        controls = ttk.Frame(left)
        controls.pack(fill=tk.X, pady=(8, 0))

        ttk.Entry(controls, textvariable=self.var_new_ability_name[key]).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(controls, text="Add", command=lambda k=key: self.ability_add(k)).pack(side=tk.LEFT, padx=6)
        ttk.Button(controls, text="Remove", command=lambda k=key: self.ability_remove(k)).pack(side=tk.LEFT)
        if self.is_dm:
            ttk.Button(controls, text="Generate", command=lambda k=key: self.spell_generate_dialog(k)).pack(side=tk.LEFT, padx=6)
        ttk.Button(controls, text="Toggle ⭐", command=lambda k=key: self.ability_toggle_favorite(k)).pack(side=tk.LEFT, padx=6)

        scroll_inner = self._make_scrollable_frame(right)

        details = ttk.LabelFrame(scroll_inner, text="Selected Ability (combat info)")
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

        # ---- Stat Boosts / Buff section ----
        ttk.Separator(details, orient="horizontal").grid(row=8, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 8))

        boost_frame = ttk.LabelFrame(details, text="Stat Boosts (buff / passive)")
        boost_frame.grid(row=9, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 6))

        ab_boost_list = tk.Listbox(boost_frame, height=4, exportselection=False)
        ab_boost_list.pack(fill=tk.X, padx=6, pady=(6, 2))
        setattr(self, f"ability_boost_list_{key}", ab_boost_list)
        self._tk_widgets.append(ab_boost_list)

        ab_boost_controls = ttk.Frame(boost_frame)
        ab_boost_controls.pack(fill=tk.X, padx=6, pady=(2, 6))

        stat_display_values = [lbl for _, lbl in BOOST_TARGET_LABELS]
        ab_boost_combo = ttk.Combobox(ab_boost_controls, values=stat_display_values,
                                       textvariable=self.ability_boost_stat[key], state="readonly", width=16)
        ab_boost_combo.pack(side=tk.LEFT, padx=(0, 4))
        self.ability_boost_stat[key].set(stat_display_values[0])

        ttk.Entry(ab_boost_controls, textvariable=self.ability_boost_value[key], width=6).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Combobox(ab_boost_controls, values=["flat", "percent"], textvariable=self.ability_boost_mode[key],
                      state="readonly", width=8).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(ab_boost_controls, text="+", width=3,
                   command=lambda k=key: self.ability_boost_add(k)).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(ab_boost_controls, text="-", width=3,
                   command=lambda k=key: self.ability_boost_remove(k)).pack(side=tk.LEFT)

        ttk.Label(details, text="Buff turns (0 = passive):").grid(row=10, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(details, textvariable=self.ability_buff_turns[key], width=10).grid(row=10, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Notes:").grid(row=11, column=0, sticky="nw", padx=6, pady=4)
        notes_box = tk.Text(details, wrap="word", height=6)
        notes_box.grid(row=11, column=1, sticky="nsew", padx=6, pady=4)
        setattr(self, f"ability_notes_box_{key}", notes_box)
        self._tk_widgets.append(notes_box)

        ttk.Button(details, text="Update Selected", command=lambda k=key: self.ability_update_selected(k)).grid(
            row=12, column=1, sticky="w", padx=6, pady=(6, 8)
        )

        if self.is_dm:
            ttk.Button(details, text="Upgrade Spell", command=lambda k=key: self.spell_upgrade_dialog(k)).grid(
                row=13, column=1, sticky="w", padx=6, pady=(0, 8)
            )

        json_row = ttk.Frame(details)
        json_row.grid(row=14, column=1, sticky="w", padx=6, pady=(0, 8))

        ttk.Button(json_row, text="Copy JSON", command=lambda s=key: self.ability_copy_json_selected(s)).pack(side=tk.LEFT)
        ttk.Button(json_row, text="Import JSON…", command=lambda s=key: self.ability_import_json_dialog(s)).pack(side=tk.LEFT, padx=8)

        move_box = ttk.LabelFrame(details, text="Transfer")
        move_box.grid(row=15, column=1, sticky="ew", padx=6, pady=(6, 8))

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

        details.grid_columnconfigure(1, weight=1)
        details.grid_rowconfigure(11, weight=1)

    def ability_render(self, key: str):
        selected_ref = self.ability_selected_ref.get(key)
        self.abilities_data[key] = sort_favorites_first(self.abilities_data[key])

        lb: tk.Listbox = getattr(self, f"ability_list_{key}")
        lb.delete(0, tk.END)
        for ab in self.abilities_data[key]:
            star = "⭐ " if ab.get("favorite", False) else ""
            ab_boosts = ab.get("stat_boosts", [])
            ab_bt = _safe_int(ab.get("buff_turns"), 0)
            marker = ""
            if ab_boosts:
                marker = " [P]" if ab_bt == 0 else " [B]"
            lb.insert(tk.END, f"{star}{ab.get('name','')}{marker}")

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

        # Load stat boosts and buff turns
        self.ability_boost_data[key] = list(ab.get("stat_boosts", []))
        self.ability_boost_render(key)
        self.ability_buff_turns[key].set(str(_safe_int(ab.get("buff_turns"), 0)))

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

        # Save stat boosts and buff turns
        ab["stat_boosts"] = list(self.ability_boost_data[key])
        ab["buff_turns"] = _safe_int(self.ability_buff_turns[key].get(), 0)

        self.ability_render(key)
        self._refresh_equipment_boosts_display()

    # ---- Ability stat boost editor ----

    def ability_boost_render(self, key: str):
        """Refresh the boost listbox for the given ability category."""
        lb: tk.Listbox = getattr(self, f"ability_boost_list_{key}")
        lb.delete(0, tk.END)
        stat_label_map = {k: lbl for k, lbl in BOOST_TARGET_LABELS}
        for b in self.ability_boost_data[key]:
            stat_name = stat_label_map.get(b["stat"], b["stat"])
            if b["mode"] == "percent":
                display = f"{stat_name}: {b['value']:+g}%"
            else:
                display = f"{stat_name}: {b['value']:+g}"
            lb.insert(tk.END, display)

    def ability_boost_add(self, key: str):
        """Add a stat boost to the currently selected ability."""
        if self.ability_selected_ref.get(key) is None:
            messagebox.showinfo("Boost", "Select an ability first.")
            return
        display_label = self.ability_boost_stat[key].get()
        stat_key = None
        for k, lbl in BOOST_TARGET_LABELS:
            if lbl == display_label:
                stat_key = k
                break
        if not stat_key:
            return
        try:
            value = float(self.ability_boost_value[key].get().strip() or "0")
        except ValueError:
            return
        if value == 0:
            return
        mode = self.ability_boost_mode[key].get() or "flat"
        self.ability_boost_data[key].append({"stat": stat_key, "value": value, "mode": mode})
        self.ability_selected_ref[key]["stat_boosts"] = list(self.ability_boost_data[key])
        self.ability_boost_render(key)
        self._refresh_equipment_boosts_display()

    def ability_boost_remove(self, key: str):
        """Remove the selected stat boost from the current ability."""
        lb: tk.Listbox = getattr(self, f"ability_boost_list_{key}")
        sel = list(lb.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            if 0 <= idx < len(self.ability_boost_data[key]):
                self.ability_boost_data[key].pop(idx)
        ab = self.ability_selected_ref.get(key)
        if ab is not None:
            ab["stat_boosts"] = list(self.ability_boost_data[key])
        self.ability_boost_render(key)
        self._refresh_equipment_boosts_display()

    def ability_copy_json_selected(self, slot: str):
        ab = self.ability_selected_ref.get(slot)
        if ab is None:
            messagebox.showinfo("Copy JSON", "Select an ability first.")
            return
        payload = self._clean_ability_for_json(ab)
        self._clipboard_set(json.dumps(payload, indent=2))
        messagebox.showinfo("Copy JSON", "Ability JSON copied to clipboard.")

    def ability_import_json_dialog(self, slot: str):
        win = tk.Toplevel(self.winfo_toplevel())
        win.title(f"Import Ability JSON → {slot}")
        win.geometry("520x620")
        win.transient(self)
        win.grab_set()
        colors = self._get_current_colors()
        style_toplevel(win, colors)

        ttk.Label(win, text="Paste JSON for an ability OR a list of abilities:").pack(anchor="w", padx=10, pady=(10, 4))

        txt = tk.Text(win, wrap="none")
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        style_tk_widget(txt, colors)

        clip = self._clipboard_get()
        if clip.strip():
            txt.insert("1.0", clip)

        status = tk.StringVar(value="")
        ttk.Label(win, textvariable=status, foreground=colors["gray"]).pack(anchor="w", padx=10, pady=(0, 8))

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

    def spell_generate_dialog(self, key: str):
        """
        Open dialog for generating spell options based on research prompt.

        Args:
            key: ability category ("core", "inner", or "outer")
        """
        win = tk.Toplevel(self.winfo_toplevel())
        win.title(f"Generate Spell → {key}")
        win.geometry("700x650")
        win.transient(self)
        win.grab_set()
        colors = self._get_current_colors()
        style_toplevel(win, colors)

        # Status message
        status = tk.StringVar(value="")

        # Prompt input
        prompt_frame = ttk.LabelFrame(win, text="Research Prompt")
        prompt_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(
            prompt_frame,
            text="Describe what your character has been researching or training:",
            font=("TkDefaultFont", 9, "italic"),
            foreground=colors["gray"]
        ).pack(anchor="w", padx=8, pady=(4, 2))

        prompt_text = tk.Text(prompt_frame, wrap="word", height=4)
        prompt_text.pack(fill=tk.X, padx=8, pady=(0, 8))
        style_tk_widget(prompt_text, colors)
        prompt_text.insert("1.0", "I practiced fire magic to attack enemies...")

        # Generation button
        gen_btn_frame = ttk.Frame(win)
        gen_btn_frame.pack(fill=tk.X, padx=10, pady=5)

        # Options listbox
        options_frame = ttk.LabelFrame(win, text="Generated Options")
        options_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        options_list = tk.Listbox(options_frame, height=5, exportselection=False)
        options_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        style_tk_widget(options_list, colors)

        # Store generated spells
        generated_spells = []

        # Edit frame (shows selected spell details)
        edit_frame = ttk.LabelFrame(win, text="Edit Selected Spell")
        edit_frame.pack(fill=tk.BOTH, padx=10, pady=5)

        # Edit fields
        name_var = tk.StringVar()
        roll_type_var = tk.StringVar(value="None")
        damage_var = tk.StringVar()
        mana_var = tk.StringVar(value="0")
        overcast_enabled_var = tk.BooleanVar(value=False)
        overcast_scale_var = tk.StringVar(value="0")

        ttk.Label(edit_frame, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(edit_frame, textvariable=name_var, width=40).grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(edit_frame, text="Roll Type:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(edit_frame, values=ROLL_TYPES, textvariable=roll_type_var, state="readonly", width=15).grid(
            row=1, column=1, sticky="w", padx=6, pady=4
        )

        ttk.Label(edit_frame, text="Damage:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(edit_frame, textvariable=damage_var, width=20).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(edit_frame, text="Mana Cost:").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(edit_frame, textvariable=mana_var, width=10).grid(row=3, column=1, sticky="w", padx=6, pady=4)

        ttk.Checkbutton(edit_frame, text="Enable Overcast", variable=overcast_enabled_var).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=6, pady=4
        )

        ttk.Label(edit_frame, text="Overcast Scale:").grid(row=5, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(edit_frame, textvariable=overcast_scale_var, width=10).grid(row=5, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(edit_frame, text="Description:").grid(row=6, column=0, sticky="nw", padx=6, pady=4)
        notes_box = tk.Text(edit_frame, wrap="word", height=4)
        notes_box.grid(row=6, column=1, sticky="nsew", padx=6, pady=4)
        style_tk_widget(notes_box, colors)

        edit_frame.grid_rowconfigure(6, weight=1)
        edit_frame.grid_columnconfigure(1, weight=1)

        # Functions
        def on_generate():
            prompt = prompt_text.get("1.0", tk.END).strip()
            if not prompt:
                status.set("Please enter a research prompt.")
                return

            # Parse prompt
            prompt_data = parse_research_prompt(prompt)

            # Get character context
            tier = self.var_tier.get() or "T1"
            mana_density = self._get_effective_stat("mana_density")

            char_stats = {k: self._get_effective_stat(k) for k in STAT_KEYS}

            # Generate spells (with Ollama if available)
            nonlocal generated_spells
            generated_spells = generate_spell_options(
                prompt_data, key, tier, mana_density, char_stats, original_prompt=prompt
            )

            # Populate listbox
            options_list.delete(0, tk.END)
            for spell in generated_spells:
                display = f"{spell['name']} ({spell['roll_type']}, {spell['mana_cost']} mana)"
                options_list.insert(tk.END, display)

            status.set(f"Generated {len(generated_spells)} spell options.")

        def on_select(event):
            sel = list(options_list.curselection())
            if len(sel) != 1:
                return

            idx = sel[0]
            if 0 <= idx < len(generated_spells):
                spell = generated_spells[idx]

                # Populate edit fields
                name_var.set(spell["name"])
                roll_type_var.set(spell["roll_type"])
                damage_var.set(spell["damage"])
                mana_var.set(str(spell["mana_cost"]))

                overcast = spell.get("overcast", {})
                overcast_enabled_var.set(bool(overcast.get("enabled", False)))
                overcast_scale_var.set(str(overcast.get("scale", 0)))

                notes_box.delete("1.0", tk.END)
                notes_box.insert("1.0", spell.get("notes", ""))

        def on_add():
            if not generated_spells:
                status.set("Generate spells first.")
                return

            sel = list(options_list.curselection())
            if len(sel) != 1:
                status.set("Select a spell to add.")
                return

            idx = sel[0]
            spell = generated_spells[idx].copy()

            # Update from edit fields
            spell["name"] = name_var.get().strip()
            spell["roll_type"] = roll_type_var.get()
            spell["damage"] = damage_var.get().strip()
            try:
                spell["mana_cost"] = int(mana_var.get() or "0")
            except ValueError:
                spell["mana_cost"] = 0

            spell["overcast"]["enabled"] = bool(overcast_enabled_var.get())
            try:
                spell["overcast"]["scale"] = int(overcast_scale_var.get() or "0")
            except ValueError:
                spell["overcast"]["scale"] = 0

            spell["notes"] = notes_box.get("1.0", tk.END).rstrip("\n")

            # Add to character
            self.abilities_data[key].append(ensure_ability_obj(spell))
            self.ability_render(key)

            status.set(f"Added '{spell['name']}' to {key} abilities.")

        def on_save_to_library():
            if not generated_spells:
                status.set("Generate spells first.")
                return

            sel = list(options_list.curselection())
            if len(sel) != 1:
                status.set("Select a spell to save.")
                return

            idx = sel[0]
            spell = generated_spells[idx].copy()

            # Update from edit fields
            spell["name"] = name_var.get().strip()
            spell["roll_type"] = roll_type_var.get()
            spell["damage"] = damage_var.get().strip()
            try:
                spell["mana_cost"] = int(mana_var.get() or "0")
            except ValueError:
                spell["mana_cost"] = 0

            spell["overcast"]["enabled"] = bool(overcast_enabled_var.get())
            try:
                spell["overcast"]["scale"] = int(overcast_scale_var.get() or "0")
            except ValueError:
                spell["overcast"]["scale"] = 0

            spell["notes"] = notes_box.get("1.0", tk.END).rstrip("\n")

            # Create metadata
            metadata = {
                "date_created": datetime.now().isoformat(),
                "source_character": self.var_name.get() or "Unknown",
                "element": "unknown",  # Could parse from spell name/notes
                "archetype": "unknown",  # Could parse from spell type
                "tier": self.var_tier.get() or "T1",
                "category": key
            }

            # Save to library
            spell_id = add_spell_to_library(spell, metadata)
            status.set(f"Saved '{spell['name']}' to library.")

        # Bind selection
        options_list.bind("<<ListboxSelect>>", on_select)

        # Buttons
        ttk.Button(gen_btn_frame, text="Generate Options", command=on_generate).pack(side=tk.LEFT, padx=4)
        ttk.Label(gen_btn_frame, textvariable=status, foreground=colors["gray"]).pack(side=tk.LEFT, padx=10)

        bottom_btns = ttk.Frame(win)
        bottom_btns.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(bottom_btns, text="Add to Character", command=on_add).pack(side=tk.LEFT)
        ttk.Button(bottom_btns, text="Save to Library", command=on_save_to_library).pack(side=tk.LEFT, padx=8)
        ttk.Button(bottom_btns, text="Close", command=win.destroy).pack(side=tk.RIGHT)

    def spell_upgrade_dialog(self, key: str):
        """
        Open dialog for upgrading an existing spell.

        Args:
            key: ability category ("core", "inner", or "outer")
        """
        # Get selected spell
        ab = self.ability_selected_ref.get(key)
        if ab is None:
            messagebox.showinfo("Upgrade Spell", "Select a spell first.")
            return

        win = tk.Toplevel(self.winfo_toplevel())
        win.title(f"Upgrade Spell: {ab.get('name', 'Unknown')}")
        win.geometry("700x680")
        win.transient(self)
        win.grab_set()
        colors = self._get_current_colors()
        style_toplevel(win, colors)

        # Status message
        status = tk.StringVar(value="")

        # Current spell info
        current_frame = ttk.LabelFrame(win, text="Current Spell")
        current_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        current_info = f"Name: {ab.get('name', '')}  |  Damage: {ab.get('damage', 'None')}  |  Mana: {ab.get('mana_cost', 0)}"
        ttk.Label(current_frame, text=current_info, font=("TkDefaultFont", 9)).pack(padx=8, pady=8)

        # Training prompt input
        prompt_frame = ttk.LabelFrame(win, text="Training/Research Prompt (Optional)")
        prompt_frame.pack(fill=tk.X, padx=10, pady=(5, 5))

        ttk.Label(
            prompt_frame,
            text="Describe how your character trained to improve this spell:",
            font=("TkDefaultFont", 9, "italic"),
            foreground=colors["gray"]
        ).pack(anchor="w", padx=8, pady=(4, 2))

        prompt_text = tk.Text(prompt_frame, wrap="word", height=3)
        prompt_text.pack(fill=tk.X, padx=8, pady=(0, 8))
        style_tk_widget(prompt_text, colors)
        prompt_text.insert("1.0", "Practiced to increase power and efficiency...")

        # Generation button
        gen_btn_frame = ttk.Frame(win)
        gen_btn_frame.pack(fill=tk.X, padx=10, pady=5)

        # Save original checkbox
        save_original_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(gen_btn_frame, text="Save original to library first", variable=save_original_var).pack(side=tk.LEFT)

        # Options listbox
        options_frame = ttk.LabelFrame(win, text="Upgrade Options")
        options_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        options_list = tk.Listbox(options_frame, height=5, exportselection=False)
        options_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        style_tk_widget(options_list, colors)

        # Store generated upgrades
        generated_upgrades = []

        # Edit frame
        edit_frame = ttk.LabelFrame(win, text="Edit Selected Upgrade")
        edit_frame.pack(fill=tk.BOTH, padx=10, pady=5)

        # Edit fields
        name_var = tk.StringVar()
        roll_type_var = tk.StringVar(value="None")
        damage_var = tk.StringVar()
        mana_var = tk.StringVar(value="0")
        overcast_enabled_var = tk.BooleanVar(value=False)
        overcast_scale_var = tk.StringVar(value="0")

        ttk.Label(edit_frame, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(edit_frame, textvariable=name_var, width=40).grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(edit_frame, text="Roll Type:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(edit_frame, values=ROLL_TYPES, textvariable=roll_type_var, state="readonly", width=15).grid(
            row=1, column=1, sticky="w", padx=6, pady=4
        )

        ttk.Label(edit_frame, text="Damage:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(edit_frame, textvariable=damage_var, width=20).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(edit_frame, text="Mana Cost:").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(edit_frame, textvariable=mana_var, width=10).grid(row=3, column=1, sticky="w", padx=6, pady=4)

        ttk.Checkbutton(edit_frame, text="Enable Overcast", variable=overcast_enabled_var).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=6, pady=4
        )

        ttk.Label(edit_frame, text="Overcast Scale:").grid(row=5, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(edit_frame, textvariable=overcast_scale_var, width=10).grid(row=5, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(edit_frame, text="Description:").grid(row=6, column=0, sticky="nw", padx=6, pady=4)
        notes_box = tk.Text(edit_frame, wrap="word", height=4)
        notes_box.grid(row=6, column=1, sticky="nsew", padx=6, pady=4)
        style_tk_widget(notes_box, colors)

        edit_frame.grid_rowconfigure(6, weight=1)
        edit_frame.grid_columnconfigure(1, weight=1)

        # Functions
        def on_generate():
            # Get training prompt
            prompt = prompt_text.get("1.0", tk.END).strip()

            # Get character context
            tier = self.var_tier.get() or "T1"

            # Generate upgrades (with optional prompt for Ollama)
            nonlocal generated_upgrades
            generated_upgrades = generate_spell_upgrades(ab, key, tier, training_prompt=prompt)

            # Populate listbox
            options_list.delete(0, tk.END)
            for upgrade in generated_upgrades:
                display = f"{upgrade['name']} (Dmg: {upgrade.get('damage', 'None')}, Mana: {upgrade['mana_cost']})"
                options_list.insert(tk.END, display)

            status.set(f"Generated {len(generated_upgrades)} upgrade options.")

        def on_select(event):
            sel = list(options_list.curselection())
            if len(sel) != 1:
                return

            idx = sel[0]
            if 0 <= idx < len(generated_upgrades):
                upgrade = generated_upgrades[idx]

                # Populate edit fields
                name_var.set(upgrade["name"])
                roll_type_var.set(upgrade["roll_type"])
                damage_var.set(upgrade["damage"])
                mana_var.set(str(upgrade["mana_cost"]))

                overcast = upgrade.get("overcast", {})
                overcast_enabled_var.set(bool(overcast.get("enabled", False)))
                overcast_scale_var.set(str(overcast.get("scale", 0)))

                notes_box.delete("1.0", tk.END)
                notes_box.insert("1.0", upgrade.get("notes", ""))

        def on_replace():
            if not generated_upgrades:
                status.set("Generate upgrades first.")
                return

            sel = list(options_list.curselection())
            if len(sel) != 1:
                status.set("Select an upgrade to apply.")
                return

            idx = sel[0]
            upgrade = generated_upgrades[idx].copy()

            # Update from edit fields
            upgrade["name"] = name_var.get().strip()
            upgrade["roll_type"] = roll_type_var.get()
            upgrade["damage"] = damage_var.get().strip()
            try:
                upgrade["mana_cost"] = int(mana_var.get() or "0")
            except ValueError:
                upgrade["mana_cost"] = 0

            upgrade["overcast"]["enabled"] = bool(overcast_enabled_var.get())
            try:
                upgrade["overcast"]["scale"] = int(overcast_scale_var.get() or "0")
            except ValueError:
                upgrade["overcast"]["scale"] = 0

            upgrade["notes"] = notes_box.get("1.0", tk.END).rstrip("\n")

            # Save original to library if checked
            if save_original_var.get():
                metadata = {
                    "date_created": datetime.now().isoformat(),
                    "source_character": self.var_name.get() or "Unknown",
                    "element": "unknown",
                    "archetype": "unknown",
                    "tier": self.var_tier.get() or "T1",
                    "category": key
                }
                add_spell_to_library(ab.copy(), metadata)

            # Replace original spell with upgrade
            # Find the spell in abilities_data and replace it
            try:
                idx_in_list = self.abilities_data[key].index(ab)
                self.abilities_data[key][idx_in_list] = ensure_ability_obj(upgrade)
                self.ability_selected_ref[key] = self.abilities_data[key][idx_in_list]
            except ValueError:
                # If not found, just append
                self.abilities_data[key].append(ensure_ability_obj(upgrade))
                self.ability_selected_ref[key] = self.abilities_data[key][-1]

            self.ability_render(key)
            self.ability_on_select(key)  # Refresh the details panel

            status.set(f"Upgraded spell to '{upgrade['name']}'.")
            win.destroy()

        # Bind selection
        options_list.bind("<<ListboxSelect>>", on_select)

        # Buttons
        ttk.Button(gen_btn_frame, text="Generate Upgrades", command=on_generate).pack(side=tk.LEFT, padx=4)
        ttk.Label(gen_btn_frame, textvariable=status, foreground=colors["gray"]).pack(side=tk.LEFT, padx=10)

        bottom_btns = ttk.Frame(win)
        bottom_btns.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(bottom_btns, text="Replace Original", command=on_replace).pack(side=tk.LEFT)
        ttk.Button(bottom_btns, text="Close", command=win.destroy).pack(side=tk.RIGHT)


    # ---------------- Notes / World ----------------

    def _build_notes_tab(self):
        frame = ttk.Frame(self.tab_notes)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(frame, text="Character Notes").pack(anchor="w")
        self.notes_text = tk.Text(frame, wrap="word")
        self.notes_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self._tk_widgets.append(self.notes_text)

    def _build_world_tab(self):
        world_nb = ttk.Notebook(self.tab_world)
        world_nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # --- Sub-tab 1: World Notes (editable) ---
        notes_frame = ttk.Frame(world_nb)
        world_nb.add(notes_frame, text="World Notes")

        ttk.Label(notes_frame, text="World & Campaign Rules (DM-provided)", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        ttk.Label(notes_frame, text="Examples: point spending rules, tier changes, combat mechanics, death rules, etc.", foreground="gray").pack(anchor="w", padx=10, pady=(0, 5))
        self.world_text = tk.Text(notes_frame, wrap="word")
        self.world_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._tk_widgets.append(self.world_text)

        # --- Sub-tab 2: Stat Calculations (read-only, from StatCalculations.md) ---
        calc_frame = ttk.Frame(world_nb)
        world_nb.add(calc_frame, text="Stat Calculations")

        calc_inner = ttk.Frame(calc_frame)
        calc_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.stat_calc_text = tk.Text(calc_inner, wrap="word", state="disabled", cursor="arrow")
        calc_scroll = ttk.Scrollbar(calc_inner, orient="vertical", command=self.stat_calc_text.yview)
        self.stat_calc_text.configure(yscrollcommand=calc_scroll.set)
        calc_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.stat_calc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._tk_widgets.append(self.stat_calc_text)

        self._load_stat_calculations()

    def _load_stat_calculations(self):
        """Load StatCalculations.md and render it with basic formatting."""
        md_path = Path(__file__).parent / "StatCalculations.md"
        try:
            content = md_path.read_text(encoding="utf-8")
        except Exception:
            content = "(Could not load StatCalculations.md)"

        tw = self.stat_calc_text
        tw.configure(state="normal")
        tw.delete("1.0", tk.END)

        # Configure tags
        tw.tag_configure("h1", font=("Segoe UI", 16, "bold"), spacing1=4, spacing3=6)
        tw.tag_configure("h2", font=("Segoe UI", 13, "bold"), spacing1=12, spacing3=4)
        tw.tag_configure("h3", font=("Segoe UI", 11, "bold"), spacing1=10, spacing3=2)
        tw.tag_configure("body", font=("Segoe UI", 10))
        tw.tag_configure("bold", font=("Segoe UI", 10, "bold"))
        tw.tag_configure("code_inline", font=("Consolas", 10))
        tw.tag_configure("code_block", font=("Consolas", 9), lmargin1=20, lmargin2=20)
        tw.tag_configure("table", font=("Consolas", 9), lmargin1=10, lmargin2=10)
        tw.tag_configure("hr", font=("Segoe UI", 1), foreground="gray", spacing1=6, spacing3=6)
        tw.tag_configure("bullet", font=("Segoe UI", 10), lmargin1=20, lmargin2=30)

        in_code = False
        for line in content.split("\n"):
            if line.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                tw.insert(tk.END, line + "\n", "code_block")
            elif line.startswith("# ") and not line.startswith("##"):
                self._insert_md_formatted(tw, line[2:], "h1")
            elif line.startswith("### "):
                self._insert_md_formatted(tw, line[4:], "h3")
            elif line.startswith("## "):
                self._insert_md_formatted(tw, line[3:], "h2")
            elif line.strip().startswith("---"):
                tw.insert(tk.END, "\u2500" * 60 + "\n", "hr")
            elif line.startswith("|"):
                tw.insert(tk.END, line + "\n", "table")
            elif line.startswith("- "):
                self._insert_md_formatted(tw, "\u2022 " + line[2:], "bullet")
            else:
                self._insert_md_formatted(tw, line, "body")

        tw.configure(state="disabled")

    def _insert_md_formatted(self, tw, text, base_tag):
        """Insert a line with inline **bold** and `code` rendered."""
        parts = re.split(r'(\*\*.*?\*\*|`[^`]+`)', text)
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                tw.insert(tk.END, part[2:-2], "bold")
            elif part.startswith("`") and part.endswith("`"):
                tw.insert(tk.END, part[1:-1], "code_inline")
            else:
                tw.insert(tk.END, part, base_tag)
        tw.insert(tk.END, "\n")

    # ---------------- Settings ----------------

    def _build_settings_tab(self):
        frame = ttk.Frame(self.tab_settings)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(frame, text="Settings", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 16))

        # --- Theme ---
        theme_frame = ttk.LabelFrame(frame, text="Appearance")
        theme_frame.pack(fill=tk.X, pady=(0, 16))

        theme_row = ttk.Frame(theme_frame)
        theme_row.pack(fill=tk.X, padx=12, pady=10)

        ttk.Label(theme_row, text="Theme:").pack(side=tk.LEFT, padx=(0, 8))
        self._settings_theme_btn = ttk.Button(
            theme_row, text="Switch to Light Mode" if self._get_app().dark_mode else "Switch to Dark Mode",
            command=self._settings_toggle_theme
        )
        self._settings_theme_btn.pack(side=tk.LEFT)

        # --- UI Scale ---
        scale_frame = ttk.LabelFrame(frame, text="UI Scale")
        scale_frame.pack(fill=tk.X, pady=(0, 16))

        scale_inner = ttk.Frame(scale_frame)
        scale_inner.pack(fill=tk.X, padx=12, pady=10)

        ttk.Label(scale_inner, text="Scale:").pack(side=tk.LEFT, padx=(0, 8))

        app = self._get_app()
        self._scale_var = tk.DoubleVar(value=getattr(app, '_ui_scale', 1.0))
        self._scale_label = ttk.Label(scale_inner, text=f"{self._scale_var.get():.0%}")
        self._scale_label.pack(side=tk.RIGHT, padx=(8, 0))

        self._scale_slider = ttk.Scale(
            scale_inner, from_=0.5, to=2.0, orient=tk.HORIZONTAL,
            variable=self._scale_var, command=self._on_scale_change
        )
        self._scale_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(scale_inner, text="Reset to 100%", command=self._reset_scale).pack(side=tk.RIGHT, padx=(8, 0))

    def _get_app(self):
        return self.winfo_toplevel()

    def _settings_toggle_theme(self):
        app = self._get_app()
        if hasattr(app, '_toggle_theme'):
            app._toggle_theme()
        # Update button text
        if hasattr(self, '_settings_theme_btn'):
            self._settings_theme_btn.configure(
                text="Switch to Light Mode" if app.dark_mode else "Switch to Dark Mode"
            )

    def _on_scale_change(self, val):
        scale = float(val)
        # Snap to nearest 5%
        scale = round(scale * 20) / 20
        self._scale_var.set(scale)
        self._scale_label.configure(text=f"{scale:.0%}")

        app = self._get_app()
        if hasattr(app, '_set_ui_scale'):
            app._set_ui_scale(scale)

    def _reset_scale(self):
        self._scale_var.set(1.0)
        self._scale_label.configure(text="100%")
        app = self._get_app()
        if hasattr(app, '_set_ui_scale'):
            app._set_ui_scale(1.0)

    # ---------------- Damage Lab ----------------

    def _build_damage_lab_tab(self):
        self.damage_lab = DamageLabTab(
            self.tab_damage_lab,
            get_actions=self._damage_lab_get_actions,
            get_pbd=self._damage_lab_get_pbd,
            get_mana_density=self._damage_lab_get_mana_density,
            get_precision=self._damage_lab_get_precision,
        )
        self.damage_lab.pack(fill=tk.BOTH, expand=True)

    def _damage_lab_get_actions(self):
        self.refresh_combat_list()
        return self.combat_actions

    def _damage_lab_get_pbd(self):
        return self._get_effective_stat("pbd")

    def _damage_lab_get_precision(self):
        return self._get_effective_stat("precision")

    def _damage_lab_get_mana_density(self):
        try:
            return self._get_effective_stat("mana_density")
        except ValueError:
            return 0

    # ---------------- Battle Sim ----------------

    def _build_battle_sim_tab(self):
        self.battle_sim = BattleSimTab(
            self.tab_battle_sim,
            get_char_a_data=self._battle_sim_get_char_a_data,
            get_char_a_actions=self._battle_sim_get_char_a_actions,
        )
        self.battle_sim.pack(fill=tk.BOTH, expand=True)

    def _battle_sim_get_char_a_data(self):
        """Build a sim character dict from this sheet's live data."""
        try:
            char = {
                "name": self.var_name.get() or "Character A",
                "stats": {},
                "hp_max": self._get_effective_hp_max(),
                "hp_current": int(self.var_hp_current.get().strip() or "20"),
                "mana_max": self._get_effective_mana_max(),
                "mana_current": int(self.var_mana_current.get().strip() or "10"),
                "mana_density": self._get_effective_stat("mana_density"),
                "actions": [],
            }
            for k in STAT_KEYS:
                char["stats"][k] = self._get_effective_stat(k)

            # Build actions from equipment + abilities
            self.refresh_combat_list()
            for a in self.combat_actions:
                char["actions"].append({
                    "kind": a["kind"],
                    "slot": a.get("slot"),
                    "ref": a["ref"],
                    "name": a.get("name", ""),
                    "display": a.get("display", a.get("name", "")),
                })
            return char
        except Exception:
            return None

    def _battle_sim_get_char_a_actions(self):
        self.refresh_combat_list()
        return self.combat_actions

    def _build_spell_library_tab(self):
        """Build the Spell Library tab (DM tool)."""
        frame = ttk.Frame(self.tab_spell_library)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel: Spell list
        left = ttk.Frame(frame)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        ttk.Label(left, text="Spell Library", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 5))

        self.library_listbox = tk.Listbox(left, height=20, exportselection=False)
        self.library_listbox.pack(fill=tk.BOTH, expand=True)
        self.library_listbox.bind("<<ListboxSelect>>", lambda _: self.library_on_select())
        self._tk_widgets.append(self.library_listbox)

        # Buttons below list
        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frame, text="Refresh", command=self.library_render).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Delete Selected", command=self.library_delete_spell).pack(side=tk.LEFT)

        # Right panel: Spell details
        right = ttk.Frame(frame)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        details = ttk.LabelFrame(right, text="Spell Details")
        details.pack(fill=tk.BOTH, expand=True)

        # Spell name
        ttk.Label(details, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.library_spell_name = tk.StringVar()
        ttk.Entry(details, textvariable=self.library_spell_name, state="readonly", width=40).grid(row=0, column=1, sticky="w", padx=6, pady=4)

        # Roll type
        ttk.Label(details, text="Roll Type:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.library_spell_roll_type = tk.StringVar()
        ttk.Entry(details, textvariable=self.library_spell_roll_type, state="readonly", width=15).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        # Damage
        ttk.Label(details, text="Damage:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.library_spell_damage = tk.StringVar()
        ttk.Entry(details, textvariable=self.library_spell_damage, state="readonly", width=20).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        # Mana cost
        ttk.Label(details, text="Mana Cost:").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        self.library_spell_mana = tk.StringVar()
        ttk.Entry(details, textvariable=self.library_spell_mana, state="readonly", width=10).grid(row=3, column=1, sticky="w", padx=6, pady=4)

        # Overcast
        ttk.Label(details, text="Overcast:").grid(row=4, column=0, sticky="w", padx=6, pady=4)
        self.library_spell_overcast = tk.StringVar()
        ttk.Entry(details, textvariable=self.library_spell_overcast, state="readonly", width=20).grid(row=4, column=1, sticky="w", padx=6, pady=4)

        ttk.Separator(details, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", padx=6, pady=8)

        # Metadata
        ttk.Label(details, text="Source Character:").grid(row=6, column=0, sticky="w", padx=6, pady=4)
        self.library_spell_source = tk.StringVar()
        ttk.Entry(details, textvariable=self.library_spell_source, state="readonly", width=30).grid(row=6, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Element/Archetype:").grid(row=7, column=0, sticky="w", padx=6, pady=4)
        self.library_spell_meta = tk.StringVar()
        ttk.Entry(details, textvariable=self.library_spell_meta, state="readonly", width=30).grid(row=7, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Tier/Category:").grid(row=8, column=0, sticky="w", padx=6, pady=4)
        self.library_spell_tier_cat = tk.StringVar()
        ttk.Entry(details, textvariable=self.library_spell_tier_cat, state="readonly", width=20).grid(row=8, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Description:").grid(row=9, column=0, sticky="nw", padx=6, pady=4)
        self.library_spell_notes = tk.Text(details, wrap="word", height=6, state="disabled")
        self.library_spell_notes.grid(row=9, column=1, sticky="nsew", padx=6, pady=4)
        self._tk_widgets.append(self.library_spell_notes)

        # Import button
        ttk.Button(details, text="Import to Character", command=self.library_import_spell).grid(row=10, column=1, sticky="w", padx=6, pady=(8, 8))

        details.grid_rowconfigure(9, weight=1)
        details.grid_columnconfigure(1, weight=1)

        # Track selected library entry
        self.library_selected_id = None

        # Initial load
        self.library_render()

    def library_render(self):
        """Refresh the library spell list."""
        spells = get_library_spells()

        self.library_listbox.delete(0, tk.END)

        if not spells:
            self.library_listbox.insert(tk.END, "(No spells in library)")
            return

        for entry in spells:
            spell = entry.get("spell", {})
            metadata = entry.get("metadata", {})

            name = spell.get("name", "Unknown")
            element = metadata.get("element", "?")
            archetype = metadata.get("archetype", "?")
            tier = metadata.get("tier", "?")
            category = metadata.get("category", "?")

            display = f"{name} [{element}/{archetype}] - {tier} {category}"
            self.library_listbox.insert(tk.END, display)

    def library_on_select(self):
        """Handle library spell selection."""
        sel = list(self.library_listbox.curselection())
        if len(sel) != 1:
            return

        idx = sel[0]
        spells = get_library_spells()

        if idx >= len(spells):
            return

        entry = spells[idx]
        spell = entry.get("spell", {})
        metadata = entry.get("metadata", {})

        # Store selected ID
        self.library_selected_id = entry.get("id")

        # Populate details
        self.library_spell_name.set(spell.get("name", ""))
        self.library_spell_roll_type.set(spell.get("roll_type", ""))
        self.library_spell_damage.set(spell.get("damage", ""))
        self.library_spell_mana.set(str(spell.get("mana_cost", 0)))

        overcast = spell.get("overcast", {})
        if overcast.get("enabled"):
            overcast_str = f"Enabled (scale: {overcast.get('scale', 0)})"
        else:
            overcast_str = "Disabled"
        self.library_spell_overcast.set(overcast_str)

        self.library_spell_source.set(metadata.get("source_character", "Unknown"))
        self.library_spell_meta.set(f"{metadata.get('element', '?')} / {metadata.get('archetype', '?')}")
        self.library_spell_tier_cat.set(f"{metadata.get('tier', '?')} / {metadata.get('category', '?')}")

        self.library_spell_notes.config(state="normal")
        self.library_spell_notes.delete("1.0", tk.END)
        self.library_spell_notes.insert("1.0", spell.get("notes", ""))
        self.library_spell_notes.config(state="disabled")

    def library_delete_spell(self):
        """Delete selected spell from library."""
        if not self.library_selected_id:
            messagebox.showinfo("Delete", "Select a spell first.")
            return

        spells = get_library_spells()
        entry = next((e for e in spells if e.get("id") == self.library_selected_id), None)
        if not entry:
            messagebox.showerror("Error", "Spell not found.")
            return

        spell_name = entry.get("spell", {}).get("name", "Unknown")

        if messagebox.askyesno("Confirm Delete", f"Delete '{spell_name}' from library?"):
            if remove_from_library(self.library_selected_id):
                self.library_selected_id = None
                self.library_render()
                messagebox.showinfo("Deleted", f"Removed '{spell_name}' from library.")
            else:
                messagebox.showerror("Error", "Failed to delete spell.")

    def library_import_spell(self):
        """Import selected library spell to character."""
        if not self.library_selected_id:
            messagebox.showinfo("Import", "Select a spell first.")
            return

        spell = import_spell_from_library(self.library_selected_id)
        if not spell:
            messagebox.showerror("Error", "Spell not found.")
            return

        # Ask which category to import to
        win = tk.Toplevel(self.winfo_toplevel())
        win.title("Import Spell")
        win.geometry("300x150")
        win.transient(self)
        win.grab_set()
        colors = self._get_current_colors()
        style_toplevel(win, colors)

        ttk.Label(win, text=f"Import '{spell.get('name', '')}' to:", font=("TkDefaultFont", 10)).pack(pady=15)

        category_var = tk.StringVar(value="core")

        ttk.Radiobutton(win, text="Core Abilities", variable=category_var, value="core").pack(anchor="w", padx=40)
        ttk.Radiobutton(win, text="Inner Abilities", variable=category_var, value="inner").pack(anchor="w", padx=40)
        ttk.Radiobutton(win, text="Outer Abilities", variable=category_var, value="outer").pack(anchor="w", padx=40)

        def do_import():
            category = category_var.get()
            self.abilities_data[category].append(ensure_ability_obj(spell))
            self.ability_render(category)
            win.destroy()
            messagebox.showinfo("Imported", f"Added '{spell.get('name', '')}' to {category} abilities.")

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Import", command=do_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=5)

    # ---------------- Item Library Tab ----------------

    def _build_item_library_tab(self):
        """Build the Item Library tab (DM tool)."""
        frame = ttk.Frame(self.tab_item_library)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel: item list
        left = ttk.Frame(frame)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        ttk.Label(left, text="Item Library", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 5))

        self.item_library_listbox = tk.Listbox(left, height=20, exportselection=False)
        self.item_library_listbox.pack(fill=tk.BOTH, expand=True)
        self.item_library_listbox.bind("<<ListboxSelect>>", lambda _: self.item_library_on_select())
        self._tk_widgets.append(self.item_library_listbox)

        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frame, text="Refresh", command=self.item_library_render).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Delete Selected", command=self.item_library_delete).pack(side=tk.LEFT)

        # Right panel: item details
        right = ttk.Frame(frame)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        details = ttk.LabelFrame(right, text="Item Details")
        details.pack(fill=tk.BOTH, expand=True)

        ttk.Label(details, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.lib_item_name = tk.StringVar()
        ttk.Entry(details, textvariable=self.lib_item_name, state="readonly", width=40).grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Roll Type:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.lib_item_roll_type = tk.StringVar()
        ttk.Entry(details, textvariable=self.lib_item_roll_type, state="readonly", width=15).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Damage:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.lib_item_damage = tk.StringVar()
        ttk.Entry(details, textvariable=self.lib_item_damage, state="readonly", width=20).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Type:").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        self.lib_item_type = tk.StringVar()
        ttk.Entry(details, textvariable=self.lib_item_type, state="readonly", width=20).grid(row=3, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Stat Boosts:").grid(row=4, column=0, sticky="w", padx=6, pady=4)
        self.lib_item_boosts = tk.StringVar()
        ttk.Entry(details, textvariable=self.lib_item_boosts, state="readonly", width=40).grid(row=4, column=1, sticky="w", padx=6, pady=4)

        ttk.Separator(details, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", padx=6, pady=8)

        ttk.Label(details, text="Source Character:").grid(row=6, column=0, sticky="w", padx=6, pady=4)
        self.lib_item_source = tk.StringVar()
        ttk.Entry(details, textvariable=self.lib_item_source, state="readonly", width=30).grid(row=6, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Category:").grid(row=7, column=0, sticky="w", padx=6, pady=4)
        self.lib_item_category = tk.StringVar()
        ttk.Entry(details, textvariable=self.lib_item_category, state="readonly", width=20).grid(row=7, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(details, text="Notes:").grid(row=8, column=0, sticky="nw", padx=6, pady=4)
        self.lib_item_notes = tk.Text(details, wrap="word", height=6, state="disabled")
        self.lib_item_notes.grid(row=8, column=1, sticky="nsew", padx=6, pady=4)
        self._tk_widgets.append(self.lib_item_notes)

        ttk.Button(details, text="Import to Character", command=self.item_library_import).grid(row=9, column=1, sticky="w", padx=6, pady=(8, 8))

        details.grid_rowconfigure(8, weight=1)
        details.grid_columnconfigure(1, weight=1)

        self.item_library_selected_id = None
        self.item_library_render()

    def item_library_render(self):
        """Refresh the item library list."""
        items = get_library_items()
        self.item_library_listbox.delete(0, tk.END)
        if not items:
            self.item_library_listbox.insert(tk.END, "(No items in library)")
            return
        for entry in items:
            item = entry.get("item", {})
            metadata = entry.get("metadata", {})
            name = item.get("name", "Unknown")
            cat = metadata.get("category", "?")
            rng = "Ranged" if item.get("is_ranged") else "Melee"
            cons = " [C]" if item.get("consumable") else ""
            display = f"{name} ({rng}{cons}) - {cat}"
            self.item_library_listbox.insert(tk.END, display)

    def item_library_on_select(self):
        """Handle item library selection."""
        sel = list(self.item_library_listbox.curselection())
        if len(sel) != 1:
            return
        idx = sel[0]
        items = get_library_items()
        if idx >= len(items):
            return
        entry = items[idx]
        item = entry.get("item", {})
        metadata = entry.get("metadata", {})

        self.item_library_selected_id = entry.get("id")

        self.lib_item_name.set(item.get("name", ""))
        self.lib_item_roll_type.set(item.get("roll_type", "None"))
        self.lib_item_damage.set(item.get("damage", ""))

        parts = []
        if item.get("is_ranged"):
            parts.append("Ranged")
        else:
            parts.append("Melee")
        if item.get("consumable"):
            parts.append("Consumable")
            hp_h = _safe_int(item.get("consume_heal_hp"), 0)
            mana_h = _safe_int(item.get("consume_heal_mana"), 0)
            turns = _safe_int(item.get("consume_turns"), 0)
            if hp_h:
                parts.append(f"HP+{hp_h}")
            if mana_h:
                parts.append(f"Mana+{mana_h}")
            if turns:
                parts.append(f"{turns} turns")
        self.lib_item_type.set(", ".join(parts))

        stat_label_map = {k: lbl for k, lbl in BOOST_TARGET_LABELS}
        boost_strs = []
        for b in item.get("stat_boosts", []):
            sn = stat_label_map.get(b.get("stat", ""), b.get("stat", ""))
            if b.get("mode") == "percent":
                boost_strs.append(f"{sn} {b.get('value', 0):+g}%")
            else:
                boost_strs.append(f"{sn} {b.get('value', 0):+g}")
        self.lib_item_boosts.set(", ".join(boost_strs) if boost_strs else "None")

        self.lib_item_source.set(metadata.get("source_character", "Unknown"))
        self.lib_item_category.set(metadata.get("category", "?"))

        self.lib_item_notes.config(state="normal")
        self.lib_item_notes.delete("1.0", tk.END)
        self.lib_item_notes.insert("1.0", item.get("notes", ""))
        self.lib_item_notes.config(state="disabled")

    def item_library_delete(self):
        """Delete selected item from library."""
        if not self.item_library_selected_id:
            messagebox.showinfo("Delete", "Select an item first.")
            return
        items = get_library_items()
        entry = next((e for e in items if e.get("id") == self.item_library_selected_id), None)
        if not entry:
            messagebox.showerror("Error", "Item not found.")
            return
        item_name = entry.get("item", {}).get("name", "Unknown")
        if messagebox.askyesno("Confirm Delete", f"Delete '{item_name}' from library?"):
            if remove_item_from_library(self.item_library_selected_id):
                self.item_library_selected_id = None
                self.item_library_render()
                messagebox.showinfo("Deleted", f"Removed '{item_name}' from library.")
            else:
                messagebox.showerror("Error", "Failed to delete item.")

    def item_library_import(self):
        """Import selected library item to character inventory."""
        if not self.item_library_selected_id:
            messagebox.showinfo("Import", "Select an item first.")
            return
        item = import_item_from_library(self.item_library_selected_id)
        if not item:
            messagebox.showerror("Error", "Item not found.")
            return

        win = tk.Toplevel(self.winfo_toplevel())
        win.title("Import Item")
        win.geometry("300x150")
        win.transient(self)
        win.grab_set()
        colors = self._get_current_colors()
        style_toplevel(win, colors)

        ttk.Label(win, text=f"Import '{item.get('name', '')}' to:", font=("TkDefaultFont", 10)).pack(pady=15)

        cat_var = tk.StringVar(value="equipment")
        ttk.Radiobutton(win, text="Equipment", variable=cat_var, value="equipment").pack(anchor="w", padx=40)
        ttk.Radiobutton(win, text="Bag", variable=cat_var, value="bag").pack(anchor="w", padx=40)
        ttk.Radiobutton(win, text="Storage", variable=cat_var, value="storage").pack(anchor="w", padx=40)

        def do_import():
            category = cat_var.get()
            self.inv_data[category].append(ensure_item_obj(item))
            self.inv_render(category)
            self._refresh_equipment_boosts_display()
            win.destroy()
            messagebox.showinfo("Imported", f"Added '{item.get('name', '')}' to {category}.")

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Import", command=do_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=5)

    def item_library_save_selected(self, inv_key: str):
        """Save the currently selected inventory item to the item library."""
        it = self.inv_selected_ref.get(inv_key)
        if it is None:
            messagebox.showinfo("Library", "Select an item first.")
            return
        item_data = self._clean_item_for_json(it)
        metadata = {
            "date_created": datetime.now().isoformat(),
            "source_character": self.var_name.get() or "Unknown",
            "category": inv_key,
        }
        add_item_to_library(item_data, metadata)
        messagebox.showinfo("Library", f"Saved '{item_data.get('name', '')}' to item library.")

    # ======================== Mob Generator Tab ========================

    def _build_mob_generator_tab(self):
        """Build the Mob Generator tab (DM tool)."""
        frame = ttk.Frame(self.tab_mob_generator)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Left panel: Configuration ---
        left = ttk.LabelFrame(frame, text="Configuration")
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=0)

        ttk.Label(left, text="Type:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.mob_type_var = tk.StringVar(value="Monster")
        ttk.Combobox(left, textvariable=self.mob_type_var, values=["Monster", "NPC"],
                     state="readonly", width=10).grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(left, text="Name (blank = random):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.mob_name_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.mob_name_var, width=22).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(left, text="Tier:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.mob_tier_var = tk.StringVar(value="T1")
        ttk.Combobox(left, textvariable=self.mob_tier_var, values=["T1", "T2", "T3", "T4"],
                     state="readonly", width=8).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(left, text="Position:").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        self.mob_position_var = tk.StringVar(value="Mid")
        ttk.Combobox(left, textvariable=self.mob_position_var,
                     values=list(MOB_POSITION_RANGES.keys()),
                     state="readonly", width=10).grid(row=3, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(left, text="Power Level:").grid(row=4, column=0, sticky="w", padx=6, pady=4)
        self.mob_power_var = tk.StringVar(value="Average")
        ttk.Combobox(left, textvariable=self.mob_power_var,
                     values=list(MOB_POWER_MULTIPLIERS.keys()),
                     state="readonly", width=16).grid(row=4, column=1, sticky="w", padx=6, pady=4)

        ttk.Separator(left, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", padx=6, pady=8)
        ttk.Label(left, text="Combat Tags:", font=("TkDefaultFont", 10, "bold")).grid(
            row=6, column=0, columnspan=2, sticky="w", padx=6, pady=4)

        self.mob_tag_vars = {}
        for i, tag in enumerate(MOB_COMBAT_TAGS):
            var = tk.BooleanVar(value=False)
            self.mob_tag_vars[tag] = var
            ttk.Checkbutton(left, text=tag, variable=var).grid(
                row=7 + i, column=0, columnspan=2, sticky="w", padx=20, pady=2)

        ttk.Separator(left, orient="horizontal").grid(row=11, column=0, columnspan=2, sticky="ew", padx=6, pady=8)
        ttk.Button(left, text="Generate", command=self._mob_generate).grid(
            row=12, column=0, columnspan=2, padx=6, pady=8)

        # --- Right panel: Preview + Save ---
        right = ttk.Frame(frame)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(right, text="Preview", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 5))

        self.mob_preview_text = tk.Text(right, wrap="word", state="disabled", height=30)
        self.mob_preview_text.pack(fill=tk.BOTH, expand=True)
        self._tk_widgets.append(self.mob_preview_text)

        btn_frame = ttk.Frame(right)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frame, text="Save as JSON...", command=self._mob_save).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Open in New Tab", command=self._mob_open_in_tab).pack(side=tk.LEFT, padx=(8, 0))

        self._generated_mob = None

    def _mob_generate(self):
        """Handle the Generate button click."""
        name = self.mob_name_var.get().strip()
        tier = self.mob_tier_var.get()
        position = self.mob_position_var.get()
        power = self.mob_power_var.get()
        creature_type = self.mob_type_var.get()
        tags = [tag for tag, var in self.mob_tag_vars.items() if var.get()]

        try:
            mob = generate_mob_character(name, tier, position, power, tags,
                                         creature_type=creature_type)
            self._generated_mob = mob
            self._mob_update_preview(mob)
        except Exception as e:
            messagebox.showerror("Generation Error", f"Failed to generate mob:\n{e}")

    def _mob_update_preview(self, mob: dict):
        """Render the generated mob into the preview text widget."""
        self.mob_preview_text.config(state="normal")
        self.mob_preview_text.delete("1.0", tk.END)

        lines = []
        lines.append(f"Name: {mob['name']}")
        lines.append(f"Tier: {mob['tier']}")
        hp = mob["resources"]["hp"]
        mana = mob["resources"]["mana"]
        lines.append(f"HP: {hp['max']}    Mana: {mana['max']}")
        lines.append("")
        lines.append("--- Stats ---")
        stat_label_map = {k: lbl for k, lbl in STAT_ORDER}
        for k in STAT_KEYS:
            label = stat_label_map.get(k, k)
            lines.append(f"  {label}: {mob['stats'].get(k, 0)}")

        lines.append("")
        lines.append("--- Equipment ---")
        equip = mob.get("inventory", {}).get("equipment", [])
        if equip:
            for item in equip:
                iname = item.get("name", "?")
                dmg = item.get("damage", "")
                rng = "Ranged" if item.get("is_ranged") else "Melee"
                dmg_str = f" {dmg}" if dmg else ""
                lines.append(f"  {iname} ({rng}){dmg_str}")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append("--- Abilities ---")
        abilities = mob.get("abilities", {})
        has_any = False
        for slot in ["core", "inner", "outer"]:
            slot_abs = abilities.get(slot, [])
            if slot_abs:
                has_any = True
                lines.append(f"  [{slot.capitalize()}]")
                for ab in slot_abs:
                    ab_name = ab.get("name", "?")
                    ab_dmg = ab.get("damage", "")
                    ab_mana = ab.get("mana_cost", 0)
                    dmg_str = f" - {ab_dmg}" if ab_dmg else ""
                    lines.append(f"    {ab_name}{dmg_str} (mana: {ab_mana})")
        if not has_any:
            lines.append("  (none)")

        lines.append("")
        lines.append("--- Notes ---")
        lines.append(mob.get("notes", ""))

        self.mob_preview_text.insert("1.0", "\n".join(lines))
        self.mob_preview_text.config(state="disabled")

    def _mob_save(self):
        """Save the generated mob as a JSON file via file dialog."""
        if not self._generated_mob:
            messagebox.showinfo("Save", "Generate a mob first.")
            return
        default_name = self._generated_mob.get("name", "mob").replace(" ", "_")
        path = filedialog.asksaveasfilename(
            title="Save mob as character JSON",
            initialfile=f"{default_name}.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            save_character(self._generated_mob, Path(path))
            messagebox.showinfo("Saved", f"Mob saved to {Path(path).name}")

    def _mob_open_in_tab(self):
        """Save the generated mob to a file and open it as a new character tab."""
        if not self._generated_mob:
            messagebox.showinfo("Open", "Generate a mob first.")
            return
        default_name = self._generated_mob.get("name", "mob").replace(" ", "_")
        path = filedialog.asksaveasfilename(
            title="Save mob and open as character tab",
            initialfile=f"{default_name}.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            p = Path(path)
            save_character(self._generated_mob, p)
            app = self.winfo_toplevel()
            if hasattr(app, "_add_character_tab"):
                app._add_character_tab(p)

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
                "display": f"{'⭐ ' if it.get('favorite', False) else ''}{it.get('name','')}  (Item:{rng}{'|Consumable' if it.get('consumable') else ''}{'|Growth' if it.get('is_growth_item') else ''})",
            })

        for slot in ["core", "inner", "outer"]:
            for ab in self.abilities_data.get(slot, []):
                ab_boosts = ab.get("stat_boosts", [])
                ab_bt = _safe_int(ab.get("buff_turns"), 0)
                tag = ""
                if ab_boosts:
                    tag = "|Passive" if ab_bt == 0 else "|Buff"
                actions.append({
                    "kind": "ability",
                    "slot": slot,
                    "ref": ab,
                    "favorite": bool(ab.get("favorite", False)),
                    "name": ab.get("name", ""),
                    "display": f"{'⭐ ' if ab.get('favorite', False) else ''}{ab.get('name','')}  (Ability:{slot}{tag})",
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

    def check_accuracy(self):
        """Calculate and display effective accuracy without rolling damage."""
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

        hit_roll_str = self.var_combat_hit_roll.get().strip()
        if not hit_roll_str:
            messagebox.showwarning("Combat", "Enter a d20 roll value first.")
            return

        try:
            d20 = int(hit_roll_str)
        except ValueError:
            messagebox.showwarning("Combat", "Hit roll must be a number (1–20).")
            return
        d20 = max(1, min(20, d20))

        ref = chosen["ref"]
        if chosen["kind"] == "ability":
            acc_key, acc_label = "spellcraft", "Spellcraft"
        elif bool(ref.get("is_ranged", False)):
            acc_key, acc_label = "ranged_acc", "Ranged Acc"
        else:
            acc_key, acc_label = "melee_acc", "Melee Acc"

        acc_val = self._get_effective_stat(acc_key)

        roll_mult = hit_roll_multiplier(d20)
        effective_acc = acc_val * roll_mult

        result = f"Accuracy: {effective_acc:.1f} ({acc_label} {acc_val} x{roll_mult:.2f}, d20={d20})"

        # If enemy evasion is provided, show glancing blow info
        ev_str = self.var_combat_enemy_evasion.get().strip()
        if ev_str:
            try:
                evasion = float(ev_str)
                glance_mult = evasion_damage_multiplier(effective_acc, evasion)
                pct = int(glance_mult * 100)
                if pct == 0:
                    result += f" | MISS (Evasion {evasion:.0f}, ratio {effective_acc/evasion:.2f})"
                else:
                    result += f" | Glancing: {pct}% dmg (Evasion {evasion:.0f}, ratio {effective_acc/evasion:.2f})"
            except ValueError:
                pass

        self.var_combat_result.set(result)

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

        # -------- Accuracy & Glancing Blow --------
        hit_roll_str = self.var_combat_hit_roll.get().strip()
        hit_info = ""
        effective_acc = None

        if hit_roll_str:
            try:
                d20 = int(hit_roll_str)
            except ValueError:
                messagebox.showwarning("Combat", "Hit roll must be a number (1–20).")
                return
            d20 = max(1, min(20, d20))

            if chosen["kind"] == "ability":
                acc_key, acc_label = "spellcraft", "Spellcraft"
            elif bool(ref.get("is_ranged", False)):
                acc_key, acc_label = "ranged_acc", "Ranged Acc"
            else:
                acc_key, acc_label = "melee_acc", "Melee Acc"

            acc_val = self._get_effective_stat(acc_key)

            roll_mult = hit_roll_multiplier(d20)
            effective_acc = acc_val * roll_mult

            hit_info = (
                f"Accuracy: {effective_acc:.1f} ({acc_label} {acc_val} x{roll_mult:.2f}, d20={d20}) | "
            )

        # Determine glancing blow multiplier if both accuracy and evasion are given
        glance_mult = 1.0
        glance_info = ""
        ev_str = self.var_combat_enemy_evasion.get().strip()
        if ev_str and effective_acc is not None:
            try:
                evasion = float(ev_str)
                glance_mult = evasion_damage_multiplier(effective_acc, evasion)
                pct = int(glance_mult * 100)
                if pct == 0:
                    self.var_combat_result.set(
                        f"{hit_info}MISS — Evasion {evasion:.0f}, ratio {effective_acc/evasion:.2f} (below 90%)"
                    )
                    return
                glance_info = f" * Glancing {pct}%"
            except ValueError:
                pass

        # -------- Early return for passive / buff-only abilities (no damage needed) --------
        if chosen["kind"] == "ability":
            ab_boosts_early = ref.get("stat_boosts", [])
            ab_bt_early = _safe_int(ref.get("buff_turns"), 0)
            has_dmg_early = bool((ref.get("damage", "") or "").strip())
            base_cost_early = int(ref.get("mana_cost", 0) or 0)

            # Pure passive — always active
            if base_cost_early <= 0 and ab_boosts_early and ab_bt_early == 0 and not has_dmg_early:
                messagebox.showinfo("Combat", "This is a passive ability — its effects are always active.")
                return

            if base_cost_early <= 0 and not has_dmg_early:
                messagebox.showwarning("Combat", "This ability has no mana_cost or damage set.")
                return

            # Buff-only spell (no damage) — spend mana, apply buff, skip damage
            if not has_dmg_early and ab_boosts_early and ab_bt_early > 0 and base_cost_early > 0:
                slot_e = chosen.get("slot", "inner")
                mana_mult_e = float(ABILITY_MODS.get(slot_e, {"mana": 1.0})["mana"])
                try:
                    spend_base_e = int((self.var_combat_mana_spend.get().strip() or str(base_cost_early)).strip())
                except ValueError:
                    spend_base_e = base_cost_early
                if spend_base_e < base_cost_early:
                    messagebox.showwarning("Combat", f"Not enough mana allocated. Base cost is {base_cost_early}.")
                    return
                spent_eff_e = int(math.ceil(spend_base_e * mana_mult_e))
                try:
                    cur_mana_e = int(self.var_mana_current.get())
                except ValueError:
                    cur_mana_e = 0
                if spent_eff_e > cur_mana_e:
                    messagebox.showwarning("Combat", f"Not enough mana. You have {cur_mana_e}, need {spent_eff_e} (slot-adjusted).")
                    return
                self.var_mana_current.set(str(cur_mana_e - spent_eff_e))
                self.active_buffs.append({
                    "name": ref.get("name", "spell"),
                    "stat_boosts": list(ab_boosts_early),
                    "turns_remaining": ab_bt_early,
                })
                self._render_active_buffs()
                self._refresh_equipment_boosts_display()
                self.var_combat_result.set(
                    f"Cast {ref.get('name','spell')}: buff applied for {ab_bt_early} turns. Mana spent: {spent_eff_e}."
                )
                return

        # -------- Damage calculation --------
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

        # -------- Items: apply PBD (melee) or Precision (ranged) as multiplier --------
        if chosen["kind"] == "item":
            apply_bonus = bool(ref.get("apply_bonus", ref.get("apply_pbd", True)))
            is_ranged = bool(ref.get("is_ranged", False))

            if not apply_bonus:
                raw_total = base
                final_total = int(math.floor(raw_total * glance_mult))
                result = f"{hit_info}Item: base {base} (rolled {rolled} + flat {flat_bonus})"
                if glance_info:
                    result += f"{glance_info} → Total {final_total} (no bonus)"
                else:
                    result += f" → Total {raw_total} (no bonus)"
                self.var_combat_result.set(result)
                return

            if is_ranged:
                pts = self._get_effective_stat("precision")
                label = "Precision"
            else:
                pts = self._get_effective_stat("pbd")
                label = "PBD"

            mult = mana_density_multiplier(pts)
            raw_total = int(math.floor(base * mult))
            final_total = int(math.floor(raw_total * glance_mult))
            result = (
                f"{hit_info}Item: base {base} (rolled {rolled} + flat {flat_bonus}) "
                f"* {label} x{mult:.2f} ({pts} pts)"
            )
            if glance_info:
                result += f"{glance_info} → Total {final_total}"
            else:
                result += f" → Total {raw_total}"
            self.var_combat_result.set(result)
            return

        # -------- Abilities: slot multipliers + overcast + mana density --------
        # (Passive and buff-only spells already handled above before damage parsing)
        slot = chosen.get("slot", "inner")
        mods = ABILITY_MODS.get(slot, {"dmg": 1.0, "mana": 1.0})
        dmg_mult = float(mods["dmg"])
        mana_mult = float(mods["mana"])

        ab_boosts = ref.get("stat_boosts", [])
        ab_buff_turns = _safe_int(ref.get("buff_turns"), 0)

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

        md_pts = self._get_effective_stat("mana_density")
        md_mult = mana_density_multiplier(md_pts)

        over_bonus = compute_overcast_bonus(base_eff, spent_eff, ref.get("overcast", {}))
        raw_total = int(math.floor((base + over_bonus) * dmg_mult * md_mult))
        final_total = int(math.floor(raw_total * glance_mult))

        self.var_mana_current.set(str(cur_mana - spent_eff))

        # Case B/D: Apply temporary buff if ability has one
        buff_note = ""
        if ab_boosts and ab_buff_turns > 0:
            self.active_buffs.append({
                "name": ref.get("name", "spell"),
                "stat_boosts": list(ab_boosts),
                "turns_remaining": ab_buff_turns,
            })
            self._render_active_buffs()
            self._refresh_equipment_boosts_display()
            buff_note = f" | Buff applied ({ab_buff_turns} turns)"

        spend_ratio = spent_eff / base_eff if base_eff > 0 else 1.0
        result = (
            f"{hit_info}{slot.title()} ability: base {base} (rolled {rolled} + flat {flat_bonus}), "
            f"overcast +{over_bonus} (spent {spent_eff}/{base_eff}={spend_ratio:.2f}x), "
            f"*{dmg_mult:.2f} slot *{md_mult:.2f} mana density"
        )
        if glance_info:
            result += f"{glance_info} → {final_total}. Mana spent: {spent_eff}.{buff_note}"
        else:
            result += f" → {raw_total}. Mana spent: {spent_eff}.{buff_note}"
        self.var_combat_result.set(result)

    # ---------------- Consumables / Active Buffs ----------------

    def consume_combat_item(self):
        """Consume the selected equipment item from the combat quick-use list."""
        if self.combat_selected_ref is None or self.combat_selected_kind != "item":
            messagebox.showinfo("Consume", "Select a consumable equipment item first.")
            return

        chosen = None
        for a in self.combat_actions:
            if a["ref"] is self.combat_selected_ref and a["kind"] == "item":
                chosen = a
                break
        if chosen is None:
            messagebox.showinfo("Consume", "Selection is out of date. Hit Refresh list and re-select.")
            return

        ref = chosen["ref"]
        if not ref.get("consumable", False):
            messagebox.showinfo("Consume", "This item is not marked as consumable.")
            return

        results = []
        name = ref.get("name", "item")

        # Instant HP heal
        heal_hp = _safe_int(ref.get("consume_heal_hp"), 0)
        if heal_hp > 0:
            try:
                cur = int(self.var_hp_current.get())
            except ValueError:
                cur = 0
            mx = self._get_effective_hp_max()
            new_hp = max(0, min(mx, cur + heal_hp))
            self.var_hp_current.set(str(new_hp))
            results.append(f"HP +{new_hp - cur}")

        # Instant Mana heal
        heal_mana = _safe_int(ref.get("consume_heal_mana"), 0)
        if heal_mana > 0:
            try:
                cur = int(self.var_mana_current.get())
            except ValueError:
                cur = 0
            mx = self._get_effective_mana_max()
            new_mana = max(0, min(mx, cur + heal_mana))
            self.var_mana_current.set(str(new_mana))
            results.append(f"Mana +{new_mana - cur}")

        # Temporary buff (stat_boosts with turns)
        turns = _safe_int(ref.get("consume_turns"), 0)
        boosts = ref.get("stat_boosts", [])
        if turns > 0 and boosts:
            self.active_buffs.append({
                "name": name,
                "stat_boosts": list(boosts),
                "turns_remaining": turns,
            })
            results.append(f"buff {turns} turns")
            self._render_active_buffs()

        # Permanent stat increase
        perm_stat = ref.get("consume_perm_stat", "")
        perm_val = _safe_int(ref.get("consume_perm_value"), 0)
        if perm_stat and perm_val:
            if perm_stat in STAT_KEYS:
                try:
                    cur = int(self.var_stats[perm_stat].get().strip() or "0")
                except ValueError:
                    cur = 0
                self.var_stats[perm_stat].set(str(cur + perm_val))
            elif perm_stat == "hp_max":
                try:
                    cur = int(self.var_hp_max.get().strip() or "0")
                except ValueError:
                    cur = 0
                self.var_hp_max.set(str(cur + perm_val))
            elif perm_stat == "mana_max":
                try:
                    cur = int(self.var_mana_max.get().strip() or "0")
                except ValueError:
                    cur = 0
                self.var_mana_max.set(str(cur + perm_val))
            stat_label = dict(BOOST_TARGET_LABELS).get(perm_stat, perm_stat)
            results.append(f"{stat_label} permanently +{perm_val}")

        # Remove the consumed item from equipment
        try:
            self.inv_data["equipment"].remove(ref)
        except ValueError:
            pass
        self.combat_selected_ref = None
        self.combat_selected_kind = None
        self.inv_selected_ref["equipment"] = None

        self.inv_render("equipment")
        self.refresh_combat_list()
        self._refresh_equipment_boosts_display()
        self._recount_growth_items()

        effect_text = ", ".join(results) if results else "no effect"
        self.var_combat_result.set(f"Consumed {name}: {effect_text}")

    def _render_active_buffs(self):
        """Refresh the active buffs listbox."""
        self.active_buffs_list.delete(0, tk.END)
        stat_label_map = {k: lbl for k, lbl in BOOST_TARGET_LABELS}
        for buff in self.active_buffs:
            boost_parts = []
            for b in buff.get("stat_boosts", []):
                stat_name = stat_label_map.get(b["stat"], b["stat"])
                if b["mode"] == "percent":
                    boost_parts.append(f"{stat_name} {b['value']:+g}%")
                else:
                    boost_parts.append(f"{stat_name} {b['value']:+g}")
            boosts_text = ", ".join(boost_parts)
            display = f"{buff['name']}: {boosts_text} ({buff['turns_remaining']} turns)"
            self.active_buffs_list.insert(tk.END, display)

    def _remove_active_buff(self):
        """Remove the selected active buff."""
        sel = list(self.active_buffs_list.curselection())
        if not sel:
            messagebox.showinfo("Buffs", "Select a buff to remove.")
            return
        for idx in reversed(sel):
            if 0 <= idx < len(self.active_buffs):
                self.active_buffs.pop(idx)
        self._render_active_buffs()
        self._refresh_equipment_boosts_display()

    # ---------------- HP / Rest ----------------

    def apply_hp_damage(self):
        try:
            dmg = int(self.var_hp_dmg.get().strip())
        except ValueError:
            messagebox.showwarning("HP", "Enter a damage number.")
            return

        try:
            cur = int(self.var_hp_current.get())
        except ValueError:
            return
        mx = self._get_effective_hp_max()

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
        except ValueError:
            return
        mx = self._get_effective_hp_max()

        cur = max(0, min(mx, cur + heal))
        self.var_hp_current.set(str(cur))
        self.var_hp_heal.set("")

    def apply_incoming_hit(self):
        """
        Apply an incoming hit to HP after glancing blow + flat DR from Physical Defense.
        Requires both Attacker Accuracy and Incoming Hit to be filled in.
        """
        acc_str = self.var_hit_attacker_accuracy.get().strip()
        inc_str = self.var_hit_incoming.get().strip()

        if not acc_str or not inc_str:
            messagebox.showwarning("Hit", "Enter both Attacker Accuracy and Incoming Hit damage.")
            return

        try:
            attacker_acc = float(acc_str)
        except ValueError:
            messagebox.showwarning("Hit", "Attacker Accuracy must be a number.")
            return

        try:
            incoming = int(inc_str)
        except ValueError:
            messagebox.showwarning("Hit", "Incoming Hit must be a number.")
            return

        try:
            cur = int(self.var_hp_current.get())
        except ValueError:
            return
        mx = self._get_effective_hp_max()

        # Glancing blow: compare attacker accuracy vs your Evasion stat
        evasion_pts = self._get_effective_stat("evasion")

        glance_mult = evasion_damage_multiplier(attacker_acc, evasion_pts)
        glance_pct = int(glance_mult * 100)

        if glance_pct == 0:
            self.var_hit_incoming.set("")
            self.var_hit_attacker_accuracy.set("")
            self.var_hit_result.set(
                f"MISS — Accuracy {attacker_acc:.1f} vs Evasion {evasion_pts}, "
                f"ratio {attacker_acc/evasion_pts:.2f} (below 90%)" if evasion_pts > 0 else "MISS"
            )
            return

        after_glance = int(math.floor(incoming * glance_mult))

        # Physical Defense DR
        phys_def_pts = self._get_effective_stat("phys_def")

        dr = phys_dr_from_points(phys_def_pts)
        final = max(0, after_glance - dr)

        new_hp = max(0, min(mx, cur - final))
        self.var_hp_current.set(str(new_hp))
        self.var_hit_incoming.set("")
        self.var_hit_attacker_accuracy.set("")
        self.var_hit_result.set(
            f"Hit {incoming} * Glancing {glance_pct}% = {after_glance} - DR {dr} = {final} → HP {new_hp}/{mx}"
        )

    def _reset_long_rest_uses(self):
        self.var_show_used.set(False)

    def apply_long_rest(self):
        hp_mx = self._get_effective_hp_max()
        mana_mx = self._get_effective_mana_max()

        self.var_hp_current.set(str(hp_mx))
        self.var_mana_current.set(str(mana_mx))
        self._reset_long_rest_uses()
        messagebox.showinfo("Long Rest", "HP and Mana restored to full. Long-rest uses reset.")

    # ---------------- Mana density label ----------------

    def _refresh_mana_density_display(self):
        pts = self._get_effective_stat("mana_density")
        self.var_mana_density_mult.set(f"x{mana_density_multiplier(pts):.2f}")

    def _compute_equipment_boosts(self) -> dict:
        """Sum passive stat boosts from equipped non-consumable items + active buffs.

        Returns {target_key: {"flat": total_flat, "percent": total_pct}}.
        Keys can be any STAT_KEY or "hp_max" / "mana_max".
        Consumable items don't give passive boosts — their boosts only
        apply when consumed (added to active_buffs).
        """
        totals = {}

        def _add_boosts(boost_list):
            for b in boost_list:
                stat = b.get("stat", "")
                if stat not in BOOST_TARGETS:
                    continue
                if stat not in totals:
                    totals[stat] = {"flat": 0.0, "percent": 0.0}
                try:
                    val = float(b.get("value", 0) or 0)
                except (ValueError, TypeError):
                    val = 0.0
                totals[stat][b.get("mode", "flat")] += val

        # Passive boosts from non-consumable equipment
        for it in self.inv_data.get("equipment", []):
            if it.get("consumable", False):
                continue  # consumables only grant boosts when consumed
            _add_boosts(it.get("stat_boosts", []))

        # Active buffs from consumed items / cast spells
        for buff in self.active_buffs:
            _add_boosts(buff.get("stat_boosts", []))

        # Passive boosts from abilities (buff_turns == 0 means always-on)
        for slot in self.ability_keys:
            for ab in self.abilities_data.get(slot, []):
                if _safe_int(ab.get("buff_turns"), 0) == 0:
                    _add_boosts(ab.get("stat_boosts", []))

        return totals

    def _apply_boost(self, base: int, info: dict) -> int:
        """Apply flat + percent boosts to a base value and return effective int."""
        if not info:
            return base
        flat = info.get("flat", 0)
        pct = info.get("percent", 0)
        return int(base + flat + math.floor(base * pct / 100))

    def _get_effective_stat(self, key: str) -> int:
        """Return the effective value of a stat after applying equipment boosts."""
        try:
            base = int(self.var_stats[key].get().strip() or "0")
        except (ValueError, KeyError):
            base = 0
        totals = self._compute_equipment_boosts()
        return self._apply_boost(base, totals.get(key))

    def _get_effective_hp_max(self) -> int:
        """Return effective HP max after applying equipment boosts."""
        try:
            base = int(self.var_hp_max.get().strip() or "0")
        except ValueError:
            base = 0
        totals = self._compute_equipment_boosts()
        return self._apply_boost(base, totals.get("hp_max"))

    def _get_effective_mana_max(self) -> int:
        """Return effective Mana max after applying equipment boosts."""
        try:
            base = int(self.var_mana_max.get().strip() or "0")
        except ValueError:
            base = 0
        totals = self._compute_equipment_boosts()
        return self._apply_boost(base, totals.get("mana_max"))

    def _refresh_equipment_boosts_display(self):
        """Update the equipment-bonus labels next to each stat on the Overview tab."""
        totals = self._compute_equipment_boosts()
        for key in STAT_KEYS:
            info = totals.get(key)
            if not info:
                self.var_equip_bonus[key].set("")
                continue
            parts = []
            flat = info.get("flat", 0)
            pct = info.get("percent", 0)
            if flat:
                parts.append(f"{flat:+g}")
            if pct:
                parts.append(f"{pct:+g}%")
            if parts:
                try:
                    base = int(self.var_stats[key].get().strip() or "0")
                except ValueError:
                    base = 0
                effective = self._apply_boost(base, info)
                self.var_equip_bonus[key].set(f"({', '.join(parts)} equip) = {effective}")
            else:
                self.var_equip_bonus[key].set("")

        # HP / Mana max boost display
        for res_key, var, _ in [("hp_max", self.var_hp_max, "HP"),
                                ("mana_max", self.var_mana_max, "Mana")]:
            info = totals.get(res_key)
            if not info:
                self.var_equip_bonus_res[res_key].set("")
                continue
            parts = []
            flat = info.get("flat", 0)
            pct = info.get("percent", 0)
            if flat:
                parts.append(f"{flat:+g}")
            if pct:
                parts.append(f"{pct:+g}%")
            if parts:
                try:
                    base = int(var.get().strip() or "0")
                except ValueError:
                    base = 0
                effective = self._apply_boost(base, info)
                self.var_equip_bonus_res[res_key].set(f"({', '.join(parts)} equip) = {effective}")
            else:
                self.var_equip_bonus_res[res_key].set("")

        self._refresh_carry_display()

    def _recount_growth_items(self):
        """Auto-count items tagged as growth items across all inventory slots."""
        count = 0
        for k in self.inv_keys:
            for it in self.inv_data[k]:
                if it.get("is_growth_item", False):
                    count += 1
        self.var_growth_current.set(str(count))

    def _refresh_carry_display(self):
        """Update the carry capacity display: total weight / max carry (strength * 10)."""
        total_weight = 0.0
        for k in self.inv_keys:
            if k == "storage":
                continue
            for it in self.inv_data[k]:
                try:
                    total_weight += float(it.get("weight", 0) or 0)
                except (ValueError, TypeError):
                    pass
        strength = self._get_effective_stat("strength")
        max_carry = strength * 10
        self.var_carry_display.set(f"{total_weight:.1f} / {max_carry} lbs")

    # ---------------- Spend Points Popup ----------------

    def open_spend_points_popup(self):
        win = tk.Toplevel(self.winfo_toplevel())
        win.title("Spend Points")
        win.geometry("600x580")
        win.transient(self)
        win.grab_set()
        colors = self._get_current_colors()
        style_toplevel(win, colors)

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
            ("", "sep"),
        ]
        for k, lab in STAT_ORDER:
            targets.append((f"{lab} (+1 per point)", f"stat:{k}"))

        # Use listbox
        lb = tk.Listbox(mid, height=18, exportselection=False)
        style_tk_widget(lb, colors)
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
        self.var_unspent.set(str(res.get("unspent_points", 0)))

        stats = c.get("stats", {})
        for k in STAT_KEYS:
            self.var_stats[k].set(str(stats.get(k, 0)))
        self._refresh_mana_density_display()

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
            self.inv_boost_data[k] = []
            self.inv_boost_render(k)
            self.inv_consumable[k].set(False)
            self.inv_consume_heal_hp[k].set("0")
            self.inv_consume_heal_mana[k].set("0")
            self.inv_consume_turns[k].set("0")
            self.inv_consume_perm_stat[k].set("")
            self.inv_consume_perm_value[k].set("0")
            self.inv_is_growth_item[k].set(False)
            self.inv_weight[k].set("0")
            self.inv_armor_slot[k].set("(none)")
            nb: tk.Text = getattr(self, f"inv_notes_box_{k}")
            nb.delete("1.0", tk.END)

        self._recount_growth_items()

        # Mana Stones
        stones = c.get("mana_stones", {})
        for t in range(1, self.MAX_MANA_STONE_TIER + 1):
            self.var_mana_stones[t].set(str(stones.get(str(t), 0)))
        self._refresh_currency_display()

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

            self.ability_boost_data[slot] = []
            self.ability_buff_turns[slot].set("0")

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
        self._refresh_equipment_boosts_display()
        self._refresh_body_map()

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
                item_dict = {
                    "name": name,
                    "favorite": bool(it.get("favorite", False)),
                    "roll_type": it.get("roll_type", "None"),
                    "damage": it.get("damage", ""),
                    "notes": it.get("notes", ""),
                    "apply_bonus": apply_bonus,
                    "apply_pbd": apply_bonus,       # back-compat
                    "is_ranged": bool(it.get("is_ranged", False)),
                }
                boosts = _normalize_stat_boosts(it.get("stat_boosts"))
                if boosts:
                    item_dict["stat_boosts"] = boosts
                if it.get("consumable"):
                    item_dict["consumable"] = True
                    item_dict["consume_heal_hp"] = _safe_int(it.get("consume_heal_hp"), 0)
                    item_dict["consume_heal_mana"] = _safe_int(it.get("consume_heal_mana"), 0)
                    item_dict["consume_turns"] = _safe_int(it.get("consume_turns"), 0)
                    perm_stat = it.get("consume_perm_stat", "")
                    perm_val = _safe_int(it.get("consume_perm_value"), 0)
                    if perm_stat and perm_val:
                        item_dict["consume_perm_stat"] = perm_stat
                        item_dict["consume_perm_value"] = perm_val
                if it.get("is_growth_item"):
                    item_dict["is_growth_item"] = True
                w = float(it.get("weight", 0) or 0)
                if w:
                    item_dict["weight"] = w
                slot = it.get("armor_slot", "")
                if slot:
                    item_dict["armor_slot"] = slot
                cleaned.append(item_dict)
            inv[k] = cleaned

        # Mana Stones save
        stones = {}
        for t in range(1, self.MAX_MANA_STONE_TIER + 1):
            val = self._get_stone_count(t)
            if val > 0:
                stones[str(t)] = val
        c["mana_stones"] = stones

        # Abilities save
        ab_all = c.setdefault("abilities", {"core": [], "inner": [], "outer": []})
        for slot in self.ability_keys:
            cleaned = []
            for ab in self.abilities_data[slot]:
                name = (ab.get("name") or "").strip()
                if not name:
                    continue
                ab_dict = {
                    "name": name,
                    "favorite": bool(ab.get("favorite", False)),
                    "roll_type": ab.get("roll_type", "None"),
                    "damage": ab.get("damage", ""),
                    "mana_cost": int(ab.get("mana_cost", 0) or 0),
                    "overcast": ab.get("overcast", {"enabled": False, "scale": 0, "power": 0.85, "cap": 999}),
                    "notes": ab.get("notes", ""),
                }
                boosts = _normalize_stat_boosts(ab.get("stat_boosts"))
                if boosts:
                    ab_dict["stat_boosts"] = boosts
                bt = _safe_int(ab.get("buff_turns"), 0)
                if bt > 0:
                    ab_dict["buff_turns"] = bt
                cleaned.append(ab_dict)
            ab_all[slot] = cleaned

        c["notes"] = self.notes_text.get("1.0", tk.END).rstrip("\n")
        c["world_info"] = self.world_text.get("1.0", tk.END).rstrip("\n")


    # ---------------- Save ----------------

    def on_save(self):
        self._save_to_disk(show_popup=True)



class CharacterApp(tk.Tk):
    """Thin window shell that hosts one or more CharacterSheet frames."""

    def __init__(self, initial_paths: list, is_dm: bool = False):
        super().__init__()
        self.is_dm = is_dm
        self.geometry("1150x780")
        self.sheets: list = []

        # Theme & scaling state
        prefs = load_prefs()
        self.dark_mode = prefs.get("dark_mode", False)
        self._ui_scale = prefs.get("ui_scale", 1.0)
        self._current_colors = DARK_COLORS if self.dark_mode else LIGHT_COLORS
        self._style = ttk.Style(self)

        # Capture base font sizes before any scaling
        self._base_font_sizes = {}
        for name in tkFont.names(self):
            f = tkFont.nametofont(name, root=self)
            self._base_font_sizes[name] = f.cget("size")

        # Apply initial UI scale
        self._apply_ui_scale(self._ui_scale)

        if is_dm:
            self._build_dm_ui(initial_paths)
        else:
            self._build_player_ui(initial_paths[0] if initial_paths else None)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._update_title()

        # Apply initial theme
        self._apply_theme()

    # ---- Player mode ----

    def _build_player_ui(self, path: Path):
        sheet = CharacterSheet(self, path, is_dm=False)
        sheet.pack(fill=tk.BOTH, expand=True)
        self.sheets.append(sheet)

    # ---- DM mode ----

    def _build_dm_ui(self, paths: list):
        dm_bar = ttk.Frame(self)
        dm_bar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(8, 0))

        ttk.Button(dm_bar, text="Open Character...", command=self.dm_open_character).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(dm_bar, text="New Character...", command=self.dm_new_character).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(dm_bar, text="Close Tab", command=self.dm_close_current_tab).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(dm_bar, text="Save All", command=self.dm_save_all).pack(side=tk.RIGHT)

        self.master_notebook = ttk.Notebook(self)
        self.master_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))
        self.master_notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        for path in paths:
            self._add_character_tab(path)

    def _add_character_tab(self, path: Path):
        for sheet in self.sheets:
            if sheet.char_path.resolve() == path.resolve():
                idx = self.sheets.index(sheet)
                self.master_notebook.select(idx)
                return

        sheet = CharacterSheet(self.master_notebook, path, is_dm=True)
        sheet.apply_theme(self._current_colors)
        display_name = sheet.get_display_name()
        self.master_notebook.add(sheet, text=display_name)
        self.sheets.append(sheet)
        self.master_notebook.select(sheet)
        self._update_title()

    def _get_active_sheet(self):
        if not self.is_dm:
            return self.sheets[0] if self.sheets else None
        try:
            current = self.master_notebook.select()
            if current:
                widget = self.nametowidget(current)
                if isinstance(widget, CharacterSheet):
                    return widget
        except Exception:
            pass
        return None

    def dm_open_character(self):
        p = filedialog.askopenfilename(
            title="Open character JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if p:
            self._add_character_tab(Path(p))

    def dm_new_character(self):
        p = filedialog.asksaveasfilename(
            title="Create new character JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if p:
            path = Path(p)
            save_character(default_character_template(), path)
            self._add_character_tab(path)

    def dm_close_current_tab(self):
        sheet = self._get_active_sheet()
        if sheet is None:
            return
        result = sheet.prompt_save_if_dirty()
        if result in ("cancelled", "save_failed"):
            return
        self.master_notebook.forget(sheet)
        self.sheets.remove(sheet)
        sheet.destroy()
        self._update_title()

    def dm_save_all(self):
        saved = 0
        for sheet in self.sheets:
            if sheet._save_to_disk(show_popup=False):
                saved += 1
        messagebox.showinfo("Save All", f"Saved {saved} of {len(self.sheets)} character(s).")

    # ---- Shared ----

    def _on_tab_changed(self, event=None):
        self._update_title()

    def _update_title(self):
        sheet = self._get_active_sheet()
        if sheet:
            name = sheet.get_display_name()
            if self.is_dm:
                self.title(f"Homebrew Character Sheet (DM) \u2014 {name}")
            else:
                self.title(f"Homebrew Character Sheet \u2014 {name}")
        else:
            if self.is_dm:
                self.title("Homebrew Character Sheet (DM)")
            else:
                self.title("Homebrew Character Sheet")

    # ---- Theme ----

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self._current_colors = DARK_COLORS if self.dark_mode else LIGHT_COLORS
        save_theme_pref(self.dark_mode)
        self._apply_theme()

    def _apply_theme(self):
        colors = self._current_colors
        apply_ttk_theme(self._style, colors)
        self.configure(bg=colors["bg"])
        for sheet in self.sheets:
            sheet.apply_theme(colors)
            # Update Settings tab theme button text
            if hasattr(sheet, '_settings_theme_btn'):
                sheet._settings_theme_btn.configure(
                    text="Switch to Light Mode" if self.dark_mode else "Switch to Dark Mode"
                )

    # ---- UI Scaling ----

    def _apply_ui_scale(self, scale: float):
        """Apply UI scaling by adjusting all named font sizes."""
        for name, base_size in self._base_font_sizes.items():
            f = tkFont.nametofont(name, root=self)
            # Font sizes can be negative (pixel-based) or positive (point-based)
            new_size = int(base_size * scale) if base_size > 0 else int(base_size * scale)
            if new_size == 0:
                new_size = -1 if base_size < 0 else 1
            f.configure(size=new_size)

    def _set_ui_scale(self, scale: float):
        """Set and save UI scale, then apply it."""
        self._ui_scale = scale
        prefs = load_prefs()
        prefs["ui_scale"] = scale
        save_prefs(prefs)
        self._apply_ui_scale(scale)

    def on_close(self):
        for sheet in list(self.sheets):
            result = sheet.prompt_save_if_dirty()
            if result in ("cancelled", "save_failed"):
                return
        self.destroy()


def dm_login_dialog() -> bool:
    """Show a login dialog. Returns True for DM mode, False for Player mode."""
    result = {"is_dm": False}

    win = tk.Tk()
    win.title("Login")
    win.geometry("340x180")
    win.resizable(False, False)

    # Apply theme to login dialog
    colors = DARK_COLORS if load_theme_pref() else LIGHT_COLORS
    login_style = ttk.Style(win)
    apply_ttk_theme(login_style, colors)
    win.configure(bg=colors["bg"])

    ttk.Label(win, text="Enter DM password or continue as Player",
              wraplength=300).pack(padx=20, pady=(18, 8))

    pw_var = tk.StringVar()
    pw_entry = ttk.Entry(win, textvariable=pw_var, show="*", width=30)
    pw_entry.pack(padx=20, pady=(0, 4))

    error_label = ttk.Label(win, text="", foreground=colors["red"])
    error_label.pack()

    btn_frame = ttk.Frame(win)
    btn_frame.pack(pady=(4, 12))

    def on_dm_login():
        if pw_var.get() == "fun":
            result["is_dm"] = True
            win.destroy()
        else:
            error_label.config(text="Wrong password. Try again.")

    def on_player():
        result["is_dm"] = False
        win.destroy()

    ttk.Button(btn_frame, text="DM Login", command=on_dm_login).pack(side=tk.LEFT, padx=8)
    ttk.Button(btn_frame, text="Player Mode", command=on_player).pack(side=tk.LEFT, padx=8)

    pw_entry.bind("<Return>", lambda e: on_dm_login())
    pw_entry.focus_set()

    win.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))
    win.mainloop()

    return result["is_dm"]


if __name__ == "__main__":
    is_dm = dm_login_dialog()

    path = pick_character_file()
    if is_dm:
        initial_paths = [path] if path else []
        app = CharacterApp(initial_paths, is_dm=True)
    else:
        if not path:
            sys.exit(0)
        app = CharacterApp([path], is_dm=False)
    app.mainloop()
