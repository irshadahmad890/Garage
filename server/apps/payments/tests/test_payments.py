import re
from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.common.tests.base import APIBase, make_job
from apps.payments import services
from apps.payments.models import Invoice, Payment
from apps.payments.signals import invoice_paid

P = "/api/payments"


class InvoiceGenerationTests(APIBase):
    def setUp(self):
        super().setUp()
        self.admin_c = self.as_user(self.admin)
        self.job = self.job_with_work()   # parts 2 x 950 = 1900, labor 2h x 1500 = 3000, subtotal 4900

    def generate(self, job=None, **data):
        return self.admin_c.post(f"{P}/jobs/{(job or self.job).id}/generate-invoice/", data, format="json")

    def test_totals_and_lines(self):
        r = self.check(self.generate(discount="400", tax_percent="10"), 201)
        self.assertRegex(r.data["invoice_number"], r"^INV-\d{4}-\d{5}$")
        self.assertEqual((r.data["parts_total"], r.data["labor_total"], r.data["subtotal"]), ("1900.00", "3000.00", "4900.00"))
        self.assertEqual((r.data["discount"], r.data["tax_amount"], r.data["total"]), ("400.00", "450.00", "4950.00"))
        self.assertEqual((r.data["amount_paid"], r.data["balance_due"], r.data["status"]), ("0.00", "4950.00", "ISSUED"))
        self.assertEqual([l["type"] for l in r.data["lines"]], ["Part", "Labor"])
        self.assertEqual(r.data["customer_name"], "Ali Raza")

    def test_defaults_without_body(self):
        r = self.check(self.generate(), 201)
        self.assertEqual((r.data["discount"], r.data["tax_percent"], r.data["total"]), ("0.00", "0.00", "4900.00"))

    def test_rules(self):
        self.check(self.generate(job=self.job_with_work(status="IN_PROGRESS")), 409)     # job not finished
        self.check(self.generate(discount="5000"), 400)                                    # more than the subtotal
        self.check(self.generate(discount="-1"), 400)
        self.check(self.generate(tax_percent="150"), 400)
        self.check(self.generate(), 201)
        self.check(self.generate(), 409)                                                   # one invoice per job
        self.check(self.admin_c.post(f"{P}/jobs/99999/generate-invoice/", {}, format="json"), 404)

    def test_invoice_does_not_change_when_prices_change_later(self):
        r = self.check(self.generate(), 201)
        self.part.price = Decimal("5000"); self.part.save()
        self.mechanic.hourly_rate = Decimal("9000"); self.mechanic.save()
        again = self.check(self.admin_c.get(f"{P}/invoices/{r.data['id']}/"), 200)
        self.assertEqual(again.data["total"], "4900.00")

    def test_only_admin_can_generate(self):
        for user in (self.cust_user, self.mech_user):
            self.check(self.as_user(user).post(f"{P}/jobs/{self.job.id}/generate-invoice/", {}, format="json"), 403)
        self.check(self.anon.post(f"{P}/jobs/{self.job.id}/generate-invoice/", {}, format="json"), 401)
        self.assertEqual(Invoice.objects.count(), 0)


