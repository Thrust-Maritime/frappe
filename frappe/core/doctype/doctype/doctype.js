// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// -------------
// Menu Display
// -------------

// $(cur_frm.wrapper).on("grid-row-render", function(e, grid_row) {
// 	if(grid_row.doc && grid_row.doc.fieldtype=="Section Break") {
// 		$(grid_row.row).css({"font-weight": "bold"});
// 	}
// })

frappe.ui.form.on('DocType', {
	refresh: function(frm) {
		if(frappe.session.user !== "Administrator" || !frappe.boot.developer_mode) {
			if(frm.is_new()) {
				frm.set_value("custom", 1);
			}
			frm.toggle_enable("custom", 0);
			frm.toggle_enable("beta", 0);
		}

		if (!frm.is_new() && !frm.doc.istable) {
			if (frm.doc.issingle) {
				frm.add_custom_button(__('Go to {0}', [frm.doc.name]), () => {
					frappe.set_route('Form', frm.doc.name);
				});
			} else {
				frm.add_custom_button(__('Go to {0} List', [frm.doc.name]), () => {
					frappe.set_route('List', frm.doc.name, 'List');
				});
			}
		}

		const customize_form_link = "<a href='/app/customize-form'>Customize Form</a>";
		if(!frappe.boot.developer_mode && !frm.doc.custom) {
			// make the document read-only
			frm.set_read_only();
			frm.dashboard.add_comment(__("DocTypes can not be modified, please use {0} instead", [customize_form_link]), "blue", true);
		} else if (frappe.boot.developer_mode) {
			let msg = __("This site is running in developer mode. Any change made here will be updated in code.");
			msg += "<br>";
			msg += __("If you just want to customize for your site, use {0} instead.", [customize_form_link]);
			frm.dashboard.add_comment(msg, "yellow");
		}

		if(frm.is_new()) {
			if (!(frm.doc.permissions && frm.doc.permissions.length)) {
				frm.add_child('permissions', {role: 'System Manager'});
			}
		} else {
			frm.toggle_enable("engine", 0);
		}

		// set label for "In List View" for child tables
		frm.get_docfield('fields', 'in_list_view').label = frm.doc.istable ?
			__('In Grid View') : __('In List View');

		frm.events.autoname(frm);
	},

	before_save: function(frm) {
		frappe.flags.update_bootinfo = frm.is_new();
	},

	after_save: function(frm) {
		if (frappe.flags.update_bootinfo) {
			frappe.boot.user.can_create.push(frm.doc.name);
			frappe.flags.update_bootinfo = false;
		}
	},

	autoname(frm) {
		frm.set_df_property('fields', 'reqd', frm.doc.autoname !== 'Prompt');
	}
})
