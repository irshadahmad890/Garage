from decimal import Decimal

from apps.common.tests.base import APIBase, make_job
from apps.mechanics.models import JobMechanic
from apps.parts.models import JobPart, Part

URL = "/api/parts/"
JP = "/api/parts/job-parts/"


class PartPermissionTests(APIBase):
    """The old part views had no permission_classes at all."""

    def test_anonymous_has_no_access_at_all(self):
        self.check(self.anon.get(URL), 401)
        self.check(self.anon.post(URL, {"name": "x", "price": "1"}, format="json"), 401)
        self.check(self.anon.delete(f"{URL}{self.part.id}/"), 401)

    def test_customer_has_no_access(self):
        c = self.as_user(self.cust_user)
        self.check(c.get(URL), 403)
        self.check(c.post(URL, {"name": "Free part", "price": "0"}, format="json"), 403)
        self.check(c.patch(f"{URL}{self.part.id}/", {"price": "1"}, format="json"), 403)
        self.check(c.delete(f"{URL}{self.part.id}/"), 403)

    def test_mechanic_can_only_read(self):
        m = self.as_user(self.mech_user)
        self.check(m.get(URL), 200)
        self.check(m.get(f"{URL}{self.part.id}/"), 200)
        self.check(m.post(URL, {"name": "x", "price": "1"}, format="json"), 403)
        self.check(m.patch(f"{URL}{self.part.id}/", {"stock": 9999}, format="json"), 403)
        self.check(m.delete(f"{URL}{self.part.id}/"), 403)
        self.part.refresh_from_db()
        self.assertEqual((self.part.price, self.part.stock), (Decimal("950.00"), 20))


class AdminPartTests(APIBase):
    def setUp(self):
        super().setUp()
        self.c = self.as_user(self.admin)

    def test_crud(self):
        r = self.check(self.c.post(URL, {"name": "  Brake   pad ", "price": "6500.50", "stock": 10}, format="json"), 201)
        self.assertEqual((r.data["name"], r.data["price"], r.data["is_active"]), ("Brake pad", "6500.50", True))
        url = f"{URL}{r.data['id']}/"
        self.check(self.c.patch(url, {"stock": 3}, format="json"), 200)
        self.assertTrue(self.check(self.c.get(url), 200).data["is_low_stock"])        # 3 <= reorder level 5
        self.check(self.c.delete(url), 204)

    def test_validation(self):
        for bad in ({"price": "-1"}, {"price": "abc"}, {"stock": -1}, {"name": "A"}, {"name": ""}, {"price": "99999999999"}):
            self.check(self.c.post(URL, {"name": "Valid", "price": "10", **bad}, format="json"), 400)

    def test_part_used_in_a_job_cannot_be_deleted(self):
        JobPart.objects.create(job=make_job(self.vehicle), part=self.part, quantity=1, unit_price=950)
        self.check(self.c.delete(f"{URL}{self.part.id}/"), 409)
        self.check(self.c.patch(f"{URL}{self.part.id}/", {"is_active": False}, format="json"), 200)   # the safe way

    def test_filters_search_ordering(self):
        low = Part.objects.create(name="Wiper blade", price=Decimal("300"), stock=2, reorder_level=5, is_active=False)
        ids = lambda q: [x["id"] for x in self.check(self.c.get(f"{URL}?{q}"), 200).data["results"]]
        self.assertEqual(ids("low_stock=true"), [low.id])
        self.assertEqual(ids("low_stock=false"), [self.part.id])
        self.assertEqual(ids("min_price=500"), [self.part.id])
        self.assertEqual(ids("max_price=500"), [low.id])
        self.assertEqual(ids("name=wiper"), [low.id])
        self.assertEqual(ids("search=oil"), [self.part.id])
        self.assertEqual(ids("is_active=false"), [low.id])
        self.assertEqual(ids("ordering=-price"), [self.part.id, low.id])


class JobPartTests(APIBase):
    def setUp(self):
        super().setUp()
        self.c = self.as_user(self.admin)
        self.job = make_job(self.vehicle)

    def add(self, **kw):
        return self.c.post(JP, {"job": self.job.id, "part": self.part.id, "quantity": 2, **kw}, format="json")

    def test_price_is_copied_from_the_part_and_cannot_be_set_by_the_client(self):
        r = self.check(self.add(unit_price="1"), 201)
        self.assertEqual((r.data["unit_price"], r.data["line_total"], r.data["part_name"]), ("950.00", "1900.00", "Oil filter"))
        Part.objects.filter(pk=self.part.pk).update(price=Decimal("2000"))
        self.assertEqual(JobPart.objects.get(pk=r.data["id"]).unit_price, Decimal("950.00"))   # old job keeps its price

    def test_validation(self):
        self.check(self.add(quantity=0), 400)
        self.check(self.add(quantity=-1), 400)
        self.check(self.add(), 201)
        self.check(self.add(), 400)                                    # same part twice on one job
        inactive = Part.objects.create(name="Old part", price=10, is_active=False)
        self.check(self.add(part=inactive.id), 400)
        self.check(self.c.post(JP, {"job": 99999, "part": self.part.id, "quantity": 1}, format="json"), 400)

    def test_update_rules(self):
        jp = JobPart.objects.create(job=self.job, part=self.part, quantity=1, unit_price=950)
        url = f"{JP}{jp.id}/"
        self.check(self.c.patch(url, {"quantity": 5}, format="json"), 200)
        other = Part.objects.create(name="Other", price=10)
        self.check(self.c.patch(url, {"part": other.id}, format="json"), 400)
        self.check(self.c.patch(url, {"job": make_job(self.vehicle2).id}, format="json"), 400)
        self.check(self.c.patch(url, {"unit_price": "1"}, format="json"), 200)
        jp.refresh_from_db()
        self.assertEqual((jp.quantity, jp.unit_price), (5, Decimal("950.00")))
        self.check(self.c.delete(url), 204)

    def test_mechanic_reads_only_parts_of_own_jobs(self):
        mine = JobPart.objects.create(job=self.job, part=self.part, quantity=1, unit_price=950)
        JobMechanic.objects.create(job=self.job, mechanic=self.mechanic)
        other_job = make_job(self.vehicle2)
        theirs = JobPart.objects.create(job=other_job, part=self.part, quantity=1, unit_price=950)
        JobMechanic.objects.create(job=other_job, mechanic=self.mechanic2)
        m = self.as_user(self.mech_user)
        self.assertEqual([x["id"] for x in self.check(m.get(JP), 200).data["results"]], [mine.id])
        self.check(m.get(f"{JP}{theirs.id}/"), 404)
        self.check(m.post(JP, {"job": self.job.id, "part": self.part.id, "quantity": 1}, format="json"), 403)
        self.check(m.patch(f"{JP}{mine.id}/", {"quantity": 9}, format="json"), 403)
        self.check(m.delete(f"{JP}{mine.id}/"), 403)

    def test_customer_and_anonymous_blocked(self):
        self.check(self.as_user(self.cust_user).get(JP), 403)
        self.check(self.anon.get(JP), 401)

    def test_filter(self):
        jp = JobPart.objects.create(job=self.job, part=self.part, quantity=1, unit_price=950)
        JobPart.objects.create(job=make_job(self.vehicle2), part=self.part, quantity=1, unit_price=950)
        ids = {x["id"] for x in self.check(self.c.get(f"{JP}?job={self.job.id}"), 200).data["results"]}
        self.assertEqual(ids, {jp.id})