class PaymentFlowTests(APIBase):
    def setUp(self):
        super().setUp()
        self.admin_c = self.as_user(self.admin)
        self.job = self.job_with_work()
        self.invoice = services.generate_invoice(self.job.id, issued_by=self.admin)   # total 4900
        self.url = f"{P}/invoices/{self.invoice.id}/payments/"
        self.paid_signals = []
        invoice_paid.connect(self._on_paid, dispatch_uid="test-paid")
        self.addCleanup(invoice_paid.disconnect, dispatch_uid="test-paid")

    def _on_paid(self, sender, invoice, **kw):
        self.paid_signals.append(invoice.pk)

    def pay(self, amount, method="cash", **kw):
        return self.admin_c.post(self.url, {"amount": amount, "method": method, **kw}, format="json")

    def test_partial_then_full_payment(self):
        r = self.check(self.pay("2000"), 201)
        self.assertRegex(r.data["receipt_number"], r"^RCT-\d{4}-\d{5}$")
        inv = self.check(self.admin_c.get(f"{P}/invoices/{self.invoice.id}/"), 200).data
        self.assertEqual((inv["status"], inv["amount_paid"], inv["balance_due"]), ("PARTIALLY_PAID", "2000.00", "2900.00"))
        self.assertEqual(self.paid_signals, [])
        self.check(self.pay("2900", method="card", reference="TXN-1"), 201)
        inv = self.check(self.admin_c.get(f"{P}/invoices/{self.invoice.id}/"), 200).data
        self.assertEqual((inv["status"], inv["balance_due"]), ("PAID", "0.00"))
        self.assertIsNotNone(inv["paid_at"])
        self.assertEqual(len(inv["payments"]), 2)
        self.assertEqual(self.paid_signals, [self.invoice.id])      # the job app can close the job from this signal
        self.check(self.pay("1"), 409)                              # already fully paid

    def test_validation(self):
        self.check(self.pay("4900.01"), 400)                        # more than the balance
        self.check(self.pay("0"), 400)
        self.check(self.pay("-5"), 400)
        self.check(self.pay("100", method="bitcoin"), 400)
        self.check(self.admin_c.post(self.url, {"method": "cash"}, format="json"), 400)
        self.assertEqual(Payment.objects.count(), 0)                # nothing was saved by the failed tries

    def test_receipt_numbers_are_in_sequence(self):
        numbers = [self.check(self.pay("100"), 201).data["receipt_number"] for _ in range(3)]
        self.assertEqual([int(n.split("-")[-1]) for n in numbers], [1, 2, 3])

    def test_only_admin_can_record_payments(self):
        for user in (self.cust_user, self.mech_user):
            self.check(self.as_user(user).post(self.url, {"amount": "100", "method": "cash"}, format="json"), 403)
        self.check(self.anon.post(self.url, {"amount": "100", "method": "cash"}, format="json"), 401)

    def test_receipts_list_filters_and_scope(self):
        self.pay("1000"); self.pay("500", method="card", reference="R1")
        other_job = self.job_with_work(vehicle=self.vehicle2)
        other_inv = services.generate_invoice(other_job.id, issued_by=self.admin)
        services.record_payment(other_inv.id, amount=Decimal("700"), method="cash", reference="", received_by=self.admin)
        ids = lambda c, q="": {x["amount"] for x in self.check(c.get(f"{P}/receipts/{q}"), 200).data["results"]}
        self.assertEqual(ids(self.admin_c), {"1000.00", "500.00", "700.00"})
        self.assertEqual(ids(self.admin_c, "?method=card"), {"500.00"})
        self.assertEqual(ids(self.admin_c, "?min_amount=800"), {"1000.00"})
        self.assertEqual(ids(self.admin_c, f"?invoice_number={self.invoice.invoice_number}"), {"1000.00", "500.00"})
        self.assertEqual(ids(self.admin_c, "?search=R1"), {"500.00"})
        self.assertEqual(ids(self.as_user(self.cust_user)), {"1000.00", "500.00"})      # only own receipts
        self.assertEqual(ids(self.as_user(self.cust2_user)), {"700.00"})
        pay_id = Payment.objects.get(amount=700).id
        self.check(self.as_user(self.cust_user).get(f"{P}/receipts/{pay_id}/"), 404)
        self.check(self.as_user(self.mech_user).get(f"{P}/receipts/"), 403)


