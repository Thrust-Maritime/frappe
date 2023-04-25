import unittest
from random import choice
from threading import Thread
from time import time
from unittest.mock import patch

import requests
import base64

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_site_url, get_test_client

try:
	_site = frappe.local.site
except Exception:
	_site = None

authorization_token = None


def maintain_state(f):
	def wrapper(*args, **kwargs):
		frappe.db.rollback()
		r = f(*args, **kwargs)
		frappe.db.commit()

		server.insert_many([
			{"doctype": "Note", "public": True, "title": "Sing"},
			{"doctype": "Note", "public": True, "title": "a"},
			{"doctype": "Note", "public": True, "title": "song"},
			{"doctype": "Note", "public": True, "title": "of"},
			{"doctype": "Note", "public": True, "title": "sixpence"},
		])

		self.assertTrue(frappe.db.get_value('Note', {'title': 'Sing'}))
		self.assertTrue(frappe.db.get_value('Note', {'title': 'a'}))
		self.assertTrue(frappe.db.get_value('Note', {'title': 'song'}))
		self.assertTrue(frappe.db.get_value('Note', {'title': 'of'}))
		self.assertTrue(frappe.db.get_value('Note', {'title': 'sixpence'}))

	def test_create_doc(self):
		server = FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)
		frappe.db.sql("delete from `tabNote` where title = 'test_create'")
		frappe.db.commit()

	@classmethod
	@maintain_state
	def setUpClass(self):
		for _ in range(10):
			doc = frappe.get_doc({"doctype": "ToDo", "description": frappe.mock("paragraph")}).insert()
			self.GENERATED_DOCUMENTS.append(doc.name)

		self.assertTrue(frappe.db.get_value('Note', {'title': 'test_create'}))

	def test_list_docs(self):
		server = FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)
		doc_list = server.get_list("Note")

		self.assertTrue(len(doc_list))

	def test_get_doc(self):
		server = FrappeClient(frappe.get_site_config().host_name, "Administrator", "admin", verify=False)
		frappe.db.sql("delete from `tabNote` where title = 'get_this'")
		frappe.db.commit()

	def post(self, path, data):
		return requests.post(f"{self.RESOURCE_URL}/{path}?sid={self.sid}", data=frappe.as_json(data))

	def put(self, path, data):
		return requests.put(f"{self.RESOURCE_URL}/{path}?sid={self.sid}", data=frappe.as_json(data))

		self.assertEqual(res.status_code, 200)
		self.assertEqual("Administrator", res.json()["message"])
		self.assertEqual(keys['api_secret'], generated_secret)

		header = {"Authorization": "Basic {}".format(base64.b64encode(frappe.safe_encode("{}:{}".format(api_key, generated_secret))).decode())}
		res = requests.post(frappe.get_site_config().host_name + "/api/method/frappe.auth.get_logged_user", headers=header)
		self.assertEqual(res.status_code, 200)
		self.assertEqual("Administrator", res.json()["message"])

		# Valid api key, invalid api secret
		api_secret = "ksk&93nxoe3os"
		header = {"Authorization": "token {}:{}".format(api_key, api_secret)}
		res = requests.post(frappe.get_site_config().host_name + "/api/method/frappe.auth.get_logged_user", headers=header)
		self.assertEqual(res.status_code, 403)


class TestMethodAPI(unittest.TestCase):
	METHOD_URL = f"{get_site_url(frappe.local.site)}/api/method"

	def test_version(self):
		# test 1: test for /api/method/version
		response = requests.get(f"{self.METHOD_URL}/version")
		json = frappe._dict(response.json())

		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(json, dict)
		self.assertIsInstance(json.message, str)
		self.assertEqual(Version(json.message), Version(frappe.__version__))

	def test_ping(self):
		# test 2: test for /api/method/ping
		response = requests.get(f"{self.METHOD_URL}/ping")
		self.assertEqual(response.status_code, 200)
		self.assertIsInstance(response.json(), dict)
		self.assertEqual(response.json()["message"], "pong")


class FrappeAPITestCase(FrappeTestCase):
	SITE = frappe.local.site
	SITE_URL = get_site_url(SITE)
	RESOURCE_URL = f"{SITE_URL}/api/resource"
	TEST_CLIENT = get_test_client()

	@property
	def sid(self):
		if not getattr(self, "_sid", None):
			from frappe.auth import CookieManager, LoginManager
			from frappe.utils import set_request

			set_request(path="/")
			frappe.local.cookie_manager = CookieManager()
			frappe.local.login_manager = LoginManager()
			frappe.local.login_manager.login_as("Administrator")
			self._sid = frappe.session.sid

		return self._sid

	def get(self, path, params=None, **kwargs):
		return make_request(target=self.TEST_CLIENT.get, args=(path,), kwargs={"data": params, **kwargs})

	def post(self, path, data, **kwargs):
		return make_request(target=self.TEST_CLIENT.post, args=(path,), kwargs={"data": data, **kwargs})

	def put(self, path, data, **kwargs):
		return make_request(target=self.TEST_CLIENT.put, args=(path,), kwargs={"data": data, **kwargs})

	def delete(self, path, **kwargs):
		return make_request(target=self.TEST_CLIENT.delete, args=(path,), kwargs=kwargs)


def make_request(target, args=None, kwargs=None, site=None):
	t = ThreadWithReturnValue(target=target, args=args, kwargs=kwargs, site=site)
	t.start()
	t.join()
	return t._return


class ThreadWithReturnValue(Thread):
	def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, *, site=None):
		Thread.__init__(self, group, target, name, args, kwargs)
		self._return = None
		self.site = site or _site

	def run(self):
		if self._target is not None:
			with patch("frappe.app.get_site_name", return_value=self.site):
				header_patch = patch("frappe.get_request_header", new=patch_request_header)
				if authorization_token:
					header_patch.start()
				self._return = self._target(*self._args, **self._kwargs)
				if authorization_token:
					header_patch.stop()

	def join(self, *args):
		Thread.join(self, *args)
		return self._return


def patch_request_header(key, *args, **kwargs):
	if key == "Authorization":
		return f"token {authorization_token}"


class TestWSGIApp(FrappeAPITestCase):
	def test_request_hooks(self):
		self.addCleanup(lambda: _test_REQ_HOOK.clear())
		get_hooks = frappe.get_hooks

		def patch_request_hooks(event: str, *args, **kwargs):
			patched_hooks = {
				"before_request": ["frappe.tests.test_api.before_request"],
				"after_request": ["frappe.tests.test_api.after_request"],
			}
			if event not in patched_hooks:
				return get_hooks(event, *args, **kwargs)
			return patched_hooks[event]

		with patch("frappe.get_hooks", patch_request_hooks):
			self.assertIsNone(_test_REQ_HOOK.get("before_request"))
			self.assertIsNone(_test_REQ_HOOK.get("after_request"))
			res = self.get("/api/method/ping")
			self.assertLess(_test_REQ_HOOK.get("before_request"), _test_REQ_HOOK.get("after_request"))


_test_REQ_HOOK = {}


def before_request(*args, **kwargs):
	_test_REQ_HOOK["before_request"] = time()


def after_request(*args, **kwargs):
	_test_REQ_HOOK["after_request"] = time()
