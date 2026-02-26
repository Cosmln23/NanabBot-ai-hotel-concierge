/**
 * Subscription Status Management
 * Common script for all admin pages to handle trial banners and subscription links
 */

(function() {
  'use strict';

  // Get token from URL or localStorage
  function getToken() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('token') || localStorage.getItem('token') || localStorage.getItem('staffToken');
  }

  // Load subscription status and update UI
  async function loadSubscriptionStatus() {
    const token = getToken();
    if (!token) return;

    try {
      const resp = await fetch('/admin/subscription-status', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!resp.ok) return;

      const data = await resp.json();

      // Get UI elements (may not exist on all pages)
      const trialBanner = document.getElementById('trialBanner');
      const expiredBanner = document.getElementById('trialExpiredBanner');
      const daysLeftEl = document.getElementById('trialDaysLeft');
      const subscriptionLink = document.getElementById('subscriptionLinkSidebar');
      const aiSettingsLink = document.getElementById('aiSettingsLinkSidebar');
      const integrationsLink = document.getElementById('integrationsLinkSidebar');

      // Hide banners initially
      if (trialBanner) trialBanner.classList.add('d-none');
      if (expiredBanner) expiredBanner.classList.add('d-none');
      if (subscriptionLink) subscriptionLink.classList.add('d-none');

      if (data.tier === 'free') {
        if (data.is_expired) {
          // Trial expired - show red banner
          if (expiredBanner) expiredBanner.classList.remove('d-none');

          // Block AI Settings and Integrations
          if (aiSettingsLink) {
            aiSettingsLink.classList.add('disabled', 'text-muted');
            aiSettingsLink.style.pointerEvents = 'none';
            aiSettingsLink.innerHTML = '<i class="fa-solid fa-lock"></i> <span data-i18n="nav_ai_settings">AI Settings</span>';
          }
          if (integrationsLink) {
            integrationsLink.classList.add('disabled', 'text-muted');
            integrationsLink.style.pointerEvents = 'none';
            integrationsLink.innerHTML = '<i class="fa-solid fa-lock"></i> <span data-i18n="nav_integrations">Integrations</span>';
          }
        } else if (data.days_remaining !== null) {
          // Trial active - show yellow banner with days remaining
          if (trialBanner) trialBanner.classList.remove('d-none');
          if (daysLeftEl) daysLeftEl.textContent = data.days_remaining;
        }
      } else if (data.tier === 'basic' || data.tier === 'pro') {
        // Show subscription management link for paying customers
        if (subscriptionLink) {
          subscriptionLink.classList.remove('d-none');
        }
      }

      // Re-apply i18n translations after updating innerHTML
      if (typeof I18N !== 'undefined' && I18N.applyTranslations) {
        I18N.applyTranslations();
      }

    } catch (err) {
      console.error('Failed to load subscription status:', err);
    }
  }

  // Setup subscription link click handler
  function setupSubscriptionLink() {
    const subscriptionLink = document.getElementById('subscriptionLinkSidebar');
    if (!subscriptionLink) return;

    subscriptionLink.addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        const resp = await fetch('/api/stripe/customer-portal', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        if (resp.ok) {
          const data = await resp.json();
          window.location.href = data.portal_url;
        } else {
          console.error('Failed to open customer portal');
        }
      } catch (err) {
        console.error('Error opening customer portal:', err);
      }
    });
  }

  // Initialize when DOM is ready
  function init() {
    loadSubscriptionStatus();
    setupSubscriptionLink();
  }

  // Run on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
