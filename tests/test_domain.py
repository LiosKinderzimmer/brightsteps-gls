import unittest

from brightsteps_gls.services.domain import build_grouping_key, common_package_count


ADDRESS = {
    "name": "Muster GmbH",
    "name2": "Lager 2",
    "country_code": "AT",
    "postal_code": "1010",
    "city": "Wien",
    "street": "Teststraße",
    "street_number": "1",
}


class GroupingTests(unittest.TestCase):
    def test_whitespace_and_case_do_not_split_a_group(self):
        other = dict(ADDRESS, name="  MUSTER   gmbh ", city="WIEN")
        self.assertEqual(
            build_grouping_key("Bright Steps", "2026-09-04", ADDRESS),
            build_grouping_key(" bright steps ", "2026-09-04", other),
        )

    def test_different_date_splits_group(self):
        self.assertNotEqual(
            build_grouping_key("Bright Steps", "2026-09-04", ADDRESS),
            build_grouping_key("Bright Steps", "2026-09-05", ADDRESS),
        )

    def test_different_address_splits_group(self):
        self.assertNotEqual(
            build_grouping_key("Bright Steps", "2026-09-04", ADDRESS),
            build_grouping_key("Bright Steps", "2026-09-04", dict(ADDRESS, street_number="2")),
        )

    def test_common_package_count_is_not_summed(self):
        self.assertEqual(common_package_count([1, 1, 3]), 3)


if __name__ == "__main__":
    unittest.main()

