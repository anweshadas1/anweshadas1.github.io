# anweshadas1.github.io

Personal academic website of Anwesha Das, served by GitHub Pages.

The pages are written in Markdown and built into static HTML:

```
content/            the words: home.md, news.md, teaching.md, personal.md, publications/*.md
templates/page.html the shared page shell
people.js           co-authors and their web pages
build.py            turns content/ into index.html, publications.html, personal.html, news.html
style.css, js/      appearance and small interactions
fonts/              Eczar, Alegreya and Alegreya Sans, served locally, with their licences (SIL OFL 1.1)
```

To rebuild after editing anything in `content/`:

```
pip install markdown pillow
python build.py
python tests/test_build.py
```

The HTML files are build output; edit `content/` instead.
