"""Unit tests for stat-buff math and core formulas.

Run with:  python -m unittest test_buffs -v

These cover the buff bugs fixed in v3.0 work:
  - negative flat boosts reduce stats
  - percent boosts (positive and negative)
  - +X% and -X% of equal magnitude are symmetric (no harsher penalty)
  - mixed flat + percent and conflicting percents combine correctly
Plus a few baseline formula checks from Context_AI_Rules.md.
"""

import unittest

import sheet_tool as st


class TestApplyBoostValue(unittest.TestCase):
    def test_no_boost(self):
        self.assertEqual(st.apply_boost_value(40, 0, 0), 40)

    def test_positive_flat(self):
        self.assertEqual(st.apply_boost_value(40, 10, 0), 50)

    def test_negative_flat(self):
        # -10 flat melee_acc on base 40 -> 30
        self.assertEqual(st.apply_boost_value(40, -10, 0), 30)

    def test_positive_percent(self):
        # +50% on base 40 -> 60
        self.assertEqual(st.apply_boost_value(40, 0, 50), 60)

    def test_negative_percent(self):
        # -20% phys_def on base 100 -> 80
        self.assertEqual(st.apply_boost_value(100, 0, -20), 80)

    def test_final_output_is_rounded(self):
        # Only the final value is rounded (ties away from zero); fractional
        # flat / percent contributions are not truncated away.
        self.assertEqual(st.apply_boost_value(10, 0, 25), 13)   # 12.5 -> 13
        self.assertEqual(st.apply_boost_value(15, 0, 5), 16)    # 15.75 -> 16
        self.assertEqual(st.apply_boost_value(10, 2.5, 0), 13)  # 12.5 flat -> 13
        self.assertEqual(st.apply_boost_value(10, 0, -25), 8)   # 7.5 -> 8

    def test_conflicting_percents_cancel(self):
        # A +50% and a -50% on the same stat net to zero change.
        self.assertEqual(st.apply_boost_value(100, 0, 0), 100)
        self.assertEqual(st.apply_boost_value(100, 0, 50 - 50), 100)

    def test_mixed_flat_and_percent(self):
        # base 100, +10 flat, +20% -> 100 + 10 + 20 = 130
        self.assertEqual(st.apply_boost_value(100, 10, 20), 130)

    def test_mixed_positive_and_negative(self):
        # base 100, +20 flat, -50% -> 100 + 20 - 50 = 70
        self.assertEqual(st.apply_boost_value(100, 20, -50), 70)

    def test_round_half_away_symmetry(self):
        self.assertEqual(st._round_half_away(2.5), 3)
        self.assertEqual(st._round_half_away(-2.5), -3)
        self.assertEqual(st._round_half_away(1.4), 1)
        self.assertEqual(st._round_half_away(-1.4), -1)


class TestBaselineFormulas(unittest.TestCase):
    def test_parse_damage_expr(self):
        # NOTE: the active parse_damage_expr (sheet_tool.py:1707) returns
        # (0,0,0) on invalid input and only strips leading/trailing space.
        # Internal spaces around the bonus are NOT handled. (There is also a
        # dead earlier definition at line 526 that the second one shadows.)
        self.assertEqual(st.parse_damage_expr("1d10"), (1, 10, 0))
        self.assertEqual(st.parse_damage_expr("2d6+3"), (2, 6, 3))
        self.assertEqual(st.parse_damage_expr("3d8-2"), (3, 8, -2))
        self.assertEqual(st.parse_damage_expr("  2d6+3  "), (2, 6, 3))
        self.assertEqual(st.parse_damage_expr("not dice"), (0, 0, 0))

    def test_mana_density_multiplier(self):
        self.assertAlmostEqual(st.mana_density_multiplier(0), 1.0)
        self.assertAlmostEqual(st.mana_density_multiplier(71), 1.71, places=2)
        self.assertAlmostEqual(st.mana_density_multiplier(100), 2.0)
        self.assertGreater(st.mana_density_multiplier(1000), st.mana_density_multiplier(100))

    def test_phys_dr(self):
        self.assertEqual(st.phys_dr_from_points(0), 0)
        self.assertEqual(st.phys_dr_from_points(4), 0)
        self.assertEqual(st.phys_dr_from_points(5), 1)
        self.assertEqual(st.phys_dr_from_points(9), 1)
        self.assertEqual(st.phys_dr_from_points(10), 2)
        self.assertEqual(st.phys_dr_from_points(14), 2)


