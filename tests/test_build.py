import base64
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import HomePage, SiteBuilder

PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")

HOME = """---
name: Ada Example
pronouns: she/her
description: Ada Example studies how examples are written.
role:
  - PhD student
  - Example University
email: ada [at] example.org
address: Room 1, Example Street 2, 12345 Exampletown
links:
  Google Scholar: https://scholar.example.org/ada
  LinkedIn: https://www.linkedin.com/in/ada-example
  CV: soon
photos:
  - images/fixture-photo.png
  - images/fixture-photo-2.png
---

I'm a sample biography, written for the tests.

## Research

I study examples. Most of it comes back to two questions:

1. **The first question.** What is an example?
2. **The second question.** When is one enough?

### A fold question?

A fold answer.
"""

NEWS = """Notes to self; only dash lines are used.

- May 2026: Gave a talk at the Example Conference.
- April 2026: Wrote a [second item](https://example.org/news).
- 2025-03: A third item with a numeric date.
"""

TEACHING = """- Summer 2026: [An example course](https://example.org/course)
- Winter 2025/26: Another example course, tutor
"""

PERSONAL = """---
description: The rest of Ada Example.
---

## Writing

Some writing.

<<Pieces will be listed here.>>

## Media

⟨Books and more.⟩
"""

FIRST_PAPER = """---
id: first-paper
date: 2025-05
title: A First Paper: With a Colon in the Title
authors: Ada Example, Bea Coauthor
venue: Example Conference 2025
short_venue: EC 2025
award: Best Paper
award_full: Best Paper Award
award_link: https://example.org/awards
citation: Proceedings of the Example Conference, 1–10.
figure: images/fixture-figure.png
links:
  PDF: https://example.org/first.pdf
  Code: soon
---

The abstract of the first paper.

```bibtex
@inproceedings{example2025first,
  title = {A First Paper},
  year  = {2025}
}
```
"""

SECOND_PAPER = """---
id: second-paper
date: 2023-01
title: A Second Paper
authors: Ada Example, Cy Coauthor
venue: Example Journal 2023
figure: images/fixture-figure.png
---

The abstract of the second paper.
"""

PEOPLE = """const ME = "Ada Example";

const PEOPLE = {
  "Bea Coauthor": "https://example.org/bea",
  "Cy Coauthor":  "https://example.org/cy"
};
"""

FIXTURE = {
    "content/home.md": HOME,
    "content/news.md": NEWS,
    "content/teaching.md": TEACHING,
    "content/personal.md": PERSONAL,
    "content/publications/2025-first.md": FIRST_PAPER,
    "content/publications/2023-second.md": SECOND_PAPER,
    "people.js": PEOPLE,
}

IMAGES = ("images/fixture-photo.png", "images/fixture-photo-2.png", "images/fixture-figure.png")


class SiteCopy:
    def __enter__(self):
        self.dir = Path(tempfile.mkdtemp())
        for name in ("templates", "images", "js"):
            shutil.copytree(ROOT / name, self.dir / name)
        shutil.copy(ROOT / "style.css", self.dir / "style.css")
        for relative, text in FIXTURE.items():
            self.write(relative, text)
        for relative in IMAGES:
            (self.dir / relative).write_bytes(PIXEL)
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)

    def read(self, relative):
        return (self.dir / relative).read_bytes().decode("utf-8")

    def write(self, relative, text):
        path = self.dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))

    def edit(self, relative, old, new):
        text = self.read(relative)
        assert old in text, f"{old!r} not in {relative}"
        self.write(relative, text.replace(old, new, 1))

    def build(self):
        builder = SiteBuilder(self.dir)
        pages = builder.build()
        return pages, builder.report


