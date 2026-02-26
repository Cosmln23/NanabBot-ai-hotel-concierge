const OWNER_TOKEN_KEY = "ownerToken";

// Store for hotels data and pending delete
let hotelsData = [];
let pendingDeleteHotelId = null;

function getToken() {
  return localStorage.getItem(OWNER_TOKEN_KEY);
}

function handleUnauthorized() {
  localStorage.removeItem(OWNER_TOKEN_KEY);
  window.location = "/ui/owner/login";
}

async function fetchWithToken(url, options = {}) {
  const token = getToken();
  if (!token) {
    handleUnauthorized();
    return null;
  }
  const mergedOptions = {
    ...(options || {}),
    headers: {
      ...(options.headers || {}),
      "Authorization": `Bearer ${token}`,
    },
  };
  const resp = await fetch(url, mergedOptions);
  if (resp.status === 401) {
    handleUnauthorized();
    return null;
  }
  return resp;
}

// Format numbers with commas
function formatNumber(num) {
  return (num || 0).toLocaleString();
}

// Format date to readable string
function formatDate(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
}

// Get tier badge class
function getTierBadgeClass(tier) {
  switch ((tier || 'free').toLowerCase()) {
    case 'pro': return 'badge-tier-pro';
    case 'basic': return 'badge-tier-basic';
    default: return 'badge-tier-free';
  }
}

// Update summary statistics
function updateSummaryStats(hotels) {
  const totalHotels = hotels.length;
  const paidHotels = hotels.filter(h => h.has_stripe).length;
  const trialHotels = hotels.filter(h => h.trial_status && h.trial_status.includes('days left')).length;
  const totalMessages = hotels.reduce((sum, h) => sum + (h.usage_30d?.messages_in || 0), 0);

  document.getElementById('statTotalHotels').textContent = formatNumber(totalHotels);
  document.getElementById('statPaidHotels').textContent = formatNumber(paidHotels);
  document.getElementById('statTrialHotels').textContent = formatNumber(trialHotels);
  document.getElementById('statTotalMessages').textContent = formatNumber(totalMessages);
}

