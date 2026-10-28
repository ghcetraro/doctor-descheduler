(() => {
  const toggle = document.getElementById("sidebar-toggle");
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebar-backdrop");

  if (!toggle || !sidebar) {
    return;
  }

  function setOpen(open) {
    sidebar.classList.toggle("open", open);
    if (backdrop) {
      backdrop.hidden = !open;
    }
    toggle.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
  }

  toggle.addEventListener("click", () => {
    setOpen(!sidebar.classList.contains("open"));
  });

  if (backdrop) {
    backdrop.addEventListener("click", () => setOpen(false));
  }

  sidebar.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    if (target.closest("a, button")) {
      setOpen(false);
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 900) {
      setOpen(false);
    }
  });
})();

(() => {
  function appSlug() {
    return document.documentElement.dataset.appSlug || "app";
  }

  function configTabKey() {
    return appSlug() + "-config-tab";
  }

  function activateTab(root, tabName) {
    root.querySelectorAll(".tabs-trigger").forEach((trigger) => {
      const active = trigger.getAttribute("data-tab") === tabName;
      trigger.classList.toggle("active", active);
      trigger.setAttribute("aria-selected", String(active));
      trigger.tabIndex = active ? 0 : -1;
    });
    root.querySelectorAll(".tabs-panel").forEach((panel) => {
      const active = panel.getAttribute("data-tab-panel") === tabName;
      panel.classList.toggle("active", active);
      panel.hidden = !active;
    });
  }

  function initTabs(root) {
    const triggers = Array.from(root.querySelectorAll(".tabs-trigger"));
    if (!triggers.length) {
      return;
    }

    let initialTab = triggers[0].getAttribute("data-tab") || "";
    const urlTab = new URLSearchParams(window.location.search).get("tab");
    if (urlTab && triggers.some((t) => t.getAttribute("data-tab") === urlTab)) {
      initialTab = urlTab;
    } else {
      try {
        const stored = localStorage.getItem(configTabKey());
        if (stored && triggers.some((t) => t.getAttribute("data-tab") === stored)) {
          initialTab = stored;
        }
      } catch (_err) {
        /* ignore */
      }
    }

    const initialFromDom = root.getAttribute("data-initial-tab");
    if (initialFromDom && triggers.some((t) => t.getAttribute("data-tab") === initialFromDom)) {
      initialTab = initialFromDom;
    }

    activateTab(root, initialTab);

    triggers.forEach((trigger) => {
      trigger.addEventListener("click", () => {
        const tabName = trigger.getAttribute("data-tab");
        if (!tabName) {
          return;
        }
        activateTab(root, tabName);
        try {
          localStorage.setItem(configTabKey(), tabName);
        } catch (_err) {
          /* ignore */
        }
      });
    });
  }

  document.querySelectorAll("[data-tabs]").forEach(initTabs);
})();

(() => {
  const dialog = document.getElementById("info-dialog");
  const titleEl = document.getElementById("info-dialog-title");
  const bodyEl = document.getElementById("info-dialog-body");
  if (!dialog || !titleEl || !bodyEl) {
    return;
  }

  function openInfo(btn) {
    const targetId = btn.getAttribute("data-info-for");
    const titleAttr = btn.getAttribute("data-info-title");
    let html = btn.getAttribute("data-info-html") || "";
    let title = titleAttr || "Información";

    if (targetId) {
      const src = document.getElementById(targetId);
      if (src) {
        html = src.tagName === "TEMPLATE" ? src.innerHTML : src.innerHTML;
        if (!titleAttr) {
          const heading = btn
            .closest(".panel-heading, .subtitle, .topbar-copy")
            ?.querySelector("h2, h1");
          if (heading) {
            title = heading.textContent.trim() || title;
          }
        }
      }
    }

    titleEl.textContent = title;
    bodyEl.innerHTML = html || "<p>Sin detalle.</p>";
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
  }

  document.addEventListener("click", (event) => {
    const btn = event.target.closest(".info-btn, .log-btn");
    if (!btn) {
      return;
    }
    event.preventDefault();
    openInfo(btn);
  });
})();
