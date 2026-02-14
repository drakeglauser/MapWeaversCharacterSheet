# Character Stats + Tier Scaling (System Context)

This document defines what each stat means, how it is used in rolls, and how tiers should scale.

Goals of the system
- Not D&D: stats are not capped at 18, and numbers can grow into huge ranges.
- Tiers represent power “bands” where cross-tier combat is normally impossible.
- Scaling should allow extreme growth while keeping gameplay testable and consistent.
- Prefer soft caps / diminishing returns rather than hard caps (unless explicitly stated).

---

## Primary Stats (Player-spendable)

### Offensive Accuracy Stats
1) Melee Accuracy
- Used to land melee attacks (swords, fists, polearms, etc.)
- Contributes to hit success AND hit quality.

2) Ranged Weapon Accuracy
- Used to land ranged weapon attacks (bows, guns, thrown items if treated as ranged).

3) Spellcraft (Spell Accuracy)
- Used to land spell attacks.
- For purely “mental” spells, oppose with Wis.
- For physical spell projectiles / beams, oppose with Evasion (or Evasion + Wis in special cases).

### "Precision / PBD-style" Scaling
4) PBD (Melee damage multiplier)
- Only applies to melee weapons/items that are tagged to use it.
- Works as a damage multiplier using the same formula as Mana Density.

5) Precision (Ranged damage multiplier)
- Only applies to ranged weapons that should scale like PBD.
- Works as a damage multiplier using the same formula as Mana Density.

### Defensive Stats
6) Physical Defense (Flat Damage Reduction)
- Reduces incoming *physical* damage by a flat amount.
- Rule: Damage Reduction (DR) = floor(Physical Defense / 5)
  - Example: Physical Defense = 0–4 => DR 0
  - 5–9 => DR 1
  - 10–14 => DR 2
  - etc.

7) Evasion (Avoidance)
- Used to avoid being hit across melee, ranged, and many non-mental spells.
- It is the “dodge” stat in opposed roll contests.

8) Wis (Mental Defense)
- Used to resist mental attacks (hit chance and/or severity).
- If a spell is categorized as “mental”, oppose Spellcraft with Wis (instead of Evasion).

### Utility / Movement / Carry
9) Utility
- Catch-all for non-combat checks: sneaking, searching, crafting, knowledge, negotiation (if you don’t want a separate social stat).
- If you later split it, do it only with explicit approval.

10) Agility
- Represents quickness: movement speed AND extra-attack potential.
- Used for “speed advantage” rules and reaction timing.
- Important: Agility is NOT accuracy. It can create extra attacks but should not directly increase hit chance unless you choose to.

11) Strength
- Carry capacity, grappling leverage, breaking objects, forcing doors.
- (Optional later) You can tie it to melee damage, but do not do that without explicit approval.

---

## Resources
- HP: hit points
- Mana: mana pool
- Mana Density: multiplier that increases spell damage scaling (and possibly other mana-related effects)
- PBD: now a regular stat (not a resource); melee damage multiplier for weapons tagged as apply_bonus

Mana Density Multiplier (current design intent)
- 0 points => 1.00x
- 71 points => 1.71x
- 100 points => 2.00x
- then logarithmic growth beyond that

---

## Roll / Resolution Model

### A) Opposed-roll hit check (recommended baseline)
Use a single consistent hit model for melee/ranged/spell:
- Attacker rolls d20 + AccuracyStat
- Defender rolls d20 + DefenseStat
  - DefenseStat is typically Evasion
  - For mental attacks: use Wis
- If attacker total >= defender total => HIT
- Otherwise => MISS

### B) Hit Quality -> Damage Multiplier (your stated preference)
If HIT, convert the margin into a multiplier in the range 0.1x–2.5x.
A simple mapping that remains stable across tiers:

Let margin = (attack_total - defense_total)

Suggested multiplier curve (example):
- margin <= 0 : miss
- margin 1–3  : 0.75x
- margin 4–7  : 1.00x
- margin 8–12 : 1.25x
- margin 13–17: 1.50x
- margin 18–24: 2.00x
- margin 25+  : 2.50x

Notes:
- This mapping is intentionally chunky so it’s easy to DM.
- If you want it smoother later, do a formula, but keep the output clamped to [0.1, 2.5].

### C) Damage pipeline (conceptual)
1) Roll base damage from the item/spell dice
2) Add flat bonus from the damage expression (e.g., +3)
3) Apply PBD/Precision multiplier (if applicable)
4) Apply hit quality multiplier (0.1x–2.5x) (if you’re using it)
5) Apply resist/weak/vuln multipliers (if used)
6) Apply Physical Defense DR (flat reduction) if the damage is physical
7) Apply crit rules (if used)

---

## PBD vs Precision (how they should behave)
- Melee weapons: if apply_bonus = true and not ranged, use PBD multiplier.
- Ranged weapons: if apply_bonus = true and is_ranged, use Precision multiplier.
- Both are now regular stats (1 point per +1, no soft caps).

Both use the same multiplier formula as Mana Density:
- 0–100 points: `multiplier = 1.0 + (points / 100)` (linear 1.0x to 2.0x)
- Above 100: `multiplier = 2.0 + log(points / 100) / log(100)` (logarithmic)

Formula:
- Total Damage = floor(Base Damage * Multiplier)

---

## Physical Defense: Flat DR
Rule:
- DR = floor(Physical Defense / 5)
- FinalPhysicalDamage = max(0, incoming_damage - DR)

Only apply DR to damage types you label “physical”.
Do NOT apply it to “mental” spells unless you explicitly change the design.

---

## Agility: Extra Attacks (design placeholder)
Agility should enable extra attacks *without changing hit chance*.

A clean, scalable rule:
- ExtraAttacks = clamp( floor((Agility - TargetAgility) / K), 0, TierExtraCap )

Where:
- K is a tuning constant (example: 50 at low tiers)
- TierExtraCap is the max extra attacks allowed by tier (see below)

This lets speed matter only when you’re meaningfully faster than the opponent.

---

## Tier Scaling Philosophy

Tiers should define:
1) “Typical” stat ranges for balance expectations
2) Soft caps where diminishing returns start
3) Extra-attack caps and other action-economy limits
4) Testing targets

Avoid hard-capping stats unless explicitly required.

### Suggested Tier Bands (editable defaults)
These are NOT “max stats”, just expected ranges.

T1 (starter)
- Typical stat range: 0–100 in primary stats
- Soft-cap starts: ~60–80 for most stats
- TierExtraCap: 1 extra attack
- Physical Defense: early DR should be small (DR 0–6 common)

T2
- Typical stat range: 100–500
- Soft-cap starts: ~300
- TierExtraCap: 2 extra attacks

T3
- Typical stat range: 500–2,000
- Soft-cap starts: ~1,200
- TierExtraCap: 3 extra attacks

T4+
- Continue expanding ranges, but use diminishing returns and caps on action economy.

Cross-tier intention:
- 1 tier difference: sometimes winnable with luck/build advantage
- 2 tiers: extreme upset only
- 3+ tiers: basically impossible
- 5 tiers: “one in a quintillion” miracle event

---

## Things that must not change without explicit approval
- Stat names and their intended purpose (Accuracy vs Defense vs Utility)
- Mana Density multiplier design intent
- Physical Defense being flat DR (not % reduction)
- Agility granting extra attacks (not accuracy)
- PBD/Precision being multiplier-based scaling (same formula as Mana Density)

End of document.
