from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.common.tests.base import APIBase, make_job
from apps.mechanics.models import JobMechanic, Mechanic, Specialization

User = get_user_model()
URL = "/api/mechanics/"
SPEC = "/api/mechanics/specializations/"
ASSIGN = "/api/mechanics/assignments/"


class MechanicTests(APIBase):
    def new_mechanic(self, **kw):
        data = {"username": "newmech", "email": "NewMech@x.com", "phone": "03451234567", "password": "Str0ng-Pass-77",
                "specialization": self.spec.id, "name": "New Mechanic", "experience_level": "junior",
                "hourly_rate": "1200.00"}
        data.update(kw)
        return data

    # ---- creating ----
    def test_admin_creates_login_and_profile_together(self):
        r = self.check(self.as_user(self.admin).post(URL, self.new_mechanic(), format="json"), 201)
        self.assertNotIn("password", r.data)
        user = User.objects.get(email="newmech@x.com")
        self.assertEqual(user.role, "mechanic")
        self.assertEqual(user.mechanic_profile.name, "New Mechanic")
        self.assertTrue(self.anon.post("/api/auth/login/", {"email": "newmech@x.com", "password": "Str0ng-Pass-77"}, format="json").status_code == 200)

    def test_failed_creation_leaves_nothing_behind(self):
        c = self.as_user(self.admin)
        users = User.objects.count()
        for bad in ({"password": "12345678"}, {"email": "MECH1@x.com"}, {"username": "mech1"},
                    {"hourly_rate": "-5"}, {"experience_level": "god"}):
            self.check(c.post(URL, self.new_mechanic(**bad), format="json"), 400)
        self.assertEqual(User.objects.count(), users)
        self.assertEqual(Mechanic.objects.count(), 2)

    def test_inactive_specialization_rejected(self):
        Specialization.objects.filter(pk=self.spec.pk).update(is_active=False)
        self.check(self.as_user(self.admin).post(URL, self.new_mechanic(), format="json"), 400)

    def test_only_admin_can_create(self):   # the mechanic could not be blocked before (permissions file unchecked)
        for user in (self.mech_user, self.cust_user):
            self.check(self.as_user(user).post(URL, self.new_mechanic(), format="json"), 403)
        self.check(self.anon.post(URL, self.new_mechanic(), format="json"), 401)

    # ---- reading / scope ----
    def test_mechanic_sees_only_own_profile(self):
        m = self.as_user(self.mech_user)
        r = self.check(m.get(URL), 200)
        self.assertEqual([x["id"] for x in r.data["results"]], [self.mechanic.id])
        self.check(m.get(f"{URL}{self.mechanic.id}/"), 200)
        self.check(m.get(f"{URL}{self.mechanic2.id}/"), 404)

    def test_customer_cannot_read(self):
        self.check(self.as_user(self.cust_user).get(URL), 403)

    def test_admin_sees_all_with_filters(self):
        c = self.as_user(self.admin)
        ids = lambda q: {x["id"] for x in self.check(c.get(f"{URL}?{q}"), 200).data["results"]}
        self.assertEqual(ids(""), {self.mechanic.id, self.mechanic2.id})
        self.assertEqual(ids("experience_level=senior"), {self.mechanic.id})
        self.assertEqual(ids("name=two"), {self.mechanic2.id})
        self.assertEqual(ids(f"specialization={self.spec.id}"), {self.mechanic.id, self.mechanic2.id})
        self.assertEqual(ids("is_active=false"), set())
        self.assertEqual(ids("search=mech1@x.com"), {self.mechanic.id})

    # ---- changing ----
    def test_mechanic_cannot_change_or_delete_own_profile(self):
        m = self.as_user(self.mech_user)
        url = f"{URL}{self.mechanic.id}/"
        self.check(m.patch(url, {"hourly_rate": "99999"}, format="json"), 403)
        self.check(m.patch(url, {"is_active": True}, format="json"), 403)
        self.check(m.put(url, {}, format="json"), 403)
        self.check(m.delete(url), 403)
        self.mechanic.refresh_from_db()
        self.assertEqual(self.mechanic.hourly_rate, Decimal("1500.00"))

    def test_admin_updates(self):
        c = self.as_user(self.admin)
        url = f"{URL}{self.mechanic.id}/"
        r = self.check(c.patch(url, {"hourly_rate": "1800.00", "experience_level": "expert"}, format="json"), 200)
        self.assertEqual(r.data["hourly_rate"], "1800.00")
        self.check(c.patch(url, {"hourly_rate": "-1"}, format="json"), 400)
        self.check(c.patch(url, {"user": self.mech2_user.id}, format="json"), 200)   # user is read-only: ignored
        self.mechanic.refresh_from_db()
        self.assertEqual(self.mechanic.user_id, self.mech_user.id)
        other = Specialization.objects.create(name="Old", is_active=False)
        self.check(c.patch(url, {"specialization": other.id}, format="json"), 400)

    def test_delete_rules(self):
        c = self.as_user(self.admin)
        job = make_job(self.vehicle)
        JobMechanic.objects.create(job=job, mechanic=self.mechanic)
        self.check(c.delete(f"{URL}{self.mechanic.id}/"), 409)                      # has assignments: protected
        self.assertTrue(User.objects.filter(pk=self.mech_user.pk).exists())
        self.check(c.delete(f"{URL}{self.mechanic2.id}/"), 204)
        self.assertFalse(User.objects.filter(pk=self.mech2_user.pk).exists())      # no orphan login is left