class InvoiceReadTests(APIBase):
    def setUp(self):
        super().setUp()
        self.admin_c = self.as_user(self.admin)
        self.inv1 = services.generate_invoice(self.job_with_work().id, issued_by=self.admin)
        self.inv2 = services.generate_invoice(self.job_with_work(vehicle=self.vehicle2).id, issued_by=self.admin)

    def test_scope(self):
        ids = lambda c: {x["id"] for x in self.check(c.get(f"{P}/invoices/"), 200).data["results"]}
        self.assertEqual(ids(self.admin_c), {self.inv1.id, self.inv2.id})
        self.assertEqual(ids(self.as_user(self.cust_user)), {self.inv1.id})
        self.assertEqual(ids(self.as_user(self.cust2_user)), {self.inv2.id})
        c = self.as_user(self.cust_user)
        self.check(c.get(f"{P}/invoices/{self.inv1.id}/"), 200)
        self.check(c.get(f"{P}/invoices/{self.inv2.id}/"), 404)
        self.check(c.post(f"{P}/invoices/{self.inv1.id}/payments/", {"amount": "1", "method": "cash"}, format="json"), 403)
        self.check(self.as_user(self.mech_user).get(f"{P}/invoices/"), 403)
        self.check(self.anon.get(f"{P}/invoices/"), 401)

    def test_filters(self):
        ids = lambda q: {x["id"] for x in self.check(self.admin_c.get(f"{P}/invoices/?{q}"), 200).data["results"]}
        self.assertEqual(ids("status=ISSUED"), {self.inv1.id, self.inv2.id})
        self.assertEqual(ids("status=PAID"), set())
        self.assertEqual(ids(f"job={self.inv1.job_id}"), {self.inv1.id})
        self.assertEqual(ids(f"job_number={self.inv2.job.job_number}"), {self.inv2.id})
        self.assertEqual(ids(f"customer={self.customer2.id}"), {self.inv2.id})
        self.assertEqual(ids("overdue=true"), set())
        Invoice.objects.filter(pk=self.inv1.pk).update(due_date=timezone.localdate() - timedelta(days=3))
        self.assertEqual(ids("overdue=true"), {self.inv1.id})
        self.assertEqual(ids("overdue=false"), {self.inv2.id})
        self.assertEqual(ids(f"issued_after={timezone.localdate()}"), {self.inv1.id, self.inv2.id})
        self.assertEqual(ids("search=LEB"), {self.inv2.id})
        self.assertEqual(len(ids("ordering=-total")), 2)

    def test_list_query_count_does_not_grow(self):
        with CaptureQueriesContext(connection) as few:
            self.check(self.admin_c.get(f"{P}/invoices/"), 200)
        for _ in range(6):
            services.generate_invoice(self.job_with_work().id, issued_by=self.admin)
        with CaptureQueriesContext(connection) as many:
            self.check(self.admin_c.get(f"{P}/invoices/"), 200)
        self.assertEqual(len(few), len(many), "N+1 queries")


class PrintTests(APIBase):
    def setUp(self):
        super().setUp()
        self.job = self.job_with_work()
        self.invoice = services.generate_invoice(self.job.id, issued_by=self.admin)
        self.payment = services.record_payment(self.invoice.id, amount=Decimal("4900"), method="cash", reference="", received_by=self.admin)

    def test_invoice_print(self):
        r = self.check(self.as_user(self.admin).get(f"{P}/invoices/{self.invoice.id}/print/"), 200)
        self.assertIn("text/html", r["Content-Type"])
        html = r.content.decode()
        for text in (self.invoice.invoice_number, self.job.job_number, "Oil filter", "Labor - Mechanic One", "Ali Raza", "LEA1234", "4900.00", "PAID"):
            self.assertIn(text, html)
        self.assertEqual(r["Cache-Control"], "private, no-store")

    def test_receipt_print(self):
        html = self.check(self.as_user(self.admin).get(f"{P}/receipts/{self.payment.id}/print/"), 200).content.decode()
        for text in ("RECEIPT", self.payment.receipt_number, self.invoice.invoice_number, "PAID IN FULL"):
            self.assertIn(text, html)

    def test_scope_for_print(self):
        mine, other = self.as_user(self.cust_user), self.as_user(self.cust2_user)
        self.check(mine.get(f"{P}/invoices/{self.invoice.id}/print/"), 200)
        self.check(mine.get(f"{P}/receipts/{self.payment.id}/print/"), 200)
        self.check(other.get(f"{P}/invoices/{self.invoice.id}/print/"), 404)
        self.check(other.get(f"{P}/receipts/{self.payment.id}/print/"), 404)
        self.check(self.as_user(self.mech_user).get(f"{P}/invoices/{self.invoice.id}/print/"), 403)
        self.check(self.anon.get(f"{P}/invoices/{self.invoice.id}/print/"), 401)
