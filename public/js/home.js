import {
  api,
  escapeHtml,
  fillShopText,
  formatDuration,
  formatPrice,
  formatTime,
  fullAddress,
  mapsUrl,
  relativeDay,
  todayWeekday,
  WEEKDAYS,
} from "./common.js";

function renderServices(services) {
  const grid = document.getElementById("service-grid");
  if (!services.length) {
    grid.innerHTML = `<p class="muted">The service menu is coming soon.</p>`;
    return;
  }
  grid.innerHTML = services
    .map(
      (service) => `
      <article class="service-card">
        <div class="service-top">
          <h3>${escapeHtml(service.name)}</h3>
          <span class="price">${formatPrice(service.price_cents)}</span>
        </div>
        <p class="muted">${escapeHtml(service.description)}</p>
        <div class="service-bottom">
          <span class="duration">${formatDuration(service.duration_min)}</span>
          <a class="link-arrow" href="/book?service=${service.id}">Book →</a>
        </div>
      </article>`,
    )
    .join("");
}

function renderVisit(shop) {
  document.getElementById("address").textContent = fullAddress(shop);
  document.getElementById("parking").textContent = shop.parking;
  document.getElementById("map-link").href = mapsUrl(shop);

  const contact = [];
  if (shop.phone) contact.push(`<li><a href="tel:${escapeHtml(shop.phone)}">${escapeHtml(shop.phone)}</a></li>`);
  if (shop.email) contact.push(`<li><a href="mailto:${escapeHtml(shop.email)}">${escapeHtml(shop.email)}</a></li>`);
  if (shop.instagram) {
    const handle = shop.instagram.replace(/^@/, "");
    contact.push(
      `<li><a href="https://instagram.com/${encodeURIComponent(handle)}" target="_blank" rel="noopener">@${escapeHtml(handle)}</a></li>`,
    );
  }
  document.getElementById("contact").innerHTML = contact.join("");

  const today = todayWeekday();
  document.getElementById("hours").innerHTML = shop.hours
    .map(
      (day) => `
      <div class="hours-row ${day.weekday === today ? "is-today" : ""}">
        <dt>${WEEKDAYS[day.weekday]}</dt>
        <dd>${day.is_open ? `${formatTime(day.open_time)} – ${formatTime(day.close_time)}` : "Closed"}</dd>
      </div>`,
    )
    .join("");
}

function renderRules(shop) {
  document.getElementById("cancellation").textContent = shop.cancellation_policy;
  document.getElementById("rules-list").innerHTML = shop.rules
    .map((rule) => `<li>${escapeHtml(rule)}</li>`)
    .join("");
  document.getElementById("rules").hidden = !shop.rules.length && !shop.cancellation_policy;
}

async function renderNextOpening() {
  const { start } = await api("/api/next-available");
  if (!start) return;
  const el = document.getElementById("next-open");
  el.innerHTML = `<span class="dot" aria-hidden="true"></span>
    Next opening <strong>${escapeHtml(relativeDay(start))} at ${formatTime(start.slice(11))}</strong>`;
  el.hidden = false;
}

async function init() {
  document.getElementById("year").textContent = new Date().getFullYear();
  const [shop, services] = await Promise.all([api("/api/shop"), api("/api/services")]);
  document.title = shop.name;
  fillShopText(shop);
  renderServices(services);
  renderVisit(shop);
  renderRules(shop);
  renderNextOpening().catch(() => {});
}

init().catch((error) => {
  document.getElementById("service-grid").innerHTML = `<p class="form-error">${escapeHtml(error.message)}</p>`;
});