class SpecializationTests(APIBase):
    def test_admin_crud(self):
        c = self.as_user(self.admin)
        r = self.check(c.post(SPEC, {"name": "  Brakes   and ABS "}, format="json"), 201)
        self.assertEqual(r.data["name"], "Brakes and ABS")
        self.check(c.post(SPEC, {"name": "brakes and abs"}, format="json"), 400)     # case-insensitive duplicate
        self.check(c.post(SPEC, {"name": "  "}, format="json"), 400)
        url = f"{SPEC}{r.data['id']}/"
        self.check(c.patch(url, {"name": "Brakes"}, format="json"), 200)
        self.check(c.patch(url, {"name": "engine"}, format="json"), 400)
        self.check(c.get(f"{SPEC}?is_active=true"), 200)
        self.check(c.delete(url), 204)

    def test_used_specialization_cannot_be_deleted(self):
        self.check(self.as_user(self.admin).delete(f"{SPEC}{self.spec.id}/"), 409)

    def test_others_are_blocked(self):
        for user in (self.mech_user, self.cust_user):
            c = self.as_user(user)
            self.check(c.get(SPEC), 403)
            self.check(c.post(SPEC, {"name": "X"}, format="json"), 403)
            self.check(c.delete(f"{SPEC}{self.spec.id}/"), 403)
        self.check(self.anon.get(SPEC), 401)


