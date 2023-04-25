# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import os
from contextlib import suppress

import redis
from io import FileIO
from frappe.utils import get_site_path
from frappe import conf

import frappe

redis_server = None

@frappe.whitelist()
def get_pending_tasks_for_doc(doctype, docname):
	return frappe.db.sql_list(
		"select name from `tabAsync Task` where status in ('Queued', 'Running') and reference_doctype=%s and reference_name=%s",
		(doctype, docname),
	)


def set_task_status(task_id, status, response=None):
	if not response:
		response = {}
	response.update({
		"status": status,
		"task_id": task_id
	})
	emit_via_redis("task_status_change", response, room="task:" + task_id)


def remove_old_task_logs():
	logs_path = get_site_path('task-logs')

	def full_path(_file):
		return os.path.join(logs_path, _file)

	files_to_remove = [full_path(_file) for _file in os.listdir(logs_path)]
	files_to_remove = [_file for _file in files_to_remove if is_file_old(_file) and os.path.isfile(_file)]
	for _file in files_to_remove:
		os.remove(_file)


def is_file_old(file_path):
	return ((time.time() - os.stat(file_path).st_mtime) > TASK_LOG_MAX_AGE)

def publish_progress(percent, title=None, doctype=None, docname=None, description=None):
	publish_realtime(
		"progress",
		{"percent": percent, "title": title, "description": description},
		user=frappe.session.user,
		doctype=doctype,
		docname=docname,
	)


def publish_realtime(
	event: str = None,
	message: dict = None,
	room: str = None,
	user: str = None,
	doctype: str = None,
	docname: str = None,
	task_id: str = None,
	after_commit: bool = False,
):
	"""Publish real-time updates

	:param event: Event name, like `task_progress` etc. that will be handled by the client (default is `task_progress` if within task or `global`)
	:param message: JSON message object. For async must contain `task_id`
	:param room: Room in which to publish update (default entire site)
	:param user: Transmit to user
	:param doctype: Transmit to doctype, docname
	:param docname: Transmit to doctype, docname
	:param after_commit: (default False) will emit after current transaction is committed"""
	if message is None:
		message = {}

	if event is None:
		event = "task_progress" if frappe.local.task_id else "global"
	elif event == "msgprint" and not user:
		user = frappe.session.user
	elif event == "list_update":
		doctype = doctype or message.get("doctype")
		room = get_doctype_room(doctype)
	elif event == "docinfo_update":
		room = get_doc_room(doctype, docname)

	if not task_id and hasattr(frappe.local, "task_id"):
		task_id = frappe.local.task_id

	if not room:
		if task_id:
			after_commit = False
			if "task_id" not in message:
				message["task_id"] = task_id
			room = get_task_progress_room(task_id)
		elif user:
			# transmit to specific user: System, Website or Guest
			room = get_user_room(user)
		elif doctype and docname:
			room = get_doc_room(doctype, docname)
		else:
			# This will be broadcasted to all Desk users
			room = get_site_room()

	if after_commit:
		params = [event, message, room]
		if not params in frappe.local.realtime_log:
			frappe.local.realtime_log.append(params)
	else:
		emit_via_redis(event, message, room)

def emit_via_redis(event, message, room):
	"""Publish real-time updates via redis

	:param event: Event name, like `task_progress` etc.
	:param message: JSON message object. For async must contain `task_id`
	:param room: name of the room"""

	with suppress(redis.exceptions.ConnectionError):
		r = get_redis_server()
		r.publish("events", frappe.as_json({"event": event, "message": message, "room": room}))

def put_log(line_no, line, task_id=None):
	r = get_redis_server()
	if not task_id:
		task_id = frappe.local.task_id
	task_progress_room = get_task_progress_room(task_id)
	task_log_key = "task_log:" + task_id
	publish_realtime('task_progress', {
		"message": {
			"lines": {line_no: line}
		},
		"task_id": task_id
	}, room=task_progress_room)
	r.hset(task_log_key, line_no, line)
	r.expire(task_log_key, 3600)


def get_redis_server():
	"""returns redis_socketio connection."""
	global redis_server
	if not redis_server:
		from redis import Redis

		redis_server = Redis.from_url(frappe.conf.redis_socketio or "redis://localhost:12311")
	return redis_server


class FileAndRedisStream(FileIO):
	def __init__(self, *args, **kwargs):
		ret = super(FileAndRedisStream, self).__init__(*args, **kwargs)
		self.count = 0
		return ret

	def write(self, data):
		ret = super(FileAndRedisStream, self).write(data)
		if frappe.local.task_id:
			put_log(self.count, data, task_id=frappe.local.task_id)
			self.count += 1
		return ret


def get_std_streams(task_id):
	stdout = FileAndRedisStream(get_task_log_file_path(task_id, 'stdout'), 'w')
	# stderr = FileAndRedisStream(get_task_log_file_path(task_id, 'stderr'), 'w')
	return stdout, stdout


def get_task_log_file_path(task_id, stream_type):
	logs_dir = frappe.utils.get_site_path('task-logs')
	return os.path.join(logs_dir, task_id + '.' + stream_type)


@frappe.whitelist(allow_guest=True)
def can_subscribe_doc(doctype, docname):
	if os.environ.get("CI"):
		return True

	from frappe.exceptions import PermissionError
	from frappe.sessions import Session

	session = Session(None, resume=True).get_session_data()
	if not frappe.has_permission(user=session.user, doctype=doctype, doc=docname, ptype="read"):
		raise PermissionError()
	return True


@frappe.whitelist(allow_guest=True)
def can_subscribe_doctype(doctype: str) -> bool:
	from frappe.exceptions import PermissionError

	if not frappe.has_permission(user=frappe.session.user, doctype=doctype, ptype="read"):
		raise PermissionError()

	return True


@frappe.whitelist(allow_guest=True)
def get_user_info(sid):
	from frappe.sessions import Session

	session = Session(None, resume=True).get_session_data()

	return {
		"user": session.user,
		"user_type": session.user_type,
	}


def get_doctype_room(doctype):
	return f"{frappe.local.site}:doctype:{doctype}"


def get_doc_room(doctype, docname):
	return f"{frappe.local.site}:doc:{doctype}/{docname}"


def get_user_room(user):
	return f"{frappe.local.site}:user:{user}"


def get_site_room():
	return f"{frappe.local.site}:all"


def get_task_progress_room(task_id):
	return f"{frappe.local.site}:task_progress:{task_id}"


def get_website_room():
	return f"{frappe.local.site}:website"
