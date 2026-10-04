import {
  api,
  escapeHtml,
  fillShopText,
  formatDate,
  formatDuration,
  formatPrice,
  formatTime,
  relativeDay,
  WEEKDAYS,
} from "./common.js";

const $ = (id) => document.getElementById(id);
let apptScope = "upcoming";

// ---------- helpers

function toast(message, kind = "ok") {
  const el = $("toast");
  el.textContent = message;
  el.classList.toggle("is-error", kind === "error");
  el.classList.add("is-visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("is-visible"), 3200);
}

async function guard(task) {
  try {
    await task();
  } catch (error) {
    if (error.status === 401) showLogin();
    else toast(error.message, "error");
  }
}

function setOptions(select, options, current) {
  const list = options.some(([value]) => value === current) ? options : [...options, [current, `${current}`]];
  select.innerHTML = list
    .map(([value, label]) => `<option value="${value}" ${value === current ? "selected" : ""}>${escapeHtml(label)}</option>`)
    .join("");
}

async function withBusy(button, task) {
  button.disabled = true;
  try {
    await guard(task);
  } finally {
    button.disabled = false;
  }
}

// ---------- login

function showLogin() {
  $("dashboard").hidden = true;
  $("logout").hidden = true;
  $("login-view").hidden = false;
  $("login-form").elements.password.focus();
}

function showDashboard() {
  $("login-view").hidden = true;
  $("dashboard").hidden = false;
  $("logout").hidden = false;
  showTab("appointments");
}

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const errorEl = $("login-error");
  const button = form.querySelector("button");
  button.disabled = true;
  try {
    await api("/api/admin/login", { method: "POST", body: { password: form.elements.password.value } });
    form.reset();
    errorEl.hidden = true;
    showDashboard();
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.hidden = false;
  } finally {
    button.disabled = false;
  }
});

$("logout").addEventListener("click", async () => {
  await api("/api/admin/logout", { method: "POST", body: {} }).catch(() => {});
  showLogin();
});

// ---------- tabs

const loaders = {
  appointments: loadAppointments,
  hours: loadHours,
  timeoff: loadTimeOff,
  services: loadServices,
  shop: loadShop,
};

function showTab(tab) {
  document.querySelectorAll(".tabs button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tab === tab);
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.hidden = panel.id !== `panel-${tab}`;
  });
  guard(loaders[tab]);
}

document.querySelector(".tabs").addEventListener("click", (event) => {
  const button = event.target.closest("[data-tab]");
  if (button) showTab(button.dataset.tab);
});

// ---------- appointments

function appointmentRow(appt) {
  const cancelled = appt.status === "cancelled";
  return `
    <div class="appt ${cancelled ? "is-cancelled" : ""}">
      <div class="appt-time">${formatTime(appt.start.slice(11))}<span>${formatDuration(appt.duration_min)}</span></div>
      <div>
        <div class="appt-name">${escapeHtml(appt.name)} ${cancelled ? `<span class="badge badge-muted">Cancelled</span>` : ""}</div>
        <div class="muted">${escapeHtml(appt.service)} · ${formatPrice(appt.price_cents)} · <span class="code">${escapeHtml(appt.code)}</span></div>
        <div class="appt-contact">
          <a href="tel:${escapeHtml(appt.phone)}">${escapeHtml(appt.phone)}</a>
          ${appt.email ? ` · <a href="mailto:${escapeHtml(appt.email)}">${escapeHtml(appt.email)}</a>` : ""}
        </div>
        ${appt.notes ? `<p class="appt-notes">“${escapeHtml(appt.notes)}”</p>` : ""}
      </div>
      ${!cancelled && apptScope === "upcoming"
        ? `<button type="button" class="btn btn-danger btn-sm" data-cancel="${appt.id}" data-name="${escapeHtml(appt.name)}">Cancel</button>`
        : ""}
    </div>`;
}

