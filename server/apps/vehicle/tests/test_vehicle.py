from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.common.tests.base import APIBase, make_job
from apps.mechanics.models import JobMechanic
from apps.vehicle.models import Vehicle, normalize_plate

User = get_user_model()
URL = "/api/vehicles/"


class PlateNormalizationTests(APIBase):
    def test_normalize(self):
        for raw in ("lea-123", "LEA 123", " Lea123 ", "LEA_123"):
            self.assertEqual(normalize_plate(raw), "LEA123")

    def test_saved_in_one_format(self):
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.registration_number, "LEA1234")


class CustomerVehicleTests(APIBase):
    def setUp(self):
        super().setUp()
        self.c = self.as_user(self.cust_user)

    def test_customer_sees_only_own_vehicles(self):
        r = self.check(self.c.get(URL), 200)
        self.assertEqual([v["id"] for v in r.data["results"]], [self.vehicle.id])
        self.check(self.c.get(f"{URL}{self.vehicle.id}/"), 200)
        self.check(self.c.get(f"{URL}{self.vehicle2.id}/"), 404)               # not 403: nothing leaks
        self.check(self.c.patch(f"{URL}{self.vehicle2.id}/", {"make": "Hack"}, format="json"), 404)
        self.check(self.c.delete(f"{URL}{self.vehicle2.id}/"), 403)            # delete is admin only

    def test_create_is_always_for_the_logged_in_customer(self):
        data = {"customer": self.customer2.id, "make": "Suzuki", "model": "Alto", "year": 2015,
                "registration_number": "lea-5555"}
        r = self.check(self.c.post(URL, data, format="json"), 201)
        self.assertEqual(r.data["customer"], self.customer.id)                # the supplied customer id is ignored
        self.assertEqual(r.data["registration_number"], "LEA5555")

    def test_customer_field_is_not_offered_to_customers(self):
        meta = self.check(self.c.options(URL), 200).data
        self.assertTrue(meta["actions"]["POST"]["customer"]["read_only"])      # customers cannot write it
        self.assertNotIn("choices", meta["actions"]["POST"]["customer"])       # and no list of all customers
        admin_meta = self.check(self.as_user(self.admin).options(URL), 200).data
        self.assertFalse(admin_meta["actions"]["POST"]["customer"]["read_only"])

    def test_customer_without_profile_cannot_create(self):
        lonely = User.objects.create_user(username="lonely", email="lonely@x.com", password=self.PASSWORD, role="customer")
        data = {"make": "Suzuki", "model": "Alto", "year": 2015, "registration_number": "ZZZ111"}
        self.check(self.as_user(lonely).post(URL, data, format="json"), 400)

    def test_duplicate_plates_in_any_format_are_rejected(self):
        base = {"make": "Suzuki", "model": "Alto", "year": 2015}
        for plate in ("LEA-1234", "lea 1234", "Lea1234"):
            self.check(self.c.post(URL, {**base, "registration_number": plate}, format="json"), 400)
        self.check(self.c.post(URL, {**base, "registration_number": "??"}, format="json"), 400)

    def test_customer_can_edit_details_but_not_the_plate_or_vin(self):
        url = f"{URL}{self.vehicle.id}/"
        self.check(self.c.patch(url, {"make": "Toyota Motors", "odometer_km": 55000}, format="json"), 200)
        self.check(self.c.patch(url, {"registration_number": "NEW-0001"}, format="json"), 400)
        self.check(self.c.patch(url, {"registration_number": "lea 1234"}, format="json"), 200)   # same plate is fine
        self.check(self.c.patch(url, {"vin": "JTDBR32E720012345"}, format="json"), 400)
        self.check(self.c.patch(url, {"is_active": False}, format="json"), 200)               # can retire the vehicle

    def test_customer_cannot_delete(self):
        self.check(self.c.delete(f"{URL}{self.vehicle.id}/"), 403)
        self.assertTrue(Vehicle.objects.filter(pk=self.vehicle.pk).exists())

    def test_year_rules(self):
        base = {"make": "Suzuki", "model": "Alto", "registration_number": "YEAR1"}
        self.check(self.c.post(URL, {**base, "year": 1850}, format="json"), 400)
        self.check(self.c.post(URL, {**base, "year": date.today().year + 5}, format="json"), 400)
        self.check(self.c.post(URL, {**base, "year": date.today().year + 1}, format="json"), 201)


