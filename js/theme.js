class ThemeToggle {
  constructor(button, root = document.documentElement, key = "theme") {
    this.button = button;
    this.root = root;
    this.key = key;
  }

  get current() {
    return this.root.dataset.theme === "dark" ? "dark" : "light";
  }

  set(theme) {
    this.root.dataset.theme = theme;
    this.button.setAttribute("aria-pressed", String(theme === "dark"));
    try { localStorage.setItem(this.key, theme); } catch (e) {}
  }

  start() {
    this.button.setAttribute("aria-pressed", String(this.current === "dark"));
    this.button.addEventListener("click", () => this.set(this.current === "dark" ? "light" : "dark"));
  }
}

class Gaze {
  constructor(button, reach = 2.2, range = 110) {
    this.button = button;
    this.pupil = button.querySelector(".gaze");
    this.reach = reach;
    this.range = range;
    this.pending = false;
    this.x = 0;
    this.y = 0;
  }

  look() {
    this.pending = false;
    const box = this.button.getBoundingClientRect();
    const dx = this.x - (box.left + box.width / 2);
    const dy = this.y - (box.top + box.height / 2);
    const dist = Math.hypot(dx, dy);
    if (dist < 1) return;
    const r = Math.min(dist / this.range, 1) * this.reach;
    this.pupil.style.transform = `translate(${(dx / dist * r).toFixed(2)}px, ${(dy / dist * r * 0.72).toFixed(2)}px)`;
  }

  start() {
    if (!this.pupil || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    addEventListener("pointermove", (e) => {
      this.x = e.clientX;
      this.y = e.clientY;
      if (!this.pending) {
        this.pending = true;
        requestAnimationFrame(() => this.look());
      }
    }, { passive: true });
    addEventListener("blur", () => { this.pupil.style.transform = ""; });
  }
}

Site.register("theme", ThemeToggle);
Site.register("gaze", Gaze);
