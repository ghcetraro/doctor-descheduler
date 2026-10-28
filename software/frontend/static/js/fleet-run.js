(() => {
  const panel = document.getElementById("run-live");
  const title = document.getElementById("run-live-title");
  const logEl = document.getElementById("run-live-log");
  if (!panel || !title || !logEl) {
    return;
  }

  let timer = 0;
  let active = "";

  function dash(value) {
    return value === null || value === undefined || value === "" ? "—" : String(value);
  }

  function paintRow(row) {
    const tr = document.querySelector(`tr[data-cluster="${CSS.escape(row.id)}"]`);
    if (!tr) {
      return;
    }
    const status = tr.querySelector('[data-field="status"]');
    const mode = tr.querySelector('[data-field="mode"]');
    const last = tr.querySelector('[data-field="last"]');
    const over = tr.querySelector('[data-field="over"]');
    const under = tr.querySelector('[data-field="under"]');
    const evicted = tr.querySelector('[data-field="evicted"]');
    if (status) {
      status.textContent = row.ok ? "ok" : row.error || "sin datos";
    }
    if (mode) {
      if (row.dry_run === true) {
        mode.textContent = "dry-run";
      } else if (row.dry_run === false) {
        mode.textContent = "real";
      } else {
        mode.textContent = "—";
      }
    }
    if (last) {
      last.textContent = dash(row.last_start);
    }
    if (over) {
      over.textContent = dash(row.overutilized);
    }
    if (under) {
      under.textContent = dash(row.underutilized);
    }
    if (evicted) {
      evicted.textContent = dash(row.evicted);
    }
  }

  function render(lines) {
    logEl.textContent = (lines || []).join("\n");
    logEl.scrollTop = logEl.scrollHeight;
  }

  function setBusy(button, busy) {
    const spinner = button.querySelector(".run-spinner");
    const label = button.querySelector(".run-label");
    button.disabled = busy;
    button.classList.toggle("is-running", busy);
    if (spinner) {
      spinner.hidden = !busy;
    }
    if (label) {
      label.textContent = busy ? "Ejecutando…" : "Ejecutar";
    }
  }

  function stopPoll() {
    if (timer) {
      window.clearInterval(timer);
      timer = 0;
    }
  }

  async function poll(clusterId) {
    const response = await fetch(`/api/v1/clusters/${encodeURIComponent(clusterId)}/progress`, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return null;
    }
    return response.json();
  }

  async function refreshFleet() {
    const response = await fetch("/api/v1/fleet", {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    (payload.clusters || []).forEach(paintRow);
  }

  async function watch(clusterId, button) {
    const refresh = document.querySelector('meta[http-equiv="refresh"]');
    if (refresh) {
      refresh.remove();
    }
    active = clusterId;
    panel.hidden = false;
    panel.classList.add("is-running");
    title.textContent = `Pasada de ${clusterId}`;
    render(["Arrancando…"]);
    setBusy(button, true);
    stopPoll();
    timer = window.setInterval(async () => {
      if (active !== clusterId) {
        return;
      }
      try {
        const data = await poll(clusterId);
        if (data && active === clusterId) {
          render(data.lines && data.lines.length ? data.lines : ["Arrancando…"]);
        }
      } catch (_err) {
        /* el POST informa el fallo */
      }
    }, 800);

    let detail = "";
    let ok = false;
    try {
      const response = await fetch(`/api/v1/clusters/${encodeURIComponent(clusterId)}/run`, {
        method: "POST",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      ok = response.ok;
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        detail = body.detail || `No se pudo ejecutar ${clusterId}.`;
      }
    } catch (_err) {
      detail = `No se pudo ejecutar ${clusterId}.`;
    }

    stopPoll();
    try {
      const data = await poll(clusterId);
      const lines = (data && data.lines) || [];
      if (detail && lines.indexOf(detail) === -1) {
        lines.push(detail);
      }
      render(lines.length ? lines : [detail || "Pasada terminada."]);
    } catch (_err) {
      if (detail) {
        render([detail]);
      }
    }
    panel.classList.remove("is-running");
    setBusy(button, false);
    if (ok) {
      try {
        await refreshFleet();
      } catch (_err2) {
        /* la tabla se actualiza en el próximo ingreso */
      }
    }
    if (active === clusterId) {
      active = "";
    }
  }

  document.querySelectorAll(".run-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const clusterId = button.getAttribute("data-cluster") || "";
      if (!clusterId || button.disabled) {
        return;
      }
      watch(clusterId, button);
    });
  });
})();
