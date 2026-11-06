class BibtexCopy {
  constructor(element, patience = 800) {
    this.element = element;
    this.source = element.querySelector("pre");
    this.button = element.querySelector("button");
    this.label = this.button ? this.button.textContent : "";
    this.patience = patience;
  }

  static within(promise, ms) {
    return Promise.race([
      promise,
      new Promise((_, reject) => setTimeout(() => reject(new Error("timed out")), ms))
    ]);
  }

  selectAndCopy() {
    const range = document.createRange();
    range.selectNodeContents(this.source);
    const selection = getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    try { return document.execCommand("copy"); } catch (e) { return false; }
  }

  flash(message) {
    this.button.textContent = message;
    setTimeout(() => { this.button.textContent = this.label; }, 1800);
  }

  async copy() {
    const text = this.source.textContent.trim();
    let copied;
    try {
      await BibtexCopy.within(navigator.clipboard.writeText(text), this.patience);
      copied = true;
    } catch (e) {
      copied = this.selectAndCopy();
    }
    this.flash(copied ? "Copied" : "Selected: press Ctrl+C");
  }

  start() {
    if (!this.source || !this.button) return;
    this.button.addEventListener("click", () => this.copy());
  }
}

Site.register("bibtex", BibtexCopy);
