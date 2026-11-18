# FullTrailerLoad — Django REST API

Backend REST API for [fulltrailerload.com](https://fulltrailerload.com), a household moving marketplace that connects customers and brokers with moving carriers. Built with Django REST Framework and consumed by a Next.js frontend.

---

## Features

- **Company accounts** — role-based registration (shipper, broker, carrier) with email OTP verification and a compliance document upload workflow
- **Moving marketplace** — move job posting, carrier bidding, counter-offers, bid acceptance, and dual-confirm job completion
- **Capacity postings** — carriers advertise available truck space and dates; customers or brokers send interest offers
- **Real-time messaging** — direct conversations scoped to jobs or capacity postings, plus a shared community chat room, both over WebSockets
- **Reviews & ratings** — post-job company reviews with role-specific sub-ratings and a cached average rating per company
- **In-app notifications** — bid, message, and review events with per-user preferences and read/unread tracking
- **Public contact form** — stores inquiries, emails the FTL team, and sends a confirmation to the submitter
- **Shipment tracking proxy** — public endpoint that queries an external tracking API and strips private fields before returning results

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Framework | Django + Django REST Framework |
| Authentication | JWT via `djangorestframework-simplejwt` |
| Real-time | Django Channels + Redis (WebSockets) |
| Task queue | Celery + Redis |
| Database | PostgreSQL (production) / SQLite (development) |
| Admin | Django Unfold |
| CORS | `django-cors-headers` |
| Filtering | `django-filter` |

---

## Project Structure

```
DRF-FullTrailerLoad/
├── apps/
│   ├── accounts/       # registration, auth, OTP, company profiles, compliance docs
│   ├── marketplace/    # move jobs, bids, bookings, capacity postings, audit log
│   ├── messaging/      # direct messages + community chat (WebSocket)
│   ├── notifications/  # in-app notification feed and preferences
│   ├── reviews/        # post-booking company reviews and rating cache
│   └── services/       # contact form, shipment tracking proxy
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── utils/
│   ├── response.py     # CustomResponse envelope helper
│   └── exceptions.py  # global DRF exception handler
├── .env.example
├── manage.py
└── requirements.txt
```

---

## Installation & Setup

```bash
# 1. Clone the repository
git clone https://github.com/Aklabu/DRF-FullTrailerLoad.git
cd DRF-FullTrailerLoad

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# edit .env with your values

# 5. Apply migrations
python manage.py migrate

# 6. Create a superuser
python manage.py createsuperuser
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values.

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for local development |
| `ALLOWED_HOSTS` | Comma-separated hostnames e.g. `localhost,127.0.0.1` |
| `DATABASE_URL` | DB connection string e.g. `postgresql://user:pass@localhost/db` |
| `REDIS_URL` | Redis for Django Channels — default `redis://127.0.0.1:6379/0` |
| `CELERY_BROKER_URL` | Redis for Celery broker — default `redis://127.0.0.1:6379/1` |
| `CELERY_RESULT_BACKEND` | Redis for Celery results — default `redis://127.0.0.1:6379/1` |
| `CORS_ALLOWED_ORIGINS` | Frontend origins e.g. `http://localhost:3000` |
| `CSRF_TRUSTED_ORIGINS` | HTTPS domains for production e.g. `https://fulltrailerload.com` |
| `EMAIL_HOST_USER` | SMTP email address |
| `EMAIL_HOST_PASSWORD` | SMTP app password |
| `DEFAULT_FROM_EMAIL` | Sender address for outgoing emails |

---

## API Endpoints

All endpoints are prefixed with `/api/`. JWT Bearer token required unless marked **public**.

| App | Prefix | Key Endpoints |
|---|---|---|
| Accounts | `/api/accounts/` | `register/`, `login/`, `logout/`, `otp/verify/`, `me/`, `password/forgot/`, `password/reset/` |
| Marketplace | `/api/marketplace/` | `loads/`, `loads/browse/`, `loads/<id>/bids/`, `bookings/<id>/complete/`, `capacity/` |
| Messaging | `/api/` | `messages/`, `messages/send/`, `messages/<id>/`, `community/messages/` |
| Reviews | `/api/` | `marketplace/jobs/<id>/review/`, `profiles/<id>/`, `profiles/<id>/reviews/` |
| Notifications | `/api/` | `notifications/`, `notifications/unread-count/`, `notifications/read-all/` |
| Services | `/api/` | `contact/` **(public)**, `tracking/search/` **(public)** |

WebSocket endpoints:
- `ws://<host>/ws/messages/` — real-time direct messaging
- `ws://<host>/ws/community/` — real-time community chat

---

## Run Locally

Start the Django development server:

```bash
python manage.py runserver
```

Start Redis and Celery in separate terminals:

```bash
redis-server

celery -A config worker -l info
```

Admin panel available at `http://localhost:8000/admin/`.

---

## License

This project is proprietary software. All rights reserved.

---

## Author

**Joni Akter Labu**
- GitHub: [github.com/Aklabu](https://github.com/Aklabu)
- LinkedIn: [linkedin.com/in/joniakterlabu](https://www.linkedin.com/in/joniakterlabu/)
