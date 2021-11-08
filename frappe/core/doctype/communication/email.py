# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import json
from email.utils import formataddr
from frappe.core.utils import get_parent_doc
from frappe.utils import (get_url, get_formatted_email, cint, list_to_str,
	validate_email_address, split_emails, parse_addr, get_datetime)
from frappe.email.email_body import get_message_id
import frappe.email.smtp
import time
from frappe import _
from frappe.utils.background_jobs import enqueue

OUTGOING_EMAIL_ACCOUNT_MISSING = _("""
	Unable to send mail because of a missing email account.
	Please setup default Email Account from Setup > Email > Email Account
""")

@frappe.whitelist()
def make(doctype=None, name=None, content=None, subject=None, sent_or_received = "Sent",
	sender=None, sender_full_name=None, recipients=None, communication_medium="Email", send_email=False,
	print_html=None, print_format=None, attachments='[]', send_me_a_copy=False, cc=None, bcc=None,
	flags=None, read_receipt=None, print_letterhead=True, email_template=None, communication_type=None,
	ignore_permissions=False):
	"""Make a new communication.

	:param doctype: Reference DocType.
	:param name: Reference Document name.
	:param content: Communication body.
	:param subject: Communication subject.
	:param sent_or_received: Sent or Received (default **Sent**).
	:param sender: Communcation sender (default current user).
	:param recipients: Communication recipients as list.
	:param communication_medium: Medium of communication (default **Email**).
	:param send_email: Send via email (default **False**).
	:param print_html: HTML Print format to be sent as attachment.
	:param print_format: Print Format name of parent document to be sent as attachment.
	:param attachments: List of attachments as list of files or JSON string.
	:param send_me_a_copy: Send a copy to the sender (default **False**).
	:param email_template: Template which is used to compose mail .
	"""
	is_error_report = (doctype=="User" and name==frappe.session.user and subject=="Error Report")
	send_me_a_copy = cint(send_me_a_copy)

	if not ignore_permissions:
		if doctype and name and not is_error_report and not frappe.has_permission(doctype, "email", name) and not (flags or {}).get('ignore_doctype_permissions'):
			raise frappe.PermissionError("You are not allowed to send emails related to: {doctype} {name}".format(
				doctype=doctype, name=name))

	if not sender:
		sender = get_formatted_email(frappe.session.user)

	recipients = list_to_str(recipients) if isinstance(recipients, list) else recipients
	cc = list_to_str(cc) if isinstance(cc, list) else cc
	bcc = list_to_str(bcc) if isinstance(bcc, list) else bcc

	comm = frappe.get_doc({
		"doctype":"Communication",
		"subject": subject,
		"content": content,
		"sender": sender,
		"sender_full_name":sender_full_name,
		"recipients": recipients,
		"cc": cc or None,
		"bcc": bcc or None,
		"communication_medium": communication_medium,
		"sent_or_received": sent_or_received,
		"reference_doctype": doctype,
		"reference_name": name,
		"email_template": email_template,
		"message_id":get_message_id().strip(" <>"),
		"read_receipt":read_receipt,
		"has_attachment": 1 if attachments else 0,
		"communication_type": communication_type
	}).insert(ignore_permissions=True)

	comm.save(ignore_permissions=True)

	if isinstance(attachments, str):
		attachments = json.loads(attachments)

	# if not committed, delayed task doesn't find the communication
	if attachments:
		add_attachments(comm.name, attachments)

	if cint(send_email):
		# Raise error if outgoing email account is missing
		_ = frappe.email.smtp.get_outgoing_email_account(append_to=comm.doctype, sender=comm.sender)
		frappe.flags.print_letterhead = cint(print_letterhead)
		comm.send(print_html, print_format, attachments, send_me_a_copy=send_me_a_copy)

	emails_not_sent_to = comm.exclude_emails_list(include_sender=send_me_a_copy)
	return {
		"name": comm.name,
		"emails_not_sent_to": ", ".join(emails_not_sent_to or [])
	}

