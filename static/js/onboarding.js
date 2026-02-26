/**
 * AI Hotel Suite Onboarding Tour
 * Uses Driver.js for interactive walkthrough
 */

const ONBOARDING_KEY = 'app_onboarding_seen';
const INTEGRATIONS_TOUR_KEY = 'integrations_tour_seen';
const ONBOARDING_VERSION = '1'; // Increment to show tour again after major updates

// Check if onboarding should be shown
function shouldShowOnboarding() {
  const seen = localStorage.getItem(ONBOARDING_KEY);
  return !seen || seen !== ONBOARDING_VERSION;
}

// Mark onboarding as complete and enable password protection
function markOnboardingSeen() {
  localStorage.setItem(ONBOARDING_KEY, ONBOARDING_VERSION);
  localStorage.setItem('first_setup_done', 'true'); // Enable password protection after first tour
}

// Get current page type
function getCurrentPage() {
  const path = window.location.pathname;
  if (path.includes('/settings/ai')) return 'ai_settings';
  if (path.includes('/settings/integrations')) return 'integrations';
  if (path.includes('/conversations/')) return 'conversation_detail';
  if (path.includes('/conversations')) return 'conversations';
  if (path.includes('/tasks')) return 'tasks';
  return 'unknown';
}

// Build steps for AI Settings page
function getAiSettingsSteps() {
  return [
    {
      popover: {
        title: I18N.t('onb_welcome_title'),
        description: I18N.t('onb_welcome_desc'),
        side: 'center',
        align: 'center'
      }
    },
    {
      element: '#aiSettingsLinkSidebar, .nav-item.active:has([data-i18n="nav_ai_settings"])',
      popover: {
        title: I18N.t('onb_ai_settings_title'),
        description: I18N.t('onb_ai_settings_desc'),
        side: 'right',
        align: 'start'
      }
    },
    {
      element: '#cardWelcome, .card:first-of-type',
      popover: {
        title: I18N.t('onb_welcome_msg_title'),
        description: I18N.t('onb_welcome_msg_desc'),
        side: 'bottom',
        align: 'start'
      }
    },
    {
      element: '#cardFacts, .card:nth-of-type(2)',
      popover: {
        title: I18N.t('onb_facts_title'),
        description: I18N.t('onb_facts_desc'),
        side: 'bottom',
        align: 'start'
      }
    },
    {
      element: '#cardKnowledge, .card:nth-of-type(3)',
      popover: {
        title: I18N.t('onb_kb_title'),
        description: I18N.t('onb_kb_desc'),
        side: 'bottom',
        align: 'start'
      }
    },
    {
      element: '#cardServices, .card:nth-of-type(4)',
      popover: {
        title: I18N.t('onb_services_title'),
        description: I18N.t('onb_services_desc'),
        side: 'bottom',
        align: 'start'
      }
    },
    {
      element: '#cardSecurity, .card:nth-of-type(5)',
      popover: {
        title: I18N.t('onb_security_title'),
        description: I18N.t('onb_security_desc'),
        side: 'bottom',
        align: 'start'
      }
    },
    {
      element: 'button[type="submit"]',
      popover: {
        title: I18N.t('onb_save_title'),
        description: I18N.t('onb_save_desc'),
        side: 'top',
        align: 'center'
      }
    },
    {
      element: '#integrationsLinkSidebar',
      popover: {
        title: I18N.t('onb_integrations_title'),
        description: I18N.t('onb_integrations_desc'),
        side: 'right',
        align: 'start'
      }
    },
    {
      element: '#conversationsLinkSidebar',
      popover: {
        title: I18N.t('onb_conversations_title'),
        description: I18N.t('onb_conversations_desc'),
        side: 'right',
        align: 'start'
      }
    },
    {
      element: '#tasksLinkSidebar',
      popover: {
        title: I18N.t('onb_tasks_title'),
        description: I18N.t('onb_tasks_desc'),
        side: 'right',
        align: 'start'
      }
    },
    {
      element: '#notificationBell',
      popover: {
        title: I18N.t('onb_notifications_title'),
        description: I18N.t('onb_notifications_desc'),
        side: 'bottom',
        align: 'end'
      }
    },
    {
      element: '.sidebar-footer, #changePasswordBtn',
      popover: {
        title: I18N.t('onb_profile_title'),
        description: I18N.t('onb_profile_desc'),
        side: 'top',
        align: 'start'
      }
    },
    {
      popover: {
        title: I18N.t('onb_finish_title'),
        description: I18N.t('onb_finish_desc'),
        side: 'center',
        align: 'center'
      }
    }
  ];
}

// Build steps for Integrations page
function getIntegrationsSteps() {
  return [
    {
      element: '#cardPms, .col-md-4:first-child .card',
      popover: {
        title: I18N.t('onb_pms_title'),
        description: I18N.t('onb_pms_desc'),
        side: 'bottom',
        align: 'start'
      }
    },
    {
      element: '#cardMessaging, .col-md-8 .card',
      popover: {
        title: I18N.t('onb_messaging_title'),
        description: I18N.t('onb_messaging_desc'),
        side: 'bottom',
        align: 'start'
      }
    },
    {
      element: '#roomQrSection',
      popover: {
        title: I18N.t('onb_roomqr_title'),
        description: I18N.t('onb_roomqr_desc'),
        side: 'top',
        align: 'start'
      }
    }
  ];
}