class AdminVehicleTests(APIBase):
    def setUp(self):
        super().setUp()
        self.c = self.as_user(self.admin)

    def test_admin_sees_all_and_must_choose_a_customer(self):
        self.assertEqual(self.check(self.c.get(URL), 200).data["count"], 2)
        data = {"make": "Kia", "model": "Sportage", "year": 2021, "registration_number": "ADM-1"}
        self.check(self.c.post(URL, data, format="json"), 400)
        r = self.check(self.c.post(URL, {**data, "customer": self.walkin.id}, format="json"), 201)
        self.assertEqual(r.data["customer_name"], "Walk In Customer")

    def test_admin_cannot_use_an_inactive_customer(self):
        self.walkin.is_active = False
        self.walkin.save()
        data = {"make": "Kia", "model": "Sportage", "year": 2021, "registration_number": "ADM-2", "customer": self.walkin.id}
        self.check(self.c.post(URL, data, format="json"), 400)

    def test_vin_rules(self):
        base = {"make": "Kia", "model": "Rio", "year": 2020, "customer": self.walkin.id}
        for i in range(2):   # blank VIN is stored as NULL, so two blanks never clash
            self.check(self.c.post(URL, {**base, "registration_number": f"VIN-{i}", "vin": ""}, format="json"), 201)
        r = self.check(self.c.post(URL, {**base, "registration_number": "VIN-9", "vin": "jtdbr32e720012345"}, format="json"), 201)
        self.assertEqual(r.data["vin"], "JTDBR32E720012345")
        self.check(self.c.post(URL, {**base, "registration_number": "VIN-10", "vin": "JTDBR32E720012345"}, format="json"), 400)

    def test_admin_can_change_plate_and_owner(self):
        r = self.check(self.c.patch(f"{URL}{self.vehicle.id}/", {"registration_number": "LEA-7777", "customer": self.walkin.id}, format="json"), 200)
        self.assertEqual((r.data["registration_number"], r.data["customer"]), ("LEA7777", self.walkin.id))

    def test_delete_rules(self):
        make_job(self.vehicle)
        self.check(self.c.delete(f"{URL}{self.vehicle.id}/"), 409)            # has a job -> protected, not a 500
        self.check(self.c.delete(f"{URL}{self.vehicle2.id}/"), 204)

    def test_filters_and_search(self):
        ids = lambda q: {x["id"] for x in self.check(self.c.get(f"{URL}?{q}"), 200).data["results"]}
        self.assertEqual(ids("plate=lea-12"), {self.vehicle.id})              # filter ignores - and spaces
        self.assertEqual(ids("plate=LEB 99"), {self.vehicle2.id})
        self.assertEqual(ids("make=honda"), {self.vehicle2.id})
        self.assertEqual(ids("year_min=2019"), {self.vehicle2.id})
        self.assertEqual(ids("year_max=2019"), {self.vehicle.id})
        self.assertEqual(ids(f"customer={self.customer.id}"), {self.vehicle.id})
        self.assertEqual(ids("search=sara"), {self.vehicle2.id})
        self.assertEqual(ids("is_active=false"), set())

    def test_list_query_count_does_not_grow(self):
        for i in range(3):
            Vehicle.objects.create(customer=self.walkin, make="A", model="B", year=2010, registration_number=f"QA{i}")
        with CaptureQueriesContext(connection) as few:
            self.check(self.c.get(URL), 200)
        for i in range(10):
            Vehicle.objects.create(customer=self.walkin, make="A", model="B", year=2010, registration_number=f"QB{i}")
        with CaptureQueriesContext(connection) as many:
            self.check(self.c.get(URL), 200)
        self.assertEqual(len(few), len(many), "N+1 queries")


class MechanicVehicleTests(APIBase):
    def setUp(self):
        super().setUp()
        self.m = self.as_user(self.mech_user)

    def test_mechanic_sees_only_vehicles_of_assigned_jobs_read_only(self):
        self.assertEqual(self.check(self.m.get(URL), 200).data["count"], 0)
        job = make_job(self.vehicle)
        JobMechanic.objects.create(job=job, mechanic=self.mechanic)
        make_job(self.vehicle2)   # a job the mechanic is NOT assigned to
        r = self.check(self.m.get(URL), 200)
        self.assertEqual([v["id"] for v in r.data["results"]], [self.vehicle.id])
        self.check(self.m.get(f"{URL}{self.vehicle.id}/"), 200)
        self.check(self.m.get(f"{URL}{self.vehicle2.id}/"), 404)
        self.check(self.m.post(URL, {}, format="json"), 403)
        self.check(self.m.patch(f"{URL}{self.vehicle.id}/", {"make": "x"}, format="json"), 403)
        self.check(self.m.delete(f"{URL}{self.vehicle.id}/"), 403)