// Render hotel row
function renderHotelRow(hotel) {
  const tierClass = getTierBadgeClass(hotel.subscription_tier);
  const tierText = (hotel.subscription_tier || 'free').charAt(0).toUpperCase() + (hotel.subscription_tier || 'free').slice(1);

  // Trial/Stripe status
  let trialStripeHtml = '';
  if (hotel.trial_status) {
    const isActive = hotel.trial_status.includes('days left');
    trialStripeHtml += `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${isActive ? 'bg-stone-200 text-stone-900' : 'bg-stone-100 text-stone-400'}">${hotel.trial_status}</span>`;
  }
  if (hotel.has_stripe) {
    trialStripeHtml += `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-stone-900 text-stone-50 ml-1"><i class="fa-solid fa-check mr-1"></i>Stripe</span>`;
  } else {
    trialStripeHtml += `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-stone-100 text-stone-500 ml-1"><i class="fa-solid fa-times mr-1"></i>No Stripe</span>`;
  }

  // Connection status
  const providerIcon = hotel.messaging_provider === 'LINE' ? 'fa-brands fa-line' : 'fa-brands fa-whatsapp';
  const providerColor = 'text-stone-900';
  const connectedClass = hotel.connected ? 'bg-stone-900 text-stone-50' : 'bg-stone-100 text-stone-400';
  const connectedText = hotel.connected ? 'Connected' : 'Disconnected';

  // Usage stats
  const usage = hotel.usage_30d || { messages_in: 0, tasks_created: 0, llm_calls: 0 };

  return `
    <tr class="hotel-row">
      <td class="px-6 py-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-stone-900 flex items-center justify-center text-white font-semibold">
            ${hotel.id}
          </div>
          <div>
            <p class="font-medium text-stone-900">${escapeHtml(hotel.name)}</p>
            <p class="text-xs text-stone-400">${hotel.admin_email || '-'}</p>
            <p class="text-xs text-stone-500">${hotel.timezone}</p>
          </div>
        </div>
      </td>
      <td class="px-6 py-4">
        <span class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold ${tierClass}">
          ${tierText}
        </span>
      </td>
      <td class="px-6 py-4">
        <div class="flex flex-wrap gap-1">
          ${trialStripeHtml}
        </div>
      </td>
      <td class="px-6 py-4">
        <div class="flex items-center gap-2">
          <i class="${providerIcon} ${providerColor}"></i>
          <span class="text-sm text-stone-600">${hotel.messaging_provider}</span>
          <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${connectedClass}">${connectedText}</span>
        </div>
      </td>
      <td class="px-6 py-4">
        <div>
          <p class="text-sm text-stone-900">${formatDate(hotel.created_at)}</p>
          <p class="text-xs text-stone-500">${hotel.months_active} months active</p>
        </div>
      </td>
      <td class="px-6 py-4">
        <div class="text-sm">
          <div class="flex items-center gap-2 text-stone-600">
            <i class="fa-solid fa-message text-xs text-stone-400"></i>
            <span>${formatNumber(usage.messages_in)}</span>
          </div>
          <div class="flex items-center gap-2 text-stone-400 text-xs mt-1">
            <span><i class="fa-solid fa-list-check mr-1"></i>${formatNumber(usage.tasks_created)}</span>
            <span><i class="fa-solid fa-robot mr-1"></i>${formatNumber(usage.llm_calls)}</span>
          </div>
        </div>
      </td>
      <td class="px-6 py-4 text-right">
        <div class="flex items-center justify-end gap-2">
          <a href="/ui/owner/hotel/${hotel.id}/setup" class="px-3 py-1.5 text-xs font-medium text-stone-600 hover:text-stone-900 bg-stone-100 hover:bg-stone-200 rounded-lg transition-colors" title="Connection Setup">
            <i class="fa-solid fa-plug"></i>
          </a>
          <a href="/ui/owner/hotels/${hotel.id}/stats" class="px-3 py-1.5 text-xs font-medium text-stone-500 hover:text-stone-900 bg-stone-100 hover:bg-stone-200 rounded-lg transition-colors" title="View Usage">
            <i class="fa-solid fa-chart-line"></i>
          </a>
          <button onclick="showConnectionInfo(${hotel.id}, '${escapeHtml(hotel.name)}')" class="px-3 py-1.5 text-xs font-medium text-stone-600 hover:text-stone-900 bg-stone-100 hover:bg-stone-200 rounded-lg transition-colors" title="Connection Info">
            <i class="fa-solid fa-info-circle"></i>
          </button>
          <button onclick="showDeleteModal(${hotel.id}, '${escapeHtml(hotel.name)}')" class="px-3 py-1.5 text-xs font-medium text-red-400 hover:text-stone-900 bg-red-500/10 hover:bg-red-500/20 rounded-lg transition-colors" title="Delete Hotel">
            <i class="fa-solid fa-trash"></i>
          </button>
        </div>
      </td>
    </tr>
  `;
}

// Escape HTML to prevent XSS
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