def validate_email(doc):
	"""Validate Email Addresses of Recipients and CC"""
	if not (doc.communication_type=="Communication" and doc.communication_medium == "Email") or doc.flags.in_receive:
		return

	# validate recipients
	for email in split_emails(doc.recipients):
		validate_email_address(email, throw=True)

	# validate CC
	for email in split_emails(doc.cc):
		validate_email_address(email, throw=True)

	for email in split_emails(doc.bcc):
		validate_email_address(email, throw=True)

	# validate sender

def notify(doc, print_html=None, print_format=None, attachments=None,
	recipients=None, cc=None, bcc=None, fetched_from_email_account=False):
	"""Calls a delayed task 'sendmail' that enqueus email in Email Queue queue

	:param print_html: Send given value as HTML attachment
	:param print_format: Attach print format of parent document
	:param attachments: A list of filenames that should be attached when sending this email
	:param recipients: Email recipients
	:param cc: Send email as CC to
	:param bcc: Send email as BCC to
	:param fetched_from_email_account: True when pulling email, the notification shouldn't go to the main recipient

	"""
	recipients, cc, bcc = get_recipients_cc_and_bcc(doc, recipients, cc, bcc,
		fetched_from_email_account=fetched_from_email_account)

	if not recipients and not cc:
		return

	doc.emails_not_sent_to = set(doc.all_email_addresses) - set(doc.sent_email_addresses)

	if frappe.flags.in_test:
		# for test cases, run synchronously
		doc._notify(print_html=print_html, print_format=print_format, attachments=attachments,
			recipients=recipients, cc=cc, bcc=None)
	else:
		enqueue(sendmail, queue="default", timeout=300, event="sendmail",
			enqueue_after_commit=True, communication_name=doc.name,
			print_html=print_html, print_format=print_format, attachments=attachments,
			recipients=recipients, cc=cc, bcc=bcc, lang=frappe.local.lang,
			session=frappe.local.session, print_letterhead=frappe.flags.print_letterhead)

def _notify(doc, print_html=None, print_format=None, attachments=None,
	recipients=None, cc=None, bcc=None):

	prepare_to_notify(doc, print_html, print_format, attachments)

	if doc.outgoing_email_account.send_unsubscribe_message:
		unsubscribe_message = _("Leave this conversation")
	else:
		unsubscribe_message = ""

	frappe.sendmail(
		recipients=(recipients or []),
		cc=(cc or []),
		bcc=(bcc or []),
		expose_recipients="header",
		sender=doc.sender,
		reply_to=doc.incoming_email_account,
		subject=doc.subject,
		content=doc.content,
		reference_doctype=doc.reference_doctype,
		reference_name=doc.reference_name,
		attachments=doc.attachments,
		message_id=doc.message_id,
		unsubscribe_message=unsubscribe_message,
		delayed=True,
		communication=doc.name,
		read_receipt=doc.read_receipt,
		is_notification=True if doc.sent_or_received =="Received" else False,
		print_letterhead=frappe.flags.print_letterhead
	)

def get_recipients_cc_and_bcc(doc, recipients, cc, bcc, fetched_from_email_account=False):
	doc.all_email_addresses = []
	doc.sent_email_addresses = []
	doc.previous_email_sender = None

	if not recipients:
		recipients = get_recipients(doc, fetched_from_email_account=fetched_from_email_account)

	if not cc:
		cc = get_cc(doc, recipients, fetched_from_email_account=fetched_from_email_account)

	if not bcc:
		bcc = get_bcc(doc, recipients, fetched_from_email_account=fetched_from_email_account)

	if fetched_from_email_account:
		# email was already sent to the original recipient by the sender's email service
		original_recipients, recipients = recipients, []

		# send email to the sender of the previous email in the thread which this email is a reply to
		#provides erratic results and can send external
		#if doc.previous_email_sender:
		#	recipients.append(doc.previous_email_sender)

		# cc that was received in the email
		original_cc = split_emails(doc.cc)

		# don't cc to people who already received the mail from sender's email service
		cc = list(set(cc) - set(original_cc) - set(original_recipients))
		remove_administrator_from_email_list(cc)

		original_bcc = split_emails(doc.bcc)
		bcc = list(set(bcc) - set(original_bcc) - set(original_recipients))
		remove_administrator_from_email_list(bcc)

	remove_administrator_from_email_list(recipients)

	return recipients, cc, bcc

