import html
import json
import re
import sys
import traceback
import unicodedata
from pathlib import Path
from string import Template

import markdown

try:
    from PIL import Image
except ImportError:
    Image = None

SITE_URL = "https://anweshadas1.github.io/"
IN_PROGRESS = "This site is in progress. Please mind your step."
MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]
NAV = [("index.html", "Home"), ("publications.html", "Publications"), ("personal.html", "Personal")]


def esc(text):
    return html.escape(str(text), quote=True)


def nfc(text):
    return unicodedata.normalize("NFC", text).strip()


class ContentError(Exception):
    def __init__(self, path, line, message):
        super().__init__(message)
        self.path = path
        self.line = line
        self.message = message


class Report:
    def __init__(self, root):
        self.root = root
        self.warnings = []
        self.errors = []

    def where(self, path, line=None):
        try:
            name = Path(path).relative_to(self.root).as_posix()
        except ValueError:
            name = str(path)
        return f"{name}, line {line}" if line else name

    def warn(self, path, line, message):
        self.warnings.append(f"{self.where(path, line)}: {message}")

    def fail(self, path, line, message):
        self.errors.append(f"{self.where(path, line)}: {message}")


class Document:
    def __init__(self, path):
        self.path = path
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        self.meta, self.body, self.body_start = self.split(text)

    def split(self, text):
        lines = text.split("\n")
        if lines[0].strip() != "---":
            return {}, text, 1
        for end in range(1, len(lines)):
            if lines[end].strip() == "---":
                return self.parse(lines[1:end], 2), "\n".join(lines[end + 1:]), end + 2
        raise ContentError(self.path, 1, "the header starts with --- but never has a closing --- line")

    def parse(self, lines, first):
        meta, parent = {}, None
        for number, raw in enumerate(lines, first):
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            if raw[:1] in (" ", "\t"):
                if parent is None:
                    raise ContentError(self.path, number, "this line is indented, but there is no field above it for it to belong to")
                self.add_child(meta, parent, raw.strip(), number)
                continue
            key, colon, value = raw.partition(":")
            if not colon or not key.strip():
                raise ContentError(self.path, number, f"expected 'field: value' but found {raw.strip()!r}")
            key, value = key.strip(), value.strip()
            meta[key] = self.clean(value) if value else None
            parent = None if value else key
        return {key: ("" if value is None else value) for key, value in meta.items()}

    def add_child(self, meta, parent, item, number):
        if item.startswith("- "):
            if meta[parent] is None:
                meta[parent] = []
            if not isinstance(meta[parent], list):
                raise ContentError(self.path, number, f"'{parent}' mixes '- item' lines with 'Name: value' lines")
            meta[parent].append(self.clean(item[2:]))
            return
        key, colon, value = item.partition(":")
        if not colon or not key.strip():
            raise ContentError(self.path, number, f"expected 'Name: value' under '{parent}' but found {item!r}")
        if meta[parent] is None:
            meta[parent] = {}
        if not isinstance(meta[parent], dict):
            raise ContentError(self.path, number, f"'{parent}' mixes '- item' lines with 'Name: value' lines")
        meta[parent][key.strip()] = self.clean(value)

    @staticmethod
    def clean(value):
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        return value


class Renderer:
    PLACEHOLDER = re.compile(r"^[ \t]*(?:<<(.+?)>>|⟨(.+?)⟩)[ \t]*$", re.M)

    def __init__(self):
        self.engine = markdown.Markdown(extensions=["smarty"], output_format="html")

    def block(self, text):
        holes = []

        def hold(match):
            holes.append(match.group(1) or match.group(2))
            return f"PLACEHOLDER{len(holes) - 1}X"

        self.engine.reset()
        out = self.engine.convert(self.PLACEHOLDER.sub(hold, text.strip()))
        for i, hole in enumerate(holes):
            out = out.replace(f"<p>PLACEHOLDER{i}X</p>",
                              f'<p class="placeholder" data-tip="{esc(IN_PROGRESS)}">&#10216;{esc(hole)}&#10217;</p>')
        return out

    def inline(self, text):
        out = self.block(text)
        match = re.fullmatch(r"<p>(.*)</p>", out, re.S)
        return match.group(1) if match else out


