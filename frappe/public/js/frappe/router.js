// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// route urls to their virtual pages

// re-route map (for rename)
frappe.provide('frappe.views');
frappe.re_route = {"#login": ""};
frappe.route_titles = {};
frappe.route_flags = {};
frappe.route_history = [];
frappe.view_factory = {};
frappe.view_factories = [];
frappe.route_options = null;

frappe.route = function() {

	// Application is not yet initiated
	if (!frappe.app) return;

	if(frappe.re_route[window.location.hash] !== undefined) {
		// after saving a doc, for example,
		// "New DocType 1" and the renamed "TestDocType", both exist in history
		// now if we try to go back,
		// it doesn't allow us to go back to the one prior to "New DocType 1"
		// Hence if this check is true, instead of changing location hash,
		// we just do a back to go to the doc previous to the "New DocType 1"
		var re_route_val = frappe.get_route_str(frappe.re_route[window.location.hash]);
		var cur_route_val = frappe.get_route_str(frappe._cur_route);
		if (decodeURIComponent(re_route_val) === decodeURIComponent(cur_route_val)) {
			window.history.back();
			return;
		} else {
			window.location.hash = frappe.re_route[window.location.hash];
		}
	}

	frappe._cur_route = window.location.hash;

// routing v2, capture all clicks so that the target is managed with push-state
$('body').on('click', 'a', function(e) {
	let override = (route) => {
		e.preventDefault();
		frappe.set_route(route);
		return false;
	};

	const target_element = e.currentTarget;
	const href = target_element.getAttribute("href");
	const is_on_same_host = target_element.hostname === window.location.hostname;

	// click handled, but not by href
	if (
		target_element.getAttribute("onclick") || // has a handler
		e.ctrlKey ||
		e.metaKey || // open in a new tab
		href === "#" // hash is home
	) {
		return;
	}

	frappe.route_history.push(route);

	if (href && href.startsWith('#')) {
		// target startswith "#", this is a v1 style route, so remake it.
		return override(target_element.hash);
	}

	if (is_on_same_host && frappe.router.is_app_route(target_element.pathname)) {
		// target has "/app, this is a v2 style route.
		return override(target_element.pathname + target_element.hash);
	}

});

frappe.router = {
	current_route: null,
	routes: {},
	factory_views: ['form', 'list', 'report', 'tree', 'print', 'dashboard'],
	list_views: ['list', 'kanban', 'report', 'calendar', 'tree', 'gantt', 'dashboard', 'image', 'inbox'],
	layout_mapped: {},

	is_app_route(path) {
		// desk paths must begin with /app or doctype route
		if (path.substr(0, 1) === '/') path = path.substr(1);
		path = path.split('/');
		if (path[0]) {
			return path[0]==='app';
		}
	},

	setup() {
		// setup the route names by forming slugs of the given doctypes
		for (let doctype of frappe.boot.user.can_read) {
			this.routes[this.slug(doctype)] = {doctype: doctype};
		}
		if (frappe.boot.doctype_layouts) {
			for (let doctype_layout of frappe.boot.doctype_layouts) {
				this.routes[this.slug(doctype_layout.name)] = {doctype: doctype_layout.document_type, doctype_layout: doctype_layout.name };
			}
		}
	},

	route() {
		// resolve the route from the URL or hash
		// translate it so the objects are well defined
		// and render the page as required

		if (!frappe.app) return;

		let sub_path = this.get_sub_path();
		if (this.re_route(sub_path)) return;

		this.current_sub_path = sub_path;
		this.current_route = this.parse();
		this.set_history(sub_path);
		this.render();
		this.set_title(sub_path);
		this.trigger('change');
	},

	parse(route) {
		route = this.get_sub_path_string(route).split('/');
		if (!route) return [];
		route = $.map(route, this.decode_component);
		this.set_route_options_from_url(route);
		return this.convert_to_standard_route(route);
	},

	convert_to_standard_route(route) {
		// /app/settings = ["Workspaces", "Settings"]
		// /app/user = ["List", "User"]
		// /app/user/view/report = ["List", "User", "Report"]
		// /app/user/view/tree = ["Tree", "User"]
		// /app/user/user-001 = ["Form", "User", "user-001"]
		// /app/user/user-001 = ["Form", "User", "user-001"]
		// /app/event/view/calendar/default = ["List", "Event", "Calendar", "Default"]

		if (frappe.workspaces[route[0]]) {
			// workspace
			route = ['Workspaces', frappe.workspaces[route[0]].name];
		} else if (this.routes[route[0]]) {
			// route
			route = this.set_doctype_route(route);
		}

		return route;
	},

	set_doctype_route(route) {
		let doctype_route = this.routes[route[0]];
		// doctype route
		if (route[1]) {
			if (route[2] && route[1]==='view') {
				route = this.get_standard_route_for_list(route, doctype_route);
			} else {
				let docname = route[1];
				if (route.length > 2) {
					docname = route.slice(1).join('/');
				}
				route = ['Form', doctype_route.doctype, docname];
			}
		} else if (frappe.model.is_single(doctype_route.doctype)) {
			route = ['Form', doctype_route.doctype, doctype_route.doctype];
		} else {
			route = ['List', doctype_route.doctype, 'List'];
		}

		if (doctype_route.doctype_layout) {
			// set the layout
			this.doctype_layout = doctype_route.doctype_layout;
		}

		return route;
	},

	get_standard_route_for_list(route, doctype_route) {
		let standard_route;
		if (route[2].toLowerCase()==='tree') {
			standard_route = ['Tree', doctype_route.doctype];
		} else {
			standard_route = ['List', doctype_route.doctype, frappe.utils.to_title_case(route[2])];
			// calendar / kanban / dashboard / folder
			if (route[3]) standard_route.push(...route.slice(3, route.length));
		}
		return standard_route;
	},

	set_history() {
		frappe.route_history.push(this.current_route);
		frappe.ui.hide_open_dialog();
	},

	render() {
		if (this.current_route[0]) {
			this.render_page();
		} else {
			// Show home
			frappe.views.pageview.show('');
		}

		if (route[1] && frappe.views[title_cased_route + "Factory"]) {
			// has a view generator, generate!
			if(!frappe.view_factory[title_cased_route]) {
				frappe.view_factory[title_cased_route] = new frappe.views[title_cased_route + "Factory"]();
			}

			frappe.view_factory[title_cased_route].show();
		} else {
			// show page
			const route_name = frappe.utils.xss_sanitise(route[0]);
			if (frappe.views.pageview) {
				frappe.views.pageview.show(route_name);
			}
		}
	} else {
		// Show desk
		frappe.views.pageview.show('');
	}


	set_title(sub_path) {
		if (frappe.route_titles[sub_path]) {
			frappe.utils.set_title(frappe.route_titles[sub_path]);
		}
	},

	set_route() {
		// set the route (push state) with given arguments
		// example 1: frappe.set_route('a', 'b', 'c');
		// example 2: frappe.set_route(['a', 'b', 'c']);
		// example 3: frappe.set_route('a/b/c');
		let route = Array.from(arguments);

		return new Promise(resolve => {
			route = this.get_route_from_arguments(route);
			route = this.convert_from_standard_route(route);
			let sub_path = this.make_url(route);
			// replace each # occurrences in the URL with encoded character except for last
			// sub_path = sub_path.replace(/[#](?=.*[#])/g, "%23");
			this.push_state(sub_path);

			setTimeout(() => {
				frappe.after_ajax && frappe.after_ajax(() => {
					resolve();
				});
			}, 100);
		}).finally(() => frappe.route_flags = {});
	},

	get_route_from_arguments(route) {
		if (route.length===1 && $.isArray(route[0])) {
			// called as frappe.set_route(['a', 'b', 'c']);
			route = route[0];
		}

	if(window.mixpanel) {
		window.mixpanel.track(route.slice(0, 2).join(' '));
	}
}

frappe.get_route = function(route) {
	// for app
	route = frappe.get_raw_route_str(route).split('/');
	route = $.map(route, frappe._decode_str);
	var parts = null;
	var doc_name = route[route.length - 1];
	// if the last part contains ? then check if it is valid query string
	if(doc_name.indexOf("?") < doc_name.indexOf("=")){
		parts = doc_name.split("?");
		route[route.length - 1] = parts[0];
	} else {
		parts = doc_name;
	}
	if (parts.length > 1) {
		var query_params = frappe.utils.get_query_params(parts[1]);
		frappe.route_options = $.extend(frappe.route_options || {}, query_params);
	}

	// backward compatibility
	if (route && route[0]==='Module') {
		frappe.set_route('modules', route[1]);
		return false;
	}

	return route;
}

frappe.get_prev_route = function() {
	if(frappe.route_history && frappe.route_history.length > 1) {
		return frappe.route_history[frappe.route_history.length - 2];
	} else {
		return [];
	}
}

frappe._decode_str = function(r) {
	try {
		return decodeURIComponent(r);
	} catch(e) {
		if (e instanceof URIError) {
			return r;
		} else {
			throw e;
		}
	}
}

frappe.get_raw_route_str = function(route) {
	if(!route)
		route = window.location.hash;

	if(route.substr(0,1)=='#') route = route.substr(1);
	if(route.substr(0,1)=='!') route = route.substr(1);

	return route;
}

frappe.get_route_str = function(route) {
	var rawRoute = frappe.get_raw_route_str(route);
	route = $.map(rawRoute.split('/'), frappe._decode_str).join('/');

	return route;
}

frappe.set_route = function() {
	return new Promise(resolve => {
		var params = arguments;
		if(params.length===1 && $.isArray(params[0])) {
			params = params[0];
		}
		var route = $.map(params, function(a) {
			if($.isPlainObject(a)) {
				frappe.route_options = a;
				return null;
			} else {
				a = encodeURIComponent(String(a));
				return a;
			}
		}).join('/');

		window.location.hash = route;

	push_state(url) {
		// change the URL and call the router
		if (window.location.pathname !== url) {

			// push/replace state so the browser looks fine
			const method = frappe.route_flags.replace_route ? "replaceState" : "pushState";
			history[method](null, null, url);

			// now process the route
			this.route();
		}
	},

	get_sub_path_string(route) {
		// return clean sub_path from hash or url
		// supports both v1 and v2 routing
		if (!route) {
			route = window.location.pathname;
			if (route.includes('app#')) {
				// to support v1
				route = window.location.hash;
			}
		}

		return this.strip_prefix(route);
	},

	strip_prefix(route) {
		if (route.substr(0, 1)=='/') route = route.substr(1); // for /app/sub
		if (route.startsWith('app/')) route = route.substr(4); // for desk/sub
		if (route == 'app') route = route.substr(4); // for /app
		if (route.substr(0, 1)=='/') route = route.substr(1);
		if (route.substr(0, 1)=='#') route = route.substr(1);
		if (route.substr(0, 1)=='!') route = route.substr(1);
		return route;
	},

	get_sub_path(route) {
		var sub_path = this.get_sub_path_string(route);
		route = $.map(sub_path.split('/'), this.decode_component).join('/');

		return route;
	},

	set_route_options_from_url(route) {
		// set query parameters as frappe.route_options
		var last_part = route[route.length - 1];
		if (last_part.indexOf("?") < last_part.indexOf("=")) {
			// has ? followed by =
			let parts = last_part.split("?");

			// route should not contain string after ?
			route[route.length - 1] = parts[0];

			let query_params = frappe.utils.get_query_params(parts[1]);
			frappe.route_options = $.extend(frappe.route_options || {}, query_params);
		}
	},

	decode_component(r) {
		try {
			return decodeURIComponent(r);
		} catch (e) {
			if (e instanceof URIError) {
				// legacy: not sure why URIError is ignored.
				return r;
			} else {
				throw e;
			}
		}
	},

	slug(name) {
		return name.toLowerCase().replace(/ /g, '-');
	}
};

// global functions for backward compatibility
frappe.get_route = () => frappe.router.current_route;
frappe.get_route_str = () => frappe.router.current_route.join('/');
frappe.set_route = function() {
	return frappe.router.set_route.apply(frappe.router, arguments);
};

frappe.get_prev_route = function() {
	if (frappe.route_history && frappe.route_history.length > 1) {
		return frappe.route_history[frappe.route_history.length - 2];
	} else {
		return [];
	}
};

frappe.set_re_route = function() {
	var tmp = window.location.hash;
	frappe.set_route.apply(null, arguments);
	frappe.re_route[tmp] = window.location.hash;
};

frappe.has_route_options = function() {
	return Boolean(Object.keys(frappe.route_options || {}).length);
}

frappe._cur_route = null;

$(window).on('hashchange', function() {
	// save the title
	frappe.route_titles[frappe._cur_route] = frappe._original_title || document.title;

	if(window.location.hash==frappe._cur_route)
		return;

	// hide open dialog
	if(window.cur_dialog) {
		if (!cur_dialog.minimizable) {
			cur_dialog.hide();
		} else if (!cur_dialog.is_minimized) {
			cur_dialog.toggle_minimize();
		}
	}

	frappe.route();

	frappe.route.trigger('change');
});

frappe.utils.make_event_emitter(frappe.route);
