// Forward Calendar model and browser-local storage. No provider or AI date generation.
(function registerCalendarService(global) {
  "use strict";
  const STORAGE_KEY = "daily-oil-trading-forward-calendar";
  const CATEGORIES = Object.freeze({ energy: "Energy", central_bank: "Rates", macro: "Macro", election: "Election", public_holiday: "Public holiday", bank_holiday: "Bank holiday", geopolitical: "Political" });
  const REGIONS = Object.freeze(["Nigeria", "USA", "Africa", "Global"]);
  const FILTERS = Object.freeze({ all: "All", energy: "Energy", rates: "Rates", macro: "Macro", political: "Political", holidays: "Holidays" });
  const FILTER_CATEGORIES = { energy: ["energy"], rates: ["central_bank"], macro: ["macro"], political: ["election", "geopolitical"], holidays: ["public_holiday", "bank_holiday"] };
  const clean = value => String(value == null ? "" : value).trim();
  function dateOnly(value) {
    const match = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(clean(value));
    if (!match) return "";
    const iso = `${match[1]}-${match[2].padStart(2,"0")}-${match[3].padStart(2,"0")}`;
    const date = new Date(`${iso}T00:00:00Z`);
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0,10) === iso ? iso : "";
  }
  function today(now = new Date()) {
    const parts = new Intl.DateTimeFormat("en-GB", { timeZone: "Africa/Lagos", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now);
    const part = name => parts.find(item => item.type === name).value;
    return `${part("year")}-${part("month")}-${part("day")}`;
  }
  function shiftMonth(month, offset) {
    if (!/^\d{4}-\d{2}$/.test(month) || !dateOnly(`${month}-01`)) return today().slice(0,7);
    const date = new Date(`${month}-01T00:00:00Z`);
    date.setUTCMonth(date.getUTCMonth() + offset);
    return date.toISOString().slice(0,7);
  }
  function normalizeEvent(input, index, group) {
    const row = input && typeof input === "object" ? input : { title: clean(input) };
    const rawDate = clean(row.event_date || row.date || row.legacy_date);
    const eventDate = dateOnly(rawDate);
    const category = Object.hasOwn(CATEGORIES,row.category) ? row.category : group === "businessEvents" ? "geopolitical" : "macro";
    return {
      ...row,
      id: clean(row.id) || `legacy-${group || "event"}-${index}`,
      event_date: eventDate,
      end_date: dateOnly(row.end_date) || null,
      title: clean(row.title), category,
      region: REGIONS.includes(row.region) ? row.region : "Global",
      country: clean(row.country) || null,
      impact_level: ["low","moderate","high"].includes(row.impact_level) ? row.impact_level : null,
      description: clean(row.description == null ? row.note : row.description),
      source_name: clean(row.source_name) || null,
      source_url: clean(row.source_url) || null,
      source_type: row.source_type === "official" ? "official" : "manual",
      verified_at: clean(row.verified_at) || null,
      active: row.active !== false && row.active !== "false",
      legacy_date: !eventDate && rawDate ? rawDate : null
    };
  }
  function normalize(source) {
    const input = source || {};
    const events = Array.isArray(input) ? input.map((row,i)=>normalizeEvent(row,i))
      : Array.isArray(input.events) ? input.events.map((row,i)=>normalizeEvent(row,i))
      : ["marketEvents","businessEvents"].flatMap(group => (Array.isArray(input[group]) ? input[group] : []).map((row,i)=>normalizeEvent(row,i,group)));
    return { version: 2, events, ...(input.storage_error ? {storage_error:input.storage_error} : {}) };
  }
  function load(storage) {
    try {
      const raw = (storage || global.localStorage).getItem(STORAGE_KEY);
      return normalize(raw ? JSON.parse(raw) : null);
    } catch (_) {
      return {version:2,events:[],storage_error:"Saved calendar could not be loaded. Check browser storage before editing."};
    }
  }
  function save(calendar, storage = global.localStorage) {
    if (calendar.storage_error) throw new Error(calendar.storage_error);
    const normalized = normalize(calendar);
    storage.setItem(STORAGE_KEY,JSON.stringify(normalized));
    return normalized;
  }
  function eventState(event, currentDate = today()) {
    if (!event.event_date) return "unscheduled";
    const end = event.end_date && event.end_date >= event.event_date ? event.end_date : event.event_date;
    if (event.event_date <= currentDate && end >= currentDate) return "today";
    if (end < currentDate) return "past";
    const days = (Date.parse(`${event.event_date}T00:00:00Z`) - Date.parse(`${currentDate}T00:00:00Z`)) / 86400000;
    return days <= 7 ? "next-seven" : "upcoming";
  }
  function matchesFilter(event, filter) {
    return filter === "all" || (FILTER_CATEGORIES[filter] || []).includes(event.category);
  }
  function eventsForMonth(calendar, month, filter = "all", currentDate = today()) {
    const start = dateOnly(`${month}-01`);
    if (!start) return [];
    const next = `${shiftMonth(month,1)}-01`;
    return normalize(calendar).events.filter(event => event.active && event.event_date && event.event_date < next && (event.end_date && event.end_date >= event.event_date ? event.end_date : event.event_date) >= start && matchesFilter(event,filter)).sort((a,b) => {
      if (month === currentDate.slice(0,7)) {
        const past = Number(eventState(a,currentDate)==="past") - Number(eventState(b,currentDate)==="past");
        if (past) return past;
      }
      return a.event_date.localeCompare(b.event_date) || a.title.localeCompare(b.title);
    });
  }
  function unscheduled(calendar,filter="all") {
    return normalize(calendar).events.filter(event=>event.active&&!event.event_date&&matchesFilter(event,filter));
  }
  function validationError(calendar) {
    for (const event of calendar.events) {
      if (!clean(event.title)) return "Enter a title for every event before saving.";
      if (!event.event_date && !event.legacy_date) return "Enter a valid date for every new event before saving.";
      if (event.end_date && event.end_date < event.event_date) return "An event end date cannot precede its start date.";
    }
    return "";
  }
  const API_BASE = "/api/calendar";

  function apiUrl(path) {
    if (typeof window !== "undefined" && window.location && window.location.origin) {
      return `${window.location.origin}${path}`;
    }
    return path;
  }

  async function fetchEvents(options = {}) {
    try {
      const fetchFn = typeof fetch !== "undefined" ? fetch : (global.fetch || null);
      if (!fetchFn) return load();
      if (typeof window === "undefined" && !global.fetchWithBase) return load();

      const params = new URLSearchParams();
      if (options.month) params.append("month", options.month);
      if (options.start_date) params.append("start_date", options.start_date);
      if (options.end_date) params.append("end_date", options.end_date);
      if (options.category) params.append("category", options.category);
      if (options.region) params.append("region", options.region);
      if (options.active !== undefined) params.append("active", String(options.active));
      if (options.include_unscheduled !== undefined) params.append("include_unscheduled", String(options.include_unscheduled));

      const query = params.toString();
      const url = apiUrl(`${API_BASE}/events${query ? `?${query}` : ""}`);
      const res = await fetchFn(url);
      if (!res.ok) {
        return load();
      }
      const data = await res.json();
      return normalize(data);
    } catch (_) {
      return load();
    }
  }

  async function createEvent(event) {
    const fetchFn = typeof fetch !== "undefined" ? fetch : (global.fetch || null);
    if (!fetchFn) throw new Error("fetch is unavailable");
    const res = await fetchFn(apiUrl(`${API_BASE}/events`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Create event failed: ${res.status}`);
    }
    return res.json();
  }

  async function updateEvent(id, event) {
    const fetchFn = typeof fetch !== "undefined" ? fetch : (global.fetch || null);
    if (!fetchFn) throw new Error("fetch is unavailable");
    const res = await fetchFn(apiUrl(`${API_BASE}/events/${id}`), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Update event failed: ${res.status}`);
    }
    return res.json();
  }

  async function deleteEvent(id) {
    const fetchFn = typeof fetch !== "undefined" ? fetch : (global.fetch || null);
    if (!fetchFn) throw new Error("fetch is unavailable");
    const res = await fetchFn(apiUrl(`${API_BASE}/events/${id}`), {
      method: "DELETE"
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Delete event failed: ${res.status}`);
    }
    return res.json();
  }

  async function migrateLegacy(events) {
    const fetchFn = typeof fetch !== "undefined" ? fetch : (global.fetch || null);
    if (!fetchFn) throw new Error("fetch is unavailable");
    const res = await fetchFn(apiUrl(`${API_BASE}/migrate-legacy`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Migration failed: ${res.status}`);
    }
    return res.json();
  }

  async function refreshEvents() {
    const fetchFn = typeof fetch !== "undefined" ? fetch : (global.fetch || null);
    if (!fetchFn) throw new Error("fetch is unavailable");
    const res = await fetchFn(apiUrl(`${API_BASE}/refresh`), {
      method: "POST"
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Refresh failed: ${res.status}`);
    }
    return res.json();
  }

  global.OilRiskCalendarService = {
    STORAGE_KEY, CATEGORIES, REGIONS, FILTERS, dateOnly, today, shiftMonth,
    normalize, load, save, eventState, eventsForMonth, unscheduled, validationError,
    fetchEvents, createEvent, updateEvent, deleteEvent, migrateLegacy, refreshEvents
  };
})(typeof window !== "undefined" ? window : globalThis);
