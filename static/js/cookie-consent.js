(function () {
  var GA_ID = "G-JZNLSJJ0HV";
  var STORAGE_KEY = "cookie_consent";

  var translations = {
    en: {
      text: "This site uses cookies for analytics to improve your experience.",
      accept: "Accept",
      decline: "Decline",
    }
  };

  function getLang() {
    try {
      var stored = localStorage.getItem("aihotelsuite_lang");
      if (stored && translations[stored]) return stored;
      var match = location.search.match(/[?&]lang=(\w+)/);
      if (match && translations[match[1]]) return match[1];
    } catch (e) {}
    return "en";
  }

  function loadGA() {
    if (document.querySelector('script[src*="googletagmanager"]')) return;
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_ID;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    function gtag() { window.dataLayer.push(arguments); }
    gtag("js", new Date());
    gtag("config", GA_ID);
  }

  function getConsent() {
    try { return localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
  }

  function setConsent(value) {
    try { localStorage.setItem(STORAGE_KEY, value); } catch (e) {}
  }

  function showBanner() {
    var lang = getLang();
    var t = translations[lang] || translations.en;

    var banner = document.createElement("div");
    banner.id = "cookie-consent-banner";
    banner.style.cssText =
      "position:fixed;bottom:0;left:0;right:0;z-index:99999;" +
      "background:#1c1917;color:#fafaf9;padding:14px 20px;" +
      "display:flex;align-items:center;justify-content:center;gap:16px;" +
      "font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif;" +
      "font-size:14px;flex-wrap:wrap;box-shadow:0 -2px 8px rgba(0,0,0,0.15);";

    var text = document.createElement("span");
    text.textContent = t.text;
    text.style.cssText = "flex:1;min-width:200px;text-align:center;";

    var btnAccept = document.createElement("button");
    btnAccept.textContent = t.accept;
    btnAccept.style.cssText =
      "background:#fafaf9;color:#1c1917;border:none;padding:8px 20px;" +
      "border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;" +
      "font-family:inherit;";

    var btnDecline = document.createElement("button");
    btnDecline.textContent = t.decline;
    btnDecline.style.cssText =
      "background:transparent;color:#a8a29e;border:1px solid #44403c;" +
      "padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px;" +
      "font-family:inherit;";

    btnAccept.addEventListener("click", function () {
      setConsent("accepted");
      banner.remove();
      loadGA();
    });

    btnDecline.addEventListener("click", function () {
      setConsent("declined");
      banner.remove();
    });

    banner.appendChild(text);
    banner.appendChild(btnAccept);
    banner.appendChild(btnDecline);
    document.body.appendChild(banner);
  }

  // Main logic
  var consent = getConsent();
  if (consent === "accepted") {
    loadGA();
  } else if (consent !== "declined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", showBanner);
    } else {
      showBanner();
    }
  }
})();
