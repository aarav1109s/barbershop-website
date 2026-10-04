# Barbershop Website — Brainstorm

Planning doc. Nothing here is locked in. Capture ideas, questions, and the product we want before we build.

**Working name:** TBD (shop name, domain, and brand voice still open)  
**Goal:** A clean, easy-to-understand site where clients book appointments and the barber runs the shop: hours, availability, cuts, pricing, location, and house rules.

---

## Why this exists

Walk-in shops lose people to “are they open?” and “do they take my cut?” Phone tagging is messy. We want one place that answers:

1. Who is this barber, and where are they?
2. What cuts exist, what do they cost, and what are the rules?
3. When can I actually book?
4. Confirm the appointment without back-and-forth.

The site should feel calm and obvious — not a dashboard dumped on a customer.

---

## Who it’s for

### Client (primary)

Someone who wants a haircut soon. They may be a first-timer or a regular. They should not need an account just to *look*. Booking might use a name + phone/email, or a light account later.

**They care about:** next available time, price, how long the cut takes, parking / address, cancellation rules, photos of the work.

### Barber (operator)

One barber for v1 (not a multi-chair salon yet). They need to set when they work, block time off, see the book, and keep services/prices/rules up to date without a developer.

**They care about:** no double-booking, buffer between cuts, days off, no-shows, looking professional.

### Later (not v1)

- Multiple barbers / chairs
- Receptionist
- Walk-in queue

---

## What “done” looks like for v1 (MVP)

A stranger can land on the site, understand the shop in under a minute, pick a service, pick a real open slot, and get a confirmation. The barber can log in, set weekly hours, block dates, and change prices/rules.

### Must have

- **Public shop page:** name, location, map/link, hours, house rules, contact
- **Services:** each cut with name, short description, duration, price, maybe a photo
- **Booking:** pick service → pick date → pick time from *real* availability → enter contact info → confirm
- **Confirmation:** on-screen + email or SMS (email is simpler to start)
- **Barber calendar:** weekly repeating availability + one-off blocks (lunch, day off, already booked)
- **Barber admin:** add/edit/hide services, edit location and rules, see upcoming appointments, cancel/reschedule
- **No double books:** a slot disappears the moment it’s taken

### Nice to have (after MVP)

- Client accounts / “my appointments”
- Reminders (24h and 2h before)
- Deposit or card-on-file for no-shows
- Waitlist when a day is full
- Instagram / gallery of cuts
- Gift cards
- Multi-barber
- Walk-in “take a number”

---

## Booking flow (client)

Keep it three short steps. No surprises at the end.

```
Home / shop info
    → Choose a haircut (price + duration visible)
        → Choose a day
            → Choose a time (only open slots)
                → Your name + phone/email
                    → Review: cut, day, time, price, location, cancel rule
                        → Book
                            → Confirmation + add-to-calendar
```

**Rules of the flow**

- Never show a time that isn’t bookable.
- Show duration and price *before* they pick a time.
- Show the shop address and cancel policy on the review step.
- If they take too long, the slot may expire — tell them clearly and offer the next time.
- Mobile first: big tap targets, one column, no tiny calendars.

**Open questions**

- Phone vs email vs both to confirm?
- Same-day booking allowed? Cutoff (e.g. 2 hours ahead)?
- How far out can they book (2 weeks vs 8 weeks)?
- Cancel/reschedule: how many hours notice?
- Do we take a deposit, or trust first and add payments later?

---

## Availability (barber)

Availability is the source of truth. Booking is just “what’s left after hours minus blocks minus existing appointments.”

### Weekly template

Example shape (numbers are placeholders):

| Day       | Working? | Hours           | Notes        |
|-----------|----------|-----------------|--------------|
| Sunday    | No       | —               |              |
| Monday    | Yes      | 10:00 – 18:00   |              |
| Tuesday   | Yes      | 10:00 – 18:00   |              |
| Wednesday | Yes      | 10:00 – 18:00   |              |
| Thursday  | Yes      | 10:00 – 19:00   |              |
| Friday    | Yes      | 9:00 – 18:00    |              |
| Saturday  | Yes      | 9:00 – 16:00    |              |

Plus:

- **Slot size** derived from the service duration (30 / 45 / 60 min, etc.)
- **Buffer** after each cut (cleanup, late client) — e.g. 5–10 min
- **Breaks** as blocked ranges (lunch 1:00–1:30)
- **Time off:** full days or ranges (“out Oct 20–22”)
- **Manual holds:** “save 4pm for a regular”

### How a slot is calculated

A time is bookable only if:

