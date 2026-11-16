"""Every endpoint x every role. This proves the common-app permissions are applied everywhere.

A role that is NOT allowed must get 401 (anonymous) or 403 (logged in).
A role that IS allowed must get anything else (200, 201, 400, 404 ... but never 401/403):
a 400 or 404 only means our empty test body or the row-level scope answered, after the permission passed."""
from decimal import Decimal

from django.db import transaction

from apps.common.tests.base import APIBase
from apps.payments import services

A, C, M = "admin", "customer", "mechanic"
ALL = (A, C, M)

# (method, path, roles that may call it)
MATRIX = [
    # --- user ---
    ("POST", "/api/auth/register/", ("anon",) + ALL),
    ("GET", "/api/auth/me/", ALL),
    ("PATCH", "/api/auth/me/", ALL),
    ("POST", "/api/auth/change-password/", ALL),
    ("POST", "/api/auth/logout/", ALL),
    # --- customers ---
    ("GET", "/api/customers/", (A,)),
    ("POST", "/api/customers/", (A,)),
    ("GET", "/api/customers/{customer}/", (A,)),
    ("PATCH", "/api/customers/{customer}/", (A,)),
    ("DELETE", "/api/customers/{customer}/", (A,)),
    ("GET", "/api/customers/me/", (C,)),
    ("PATCH", "/api/customers/me/", (C,)),
    # --- vehicles ---
    ("GET", "/api/vehicles/", (A, C, M)),
    ("POST", "/api/vehicles/", (A, C)),
    ("GET", "/api/vehicles/{vehicle}/", (A, C, M)),
    ("PATCH", "/api/vehicles/{vehicle}/", (A, C)),
    ("DELETE", "/api/vehicles/{vehicle}/", (A,)),
    # --- mechanics ---
    ("GET", "/api/mechanics/", (A, M)),
    ("POST", "/api/mechanics/", (A,)),
    ("GET", "/api/mechanics/{mechanic}/", (A, M)),
    ("PATCH", "/api/mechanics/{mechanic}/", (A,)),
    ("DELETE", "/api/mechanics/{mechanic}/", (A,)),
    ("GET", "/api/mechanics/specializations/", (A,)),
    ("POST", "/api/mechanics/specializations/", (A,)),
    ("GET", "/api/mechanics/specializations/{spec}/", (A,)),
    ("PATCH", "/api/mechanics/specializations/{spec}/", (A,)),
    ("DELETE", "/api/mechanics/specializations/{spec}/", (A,)),
    ("GET", "/api/mechanics/assignments/", (A, M)),
    ("POST", "/api/mechanics/assignments/", (A,)),
    ("GET", "/api/mechanics/assignments/{assignment}/", (A, M)),
    ("PATCH", "/api/mechanics/assignments/{assignment}/", (A, M)),
    ("PUT", "/api/mechanics/assignments/{assignment}/", (A,)),
    ("DELETE", "/api/mechanics/assignments/{assignment}/", (A,)),
    # --- parts ---
    ("GET", "/api/parts/", (A, M)),
    ("POST", "/api/parts/", (A,)),
    ("GET", "/api/parts/{part}/", (A, M)),
    ("PATCH", "/api/parts/{part}/", (A,)),
    ("DELETE", "/api/parts/{part}/", (A,)),
    ("GET", "/api/parts/job-parts/", (A, M)),
    ("POST", "/api/parts/job-parts/", (A,)),
    ("GET", "/api/parts/job-parts/{job_part}/", (A, M)),
    ("PATCH", "/api/parts/job-parts/{job_part}/", (A,)),
    ("DELETE", "/api/parts/job-parts/{job_part}/", (A,)),
    # --- payments ---
    ("GET", "/api/payments/invoices/", (A, C)),
    ("GET", "/api/payments/invoices/{invoice}/", (A, C)),
    ("GET", "/api/payments/invoices/{invoice}/print/", (A, C)),
    ("POST", "/api/payments/invoices/{invoice}/payments/", (A,)),
    ("POST", "/api/payments/jobs/{job}/generate-invoice/", (A,)),
    ("GET", "/api/payments/receipts/", (A, C)),
    ("GET", "/api/payments/receipts/{payment}/", (A, C)),
    ("GET", "/api/payments/receipts/{payment}/print/", (A, C)),
]


class PermissionMatrixTests(APIBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from apps.mechanics.models import JobMechanic
        from apps.parts.models import JobPart
        cls.job = cls.job_with_work_cls()
        cls.assignment = JobMechanic.objects.filter(job=cls.job).first()
        cls.job_part = JobPart.objects.filter(job=cls.job).first()
        cls.invoice = services.generate_invoice(cls.job.id, issued_by=cls.admin)
        cls.payment = services.record_payment(cls.invoice.id, amount=Decimal("100"), method="cash", reference="", received_by=cls.admin)

    @classmethod
    def job_with_work_cls(cls):
        from apps.common.tests.base import make_job
        from apps.mechanics.models import JobMechanic
        from apps.parts.models import JobPart
        job = make_job(cls.vehicle, "COMPLETED")
        JobPart.objects.create(job=job, part=cls.part, quantity=2, unit_price=Decimal("950"))
        JobMechanic.objects.create(job=job, mechanic=cls.mechanic, working_hours=Decimal("2"), hourly_rate=Decimal("1500"))
        return job

    def client_for(self, role):
        users = {A: self.admin, C: self.cust_user, M: self.mech_user}
        return self.anon if role == "anon" else self.as_user(users[role])

    def test_every_endpoint_for_every_role(self):
        ids = {"customer": self.customer.id, "vehicle": self.vehicle.id, "mechanic": self.mechanic.id, "spec": self.spec.id,
               "assignment": self.assignment.id, "part": self.part.id, "job_part": self.job_part.id,
               "invoice": self.invoice.id, "payment": self.payment.id, "job": self.job.id}
        checked = 0
        for method, path, allowed in MATRIX:
            url = path.format(**ids)
            for role in ("anon", A, C, M):
                with self.subTest(f"{method} {path} as {role}"):
                    with transaction.atomic():
                        response = getattr(self.client_for(role), method.lower())(url, {}, format="json")
                        transaction.set_rollback(True)   # every call starts from the same data
                    if role in allowed:
                        self.assertNotIn(response.status_code, (401, 403), f"{role} should be allowed")
                    else:
                        self.assertEqual(response.status_code, 401 if role == "anon" else 403, f"{role} should be blocked")
                    checked += 1
        self.assertGreater(checked, 150)
