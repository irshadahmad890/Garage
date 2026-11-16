from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from apps.common.tests.base import APIBase
from apps.customers.models import Customer

User = get_user_model()
BASE = "/api/auth"


class RegisterTests(APIBase):
    payload = {"username": "newcust", "email": "New.Cust@Mail.com", "password": "Str0ng-Pass-77",
               "phone": "03001112233", "name": "New Customer", "address": "Lahore"}

    def test_register_creates_user_and_customer_profile(self):
        r = self.check(self.anon.post(f"{BASE}/register/", self.payload, format="json"), 201)
        self.assertNotIn("password", r.data)
        user = User.objects.get(pk=r.data["id"])
        self.assertEqual((user.role, user.email), ("customer", "new.cust@mail.com"))   # lower-cased
        profile = user.customer_profile
        self.assertEqual((profile.name, profile.phone, profile.address), ("New Customer", "03001112233", "Lahore"))

    def test_role_and_admin_flags_cannot_come_from_the_client(self):
        data = {**self.payload, "role": "admin", "is_superuser": True, "is_staff": True}
        r = self.check(self.anon.post(f"{BASE}/register/", data, format="json"), 201)
        user = User.objects.get(pk=r.data["id"])
        self.assertEqual(user.role, "customer")
        self.assertFalse(user.is_superuser or user.is_staff)

    def test_validation(self):
        post = lambda **kw: self.anon.post(f"{BASE}/register/", {**self.payload, **kw}, format="json")
        self.check(post(password="12345678"), 400)                         # weak password (was accepted before)
        self.check(post(password="short"), 400)
        self.check(post(name="A"), 400)
        self.check(post(email="not-an-email"), 400)
        self.check(post(email="CUST1@x.com"), 400)                         # same email, other capital letters
        self.check(post(username="cust1"), 400)
        self.assertEqual(Customer.objects.filter(name="New Customer").count(), 0)  # nothing half-created

    def test_two_users_without_phone_are_allowed(self):
        for i in range(2):
            data = {**self.payload, "username": f"nophone{i}", "email": f"nophone{i}@x.com", "phone": ""}
            self.check(self.anon.post(f"{BASE}/register/", data, format="json"), 201)
        self.assertEqual(User.objects.filter(phone__isnull=True, email__startswith="nophone").count(), 2)

    def test_duplicate_phone_rejected(self):
        self.check(self.anon.post(f"{BASE}/register/", self.payload, format="json"), 201)
        self.check(self.anon.post(f"{BASE}/register/", {**self.payload, "username": "x2", "email": "x2@x.com"}, format="json"), 400)

    def test_register_is_throttled(self):
        codes = [self.anon.post(f"{BASE}/register/", {}, format="json").status_code for _ in range(12)]
        self.assertIn(429, codes)


class LoginTests(APIBase):
    def login(self, email, password=None):
        return self.anon.post(f"{BASE}/login/", {"email": email, "password": password or self.PASSWORD}, format="json")

    def test_login_with_email_returns_tokens_and_role_claim(self):
        r = self.check(self.login("cust1@x.com"), 200)
        self.assertEqual(AccessToken(r.data["access"])["role"], "customer")
        self.assertEqual(AccessToken(r.data["access"])["email"], "cust1@x.com")

    def test_email_capital_letters_do_not_matter(self):
        self.check(self.login("CUST1@X.com"), 200)

    def test_wrong_password_and_unknown_user(self):
        self.check(self.login("cust1@x.com", "wrong-password"), 401)
        self.check(self.login("nobody@x.com"), 401)

    def test_inactive_user_cannot_login(self):
        User.objects.filter(pk=self.cust_user.pk).update(is_active=False)
        self.check(self.login("cust1@x.com"), 401)

    def test_login_is_throttled(self):
        codes = [self.login("cust1@x.com", "bad-password").status_code for _ in range(25)]
        self.assertIn(429, codes)

    def test_refresh_rotates_the_token_and_old_one_is_blacklisted(self):
        tokens = self.check(self.login("cust1@x.com"), 200).data
        r = self.check(self.anon.post(f"{BASE}/token/refresh/", {"refresh": tokens["refresh"]}, format="json"), 200)
        self.assertNotEqual(r.data["refresh"], tokens["refresh"])
        self.check(self.anon.post(f"{BASE}/token/refresh/", {"refresh": tokens["refresh"]}, format="json"), 401)

    def test_superuser_gets_admin_role(self):
        self.assertEqual(self.admin.role, "admin")   # FIX: used to be "customer"