// Build steps for Conversations page
function getConversationsSteps() {
  return [
    {
      element: '.input-group:has(input[data-i18n-placeholder="conv_search_ph"])',
      popover: {
        title: I18N.t('onb_search_title'),
        description: I18N.t('onb_search_desc'),
        side: 'bottom',
        align: 'end'
      }
    },
    {
      element: '#conversations-table',
      popover: {
        title: I18N.t('onb_chatlist_title'),
        description: I18N.t('onb_chatlist_desc'),
        side: 'top',
        align: 'center'
      }
    }
  ];
}

// Build steps for Conversation Detail page
function getConversationDetailSteps() {
  return [
    {
      element: '#togglePauseBtn',
      popover: {
        title: I18N.t('onb_takecontrol_title'),
        description: I18N.t('onb_takecontrol_desc'),
        side: 'left',
        align: 'start'
      }
    },
    {
      element: '#manualMessage',
      popover: {
        title: I18N.t('onb_manualreply_title'),
        description: I18N.t('onb_manualreply_desc'),
        side: 'top',
        align: 'center'
      }
    }
  ];
}

// Build steps for Tasks page
function getTasksSteps() {
  return [
    {
      element: '#critical-zone',
      popover: {
        title: I18N.t('onb_critical_title'),
        description: I18N.t('onb_critical_desc'),
        side: 'bottom',
        align: 'start'
      }
    },
    {
      element: '#task-tabs',
      popover: {
        title: I18N.t('onb_filters_title'),
        description: I18N.t('onb_filters_desc'),
        side: 'bottom',
        align: 'start'
      }
    }
  ];
}

// Start the onboarding tour
function startOnboarding() {
  if (typeof driver === 'undefined' || typeof driver.js === 'undefined') {
    console.warn('Driver.js not loaded');
    return;
  }

  const currentPage = getCurrentPage();
  let steps = [];
  let tourKey = ONBOARDING_KEY;

  // Determine which tour to show based on current page
  if (currentPage === 'ai_settings') {
    steps = getAiSettingsSteps();
    tourKey = ONBOARDING_KEY;
  } else if (currentPage === 'integrations') {
    // Check if integrations tour already seen
    if (localStorage.getItem(INTEGRATIONS_TOUR_KEY)) {
      return;
    }
    steps = getIntegrationsSteps();
    tourKey = INTEGRATIONS_TOUR_KEY;
  } else {
    // For other pages, don't auto-start
    return;
  }

  // Filter out steps with missing elements (except popover-only steps)
  steps = steps.filter(step => {
    if (!step.element) return true; // Popover-only steps always included
    const el = document.querySelector(step.element.split(',')[0]);
    return el !== null;
  });

  if (steps.length === 0) return;

  const driverObj = driver.js.driver({
    showProgress: true,
    steps: steps,
    nextBtnText: I18N.t('onb_next') || 'Next',
    prevBtnText: I18N.t('onb_prev') || 'Previous',
    doneBtnText: I18N.t('onb_done') || 'Done',
    onDestroyStarted: () => {
      // Mark the appropriate tour as seen
      if (tourKey === ONBOARDING_KEY) {
        markOnboardingSeen();
      } else {
        localStorage.setItem(tourKey, 'true');
      }
      driverObj.destroy();
    }
  });

  // Small delay to ensure page is fully loaded
  setTimeout(() => {
    driverObj.drive();
  }, 500);
}

// Manual trigger for tour (can be called from Help page or menu)
function restartOnboarding() {
  localStorage.removeItem(ONBOARDING_KEY);
  const token = localStorage.getItem('token');
  const url = '/ui/admin/settings/ai' + (token ? '?token=' + encodeURIComponent(token) : '');
  window.location.href = url;
}

// Expose to window for manual trigger
window.restartOnboarding = restartOnboarding;
window.startOnboarding = startOnboarding;

// Check if any tour should be shown on current page
function shouldShowAnyTour() {
  const currentPage = getCurrentPage();

  if (currentPage === 'ai_settings') {
    return shouldShowOnboarding();
  } else if (currentPage === 'integrations') {
    return !localStorage.getItem(INTEGRATIONS_TOUR_KEY);
  }
  return false;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function () {
  // Wait for password modal to be handled first
  setTimeout(() => {
    const firstSetupDone = localStorage.getItem('first_setup_done');

    // For first-time users, skip all protection checks and start tour
    if (!firstSetupDone) {
      if (shouldShowAnyTour()) {
        startOnboarding();
      }
      return;
    }

    // For existing users, check if protected content is showing
    const passwordModal = document.getElementById('passwordModal');
    const pinModal = document.getElementById('pinModal');
    const protectedOverlay = document.getElementById('protectedOverlay');

    // Don't start if protected content is showing (check computed style)
    if (protectedOverlay) {
      const computedDisplay = window.getComputedStyle(protectedOverlay).display;
      if (computedDisplay !== 'none') {
        return;
      }
    }

    // Don't start if modals are open
    if ((passwordModal && passwordModal.classList.contains('show')) ||
      (pinModal && pinModal.classList.contains('show'))) {
      return;
    }

    if (shouldShowAnyTour()) {
      startOnboarding();
    }
  }, 1500); // Wait for auth to complete
});