class People:
    def __init__(self, path, report):
        self.me, self.names = None, set()
        if not path.exists():
            report.warn(path, None, "people.js is missing, so co-author names cannot be checked")
            return
        text = path.read_text(encoding="utf-8")
        me = re.search(r'const\s+ME\s*=\s*"([^"]+)"', text)
        block = re.search(r"const\s+PEOPLE\s*=\s*\{(.*?)\};", text, re.S)
        self.me = nfc(me.group(1)) if me else None
        self.names = {nfc(name) for name in re.findall(r'"([^"]+)"\s*:', block.group(1))} if block else set()

    def unknown(self, authors):
        return [name for name in authors if name != self.me and name not in self.names]


class Dates:
    @staticmethod
    def attribute(label):
        label = label.strip()
        match = re.fullmatch(r"(\d{4})-(\d{1,2})", label)
        if match and 1 <= int(match.group(2)) <= 12:
            return f"{match.group(1)}-{int(match.group(2)):02d}"
        match = re.fullmatch(r"([A-Za-z]{3,})\.?\s+(\d{4})", label)
        if match:
            for number, month in enumerate(MONTHS, 1):
                if month.startswith(match.group(1).lower()):
                    return f"{match.group(2)}-{number:02d}"
        if re.fullmatch(r"\d{4}", label):
            return label
        return None


class DatedItem:
    def __init__(self, label, stamp, text):
        self.label = label
        self.stamp = stamp
        self.text = text
        self.detail_lines = []
        self.detail = ""

    def date_html(self):
        if self.stamp:
            return f'<time datetime="{self.stamp}">{esc(self.label)}</time>'
        return f"<time>{esc(self.label)}</time>" if self.label else ""

    def short_html(self):
        return f"        <li>{self.date_html()}{self.text}</li>"

    def full_html(self):
        detail = f'\n        <div class="detail">{self.detail}</div>\n      ' if self.detail else ""
        return f"      <li>{self.date_html()}<span class=\"headline\">{self.text}</span>{detail}</li>"


class DatedList:
    ITEM = re.compile(r"^[-*]\s+(.*\S)\s*$")

    def __init__(self, path, renderer, report, needs_dates):
        self.items = []
        document = Document(path)
        for number, raw in enumerate(document.body.split("\n"), document.body_start):
            match = self.ITEM.match(raw)
            if match:
                self.items.append(self.item(match.group(1), path, number, report, renderer, needs_dates))
            elif self.items and raw[:1] in (" ", "\t") and raw.strip():
                self.items[-1].detail_lines.append(raw.strip())
            elif self.items and not raw.strip() and self.items[-1].detail_lines:
                self.items[-1].detail_lines.append("")
        for item in self.items:
            if any(item.detail_lines):
                item.detail = renderer.block("\n".join(item.detail_lines))
        if not self.items:
            report.warn(path, None, "no items found; each item is a line that starts with a dash")

    @staticmethod
    def item(line, path, number, report, renderer, needs_dates):
        label, colon, text = line.partition(": ")
        if not colon:
            report.warn(path, number, "there is no 'Date: ' before the text, so this item is shown without a date")
            label, text = "", line
        stamp = Dates.attribute(label) if label else None
        if needs_dates and label and not stamp:
            report.warn(path, number, f"'{label}' is not a date like 'May 2026', so it is shown exactly as written")
        return DatedItem(label.strip(), stamp, renderer.inline(text))


