# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
from werkzeug.wrappers import Request
from werkzeug.test import EnvironBuilder


def update_system_settings(args, commit=False):
	doc = frappe.get_doc("System Settings")
	doc.update(args)
	doc.flags.ignore_mandatory = 1
	doc.save()
	if commit:
		frappe.db.commit()


def insert_test_data(doctype, sort_fn=None):
	import frappe.model
	data = get_test_doclist(doctype)
	if sort_fn:
		data = sorted(data, key=sort_fn)


global_test_dependencies = ["User"]
