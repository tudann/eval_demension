from __future__ import annotations

import csv
import unittest
from collections import defaultdict
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class CsvDimensionAlignmentTests(unittest.TestCase):
    def test_seven_dimensions_match_csv_secondary_items_exactly(self) -> None:
        config = yaml.safe_load((ROOT / "configs" / "dims_13_18.yaml").read_text(encoding="utf-8"))
        dimensions = config["dimensions"]
        with (ROOT / "data" / "d13_d20_cases.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

        csv_items: dict[str, set[str]] = defaultdict(set)
        csv_names: dict[str, str] = {}
        for row in rows:
            number, name = row["一级维度"].split(". ", 1)
            if number == "19":
                continue
            csv_items[number].add(row["二级维度"])
            csv_names[number] = name

        self.assertEqual(set(csv_items), {"13", "14", "15", "16", "17", "18", "20"})
        self.assertEqual(len(dimensions), 7)
        self.assertEqual(sum(len(items) for items in csv_items.values()), 39)
        for key, dimension in dimensions.items():
            number = key.split("_", 1)[0]
            with self.subTest(dimension=key):
                self.assertEqual(dimension["name_zh"], csv_names[number])
                configured = [subpoint["name_zh"] for subpoint in dimension["subpoints"].values()]
                self.assertEqual(len(configured), len(set(configured)))
                self.assertEqual(set(configured), csv_items[number])
                self.assertTrue(all(subpoint["components"].get("checklist", 0) > 0
                                    for subpoint in dimension["subpoints"].values()))


if __name__ == "__main__":
    unittest.main()
