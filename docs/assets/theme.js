(function () {
  var KEY = "ezy-theme";
  var root = document.documentElement;
  var stored = localStorage.getItem(KEY);
  if (stored) root.setAttribute("data-theme", stored);

  function current() {
    var attr = root.getAttribute("data-theme");
    if (attr) return attr;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    localStorage.setItem(KEY, theme);
    var btn = document.querySelector(".theme-toggle");
    if (btn) btn.textContent = theme === "dark" ? "\u25CF" : "\u25CB";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.querySelector(".theme-toggle");
    if (!btn) return;
    btn.textContent = current() === "dark" ? "\u25CF" : "\u25CB";
    btn.addEventListener("click", function () {
      apply(current() === "dark" ? "light" : "dark");
    });
  });
})();