async function loadHotels() {
  const statusEl = document.getElementById("status");
  const tableBody = document.getElementById("hotelsTableBody");
  const emptyState = document.getElementById("emptyState");
  const tableContainer = document.getElementById("hotelsTableContainer");

  if (statusEl) {
    statusEl.classList.remove("hidden");
    statusEl.innerHTML = `<div class="inline-flex items-center gap-3 text-stone-400"><i class="fa-solid fa-spinner fa-spin"></i><span>${I18N.t('loading_common')}</span></div>`;
  }

  // Try to fetch detailed data first, fall back to basic endpoint
  let resp = await fetchWithToken("/owner/hotels/detailed");
  let isDetailed = true;

  if (!resp || !resp.ok) {
    // Fallback to basic endpoint
    resp = await fetchWithToken("/owner/hotels");
    isDetailed = false;
  }

  if (!resp) return;

  const data = await resp.json();
  hotelsData = data;

  if (statusEl) {
    statusEl.classList.add("hidden");
  }

  if (!data.length) {
    if (tableBody) tableBody.innerHTML = '';
    if (emptyState) emptyState.classList.remove("hidden");
    updateSummaryStats([]);
    return;
  }

  if (emptyState) emptyState.classList.add("hidden");

  if (isDetailed) {
    // Render detailed view
    updateSummaryStats(data);
    if (tableBody) {
      tableBody.innerHTML = data.map(h => renderHotelRow(h)).join('');
    }
  } else {
    // Fallback: render basic view with limited info
    updateSummaryStats(data.map(h => ({ ...h, usage_30d: { messages_in: 0, tasks_created: 0, llm_calls: 0 } })));
    if (tableBody) {
      tableBody.innerHTML = data.map(h => `
        <tr class="hotel-row">
          <td class="px-6 py-4">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-brand-slate flex items-center justify-center text-brand-teal font-semibold">
                ${h.id}
              </div>
              <div>
                <p class="font-medium text-stone-900">${escapeHtml(h.name)}</p>
                <p class="text-xs text-stone-500">${h.timezone}</p>
              </div>
            </div>
          </td>
          <td class="px-6 py-4" colspan="5">
            <span class="text-stone-400 text-sm">Detailed info unavailable</span>
          </td>
          <td class="px-6 py-4 text-right">
            <div class="flex items-center justify-end gap-2">
              <a href="/ui/owner/hotel/${h.id}/setup" class="px-3 py-1.5 text-xs font-medium text-stone-600 hover:text-stone-900 bg-stone-100 hover:bg-stone-200 rounded-lg transition-colors">
                <i class="fa-solid fa-plug mr-1"></i>Setup
              </a>
              <a href="/ui/owner/hotels/${h.id}/stats" class="px-3 py-1.5 text-xs font-medium text-brand-sky hover:text-stone-900 bg-brand-sky/10 hover:bg-brand-sky/20 rounded-lg transition-colors">
                <i class="fa-solid fa-chart-line mr-1"></i>Usage
              </a>
            </div>
          </td>
        </tr>
      `).join('');
    }
  }
}

// Delete modal functions
function showDeleteModal(hotelId, hotelName) {
  pendingDeleteHotelId = hotelId;
  const modal = document.getElementById("deleteModal");
  const nameEl = document.getElementById("deleteHotelName");
  if (nameEl) nameEl.textContent = hotelName;
  if (modal) modal.classList.remove("hidden");
}

function closeDeleteModal() {
  const modal = document.getElementById("deleteModal");
  if (modal) modal.classList.add("hidden");
  pendingDeleteHotelId = null;
}

async function confirmDeleteHotel() {
  if (!pendingDeleteHotelId) return;

  const confirmBtn = document.getElementById("confirmDeleteBtn");
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i>Deleting...';
  }

  const resp = await fetchWithToken(`/owner/hotels/${pendingDeleteHotelId}`, {
    method: "DELETE",
  });

  if (confirmBtn) {
    confirmBtn.disabled = false;
    confirmBtn.innerHTML = '<i class="fa-solid fa-trash mr-2"></i>Delete Hotel';
  }

  if (!resp) return;

  if (resp.ok) {
    closeDeleteModal();
    loadHotels(); // Refresh the list
  } else {
    const err = await resp.json().catch(() => ({}));
    alert(err?.detail || 'Failed to delete hotel. Please try again.');
  }
}

// Connection info modal functions
function closeConnectionModal() {
  const modal = document.getElementById("connectionInfoModal");
  if (modal) modal.classList.add("hidden");
}