class ProfileTests(APIBase):
    def test_me_requires_login(self):
        self.check(self.anon.get(f"{BASE}/me/"), 401)

    def test_get_me(self):
        r = self.check(self.as_user(self.cust_user).get(f"{BASE}/me/"), 200)
        self.assertEqual((r.data["email"], r.data["role"]), ("cust1@x.com", "customer"))

    def test_patch_me_changes_only_personal_fields(self):
        c = self.as_user(self.cust_user)
        r = self.check(c.patch(f"{BASE}/me/", {"first_name": "Ali", "phone": "03005550000",
                                               "role": "admin", "email": "hacker@x.com", "username": "hacker"}, format="json"), 200)
        self.cust_user.refresh_from_db()
        self.assertEqual((self.cust_user.first_name, self.cust_user.phone), ("Ali", "03005550000"))
        self.assertEqual((self.cust_user.role, self.cust_user.email, self.cust_user.username),
                         ("customer", "cust1@x.com", "cust1"))

    def test_phone_clash_and_put_not_allowed(self):
        self.as_user(self.cust2_user).patch(f"{BASE}/me/", {"phone": "03009998888"}, format="json")
        self.check(self.as_user(self.cust_user).patch(f"{BASE}/me/", {"phone": "03009998888"}, format="json"), 400)
        self.check(self.as_user(self.cust_user).put(f"{BASE}/me/", {}, format="json"), 405)


class PasswordAndLogoutTests(APIBase):
    def tokens(self, email="cust1@x.com", password=None):
        return self.check(self.anon.post(f"{BASE}/login/", {"email": email, "password": password or self.PASSWORD}, format="json"), 200).data

    def test_change_password(self):
        tokens = self.tokens()
        c = self.as_user(self.cust_user)
        url = f"{BASE}/change-password/"
        self.check(c.post(url, {"old_password": "wrong", "new_password": "Brand-New-Pass-9"}, format="json"), 400)
        self.check(c.post(url, {"old_password": self.PASSWORD, "new_password": "12345678"}, format="json"), 400)
        self.check(c.post(url, {"old_password": self.PASSWORD, "new_password": self.PASSWORD}, format="json"), 400)
        self.check(c.post(url, {"old_password": self.PASSWORD, "new_password": "Brand-New-Pass-9"}, format="json"), 200)
        self.tokens(password="Brand-New-Pass-9")                                                     # new password works
        self.check(self.anon.post(f"{BASE}/login/", {"email": "cust1@x.com", "password": self.PASSWORD}, format="json"), 401)
        # the refresh token from before the change is dead
        self.check(self.anon.post(f"{BASE}/token/refresh/", {"refresh": tokens["refresh"]}, format="json"), 401)

    def test_change_password_needs_login(self):
        self.check(self.anon.post(f"{BASE}/change-password/", {}, format="json"), 401)

    def test_logout_blacklists_refresh_token(self):
        tokens = self.tokens()
        c = self.as_user(self.cust_user)
        self.check(c.post(f"{BASE}/logout/", {"refresh": tokens["refresh"]}, format="json"), 205)
        self.check(self.anon.post(f"{BASE}/token/refresh/", {"refresh": tokens["refresh"]}, format="json"), 401)
        self.check(c.post(f"{BASE}/logout/", {"refresh": "garbage"}, format="json"), 400)
        self.check(self.anon.post(f"{BASE}/logout/", {"refresh": tokens["refresh"]}, format="json"), 401)
