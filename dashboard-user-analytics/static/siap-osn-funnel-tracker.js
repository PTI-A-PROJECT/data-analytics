/**
 * SIAP OSN — User Analytics & Conversion Funnel Tracker SDK
 * Menginstrumentasi 4 tahapan interaksi calon pengguna sesuai dokumen System Analyst:
 * 1. page_visit          (Buka Halaman Landing / Login / Registrasi)
 * 2. click_register      (Pilih Registrasi / Klik Tombol Daftar)
 * 3. start_registration  (Ketikan pertama pada input Nama / Email / Password)
 * 4. account_created     (Dicatat otomatis oleh Backend saat simpanAkunBaru berhasil)
 */
(function (global) {
  "use strict";

  const ANON_STORAGE_KEY = "siap_osn_anon_id";
  const SESSION_STORAGE_KEY = "siap_osn_session_id";
  const SENT_STAGES_KEY = "siap_osn_sent_stages";

  function generateUuidV4() {
    if (global.crypto && typeof global.crypto.randomUUID === "function") {
      return global.crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function detectDeviceType() {
    const ua = (navigator.userAgent || "").toLowerCase();
    if (/ipad|tablet/.test(ua)) return "tablet";
    if (/mobi|android|iphone/.test(ua)) return "mobile";
    return "desktop";
  }

  class SiapOsnFunnelTracker {
    constructor(options = {}) {
      this.endpoint = options.endpoint || "/api/v1/onboarding/step";
      this.utmSource = options.utmSource || this._extractUtmSource();
      this.listeners = [];
      this.anonymousId = this._getOrCreateAnonId();
      this.sessionId = this._getOrCreateSessionId();
      this.sentStages = this._getSentStages();
      if (options.autoInstrument) {
        this.autoInstrument();
      }
    }

    _getOrCreateAnonId() {
      let id = localStorage.getItem(ANON_STORAGE_KEY);
      if (!id) {
        id = generateUuidV4();
        localStorage.setItem(ANON_STORAGE_KEY, id);
      }
      return id;
    }

    _getOrCreateSessionId() {
      let id = sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (!id) {
        id = generateUuidV4();
        sessionStorage.setItem(SESSION_STORAGE_KEY, id);
      }
      return id;
    }

    _getSentStages() {
      try {
        const raw = sessionStorage.getItem(SENT_STAGES_KEY);
        return raw ? new Set(JSON.parse(raw)) : new Set();
      } catch (_) {
        return new Set();
      }
    }

    _saveSentStages() {
      sessionStorage.setItem(
        SENT_STAGES_KEY,
        JSON.stringify(Array.from(this.sentStages))
      );
    }

    _extractUtmSource() {
      try {
        const params = new URLSearchParams(global.location.search);
        return params.get("utm_source") || "organik_google";
      } catch (_) {
        return "organik_google";
      }
    }

    onEvent(callback) {
      if (typeof callback === "function") {
        this.listeners.push(callback);
      }
    }

    _notify(eventRecord) {
      this.listeners.forEach((cb) => {
        try {
          cb(eventRecord);
        } catch (_) {}
      });
    }

    resetIdentity(customUtmSource, customDevice) {
      this.anonymousId = generateUuidV4();
      this.sessionId = generateUuidV4();
      this.sentStages = new Set();
      localStorage.setItem(ANON_STORAGE_KEY, this.anonymousId);
      sessionStorage.setItem(SESSION_STORAGE_KEY, this.sessionId);
      this._saveSentStages();
      if (customUtmSource) this.utmSource = customUtmSource;
      if (customDevice) this.overrideDevice = customDevice;
    }

    async trackStage(stage, options = {}) {
      const force = Boolean(options.force);
      if (!force && this.sentStages.has(stage)) {
        return { skipped: true, stage };
      }

      const payload = {
        anonymous_id: this.anonymousId,
        session_id: this.sessionId,
        stage: stage,
        page_path: options.pagePath || global.location.pathname || "/",
        device_type: options.deviceType || this.overrideDevice || detectDeviceType(),
        utm_source: options.utmSource || this.utmSource,
        referrer: document.referrer || null,
        auto_backfill: options.autoBackfill !== false,
      };

      this.sentStages.add(stage);
      this._saveSentStages();

      const response = await fetch(this.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        keepalive: true,
      });

      const data = await response.json();
      if (Array.isArray(data.recorded_stages)) {
        data.recorded_stages.forEach((s) => this.sentStages.add(s));
        this._saveSentStages();
      }

      this._notify({
        timestamp: new Date().toISOString(),
        stage: stage,
        recorded_stages: data.recorded_stages || [stage],
        anonymous_id: this.anonymousId,
        session_id: this.sessionId,
        page_path: payload.page_path,
      });

      return data;
    }

    trackPageVisit(pagePath = "/") {
      return this.trackStage("page_visit", { pagePath });
    }

    trackClickRegister(pagePath = "/register") {
      return this.trackStage("click_register", { pagePath });
    }

    trackStartRegistration(pagePath = "/register") {
      return this.trackStage("start_registration", { pagePath });
    }

    autoInstrument() {
      // 1. Tangkap klik otomatis pada link atau tombol registrasi
      document.addEventListener("click", (e) => {
        const target = e.target.closest("a, button, [data-funnel-track]");
        if (!target) return;
        const trackAttr = target.getAttribute("data-funnel-track");
        const href = target.getAttribute("href") || "";
        if (trackAttr === "click_register" || href.includes("register") || href.includes("daftar")) {
          this.trackClickRegister(href || "/register");
        }
      });

      // 2. Tangkap input pertama pada form registrasi secara otomatis
      document.addEventListener("input", (e) => {
        const input = e.target;
        const form = input.closest("form");
        if (!form) return;
        const formId = form.id || "";
        const formAction = form.getAttribute("action") || "";
        if (
          form.hasAttribute("data-funnel-form") ||
          formId.includes("register") ||
          formId.includes("daftar") ||
          formAction.includes("register")
        ) {
          this.trackStartRegistration(global.location.pathname || "/register");
        }
      });
    }

    getIdentityPayload(extra = {}) {
      return {
        anonymous_id: this.anonymousId,
        session_id: this.sessionId,
        device_type: this.overrideDevice || detectDeviceType(),
        utm_source: this.utmSource,
        ...extra,
      };
    }
  }

  global.SiapOsnFunnelTracker = SiapOsnFunnelTracker;
})(window);
