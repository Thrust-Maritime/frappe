# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

"""This module handles the On Demand Backup utility"""

from __future__ import print_function, unicode_literals

import os
import json
from calendar import timegm
from datetime import datetime
from glob import glob

import frappe
from frappe import _, conf
from frappe.utils import cint, get_file_size, get_url, now, now_datetime

# backup variable for backwards compatibility
verbose = False
_verbose = verbose


class BackupGenerator:
	"""
		This class contains methods to perform On Demand Backup

		To initialize, specify (db_name, user, password, db_file_name=None, db_host="localhost")
		If specifying db_file_name, also append ".sql.gz"
	"""
	def __init__(self, db_name, user, password, backup_path_db=None, backup_path_files=None,
		backup_path_private_files=None, db_host="localhost", db_port=None, verbose=False,
		db_type='mariadb'):
		global _verbose
		self.db_host = db_host
		self.db_port = db_port
		self.db_name = db_name
		self.db_type = db_type
		self.user = user
		self.password = password
		self.backup_path_files = backup_path_files
		self.backup_path_db = backup_path_db
		self.backup_path_private_files = backup_path_private_files

		if not self.db_type:
			self.db_type = 'mariadb'

		if not self.db_port and self.db_type == 'mariadb':
			self.db_port = 3306
		elif not self.db_port and self.db_type == 'postgres':
			self.db_port = 5432

		site = frappe.local.site or frappe.generate_hash(length=8)
		self.site_slug = site.replace('.', '_')

		self.verbose = verbose
		_verbose = verbose

	def get_backup(self, older_than=24, ignore_files=False, force=False):
		"""
			Takes a new dump if existing file is old
			and sends the link to the file as email
		"""
		#Check if file exists and is less than a day old
		#If not Take Dump
		if not force:
			last_db, last_file, last_private_file, site_config_backup_path = self.get_recent_backup(older_than)
		else:
			last_db, last_file, last_private_file, site_config_backup_path = False, False, False, False

		if not (
			self.backup_path_conf
			and self.backup_path_db
			and self.backup_path_files
			and self.backup_path_private_files
		):
			self.set_backup_file_name()

		if not (last_db and last_file and last_private_file and site_config_backup_path):
			self.take_dump()
			self.copy_site_config()
			if not ignore_files:
				self.zip_files()

		else:
			self.backup_path_files = last_file
			self.backup_path_db = last_db
			self.backup_path_private_files = last_private_file
			self.site_config_backup_path = site_config_backup_path

	def set_backup_file_name(self):
		partial = "-partial" if self.partial else ""
		ext = "tgz" if self.compress_files else "tar"
		self.todays_date = now_datetime().strftime("%Y%m%d_%H%M%S")

		if not self.backup_path_db:
			self.backup_path_db = os.path.join(backup_path, for_db)
		if not self.backup_path_files:
			self.backup_path_files = os.path.join(backup_path, for_public_files)
		if not self.backup_path_private_files:
			self.backup_path_private_files = os.path.join(backup_path, for_private_files)

	def get_recent_backup(self, older_than):
		backup_path = get_backup_path()

		file_type_slugs = {
			"database": "*-{{}}-{}database.sql.gz".format("*" if partial else ""),
			"public": "*-{}-files.tar",
			"private": "*-{}-private-files.tar",
			"config": "*-{}-site_config_backup.json",
		}

		def backup_time(file_path):
			file_name = file_path.split(os.sep)[-1]
			file_timestamp = file_name.split("-")[0]
			return timegm(datetime.strptime(file_timestamp, "%Y%m%d_%H%M%S").utctimetuple())

		def get_latest(file_pattern):
			file_pattern = os.path.join(backup_path, file_pattern.format(self.site_slug))
			file_list = glob(file_pattern)
			if file_list:
				return max(file_list, key=backup_time)

		def old_enough(file_path):
			if file_path:
				if not os.path.isfile(file_path) or is_file_old(file_path, older_than):
					return None
				return file_path

		latest_backups = {
			file_type: get_latest(pattern)
			for file_type, pattern in file_type_slugs.items()
		}

		recent_backups = {
			file_type: old_enough(file_name) for file_type, file_name in latest_backups.items()
		}

		return (
			recent_backups.get("database"),
			recent_backups.get("public"),
			recent_backups.get("private"),
			recent_backups.get("config"),
		)

	def zip_files(self):
		# For backwards compatibility - pre v13
		click.secho(
			"BackupGenerator.zip_files has been deprecated in favour of" " BackupGenerator.backup_files",
			fg="yellow",
		)
		return self.backup_files()

	def get_summary(self):
		summary = {
			"config": {
				"path": self.backup_path_conf,
				"size": get_file_size(self.backup_path_conf, format=True),
			},
			"database": {
				"path": self.backup_path_db,
				"size": get_file_size(self.backup_path_db, format=True),
			},
		}

		if os.path.exists(self.backup_path_files) and os.path.exists(self.backup_path_private_files):
			summary.update(
				{
					"public": {
						"path": self.backup_path_files,
						"size": get_file_size(self.backup_path_files, format=True),
					},
					"private": {
						"path": self.backup_path_private_files,
						"size": get_file_size(self.backup_path_private_files, format=True),
					},
				}
			)

		return summary

	def print_summary(self):
		backup_summary = self.get_summary()
		print("Backup Summary for {0} at {1}".format(frappe.local.site, now()))

		title = max([len(x) for x in backup_summary])
		path = max([len(x["path"]) for x in backup_summary.values()])

		for _type, info in backup_summary.items():
			template = "{{0:{0}}}: {{1:{1}}} {{2}}".format(title, path)
			print(template.format(_type.title(), info["path"], info["size"]))

	def backup_files(self):
		for folder in ("public", "private"):
			files_path = frappe.get_site_path(folder, "files")
			backup_path = self.backup_path_files if folder == "public" else self.backup_path_private_files

			cmd_string = """tar -cf %s %s""" % (backup_path, files_path)
			err, out = frappe.utils.execute_in_shell(cmd_string)

			frappe.utils.execute_in_shell(
				cmd_string.format(backup_path, files_path), verbose=self.verbose, low_priority=True
			)

	def copy_site_config(self):
		site_config_backup_path = os.path.join(
			get_backup_path(),
			"{time_stamp}-{site_slug}-site_config_backup.json".format(
				time_stamp=self.todays_date,
				site_slug=self.site_slug))
		site_config_path = os.path.join(frappe.get_site_path(), "site_config.json")
		site_config = {}
		if os.path.exists(site_config_path):
			site_config.update(frappe.get_file_json(site_config_path))
		with open(site_config_backup_path, "w") as f:
			f.write(json.dumps(site_config, indent=2))
			f.flush()
		self.site_config_backup_path = site_config_backup_path

	def take_dump(self):
		import frappe.utils
		from frappe.utils.change_log import get_app_branch

		db_exc = {
			"mariadb": ("mysqldump", which("mysqldump")),
			"postgres": ("pg_dump", which("pg_dump")),
		}[self.db_type]
		gzip_exc = which("gzip")

		if not (gzip_exc and db_exc[1]):
			_exc = "gzip" if not gzip_exc else db_exc[0]
			frappe.throw(
				f"{_exc} not found in PATH! This is required to take a backup.", exc=frappe.ExecutableNotFound
			)
		db_exc = db_exc[0]

		database_header_content = [
			f"Backup generated by Frappe {frappe.__version__} on branch {get_app_branch('frappe') or 'N/A'}",
			"",
		]

		# escape reserved characters
		args = frappe._dict(
			[item[0], frappe.utils.esc(str(item[1]), "$ ")] for item in self.__dict__.copy().items()
		)

		cmd_string = """mysqldump --single-transaction --quick --lock-tables=false -u %(user)s -p%(password)s %(db_name)s -h %(db_host)s -P %(db_port)s | gzip > %(backup_path_db)s """ % args

		if self.partial:
			print("".join(backup_info), "\n")
			database_header_content.extend(
				[
					f"Partial Backup of Frappe Site {frappe.local.site}",
					("Backup contains: " if self.backup_includes else "Backup excludes: ") + backup_info[1],
					"",
				]
			)

		generated_header = "\n".join([f"-- {x}" for x in database_header_content]) + "\n"

		with gzip.open(args.backup_path_db, "wt") as f:
			f.write(generated_header)

		if self.db_type == "postgres":
			if self.backup_includes:
				args["include"] = " ".join(
					["--table='public.\"{0}\"'".format(table) for table in self.backup_includes]
				)
			elif self.backup_excludes:
				args["exclude"] = " ".join(
					["--exclude-table-data='public.\"{0}\"'".format(table) for table in self.backup_excludes]
				)

			cmd_string = (
				"self=$$; "
				"( {db_exc} postgres://{user}:{password}@{db_host}:{db_port}/{db_name}"
				" {include} {exclude} || kill $self ) | {gzip} >> {backup_path_db}"
			)

		else:
			if self.backup_includes:
				args["include"] = " ".join(["'{0}'".format(x) for x in self.backup_includes])
			elif self.backup_excludes:
				args["exclude"] = " ".join(
					[
						"--ignore-table='{0}.{1}'".format(frappe.conf.db_name, table)
						for table in self.backup_excludes
					]
				)

			cmd_string = (
				# Remember process of this shell and kill it if mysqldump exits w/ non-zero code
				"self=$$; "
				" ( {db_exc} --single-transaction --quick --lock-tables=false -u {user}"
				" -p{password} {db_name} -h {db_host} -P {db_port} {include} {exclude} || kill $self ) "
				" | {gzip} >> {backup_path_db}"
			)

		command = cmd_string.format(
			user=args.user,
			password=args.password,
			db_exc=db_exc,
			db_host=args.db_host,
			db_port=args.db_port,
			db_name=args.db_name,
			backup_path_db=args.backup_path_db,
			exclude=args.get("exclude", ""),
			include=args.get("include", ""),
			gzip=gzip_exc,
		)

		if self.verbose:
			print(command.replace(args.password, "*" * 10) + "\n")

		frappe.utils.execute_in_shell(command, low_priority=True, check_exit_code=True)

	def send_email(self):
		"""
			Sends the link to backup file located at erpnext/backups
		"""
		from frappe.email import get_system_managers

		recipient_list = get_system_managers()
		db_backup_url = get_url(os.path.join("backups", os.path.basename(self.backup_path_db)))
		files_backup_url = get_url(os.path.join("backups", os.path.basename(self.backup_path_files)))

		msg = """Hello,

Your backups are ready to be downloaded.

1. [Click here to download the database backup](%(db_backup_url)s)
2. [Click here to download the files backup](%(files_backup_url)s)

This link will be valid for 24 hours. A new backup will be available for
download only after 24 hours.""" % {
			"db_backup_url": db_backup_url,
			"files_backup_url": files_backup_url
		}

		datetime_str = datetime.fromtimestamp(os.stat(self.backup_path_db).st_ctime)
		subject = datetime_str.strftime("%d/%m/%Y %H:%M:%S") + """ - Backup ready to be downloaded"""

		frappe.sendmail(recipients=recipient_list, msg=msg, subject=subject)
		return recipient_list