def between(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


class LivePagesAreCurrent(unittest.TestCase):
    def test_pages_in_the_folder_match_the_content(self):
        builder = SiteBuilder(ROOT)
        pages = builder.build()
        self.assertEqual(builder.report.errors, [], "content/ has an error: run python build.py to see it")
        for name, text in pages.items():
            self.assertEqual(text, (ROOT / name).read_text(encoding="utf-8"), f"{name} is out of date: run python build.py")


class BuildsCleanly(unittest.TestCase):
    def test_sample_content_builds_without_warnings(self):
        with SiteCopy() as site:
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            self.assertEqual(report.warnings, [])
            self.assertEqual(sorted(pages), ["index.html", "news.html", "personal.html", "publications.html", "sitemap.xml"])
            self.assertIn("https://anweshadas1.github.io/news.html", pages["sitemap.xml"])


class Pronouns(unittest.TestCase):
    def test_pronouns_follow_the_name_in_the_heading(self):
        with SiteCopy() as site:
            pages, report = site.build()
            self.assertEqual(report.warnings, [])
            self.assertIn('<h1>Ada Example <span class="pronouns">(she/her)</span></h1>', pages["index.html"])

    def test_brackets_written_in_the_field_are_not_doubled(self):
        with SiteCopy() as site:
            site.edit("content/home.md", "pronouns: she/her", "pronouns: (she/her)")
            pages, _ = site.build()
            self.assertIn('<span class="pronouns">(she/her)</span>', pages["index.html"])

    def test_no_pronouns_line_means_no_span(self):
        with SiteCopy() as site:
            site.edit("content/home.md", "pronouns: she/her\n", "")
            pages, report = site.build()
            self.assertEqual(report.warnings, [])
            self.assertIn("<h1>Ada Example</h1>", pages["index.html"])
            self.assertNotIn('class="pronouns"', pages["index.html"])

    def test_pronouns_stay_out_of_the_role_and_the_affiliation(self):
        with SiteCopy() as site:
            pages, _ = site.build()
            home = pages["index.html"]
            self.assertEqual(between(home, '<p class="role">', "</p>"), "PhD student<br>Example University")
            self.assertIn('"name": "Example University"', between(home, '<script type="application/ld+json">', "</script>"))
            self.assertEqual(home.count("she/her"), 1)
            for name in ("publications.html", "personal.html", "news.html"):
                self.assertNotIn("she/her", pages[name])

    def test_pronouns_as_a_list_warn_and_are_skipped(self):
        with SiteCopy() as site:
            site.edit("content/home.md", "pronouns: she/her\n", "pronouns:\n  - she/her\n")
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            self.assertTrue(any("home.md" in w and "'pronouns' should be one line" in w for w in report.warnings))
            self.assertIn("<h1>Ada Example</h1>", pages["index.html"])


class Footer(unittest.TestCase):
    def test_footer_links_to_google_scholar_on_every_page(self):
        with SiteCopy() as site:
            pages, _ = site.build()
            for name in ("index.html", "publications.html", "personal.html", "news.html"):
                footer = between(pages[name], '<footer class="foot">', "</footer>")
                self.assertIn("Room 1, Example Street 2, 12345 Exampletown &middot; "
                              '<a href="https://scholar.example.org/ada" target="_blank" rel="noopener">Google Scholar</a>', footer)

    def test_no_scholar_link_means_none_in_the_footer(self):
        with SiteCopy() as site:
            site.edit("content/home.md", "  Google Scholar: https://scholar.example.org/ada\n", "")
            pages, report = site.build()
            self.assertEqual(report.warnings, [])
            self.assertNotIn("Google Scholar", between(pages["index.html"], '<footer class="foot">', "</footer>"))


class NewTabs(unittest.TestCase):
    def test_only_links_to_other_sites_open_in_a_new_tab(self):
        with SiteCopy() as site:
            pages, _ = site.build()
            tags = [tag for name, text in pages.items() if name.endswith(".html") for tag in re.findall(r"<a\b[^>]*>", text)]
            self.assertTrue(any('href="https://example.org/news"' in tag for tag in tags))
            self.assertTrue(any('href="news.html"' in tag for tag in tags))
            for tag in tags:
                elsewhere = re.search(r'href="https?://', tag) is not None
                self.assertEqual('target="_blank" rel="noopener"' in tag, elsewhere, tag)

    def test_a_link_that_already_says_where_to_open_is_left_alone(self):
        with SiteCopy() as site:
            site.edit("content/personal.md", "Some writing.", 'Some <a href="https://example.org/same" target="_self">writing</a>.')
            pages, _ = site.build()
            self.assertIn('<a href="https://example.org/same" target="_self">', pages["personal.html"])


class Emoji(unittest.TestCase):
    def test_a_link_made_only_of_emoji_is_marked_so_it_has_no_underline(self):
        with SiteCopy() as site:
            site.edit("content/personal.md", "Some writing.",
                      "Some writing ([🌻](https://example.org/flower)), [❤️](https://example.org/heart) and [an award 🎉](https://example.org/award).")
            pages, report = site.build()
            self.assertEqual(report.warnings, [])
            page = pages["personal.html"]
            self.assertIn('<a href="https://example.org/flower" class="emoji" target="_blank" rel="noopener">🌻</a>', page)
            self.assertIn('<a href="https://example.org/heart" class="emoji" target="_blank" rel="noopener">❤️</a>', page)
            self.assertIn('<a href="https://example.org/award" target="_blank" rel="noopener">an award 🎉</a>', page)

    def test_emoji_in_ordinary_text_pass_through(self):
        with SiteCopy() as site:
            site.edit("content/news.md", "Example Conference.", "Example Conference 🎉!")
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            self.assertIn("Example Conference 🎉!", pages["index.html"])


class ForgivesEverydayEdits(unittest.TestCase):
    def test_title_with_colon_needs_no_quotes(self):
        with SiteCopy() as site:
            pages, report = site.build()
            self.assertIn("A First Paper: With a Colon in the Title", pages["publications.html"])

    def test_quoted_values_also_work(self):
        with SiteCopy() as site:
            site.edit("content/home.md", "email: ada [at] example.org", 'email: "ada [at] example.org"')
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            self.assertIn("<li>ada [at] example.org</li>", pages["index.html"])

    def test_news_line_without_colon_is_kept_with_a_warning(self):
        with SiteCopy() as site:
            site.edit("content/news.md", "- May 2026: Gave a talk", "- Gave a talk")
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            self.assertTrue(any("news.md" in w and "without a date" in w for w in report.warnings))
            self.assertIn("Gave a talk at the Example Conference.", pages["index.html"])

    def test_unusual_date_is_shown_as_written(self):
        with SiteCopy() as site:
            site.edit("content/news.md", "- May 2026: Gave a talk", "- Spring-ish 2026: Gave a talk")
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            self.assertIn("<time>Spring-ish 2026</time>", pages["index.html"])

    def test_unknown_coauthor_warns_but_builds(self):
        with SiteCopy() as site:
            site.edit("content/publications/2023-second.md", "Cy Coauthor", "Cy Coauthor, New Person")
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            self.assertTrue(any("New Person" in w for w in report.warnings))

    def test_missing_figure_warns_and_drops_it(self):
        with SiteCopy() as site:
            site.edit("content/publications/2023-second.md", "fixture-figure.png", "nope.png")
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            self.assertIn('class="pub no-figure" id="second-paper"', pages["publications.html"])

    def test_new_paper_from_a_minimal_file(self):
        with SiteCopy() as site:
            site.write("content/publications/2027-new.md",
                       "---\ndate: 2027-01\ntitle: A New Paper: With a Colon\nauthors: Ada Example, Bea Coauthor\nvenue: Example Venue 2027\n---\n\nAn abstract.\n")
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            listed = between(pages["index.html"], '<ul class="pub-short">', "</ul>")
            self.assertLess(listed.index("A New Paper"), listed.index("A First Paper"))
            self.assertIn('id="new"', pages["publications.html"])

    def test_windows_line_endings_and_bom(self):
        with SiteCopy() as site:
            text = site.read("content/news.md").replace("\n", "\r\n")
            (site.dir / "content" / "news.md").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            self.assertIn("Gave a talk at the Example Conference.", pages["index.html"])

    def test_placeholders_in_both_spellings(self):
        with SiteCopy() as site:
            pages, _ = site.build()
            self.assertEqual(pages["personal.html"].count('class="placeholder"'), 2)
            self.assertIn("&#10216;Pieces will be listed here.&#10217;", pages["personal.html"])
            self.assertIn("&#10216;Books and more.&#10217;", pages["personal.html"])


class NewsPageAndLimit(unittest.TestCase):
    def news(self, count):
        lines = [f"- May {2000 + i}: Item number {i}." for i in range(count, 0, -1)]
        return "Notes.\n\n" + "\n".join(lines) + "\n"

    def test_home_shows_only_the_newest_and_links_to_all(self):
        limit = HomePage.NEWS_ON_HOME
        with SiteCopy() as site:
            site.write("content/news.md", self.news(limit + 3))
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            sidebar = between(pages["index.html"], '<section class="side-news">', "</section>")
            self.assertEqual(sidebar.count("<li>"), limit)
            self.assertIn('href="news.html">More news', sidebar)
            self.assertIn(f"Item number {limit + 3}.", sidebar)
            self.assertNotIn("Item number 3.", sidebar)
            self.assertEqual(pages["news.html"].count('<span class="headline">'), limit + 3)

    def test_indented_lines_are_a_write_up_on_the_news_page_only(self):
        with SiteCopy() as site:
            site.edit("content/news.md", "- May 2026: Gave a talk at the Example Conference.\n",
                      "- May 2026: Gave a talk at the Example Conference.\n  A longer note with a [link](https://example.org).\n\n  A second paragraph.\n")
            pages, report = site.build()
            self.assertEqual(report.errors, [])
            self.assertIn('<div class="detail"><p>A longer note with a <a href="https://example.org" target="_blank" rel="noopener">link</a>.</p>\n<p>A second paragraph.</p></div>', pages["news.html"])
            self.assertNotIn("A longer note", pages["index.html"])

    def test_news_page_is_not_in_the_navigation(self):
        with SiteCopy() as site:
            pages, _ = site.build()
            nav = between(pages["news.html"], "<nav>", "</nav>")
            self.assertNotIn("news.html", nav)
            self.assertNotIn('aria-current="page"', nav)


class RefusesClearly(unittest.TestCase):
    def assertFailsAt(self, report, filename, words):
        self.assertTrue(report.errors, "expected an error")
        self.assertTrue(any(filename in e and words in e for e in report.errors), report.errors)

    def test_paper_without_title(self):
        with SiteCopy() as site:
            site.edit("content/publications/2023-second.md", "title: A Second", "titel: A Second")
            pages, report = site.build()
            self.assertFailsAt(report, "2023-second.md", "needs a 'title")
            self.assertEqual(pages, {})

    def test_header_never_closed(self):
        with SiteCopy() as site:
            site.edit("content/home.md", "\n---\n", "\n")
            pages, report = site.build()
            self.assertFailsAt(report, "home.md", "closing ---")
            self.assertEqual(pages, {})

    def test_stray_indented_line(self):
        with SiteCopy() as site:
            site.edit("content/home.md", "name: Ada Example\n", "  name: Ada Example\n")
            pages, report = site.build()
            self.assertFailsAt(report, "home.md, line 2", "indented")

    def test_two_papers_with_the_same_id(self):
        with SiteCopy() as site:
            site.edit("content/publications/2023-second.md", "id: second-paper", "id: first-paper")
            pages, report = site.build()
            self.assertFailsAt(report, "publications", "share the id")

    def test_failed_build_writes_nothing(self):
        with SiteCopy() as site:
            site.edit("content/publications/2023-second.md", "title: A Second", "titel: A Second")
            builder = SiteBuilder(site.dir)
            pages = builder.build()
            self.assertTrue(builder.report.errors)
            self.assertEqual(pages, {})
            self.assertFalse((site.dir / "index.html").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
