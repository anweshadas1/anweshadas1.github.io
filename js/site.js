class Site {
  static modules = {};

  static register(name, Module) {
    Site.modules[name] = Module;
  }

  static start() {
    document.querySelectorAll("[data-module]").forEach((element) => {
      element.dataset.module.split(/\s+/).forEach((name) => {
        const Module = Site.modules[name];
        if (Module) new Module(element).start();
        else console.warn(`No module called "${name}" is loaded on this page.`);
      });
    });
  }
}

document.addEventListener("DOMContentLoaded", () => Site.start());
