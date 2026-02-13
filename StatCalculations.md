# Stat Calculations Reference

This document explains every stat, resource, and formula used in the Homebrew Character Sheet system.

---

## Base Stats

All base stats cost **1 point per +1**. There are no soft caps on base stats.

| Stat | Description |
|------|-------------|
| **Melee Accuracy** | Accuracy for melee attack rolls |
| **Ranged Accuracy** | Accuracy for ranged weapon attack rolls |
| **Spellcraft** | Accuracy for spell attack rolls |
| **Precision** | Bonus damage for ranged weapons (same role as PBD for melee) |
| **Physical Defense** | Provides flat damage reduction (DR) against incoming hits |
| **Evasion** | Ability to dodge or avoid attacks |
| **Wisdom** | Wisdom-based defense |
| **Utility** | General-purpose utility stat |
| **Agility** | Speed and nimbleness |
| **Strength** | Raw physical power |

---

## Resource Pools

### HP (Health Points)

| Range | Cost | Gain |
|-------|------|------|
| Below 100 max HP | 1 point | +2 HP |
| At or above 100 max HP | 1 point | +1 HP |

The soft cap at **100 HP** means it takes twice as many points to increase HP once you pass that threshold. Current HP is clamped between 0 and your max.

### Mana

| Range | Cost | Gain |
|-------|------|------|
| Below 50 max Mana | 1 point | +1 Mana |
| At or above 50 max Mana | 3 points | +2 Mana |

After 50 max mana, progression slows — you pay 3 points for every 2 mana gained.

### PBD (Power-Based Damage)

PBD is the melee damage bonus added to weapon attacks.

| Range | Cost | Gain |
|-------|------|------|
| Below 100 PBD | 1 point | +1 PBD |
| At or above 100 PBD | 5 points | +1 PBD |

After the soft cap of **100**, PBD becomes expensive at 5 points per +1.

### Mana Density

Mana Density is a multiplier that scales all ability damage. It costs **1 point per +1**. The multiplier is calculated as:

| Mana Density Points | Multiplier |
|---------------------|------------|
| 0 | 1.00x |
| 25 | 1.25x |
| 50 | 1.50x |
| 75 | 1.75x |
| 100 | 2.00x |
| 10,000 | 3.00x |

**Formula:**
- **0–100 points:** `multiplier = 1.0 + (points / 100)` — linear scaling from 1.0x to 2.0x
- **Above 100 points:** `multiplier = 2.0 + log(points / 100) / log(100)` — logarithmic scaling with heavy diminishing returns

---

## Physical Defense & Damage Reduction

Physical Defense provides flat **Damage Reduction (DR)** against incoming hits.

```
DR = floor(Physical Defense / 5)
```

Every **5 points** of Physical Defense = **1 DR**.

When you take a hit:
```
Final Damage = max(0, Incoming Damage - DR)
```

**Example:** 20 incoming damage with 35 Physical Defense → DR = 7 → Final Damage = 13

---

## Weapon Damage (Items)

### Dice Notation

Damage is written in standard dice notation: `NdS+F`
- **N** = number of dice
- **S** = die size (number of sides)
- **F** = flat bonus (can be negative, e.g. `2d6-1`)

**Example:** `2d8+3` means roll two 8-sided dice and add 3.

### Melee Weapons (PBD Scaling)

When an item has "Apply Bonus" enabled and is **not** ranged:

```
Base Damage     = Dice Roll + Flat Bonus
Roll Percentage = Dice Roll / Max Possible Roll    (clamped 0–100%)
PBD Bonus       = floor(PBD * Roll Percentage * Die Factor)
Total Damage    = Base Damage + PBD Bonus
```

The **Die Factor** scales PBD contribution based on the die size used:

| Die Size | Factor | Effect |
|----------|--------|--------|
| d4 | 0.50 | PBD adds up to 50% of its value |
| d6 | ~0.67 | |
| d8 | ~0.83 | |
| d10 | 1.00 | PBD adds up to 100% of its value |
| d12 | ~1.56 | |
| d20 | ~2.11 | PBD adds up to 211% of its value |

Values between these are linearly interpolated.

**Example:** 2d8+2 weapon, rolled 10, PBD is 50
- Base = 10 + 2 = 12
- Max roll = 2 * 8 = 16
- Roll % = 10 / 16 = 62.5%
- Die factor for d8 = ~0.83
- PBD Bonus = floor(50 * 0.625 * 0.83) = floor(25.9) = **25**
- **Total = 12 + 25 = 37**

### Ranged Weapons (Precision Scaling)

When an item has "Apply Bonus" enabled and **is** ranged, it uses **Precision** instead of PBD, but the formula is identical:

