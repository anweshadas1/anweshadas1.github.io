class AuthorList {
  constructor(element, people = PEOPLE, me = ME) {
    this.element = element;
    this.people = new Map(Object.entries(people).map(([name, url]) => [AuthorList.key(name), url]));
    this.me = AuthorList.key(me);
  }

  static key(name) {
    return name.normalize("NFC").replace(/\s+/g, " ").trim();
  }

  names() {
    return this.element.textContent.split(",").map(AuthorList.key).filter(Boolean);
  }

  node(name) {
    if (name === this.me) {
      const self = document.createElement("span");
      self.className = "me";
      self.textContent = name;
      return self;
    }
    const url = this.people.get(name);
    if (!url) {
      console.warn(`people.js has no entry for "${name}", so it is shown without a link.`);
      return document.createTextNode(name);
    }
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = name;
    return link;
  }

  start() {
    const names = this.names();
    this.element.textContent = "";
    names.forEach((name, i) => {
      if (i > 0) this.element.append(", ");
      this.element.append(this.node(name));
    });
  }
}

Site.register("authors", AuthorList);
