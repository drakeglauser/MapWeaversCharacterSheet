# Major Update Plan - v3.0

> Living document - add new items as they come up. Each section has a checklist to track progress.

---

## 1. Tier System Implementation

The tier field exists on characters (`T1`-`T4`) but doesn't mechanically enforce or gate anything yet. This update makes tier a first-class system.

### Steps

- [ ] **1.1 Define tier rules document** - Formalize what each tier unlocks/restricts:
  - Stat soft-cap warnings per tier (e.g., T1 warns above 80, T2 above 300)
  - Allowed dice ranges per tier for abilities/spells
  - Ability slot scaling per tier (e.g., T1 gets fewer outer slots)
  - Equipment tier tags - items can require a minimum tier to equip
- [ ] **1.2 Add tier field to items** - New `"min_tier"` field on item schema so gear can be tier-gated
  - Update `ensure_item_obj()` for backward compatibility (default `"min_tier": "T1"`)
  - Enforce tier check when equipping - show warning if character tier is below item requirement
- [ ] **1.3 Add tier field to abilities/spells** - New `"min_tier"` on ability schema
  - Update spell library entries with appropriate tier tags
  - Enforce tier check when slotting abilities
- [ ] **1.4 Tier-based stat warnings in Overview tab** - When a stat exceeds the soft-cap for the character's current tier, highlight it (yellow/orange) as a visual cue
- [ ] **1.5 Tier-aware mob generator** - The generator already uses tier for stat ranges, but verify it respects all new tier rules (equipment tier tags, ability tier tags) when auto-building NPCs/monsters
- [ ] **1.6 Tier advancement UI** - Add a way for the user to advance a character's tier, with a summary of what changes (new stat caps, unlocked slots, etc.)

---

## 2. NPC/Monster Generator Bug Fixes

### Known Issues to Investigate & Fix

- [ ] **2.1 Audit `generate_mob_character()`** - Walk through the full generation path and document every place it can fail silently or produce bad data
- [ ] **2.2 Equipment assignment failures** - Generated mobs sometimes have missing or malformed equipment; verify `ensure_item_obj()` is called on all generated items
- [ ] **2.3 Spell assignment failures** - Generated mobs can end up with spells that don't match their tier or tags; validate spell selection logic against tier dice ranges
- [ ] **2.4 Stat weight edge cases** - When multiple conflicting tags are selected (e.g., Melee + Magic), verify the weight merging produces reasonable results instead of flattening everything
- [ ] **2.5 Preview display bugs** - Verify the right-panel preview text renders all fields correctly, especially after schema changes from this update
- [ ] **2.6 "Open in Tab" consistency** - Ensure a generated mob opened in a character tab has all fields populated and functional (no missing keys, no stale references)

---

## 3. Status Effects System (Tier-Scaled)

A new system for temporary status effects (buffs/debuffs) that scale with tier.

### Steps

- [ ] **3.1 Design status effect schema** - Define the data structure:
  ```
  {
    "name": str,              # e.g., "Burning", "Poisoned", "Blessed"
    "effect_type": "buff|debuff|neutral",
    "duration": int,          # turns remaining (-1 for permanent until removed)
    "tier": "T1|T2|T3|T4",   # tier of the source that applied it
    "stat_modifiers": [       # same format as item stat_boosts
      {"stat": str, "value": int, "mode": "flat|percent"}
    ],
    "dot_damage": int,        # damage per turn (0 if none)
    "dot_healing": int,       # healing per turn (0 if none)
    "stacks": int,            # current stack count
    "max_stacks": int,        # max allowed stacks
    "source": str             # what applied this effect
  }
  ```
- [ ] **3.2 Tier scaling rules for status effects** - Define how tier affects potency:
  - Higher tier source = stronger effect values
  - Cross-tier resistance: effects from a lower tier source have reduced duration/potency against higher tier targets
  - Same-tier: full effect
  - Define the specific scaling multipliers per tier gap
- [ ] **3.3 Add `"status_effects"` to character data** - New field in character template, default empty list
  - Update `default_character_template()` and JSON save/load with backward compatibility
- [ ] **3.4 Status effect application logic** - Functions to add, remove, tick (reduce duration), and stack effects
  - Apply stat modifiers from active effects into `_compute_equipment_boosts()` alongside item boosts and ability buffs
  - Process DoT damage/healing per turn
- [ ] **3.5 Status Effects UI panel** - Add a visible list of active status effects on the Overview tab or a new sub-panel
  - Show name, remaining duration, source, stat changes
  - Allow manual add/remove for DM control