@frappe.whitelist()
def get_backup():
	"""
		This function is executed when the user clicks on
		Toos > Download Backup
	"""
	delete_temp_backups()
	odb = BackupGenerator(frappe.conf.db_name, frappe.conf.db_name,\
						  frappe.conf.db_password, db_host = frappe.db.host,\
							db_type=frappe.conf.db_type, db_port=frappe.conf.db_port)
	odb.get_backup()
	recipient_list = odb.send_email()
	frappe.msgprint(_("Download link for your backup will be emailed on the following email address: {0}").format(', '.join(recipient_list)))


@frappe.whitelist()
def fetch_latest_backups():
	"""Fetches paths of the latest backup taken in the last 30 days
	Only for: System Managers

	Returns:
	        dict: relative Backup Paths
	"""
	frappe.only_for("System Manager")
	odb = BackupGenerator(
		frappe.conf.db_name,
		frappe.conf.db_name,
		frappe.conf.db_password,
		db_host=frappe.db.host,
		db_type=frappe.conf.db_type,
		db_port=frappe.conf.db_port,
	)
	database, public, private, config = odb.get_recent_backup(older_than=24 * 30)

	return {
		"database": database,
		"public": public,
		"private": private,
		"config": config
	}


def scheduled_backup(older_than=6, ignore_files=False, backup_path_db=None, backup_path_files=None, backup_path_private_files=None, force=False, verbose=False):
	"""this function is called from scheduler
		deletes backups older than 7 days
		takes backup"""
	odb = new_backup(older_than, ignore_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files, force=force, verbose=verbose)
	return odb

