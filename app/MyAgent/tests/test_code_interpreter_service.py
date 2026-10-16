import unittest

from code_interpreter_service import _validate_file_name


class GeneratedFileNameTests(unittest.TestCase):
    def test_accepts_safe_english_file_names(self):
        for file_name in ("report.xlsx", "monthly_sales-2026.csv", "aircon_01.pdf"):
            with self.subTest(file_name=file_name):
                _validate_file_name(file_name)

    def test_rejects_non_ascii_spaces_and_uppercase_letters(self):
        for file_name in ("売上.xlsx", "monthly report.xlsx", "Report.xlsx"):
            with self.subTest(file_name=file_name), self.assertRaises(ValueError):
                _validate_file_name(file_name)


if __name__ == "__main__":
    unittest.main()
