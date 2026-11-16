# AutoCare - corrected apps (user, customers, vehicle, mechanics, parts, payments) + common

Tested: **103 tests pass** (`python manage.py test`) and a live HTTP check. Your own `job` app is NOT included:
`apps/job` in this zip is a small **STUB** so the tests can run. Do not copy it over your real job app.

## How to apply (in this order)

1. **Install:** `pip install django-filter` (add it to requirements.txt).
2. **settings.py**, compare with `config/settings.py` in this zip. The changes are marked `NEW`:
   * `INSTALLED_APPS`: add `"django_filters"`, `"rest_framework_simplejwt.token_blacklist"`, `"apps.common"`
   * `DATABASES["default"]["ATOMIC_REQUESTS"] = True`
   * `REST_FRAMEWORK`: default permission `IsAuthenticated`, filter backends, pagination, throttle rates, exception handler
   * `SIMPLE_JWT`: `ROTATE_REFRESH_TOKENS` and `BLACKLIST_AFTER_ROTATION`
   * the `DEFAULT_TAX_PERCENT`, `INVOICE_DUE_DAYS`, `CURRENCY`, `SHOP_*` values (used by payments)
3. **urls.py:** add `path("api/payments/", include("apps.payments.urls"))` (other mounts stay as they are).
4. **Copy folders** (keep your `migrations/` folders and your `admin.py` files):
   `apps/common` (new) -> `apps/user` -> `apps/customers` -> `apps/vehicle` -> `apps/mechanics` -> `apps/parts` -> `apps/payments` (new).
5. **Delete** `apps/mechanics/permissions.py`. All permissions now come from `apps/common/permissions.py`.
6. `python manage.py makemigrations common user customers vehicle mechanics parts payments` then `python manage.py migrate`.
   (All new fields have defaults, so there are no questions to answer.)
7. **One-time data fixes** in `python manage.py shell`:
   ```python
   from apps.user.models import User
   from apps.vehicle.models import Vehicle
   User.objects.filter(is_superuser=True).update(role="admin")   # old super users have role "customer"
   User.objects.filter(phone="").update(phone=None)               # empty phone must be NULL
   for u in User.objects.all(): u.save()                          # lower-case emails
   for v in Vehicle.objects.all(): v.save()                       # one format for plates (LEA-123 -> LEA123)
   ```
   (If the last line gives an IntegrityError, two old vehicles had the same plate in different formats. Fix those two by hand.)
8. Run the tests. Adapt ONE function first: `make_job()` in `apps/common/tests/base.py` (add the fields your Job needs).

## What your job app must provide (assumptions made by these apps)

* `Job.vehicle` (a ForeignKey to Vehicle), `Job.job_number`, `Job.status`
* `payments/services.py` has `INVOICEABLE_STATUSES = ("COMPLETED",)`. Change it to your real status value(s).
* When an invoice is fully paid, payments sends the `invoice_paid` signal (`apps/payments/signals.py`).
  In the job app, listen to it and close the job: `@receiver(invoice_paid) def close_job(sender, invoice, **kw): ...`
* `JobMechanic` and `JobPart` now refer to the job as the text `"job.Job"`, so your job app can import Mechanic and Part without a circular import.

## What changed, by app

**common (new):** `permissions.py` (one place for all role rules, with `|` support), `mixins.py` (row-level scope),
`exceptions.py` (protected delete -> 409, duplicate -> 409, instead of 500), `pagination.py`, `numbering.py`, `db.py`.

**user:** createsuperuser gets role `admin` - password validation on register - register also creates the Customer profile
(in one transaction) - email saved in lower case, empty phone saved as NULL - login ignores capital letters in email -
throttling on register/login/password - NEW: `PATCH /me/`, `change-password/`, `logout/` (refresh token blacklist).

**customers:** `perform_create` bug fixed (it linked every new customer to the caller) - only admin can list/create/edit/delete -
customer deletes are blocked - NEW `customers/me/` (customer edits own name/phone/address) - new fields `phone`, `is_active` -
`user` is `SET_NULL` - phone/name validation - filters: name, phone, has_account, is_active, search.

**vehicle:** plate saved in one format and checked for duplicates in any format - customer cannot delete or change plate/VIN -
`customer` is hidden/read-only for customers (it comes from the login) - mechanic sees only vehicles of assigned jobs (read only) -
real year limit - new fields `vin`, `odometer_km`, `is_active` - filters: plate, make, year range, customer, is_active.

**mechanics:** mechanic cannot edit own profile, create mechanics, or delete - only `working_hours` of own assignment can be patched -
mechanic rate copied into `JobMechanic.hourly_rate` (old invoices never change) - deleting a mechanic also deletes the login account;
a mechanic with assignments is protected (409) - password/email/phone checks on create - filters for all three lists.

**parts:** **the part views had no permissions. Fixed:** admin writes, mechanic reads, others blocked - price cannot be negative -
`is_active`, `reorder_level` - NEW `job-parts/` endpoints: price is copied from the part, line cannot move to another job/part -
filters: name, price range, low_stock, is_active.

**payments (new):** invoice per job (totals copied at creation), partial/full payments with receipt numbers, row lock so two
payments at once are safe, printable invoice and receipt, filters (status, overdue, customer, dates, method, amount).

## Endpoints and who may use them   (A = admin, C = customer, M = mechanic)

| Endpoint | Methods | Who |
|---|---|---|
| `/api/auth/register/`, `login/`, `token/refresh/` | POST | everyone |
| `/api/auth/me/` | GET, PATCH | A, C, M |
| `/api/auth/change-password/`, `logout/` | POST | A, C, M |
| `/api/customers/`, `/api/customers/<id>/` | GET, POST / GET, PATCH, PUT, DELETE | A |
| `/api/customers/me/` | GET, PATCH | C |
| `/api/vehicles/` | GET / POST | A, C (own), M (assigned jobs) / A, C |
| `/api/vehicles/<id>/` | GET / PATCH, PUT / DELETE | A, C (own), M / A, C (own) / A |
| `/api/mechanics/`, `/api/mechanics/<id>/` | GET / POST, PATCH, PUT, DELETE | A, M (own) / A |
| `/api/mechanics/specializations/...` | all | A |
| `/api/mechanics/assignments/...` | GET, POST, PUT, DELETE / PATCH | A (all), M (own: read, and PATCH working_hours only) |
| `/api/parts/`, `/api/parts/<id>/` | GET / POST, PATCH, PUT, DELETE | A, M / A |
| `/api/parts/job-parts/...` | GET / POST, PATCH, PUT, DELETE | A, M (own jobs) / A |
| `/api/payments/invoices/`, `<id>/`, `<id>/print/` | GET | A, C (own) |
| `/api/payments/invoices/<id>/payments/` | POST | A |
| `/api/payments/jobs/<job_id>/generate-invoice/` | POST | A |
| `/api/payments/receipts/`, `<id>/`, `<id>/print/` | GET | A, C (own) |

## Test files

`apps/<app>/tests/test_*.py` for each app, and `apps/common/tests/test_permission_matrix.py`: every endpoint x every role
(204 checks). Run one app with `python manage.py test apps.parts`.