async function showConnectionInfo(hotelId, hotelName) {
  const modal = document.getElementById("connectionInfoModal");
  const statusBadge = document.getElementById("connectionStatusBadge");
  const statusMsg = document.getElementById("connectionStatusMessage");
  const webhookInput = document.getElementById("connectionWebhookUrl");
  const pinInput = document.getElementById("connectionSecurityPin");
  const title = document.getElementById("connectionInfoTitle");

  if (title) title.textContent = `${I18N.t('owner_connection_info_title') || 'Connection Info'} - ${hotelName || hotelId}`;
  if (statusBadge) {
    statusBadge.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-2"></i><span>${I18N.t('owner_status_checking') || 'Checking...'}</span>`;
    statusBadge.className = "inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-slate-500/20 text-stone-400";
  }
  if (statusMsg) statusMsg.textContent = "";
  if (webhookInput) webhookInput.value = "";
  if (pinInput) pinInput.value = "";

  if (modal) modal.classList.remove("hidden");

  const resp = await fetchWithToken(`/owner/hotel/${hotelId}/connection-status`);
  if (!resp) return;
  const data = await resp.json();

  if (webhookInput && data.webhook_url) webhookInput.value = data.webhook_url;
  if (pinInput && data.security_pin) pinInput.value = data.security_pin;

  if (statusBadge) {
    if (data.status === "ok") {
      statusBadge.innerHTML = `<i class="fa-solid fa-check mr-2"></i>${I18N.t('owner_status_connected') || 'Connected'}`;
      statusBadge.className = "inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-500/20 text-green-400";
    } else {
      statusBadge.innerHTML = `<i class="fa-solid fa-exclamation-triangle mr-2"></i>${I18N.t('owner_status_error') || 'Error'}`;
      statusBadge.className = "inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-500/20 text-red-400";
    }
  }
  if (statusMsg) statusMsg.textContent = data.message || "";
}

function hotelIdFromPath() {
  const parts = window.location.pathname.split("/");
  const idxPlural = parts.indexOf("hotels");
  const idxSingular = parts.indexOf("hotel");
  const idx = idxPlural >= 0 ? idxPlural : idxSingular;
  if (idx >= 0 && parts.length > idx + 1) return parts[idx + 1];
  return null;
}

