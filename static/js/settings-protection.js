/**
 * Settings Protection - Password verification utility
 *
 * NOTE: Page-level protection is now built into each protected page
 * (ai_settings.html, integrations.html). This file is kept for backwards
 * compatibility but no longer intercepts navigation or stores unlock state.
 *
 * Each protected page shows a password modal immediately on load and
 * requires verification before showing content.
 */

(function() {
  // Get auth token
  function getToken() {
    return localStorage.getItem('token') || localStorage.getItem('staffToken') || '';
  }

  // Verify password with backend
  async function verifyPassword(password) {
    const token = getToken();
    if (!token) return { success: false, error: 'Not authenticated' };

    try {
      const resp = await fetch('/api/admin/verify-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ password })
      });
      const data = await resp.json();
      return { success: resp.ok, error: data.detail || 'Invalid password' };
    } catch (err) {
      console.error('Password verification error:', err);
      return { success: false, error: 'Network error' };
    }
  }

  // Export utility functions (kept for backwards compatibility)
  window.SettingsProtection = {
    verifyPassword,
    getToken
  };
})();