def remove_administrator_from_email_list(email_list):
	administrator_email = list(filter(lambda emails: "Administrator" in emails, email_list))
	if administrator_email:
		email_list.remove(administrator_email[0])

def prepare_to_notify(doc, print_html=None, print_format=None, attachments=None):
	"""Prepare to make multipart MIME Email

	:param print_html: Send given value as HTML attachment.
	:param print_format: Attach print format of parent document."""

	view_link = frappe.utils.cint(frappe.db.get_value("System Settings", "System Settings", "attach_view_link"))

	if print_format and view_link:
		doc.content += get_attach_link(doc, print_format)

	set_incoming_outgoing_accounts(doc)

	if not doc.sender:
		doc.sender = doc.outgoing_email_account.email_id

	if not doc.sender_full_name:
		doc.sender_full_name = doc.outgoing_email_account.name or _("Notification")

	if doc.sender:
		# combine for sending to get the format 'Jane <jane@example.com>'
		doc.sender = get_formatted_email(doc.sender_full_name, mail=doc.sender)

	doc.attachments = []

	if print_html or print_format:
		doc.attachments.append({"print_format_attachment":1, "doctype":doc.reference_doctype,
			"name":doc.reference_name, "print_format":print_format, "html":print_html})

	if attachments:
		if isinstance(attachments, string_types):
			attachments = json.loads(attachments)

		for a in attachments:
			if isinstance(a, string_types):
				# is it a filename?
				try:
					# check for both filename and file id
					file_id = frappe.db.get_list('File', or_filters={'file_name': a, 'name': a}, limit=1)
					if not file_id:
						frappe.throw(_("Unable to find attachment {0}").format(a))
					file_id = file_id[0]['name']
					_file = frappe.get_doc("File", file_id)
					_file.get_content()
					# these attachments will be attached on-demand
					# and won't be stored in the message
					doc.attachments.append({"fid": file_id})
				except IOError:
					frappe.throw(_("Unable to find attachment {0}").format(a))
			else:
				doc.attachments.append(a)

def set_incoming_outgoing_accounts(doc):
	from frappe.email.doctype.email_account.email_account import EmailAccount
	incoming_email_account = EmailAccount.find_incoming(
		match_by_email=doc.sender, match_by_doctype=doc.reference_doctype)
	doc.incoming_email_account = incoming_email_account.email_id if incoming_email_account else None

	doc.outgoing_email_account = EmailAccount.find_outgoing(
		match_by_email=doc.sender, match_by_doctype=doc.reference_doctype)

	if doc.sent_or_received == "Sent":
		doc.db_set("email_account", doc.outgoing_email_account.name)

def add_attachments(name, attachments):
	'''Add attachments to the given Communication'''
	# loop through attachments
	for a in attachments:
		if isinstance(a, str):
			attach = frappe.db.get_value("File", {"name":a},
				["file_name", "file_url", "is_private"], as_dict=1)
			# save attachments to new doc
			_file = frappe.get_doc({
				"doctype": "File",
				"file_url": attach.file_url,
				"attached_to_doctype": "Communication",
				"attached_to_name": name,
				"folder": "Home/Attachments",
				"is_private": attach.is_private
			})
			_file.save(ignore_permissions=True)

@frappe.whitelist(allow_guest=True)
def mark_email_as_seen(name=None):
	try:
		if name and frappe.db.exists("Communication", name) and not frappe.db.get_value("Communication", name, "read_by_recipient"):
			frappe.db.set_value("Communication", name, "read_by_recipient", 1)
			frappe.db.set_value("Communication", name, "delivery_status", "Read")
			frappe.db.set_value("Communication", name, "read_by_recipient_on", get_datetime())
			frappe.db.commit()
	except Exception:
		frappe.log_error(frappe.get_traceback())
	finally:
		# Return image as response under all circumstances
		from PIL import Image
		import io
		im = Image.new('RGBA', (1, 1))
		im.putdata([(255,255,255,0)])
		buffered_obj = io.BytesIO()
		im.save(buffered_obj, format="PNG")

		frappe.response["type"] = 'binary'
		frappe.response["filename"] = "imaginary_pixel.png"
		frappe.response["filecontent"] = buffered_obj.getvalue()