class Paper:
    FIELDS = {"id", "date", "title", "authors", "venue", "short_venue", "award", "award_full",
              "award_link", "citation", "figure", "figure_alt", "links"}
    REQUIRED = ("title", "authors", "venue")
    FENCE = re.compile(r"```[ \t]*(?:bibtex|bib)?[ \t]*\n(.*?)```", re.S | re.I)

    def __init__(self, path, root, renderer, people, report):
        document = Document(path)
        meta = document.meta
        for field in self.REQUIRED:
            if not isinstance(meta.get(field), str) or not meta.get(field):
                raise ContentError(path, 1, f"the header needs a '{field}: ...' line")
        for key in meta:
            if key not in self.FIELDS:
                report.warn(path, None, f"the field '{key}' is not used by the site and is ignored")
        self.id = re.sub(r"[^a-z0-9-]+", "-", (meta.get("id") or re.sub(r"^\d{4}-", "", path.stem)).lower()).strip("-")
        self.date = meta.get("date", "")
        if self.date and not Dates.attribute(self.date):
            report.warn(path, None, f"the date '{self.date}' is not like '2026-05', so papers may be ordered by file name")
        self.title = meta["title"]
        self.authors = [nfc(name) for name in meta["authors"].split(",") if name.strip()]
        for name in people.unknown(self.authors):
            report.warn(path, None, f"'{name}' is not in people.js, so the name will not be a link")
        self.venue = meta["venue"]
        self.short_venue = meta.get("short_venue") or self.venue
        self.award = meta.get("award", "")
        self.award_full = meta.get("award_full", "")
        self.award_link = meta.get("award_link", "")
        self.citation = meta.get("citation", "")
        self.links = meta.get("links") or {}
        if not isinstance(self.links, dict):
            report.warn(path, None, "'links:' should be followed by indented lines like '  PDF: https://...'; links skipped")
            self.links = {}
        self.figure, self.size = self.find_figure(meta.get("figure", ""), root, path, report)
        self.figure_alt = meta.get("figure_alt") or f"Teaser figure from {self.title.split(':')[0]}"
        fence = self.FENCE.search(document.body)
        self.bibtex = fence.group(1).strip() if fence else ""
        abstract = self.FENCE.sub("", document.body).strip()
        if "```" in abstract:
            report.warn(path, None, "a ``` fence is opened but never closed, so it is shown as text")
        self.abstract = renderer.block(abstract) if abstract else ""
        if not abstract:
            report.warn(path, None, "there is no abstract under the header")
        self.sort_key = (Dates.attribute(self.date) or "0000", path.name)
        self.renderer = renderer

    @staticmethod
    def find_figure(figure, root, path, report):
        if not figure:
            return "", None
        if not (root / figure).exists():
            report.warn(path, None, f"the figure '{figure}' does not exist, so the paper is shown without it")
            return "", None
        size = None
        if Image is not None:
            with Image.open(root / figure) as image:
                size = image.size
        return figure, size

    def title_html(self):
        return self.renderer.inline(self.title)

    def award_badge(self):
        return f'<span class="award">{esc(self.award)}</span>' if self.award else ""

    def authors_html(self):
        return esc(", ".join(self.authors))

    def link_row(self):
        parts = []
        for label, target in self.links.items():
            if target.lower() in ("", "soon"):
                parts.append(f'<span class="soon" data-tip="{esc(IN_PROGRESS)}">{esc(label)}</span>')
            else:
                parts.append(f'<a href="{esc(target)}">{esc(label)}</a>')
        return "\n          ".join(parts)

    def short_entry(self):
        return (f'      <li>\n'
                f'        <a class="pub-title" href="publications.html#{self.id}">{self.title_html()}</a>\n'
                f'        <p class="authors" data-module="authors">{self.authors_html()}</p>\n'
                f'        <p class="venue">{self.award_badge()}{esc(self.short_venue)}</p>\n'
                f'      </li>')

    def full_entry(self):
        figure = ""
        if self.figure:
            size = f' width="{self.size[0]}" height="{self.size[1]}"' if self.size else ""
            figure = (f'      <figure class="pub-figure">\n'
                      f'        <img src="{esc(self.figure)}" alt="{esc(self.figure_alt)}"{size}>\n'
                      f'      </figure>\n')
        award = ""
        if self.award_full:
            award = f' <a href="{esc(self.award_link)}">{esc(self.award_full)}</a>.' if self.award_link else f" {esc(self.award_full)}."
        citation = f'        <p class="venue">{esc(self.citation)}{award}</p>\n' if (self.citation or award) else ""
        links = f'        <p class="pub-links">\n          {self.link_row()}\n        </p>\n' if self.links else ""
        abstract = (f'        <details>\n          <summary>Abstract</summary>\n'
                    f'          {self.abstract}\n        </details>\n') if self.abstract else ""
        bibtex = (f'        <details class="bib" data-module="bibtex">\n          <summary>BibTeX</summary>\n'
                  f'<pre>{html.escape(self.bibtex, quote=False)}</pre>\n'
                  f'          <button type="button">Copy BibTeX</button>\n        </details>\n') if self.bibtex else ""
        css = "pub" if self.figure else "pub no-figure"
        return (f'    <article class="{css}" id="{self.id}">\n{figure}'
                f'      <div>\n'
                f'        <p class="venue">{self.award_badge()}{esc(self.venue)}</p>\n'
                f'        <h2>{self.title_html()}</h2>\n'
                f'        <p class="authors" data-module="authors">{self.authors_html()}</p>\n'
                f'{citation}{links}{abstract}{bibtex}'
                f'      </div>\n    </article>')


