"""Unit tests for language tagging, redaction, sample allocation and agreement.

Run from the project root:
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import numpy as np  # noqa: E402

from agreement import cohen_kappa, landis_koch  # noqa: E402
from draw_samples import allocate_analysis, allocate_strata, largest_remainder  # noqa: E402
from textproc import dedup_key, redact, tag_language  # noqa: E402


class LanguageTagging(unittest.TestCase):
    def test_bangla(self):
        self.assertEqual(tag_language("টাকা পাঠাতে পারছি না, অ্যাপ বারবার বন্ধ হয়ে যায়")["lang_group"], "bangla")

    def test_bangla_with_a_few_english_words(self):
        text = "বিকাশ অ্যাপে লগইন করতে গেলে বারবার সমস্যা হচ্ছে, OTP আসে না"
        self.assertEqual(tag_language(text)["lang_group"], "bangla")

    def test_english(self):
        self.assertEqual(tag_language("The app crashes every time I try to send money")["lang_group"], "english")

    def test_english_mentioning_taka_once(self):
        self.assertEqual(tag_language("I lost 500 taka and support never answered")["lang_group"], "english")

    def test_romanized(self):
        self.assertEqual(tag_language("ami taka send korte parchi na, app ta kaj kore na")["lang_group"], "romanized")

    def test_short_romanized_with_one_listed_word(self):
        self.assertEqual(tag_language("bkash app open hoina")["lang_group"], "romanized")

    def test_long_code_mixed_romanized(self):
        text = "amar phone e app ta 3 din dhore problem korche ar notun version download korleo thik hoy na"
        self.assertEqual(tag_language(text)["lang_group"], "romanized")

    def test_mixed(self):
        text = "app ta khub slow, টাকা পাঠাতে অনেক সময় লাগে always"
        self.assertEqual(tag_language(text)["lang_group"], "mixed")

    def test_digits_and_emoji_are_ignored(self):
        self.assertEqual(tag_language("Very bad app 😡 100% fraud 2025")["lang_group"], "english")


class Redaction(unittest.TestCase):
    def test_phone_latin_digits(self):
        text, counts = redact("call me at 01712-345678 please")
        self.assertEqual(text, "call me at [PHONE] please")
        self.assertEqual(counts, {"PHONE": 1})

    def test_phone_with_country_code(self):
        self.assertEqual(redact("+8801812345678 is my bkash")[0], "[PHONE] is my bkash")

    def test_phone_bengali_digits(self):
        self.assertEqual(redact("আমার নম্বর ০১৭১২৩৪৫৬৭৮")[0], "আমার নম্বর [PHONE]")

    def test_nid_and_long_numbers(self):
        text, counts = redact("NID 1990123456789 and account 1234567890")
        self.assertEqual(text, "NID [ID_NUMBER] and account [ID_NUMBER]")
        self.assertEqual(counts, {"ID_NUMBER": 2})

    def test_amounts_are_kept(self):
        for amount in ("5000 taka", "10,000 tk", "১০০০০ টাকা", "transaction 100000 taka"):
            self.assertEqual(redact(amount)[0], amount)

    def test_transaction_id_with_keyword(self):
        self.assertEqual(redact("TrxID: 8N7A6B5C4D failed")[0], "TrxID: [TRX_ID] failed")
        self.assertEqual(redact("txn id 71ab3cde")[0], "txn id [TRX_ID]")

    def test_standalone_transaction_code(self):
        self.assertEqual(redact("money gone, BJK5L2M9XQ never arrived")[0], "money gone, [TRX_ID] never arrived")

    def test_plain_capitals_are_kept(self):
        self.assertEqual(redact("WORST APP EVER, PLEASE FIX OTP")[0], "WORST APP EVER, PLEASE FIX OTP")

    def test_email(self):
        self.assertEqual(redact("mail me: someone.name@gmail.com")[0], "mail me: [EMAIL]")

    def test_provider_support_email_is_kept(self):
        text, counts = redact("Please write to support@bkash.com with details.", is_reply=True)
        self.assertEqual(text, "Please write to support@bkash.com with details.")
        self.assertEqual(counts, {})

    def test_reply_greeting_name(self):
        self.assertEqual(redact("Dear Rahim, sorry for the trouble.", is_reply=True)[0],
                         "Dear [NAME], sorry for the trouble.")
        self.assertEqual(redact("Dear Sir, sorry for the trouble.", is_reply=True)[0],
                         "Dear Sir, sorry for the trouble.")


class Dedup(unittest.TestCase):
    def test_case_and_punctuation_insensitive(self):
        self.assertEqual(dedup_key("Very bad app!!!  Money gone."), dedup_key("very bad app money gone"))

    def test_bangla_marks_kept(self):
        self.assertNotEqual(dedup_key("টাকা"), dedup_key("টক"))


class Allocation(unittest.TestCase):
    def test_equal_when_all_have_enough(self):
        self.assertEqual(allocate_analysis({"a": 900, "b": 800, "c": 700, "d": 600}),
                         {"a": 400, "b": 400, "c": 400, "d": 400})

    def test_shortfall_is_shared(self):
        alloc = allocate_analysis({"a": 9000, "b": 5000, "c": 700, "d": 247})
        self.assertEqual(alloc["d"], 247)
        self.assertEqual(sum(alloc.values()), 1600)
        self.assertEqual(sorted(alloc[k] for k in "abc"), [451, 451, 451])

    def test_strata_floor_and_total(self):
        alloc = allocate_strata({"bangla": 60, "english": 300, "mixed": 8, "romanized": 32}, 50, 5,
                                np.random.default_rng(1))
        self.assertEqual(sum(alloc.values()), 50)
        self.assertEqual(alloc["mixed"], 5)
        self.assertGreaterEqual(alloc["romanized"], 5)

    def test_strata_small_group_takes_all(self):
        alloc = allocate_strata({"bangla": 100, "english": 300, "mixed": 2}, 50, 5, np.random.default_rng(1))
        self.assertEqual(alloc["mixed"], 2)
        self.assertEqual(sum(alloc.values()), 50)

    def test_largest_remainder_sums(self):
        alloc = largest_remainder({"a": 12.5, "b": 12.5, "c": 12.5, "d": 12.5}, 50, np.random.default_rng(1))
        self.assertEqual(sum(alloc.values()), 50)
        self.assertEqual(sorted(alloc.values()), [12, 12, 13, 13])


class Agreement(unittest.TestCase):
    def test_unweighted_kappa(self):
        r = cohen_kappa(["y", "y", "n", "n"], ["y", "n", "n", "n"])
        self.assertAlmostEqual(r["observed"], 0.75)
        self.assertAlmostEqual(r["chance"], 0.5)
        self.assertAlmostEqual(r["kappa"], 0.5)

    def test_weighted_kappa(self):
        a, b = ["x", "y", "z", "z"], ["x", "z", "z", "y"]
        self.assertAlmostEqual(cohen_kappa(a, b)["kappa"], 0.2)
        self.assertAlmostEqual(cohen_kappa(a, b, order=["x", "y", "z"])["kappa"], 0.1875 / 0.4375)

    def test_perfect_agreement(self):
        self.assertAlmostEqual(cohen_kappa(["D1", "D2", "N5"], ["D1", "D2", "N5"])["kappa"], 1.0)

    def test_landis_koch_bands(self):
        self.assertEqual(landis_koch(-0.1), "poor")
        self.assertEqual(landis_koch(0.0), "slight")
        self.assertEqual(landis_koch(0.5), "moderate")
        self.assertEqual(landis_koch(0.76), "substantial")
        self.assertEqual(landis_koch(0.875), "almost perfect")


if __name__ == "__main__":
    unittest.main()
