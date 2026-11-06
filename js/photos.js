class PhotoCycler {
  constructor(img) {
    this.img = img;
    this.photos = (img.dataset.photos || img.getAttribute("src")).split(/\s+/).filter(Boolean);
    this.index = Math.max(0, this.photos.indexOf(img.getAttribute("src")));
  }

  preload() {
    this.photos.forEach((src) => { new Image().src = src; });
  }

  show(index) {
    this.index = (index + this.photos.length) % this.photos.length;
    this.img.src = this.photos[this.index];
    this.img.dataset.index = String(this.index);
  }

  next() {
    this.show(this.index + 1);
  }

  start() {
    if (this.photos.length < 2) return;
    this.preload();
    this.img.classList.add("cycles");
    this.img.dataset.index = String(this.index);
    this.img.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse") this.next(); });
    this.img.addEventListener("click", () => this.next());
  }
}

Site.register("photos", PhotoCycler);