class Page:
    filename = ""
    scripts = ["js/site.js", "js/theme.js"]
    og_type = "website"
    LINK = re.compile(r'<a\b[^>]*\bhref="(https?://[^"]*)"[^>]*>')
    LABELLED = re.compile(r"(<a\b[^>]*)>([^<]+)</a>")
    EMOJI_PARTS = {"So", "Sk", "Mn", "Me", "Cf"}

    def __init__(self, site):
        self.site = site

    def nav(self):
        lines = []
        for href, label in NAV:
            current = ' aria-current="page"' if href == self.filename else ""
            lines.append(f'      <a href="{href}"{current}>{label}</a>')
        return "\n".join(lines)

    def canonical(self):
        return SITE_URL if self.filename == "index.html" else SITE_URL + self.filename

    def render(self):
        scripts = self.scripts
        values = {
            "title": esc(self.title()),
            "description": esc(self.description()),
            "canonical": self.canonical(),
            "og_type": self.og_type,
            "og_image": SITE_URL + self.og_image(),
            "head_extra": self.head_extra(),
            "name": esc(self.site.name),
            "nav": self.nav(),
            "body": self.body(),
            "footer": self.site.footer(),
            "scripts": "\n".join(f'<script src="{src}"></script>' for src in scripts),
        }
        return self.other_sites_in_new_tabs(self.emoji_links(Template(self.site.template).substitute(values)))

    @classmethod
    def only_emoji(cls, label):
        kinds = [unicodedata.category(ch) for ch in html.unescape(label) if not ch.isspace()]
        return "So" in kinds and all(kind in cls.EMOJI_PARTS for kind in kinds)

    @classmethod
    def emoji_links(cls, text):
        def mark(match):
            tag, label = match.groups()
            if not cls.only_emoji(label):
                return match.group(0)
            tag = tag.replace(' class="', ' class="emoji ', 1) if ' class="' in tag else tag + ' class="emoji"'
            return f"{tag}>{label}</a>"
        return cls.LABELLED.sub(mark, text)

    @classmethod
    def other_sites_in_new_tabs(cls, text):
        def mark(match):
            tag = match.group(0)
            if "target=" in tag or match.group(1).startswith(SITE_URL):
                return tag
            return tag[:-1] + ' target="_blank" rel="noopener">'
        return cls.LINK.sub(mark, text)

    def head_extra(self):
        return ""

    def og_image(self):
        return self.site.photos[0] if self.site.photos else "images/apple-touch-icon.png"


