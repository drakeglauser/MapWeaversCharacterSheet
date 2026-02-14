# AI Agent Development Rules (Project Context)

This is the “contract” for any AI agent working on this codebase.

## Non-negotiables
1) DO NOT change gameplay mechanics or formulas without asking first.
   - Examples: damage scaling, mana density formula, DR rule, hit-quality curve, crit behavior.

2) Prefer minimal, local changes.
   - If a change can be done by editing 1–2 methods, do that.
   - Avoid refactors that touch unrelated code.

3) Do not add “extra” features unless explicitly requested.
   - User has been docked points before for extra code.

4) Preserve JSON compatibility.
   - Players may have old character files. If new fields are added:
     - Provide defaults in ensure_* functions
     - Never break loading older JSONs

5) Keep dependencies minimal.
   - Prefer stdlib.
   - Avoid adding new packages unless asked (especially for GUI).

## Testing requirements (always do this when editing logic)
When adding/changing core logic, add basic tests.
Minimum tests to include (as applicable):
- parse_damage_expr: handles "1d10", "2d6+3", "3d8-2", whitespace, invalid strings
- mana_density_multiplier:
  - 0 -> 1.0x
  - 71 -> 1.71x (or very close if float formatting)
  - 100 -> 2.0x
  - monotonic growth beyond 100
- Physical Defense DR:
  - 0..4 => DR 0
  - 5..9 => DR 1
  - 10..14 => DR 2
- PBD / Precision multiplier:
  - Same formula as Mana Density (1.0 + pts/100 up to 100, then log)
  - Both are regular stats (1 point per +1, no soft caps)

Preferred test style:
- Use Python’s built-in unittest unless the user explicitly wants pytest.
- Keep tests deterministic (no randomness).
- Keep tests small and targeted.

## UI rules (Tkinter)
- Avoid large UI rewrites.
- If you add a button/field:
  - Keep layout consistent (LabelFrame, grid/pack patterns already used)
  - Don’t move or rename existing UI elements without approval

## Delivery rules for code responses
- If user asks for “full file”, return the full file.
- If user asks for “small fixes”, return only the methods (or minimal patches).
- Be explicit about where each snippet goes (method name, class, file name).
- Avoid introducing unused imports / unused functions.

## Data schema rules
If adding new fields to items/abilities:
- Update ensure_item_obj / ensure_ability_obj to backfill defaults
- Update save logic so it writes the field
- Update UI edit panel so it can edit the field
- Keep field names stable once introduced

## Safety / stability checks before final output
Before providing code changes:
- Confirm no syntax errors
- Confirm it runs without new external dependencies
- Confirm old JSON files still load
- Confirm new logic has at least a minimal test

## “Ask first” list
These require explicit confirmation before implementation:
- Any change to combat resolution rules (hit chance, crit rules, action economy)
- Any change to scaling formulas (mana density, overcast, PBD/Precision multipliers)
- Any new stat meaning or new stat added/removed
- Any new file format or export/import behavior beyond simple JSON copy/paste

End of document.
