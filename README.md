# HostelFinder

HostelFinder is a Flask + SQLite student housing directory for Hyderabad. It
helps students choose a college, compare nearby hostels and PG rooms by
distance, price, amenities, and reviews, and explore them on an OpenStreetMap
map.

## Included

- Autocomplete search for 18 Hyderabad colleges with campus coordinates, plus
  a **Use my current location** button that ranks nearby colleges from the
  browser's GPS permission.
- Six clearly labelled **Sample data** listings per college, with Haversine
  distance and approximate walking time.
- Radius, property type, price, food, AC, sharing, and sort filters.
- Leaflet/OpenStreetMap split map with numbered hostel markers, radius circle,
  popups, highlighting, and Google Maps directions.
- Listing detail pages with local media gallery/lightbox, mini-map, amenities,
  contact actions, rating breakdown, and reviews.
- Account registration/login with Werkzeug password hashes and sessions.
- CSRF protection for forms and API mutations; SQLAlchemy parameterized queries.
- Validated local uploads: JPG/PNG/WEBP images up to 5 MB, MP4/WEBM videos up
  to 50 MB, random filenames, and generated image thumbnails.
- Student-submitted listings start as `pending` and require admin approval.
- Admin queue for listing approval/rejection and review/media removal.
- Dark mode, loading skeletons, empty states, responsive mobile layout, and
  friendly error messages.

## Setup

From this directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>.

### Finding colleges near your current location

Click **Use my current location** in the search card and allow the browser
permission prompt. HostelFinder calls `/api/colleges/nearby` with the returned
latitude/longitude, calculates distances locally, and shows the closest seeded
Hyderabad colleges. The coordinates are used for that request only and are not
stored. Location access works on `localhost`/`127.0.0.1`; when opening the app
from another device or hostname, serve it over HTTPS because browsers block
geolocation on ordinary HTTP pages. The app does not require a Google Maps API
key; Google Maps remains available through the directions links.

On its first run the app creates `instance/hostelfinder.db`, the `uploads/`
folders, and the sample dataset. The database is not overwritten on later
runs. Set `HOSTELFINDER_SECRET_KEY` before deployment; the default key is only
for local development.

### Local demo admin account

The first-run seed creates:

- Email: `admin@hostelfinder.local`
- Password: `Admin123!`

Use this only for the local demo and change the account/password before a
real deployment. The sample account is `sample@hostelfinder.local` with
password `SampleOnly123!`; it exists only to own clearly marked sample rows.

## Tests

```powershell
python -m pytest -q
```

The smoke tests exercise college autocomplete, filtered hostels, page/map
assets, registration, review creation/edit/deletion, helpful votes, image
validation, and pending listing uploads.

## Adding data

- Add or edit colleges in `COLLEGE_SEEDS` in `app.py`. For an existing database,
  insert a `College` through a small Flask shell script or remove the local
  `instance/hostelfinder.db` and start again.
- Users can add a listing from **Add a listing**. Click its map to set exact
  coordinates; it will remain pending until an admin approves it.
- For production, replace the local SQLite URL, set a strong secret, put the
  app behind HTTPS, and serve uploads from a controlled storage layer.

## Project layout

```text
HostelFinder/
├── app.py                 # models, seed data, routes, validation
├── templates/             # Flask/Jinja pages
├── static/css/            # responsive UI and theme
├── static/js/             # map, search, detail, upload, admin behavior
├── uploads/               # local media storage and generated thumbnails
├── instance/              # generated SQLite database
├── tests/                 # Flask smoke tests
├── requirements.txt
└── README.md
```

All seeded listings, illustrations, and reviews carry `is_sample=True` and
are visibly labelled in the UI. Seed reviews use explicit demonstration copy;
they are not presented as real student experiences.
