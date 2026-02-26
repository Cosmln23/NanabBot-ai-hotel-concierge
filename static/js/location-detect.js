/**
 * Automatic Location & Language Detection
 * Detects user's country via IP geolocation and sets appropriate language/region
 */

// Configuration
const GEO_API_URL = 'https://ipapi.co/json/';
const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

// Country to language mapping
const COUNTRY_LANG_MAP = {
  'TH': 'th',  // Thailand -> Thai
  'RO': 'ro',  // Romania -> Romanian
};

/**
 * Main detection function
 * @returns {Promise<{country: string, lang: string}>}
 */
async function detectLocation() {
  try {
    // Step 1: Check localStorage cache (for speed)
    const cachedCountry = localStorage.getItem('detectedCountry');
    const cacheTimestamp = localStorage.getItem('detectedCountryTime');

    if (cachedCountry && cacheTimestamp) {
      const age = Date.now() - parseInt(cacheTimestamp);
      if (age < CACHE_DURATION) {
        // Cache is fresh, use it
        const lang = COUNTRY_LANG_MAP[cachedCountry] || 'en';
        return { country: cachedCountry, lang };
      }
    }

    // Step 2: Fetch from IP Geolocation API
    const response = await fetch(GEO_API_URL, {
      timeout: 3000,
      signal: AbortSignal.timeout(3000)
    });

    if (!response.ok) throw new Error('API request failed');

    const data = await response.json();
    const country = data.country_code || 'OTHER';
    const lang = COUNTRY_LANG_MAP[country] || 'en';

    // Save to localStorage with timestamp
    localStorage.setItem('detectedCountry', country);
    localStorage.setItem('detectedCountryTime', Date.now().toString());
    localStorage.setItem('app_lang', lang);

    return { country, lang };

  } catch (error) {
    // Step 3: Fallback to browser language
    const browserLang = (navigator.language || navigator.userLanguage || 'en').slice(0, 2).toLowerCase();
    const country = Object.keys(COUNTRY_LANG_MAP).find(k => COUNTRY_LANG_MAP[k] === browserLang) || 'OTHER';
    const lang = COUNTRY_LANG_MAP[country] || browserLang;

    // Cache fallback result too (shorter duration)
    localStorage.setItem('detectedCountry', country);
    localStorage.setItem('detectedCountryTime', Date.now().toString());
    localStorage.setItem('app_lang', lang);

    return { country, lang };
  }
}

/**
 * Update links with detected country parameter
 * @param {string} country - Detected country code
 */
function updateLinksWithCountry(country) {
  // Find all links pointing to /register
  const registerLinks = document.querySelectorAll('a[href*="/register"]');

  registerLinks.forEach(link => {
    const href = link.getAttribute('href');
    const url = new URL(href, window.location.origin);

    // Add country parameter if not already present
    if (!url.searchParams.has('country')) {
      url.searchParams.set('country', country);
      link.setAttribute('href', url.pathname + url.search);
    }
  });
}

/**
 * Get current detected location
 * @returns {{country: string, lang: string}}
 */
function getCurrentLocation() {
  const country = localStorage.getItem('detectedCountry') || 'OTHER';
  const lang = localStorage.getItem('app_lang') || 'en';
  return { country, lang };
}

/**
 * Clear cached location (for testing)
 */
function clearLocationCache() {
  localStorage.removeItem('detectedCountry');
  localStorage.removeItem('detectedCountryTime');
  localStorage.removeItem('app_lang');
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { detectLocation, getCurrentLocation, updateLinksWithCountry, clearLocationCache };
}
