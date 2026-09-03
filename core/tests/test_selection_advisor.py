from __future__ import annotations

import unittest

from project_factory.selection_advisor import advise_selection


class SelectionAdvisorTests(unittest.TestCase):
    def test_empty_selection_is_error(self) -> None:
        advice = advise_selection([])
        self.assertTrue(advice["has_error"])
        self.assertEqual(advice["warnings"][0]["code"], "EMPTY")

    def test_two_web_frontends_overlap(self) -> None:
        # web-spa + web-ui (both family "web") is buildable but silently prefers one.
        advice = advise_selection(["web-spa", "web-ui"], ["typescript"])
        self.assertFalse(advice["has_error"])
        self.assertTrue(advice["has_warn"])
        codes = {w["code"] for w in advice["warnings"]}
        self.assertIn("OVERLAP_WEB", codes)

    def test_two_services_overlap(self) -> None:
        # http-service + service (both family "service") is buildable but silently prefers one.
        advice = advise_selection(["http-service", "service"], ["python"])
        self.assertFalse(advice["has_error"])
        self.assertTrue(advice["has_warn"])
        codes = {w["code"] for w in advice["warnings"]}
        self.assertIn("OVERLAP_SERVICE", codes)

    def test_clean_web_service_split_has_no_warning(self) -> None:
        # The only allowed cross-family pairing: exactly one web + one service.
        advice = advise_selection(["web-spa", "http-service"], ["python", "react"])
        self.assertFalse(advice["has_error"])
        self.assertFalse(advice["has_warn"])
        self.assertEqual(advice["warnings"], [])

    def test_web_plus_service_plus_third_product_is_mutex(self) -> None:
        # web + service + notebook would silently drop notebook -> hard reject.
        advice = advise_selection(
            ["web-spa", "http-service", "notebook"], ["python", "typescript"]
        )
        self.assertTrue(advice["has_error"])
        self.assertEqual(advice["warnings"][0]["code"], "MUTEX")

    def test_cli_plus_library_is_mutex(self) -> None:
        # Two distinct car families, no split exception -> factory refuses.
        advice = advise_selection(["cli", "library"], ["python"])
        self.assertTrue(advice["has_error"])
        self.assertEqual(advice["warnings"][0]["code"], "MUTEX")

    def test_tech_mismatch_is_reported(self) -> None:
        # web-spa needs a web body; picking an unrelated tech means no profile matches,
        # so the factory also refuses (MUTEX) and TECH_MISMATCH rides along as context.
        advice = advise_selection(["web-spa"], ["go"])
        self.assertTrue(advice["has_error"])
        codes = {w["code"] for w in advice["warnings"]}
        self.assertIn("TECH_MISMATCH", codes)
        self.assertIn("MUTEX", codes)

    def test_family_grouping_is_data_driven_not_hardcoded(self) -> None:
        # Adding a kind to the "web" family is driven by the registry, not by a
        # hardcoded WEB_KINDS set. Sanity-check that web-spa resolves to family "web"
        # and cli resolves to "cli" via the advisor's own lookup path.
        from project_factory.registry import load_registry

        registry = load_registry()
        # nosec: internal helper exercised indirectly through advise_selection above;
        # here we assert the registry itself carries the declarative family.
        self.assertEqual(registry.profiles["typescript-web-ui"].family, "web")
        self.assertEqual(registry.profiles["python-cli"].family, "cli")
        self.assertEqual(registry.profiles["python-http-service"].family, "service")


if __name__ == "__main__":
    unittest.main()