class AssignmentTests(APIBase):
    def setUp(self):
        super().setUp()
        self.job = make_job(self.vehicle)
        self.admin_c = self.as_user(self.admin)

    def assign(self, mechanic, hours="0", job=None):
        return self.admin_c.post(ASSIGN, {"job": (job or self.job).id, "mechanic": mechanic.id, "working_hours": hours}, format="json")

    def test_admin_assigns_and_the_rate_is_copied(self):
        r = self.check(self.assign(self.mechanic, "1.5"), 201)
        self.assertEqual((r.data["hourly_rate"], r.data["working_hours"], r.data["mechanic_name"]), ("1500.00", "1.50", "Mechanic One"))
        Mechanic.objects.filter(pk=self.mechanic.pk).update(hourly_rate=Decimal("9000"))   # a raise later...
        self.assertEqual(JobMechanic.objects.get(pk=r.data["id"]).hourly_rate, Decimal("1500.00"))  # ...old job unchanged

    def test_client_cannot_set_the_rate(self):
        r = self.check(self.admin_c.post(ASSIGN, {"job": self.job.id, "mechanic": self.mechanic.id, "hourly_rate": "1"}, format="json"), 201)
        self.assertEqual(r.data["hourly_rate"], "1500.00")

    def test_validation(self):
        self.check(self.assign(self.mechanic), 201)
        self.check(self.assign(self.mechanic), 400)                          # same mechanic twice on one job
        self.check(self.assign(self.mechanic2, "-1"), 400)
        Mechanic.objects.filter(pk=self.mechanic2.pk).update(is_active=False)
        self.check(self.assign(self.mechanic2), 400)                         # inactive mechanic
        self.check(self.admin_c.post(ASSIGN, {"job": 99999, "mechanic": self.mechanic.id}, format="json"), 400)

    def test_admin_cannot_move_an_assignment(self):
        jm = JobMechanic.objects.create(job=self.job, mechanic=self.mechanic)
        self.check(self.admin_c.patch(f"{ASSIGN}{jm.id}/", {"mechanic": self.mechanic2.id}, format="json"), 400)
        self.check(self.admin_c.patch(f"{ASSIGN}{jm.id}/", {"job": make_job(self.vehicle2).id}, format="json"), 400)
        self.check(self.admin_c.patch(f"{ASSIGN}{jm.id}/", {"working_hours": "3"}, format="json"), 200)

    def test_mechanic_sees_only_own_assignments(self):
        mine = JobMechanic.objects.create(job=self.job, mechanic=self.mechanic)
        other = JobMechanic.objects.create(job=self.job, mechanic=self.mechanic2)
        m = self.as_user(self.mech_user)
        self.assertEqual([x["id"] for x in self.check(m.get(ASSIGN), 200).data["results"]], [mine.id])
        self.check(m.get(f"{ASSIGN}{mine.id}/"), 200)
        self.check(m.get(f"{ASSIGN}{other.id}/"), 404)

    def test_mechanic_can_only_patch_his_own_working_hours(self):
        mine = JobMechanic.objects.create(job=self.job, mechanic=self.mechanic, hourly_rate=Decimal("1500"))
        other = JobMechanic.objects.create(job=self.job, mechanic=self.mechanic2)
        m = self.as_user(self.mech_user)
        self.check(m.patch(f"{ASSIGN}{mine.id}/", {"working_hours": "4.5"}, format="json"), 200)
        self.check(m.patch(f"{ASSIGN}{mine.id}/", {"working_hours": "-2"}, format="json"), 400)
        # fields the mechanic must not touch are ignored
        self.check(m.patch(f"{ASSIGN}{mine.id}/", {"hourly_rate": "99999", "mechanic": self.mechanic2.id, "job": make_job(self.vehicle2).id}, format="json"), 200)
        mine.refresh_from_db()
        self.assertEqual((mine.working_hours, mine.hourly_rate, mine.mechanic_id, mine.job_id),
                         (Decimal("4.50"), Decimal("1500.00"), self.mechanic.id, self.job.id))
        self.check(m.patch(f"{ASSIGN}{other.id}/", {"working_hours": "9"}, format="json"), 404)   # not his
        self.check(m.post(ASSIGN, {"job": self.job.id, "mechanic": self.mechanic.id}, format="json"), 403)
        self.check(m.delete(f"{ASSIGN}{mine.id}/"), 403)
        self.check(m.put(f"{ASSIGN}{mine.id}/", {}, format="json"), 403)

    def test_customer_blocked_and_filters_for_admin(self):
        self.check(self.as_user(self.cust_user).get(ASSIGN), 403)
        self.check(self.anon.get(ASSIGN), 401)
        a = JobMechanic.objects.create(job=self.job, mechanic=self.mechanic)
        JobMechanic.objects.create(job=self.job, mechanic=self.mechanic2)
        ids = lambda q: {x["id"] for x in self.check(self.admin_c.get(f"{ASSIGN}?{q}"), 200).data["results"]}
        self.assertEqual(ids(f"mechanic={self.mechanic.id}"), {a.id})
        self.assertEqual(len(ids(f"job={self.job.id}")), 2)
        self.check(self.admin_c.delete(f"{ASSIGN}{a.id}/"), 204)
