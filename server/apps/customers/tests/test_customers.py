from django.contrib.auth import get_user_model

from apps.common.tests.base import APIBase
from apps.customers.models import Customer

User = get_user_model()
URL = "/api/customers/"


class CustomerAccessTests(APIBase):
    def test_anonymous_is_401(self):
        self.check(self.anon.get(URL), 401)

    def test_customer_and_mechanic_cannot_use_admin_endpoints(self):
        for user in (self.cust_user, self.mech_user):
            c = self.as_user(user)
            self.check(c.get(URL), 403)
            self.check(c.post(URL, {"name": "Hacker"}, format="json"), 403)
            self.check(c.get(f"{URL}{self.customer.id}/"), 403)
            self.check(c.patch(f"{URL}{self.customer.id}/", {"name": "x"}, format="json"), 403)
            self.check(c.delete(f"{URL}{self.customer.id}/"), 403)

    def test_customer_cannot_delete_own_profile(self):   # was possible before
        self.check(self.as_user(self.cust_user).delete(f"{URL}{self.customer.id}/"), 403)
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())


class AdminCustomerTests(APIBase):
    def setUp(self):
        super().setUp()
        self.c = self.as_user(self.admin)

    def test_list_with_vehicle_count_and_pagination(self):
        r = self.check(self.c.get(URL), 200)
        self.assertEqual(r.data["count"], 3)
        ali = next(x for x in r.data["results"] if x["name"] == "Ali Raza")
        self.assertEqual(ali["vehicle_count"], 1)

    def test_admin_can_create_many_walk_in_customers(self):   # the old code linked every new customer to the admin
        for i in range(3):
            r = self.check(self.c.post(URL, {"name": f"Walk In {i}", "phone": "03211234567"}, format="json"), 201)
            self.assertIsNone(r.data["user"])
        self.assertEqual(Customer.objects.filter(user=self.admin).count(), 0)

    def test_create_and_link_login_account(self):
        new_user = User.objects.create_user(username="c3", email="c3@x.com", password=self.PASSWORD, role="customer")
        r = self.check(self.c.post(URL, {"name": "Third Customer", "user": new_user.id}, format="json"), 201)
        self.assertEqual(r.data["user"], new_user.id)
        # the same account cannot be linked twice -> clean 400, not a 500
        self.check(self.c.post(URL, {"name": "Copy", "user": new_user.id}, format="json"), 400)
        # a mechanic login cannot be a customer
        self.check(self.c.post(URL, {"name": "Wrong", "user": self.mech_user.id}, format="json"), 400)

    def test_validation(self):
        self.check(self.c.post(URL, {"name": "A"}, format="json"), 400)
        self.check(self.c.post(URL, {"name": "Valid Name", "phone": "abc"}, format="json"), 400)
        self.check(self.c.post(URL, {"phone": "03001234567"}, format="json"), 400)
        r = self.check(self.c.post(URL, {"name": "  Spaced   Out  ", "phone": "0300 1234567"}, format="json"), 201)
        self.assertEqual(r.data["name"], "Spaced Out")

    def test_update_and_deactivate(self):
        r = self.check(self.c.patch(f"{URL}{self.walkin.id}/", {"is_active": False, "address": "Multan"}, format="json"), 200)
        self.assertFalse(r.data["is_active"])

    def test_delete_rules(self):
        self.check(self.c.delete(f"{URL}{self.customer.id}/"), 409)          # owns a vehicle -> protected
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())
        self.check(self.c.delete(f"{URL}{self.walkin.id}/"), 204)

    def test_filters_and_search(self):
        ids = lambda q: {x["id"] for x in self.check(self.c.get(f"{URL}?{q}"), 200).data["results"]}
        self.assertEqual(ids("search=ali"), {self.customer.id})
        self.assertEqual(ids("name=sara"), {self.customer2.id})
        self.assertEqual(ids("phone=0311"), {self.walkin.id})
        self.assertEqual(ids("has_account=false"), {self.walkin.id})
        self.assertEqual(ids("has_account=true"), {self.customer.id, self.customer2.id})
        self.assertEqual(ids("search=cust2@x.com"), {self.customer2.id})
        Customer.objects.filter(pk=self.walkin.pk).update(is_active=False)
        self.assertEqual(ids("is_active=false"), {self.walkin.id})

    def test_deleting_a_login_account_keeps_the_customer(self):   # on_delete is SET_NULL now
        self.cust2_user.delete()
        self.customer2.refresh_from_db()
        self.assertIsNone(self.customer2.user)


class MyProfileTests(APIBase):
    URL = "/api/customers/me/"

    def test_customer_reads_and_edits_own_profile(self):
        c = self.as_user(self.cust_user)
        self.assertEqual(self.check(c.get(self.URL), 200).data["name"], "Ali Raza")
        r = self.check(c.patch(self.URL, {"name": "Ali R. Raza", "address": "Lahore", "phone": "03001230000"}, format="json"), 200)
        self.assertEqual((r.data["name"], r.data["address"]), ("Ali R. Raza", "Lahore"))

    def test_customer_cannot_change_link_or_status(self):
        c = self.as_user(self.cust_user)
        self.check(c.patch(self.URL, {"user": self.cust2_user.id, "is_active": False}, format="json"), 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.user_id, self.cust_user.id)
        self.assertTrue(self.customer.is_active)
        self.assertNotIn("user", c.get(self.URL).data)

    def test_validation(self):
        c = self.as_user(self.cust_user)
        self.check(c.patch(self.URL, {"phone": "abc"}, format="json"), 400)
        self.check(c.patch(self.URL, {"name": "X"}, format="json"), 400)
        self.check(c.put(self.URL, {}, format="json"), 405)

    def test_only_customers_and_users_with_a_profile(self):
        self.check(self.as_user(self.admin).get(self.URL), 403)
        self.check(self.as_user(self.mech_user).get(self.URL), 403)
        self.check(self.anon.get(self.URL), 401)
        lonely = User.objects.create_user(username="lonely", email="lonely@x.com", password=self.PASSWORD, role="customer")
        self.check(self.as_user(lonely).get(self.URL), 404)