async function loadHotelStats() {
  const statusEl = document.getElementById("status");
  if (statusEl) statusEl.textContent = I18N.t('loading_common');
  const hid = hotelIdFromPath();
  if (!hid) {
    if (statusEl) statusEl.textContent = I18N.t('owner_missing_hotel_id') || 'Missing hotel id';
    return;
  }
  const resp = await fetchWithToken(`/owner/hotels/${hid}/usage/daily?days=30`);
  if (!resp) return;
  const data = await resp.json();
  const hotelTitle = document.getElementById("hotelTitle");
  if (hotelTitle) hotelTitle.textContent = `${I18N.t('owner_stats_title')} #${hid}`;
  const tbody = document.querySelector("#stats-table tbody");
  tbody.innerHTML = "";
  if (!data.length) {
    statusEl.textContent = I18N.t('no_data');
    return;
  }
  statusEl.textContent = "";
  data.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.date ? new Date(row.date).toLocaleDateString() : ""}</td>
      <td class="text-center">${row.messages_in || 0}</td>
      <td class="text-center">${row.messages_out || row.messages_out_bot || 0}</td>
      <td class="text-center">${row.tasks_created || 0}</td>
      <td class="text-center">${row.tasks_done || 0}</td>
      <td class="text-center">${row.llm_calls || 0}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function submitNewHotelForm(event) {
  event.preventDefault();
  const alertBox = document.getElementById("addHotelAlert");
  alertBox.classList.add("hidden");
  alertBox.classList.remove("bg-green-500/20", "text-green-400", "bg-red-500/20", "text-red-400");

  const payload = {
    hotel_name: document.getElementById("hotelName").value.trim(),
    hotel_timezone: document.getElementById("hotelTimezone").value.trim(),
    admin_name: document.getElementById("adminName").value.trim(),
    admin_email: document.getElementById("adminEmail").value.trim(),
    admin_password: document.getElementById("adminPassword").value,
    messaging_provider: "meta",
    interface_language: document.getElementById("hotelInterfaceLanguage")?.value || "en",
    language_locked: Boolean(document.getElementById("hotelLanguageLocked")?.checked),
  };

  if (!payload.hotel_name || !payload.hotel_timezone || !payload.admin_name || !payload.admin_email || !payload.admin_password) {
    alertBox.textContent = I18N.t("owner_err_required") || "All fields are required.";
    alertBox.classList.remove("hidden");
    alertBox.classList.add("bg-red-500/20", "text-red-400");
    return;
  }

  const token = getToken();
  if (!token) {
    handleUnauthorized();
    return;
  }

  const resp = await fetch("/owner/setup-hotel", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (resp.status === 401) {
    handleUnauthorized();
    return;
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    let message = I18N.t("owner_err_create") || "Failed to create hotel.";
    if (err?.detail) {
      if (typeof err.detail === "string") {
        message = err.detail;
      } else {
        message = JSON.stringify(err.detail);
      }
    } else if (Object.keys(err || {}).length) {
      message = JSON.stringify(err);
    }
    alertBox.textContent = message;
    alertBox.classList.remove("hidden");
    alertBox.classList.add("bg-red-500/20", "text-red-400");
    return;
  }

  const data = await resp.json();
  showSuccessInstructions(data);
  // refresh list
  loadHotels();
  document.getElementById("addHotelForm").reset();
}

function bindAddHotelForm() {
  const showBtn = document.getElementById("showAddHotelBtn");
  const hideBtn = document.getElementById("hideAddHotelBtn");
  const card = document.getElementById("addHotelCard");
  if (showBtn && card) {
    showBtn.addEventListener("click", () => {
      resetSuccessView();
      card.classList.remove("hidden");
    });
  }
  if (hideBtn && card) {
    hideBtn.addEventListener("click", () => {
      card.classList.add("hidden");
    });
  }
  const form = document.getElementById("addHotelForm");
  if (form) {
    form.addEventListener("submit", submitNewHotelForm);
  }
}

function bindLogout() {
  const btn = document.getElementById("logoutBtn");
  if (!btn) return;
  btn.addEventListener("click", () => {
    localStorage.removeItem(OWNER_TOKEN_KEY);
    window.location = "/ui/owner/login";
  });
}

function bindDeleteModal() {
  const confirmBtn = document.getElementById("confirmDeleteBtn");
  if (confirmBtn) {
    confirmBtn.addEventListener("click", confirmDeleteHotel);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bindLogout();
  bindDeleteModal();
  if (window.ownerPage === "dashboard") {
    bindAddHotelForm();
    loadHotels();
  }
  if (window.ownerPage === "hotel_stats") {
    loadHotelStats();
  }
  if (window.ownerPage === "hotel_setup") {
    loadHotelSetup();
    const saveBtn = document.getElementById("saveSetupBtn");
    if (saveBtn) saveBtn.addEventListener("click", saveHotelSetup);
    const testBtn = document.getElementById("testSetupBtn");
    if (testBtn) testBtn.addEventListener("click", testHotelConnection);
    const copyBtn = document.getElementById("copySetupWebhook");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        const url = document.getElementById("setupLineWebhook")?.value || "";
        if (!url) return;
        navigator.clipboard.writeText(url);
      });
    }
    const copyPinBtn = document.getElementById("copySetupPin");
    if (copyPinBtn) {
      copyPinBtn.addEventListener("click", () => {
        const val = document.getElementById("setupSecurityPin")?.value || "";
        if (val) navigator.clipboard.writeText(val);
      });
    }
  }
  if (window.ownerPage === "platform_settings") {
    loadPlatformSettings();
    const saveBtn = document.getElementById("savePlatformSettings");
    if (saveBtn) saveBtn.addEventListener("click", savePlatformSettings);
  }
});

