(() => {
  let deferredPrompt = null;

  function isIos() {
    return /iphone|ipad|ipod/i.test(navigator.userAgent);
  }

  function isStandalone() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true
    );
  }

  function installButtons() {
    return document.querySelectorAll("[data-pwa-install]");
  }

  function statusEls() {
    return document.querySelectorAll("[data-pwa-install-status]");
  }

  function iosHints() {
    return document.querySelectorAll("[data-pwa-ios-hint]");
  }

  function setStatus(text) {
    statusEls().forEach((el) => {
      el.textContent = text;
      el.hidden = !text;
    });
  }

  function showButtons(show) {
    installButtons().forEach((btn) => {
      btn.hidden = !show;
      btn.disabled = !show;
    });
  }

  function refreshUi() {
    if (isStandalone()) {
      showButtons(false);
      iosHints().forEach((el) => {
        el.hidden = true;
      });
      setStatus("La app ya está instalada en este dispositivo.");
      return;
    }

    if (isIos()) {
      showButtons(false);
      iosHints().forEach((el) => {
        el.hidden = false;
      });
      setStatus("");
      return;
    }

    iosHints().forEach((el) => {
      el.hidden = true;
    });

    showButtons(true);
    if (deferredPrompt) {
      setStatus("Tocá el botón para instalar la app en este dispositivo.");
      return;
    }

    setStatus(
      "Si el navegador no abre el diálogo, usá el menú (⋮) → Instalar app / Agregar a pantalla de inicio. Hace falta HTTPS (Chrome/Edge en Android)."
    );
  }

  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) {
      return;
    }
    try {
      await navigator.serviceWorker.register("/sw.js", { scope: "/" });
    } catch (error) {
      console.warn("PWA: no se pudo registrar service worker", error);
    }
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    refreshUi();
  });

  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    refreshUi();
  });

  document.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const btn = target.closest("[data-pwa-install]");
    if (!btn) {
      return;
    }
    if (!deferredPrompt) {
      setStatus(
        "El navegador aún no ofrece el diálogo automático. Usá el menú (⋮) → Instalar app / Agregar a pantalla de inicio."
      );
      return;
    }
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    refreshUi();
  });

  refreshUi();
  registerServiceWorker();
})();