def new_backup(older_than=6, ignore_files=False, backup_path_db=None, backup_path_files=None, backup_path_private_files=None, force=False, verbose=False):
	delete_temp_backups(older_than = frappe.conf.keep_backups_for_hours or 24)
	odb = BackupGenerator(frappe.conf.db_name, frappe.conf.db_name,\
						  frappe.conf.db_password,
						  backup_path_db=backup_path_db, backup_path_files=backup_path_files,
						  backup_path_private_files=backup_path_private_files,
						  db_host = frappe.db.host,
						  db_port = frappe.db.port,
						  db_type = frappe.conf.db_type,
						  verbose=verbose)
	odb.get_backup(older_than, ignore_files, force=force)
	return odb

def delete_temp_backups(older_than=24):
	"""
		Cleans up the backup_link_path directory by deleting files older than 24 hours
	"""
	backup_path = get_backup_path()
	if os.path.exists(backup_path):
		file_list = os.listdir(get_backup_path())
		for this_file in file_list:
			this_file_path = os.path.join(get_backup_path(), this_file)
			if is_file_old(this_file_path, older_than):
				os.remove(this_file_path)

def is_file_old(db_file_name, older_than=24):
		"""
			Checks if file exists and is older than specified hours
			Returns ->
			True: file does not exist or file is old
			False: file is new
		"""
		if os.path.isfile(db_file_name):
			from datetime import timedelta
			#Get timestamp of the file
			file_datetime = datetime.fromtimestamp\
						(os.stat(db_file_name).st_ctime)
			if datetime.today() - file_datetime >= timedelta(hours = older_than):
				if _verbose:
					print("File is old")
				return True
			else:
				if _verbose:
					print("File is recent")
				return False
		else:
			if _verbose:
				print("File does not exist")
			return True

