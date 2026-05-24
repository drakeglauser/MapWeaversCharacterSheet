# Tier Rules

> Status: **Design agreed with user 2026-04-29**, refined section by section. Nothing wired into code yet. Four small `[CONFIRM]` items remain (see Status Summary at the bottom). Anything marked `[CONFIRM]` is still my proposed value awaiting your call.

This document formalizes how Tiers (T1–T4+) behave as a first-class system. It is the source of truth for Sections 1, 3, and 4 of `prompt.md` (and informs Section 2's mob generator audit).

It deliberately respects the existing rules in `Context_AI_Rules.md` and `CharacterBuilding_info.md` — the Mana Density / PBD / Precision / DR / Glancing Blow formulas are NOT touched by anything below.

---

## 1. Stat Points, Tier Budgets & Progress

> **Status of this section: agreed with user 2026-04-29**, except items still marked `[CONFIRM]`.

The tier is primarily a **budget on normal earned stat points**, plus a per-tier cap on permanent-buff consumables. It does NOT hard-cap individual stat values.

### 1.1 Where stats come from (and what is counted/capped)

| Source | Counts toward tier budget / progress? | Limited by |
|--------|---------------------------------------|------------|
| Starting baseline (5 per stat) | **No** — free | fixed |
| Normal earned points (from combat) | **Yes** | the tier budget (1.2) |
| Tier-up bonus points (1.4) | **No** | one-time grant only |
| Perm-buff consumables | **No** | their own pool cap (1.5) |
| Equipment | No | equipment slots |
| Buff spells / effects | No | duration |
| Passive abilities | No | ability slots |

Only **normal earned points** count toward the budget and the progress bar. Everything else is limited by its own mechanism (slots, duration, or the perm-buff pool cap), so the user does not want extra caps on them.

### 1.2 Tier point budgets (cumulative — carries forward)

Total **normal earned points** a character can have spent at each tier. Stacking: reaching T2 does not wipe the T1 points; the budget is the running total.

| Tier | Total budget | Floor (= previous ceiling) |
|------|-------------|----------------------------|
| T1 | 100 | 0 |
| T2 | 500 | 100 |
| T3 | 2,000 | 500 |
| T4 | 10,000 | 2,000 |
| T5 | 50,000 | 10,000 |

**Confirmed** (user 2026-04-29): T1 100 / T2 500 / T3 2,000 / T4 10,000. They mirror the typical stat-range ceilings in `CharacterBuilding_info.md`. T5+ to be defined later.

The starting baseline (5 in each of 11 stats = 55 points; mana_density starts at 0) is **free** and excluded from "points spent."

### 1.3 Tier progress bar (player sees a vague band; DM sees the number)

```
progress = (normal_points_spent - tier_floor) / (tier_ceiling - tier_floor)   # clamped 0–100%
```

Player-facing label bands (using the agreed "High to Peak ≈ 80–95%" anchor):

Bands are **fixed** (agreed user 2026-04-29). **Bottom anchors at 0%** (just entered the tier) and **Peak anchors at 100%** (at the tier cap / eligible to advance); the rest sit in between as below:

| Band | % range |
|------|---------|
| Bottom | 0–10% |
| Bottom-Low | 10–20% |
| Low | 20–30% |
| Low-Mid | 30–40% |
| Mid | 40–55% |
| Mid-High | 55–65% |
| High | 65–80% |
| **High-Peak** | **80–95%** |
| Peak | 95–100% (reaches 100% at the cap) |

- **Player view:** shows only the band (e.g. "Mid-High"). No raw numbers.
- **DM view:** shows the exact figure (e.g. "320 / 2,000 pts — Mid-High"). Gated on the existing `is_dm` flag.

**Bar never reads as "done"** (user 2026-04-29): the visual fill is **not clamped at 100%**. Even at Peak it keeps a visible sliver of headroom and continues to inch as the character keeps growing (tier-up bonus points, perm-buff pool, gear, etc.), so a player at Peak does not feel they have hit a hard ceiling. The text **label** still tops out at "Peak", but the bar itself never snaps to a full/complete state.
  - Practically: the band label is derived from `normal_points_spent` within the tier (caps at Peak), while the bar's fill is driven by the character's *total* accumulated stat investment (uncapped), so the two can diverge once normal points max out — by design.

`[CONFIRM]` only the exact "keep inching" visual at implementation time (e.g. overflow scale vs. always-95%-with-a-moving-tail). Band cut points are locked.

### 1.4 Tier-up bonus ("you get a buff when you tier up")

On tier-up the character is granted a one-time pool of bonus points:

```
bonus_granted = floor(0.50 * total_normal_points_ever_earned_and_spent)
```

- Only **normal** earned points feed the 50% — baseline, prior bonus points, perm-buff, and gear do **not** count in the base.
- Bonus points are **spendable anywhere**.
- Bonus points **do NOT count** toward the tier budget or the progress bar.

**Confirmed cumulative** (user 2026-04-29) — each tier-up adds a fresh batch and you keep previously granted ones. Example:
- End of T1: 100 normal earned → tier up → **+50 bonus**.
- Earn up to 500 normal by end of T2 → tier up → **+250 bonus** (50% of 500), on top of the earlier 50.

### 1.5 Perm-buff consumable pool cap (one shared pool, all stats combined)

A single running total per character of stat points gained from perm-buff consumables. The cap **scales with the tier's point budget** (1.2) — not flat numbers (user 2026-04-29):

- **Soft cap = 70% of the tier budget.** Below this, perm-buff points apply at full value (1 consumable point = +1 stat).
- **Diminishing-returns zone = 70% → 85% of the tier budget.** Perm-buff points in this band grant progressively *less* actual stat the closer you get to 85%.
- **Hard cap = 85% of the tier budget.** Perm-buff consumption is blocked at/above this (DM override allowed).

| Tier | Budget | Soft (70%) | Hard (85%) |
|------|--------|-----------|-----------|
| T1 | 100 | 70 | 85 |
| T2 | 500 | 350 | 425 |
| T3 | 2,000 | 1,400 | 1,700 |
| T4 | 10,000 | 7,000 | 8,500 |

**Diminishing-returns curve (agreed user 2026-04-29): accelerating — gets worse and worse toward 85%.** Let `p` = current pool as a fraction of the tier budget. The effective value of the next perm-buff point =

```
clamp((0.85 - p) / (0.85 - 0.70), 0, 1) ** 2      # squared = accelerating falloff
```

| Pool (% of budget) | Effective value of next point |
|--------------------|-------------------------------|
| ≤ 70% | 100% |
| 75% | ~44% |
| 77.5% | 25% |
| 80% | ~11% |
| 85% | 0% (hard cap — blocked) |

The exponent (2) controls how sharply it dives; bump it higher if you want it even steeper. `[CONFIRM]` exponent value only.

- **DM override of the hard block: YES** (confirmed user 2026-04-29).
- Does **not** count toward budget/progress.

### 1.6 Implementation note — new data tracking required

To compute all of the above, the character data must track point **sources** separately (new fields, with backward-compatible defaults so old saves still load):

- `normal_earned_lifetime` — total normal points ever earned (drives the 50% bonus).
- `normal_spent` (or derive from stats minus baseline minus other sources) — for budget/progress.
- `tierup_bonus_pool` — granted / spent / remaining.
- `perm_buff_pool_total` — running sum for the cap.

Today stats are stored as flat integers with no source breakdown, so this bookkeeping is the main new plumbing for Section 1. `[CONFIRM]` exact field design when we implement.

---

## 2. Tier Dice Ranges — DROPPED (not a tier rule)

**Decision (user 2026-04-29): tier dice ranges are not a meaningful tier mechanic and will NOT be enforced or gated.** Damage is shaped by stats (PBD/Precision/Mana Density), slot multipliers, and effects — the raw die size doesn't carry tier balance, so there is no value in restricting it.

Consequences:
- **No** validation, warning, or gating based on die size vs. tier anywhere (authoring, slotting, or equipping).
- The existing `TIER_DICE` table stays **only** as an internal default the spell *generator* uses to have something to roll. It gates nothing and is not a "rule." No code change required unless we later rework the generator.
- Nothing else in tier_rules depends on dice ranges.

---

## 3. Ability Slot Caps Per Tier

**Decision (user 2026-04-29): slots scale by tier and keep growing every tier (no cap).**

Starting counts at T1 and growth:
- **Core:** start 7, **+1 every 2 tiers** (first bump at T3, then T5, T7…)
- **Inner:** start 9, **+1 per tier**
- **Outer:** start 11, **+2 per tier**

Formulas (tier number `n`, where T1 = 1):

```
core_max  = 7  + floor((n - 1) / 2)
inner_max = 9  + (n - 1)
outer_max = 11 + 2 * (n - 1)
```

| Tier | Core | Inner | Outer |
|------|------|-------|-------|
| T1 | 7 | 9 | 11 |
| T2 | 7 | 10 | 13 |
| T3 | 8 | 11 | 15 |
| T4 | 8 | 12 | 17 |
| T5 | 9 | 13 | 19 |
| T6 | 9 | 14 | 21 |

**Rules:**
- When a character's tier changes, `skills.{core,inner,outer}.max` are recomputed from the formulas for the new tier.
- **Tiering down never deletes slotted abilities** — if a demote drops a cap below what's slotted, the extras sit "over cap" (flagged) until the player removes them; nothing auto-deletes.
- No upper tier cap — slots keep climbing with `n`.

**Migration (confirmed user 2026-04-29):** the current default template uses Core 2 / Inner 5 / Outer 9. On load, a character's slot maxes are **recomputed from its tier** via the formulas above (old hand-set maxes are replaced by the tier-derived values).

**Scope (user 2026-04-29):** the world has up to **50 tiers**, but we are **only building/testing logic for T1–T5 at this stage**. The formulas extend cleanly to any `n`, but no special-case logic beyond T5 will be added now.

---

## 4. `min_tier` Field — Items and Abilities — DROPPED (not needed)

**Decision (user 2026-04-29): no `min_tier` gating on items or abilities.** Equipment is handed out by the DM, who can apply narrative strain when a character uses gear/abilities above their tier. No field, no editor control, no warning, no enforcement.

This also removes the `min_tier` filter that earlier appeared in the Section 6 mob-generator notes.

---

## 5. Cross-Tier Effects (for Status Effects, prompt Section 3)

**Decision (user 2026-04-29): exponential scaling, base 2, fail when the effect would do nothing.**

When a status effect (buff/debuff) is applied from a source of one tier to a target of another tier, its potency is scaled exponentially:

```
gap  = source_tier - target_tier        # T1=1, T2=2, ... ; can be negative
mult = 2 ** gap                          # always > 0, never negative
```

| gap | mult |
|-----|------|
| +3 | 8.0× |
| +2 | 4.0× |
| +1 | 2.0× |
| 0 | 1.0× |
| −1 | 0.50× |
| −2 | 0.25× |
| −3 | 0.125× |
| −4 | 0.0625× |

**Applies to potency:** every `stat_modifier` value and the `dot_damage` / `dot_healing` of the effect (and any %-based effect like a slow).

**Fail condition (emergent, not a fixed tier cutoff):** after scaling and rounding, if the effect produces **no actual change** — a slow that rounds to 0%, a stat mod that rounds to 0, DoT/HoT that rounds to 0 — the effect is **dropped** (not applied / removed if already present). Consequence: a player's *strong* debuff on a much-higher-tier boss still does a little, but a *weak* one fizzles to nothing and drops. This is what keeps players viable when fighting up without a hard "−3 = always nothing" wall.

**Frozen at apply time:** `mult` is computed once when the effect is applied and stored on the active effect record, so changing a combatant's tier mid-fight doesn't retroactively rescale existing effects.

**Duration (confirmed user 2026-04-29): NOT scaled.** Duration (turns) stays as authored; only **potency** scales by `2^gap`, and the do-nothing rule is what drops an effect. A high-tier source's effect does not last longer on a low-tier target — it just hits harder.

---

## 6. Equipment Tier Tags in the Mob Generator — MOOT

This section depended on `min_tier` (Section 4, dropped) and tier dice bands (Section 2, dropped), so there is nothing tier-rule-specific for the generator to enforce. The general mob-generator bug audit (prompt.md Section 2) is tracked separately and is unaffected by tier rules.

---

## 7. Tier Advancement UI

**Decisions (user 2026-04-29):** player-driven advance only; **no demotion exists** (no Lower Tier button, no demote logic anywhere); tier-up bonus goes to a **separate spendable pool**.

UX:
- An **"Advance Tier"** button appears (for the player, not DM-gated) **only when the character is eligible to tier up** (eligibility rule — see `[CONFIRM]` below).
- Click → confirmation dialog summarizing the T(n) → T(n+1) changes:
  - Point **budget**: e.g. "500 → 2,000"
  - **Tier-up bonus granted**: e.g. "+250 bonus points (50% of your 500 normal earned)" → added to the separate **tier-up bonus pool** (spendable; never counts toward budget/progress — Section 1.4)
  - New **ability slots**: e.g. "Core 7→8, Inner 10→11, Outer 13→15"
  - New **perm-buff pool cap**: e.g. "soft 350→1,400, hard 425→1,700"
  - Reassurance line: "No stats reset. No abilities removed."
- On confirm: `char.tier = next_tier`; grant bonus into the bonus pool; recompute slot maxes (Section 3) and perm-buff caps (Section 1.5); save; refresh.
- **No demotion.** There is intentionally no way to lower a tier.

**Eligibility (confirmed user 2026-04-29):** the Advance button **appears automatically once the character reaches the tier cap** (`normal_points_spent >= tier_budget`, i.e. Peak). Clicking it raises a **confirmation prompt** ("Are you sure you want to advance to T(n+1)?").

**Advancing is optional.** A character may stay at the peak of their tier indefinitely — there are in-world story reasons a character would choose not to tier up. The button is an availability, never a forced/automatic transition. (This is also why the progress bar never reads as "done" — a peak character is still playing and growing.)

---

## 8. Things Explicitly NOT Changing

For your peace of mind, here's what tier work will **not** touch:

- Mana Density, PBD, Precision multiplier formulas
- Physical Defense flat DR (`DR = floor(phys_def / 5)`)
- Glancing Blow / Hit Quality curves
- Damage pipeline ordering
- Stat names, costs (1 pt = +1), or HP/Mana point-cost soft caps
- Existing JSON files — all backward compat via defaults

---

## Status Summary (refined with user 2026-04-29)

| # | Section | Status |
|---|---------|--------|
| 1 | Stat points, tier budgets, progress bar | **Agreed** (T budgets 100/500/2,000/10,000; baseline free; cumulative tier-up bonus; vague player bar / exact DM number; bar never reads "done") |
| 1.5 | Perm-buff consumable cap | **Agreed** — soft 70% / accelerating (squared) diminishing 70–85% / hard 85% of budget, DM override |
| 2 | Tier dice ranges | **Dropped** |
| 3 | Ability slot caps | **Agreed** — scale per tier, no cap (Core 7 +1/2tiers, Inner 9 +1/tier, Outer 11 +2/tier); recompute maxes from tier on load |
| 4 | `min_tier` on items/abilities | **Dropped** |
| 5 | Cross-tier effect scaling | **Agreed** — `2^gap` potency only (duration unscaled), fail when it rounds to nothing |
| 6 | Mob-gen tier tags | **Moot** |
| 7 | Tier advancement UI | **Agreed** — player advance only (no demotion), button at cap + confirm, optional, bonus to separate pool |

**Scope:** world has up to 50 tiers; only T1–T5 logic is being built now.

### Remaining open items (implementation-time polish only)
- `[CONFIRM]` 1.5 taper **exponent** (squared by default; raise for steeper).
- `[CONFIRM]` 1.3 "keep inching" bar visual.

**T5 budget = 50,000** (confirmed user 2026-04-29). Design is **fully locked**. Implementation is significant new plumbing (point-source tracking on characters, save/load migration, progress bar UI, perm-buff pool, tier-up flow) — recommend building in stages.