- [ ] **3.6 Predefined status effect library** - Create a set of common effects:
  - **Debuffs:** Burning, Poisoned, Frozen, Stunned, Blinded, Cursed, Weakened
  - **Buffs:** Blessed, Haste, Shield, Regeneration, Empowered, Fortified
  - Each with tier-appropriate default values
- [ ] **3.7 Integrate with Battle Sim** - Status effects should tick and apply during simulated combat rounds

---

## 4. Held Weapons on Body Map & Equipment

Currently the body map shows armor slots only. Add weapon slots so held weapons are visible and manageable from the body map.

### Steps

- [ ] **4.1 Add weapon slots to body map** - New slots:
  - Main Hand (right hand area)
  - Off Hand (left hand area)
  - These are separate from the Gauntlets/Hands armor slots
- [ ] **4.2 Update `_body_slot_regions`** - Add hit-test regions for the weapon slots on the humanoid silhouette, positioned near the hands but visually distinct (e.g., extending outward from the hand)
- [ ] **4.3 Draw weapon indicators on body model** - Render weapon icons or shapes at the hand positions when weapons are equipped
- [ ] **4.4 Weapon equip logic** - When a weapon-type item is assigned to Main Hand or Off Hand:
  - Apply its `stat_boosts` like any other equipped item
  - Mark it as the active weapon for damage calculations
  - Enforce one weapon per hand
- [ ] **4.5 Dual-wield / two-handed support** - Decide rules:
  - Two-handed weapons occupy both Main Hand and Off Hand
  - Dual-wield: separate weapons in each hand
  - UI should prevent equipping a second weapon if a two-handed weapon is held
- [ ] **4.6 Update Damage Lab & Battle Sim** - Weapon selection in damage calculations should pull from equipped weapon slots rather than requiring manual selection
- [ ] **4.7 Distinguish weapon items from armor items** - Add `"item_type": "weapon|armor|accessory|consumable"` field to item schema (backward compatible default based on existing fields)

---

## 5. Fix: Negative Effect Items Not Modifying Stats

Items with negative `stat_boosts` values (e.g., a cursed ring with `-5 melee_acc`) are not correctly reducing stats.

### Steps

- [ ] **5.1 Trace `_compute_equipment_boosts()`** - Identify where negative values are being dropped or zeroed out
  - Check if there's a `max(0, ...)` or absolute value call that strips negatives
  - Check if the UI display logic filters out negative boosts
- [ ] **5.2 Fix the calculation** - Ensure negative flat and negative percent boosts are summed correctly into the totals
- [ ] **5.3 Fix the display** - Negative boosts should show in red on the Overview tab and Body Map slot details
- [ ] **5.4 Test cases** - Verify with:
  - Item with `-10 flat melee_acc` reduces displayed and effective melee_acc by 10
  - Item with `-20% percent phys_def` reduces displayed and effective phys_def by 20%
  - Mixed positive and negative boosts on different items sum correctly

---

## 6. Fix: Effects Not Applied Until Item Update After Equip

When an item is equipped, its stat boosts don't take effect until the item is edited/updated. Stats should refresh immediately on equip.

### Steps

- [ ] **6.1 Identify the refresh gap** - Trace the equip action flow:
  - Where does equipping an item happen? (Body Map click, Inventory action, etc.)
  - After equipping, is `_compute_equipment_boosts()` called?
  - After computing boosts, is the Overview tab refreshed?
- [ ] **6.2 Add refresh calls after every equip/unequip action** - Ensure `_compute_equipment_boosts()` + UI refresh is triggered:
  - On equip via Body Map
  - On equip via Inventory tab
  - On unequip / swap
  - On item removal from equipment list
- [ ] **6.3 Add refresh calls after ability slot changes** - Same issue may exist for ability passive buffs:
  - Slotting a passive ability should immediately apply its boosts
  - Removing a passive ability should immediately remove its boosts
- [ ] **6.4 Verify with edge cases:**
  - Equip item -> stats update immediately (no save/load or edit needed)
  - Swap item in slot -> old boosts removed, new boosts applied
  - Remove item from slot -> boosts removed immediately
  - Equip item with both positive and negative boosts -> both applied

---

## 7. Future Ideas (Add Here)

_Space for additional features and fixes as they come up._

- [ ] ...
- [ ] ...
- [ ] ...

---

## Priority Order (Suggested)

1. **Bug fixes first** (Sections 5 & 6) - Fix stat modification bugs so the foundation is solid
2. **Tier system** (Section 1) - Core system that other features depend on
3. **Status effects** (Section 3) - Builds on tier system
4. **Held weapons** (Section 4) - Body map enhancement
5. **Mob generator fixes** (Section 2) - Can be done alongside other work, but best after tier system is in place so generated mobs use tier rules