async function loadAppointments() {
  const list = $("appt-list");
  const appointments = await api(`/api/admin/appointments?scope=${apptScope}`);
  if (!appointments.length) {
    list.innerHTML = `<div class="empty">${apptScope === "upcoming"
      ? "No upcoming appointments yet. They'll show up here as soon as someone books."
      : "No past appointments yet."}</div>`;
    return;
  }
  const byDay = new Map();
  for (const appt of appointments) {
    const day = appt.start.slice(0, 10);
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day).push(appt);
  }
  list.innerHTML = [...byDay]
    .map(([day, appts]) => {
      const booked = appts.filter((a) => a.status === "booked").length;
      return `
        <section class="appt-day">
          <h3 class="day-label">${escapeHtml(relativeDay(day))}
            <span class="muted"> · ${booked} ${booked === 1 ? "cut" : "cuts"}</span></h3>
          ${appts.map(appointmentRow).join("")}
        </section>`;
    })
    .join("");
}

$("appt-scope").addEventListener("click", (event) => {
  const button = event.target.closest("[data-scope]");
  if (!button) return;
  apptScope = button.dataset.scope;
  document.querySelectorAll("#appt-scope button").forEach((b) => b.classList.toggle("is-active", b === button));
  guard(loadAppointments);
});

$("appt-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-cancel]");
  if (!button) return;
  if (!confirm(`Cancel ${button.dataset.name}'s appointment? Let them know by phone or text.`)) return;
  withBusy(button, async () => {
    await api(`/api/admin/appointments/${button.dataset.cancel}/cancel`, { method: "POST", body: {} });
    toast("Appointment cancelled. That time is open again.");
    await loadAppointments();
  });
});

// ---------- hours & booking rules

const BUFFER_OPTIONS = [0, 5, 10, 15, 20, 30].map((m) => [m, m ? `${m} minutes` : "None"]);
const INTERVAL_OPTIONS = [10, 15, 20, 30, 60].map((m) => [m, m === 60 ? "Every hour" : `Every ${m} minutes`]);
const NOTICE_OPTIONS = [
  [0, "No minimum"],
  [30, "30 minutes"],
  [60, "1 hour"],
  [120, "2 hours"],
  [240, "4 hours"],
  [720, "12 hours"],
  [1440, "1 day"],
  [2880, "2 days"],
];
const WINDOW_OPTIONS = [7, 14, 21, 28, 42, 60, 90].map((d) => [d, d % 7 === 0 ? `${d / 7} weeks` : `${d} days`]);
WINDOW_OPTIONS[0][1] = "1 week";

async function loadHours() {
  const shop = await api("/api/shop");
  $("hours-rows").innerHTML = shop.hours
    .map(
      (day) => `
      <div class="hours-edit ${day.is_open ? "" : "is-closed"}" data-weekday="${day.weekday}">
        <label class="toggle"><input type="checkbox" name="is_open" ${day.is_open ? "checked" : ""}> ${WEEKDAYS[day.weekday]}</label>
        <input type="time" name="open_time" value="${day.open_time}" step="900" aria-label="${WEEKDAYS[day.weekday]} opens">
        <span class="muted to">to</span>
        <input type="time" name="close_time" value="${day.close_time}" step="900" aria-label="${WEEKDAYS[day.weekday]} closes">
      </div>`,
    )
    .join("");
  const form = $("hours-form");
  setOptions(form.elements.buffer_minutes, BUFFER_OPTIONS, shop.buffer_minutes);
  setOptions(form.elements.slot_interval, INTERVAL_OPTIONS, shop.slot_interval);
  setOptions(form.elements.min_notice_minutes, NOTICE_OPTIONS, shop.min_notice_minutes);
  setOptions(form.elements.max_days_ahead, WINDOW_OPTIONS, shop.max_days_ahead);
}

$("hours-rows").addEventListener("change", (event) => {
  if (event.target.name === "is_open") {
    event.target.closest(".hours-edit").classList.toggle("is-closed", !event.target.checked);
  }
});

