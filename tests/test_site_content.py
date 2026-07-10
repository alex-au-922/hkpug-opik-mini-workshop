from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE_HTML = ROOT / "site" / "index.html"
SITE_STYLES = ROOT / "site" / "styles.css"
SITE_SCRIPT = ROOT / "site" / "script.js"


class SiteContentTest(unittest.TestCase):
    def test_all_workshop_questions_are_present(self) -> None:
        html = SITE_HTML.read_text()

        self.assertEqual(len(re.findall(r'<details class="case"', html)), 6)
        self.assertEqual(
            set(re.findall(r'data-question="(\d{3}-[A-D])"', html)),
            {
                f"{case_id}-{label}"
                for case_id in ("001", "002", "003", "004", "005", "006")
                for label in "ABCD"
            },
        )
        for case_id in ("001", "002", "003", "004", "005", "006"):
            self.assertIn(f'id="case-{case_id}"', html)
            self.assertIn(f'data-copy-case="{case_id}"', html)

    def test_questions_are_navigable_without_javascript(self) -> None:
        html = SITE_HTML.read_text()

        self.assertIn('id="questions"', html)
        self.assertIn('href="#questions"', html)
        self.assertEqual(html.count('class="evidence-badge code"'), 4)
        self.assertIn('class="evidence-badge experiment"', html)
        self.assertIn('<script src="./script.js" defer></script>', html)

    def test_grid_questions_keep_visible_letter_labels(self) -> None:
        styles = SITE_STYLES.read_text()

        self.assertIn("counter-reset: question", styles)
        self.assertIn('content: counter(question, upper-alpha) "."', styles)

    def test_copy_action_has_a_legacy_clipboard_fallback(self) -> None:
        script = SITE_SCRIPT.read_text()

        self.assertIn("async function writeToClipboard", script)
        self.assertIn('document.execCommand("copy")', script)

    def test_mobile_hero_leaves_room_for_the_questions(self) -> None:
        styles = SITE_STYLES.read_text()

        self.assertIsNotNone(
            re.search(
                r"@media \(max-width: 640px\).*?\.flow-panel\s*"
                r"\{\s*display: none;\s*\}",
                styles,
                re.DOTALL,
            )
        )


if __name__ == "__main__":
    unittest.main()
