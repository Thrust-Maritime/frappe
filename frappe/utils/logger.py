from __future__ import unicode_literals
import frappe
import logging
import os
from copy import deepcopy
from logging.handlers import RotatingFileHandler
from six import text_type

# imports - module imports
import frappe
from frappe.utils import get_sites

default_log_level = logging.DEBUG
LOG_FILENAME = '../logs/frappe.log'

def get_logger(module, with_more_info=True):
	if module in frappe.loggers:
		return frappe.loggers[module]

def get_logger(
	module=None, with_more_info=False, allow_site=True, filter=None, max_size=100_000, file_count=20
):
	"""Application Logger for your given module

	Args:
	        module (str, optional): Name of your logger and consequently your log file. Defaults to None.
	        with_more_info (bool, optional): Will log the form dict using the SiteContextFilter. Defaults to False.
	        allow_site ((str, bool), optional): Pass site name to explicitly log under it's logs. If True and unspecified, guesses which site the logs would be saved under. Defaults to True.
	        filter (function, optional): Add a filter function for your logger. Defaults to None.
	        max_size (int, optional): Max file size of each log file in bytes. Defaults to 100_000.
	        file_count (int, optional): Max count of log files to be retained via Log Rotation. Defaults to 20.

	Returns:
	        <class 'logging.Logger'>: Returns a Python logger object with Site and Bench level logging capabilities.
	"""

	if allow_site is True:
		site = getattr(frappe.local, "site", None)
	elif allow_site in get_sites():
		site = allow_site
	else:
		site = False

	logger_name = "{0}-{1}".format(module, site or "all")

	try:
		return frappe.loggers[logger_name]
	except KeyError:
		pass

	if not module:
		module = "frappe"
		with_more_info = True

	logfile = module + ".log"
	log_filename = os.path.join("..", "logs", logfile)

	logger = logging.getLogger(logger_name)
	logger.setLevel(frappe.log_level or default_log_level)
	logger.propagate = False

	formatter = logging.Formatter("%(asctime)s %(levelname)s {0} %(message)s".format(module))
	handler = RotatingFileHandler(log_filename, maxBytes=max_size, backupCount=file_count)
	handler.setFormatter(formatter)

	if with_more_info:
		handler.addFilter(SiteContextFilter())

	logger = logging.getLogger(module)
	logger.setLevel(frappe.log_level or default_log_level)
	logger.addHandler(handler)
	logger.propagate = False

	frappe.loggers[module] = logger

	return logger

class SiteContextFilter(logging.Filter):
	"""This is a filter which injects request information (if available) into the log."""
	def filter(self, record):
		if "Form Dict" not in text_type(record.msg):
			site = getattr(frappe.local, "site", None)
			form_dict = sanitized_dict(getattr(frappe.local, "form_dict", None))
			record.msg = str(record.msg) + f"\nSite: {site}\nForm Dict: {form_dict}"
			return True

def get_more_info_for_log():
	'''Adds Site, Form Dict into log entry'''
	more_info = []
	site = getattr(frappe.local, 'site', None)
	if site:
		more_info.append('Site: {0}'.format(site))

	form_dict = getattr(frappe.local, 'form_dict', None)
	if form_dict:
		more_info.append('Form Dict: {0}'.format(frappe.as_json(form_dict)))

	if more_info:
		# to append a \n
		more_info = more_info + ['']

	return '\n'.join(more_info)

def set_log_level(level):
	'''Use this method to set log level to something other than the default DEBUG'''
	frappe.log_level = getattr(logging, (level or '').upper(), None) or default_log_level
	frappe.loggers = {}


def sanitized_dict(form_dict):
	if not isinstance(form_dict, dict):
		return form_dict

	sanitized_dict = deepcopy(form_dict)

	blocklist = [
		"password",
		"passwd",
		"secret",
		"token",
		"key",
		"pwd",
	]

	for k in sanitized_dict:
		for secret_kw in blocklist:
			if secret_kw in k:
				sanitized_dict[k] = "********"
	return sanitized_dict