class TestTierHelpers(unittest.TestCase):
    def test_tier_num(self):
        self.assertEqual(st.tier_num("T3"), 3)
        self.assertEqual(st.tier_num(4), 4)
        self.assertEqual(st.tier_num("5"), 5)
        self.assertEqual(st.tier_num("garbage"), 1)
        self.assertEqual(st.tier_num(0), 1)

    def test_tier_budget_and_floor(self):
        self.assertEqual(st.tier_budget(1), 100)
        self.assertEqual(st.tier_budget(2), 500)
        self.assertEqual(st.tier_budget(5), 50000)
        self.assertEqual(st.tier_budget(99), 50000)  # clamps to max defined
        self.assertEqual(st.tier_floor(1), 0)
        self.assertEqual(st.tier_floor(2), 100)
        self.assertEqual(st.tier_floor(3), 500)

    def test_tier_slot_maxes(self):
        self.assertEqual(st.tier_slot_maxes(1), {"core": 7, "inner": 9, "outer": 11})
        self.assertEqual(st.tier_slot_maxes(2), {"core": 7, "inner": 10, "outer": 13})
        self.assertEqual(st.tier_slot_maxes(3), {"core": 8, "inner": 11, "outer": 15})
        self.assertEqual(st.tier_slot_maxes(5), {"core": 9, "inner": 13, "outer": 19})

    def test_perm_buff_caps(self):
        self.assertEqual(st.perm_buff_caps(1), (70, 85))
        self.assertEqual(st.perm_buff_caps(2), (350, 425))

    def test_perm_buff_point_value(self):
        # T1 budget 100: full value below 70, zero at/after 85, squared taper between.
        self.assertEqual(st.perm_buff_point_value(0, 1), 1.0)
        self.assertEqual(st.perm_buff_point_value(70, 1), 1.0)
        self.assertEqual(st.perm_buff_point_value(85, 1), 0.0)
        self.assertEqual(st.perm_buff_point_value(90, 1), 0.0)
        # at 77.5% -> ((0.85-0.775)/0.15)^2 = 0.5^2 = 0.25
        self.assertAlmostEqual(st.perm_buff_point_value(77.5, 1), 0.25, places=3)

    def test_cross_tier_mult(self):
        self.assertEqual(st.cross_tier_mult("T2", "T2"), 1.0)
        self.assertEqual(st.cross_tier_mult("T3", "T1"), 4.0)   # +2 gap
        self.assertEqual(st.cross_tier_mult("T1", "T3"), 0.25)  # -2 gap
        self.assertEqual(st.cross_tier_mult("T1", "T4"), 0.125)

    def test_tierup_bonus_points(self):
        self.assertEqual(st.tierup_bonus_points(100), 50)
        self.assertEqual(st.tierup_bonus_points(501), 250)
        self.assertEqual(st.tierup_bonus_points(0), 0)

    def test_apply_perm_buff_gain_below_soft(self):
        # T1 budget 100, soft 70: full value while pool stays under 70.
        gain, new_pool, applied = st.apply_perm_buff_gain(0, 1, 10)
        self.assertEqual((gain, new_pool, applied), (10, 10, 10))

    def test_apply_perm_buff_gain_hard_block(self):
        # Pool already at hard cap (85): nothing applies.
        gain, new_pool, applied = st.apply_perm_buff_gain(85, 1, 10)
        self.assertEqual((gain, new_pool, applied), (0, 85, 0))

    def test_apply_perm_buff_gain_partial_into_cap(self):
        # Pool 80 of T1: only 5 nominal points fit before the hard cap at 85.
        gain, new_pool, applied = st.apply_perm_buff_gain(80, 1, 20)
        self.assertEqual(new_pool, 85)
        self.assertEqual(applied, 5)
        self.assertLess(gain, 5)  # diminished in the 70-85 zone

    def test_apply_perm_buff_gain_diminishes(self):
        # Crossing into the soft zone yields less than nominal.
        gain, new_pool, applied = st.apply_perm_buff_gain(65, 1, 10)
        self.assertEqual((new_pool, applied), (75, 10))
        self.assertLess(gain, 10)

    def test_tier_progress(self):
        # T1: floor 0, ceil 100
        frac, label = st.tier_progress(0, 1)
        self.assertEqual(label, "Bottom")
        frac, label = st.tier_progress(100, 1)
        self.assertEqual((frac, label), (1.0, "Peak"))
        # T3: floor 500, ceil 2000 -> 1100 spent = (1100-500)/1500 = 0.4 -> Mid
        frac, label = st.tier_progress(1100, 3)
        self.assertAlmostEqual(frac, 0.4, places=3)
        self.assertEqual(label, "Mid")
        # T3 at 1600 -> (1600-500)/1500 = 0.733 -> High
        _, label = st.tier_progress(1600, 3)
        self.assertEqual(label, "High")


class TestTierMigration(unittest.TestCase):
    def test_migrate_backfills_and_recomputes(self):
        # Old save: no tier_points, stale skills maxes, tier T2.
        char = {"tier": "T2", "skills": {"core": {"current": 1, "max": 2}}}
        st._migrate_tier_schema(char)
        self.assertEqual(char["tier_points"]["normal_earned_lifetime"], 0)
        self.assertEqual(char["tier_points"]["tierup_bonus_pool"], 0)
        self.assertEqual(char["tier_points"]["perm_buff_pool"], 0)
        # slot maxes recomputed from T2; current preserved
        self.assertEqual(char["skills"]["core"], {"current": 1, "max": 7})
        self.assertEqual(char["skills"]["inner"]["max"], 10)
        self.assertEqual(char["skills"]["outer"]["max"], 13)

    def test_migrate_flags_old_save_for_history_prompt(self):
        # No tier_points block => predates tracking => initialized False (will prompt).
        char = {"tier": "T1"}
        st._migrate_tier_schema(char)
        self.assertFalse(char["tier_points"]["initialized"])

    def test_migrate_keeps_initialized_when_present(self):
        # Already-tracked save keeps its flag and is not re-prompted.
        char = {"tier": "T1", "tier_points": {"normal_earned_lifetime": 80, "initialized": True}}
        st._migrate_tier_schema(char)
        self.assertTrue(char["tier_points"]["initialized"])
        self.assertEqual(char["tier_points"]["normal_earned_lifetime"], 80)

    def test_migrate_is_idempotent(self):
        char = {"tier": "T1"}
        st._migrate_tier_schema(char)
        first = dict(char["tier_points"])
        st._migrate_tier_schema(char)
        self.assertEqual(char["tier_points"], first)
        self.assertEqual(char["skills"]["outer"]["max"], 11)


if __name__ == "__main__":
    unittest.main()