function showSuccessInstructions(data) {
  const form = document.getElementById("addHotelForm");
  const successBox = document.getElementById("addHotelSuccess");
  const alertBox = document.getElementById("addHotelAlert");
  if (!form || !successBox || !alertBox) return;

  form.classList.add("hidden");
  successBox.classList.remove("hidden");
  const gotoBtn = document.getElementById("gotoSetupBtn");
  if (gotoBtn) {
    gotoBtn.onclick = () => {
      window.location = `/ui/owner/hotel/${data.hotel_id}/setup`;
    };
  }
  const pinField = document.getElementById("securityPinField");
  if (pinField && data.security_pin) {
    pinField.value = data.security_pin;
  }
  const copyPinBtn = document.getElementById("copySecurityPinBtn");
  if (copyPinBtn) {
    copyPinBtn.onclick = () => {
      const val = pinField?.value || "";
      if (val) navigator.clipboard.writeText(val);
    };
  }
  alertBox.textContent = I18N.t('owner_created_msg')
    .replace('{hotel}', data.hotel_name)
    .replace('{admin}', data.admin_email);
  alertBox.classList.remove("hidden");
  alertBox.classList.add("bg-green-500/20", "text-green-400");
}

function resetSuccessView() {
  const form = document.getElementById("addHotelForm");
  const successBox = document.getElementById("addHotelSuccess");
  const alertBox = document.getElementById("addHotelAlert");
  if (form) form.classList.remove("hidden");
  if (successBox) successBox.classList.add("hidden");
  if (alertBox) {
    alertBox.classList.add("hidden");
    alertBox.classList.remove("bg-amber-500/20", "text-amber-400");
  }
}

function toggleSetupFields(mode) {
  const waBox = document.getElementById("waFields");
  const lineBox = document.getElementById("lineFields");
  if (waBox) waBox.classList.toggle("hidden", mode !== "meta_custom");
  if (lineBox) lineBox.classList.toggle("hidden", mode !== "line");
}

async function loadHotelSetup() {
  const statusEl = document.getElementById("status");
  if (statusEl) {
    statusEl.textContent = I18N.t('loading_common');
    statusEl.classList.remove("hidden");
  }
  const hid = hotelIdFromPath();
  if (!hid) {
    if (statusEl) statusEl.textContent = I18N.t('owner_missing_hotel_id') || 'Missing hotel id';
    return;
  }
  const resp = await fetchWithToken(`/owner/hotels/${hid}/connection`);
  if (!resp) return;
  const data = await resp.json();
  const providerSelect = document.getElementById("setupProvider");
  const lineWebhook = document.getElementById("setupLineWebhook");
  const subtitle = document.getElementById("hotelSetupSubtitle");
  if (subtitle && data.hotel_id) {
    subtitle.textContent = `${I18N.t('owner_hotel_connection') || 'Hotel connection'} #${data.hotel_id}`;
  }
  if (lineWebhook && data.webhook_url) {
    lineWebhook.value = data.webhook_url;
  }
  const pinField = document.getElementById("setupSecurityPin");
  if (pinField && data.security_pin) {
    pinField.value = data.security_pin;
  }
  const langSelect = document.getElementById("setupInterfaceLanguage");
  if (langSelect && data.interface_language) {
    langSelect.value = data.interface_language;
  }
  const langLock = document.getElementById("setupLanguageLocked");
  if (langLock) {
    langLock.checked = Boolean(data.language_locked);
  }
  const lockBox = document.getElementById("setupLocked");
  if (lockBox) {
    lockBox.checked = Boolean(data.messaging_locked);
  }
  if (providerSelect) {
    let mode = "meta_default";
    if (data.messaging_provider === "line") mode = "line";
    if (data.messaging_provider === "meta" && (data.whatsapp_access_token_masked || data.whatsapp_phone_id_masked)) {
      mode = "meta_custom";
    }
    providerSelect.value = mode;
    toggleSetupFields(mode);
    providerSelect.addEventListener("change", () => toggleSetupFields(providerSelect.value));
  }
  if (statusEl) statusEl.classList.add("hidden");
}

