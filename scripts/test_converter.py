import importlib.util
import re
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("convert_rules.py")
spec = importlib.util.spec_from_file_location("convert_rules", MODULE_PATH)
conv = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(conv)


class ConverterTests(unittest.TestCase):
    def test_qy_basic_categories(self):
        text = """! Title: 晴雅广告拦截规则
! Version: test
||example.com^
||*.ads.example.com^
||ad-*.kwaidc.com^
||*googleads*^
||ad.wx.com:12638^
"""
        _, suffixes, keywords, wildcards, ports, unsupported = conv.parse_qy(text)
        self.assertEqual(suffixes, ["example.com"])
        self.assertEqual(keywords, ["googleads"])
        self.assertEqual(wildcards, ["*.ads.example.com", "ad-*.kwaidc.com"])
        self.assertEqual(ports["12638"], {"ad.wx.com"})
        self.assertEqual(unsupported, [])

    def test_leading_star_dot_does_not_become_suffix(self):
        text = "! Title: 晴雅广告拦截规则\n||*.example.com^\n"
        _, suffixes, _, wildcards, _, _ = conv.parse_qy(text)
        self.assertEqual(suffixes, [])
        self.assertEqual(wildcards, ["*.example.com"])

    def test_abp_domain_anchor_projection(self):
        rx = re.compile(conv.abp_host_regex("ad-*.kwaidc.com"))
        self.assertTrue(rx.fullmatch("ad-x.kwaidc.com"))
        self.assertTrue(rx.fullmatch("a.b.ad-x.kwaidc.com"))
        self.assertTrue(rx.fullmatch("ad-x.y.kwaidc.com"))
        self.assertFalse(rx.fullmatch("badad-x.kwaidc.com"))

    def test_star_dot_excludes_apex(self):
        rx = re.compile(conv.abp_host_regex("*.ads.example.com"))
        self.assertTrue(rx.fullmatch("x.ads.example.com"))
        self.assertTrue(rx.fullmatch("x.y.ads.example.com"))
        self.assertFalse(rx.fullmatch("ads.example.com"))

    def test_question_mark_is_not_treated_as_abp_hostname_wildcard(self):
        text = "! Title: 晴雅广告拦截规则\n||ad?.example.com^\n"
        _, suffixes, keywords, wildcards, ports, unsupported = conv.parse_qy(text)
        self.assertFalse(suffixes or keywords or wildcards or ports)
        self.assertEqual(len(unsupported), 1)

    def test_path_and_modifier_are_not_widened(self):
        text = """! Title: 晴雅广告拦截规则
||api.example.com/ads/*^
||example.com^$app=com.test
"""
        _, suffixes, keywords, wildcards, ports, unsupported = conv.parse_qy(text)
        self.assertFalse(suffixes or keywords or wildcards or ports)
        self.assertEqual(len(unsupported), 2)

    def test_adaway_is_exact_and_localhost_is_ignored(self):
        text = """127.0.0.1 localhost
::1 localhost
127.0.0.1 analytics.example.com
0.0.0.0 ads.example.net
"""
        domains, skipped = conv.parse_adaway(text)
        self.assertEqual(domains, ["ads.example.net", "analytics.example.com"])
        self.assertEqual(skipped, 0)

    def test_suffix_shadowing(self):
        suffixes = {"example.com"}
        self.assertTrue(conv.covered_by_suffix("example.com", suffixes))
        self.assertTrue(conv.covered_by_suffix("a.b.example.com", suffixes))
        self.assertFalse(conv.covered_by_suffix("badexample.com", suffixes))

    def test_fixed_prefix_wildcard_gets_subdomain_variant(self):
        self.assertEqual(
            conv.wildcard_variants("ad-*.example.com"),
            ["ad-*.example.com", "*.ad-*.example.com"],
        )
        self.assertEqual(
            conv.wildcard_variants("*.example.com"),
            ["*.example.com"],
        )


if __name__ == "__main__":
    unittest.main()
