frappe.ui.FilterGroup = class {
	constructor(opts) {
		$.extend(this, opts);
		this.wrapper = this.parent;
		this.filters = [];
		this.make();
		window.fltr = this;
	}

	make() {
		this.wrapper.append(this.get_container_template());
		this.set_events();
	}

	toggle_clear_filter() {
		let clear_filter_button = this.wrapper.find('.clear-filters');

		if (this.filters.length == 0) {
			clear_filter_button.hide();
		} else {
			clear_filter_button.show();
		}
	}

	make_popover() {
		this.init_filter_popover();
		this.set_clear_all_filters_event();
		this.set_popover_events();
	}

	set_clear_all_filters_event() {
		if (!this.filter_x_button) return;

		this.filter_x_button.on("click", () => {
			this.toggle_empty_filters(true);
			if (typeof this.base_list !== "undefined") {
				// It's a list view. Clear all the filters, also the ones in the
				// FilterArea outside this FilterGroup
				this.base_list.filter_area.clear();
			} else {
				// Not a list view, just clear the filters in this FilterGroup
				this.clear_filters();
			}
			this.update_filter_button();
		});
	}

	hide_popover() {
		this.filter_button.popover("hide");
	}

	init_filter_popover() {
		this.filter_button.popover({
			content: this.get_filter_area_template(),
			template: `
				<div class="filter-popover popover">
					<div class="arrow"></div>
					<div class="popover-body popover-content">
					</div>
				</div>
			`,
			html: true,
			trigger: 'manual',
			container: 'body',
			placement: 'bottom',
			offset: '-100px, 0'
		});
	}

	toggle_empty_filters(show) {
		this.wrapper &&
			this.wrapper.find('.empty-filters').toggle(show);
	}

	set_popover_events() {
		$(document.body).on('click', (e) => {
			if (this.wrapper && this.wrapper.is(':visible')) {
				const in_datepicker = $(e.target).is('.datepicker--cell')
					|| $(e.target).closest('.datepicker--nav-title').length !== 0
					|| $(e.target).parents('.datepicker--nav-action').length !== 0;

				if (
					$(e.target).parents('.filter-popover').length === 0
					&& $(e.target).parents('.filter-box').length === 0
					&& this.filter_button.find($(e.target)).length === 0
					&& !$(e.target).is(this.filter_button)
					&& !in_datepicker
				) {
					this.wrapper && this.hide_popover();
				}
			}
		});

		this.filter_button.on('click', () => {
			this.filter_button.popover('toggle');
		});

		this.filter_button.on('shown.bs.popover', () => {
			let hide_empty_filters = this.filters && this.filters.length > 0;

			if (!this.wrapper) {
				this.wrapper = $('.filter-popover');
				if (hide_empty_filters) {
					this.toggle_empty_filters(false);
					this.add_filters_to_popover(this.filters);
				}
				this.set_filter_events();
			}
			this.toggle_empty_filters(false);
			!hide_empty_filters && this.add_filter(this.doctype, 'name');
		});

		this.filter_button.on('hidden.bs.popover', () => {
			this.apply();
		});

		// REDESIGN-TODO: (Temporary) Review and find best solution for this
		frappe.router.on("change", () => {
			if (this.wrapper && this.wrapper.is(":visible")) {
				this.hide_popover();
			}
		});
	}

	add_filters_to_popover(filters) {
		filters.forEach(filter => {
			filter.parent = this.wrapper;
			filter.field = null;
			filter.make();
		});
	}

	apply() {
		this.update_filters();
		this.on_change();
	}

	update_filter_button() {
		const filters_applied = this.filters.length > 0;
		const button_label = filters_applied
			? this.filters.length > 1
				? __("{0} filters", [this.filters.length])
				: __("{0} filter", [this.filters.length])
			: __('Filter');


		this.filter_button
			.toggleClass('btn-default', !filters_applied)
			.toggleClass('btn-primary-light', filters_applied);

		this.filter_button.find('.filter-icon')
			.toggleClass('active', filters_applied);

		this.filter_button.find('.button-label').html(button_label);
	}

	set_filter_events() {
		this.wrapper.find('.add-filter').on('click', () => {
			this.add_filter(this.doctype, 'name')
				.then(this.toggle_clear_filter());

		});
		this.wrapper.find('.clear-filters').on('click', () => {
			this.clear_filters();
			this.on_change();
			this.hide_popover();
		});

		this.wrapper.find(".apply-filters").on("click", () => this.hide_popover());
	}

	add_filters(filters) {
		let promises = [];

		for (const filter of filters) {
			promises.push(() => this.add_filter(...filter));
		}

		promises.push(() => this.toggle_clear_filter());

		return frappe.run_serially(promises);
	}

	add_filter(doctype, fieldname, condition, value, hidden) {
		if (!fieldname) return Promise.resolve();
		// adds a new filter, returns true if filter has been added

		// {}: Add in page filter by fieldname if exists ('=' => 'like')

		if(!this.validate_args(doctype, fieldname)) return false;
		const is_new_filter = arguments.length < 2;
		if (is_new_filter && this.wrapper.find(".new-filter:visible").length) {
			// only allow 1 new filter at a time!
			return Promise.resolve();
		} else {
			let args = [doctype, fieldname, condition, value, hidden];
			const promise = this.push_new_filter(args, is_new_filter);
			return (promise && promise.then) ? promise : Promise.resolve();
		}
	}

	validate_args(doctype, fieldname) {

		if(doctype && fieldname
			&& !frappe.meta.has_field(doctype, fieldname)
			&& !frappe.model.std_fields_list.includes(fieldname)) {

			frappe.throw(__(`Invalid filter: "${[fieldname.bold()]}"`));
			return false;
		}
		return true;
	}

	push_new_filter(args, is_new_filter=false) {
		// args: [doctype, fieldname, condition, value]
		if(this.filter_exists(args)) return;

		// {}: Clear page filter fieldname field

		let filter = this._push_new_filter(...args);

		if (filter && filter.value) {
			filter.setup_state(is_new_filter);
			return filter._filter_value_set; // internal promise
		}
	}

	_push_new_filter(doctype, fieldname, condition, value, hidden = false) {
		let args = {
			parent: this.wrapper,
			parent_doctype: this.doctype,
			doctype: doctype,
			_parent_doctype: this.parent_doctype,
			fieldname: fieldname,
			condition: condition,
			value: value,
			hidden: hidden,
			on_change: (update) => {
				if(update) this.update_filters();
				this.on_change();
			},
			filter_items: (doctype, fieldname) => {
				return !this.filter_exists([doctype, fieldname]);
			}
		};
		let filter = new frappe.ui.Filter(args);
		this.filters.push(filter);
		return filter;
	}

	filter_exists(filter_value) {
		// filter_value of form: [doctype, fieldname, condition, value]
		let exists = false;
		this.filters.filter(f => f.field).map(f => {
			let f_value = f.get_value();
			if (filter_value.length === 2) {
				exists = filter_value[0] === f_value[0] && filter_value[1] === f_value[1];
				return;
			}

			let value = filter_value[3];
			let equal = frappe.utils.arrays_equal;

			if(equal(f_value.slice(0, 4), filter_value.slice(0, 4)) || (Array.isArray(value) && equal(value, f_value[3]))) {
				exists = true;
			}
		});
		return exists;
	}

	get_filters() {
		return this.filters.filter(f => f.field).map(f => {
			return f.get_value();
		});
		// {}: this.list.update_standard_filters(values);
	}

	update_filters() {
		this.filters = this.filters.filter(f => f.field); // remove hidden filters
		this.toggle_clear_filter();
	}

	clear_filters() {
		this.filters.map(f => f.remove(true));
		// {}: Clear page filters, .date-range-picker (called list run())
		this.filters = [];
	}

	get_filter(fieldname) {
		return this.filters.filter(f => {
			return (f.field && f.field.df.fieldname==fieldname);
		})[0];
	}

	get_container_template() {
		return $(`<div class="tag-filters-area">
			<div class="active-tag-filters">
				<button class="btn btn-default btn-xs filter-button text-muted add-filter">
					${__("Add Filter")}
				</button><button class="btn btn-default btn-xs filter-button text-muted clear-filters" style="display: none;">
					${__("Clear Filters")}
				</button>
			</div>
		</div>
		<div class="filter-edit-area"></div>`);
	}
};
