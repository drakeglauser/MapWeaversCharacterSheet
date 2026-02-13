# character_sheet.py
import json
import math
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path
import tkinter as tk
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


def load_theme_pref() -> bool:
    """Returns True if dark mode was saved, else False."""
    try:
        with open(PREFS_PATH, "r") as f:
            return json.load(f).get("dark_mode", False)
    except Exception:
        return False


def save_theme_pref(dark: bool):
    try:
        with open(PREFS_PATH, "w") as f:
            json.dump({"dark_mode": dark}, f)
    except Exception:
        pass


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

T1_PBD_SOFT_CAP = 100
T1_PBD_COST_BEFORE_CAP = 1
T1_PBD_GAIN_BEFORE_CAP = 1
T1_PBD_COST_AFTER_CAP = 5
T1_PBD_GAIN_AFTER_CAP = 1


# ---------- New Stats (your list) ----------
STAT_ORDER = [
    ("melee_acc",  "Melee Accuracy"),
    ("ranged_acc", "Ranged Weapon Accuracy"),
    ("spellcraft", "Spellcraft"),
    ("precision",  "Precision"),

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
        self.tab_spell_library = ttk.Frame(self.tabs)

        self.tabs.add(self.tab_overview, text="Overview")
        self.tabs.add(self.tab_inventory, text="Inventory")
        self.tabs.add(self.tab_abilities, text="Abilities")
        self.tabs.add(self.tab_notes, text="Notes")
        self.tabs.add(self.tab_world, text="World Info")
        self.tabs.add(self.tab_damage_lab, text="Damage Lab")
        if self.is_dm:
            self.tabs.add(self.tab_spell_library, text="Spell Library (DM)")

        self._build_overview_tab()
        self._build_inventory_tab()
        self._build_abilities_tab()
        self._build_notes_tab()
        self._build_world_tab()
        self._build_damage_lab_tab()
        self._build_spell_library_tab()

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
        self._tk_widgets.append(self.combat_list)

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
        # Also theme the damage lab
        if hasattr(self, "damage_lab"):
            self.damage_lab.apply_theme(colors)

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
        self._tk_widgets.append(lb)

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
        self._tk_widgets.append(notes_box)

        ttk.Button(details, text="Update Selected", command=lambda k=key: self.inv_update_selected(k)).grid(
            row=5, column=1, sticky="w", padx=6, pady=(6, 8)
        )

        move_box = ttk.LabelFrame(details, text="Transfer")
        move_box.grid(row=6, column=1, sticky="ew", padx=6, pady=(6, 8))

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
        json_row.grid(row=7, column=1, sticky="w", padx=6, pady=(0, 8))

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
        self._tk_widgets.append(lb)

        controls = ttk.Frame(left)
        controls.pack(fill=tk.X, pady=(8, 0))

        ttk.Entry(controls, textvariable=self.var_new_ability_name[key]).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(controls, text="Add", command=lambda k=key: self.ability_add(k)).pack(side=tk.LEFT, padx=6)
        ttk.Button(controls, text="Remove", command=lambda k=key: self.ability_remove(k)).pack(side=tk.LEFT)
        if self.is_dm:
            ttk.Button(controls, text="Generate", command=lambda k=key: self.spell_generate_dialog(k)).pack(side=tk.LEFT, padx=6)
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
        self._tk_widgets.append(notes_box)

        ttk.Button(details, text="Update Selected", command=lambda k=key: self.ability_update_selected(k)).grid(
            row=9, column=1, sticky="w", padx=6, pady=(6, 8)
        )

        if self.is_dm:
            ttk.Button(details, text="Upgrade Spell", command=lambda k=key: self.spell_upgrade_dialog(k)).grid(
                row=10, column=1, sticky="w", padx=6, pady=(0, 8)
            )

        json_row = ttk.Frame(details)
        json_row.grid(row=11, column=1, sticky="w", padx=6, pady=(0, 8))

        ttk.Button(json_row, text="Copy JSON", command=lambda s=key: self.ability_copy_json_selected(s)).pack(side=tk.LEFT)
        ttk.Button(json_row, text="Import JSON…", command=lambda s=key: self.ability_import_json_dialog(s)).pack(side=tk.LEFT, padx=8)

        move_box = ttk.LabelFrame(details, text="Transfer")
        move_box.grid(row=12, column=1, sticky="ew", padx=6, pady=(6, 8))

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
            try:
                mana_density = int(self.var_mana_density.get() or "0")
            except ValueError:
                mana_density = 0

            char_stats = {k: int(self.var_stats[k].get() or "0") for k in STAT_KEYS}

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
        frame = ttk.Frame(self.tab_world)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(frame, text="World & Campaign Rules (DM-provided)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Examples: point spending rules, tier changes, combat mechanics, death rules, etc.", foreground="gray").pack(anchor="w", pady=(0, 5))
        self.world_text = tk.Text(frame, wrap="word")
        self.world_text.pack(fill=tk.BOTH, expand=True)
        self._tk_widgets.append(self.world_text)

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
            ("PBD (Tier 1 rule)", "pbd"),
            ("Mana Density (+1 per point)", "mana_density"),
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



class CharacterApp(tk.Tk):
    """Thin window shell that hosts one or more CharacterSheet frames."""

    def __init__(self, initial_paths: list, is_dm: bool = False):
        super().__init__()
        self.is_dm = is_dm
        self.geometry("1150x780")
        self.sheets: list = []

        # Theme state
        self.dark_mode = load_theme_pref()
        self._current_colors = DARK_COLORS if self.dark_mode else LIGHT_COLORS
        self._style = ttk.Style(self)

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
        # Theme toggle bar
        theme_bar = ttk.Frame(self)
        theme_bar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(4, 0))
        self._theme_btn = ttk.Button(theme_bar, text="Dark Mode", command=self._toggle_theme)
        self._theme_btn.pack(side=tk.RIGHT)

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
        self._theme_btn = ttk.Button(dm_bar, text="Dark Mode", command=self._toggle_theme)
        self._theme_btn.pack(side=tk.RIGHT, padx=(0, 6))

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
        self._theme_btn.configure(text="Light Mode" if self.dark_mode else "Dark Mode")
        for sheet in self.sheets:
            sheet.apply_theme(colors)

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
