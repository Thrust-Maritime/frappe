// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.breadcrumbs = {
	all: {},

	preferred: {
		"File": "",
		"Dashboard": "Customization",
		"Dashboard Chart": "Customization",
		"Dashboard Chart Source": "Customization",
	},

	module_map: {
		'Core': 'Settings',
		'Email': 'Settings',
		'Custom': 'Settings',
		'Workflow': 'Settings',
		'Printing': 'Settings',
		'Automation': 'Settings',
		'Setup': 'Settings',
	},

	set_doctype_module: function(doctype, module) {
		localStorage["preferred_breadcrumbs:" + doctype] = module;
	},

	get_doctype_module: function(doctype) {
		return localStorage["preferred_breadcrumbs:" + doctype];
	},

	add: function(module, doctype, type) {
		let obj;
		if (typeof module === 'object') {
			obj = module;
		} else {
			obj = {
				module:module,
				doctype:doctype,
				type:type
			}
		}

		frappe.breadcrumbs.all[frappe.breadcrumbs.current_page()] = obj;
		frappe.breadcrumbs.update();
	},

	current_page: function() {
		return frappe.get_route_str();
	},

	update: function() {
		var breadcrumbs = frappe.breadcrumbs.all[frappe.breadcrumbs.current_page()];

		if(!frappe.visible_modules) {
			frappe.visible_modules = $.map(frappe.boot.allowed_modules, (m) => {
				return m.module_name;
			});
		}

		var $breadcrumbs = $("#navbar-breadcrumbs").empty();

		if(!breadcrumbs) {
			$("body").addClass("no-breadcrumbs");
			return;
		}

		if (breadcrumbs.type === 'Custom') {
			this.set_custom_breadcrumbs(breadcrumbs);
		} else {
			// workspace
			this.set_workspace_breadcrumb(breadcrumbs);

			// form / print
			let view = frappe.get_route()[0];
			view = view ? view.toLowerCase() : null;
			if (breadcrumbs.doctype && ["print", "form"].includes(view)) {
				this.set_list_breadcrumb(breadcrumbs);
				this.set_form_breadcrumb(breadcrumbs, view);
			} else if (breadcrumbs.doctype && view === 'list') {
				this.set_list_breadcrumb(breadcrumbs);
			} else if (breadcrumbs.doctype && view == 'dashboard-view') {
				this.set_list_breadcrumb(breadcrumbs);
				this.set_dashboard_breadcrumb(breadcrumbs);
			}
		}

		// get preferred module for breadcrumbs, based on sent via module
		var from_module = frappe.breadcrumbs.get_doctype_module(breadcrumbs.doctype);

		if(from_module) {
			breadcrumbs.module = from_module;
		} else if(frappe.breadcrumbs.preferred[breadcrumbs.doctype]!==undefined) {
			// get preferred module for breadcrumbs
			breadcrumbs.module = frappe.breadcrumbs.preferred[breadcrumbs.doctype];
		}

		if(breadcrumbs.module) {
			if (frappe.breadcrumbs.module_map[breadcrumbs.module]) {
				breadcrumbs.module = frappe.breadcrumbs.module_map[breadcrumbs.module];
			}

			if(frappe.get_module(breadcrumbs.module)) {
				// if module access exists
				var module_info = frappe.get_module(breadcrumbs.module),
					icon = module_info && module_info.icon,
					label = module_info ? module_info.label : breadcrumbs.module;


				if(module_info && !module_info.blocked && frappe.visible_modules.includes(module_info.module_name)) {
					$(repl('<li><a href="#modules/%(module)s">%(label)s</a></li>',
						{ module: breadcrumbs.module, label: __(label) }))
						.appendTo($breadcrumbs);
				}
			}
		}
		if(breadcrumbs.doctype && frappe.get_route()[0]==="Form") {
			if(breadcrumbs.doctype==="User"
				|| frappe.get_doc('DocType', breadcrumbs.doctype).issingle) {
				// no user listview for non-system managers and single doctypes
			} else {
				var route;
				if(frappe.boot.treeviews.indexOf(breadcrumbs.doctype) !== -1) {
					var view = frappe.model.user_settings[breadcrumbs.doctype].last_view || 'Tree';
					route = view + '/' + breadcrumbs.doctype;
				} else {
					route = 'List/' + breadcrumbs.doctype;
				}
				$(repl('<li><a href="#%(route)s">%(label)s</a></li>',
					{route: route, label: __(breadcrumbs.doctype)}))
					.appendTo($breadcrumbs);
			}
			$(`<li><a href="/app/${route}">${__(doctype)}</a></li>`)
				.appendTo(this.$breadcrumbs);
		}
	},

	set_form_breadcrumb(breadcrumbs, view) {
		const doctype = breadcrumbs.doctype;
		const docname = frappe.get_route().slice(2).join("/");
		let form_route = `/app/${frappe.router.slug(doctype)}/${docname}`;
		$(`<li><a href="${form_route}">${__(docname)}</a></li>`)
			.appendTo(this.$breadcrumbs);

		if (view === "form") {
			let last_crumb = this.$breadcrumbs.find('li').last();
			last_crumb.addClass('disabled');
			last_crumb.css("cursor", "copy");
			last_crumb.click((event) => {
				event.stopImmediatePropagation();
				frappe.utils.copy_to_clipboard(last_crumb.text());
			});
		}

		$("body").removeClass("no-breadcrumbs");
	},

	set_dashboard_breadcrumb(breadcrumbs) {
		const doctype = breadcrumbs.doctype;
		const docname = frappe.get_route()[1];
		let dashboard_route = `/app/${frappe.router.slug(doctype)}/${docname}`;
		$(`<li><a href="${dashboard_route}">${__(docname)}</a></li>`)
			.appendTo(this.$breadcrumbs);
	},

	setup_modules() {
		if (!frappe.visible_modules) {
			frappe.visible_modules = $.map(frappe.boot.allowed_workspaces, (m) => {
				return m.module;
			});
		}
	},

	rename(doctype, old_name, new_name) {
		var old_route_str = ["Form", doctype, old_name].join("/");
		var new_route_str = ["Form", doctype, new_name].join("/");
		frappe.breadcrumbs.all[new_route_str] = frappe.breadcrumbs.all[old_route_str];
		delete frappe.breadcrumbs.all[old_route_str];
	}

}