class HomePage(Page):
    filename = "index.html"
    scripts = ["people.js", "js/site.js", "js/authors.js", "js/theme.js", "js/photos.js"]
    og_type = "profile"
    NEWS_ON_HOME = 4

    def title(self):
        return self.site.name

    def description(self):
        return self.site.home.meta.get("description") or self.site.name

    def head_extra(self):
        same = [target for target in self.site.links.values() if target.startswith("http")]
        person = {"@context": "https://schema.org", "@type": "Person", "name": self.site.name, "url": SITE_URL,
                  "jobTitle": self.site.roles[0] if self.site.roles else "",
                  "affiliation": {"@type": "CollegeOrUniversity", "name": self.site.roles[-1] if len(self.site.roles) > 1 else ""},
                  "sameAs": same}
        if self.site.photos:
            person["image"] = SITE_URL + self.site.photos[0]
        return '<script type="application/ld+json">\n' + json.dumps(person, ensure_ascii=False, indent=2) + "\n</script>"

    def profile(self):
        site = self.site
        photo = ""
        if site.photos:
            size = ""
            if Image is not None:
                with Image.open(site.root / site.photos[0]) as image:
                    size = f' width="{image.size[0]}" height="{image.size[1]}"'
            cycle = f' data-module="photos" data-photos="{esc(" ".join(site.photos))}"' if len(site.photos) > 1 else ""
            photo = f'    <img class="portrait" src="{esc(site.photos[0])}" alt="{esc(site.name)}"{size}{cycle}>\n'
        links = [f"      <li>{esc(site.email)}</li>"] if site.email else []
        for label, target in site.links.items():
            if target.lower() in ("", "soon"):
                links.append(f'      <li><span class="soon" data-tip="{esc(IN_PROGRESS)}">{esc(label)}</span></li>')
            else:
                links.append(f'      <li><a href="{esc(target)}">{esc(label)}</a></li>')
        news = "\n".join(item.short_html() for item in site.news.items[:self.NEWS_ON_HOME])
        more = '      <p class="news-more"><a href="news.html">More news</a></p>\n' if site.news.items else ""
        role = "<br>".join(esc(r) for r in site.roles)
        return (f'  <aside class="profile">\n{photo}'
                f'    <p class="role">{role}</p>\n'
                f'    <ul class="profile-links">\n' + "\n".join(links) + "\n    </ul>\n\n"
                f'    <section class="side-news">\n      <h2>News</h2>\n      <ol class="timeline">\n{news}\n      </ol>\n{more}    </section>\n'
                f'  </aside>')

    def research(self, title, text):
        parts = re.split(r"^### +(.+?)[ \t]*$", text, flags=re.M)
        main = self.site.renderer.block(parts[0]).replace("<ol>", '<ol class="questions">', 1)
        folds = [f'      <details class="aside">\n        <summary>{self.site.renderer.inline(q)}</summary>\n'
                 f'        {self.site.renderer.block(a)}\n      </details>'
                 for q, a in zip(parts[1::2], parts[2::2])]
        asides = ('\n    <div class="asides">\n' + "\n".join(folds) + "\n    </div>") if folds else ""
        return f"    <h2>{esc(title)}</h2>\n    {main}{asides}"

    def body(self):
        site = self.site
        parts = re.split(r"^## +(.+?)[ \t]*$", site.home.body, flags=re.M)
        pronouns = f' <span class="pronouns">({esc(site.pronouns)})</span>' if site.pronouns else ""
        sections = [f"    <h1>{esc(site.name)}{pronouns}</h1>", "    " + site.renderer.block(parts[0])]
        for title, text in zip(parts[1::2], parts[2::2]):
            if title.strip().lower() == "research":
                sections.append(self.research(title.strip(), text))
            else:
                sections.append(f"    <h2>{esc(title.strip())}</h2>\n    {site.renderer.block(text)}")
        if site.papers:
            sections.append('    <h2>Publications</h2>\n    <ul class="pub-short">\n'
                            + "\n".join(p.short_entry() for p in site.papers)
                            + '\n    </ul>\n    <p class="more"><a href="publications.html">Abstracts, figures and BibTeX on the publications page</a></p>')
        if site.teaching.items:
            rows = "\n".join(f'      <li><span class="when">{esc(item.label)}</span><span>{item.text}</span></li>'
                             for item in site.teaching.items)
            sections.append(f'    <h2>Teaching</h2>\n    <ul class="dated">\n{rows}\n    </ul>')
        return (f'<div class="home">\n\n{self.profile()}\n\n  <main id="main" class="content">\n'
                + "\n\n".join(sections) + "\n  </main>\n\n</div>")


