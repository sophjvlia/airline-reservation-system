# ✈ Python Airlines: Enterprise Airline Reservation System

> A robust, server-rendered airline reservation platform built with Django, HTMX, and Tailwind CSS, following modular enterprise architecture and rigorous database concurrency controls.

[![Django](https://img.shields.io/badge/Django-5.x-green?style=flat-square&logo=django)](https://www.djangoproject.com/)
[![HTMX](https://img.shields.io/badge/HTMX-1.9-blue?style=flat-square&logo=htmx)](https://htmx.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.x-38B2AC?style=flat-square&logo=tailwind-css)](https://tailwindcss.com/)
[![Architecture](https://img.shields.io/badge/Architecture-Service_Layer_Pattern-orange?style=flat-square)]()

---

## 🏗 Architecture & Design Principles

Python Airlines is engineered to mirror real-world aviation software standards:
* **Separation of Concerns:** Business logic, validation, and database operations are strictly decoupled from request handling by isolating them inside a dedicated `services.py` layer, leaving `views.py` strictly responsible for HTTP routing and response rendering.
* **Concurrency Control:** Utilizes Django's `transaction.atomic` and row-level locking (`select_for_update`) to prevent race conditions during high-demand seat bookings.
* **Progressive Enhancement:** Leverages **HTMX** for seamless, partial-page search updates and dynamic rendering without the heavy overhead or complexity of a separate Single Page Application (SPA) frontend.
* **Enterprise Styling:** Styled cleanly using **Tailwind CSS** via CDN for rapid prototyping and responsive layouts.

---

## 🗺 Project Milestones & Progress

- [x] **Milestone 1: Database Models & Architecture**
  * Designed normalized models for `Airport`, `Flight` (with gates, statuses, and dynamic seat inventory), and `Reservation` (with unique 6-character PNRs and payment/booking enums).
- [x] **Milestone 2: Core Search Engine Service**
  * Implemented complex routing algorithms supporting both direct itineraries and connecting multi-leg flights based on origin, destination, and departure dates.
- [x] **Milestone 3: Transactional Booking & PNR Generation**
  * Built atomic booking routines ensuring safe seat decrementing and secure Passenger Name Record (PNR) generation.
- [x] **Milestone 4: Developer Environment & Scripting**
  * Established clean virtual environment hygiene, dependency management, and automated test-booking scripts to validate backend services via the REPL/CLI.
- [x] **Milestone 5: Frontend UI, Search, & Checkout Flow**
  * Built responsive Tailwind layouts, HTMX-powered real-time flight search, and complete passenger checkout flows with validation handling.
  * Added airport-local search dates and flight times, responsive mobile navigation and cabin seating, and selected-seat persistence through checkout.
- [x] **Milestone 6: Accounts & Booking Management**
  * Added Django account registration, sign-in/sign-out, account-owned bookings, and cancellation before departure.
  * Kept guest PNR lookup read-only and added a repeatable reservation seeder for development.

---

## 💡 Key Learnings & Engineering Takeaways

1. **Service-Driven Architecture:** Isolating database queries and business calculations inside `services.py` makes unit testing individual features trivial and keeps views lightweight and maintainable.
2. **Race Condition Mitigation:** In airline booking systems, two users might try to grab the last remaining seat simultaneously. Using `select_for_update()` ensures database row locks prevent overbooking.
3. **HTMX in Monoliths:** HTMX provides the snappy, reactive feel of a modern JS framework while allowing developers to retain the security, simplicity, and SEO benefits of a server-rendered Django backend.

---

## 🚀 Getting Started Locally

### Prerequisites
* Python 3.12+
* Git

### Installation & Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/your-username/airline_reservation_system.git
   cd airline_reservation_system
   ```

2. **Create and Activate a Virtual Environment:**
   ```bash
   python -m venv venv
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Database Migrations:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Start the Development Server:**
   ```bash
   python manage.py runserver
   ```

6. Open your browser and navigate to `http://127.0.0.1:8000/` to explore the application.

### Sample Flights

To add sample flights for November 2026 through January 2027, run:

```bash
python manage.py seed_future_flights
```

This repeatable command adds one flight per month on the KUL–SIN, KUL–HND,
SIN–LHR, and SIN–JFK routes. It preserves existing airports, flights, and
reservations. Unlike `seed_data`, it does not clear existing records.

### Sample Reservations

After flight data is available, populate the development database with sample bookings:

```bash
python manage.py seed_reservations
```

By default, the sample bookings are guest bookings for testing PNR lookup. To attach them to an existing account's bookings page, pass its username:

```bash
python manage.py seed_reservations --username your_username
```

The command is safe to run more than once and does not clear or recreate flights.
The default sample booking references are `PYT234` and `PYT235`.

## AWS Deployment Scaffold

The application remains a server-rendered Django site. The AWS scaffold runs the whole Django HTTP application in one container-based Lambda using the AWS Lambda Web Adapter, with API Gateway HTTP API as the public HTTPS entry point. It does not split Django views into separate Lambda functions and does not require an Amplify frontend.

The SAM template provisions:

- A private VPC with Lambda and a private, single-AZ PostgreSQL RDS instance.
- Security groups allowing PostgreSQL only from the application Lambda.
- A Secrets Manager interface endpoint so the private Lambda can load its generated database credentials and Django secret without a NAT gateway.
- Generated database and Django secrets, stored outside the repository.
- A separate one-off Lambda for applying Django migrations.

WhiteNoise serves Django's collected static assets, including admin files, from the application image. The Lambda Web Adapter exposes the Django HTTP server; it does not independently publish Django static files. S3/CloudFront is not included.

### Build and deploy

Requirements: Docker, AWS SAM CLI, AWS CLI credentials for the target account/region, and permission to create the stack resources. API Gateway provides the AWS HTTPS URL, so the app does not need a separate load balancer or custom domain for the initial deployment.

```bash
sam validate --lint
sam build --use-container
sam deploy --guided
```

The stack outputs `ApplicationUrl`. After deployment, apply database migrations using the `MigrationFunctionName` output:

```bash
aws lambda invoke --function-name <MigrationFunctionName> --cli-binary-format raw-in-base64-out --payload '{}' migration-result.json
```

The migration function runs in the private VPC and uses the same database and secret settings as the web app. Inspect `migration-result.json` and the function logs before using the application. Do not run `seed_data` against production; that command deletes existing airport and flight rows.

### Cost and availability notes

This scaffold avoids a dedicated application load balancer and NAT gateway. Lambda and API Gateway costs scale with requests, but RDS, the Secrets Manager secrets, and the Secrets Manager VPC endpoint incur ongoing charges while provisioned. The database is small and single-AZ to reduce baseline cost, so it has no automatic cross-AZ failover. Check current prices, database class availability, and service quotas in the chosen Region before deploying.

The RDS deletion policy creates a snapshot when the stack is deleted; snapshots can continue to incur storage charges. Export or retain data you need, and review stack changes before deleting resources. This scaffold has not been deployed to AWS from this repository.

The flight-search backdrop is a locally stored Unsplash coastal image (`photo-1518837695005-2083093ee35b`), served from the app's static files under the [Unsplash License](https://unsplash.com/license).