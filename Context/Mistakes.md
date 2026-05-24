# Bug Log / Fixes

Running log of bugs found and how they were fixed, so we can regression-test in the future.

---

## v3.0 — Stat Buff Fixes (Sections 5 & 6 of prompt.md)

### Fixed

1. **+X% and -X% interacted weirdly / output not rounded cleanly.**
   - Cause: `_apply_boost` used `math.floor(base * pct / 100)` then `int(...)` the sum,
     which floored the percent and truncated the total (dropping fractional flat values).
   - Fix: extracted pure `apply_boost_value(base, flat, pct)` (sheet_tool.py, near
     `_safe_int`). It computes `base + flat + base*pct/100` and rounds the **final
     output** once via `_round_half_away` (ties away from zero). `_apply_boost` delegates.
   - CONFIRMED DESIGN (user, this session): percent is against **base only**; multiple
     percents are **additive** (+50% and -50% net to 0%); only the final value is rounded
     (symmetry of +X% vs -X% is NOT a requirement).

2. **Negative boosts not shown in red.**
   - Overview tab: equip-bonus labels now recolor — red when boosts lower the value,
     green when they raise it, gray when net zero. (Added `Green.TLabel` style + a
     `green` theme color; stored label refs in `self.lbl_equip_bonus` /
     `self.lbl_equip_bonus_res`; logic in `_boost_style_for` +
     `_refresh_equipment_boosts_display`.)
   - Body Map slot details: negative boost lines render red, positive green
     (Text widget tags in `_body_map_click`).

3. **HP/Mana boost label was confusing** (looked like a second buff stacked on top).
   - Reworded to `(+20, -10% boosts → total 110)` so it's clearly the resulting value,
     not an extra buff. Base entry box is never overwritten with the boosted value.

4. **Permanent buff items (consume_perm_stat) hardened.**
   - HP/Mana max perm change now also adjusts current: a gain grants the HP/Mana now,
     a loss re-clamps current down to the new effective max (previously current could
     exceed max). Regular stats clamp to >= 0.
   - Result text shows a signed value (`permanently -5` instead of `permanently +-5`).

### Tests
- `test_buffs.py` (unittest). Run: `python -m unittest test_buffs -v`.
- Covers apply_boost_value (neg flat, neg/pos percent, symmetry, conflicting percents,
  mixed flat+percent), `_round_half_away`, plus baseline parse_damage_expr /
  mana_density / phys_dr from Context_AI_Rules.md.

### Findings NOT fixed (flagged for later, out of scope for buff bugs)
- **Duplicate `parse_damage_expr`**: sheet_tool.py has two definitions (line ~526 and
  ~1707). The second shadows the first. Active one returns `(0,0,0)` on invalid and only
  strips leading/trailing whitespace (internal spaces around the bonus like `2d6 + 3`
  are dropped). Consider de-duping and handling internal whitespace.
- **Section 6 (refresh on equip)**: traced all equip/move/remove/boost paths — they do
  call `_refresh_equipment_boosts_display`. In this app "equipped" for boost purposes =
  item is in the `equipment` category (armor_slot is independent). No live bug found this
  pass; revisit if a concrete repro appears.