class PublicationsPage(Page):
    filename = "publications.html"
    scripts = ["people.js", "js/site.js", "js/authors.js", "js/theme.js", "js/bibtex.js"]

    def title(self):
        return f"Publications · {self.site.name}"

    def description(self):
        return f"Publications by {self.site.name}, with abstracts, figures and BibTeX."

    def og_image(self):
        figures = [p.figure for p in self.site.papers if p.figure]
        return figures[0] if figures else super().og_image()

    def body(self):
        scholar = self.site.scholar
        also = f'    <p>Also on <a href="{esc(scholar)}">Google Scholar</a>.</p>\n\n' if scholar else ""
        entries = "\n\n".join(p.full_entry() for p in self.site.papers)
        return (f'<div class="single wide">\n  <main id="main" class="content">\n    <h1>Publications</h1>\n'
                f'{also}{entries}\n  </main>\n</div>')


class NewsPage(Page):
    filename = "news.html"

    def title(self):
        return f"News · {self.site.name}"

    def description(self):
        return f"News from {self.site.name}."

    def body(self):
        rows = "\n".join(item.full_html() for item in self.site.news.items)
        return (f'<div class="single">\n  <main id="main" class="content news-page">\n    <h1>News</h1>\n'
                f'    <ol class="timeline">\n{rows}\n    </ol>\n  </main>\n</div>')


class PersonalPage(Page):
    filename = "personal.html"

    def title(self):
        return f"{self.site.personal.meta.get('title') or 'Personal'} · {self.site.name}"

    def description(self):
        return self.site.personal.meta.get("description") or f"The rest of {self.site.name}."

    def body(self):
        content = self.site.renderer.block(self.site.personal.body).replace("<h2>", '<h2 class="section-first">', 1)
        heading = esc(self.site.personal.meta.get("title") or "Personal")
        return (f'<div class="single">\n  <main id="main" class="content">\n    <h1>{heading}</h1>\n\n'
                f'    {content}\n  </main>\n</div>')