async function saveHotelSetup() {
  const statusEl = document.getElementById("status");
  const alertBox = document.getElementById("setupAlert");
  if (alertBox) alertBox.classList.add("hidden");
  const hid = hotelIdFromPath();
  if (!hid) return;
  const modeRaw = document.getElementById("setupProvider")?.value || "meta_default";
  const mode = modeRaw.toLowerCase();
  const payload = {};

  if (mode === "line") {
    const secret = document.getElementById("setupLineSecret")?.value.trim() || "";
    const token = document.getElementById("setupLineToken")?.value.trim() || "";
    if (!secret || !token) {
      if (alertBox) {
        alertBox.textContent = I18N.t('owner_err_line_keys') || 'LINE requires Channel Secret and Access Token.';
        alertBox.className = "alert alert-danger";
        alertBox.classList.remove("hidden");
      }
      return;
    }
    payload.messaging_provider = "line";
    payload.line_channel_secret = secret;
    payload.line_channel_access_token = token;
  } else if (mode === "meta_custom") {
    const phoneId = document.getElementById("setupWaPhoneId")?.value.trim() || "";
    const accessToken = document.getElementById("setupWaAccessToken")?.value.trim() || "";
    const businessId = document.getElementById("setupWaBusinessId")?.value.trim() || "";
    if (!phoneId || !accessToken) {
      if (alertBox) {
        alertBox.textContent = I18N.t('owner_err_wa_keys') || 'Phone Number ID and Access Token are required for custom WhatsApp.';
        alertBox.className = "alert alert-danger";
        alertBox.classList.remove("hidden");
      }
      return;
    }
    payload.messaging_provider = "meta";
    payload.whatsapp_phone_id = phoneId;
    payload.whatsapp_access_token = accessToken;
    payload.whatsapp_business_account_id = businessId;
  } else {
    // meta_default / fallback: force platform defaults and clear custom keys
    payload.messaging_provider = "meta";
    payload.whatsapp_phone_id = "";
    payload.whatsapp_access_token = "";
    payload.whatsapp_business_account_id = "";
  }

  const lockBox = document.getElementById("setupLocked");
  if (lockBox) {
    payload.messaging_locked = lockBox.checked;
  }
  const langSelect = document.getElementById("setupInterfaceLanguage");
  if (langSelect) {
    payload.interface_language = langSelect.value || "en";
  }
  const langLock = document.getElementById("setupLanguageLocked");
  if (langLock) {
    payload.language_locked = Boolean(langLock.checked);
  }

  const resp = await fetchWithToken(`/owner/hotels/${hid}/connection`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp) return;
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    if (alertBox) {
      alertBox.textContent = err?.detail || I18N.t('owner_err_save_connection') || 'Failed to save connection.';
      alertBox.className = "alert alert-danger";
      alertBox.classList.remove("hidden");
    }
    return;
  }
  const data = await resp.json();
  if (document.getElementById("setupLineWebhook") && data.webhook_url) {
    document.getElementById("setupLineWebhook").value = data.webhook_url;
  }
  if (alertBox) {
    let msg = I18N.t('save_success');
    if (data.warning) msg += ` ${I18N.t('owner_warning') || 'Warning:'} ${data.warning}`;
    alertBox.textContent = msg;
    alertBox.className = "alert alert-success";
    alertBox.classList.remove("hidden");
  }
}

async function testHotelConnection() {
  const alertBox = document.getElementById("setupAlert");
  if (alertBox) alertBox.classList.add("hidden");
  const hid = hotelIdFromPath();
  if (!hid) return;
  const resp = await fetchWithToken(`/owner/hotel/${hid}/connection-status`);
  if (!resp) return;
  const data = await resp.json();
  if (alertBox) {
    alertBox.textContent = data.message || I18N.t('owner_test_completed') || 'Test completed.';
    alertBox.className = data.status === "ok" ? "alert alert-success" : "alert alert-warning";
    alertBox.classList.remove("hidden");
  }
}

