from django.test import Client, SimpleTestCase
from django.urls import reverse


class ScaffoldBoundaryTests(SimpleTestCase):
    def test_health_is_liveness_only(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "framework-only")
        self.assertNotIn("model_ready", response.json())

    def test_project_entry_identifies_scaffold(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "framework-only")
        self.assertEqual(response.json()["links"]["health"], reverse("health"))

    def test_business_routes_never_fabricate_success(self):
        routes = [
            ("post", "accounts:login", {}, "accounts.login"),
            ("get", "courses:list", {}, "courses.list"),
            ("get", "courses:tasks", {"course_id": 1}, "courses.tasks"),
            ("post", "knowledge:search", {}, "knowledge.search"),
            ("post", "learning:conversations", {}, "learning.conversations"),
            ("post", "learning:events", {}, "learning.events"),
            ("post", "model_gateway:chat", {}, "model_gateway.chat"),
        ]
        for method, route, kwargs, module in routes:
            with self.subTest(route=route):
                response = getattr(self.client, method)(reverse(route, kwargs=kwargs))
                self.assertEqual(response.status_code, 501)
                error = response.json()["error"]
                self.assertEqual(error["code"], "NOT_IMPLEMENTED")
                self.assertEqual(error["module"], module)

    def test_wrong_methods_are_rejected(self):
        self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 405)
        self.assertEqual(self.client.post(reverse("courses:list")).status_code, 405)

    def test_csrf_is_not_disabled_for_placeholder_posts(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("model_gateway:chat")).status_code, 403)

    def test_backend_has_no_command_execution_endpoint(self):
        self.assertEqual(self.client.post("/api/terminal/execute/").status_code, 404)
