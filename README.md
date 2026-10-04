# Barbershop website

Site for booking haircuts, showing the menu (pricing, duration, rules, location), and letting the barber set availability.

Planning notes live in [BRAINSTORM.md](./BRAINSTORM.md).

## Run it locally

Needs only Python 3.9+ (already on macOS). No installs.

```bash
python3 server.py
```

Then open:

- **Site:** http://localhost:8000
- **Booking:** http://localhost:8000/book
- **Barber admin:** http://localhost:8000/admin (password `barber`)

Change the admin password or port with environment variables:

```bash
ADMIN_PASSWORD=something-secret PORT=3000 python3 server.py
```

Data is stored in `data/barbershop.db` (SQLite). The first run fills it with a sample shop, services and hours you can edit from the admin page. Delete the file to start over.

## Tests

```bash
python3 -m unittest
```

## How it's put together

| Path | What it does |
|------|--------------|
| `server.py` | Web server: serves the pages and the JSON API |
| `barbershop/db.py` | Database tables and starter data |
| `barbershop/slots.py` | Works out which times are free (hours, buffer, time off, existing bookings) |
| `public/` | The pages: home, booking flow, barber admin |