function bindCopyButtons() {
  const copyMain = document.getElementById("copyWebhookUrlBtn");
  if (copyMain) {
    copyMain.addEventListener("click", () => {
      const url = document.getElementById("webhookUrlField")?.value || "";
      if (!url) return;
      navigator.clipboard.writeText(url);
    });
  }
  const copyModal = document.getElementById("copyConnectionWebhookBtn");
  if (copyModal) {
    copyModal.addEventListener("click", () => {
      const url = document.getElementById("connectionWebhookUrl")?.value || "";
      if (!url) return;
      navigator.clipboard.writeText(url);
    });
  }
}

async function loadPlatformSettings() {
  const statusEl = document.getElementById("status");
  const alertBox = document.getElementById("platformAlert");
  if (statusEl) {
    statusEl.textContent = I18N.t('loading_common');
    statusEl.classList.remove("hidden");
  }
  const resp = await fetchWithToken("/owner/platform-settings");
  if (!resp) return;
  const data = await resp.json();
  const hintOpenAI = document.getElementById("platformOpenAIHint");
  const hintResend = document.getElementById("platformResendHint");
  const hintWa = document.getElementById("platformWaHint");
  if (hintOpenAI) hintOpenAI.textContent = data.OPENAI_API_KEY ? `${I18N.t('owner_current_prefix')} ${data.OPENAI_API_KEY}` : I18N.t('owner_not_set');
  if (hintResend) hintResend.textContent = data.RESEND_API_KEY ? `${I18N.t('owner_current_prefix')} ${data.RESEND_API_KEY}` : I18N.t('owner_not_set');
  if (hintWa) hintWa.textContent = data.WHATSAPP_PLATFORM_TOKEN ? `${I18N.t('owner_current_prefix')} ${data.WHATSAPP_PLATFORM_TOKEN}` : I18N.t('owner_not_set');
  if (statusEl) statusEl.classList.add("hidden");
  if (alertBox) alertBox.classList.add("hidden");
}

async function savePlatformSettings() {
  const alertBox = document.getElementById("platformAlert");
  if (alertBox) alertBox.classList.add("hidden");
  const payload = {};
  const openaiVal = document.getElementById("platformOpenAI")?.value.trim();
  const resendVal = document.getElementById("platformResend")?.value.trim();
  const waVal = document.getElementById("platformWaToken")?.value.trim();
  if (openaiVal) payload.openai_api_key = openaiVal;
  if (resendVal) payload.resend_api_key = resendVal;
  if (waVal) payload.whatsapp_platform_token = waVal;

  const resp = await fetchWithToken("/owner/platform-settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp) return;
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    if (alertBox) {
      alertBox.textContent = err?.detail || I18N.t('owner_err_save_platform') || "Failed to save platform settings.";
      alertBox.className = "alert alert-danger";
      alertBox.classList.remove("hidden");
    }
    return;
  }
  if (alertBox) {
    alertBox.textContent = I18N.t('owner_saved') || "Saved.";
    alertBox.className = "alert alert-success";
    alertBox.classList.remove("hidden");
  }
  loadPlatformSettings();
}

function bindSuccessClose() {
  const btn = document.getElementById("closeSuccessBtn");
  if (btn) {
    btn.addEventListener("click", () => resetSuccessView());
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bindCopyButtons();
  bindSuccessClose();
  const copyPinBtn = document.getElementById("copyConnectionPinBtn");
  if (copyPinBtn) {
    copyPinBtn.addEventListener("click", () => {
      const val = document.getElementById("connectionSecurityPin")?.value || "";
      if (val) navigator.clipboard.writeText(val);
    });
  }
});
