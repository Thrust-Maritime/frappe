// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on('Web Page', {
	layout: function(frm) {
		if (frm.is_new()) {
			if (frm.doc.insert_code) {
				if (!frm.doc.javascript) {
					frm.set_value('javascript', `frappe.ready(() => {\n\t\n});`);
				}
			}
		}
	},
	insert_code: function(frm) {
		frm.events.layout(frm);
	},
	onload: function(frm) {
		frm.set_query('web_template', 'page_blocks', function() {
			return {
				filters: {
					"type": 'Section'
				}
			};
		});
	},
	validate: function(frm) {
		if (frm.doc.title && !frm.doc.route) {
			frm.set_value('route', frappe.scrub(frm.doc.title, '-'));
		}
	},
	refresh: function(frm) {
		if (frm.doc.template_path) {
			frm.set_read_only();
		} else {
			frm.events.layout(frm);
		}
	},
	published: function (frm) {
		// If current date is before end date,
		// and web page is manually unpublished,
		// set end date to current date.
		if (!frm.doc.published && frm.doc.end_date) {
			var end_date = frappe.datetime.str_to_obj(frappe.datetime.now_datetime());

			// Set date a few seconds in the future to avoid throwing
			// start and end date validation error
			end_date.setSeconds(end_date.getSeconds() + 5)

			frm.set_value("end_date", end_date);
		}
	},

	set_meta_tags(frm) {
		frappe.utils.set_meta_tag(frm.doc.route);
	}
})