$("hours-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const days = [...form.querySelectorAll(".hours-edit")].map((row) => ({
    weekday: Number(row.dataset.weekday),
    is_open: row.querySelector("[name=is_open]").checked,
    open_time: row.querySelector("[name=open_time]").value,
    close_time: row.querySelector("[name=close_time]").value,
  }));
  const rules = Object.fromEntries(
    ["buffer_minutes", "slot_interval", "min_notice_minutes", "max_days_ahead"].map((name) => [
      name,
      Number(form.elements[name].value),
    ]),
  );
  withBusy(form.querySelector("button[type=submit]"), async () => {
    await api("/api/admin/hours", { method: "PUT", body: { days } });
    await api("/api/admin/shop", { method: "PUT", body: rules });
    toast("Hours and booking rules saved.");
  });
});

// ---------- time off

function describeBlock(block) {
  const [startDay, startTime] = block.start.split("T");
  const [endDay, endTime] = block.end.split("T");
  const short = { weekday: "short", month: "short", day: "numeric" };
  if (startTime === "00:00" && endTime === "00:00") {
    const lastDay = new Date(`${endDay}T00:00`);
    lastDay.setDate(lastDay.getDate() - 1);
    const lastIso = `${lastDay.getFullYear()}-${String(lastDay.getMonth() + 1).padStart(2, "0")}-${String(lastDay.getDate()).padStart(2, "0")}`;
    return lastIso === startDay
      ? `${formatDate(startDay, short)} · All day`
      : `${formatDate(startDay, short)} – ${formatDate(lastIso, short)} · All day`;
  }
  if (startDay === endDay) {
    return `${formatDate(startDay, short)} · ${formatTime(startTime)} – ${formatTime(endTime)}`;
  }
  return `${formatDate(startDay, short)} ${formatTime(startTime)} – ${formatDate(endDay, short)} ${formatTime(endTime)}`;
}

async function loadTimeOff() {
  const form = $("block-form");
  if (!form.elements.start_date.value) {
    const today = new Date();
    const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    form.elements.start_date.value = iso;
    form.elements.end_date.value = iso;
  }
  const blocks = await api("/api/admin/blocks");
  $("block-list").innerHTML = blocks.length
    ? blocks
        .map(
          (block) => `
          <div class="list-row">
            <div>
              <strong>${escapeHtml(describeBlock(block))}</strong>
              ${block.reason ? `<span class="muted">${escapeHtml(block.reason)}</span>` : ""}
            </div>
            <button type="button" class="btn btn-ghost btn-sm" data-remove-block="${block.id}">Remove</button>
          </div>`,
        )
        .join("")
    : `<div class="empty">No time off scheduled.</div>`;
}

$("block-form").addEventListener("change", (event) => {
  const form = event.currentTarget;
  if (event.target.name === "all_day") $("block-times").hidden = event.target.checked;
  if (event.target.name === "start_date" && form.elements.end_date.value < event.target.value) {
    form.elements.end_date.value = event.target.value;
  }
});

$("block-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const body = {
    start_date: form.elements.start_date.value,
    end_date: form.elements.end_date.value,
    all_day: form.elements.all_day.checked,
    start_time: form.elements.start_time.value,
    end_time: form.elements.end_time.value,
    reason: form.elements.reason.value,
  };
  withBusy(form.querySelector("button[type=submit]"), async () => {
    const result = await api("/api/admin/blocks", { method: "POST", body });
    form.elements.reason.value = "";
    const clashes = result.overlapping_appointments;
    if (clashes) {
      toast(`Time off added. Heads up: ${clashes} booked ${clashes === 1 ? "appointment overlaps" : "appointments overlap"} it.`, "error");
    } else {
      toast("Time off added.");
    }
    await loadTimeOff();
  });
});

