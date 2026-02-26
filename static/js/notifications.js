(function () {
  const POLL_INTERVAL_MS = 40000;
  let lastCheck = null;
  let baseTitle = document.title;

  function getCookieToken() {
    const match = document.cookie.match(/(?:^|; )admin_token=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function getToken() {
    const stored = localStorage.getItem("token");
    if (stored) return stored;
    const cookieToken = getCookieToken();
    if (cookieToken) {
      localStorage.setItem("token", cookieToken);
    }
    return cookieToken;
  }

  function handleUnauthorized() {
    localStorage.removeItem("token");
    document.cookie = "admin_token=; Max-Age=0; path=/";
    window.location = "/ui/admin/login";
  }

  function buildUiUrl(path) {
    const token = getToken();
    if (!token) return "/ui/admin/login";
    const sep = path.includes("?") ? "&" : "?";
    return `${path}${sep}token=${encodeURIComponent(token)}`;
  }

  function t(key, fallback) {
    if (window.I18N && typeof I18N.t === "function") {
      return I18N.t(key);
    }
    return fallback;
  }

  function updateTitle(count) {
    if (!baseTitle) baseTitle = document.title || "Admin";
    document.title = count > 0 ? `(${count}) ${baseTitle}` : baseTitle;
  }

  function getUnseenCount() {
    const raw = localStorage.getItem("notif_unseen");
    const parsed = Number(raw || 0);
    return Number.isNaN(parsed) ? 0 : parsed;
  }

  function setUnseenCount(count) {
    const safe = Math.max(0, Number(count || 0));
    localStorage.setItem("notif_unseen", String(safe));
    updateBadge(safe);
    updateTitle(safe);
  }

  function incrementUnseen(delta) {
    const next = getUnseenCount() + Number(delta || 0);
    setUnseenCount(next);
  }

  function clearUnseen() {
    setUnseenCount(0);
  }

  function updateBadge(count) {
    const badge = document.getElementById("notificationBadge");
    if (!badge) return;
    if (count > 0) {
      badge.textContent = String(count);
      badge.classList.remove("d-none");
    } else {
      badge.classList.add("d-none");
    }
  }

  function isMuted() {
    return localStorage.getItem("notif_muted") === "1";
  }

  function updateMuteButton() {
    const btn = document.getElementById("notificationMute");
    if (!btn) return;
    const icon = btn.querySelector("i");
    const muted = isMuted();
    if (icon) {
      icon.className = muted ? "fa-solid fa-volume-xmark" : "fa-solid fa-volume-high";
    }
    btn.setAttribute("data-i18n-title", muted ? "notif_sound_off" : "notif_sound_on");
    const title = muted ? t("notif_sound_off", "Sound off") : t("notif_sound_on", "Sound on");
    btn.setAttribute("title", title);
  }

  function showToast(message, actionText, actionHref) {
    const container = document.getElementById("notificationToasts");
    if (!container) return;
    const toastEl = document.createElement("div");
    toastEl.className = "toast align-items-center text-bg-dark border-0 mb-2"; // Stone theme (was text-bg-primary blue)
    toastEl.setAttribute("role", "alert");
    toastEl.setAttribute("aria-live", "assertive");
    toastEl.setAttribute("aria-atomic", "true");
    const actionHtml = actionHref
      ? `<a class="btn btn-sm btn-secondary ms-2" href="${actionHref}" data-notif-action="1">${actionText}</a>`
      : "";
    const toastBody = document.createElement("div");
    toastBody.className = "d-flex";
    const bodyDiv = document.createElement("div");
    bodyDiv.className = "toast-body";
    bodyDiv.textContent = message;
    toastBody.appendChild(bodyDiv);
    if (actionHref) {
      const actionLink = document.createElement("a");
      actionLink.className = "btn btn-sm btn-secondary ms-2";
      actionLink.href = actionHref;
      actionLink.setAttribute("data-notif-action", "1");
      actionLink.textContent = actionText;
      toastBody.appendChild(actionLink);
    }
    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "btn-close btn-close-white me-2 m-auto";
    closeBtn.setAttribute("data-bs-dismiss", "toast");
    closeBtn.setAttribute("aria-label", "Close");
    toastBody.appendChild(closeBtn);
    toastEl.appendChild(toastBody);
    container.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { delay: 7000 });
    toast.show();
    toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
    const action = toastEl.querySelector('[data-notif-action="1"]');
    if (action) {
      action.addEventListener("click", () => {
        clearUnseen();
      });
    }
  }

  function playNormalSound(ctx) {
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = 880;
    gain.gain.value = 0.04;
    oscillator.connect(gain);
    gain.connect(ctx.destination);
    oscillator.start();
    oscillator.stop(ctx.currentTime + 0.2);
  }

  function playUrgentSound(ctx) {
    const now = ctx.currentTime;
    const pattern = [
      { freq: 1040, start: 0.0, dur: 0.12 },
      { freq: 740, start: 0.16, dur: 0.12 },
      { freq: 1200, start: 0.32, dur: 0.16 },
    ];
    pattern.forEach((p) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "square";
      osc.frequency.value = p.freq;
      gain.gain.value = 0.05;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now + p.start);
      osc.stop(now + p.start + p.dur);
    });
  }

  function playNotificationSound(mode) {
    try {
      if (isMuted()) return;
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const ctx = new AudioContext();
      if (ctx.state === "suspended") {
        ctx.resume();
      }
      if (mode === "urgent") {
        playUrgentSound(ctx);
      } else {
        playNormalSound(ctx);
      }
      setTimeout(() => ctx.close(), 800);
    } catch (err) {
      // Autoplay can be blocked; ignore silently.
    }
  }

  async function checkNotifications() {
    const token = getToken();
    if (!token) return;
    const params = lastCheck ? `?last_check=${encodeURIComponent(lastCheck)}` : "";
    try {
      const resp = await fetch(`/api/admin/notifications/check${params}`, {
        headers: { "Authorization": `Bearer ${token}` },
      });
      if (resp.status === 401) {
        handleUnauthorized();
        return;
      }
      if (!resp.ok) return;
      const data = await resp.json();
      lastCheck = data.server_time || new Date().toISOString();

      const newTasks = Number(data.new_tasks_count || 0);
      const newHandoffs = Number(data.new_handoff_count || 0);
      const criticalCount = Number(data.new_critical_count || 0);
      const urgentCount = Number(data.new_urgent_count || 0);
      const totalNew = newTasks + newHandoffs;
      const unseen = getUnseenCount();
      updateBadge(unseen);
      updateTitle(unseen);

      if (data.has_new) {
        if (totalNew > 0) {
          incrementUnseen(totalNew);
        }
        const urgentAlert = criticalCount + urgentCount > 0;
        playNotificationSound(urgentAlert ? "urgent" : "normal");
        if (newTasks > 0) {
          const msg = t("notif_new_tasks", "New tasks: {count}").replace(
            "{count}",
            String(newTasks),
          );
          showToast(msg, t("notif_view_tasks", "View tasks"), buildUiUrl("/ui/admin/tasks"));
          if (typeof window.loadTasks === "function") {
            window.loadTasks();
          }
        }
        if (newHandoffs > 0) {
          const msg = t("notif_new_handoffs", "New handoff requests: {count}").replace(
            "{count}",
            String(newHandoffs),
          );
          showToast(
            msg,
            t("notif_view_conversations", "View conversations"),
            buildUiUrl("/ui/admin/conversations"),
          );
          if (typeof window.loadConversations === "function") {
            window.loadConversations();
          }
        }
      }
    } catch (err) {
      // Keep silent on polling errors to avoid noisy UI.
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    setUnseenCount(getUnseenCount());
    updateMuteButton();
    const bell = document.getElementById("notificationBell");
    if (bell) {
      bell.addEventListener("click", () => {
        clearUnseen();
        window.location = buildUiUrl("/ui/admin/tasks");
      });
    }
    const mute = document.getElementById("notificationMute");
    if (mute) {
      mute.addEventListener("click", () => {
        const next = !isMuted();
        localStorage.setItem("notif_muted", next ? "1" : "0");
        updateMuteButton();
      });
    }
    if (!getToken()) return;
    checkNotifications();
    setInterval(checkNotifications, POLL_INTERVAL_MS);
  });
})();