def get_backup_path():
	backup_path = frappe.utils.get_site_path(conf.get("backup_path", "private/backups"))
	return backup_path

def backup(with_files=False, backup_path_db=None, backup_path_files=None, quiet=False):
	"Backup"
	odb = scheduled_backup(ignore_files=not with_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files, force=True)
	return {
		"backup_path_db": odb.backup_path_db,
		"backup_path_files": odb.backup_path_files,
		"backup_path_private_files": odb.backup_path_private_files
	}


if __name__ == "__main__":
	"""
		is_file_old db_name user password db_host db_type db_port
		get_backup  db_name user password db_host db_type db_port
	"""
	import sys
	cmd = sys.argv[1]

	db_type = 'mariadb'
	try:
		db_type = sys.argv[6]
	except IndexError:
		pass

	db_port = 3306
	try:
		db_port = int(sys.argv[7])
	except IndexError:
		pass

	if cmd == "is_file_old":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost", db_type=db_type, db_port=db_port)
		is_file_old(odb.db_file_name)

	if cmd == "get_backup":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost", db_type=db_type, db_port=db_port)
		odb.get_backup()

	if cmd == "take_dump":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost", db_type=db_type, db_port=db_port)
		odb.take_dump()

	if cmd == "send_email":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost", db_type=db_type, db_port=db_port)
		odb.send_email("abc.sql.gz")

	if cmd == "delete_temp_backups":
		delete_temp_backups()
