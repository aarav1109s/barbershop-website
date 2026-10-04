export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export async function api(path, { method = "GET", body } = {}) {
  const options = { method, credentials: "same-origin", headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error("Can't reach the server. Check your connection and try again.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(data?.error || "Something went wrong. Please try again.");
    error.status = response.status;
    throw error;
  }
  return data;
}

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => HTML_ESCAPES[char]);
}

export function formatPrice(cents) {
  const dollars = cents / 100;
  return Number.isInteger(dollars) ? `$${dollars}` : `$${dollars.toFixed(2)}`;
}

export function formatDuration(minutes) {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} hr ${rest} min` : `${hours} hr`;
}

export function formatTime(hhmm) {
  const [hour, minute] = hhmm.split(":").map(Number);
  const suffix = hour >= 12 ? "PM" : "AM";
  return `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${suffix}`;
}

/** Parses "YYYY-MM-DD" (or the date part of "YYYY-MM-DDTHH:MM") as a local date. */
export function parseDate(iso) {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function formatDate(iso, options = { weekday: "long", month: "long", day: "numeric" }) {
  return parseDate(iso).toLocaleDateString(undefined, options);
}

export function relativeDay(iso) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((parseDate(iso) - today) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  return formatDate(iso, { weekday: "long", month: "short", day: "numeric" });
}

/** Monday = 0 ... Sunday = 6, matching the server. */
export function todayWeekday() {
  return (new Date().getDay() + 6) % 7;
}

export function fullAddress(shop) {
  return [shop.address, shop.city].filter(Boolean).join(", ");
}

export function mapsUrl(shop) {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(fullAddress(shop))}`;
}

export function fillShopText(shop) {
  document.querySelectorAll("[data-shop]").forEach((el) => {
    el.textContent = shop[el.dataset.shop] || "";
  });
}
