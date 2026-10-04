import {
  api,
  escapeHtml,
  fillShopText,
  formatDate,
  formatDuration,
  formatPrice,
  formatTime,
  fullAddress,
} from "./common.js";

const STEPS = ["service", "time", "details", "done"];
const state = { shop: null, services: [], service: null, date: null, time: null, booking: null };

const $ = (id) => document.getElementById(id);

function showStep(name) {
  const current = STEPS.indexOf(name);
  for (const step of STEPS) $(`step-${step}`).hidden = step !== name;
  document.querySelectorAll("#stepper li").forEach((li) => {
    const index = STEPS.indexOf(li.dataset.step);
    li.classList.toggle("is-active", index === current);
    li.classList.toggle("is-done", index < current);
  });
  $("stepper").hidden = name === "done";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---------- step 1: service

function renderServices() {
  const list = $("service-list");
  if (!state.services.length) {
    list.innerHTML = `<div class="empty">No services are bookable online right now. Please call the shop.</div>`;
    return;
  }
  list.innerHTML = state.services
    .map(
      (service) => `
      <button type="button" class="choice" data-service="${service.id}">
        <span>
          <span class="choice-title">${escapeHtml(service.name)}</span>
          <span class="choice-desc">${escapeHtml(service.description)}</span>
        </span>
        <span class="choice-meta">
          <span class="price">${formatPrice(service.price_cents)}</span>
          <span class="duration">${formatDuration(service.duration_min)}</span>
        </span>
      </button>`,
    )
    .join("");
}

function selectService(id) {
  const service = state.services.find((s) => s.id === id);
  if (!service) return;
  state.service = service;
  state.date = null;
  state.time = null;
  $("time-service").textContent =
    `${service.name} · ${formatDuration(service.duration_min)} · ${formatPrice(service.price_cents)}`;
  $("time-notice").hidden = true;
  showStep("time");
  loadDays();
}

// ---------- step 2: day & time

const DAY_NOTES = { closed: "Closed", full: "No times" };

async function loadDays() {
  const strip = $("day-strip");
  const grid = $("time-grid");
  strip.innerHTML = "";
  grid.innerHTML = `<p class="muted">Finding open times…</p>`;
  try {
    const days = await api(`/api/days?service_id=${state.service.id}`);
    strip.innerHTML = days
      .map((day) => {
        const date = new Date(`${day.date}T00:00`);
        const note = DAY_NOTES[day.status] || date.toLocaleDateString(undefined, { month: "short" });
        return `
          <button type="button" class="day" data-date="${day.date}" aria-pressed="false"
                  ${day.status === "open" ? "" : "disabled"}
                  aria-label="${escapeHtml(formatDate(day.date))}${day.status === "open" ? "" : `, ${note}`}">
            <span class="day-name">${date.toLocaleDateString(undefined, { weekday: "short" })}</span>
            <span class="day-num">${date.getDate()}</span>
            <span class="day-note">${note}</span>
          </button>`;
      })
      .join("");

    const firstOpen = days.find((day) => day.status === "open");
    if (!firstOpen) {
      grid.innerHTML = `<div class="empty">No open times in the next ${days.length - 1} days.
        Call ${escapeHtml(state.shop.phone || "the shop")} and we'll try to fit you in.</div>`;
      return;
    }
    const keep = days.find((day) => day.date === state.date && day.status === "open");
    selectDay((keep || firstOpen).date);
  } catch (error) {
    grid.innerHTML = `<p class="form-error">${escapeHtml(error.message)}</p>`;
  }
}

function selectDay(date) {
  state.date = date;
  state.time = null;
  document.querySelectorAll("#day-strip .day").forEach((button) => {
    const selected = button.dataset.date === date;
    button.setAttribute("aria-pressed", String(selected));
    if (selected) button.scrollIntoView({ block: "nearest", inline: "nearest" });
  });
  loadTimes();
}

function timeGroup(hhmm) {
  const hour = Number(hhmm.slice(0, 2));
  if (hour < 12) return "Morning";
  if (hour < 17) return "Afternoon";
  return "Evening";
}

async function loadTimes() {
  const grid = $("time-grid");
  const date = state.date;
  grid.innerHTML = `<p class="muted">Loading times…</p>`;
  try {
    const { times } = await api(`/api/slots?service_id=${state.service.id}&date=${date}`);
    if (date !== state.date) return;
    if (!times.length) {
      grid.innerHTML = `<div class="empty">That day just filled up. Try another day.</div>`;
      return;
    }
    const groups = new Map();
    for (const time of times) {
      const label = timeGroup(time);
      if (!groups.has(label)) groups.set(label, []);
      groups.get(label).push(time);
    }
    grid.innerHTML = [...groups]
      .map(
        ([label, group]) => `
        <div class="time-group">
          <h3>${label}</h3>
          <div class="times">
            ${group.map((time) => `<button type="button" class="time" data-time="${time}">${formatTime(time)}</button>`).join("")}
          </div>
        </div>`,
      )
      .join("");
  } catch (error) {
    grid.innerHTML = `<p class="form-error">${escapeHtml(error.message)}</p>`;
  }
}

function selectTime(time) {
  state.time = time;
  $("review").innerHTML = summaryRows({
    service: state.service.name,
    date: state.date,
    time,
    duration: state.service.duration_min,
    price: state.service.price_cents,
  });
  $("policy").textContent = state.shop.cancellation_policy;
  $("form-error").hidden = true;
  showStep("details");
  $("details-form").elements.name.focus({ preventScroll: true });
}

// ---------- step 3: details

function summaryRows({ service, date, time, duration, price, code }) {
  const rows = [
    ["Service", service],
    ["When", `${formatDate(date)} at ${formatTime(time)}`],
    ["Length", formatDuration(duration)],
    ["Price", formatPrice(price)],
    ["Where", fullAddress(state.shop)],
  ];
  if (code) rows.push(["Booking code", `<span class="code">${escapeHtml(code)}</span>`]);
  return rows
    .map(([label, value]) => {
      const html = label === "Booking code" ? value : escapeHtml(value);
      return `<div class="review-row"><span>${label}</span><span>${html}</span></div>`;
    })
    .join("");
}

function validate(form) {
  const name = form.elements.name.value.trim();
  const phone = form.elements.phone.value.trim();
  const email = form.elements.email.value.trim();
  if (!name) return ["name", "Please enter your name."];
  if (phone.replace(/\D/g, "").length < 7) return ["phone", "Please enter a phone number we can reach you at."];
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return ["email", "That email address doesn't look right."];
  return null;
}

async function submitBooking(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const errorEl = $("form-error");
  const problem = validate(form);
  if (problem) {
    errorEl.textContent = problem[1];
    errorEl.hidden = false;
    form.elements[problem[0]].focus();
    return;
  }

  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  button.textContent = "Booking…";
  errorEl.hidden = true;
  try {
    state.booking = await api("/api/bookings", {
      method: "POST",
      body: {
        service_id: state.service.id,
        date: state.date,
        time: state.time,
        name: form.elements.name.value,
        phone: form.elements.phone.value,
        email: form.elements.email.value,
        notes: form.elements.notes.value,
      },
    });
    renderDone();
    showStep("done");
  } catch (error) {
    if (error.status === 409) {
      $("time-notice").textContent = error.message;
      $("time-notice").hidden = false;
      showStep("time");
      loadDays();
    } else {
      errorEl.textContent = error.message;
      errorEl.hidden = false;
    }
  } finally {
    button.disabled = false;
    button.textContent = "Confirm booking";
  }
}

// ---------- done

function icsText(value) {
  return String(value).replace(/[\\,;]/g, (char) => `\\${char}`).replace(/\n/g, "\\n");
}

function icsStamp(localDateTime) {
  return `${localDateTime.replace(/[-:]/g, "")}00`;
}

function calendarFile(booking) {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Barbershop//Booking//EN",
    "BEGIN:VEVENT",
    `UID:${booking.code}@barbershop`,
    `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").split(".")[0]}Z`,
    `DTSTART:${icsStamp(booking.start)}`,
    `DTEND:${icsStamp(booking.end)}`,
    `SUMMARY:${icsText(`${booking.service} at ${state.shop.name}`)}`,
    `LOCATION:${icsText(fullAddress(state.shop))}`,
    `DESCRIPTION:${icsText(`Booking code ${booking.code}. ${state.shop.cancellation_policy}`)}`,
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return new Blob([lines.join("\r\n")], { type: "text/calendar" });
}

function renderDone() {
  const booking = state.booking;
  const firstName = booking.name.split(/\s+/)[0];
  $("done-message").textContent =
    `Thanks, ${firstName}. See you ${formatDate(booking.start)} at ${formatTime(booking.start.slice(11))}.`;
  $("done-summary").innerHTML = summaryRows({
    service: booking.service,
    date: booking.start,
    time: booking.start.slice(11),
    duration: booking.duration_min,
    price: booking.price_cents,
    code: booking.code,
  });
  $("calendar-link").href = URL.createObjectURL(calendarFile(booking));
}

// ---------- wiring

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-service], [data-date], [data-time], [data-go]");
  if (!target || target.disabled) return;
  if (target.dataset.service) selectService(Number(target.dataset.service));
  else if (target.dataset.date) selectDay(target.dataset.date);
  else if (target.dataset.time) selectTime(target.dataset.time);
  else if (target.dataset.go === "service") showStep("service");
  else if (target.dataset.go === "time") {
    showStep("time");
    loadDays();
  }
});

$("details-form").addEventListener("submit", submitBooking);

async function init() {
  const [shop, services] = await Promise.all([api("/api/shop"), api("/api/services")]);
  state.shop = shop;
  state.services = services;
  document.title = `Book a cut · ${shop.name}`;
  fillShopText(shop);
  renderServices();

  const preselected = Number(new URLSearchParams(location.search).get("service"));
  if (services.some((s) => s.id === preselected)) selectService(preselected);
  else showStep("service");
}

init().catch((error) => {
  $("service-list").innerHTML = `<p class="form-error">${escapeHtml(error.message)}</p>`;
});