class SiteBuilder:
    HOME_FIELDS = {"name", "pronouns", "description", "role", "email", "address", "links", "photos"}

    def __init__(self, root, content=None):
        self.root = Path(root)
        self.content = Path(content) if content else self.root / "content"
        self.report = Report(self.root)
        self.renderer = Renderer()
        self.papers = []

    def footer(self):
        parts = [esc(part) for part in (self.name, self.email, self.address) if part]
        if self.scholar:
            parts.append(f'<a href="{esc(self.scholar)}">Google Scholar</a>')
        return " &middot; ".join(parts)

    def load(self):
        self.template = (self.root / "templates" / "page.html").read_text(encoding="utf-8")
        self.people = People(self.root / "people.js", self.report)
        self.home = Document(self.content / "home.md")
        meta = self.home.meta
        for key in meta:
            if key not in self.HOME_FIELDS:
                self.report.warn(self.home.path, None, f"the field '{key}' is not used by the site and is ignored")
        self.name = meta.get("name") or "Anwesha Das"
        pronouns = meta.get("pronouns", "")
        if not isinstance(pronouns, str):
            self.report.warn(self.home.path, None, "'pronouns' should be one line, like 'pronouns: she/her', so it is skipped")
            pronouns = ""
        self.pronouns = pronouns.strip().strip("()").strip()
        self.email = meta.get("email", "")
        self.address = meta.get("address", "")
        roles = meta.get("role", [])
        self.roles = roles if isinstance(roles, list) else [roles]
        self.links = meta.get("links") if isinstance(meta.get("links"), dict) else {}
        scholar = self.links.get("Google Scholar", "")
        self.scholar = scholar if scholar.startswith("http") else ""
        photos = meta.get("photos", [])
        photos = photos if isinstance(photos, list) else [photos]
        self.photos = []
        for photo in photos:
            if (self.root / photo).exists():
                self.photos.append(photo)
            else:
                self.report.warn(self.home.path, None, f"the photo '{photo}' does not exist and is skipped")
        self.news = DatedList(self.content / "news.md", self.renderer, self.report, needs_dates=True)
        self.teaching = DatedList(self.content / "teaching.md", self.renderer, self.report, needs_dates=False)
        self.personal = Document(self.content / "personal.md")
        for path in sorted((self.content / "publications").glob("*.md")):
            try:
                self.papers.append(Paper(path, self.root, self.renderer, self.people, self.report))
            except ContentError as error:
                self.report.fail(error.path, error.line, error.message)
        ids = [p.id for p in self.papers]
        for duplicate in {i for i in ids if ids.count(i) > 1}:
            self.report.fail(self.content / "publications", None, f"two papers share the id '{duplicate}'; give one a different 'id:'")
        self.papers.sort(key=lambda p: p.sort_key, reverse=True)

    def build(self):
        pages = {}
        try:
            self.load()
            if self.report.errors:
                return pages
            built = [HomePage(self), PublicationsPage(self), PersonalPage(self), NewsPage(self)]
            for page in built:
                pages[page.filename] = page.render()
            pages["sitemap.xml"] = self.sitemap(built)
        except ContentError as error:
            self.report.fail(error.path, error.line, error.message)
        except FileNotFoundError as error:
            self.report.fail(error.filename or "", None, "this file is missing")
        self.verify(pages)
        return pages

    @staticmethod
    def sitemap(pages):
        urls = "\n".join(f"  <url><loc>{page.canonical()}</loc></url>" for page in pages)
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "\n</urlset>\n")

    def verify(self, pages):
        ids = {name: set(re.findall(r'\bid="([^"]+)"', text)) for name, text in pages.items()}
        for name, text in pages.items():
            for target in re.findall(r'\b(?:href|src)="([^"]+)"', text):
                target = html.unescape(target)
                if target.startswith(("http://", "https://", "mailto:", "//")):
                    continue
                path, _, anchor = target.partition("#")
                if path and path not in pages and not (self.root / path).exists():
                    self.report.warn(name, None, f"links to '{target}', which does not exist")
                elif anchor and (path or name) in ids and anchor not in ids[path or name]:
                    self.report.warn(name, None, f"links to '#{anchor}', which is not on that page")

    def write(self, pages):
        written = []
        for name, text in pages.items():
            target = self.root / name
            if not target.exists() or target.read_text(encoding="utf-8") != text:
                target.write_text(text, encoding="utf-8", newline="\n")
                written.append(name)
        return written


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    builder = SiteBuilder(Path(__file__).resolve().parent)
    try:
        pages = builder.build()
    except Exception as error:
        print(f"Something unexpected went wrong ({error}). Nothing was written.")
        if "--debug" in argv:
            traceback.print_exc()
        return 2
    for warning in builder.report.warnings:
        print(f"warning  {warning}")
    if builder.report.errors:
        for error in builder.report.errors:
            print(f"ERROR    {error}")
        print("Nothing was written; the site is unchanged. Fix the line above and run the build again.")
        return 1
    if "--check" in argv:
        print(f"Check passed: {', '.join(pages)} would build.")
        return 0
    written = builder.write(pages)
    print(f"Built: {', '.join(written)}." if written else "Built: nothing changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
