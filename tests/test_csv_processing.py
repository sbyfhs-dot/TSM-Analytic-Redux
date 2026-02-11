from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tsm_analytics.csv_processing import ColumnMapping, format_copper, normalize_sales_data, parse_item_id


class CsvProcessingTests(unittest.TestCase):
    def test_parse_item_string(self):
        self.assertEqual(parse_item_id("i:4306"), 4306)
        self.assertEqual(parse_item_id("item:i:14047"), 14047)
        self.assertIsNone(parse_item_id("foo"))

    def test_copper_formatting(self):
        self.assertEqual(format_copper(150), "1s 50c")
        self.assertEqual(format_copper(665), "6s 65c")
        self.assertEqual(format_copper(10500), "1g 5s 0c")

    def test_total_calculation(self):
        csv_data = "soldAt,price,itemString,qty\n1700000000,150,i:4306,3\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "sales.csv"
            csv_path.write_text(csv_data, encoding="utf-8")
            frame = normalize_sales_data(
                str(csv_path),
                ColumnMapping(timestamp="soldAt", price="price", item="itemString", quantity="qty"),
                item_name_map={"4306": "Silk Cloth"},
            )

        row = frame.iloc[0]
        self.assertEqual(int(row["price_copper"]), 150)
        self.assertEqual(int(row["quantity"]), 3)
        self.assertEqual(int(row["total_copper"]), 450)
        self.assertEqual(row["price_display"], "1s 50c")
        self.assertEqual(row["total_display"], "4s 50c")


if __name__ == "__main__":
    unittest.main()