```
Precision Bonus = floor(Precision * Roll Percentage * Die Factor)
Total Damage    = Base Damage + Precision Bonus
```

### No Bonus

When "Apply Bonus" is disabled, the total damage is just the dice roll plus the flat bonus with no stat scaling.

---

## Ability Damage (Spells)

Abilities have three slots, each with different multipliers:

| Slot | Damage Multiplier | Mana Cost Multiplier | Max Slots |
|------|-------------------|----------------------|-----------|
| **Core** | 1.50x | 0.75x | 2 |
| **Inner** | 1.00x | 1.00x | 5 |
| **Outer** | 0.75x | 2.00x | 9 |

- **Core** abilities deal 50% more damage but cost 25% less mana — your strongest spells.
- **Inner** abilities are the baseline with no modifiers.
- **Outer** abilities deal 25% less damage and cost double mana — situational or utility spells.

### Ability Damage Formula

```
Base Damage         = Dice Roll + Flat Bonus
Base Cost (eff)     = ceil(Mana Cost * Mana Multiplier)
Spent (eff)         = ceil(Mana Spent * Mana Multiplier)
Mana Density Mult   = mana_density_multiplier(Mana Density points)
Overcast Bonus      = compute_overcast_bonus(Base Cost eff, Spent eff, Overcast Config)

Total Damage = floor((Base Damage + Overcast Bonus) * Damage Multiplier * Mana Density Mult)
Mana Deducted = Spent (eff)
```

**Example (Core ability):**
- Dice: 3d6, rolled 12, flat bonus 0
- Mana cost: 10, spending 10 mana
- Mana Density: 50 points → 1.50x multiplier
- Overcast: disabled
- Base damage = 12
- Base cost eff = ceil(10 * 0.75) = 8
- Spent eff = ceil(10 * 0.75) = 8
- Total = floor((12 + 0) * 1.50 * 1.50) = floor(27) = **27 damage**, 8 mana spent

---

## Overcast System

Overcast lets you spend extra mana beyond the base cost to boost an ability's damage. It uses **logarithmic scaling** so dumping huge amounts of mana has diminishing returns.

### Overcast Settings (per ability)

| Setting | Default | Description |
|---------|---------|-------------|
| **Enabled** | Off | Whether overcasting is allowed |
| **Scale** | 0 | Bonus damage at 2x mana spend |
| **Power** | 0.85 | Diminishing returns exponent (lower = more diminishing) |
| **Cap** | 999 | Maximum overcast bonus |

### Overcast Formula

```
If spending <= base cost, or overcast is disabled: bonus = 0

Otherwise:
    ratio = Mana Spent (eff) / Base Cost (eff)
    x     = log2(ratio)
    bonus = floor(Scale * x^Power)
    bonus = min(bonus, Cap)
```

### Overcast Scaling Examples

With Scale = 5, Power = 0.85:

| Mana Ratio | log2 | Bonus |
|------------|------|-------|
| 1x (base) | 0.0 | 0 |
| 2x | 1.0 | 5 |
| 4x | 2.0 | 9 |
| 8x | 3.0 | 13 |
| 16x | 4.0 | 16 |

The bonus grows, but each doubling of mana adds less than the last.

---

## Target Multipliers (Damage Lab)

When simulating damage in the Damage Lab, you can apply target resistance modifiers:

| Target Type | Multiplier |
|-------------|------------|
| Normal | 1.0x |
| Resistant | 0.5x |
| Weak | 1.5x |
| Vulnerable | 2.0x |

**Critical hits** double the final damage.

---

## Long Rest

A long rest fully restores:
- **HP** → set to max
- **Mana** → set to max
- Resets any per-rest ability uses

---

## Growth Items

Characters can bind growth items up to their max capacity. These are tracked as:
- **Bound Current** / **Bound Max**

---

## Spell Generation (DM Tool)

When the DM generates a spell, its stats are based on tier and slot:

### Tier Dice Ranges

| Tier | Die Size | Dice Count |
|------|----------|------------|
| T1 | d4–d6 | 1–2 |
| T2 | d6–d8 | 1–3 |
| T3 | d8–d12 | 2–4 |
| T4 | d10–d20 | 2–5 |

The mana cost is derived from the average damage of the roll, modified by the slot's mana multiplier and the spell's archetype, with some random variance (up to +/-20%).

---

## Summary: Full Damage Pipeline

### Weapon Attack
```
Roll Dice → Add Flat Bonus → Add PBD/Precision Scaling → Final Damage
```

### Ability Cast
```
Roll Dice → Add Flat Bonus → Add Overcast Bonus → Apply Slot Multiplier → Apply Mana Density Multiplier → Final Damage
```

### Incoming Hit
```
Incoming Damage → Subtract DR (from Phys Def / 5) → Apply to HP
```
