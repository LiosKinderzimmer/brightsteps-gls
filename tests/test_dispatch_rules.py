import unittest
from datetime import date

from brightsteps_gls.services.domain import OrderAvailability, decide_dispatch, workdays_between


def order(name, group="Vertriebspartner", address="A", ordered=10, available=5, value=100, day=date(2026, 9, 1)):
    return OrderAvailability(name, group, address, day, ordered, available, value)


class DispatchRuleTests(unittest.TestCase):
    def test_end_customer_waits_for_complete_order(self):
        decision = decide_dispatch([order("SO-1", "Endkunde")], date(2026, 9, 10))[0]
        self.assertFalse(decision.release)
        self.assertIn("Gesamtlieferung", decision.reason)

    def test_complete_order_is_released_below_minimum(self):
        decision = decide_dispatch([order("SO-1", ordered=2, available=2, value=5)], date(2026, 9, 2))[0]
        self.assertTrue(decision.release)

    def test_address_pool_combines_separate_orders(self):
        decisions = decide_dispatch(
            [order("SO-1", value=80), order("SO-2", value=75)], date(2026, 9, 2)
        )
        self.assertTrue(all(row.release for row in decisions))

    def test_different_addresses_do_not_share_minimum(self):
        decisions = decide_dispatch(
            [order("SO-1", address="A", value=80), order("SO-2", address="B", value=75)],
            date(2026, 9, 2),
        )
        self.assertFalse(any(row.release for row in decisions))

    def test_kindergarten_complete_ships_immediately(self):
        decision = decide_dispatch(
            [order("SO-1", "Kindergarten", ordered=2, available=2, value=5)], date(2026, 9, 2)
        )[0]
        self.assertTrue(decision.release)

    def test_kindergarten_partial_waits_five_workdays(self):
        early = decide_dispatch([order("SO-1", "Kindergarten", value=200)], date(2026, 9, 4))[0]
        late = decide_dispatch([order("SO-1", "Kindergarten", value=200)], date(2026, 9, 8))[0]
        self.assertFalse(early.release)
        self.assertTrue(late.release)

    def test_holiday_does_not_count_as_workday(self):
        self.assertEqual(workdays_between(date(2026, 9, 1), date(2026, 9, 8), [date(2026, 9, 7)]), 4)

    def test_zero_stock_is_never_released(self):
        decision = decide_dispatch([order("SO-1", ordered=1, available=0, value=0)], date(2026, 9, 8))[0]
        self.assertFalse(decision.release)


if __name__ == "__main__":
    unittest.main()