1. It falls inside working hours that day
2. It is not inside a block
3. The full duration + buffer fits before closing / next block
4. It does not overlap another appointment

Barber should see a **week view** of booked vs free, and be able to close a day in one tap.

---

## Shop information (public)

This is the “info on the haircuts / location / rules / pricing” the site exists to make obvious.

### Location

- Street address, city, parking notes, transit notes
- Google Maps link / embed
- “How to find us” one-liner (e.g. door on the alley, ring the bell)

### House rules (examples to edit)

- Arrive 5 minutes early; more than 10 minutes late may lose the slot
- Cancel at least X hours ahead
- Kids / walk-ins / card vs cash
- Health / skin / extra-long hair notes if relevant
- No-show policy

### Pricing & services (catalog)

Each service should be its own card:

| Field        | Example                    |
|--------------|----------------------------|
| Name         | Skin fade                  |
| Description  | Tight sides, blended top   |
| Duration     | 45 min                     |
| Price        | $45                        |
| Add-ons      | Beard line-up +$15         |
| Photo        | Optional                   |
| Visible?     | Yes / hidden (seasonal)    |

**Pricing principles**

- Price is always next to the name. No “call for quote” on standard cuts.
- Add-ons are optional and extend duration if they take time.
- Tax included or shown clearly — pick one and stay consistent.

Need real list from the barber: names, times, prices, photos.

---

## UI: easy and clean

The visual goal is a **quiet shop window**, not a SaaS admin theme.

### Principles

- **One job per screen.** Don’t mix “book now” with a wall of settings.
- **Read it in 5 seconds:** shop name, next available, starting price, address.
- **Type first:** strong headlines, generous space, few fonts (one display + one body).
- **Limited color:** dark barbershop neutrals + one accent (e.g. cream, charcoal, a single warm highlight). High contrast for text.
- **Photography over decoration:** a few real cuts / the chair / the storefront beat stock icons.
- **Buttons say the action:** “Book a cut”, not “Submit”.
- **Admin stays in the back.** Clients never see calendar guts.

### Public pages (information architecture)

1. **Home** — hero, next availability teaser, featured cuts, location snippet, Book CTA
2. **Services** — full menu with prices and durations
3. **Book** — the flow above
4. **Location & hours** — map, parking, rules
5. **Confirmation** — after booking (not in the main nav)

Optional: About / gallery.

### Barber pages (simple, not “enterprise”)

- Today / upcoming
- Calendar (week)
- Availability & time off
- Services & prices
- Shop info & rules
- Settings (contact, notifications)

If a client can understand the public site, the barber should understand admin without a tutorial.

### Mobile

Most booking will happen on a phone. Design phone-first. Desktop is a wider version of the same layout, not a different product.

---

## Content we still need from the shop

Copy this list and fill it in as we learn it:

- [ ] Shop name and tagline
- [ ] Address, parking, how to find the door
- [ ] Phone / Instagram / email
- [ ] Logo, brand colors, photos
- [ ] Full service menu (name, time, price, add-ons)
- [ ] Default weekly hours
- [ ] Buffer between cuts
- [ ] Same-day / advance booking rules
- [ ] Cancel / late / no-show policy
- [ ] Payment: cash, card, Venmo, deposit or not
- [ ] One barber or more later?

---

## Technical sketch (later — not building yet)

Only enough to know we’re not boxing ourselves in:

- **Public site + booking UI** (web, mobile-first)
- **Barber login** (password magic-link is fine for one user)
- **Database:** services, weekly hours, blocks, appointments, clients
- **Slot engine:** compute free times from the rules above
- **Notifications:** email first; SMS later
- **Payments:** skip for first version unless no-shows are already a problem

Stack is still open. Choose when we leave planning: something fast to ship a clean UI (e.g. a simple Next.js or similar app) is enough.

---

## Decisions log

Record choices here so we don’t re-litigate them.

| Date | Decision | Why |
|------|----------|-----|
| 2026-10-04 | Start with **one barber**, public booking, barber-controlled availability | Matches the first product we described |
| 2026-10-04 | **Plan before code** — this file is the working brief | You asked to think it through first |
| 2026-10-04 | Repo is public: `barbershop-website` | Setup preference |

---

## Open questions for next chat

1. What’s the real shop name, city, and hours?
2. Do you want clients to pay online, or just reserve?
3. Email confirmation only, or text too?
4. Any must-have look (photos, colors, sites you like)?
5. Ready to sketch pages / wireframes next, or still collecting menu + rules?

When those are clearer, next artifacts can be: a one-page wireframe of Home + Book, and a first-pass service list.
