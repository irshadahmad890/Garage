from decimal import Decimal

from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

from apps.customers.models import Customer
from apps.job.models import Job
from apps.mechanics.models import JobMechanic, Mechanic, Specialization
from apps.parts.models import JobPart, Part
from apps.user.models import User
from apps.vehicle.models import Vehicle


def make_job(vehicle, status="DRAFT"):
    """ADAPT THIS ONE FUNCTION to your real Job model (add the required fields). Nothing else in the tests creates jobs."""
    return Job.objects.create(vehicle=vehicle, status=status, complaint="Test job")


class APIBase(APITestCase):
    PASSWORD = "Pass12345!"

    @classmethod
    def setUpTestData(cls):
        mk = User.objects.create_user
        cls.admin = User.objects.create_superuser(username="admin", email="admin@x.com", password=cls.PASSWORD)
        cls.mech_user = mk(username="mech1", email="mech1@x.com", password=cls.PASSWORD, role="mechanic")
        cls.mech2_user = mk(username="mech2", email="mech2@x.com", password=cls.PASSWORD, role="mechanic")
        cls.cust_user = mk(username="cust1", email="cust1@x.com", password=cls.PASSWORD, role="customer")
        cls.cust2_user = mk(username="cust2", email="cust2@x.com", password=cls.PASSWORD, role="customer")
        cls.customer = Customer.objects.create(user=cls.cust_user, name="Ali Raza", phone="03001234567")
        cls.customer2 = Customer.objects.create(user=cls.cust2_user, name="Sara Khan", phone="03007654321")
        cls.walkin = Customer.objects.create(name="Walk In Customer", phone="03111111111")
        cls.vehicle = Vehicle.objects.create(customer=cls.customer, make="Toyota", model="Corolla", year=2018,
                                             registration_number="LEA-1234")
        cls.vehicle2 = Vehicle.objects.create(customer=cls.customer2, make="Honda", model="Civic", year=2020,
                                              registration_number="LEB-9999")
        cls.spec = Specialization.objects.create(name="Engine")
        cls.mechanic = Mechanic.objects.create(user=cls.mech_user, specialization=cls.spec, name="Mechanic One",
                                               experience_level="senior", hourly_rate=Decimal("1500"))
        cls.mechanic2 = Mechanic.objects.create(user=cls.mech2_user, specialization=cls.spec, name="Mechanic Two",
                                                experience_level="junior", hourly_rate=Decimal("900"))
        cls.part = Part.objects.create(name="Oil filter", price=Decimal("950"), stock=20)

    def setUp(self):
        cache.clear()   # throttle counters live in the cache
        self.anon = APIClient()

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def check(self, response, code):
        self.assertEqual(response.status_code, code, getattr(response, "data", response.content))
        return response

    # ---- data helpers ----
    def job_with_work(self, vehicle=None, status="COMPLETED", mechanic=None):
        """A job with 2 x Oil filter (950) and 2 hours of labor at 1500 => parts 1900 + labor 3000 = 4900."""
        job = make_job(vehicle or self.vehicle, status)
        JobPart.objects.create(job=job, part=self.part, quantity=2, unit_price=Decimal("950"))
        JobMechanic.objects.create(job=job, mechanic=mechanic or self.mechanic, working_hours=Decimal("2"),
                                   hourly_rate=Decimal("1500"))
        return job
