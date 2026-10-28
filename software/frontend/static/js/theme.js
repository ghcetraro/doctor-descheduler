(() => {
  function applyThemeColor(theme) {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.content = theme === "light" ? "#f4f6f8" : "#0f1419";
    }
  }

  function updateThemeUi(theme) {
    const isLight = theme === "light";
    document.querySelectorAll("[data-theme-option]").forEach((button) => {
      const option = button.getAttribute("data-theme-option");
      const active = option === theme;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const desc = document.getElementById("theme-setting-desc");
    if (desc) {
      desc.textContent = isLight ? "Modo claro activo" : "Modo oscuro activo";
    }
  }

  function applyTheme(theme) {
    const value = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", value);
    applyThemeColor(value);
    updateThemeUi(value);
    return value;
  }

  function saveTheme(theme) {
    const value = applyTheme(theme);
    fetch("/api/v1/appearance", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ theme: value }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("save");
        }
      })
      .catch(() => {
        const desc = document.getElementById("theme-setting-desc");
        if (desc) {
          desc.textContent = "No se pudo guardar el tema.";
        }
      });
  }

  function initTheme() {
    const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
    applyTheme(current);
    document.querySelectorAll("[data-theme-option]").forEach((button) => {
      button.addEventListener("click", () => {
        saveTheme(button.getAttribute("data-theme-option") || "dark");
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTheme);
  } else {
    initTheme();
  }
})();