$("block-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-block]");
  if (!button) return;
  withBusy(button, async () => {
    await api(`/api/admin/blocks/${button.dataset.removeBlock}`, { method: "DELETE" });
    toast("Time off removed.");
    await loadTimeOff();
  });
});

// ---------- services

function serviceForm(service) {
  const isNew = !service;
  const s = service || { name: "", description: "", duration_min: 30, price_cents: 0, active: true };
  return `
    <form class="card form service-edit" data-id="${isNew ? "" : s.id}">
      <div class="service-edit-head">
        <h3>${isNew ? "New service" : escapeHtml(s.name)}</h3>
        <label class="toggle"><input type="checkbox" name="active" ${s.active ? "checked" : ""}> Show on site</label>
      </div>
      <div class="grid-2">
        <label>Name <input name="name" required maxlength="60" value="${escapeHtml(s.name)}"></label>
        <label>Price ($) <input name="price" type="number" min="0" max="1000" step="0.01" required value="${s.price_cents / 100}"></label>
      </div>
      <label>Description <input name="description" maxlength="240" value="${escapeHtml(s.description)}"></label>
      <div class="grid-2">
        <label>Length (minutes) <input name="duration_min" type="number" min="5" max="240" step="5" required value="${s.duration_min}"></label>
      </div>
      <div class="form-actions">
        ${isNew ? `<button type="button" class="btn btn-ghost" data-discard>Discard</button>` : ""}
        <button class="btn btn-primary" type="submit">${isNew ? "Add service" : "Save"}</button>
      </div>
    </form>`;
}

async function loadServices() {
  const services = await api("/api/admin/services");
  $("service-forms").innerHTML = services.length
    ? services.map(serviceForm).join("")
    : `<div class="empty">No services yet. Add your first one.</div>`;
}

$("add-service").addEventListener("click", () => {
  const container = $("service-forms");
  if (container.querySelector('form[data-id=""]')) return;
  container.querySelector(".empty")?.remove();
  container.insertAdjacentHTML("afterbegin", serviceForm(null));
  container.querySelector('form[data-id=""] [name=name]').focus();
});

$("service-forms").addEventListener("click", (event) => {
  if (event.target.closest("[data-discard]")) event.target.closest("form").remove();
});

$("service-forms").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.target;
  const body = {
    name: form.elements.name.value,
    description: form.elements.description.value,
    duration_min: Number(form.elements.duration_min.value),
    price_cents: Math.round(Number(form.elements.price.value) * 100),
    active: form.elements.active.checked,
  };
  const id = form.dataset.id;
  withBusy(form.querySelector("button[type=submit]"), async () => {
    if (id) await api(`/api/admin/services/${id}`, { method: "PUT", body });
    else await api("/api/admin/services", { method: "POST", body });
    toast(id ? "Service saved." : "Service added.");
    await loadServices();
  });
});

// ---------- shop info

const SHOP_FIELDS = ["name", "tagline", "address", "city", "parking", "phone", "email", "instagram", "cancellation_policy"];

async function loadShop() {
  const shop = await api("/api/shop");
  const form = $("shop-form");
  for (const field of SHOP_FIELDS) form.elements[field].value = shop[field];
  form.elements.rules.value = shop.rules.join("\n");
}

$("shop-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const body = Object.fromEntries(SHOP_FIELDS.map((field) => [field, form.elements[field].value]));
  body.rules = form.elements.rules.value.split("\n").map((rule) => rule.trim()).filter(Boolean);
  withBusy(form.querySelector("button[type=submit]"), async () => {
    const shop = await api("/api/admin/shop", { method: "PUT", body });
    fillShopText(shop);
    toast("Shop info saved.");
  });
});

// ---------- start

async function init() {
  api("/api/shop").then(fillShopText).catch(() => {});
  const { authenticated } = await api("/api/admin/session");
  if (authenticated) showDashboard();
  else showLogin();
}

init().catch((error) => toast(error.message, "error"));
