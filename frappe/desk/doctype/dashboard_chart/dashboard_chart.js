// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.provide('frappe.dashboards.chart_sources');

frappe.ui.form.on('Dashboard Chart', {
	setup: function(frm) {
		// fetch timeseries from source
		frm.add_fetch('source', 'timeseries', 'timeseries');
	},

	refresh: function(frm) {
		frm.chart_filters = null;
		frm.set_df_property("filters_section", "hidden", 1);
		frm.set_df_property("dynamic_filters_section", "hidden", 1);

		frm.trigger('set_parent_document_type');
		frm.trigger('set_time_series');
		frm.set_query('document_type', function() {
			return {
				filters: {
					'issingle': false
				}
			}
		});
		frm.trigger('update_options');
	},

	source: function(frm) {
		frm.trigger("show_filters");
	},

	chart_type: function(frm) {
		// set timeseries based on chart type
		if (['Count', 'Average', 'Sum'].includes(frm.doc.chart_type)) {
			frm.set_value('timeseries', 1);
		} else {
			frm.set_value('timeseries', 0);
		}
		frm.set_value('document_type', '');
	},

	document_type: function(frm) {
		// update `based_on` options based on date / datetime fields
		frm.set_value('source', '');
		frm.set_value('based_on', '');
		frm.set_value('value_based_on', '');
		frm.set_value('parent_document_type', '');
		frm.set_value('filters_json', '[]');
		frm.set_value('dynamic_filters_json', '[]');
		frm.trigger('update_options');
		frm.trigger('set_parent_document_type');
	},

	report_name: function(frm) {
		frm.set_value('x_field', '');
		frm.set_value('y_axis', []);
		frm.set_df_property('x_field', 'options', []);
		frm.set_value('filters_json', '{}');
		frm.set_value('dynamic_filters_json', '{}');
		frm.set_value('use_report_chart', 0);
		frm.trigger('set_chart_report_filters');
	},

	set_chart_report_filters: function(frm) {
		let report_name = frm.doc.report_name;

		if (report_name) {
			if (frm.doc.filters_json.length > 2) {
				frm.trigger('show_filters');
				frm.trigger('set_chart_field_options');
			} else {
				frappe.report_utils.get_report_filters(report_name).then(filters => {
					if (filters) {
						frm.chart_filters = filters;
						let filter_values = frappe.report_utils.get_filter_values(filters);
						frm.set_value('filters_json', JSON.stringify(filter_values));
					}
					frm.trigger('show_filters');
					frm.trigger('set_chart_field_options');
				});
			}

		}
	},

	use_report_chart: function(frm) {
		!frm.doc.use_report_chart && frm.trigger('set_chart_field_options');
	},

	set_chart_field_options: function(frm) {
		let filters = frm.doc.filters_json.length > 2 ? JSON.parse(frm.doc.filters_json) : null;
		if (frm.doc.dynamic_filters_json && frm.doc.dynamic_filters_json.length > 2) {
			filters = frappe.dashboard_utils.get_all_filters(frm.doc);
		}
		frappe.xcall(
			'frappe.desk.query_report.run',
			{
				report_name: frm.doc.report_name,
				filters: filters,
				ignore_prepared_report: 1
			}
		).then(data => {
			frm.report_data = data;
			let report_has_chart = Boolean(data.chart);

			frm.set_df_property('use_report_chart', 'hidden', !report_has_chart);

			if (!frm.doc.use_report_chart) {
				if (data.result.length) {
					frm.field_options = frappe.report_utils.get_field_options_from_report(data.columns, data);
					frm.set_df_property('x_field', 'options', frm.field_options.non_numeric_fields);
					if (!frm.field_options.numeric_fields.length) {
						frappe.msgprint(__("Report has no numeric fields, please change the Report Name"));
					} else {
						let y_field_df = frappe.meta.get_docfield('Dashboard Chart Field', 'y_field', frm.doc.name);
						y_field_df.options = frm.field_options.numeric_fields;
					}
				} else {
					frappe.msgprint(__('Report has no data, please modify the filters or change the Report Name'));
				}
			} else {
				frm.set_value('use_report_chart', 1);
				frm.set_df_property('use_report_chart', 'hidden', false);
			}
		});
	},

	timespan: function(frm) {
		const time_interval_options = {
			"Select Date Range": ["Quarterly", "Monthly", "Weekly", "Daily"],
			"Last Year": ["Quarterly", "Monthly", "Weekly", "Daily"],
			"Last Quarter": ["Monthly", "Weekly", "Daily"],
			"Last Month": ["Weekly", "Daily"],
			"Last Week": ["Daily"]
		};
		if (frm.doc.timespan) {
			frm.set_df_property('time_interval', 'options', time_interval_options[frm.doc.timespan]);
		}
	},

	update_options: function(frm) {
		let doctype = frm.doc.document_type;
		let date_fields = [
			{label: __('Created On'), value: 'creation'},
			{label: __('Last Modified On'), value: 'modified'}
		];
		let value_fields = [];
		let group_by_fields = [];
		let aggregate_function_fields = [];
		let update_form = function() {
			// update select options
			frm.set_df_property('based_on', 'options', date_fields);
			frm.set_df_property('value_based_on', 'options', value_fields);
			frm.set_df_property('group_by_based_on', 'options', group_by_fields);
			frm.set_df_property('aggregate_function_based_on', 'options', aggregate_function_fields);
			frm.trigger("show_filters");
		}


		if (doctype) {
			frappe.model.with_doctype(doctype, () => {
				// get all date and datetime fields
				frappe.get_meta(doctype).fields.map(df => {
					if (['Date', 'Datetime'].includes(df.fieldtype)) {
						date_fields.push({label: df.label, value: df.fieldname});
					}
					if (['Int', 'Float', 'Currency', 'Percent', 'Duration'].includes(df.fieldtype)) {
						value_fields.push({label: df.label, value: df.fieldname});
						aggregate_function_fields.push({label: df.label, value: df.fieldname});
					}
					if (['Link', 'Select'].includes(df.fieldtype)) {
						group_by_fields.push({label: df.label, value: df.fieldname});
					}
				});
				update_form();
			});
		} else {
			// update select options
			update_form();
		}

	},

	show_filters: function(frm) {
		if (frm.chart_filters && frm.chart_filters.length) {
			frm.trigger('render_filters_table');
		} else {
			if (frm.doc.chart_type==='Custom') {
				if (frm.doc.source) {
					frappe.xcall('frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config', {name: frm.doc.source})
						.then(config => {
							frappe.dom.eval(config);
							frm.chart_filters = frappe.dashboards.chart_sources[frm.doc.source].filters;
							frm.trigger('render_filters_table');
						});
				} else {
					frm.chart_filters = [];
					frm.trigger('render_filters_table');
				}
			} else {
				// standard filters
				if (frm.doc.document_type) {
					frappe.model.with_doctype(frm.doc.document_type, () => {
						frm.chart_filters = [];
						frappe.get_meta(frm.doc.document_type).fields.map(df => {
							if (['Link', 'Select'].includes(df.fieldtype)) {
								let _df = copy_dict(df);

								// nothing is mandatory
								_df.reqd = 0;
								_df.default = null;
								_df.depends_on = null;
								_df.read_only = 0;
								_df.permlevel = 1;
								_df.hidden = 0;

								frm.chart_filters.push(_df);
							}
						});
						frm.trigger('render_filters_table');
					});
				}
			}

		}
	},

	render_filters_table: function(frm) {
		frm.set_df_property("filters_section", "hidden", 0);
		let fields = frm.chart_filters;

		let wrapper = $(frm.get_field('filters_json').wrapper).empty();
		let table = $(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
			<thead>
				<tr>
					<th style="width: 50%">${__('Filter')}</th>
					<th>${__('Value')}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);
		$(`<p class="text-muted small">${__("Click table to edit")}</p>`).appendTo(wrapper);

		let filters = JSON.parse(frm.doc.filters_json || '{}');
		var filters_set = false;
		fields.map(f => {
			if (filters[f.fieldname]) {
				const filter_row = $(`<tr><td>${f.label}</td><td>${filters[f.fieldname] || ""}</td></tr>`);
				table.find('tbody').append(filter_row);
				filters_set = true;
			}
		});

		if (!filters_set) {
			const filter_row = $(`<tr><td colspan="2" class="text-muted text-center">
				${__("Click to Set Filters")}</td></tr>`);
			table.find('tbody').append(filter_row);
		}

		table.on('click', () => {
			let dialog = new frappe.ui.Dialog({
				title: __('Set Filters'),
				fields: fields,
				primary_action: function() {
					let values = this.get_values();
					if(values) {
						this.hide();
						frm.set_value('filters_json', JSON.stringify(values));
						frm.trigger('show_filters');
					}
				},
				primary_action_label: "Set"
			});
			frappe.dashboards.filters_dialog = dialog;

			if (is_document_type) {
				frm.filter_group = new frappe.ui.FilterGroup({
					parent: dialog.get_field('filter_area').$wrapper,
					doctype: frm.doc.document_type,
					parent_doctype: frm.doc.parent_document_type,
					on_change: () => {},
				});

				frm.filter_group.add_filters_to_filter_group(filters);
			}

			dialog.show();
			dialog.set_values(filters);
			frappe.dashboards.filters_dialog = dialog;
		});
	},

	render_dynamic_filters_table(frm) {
		frm.set_df_property("dynamic_filters_section", "hidden", 0);

		let is_document_type = frm.doc.chart_type !== 'Report'
			&& frm.doc.chart_type !== 'Custom';

		let wrapper = $(frm.get_field('dynamic_filters_json').wrapper).empty();

		frm.dynamic_filter_table = $(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
			<thead>
				<tr>
					<th style="width: 20%">${__('Filter')}</th>
					<th style="width: 20%">${__('Condition')}</th>
					<th>${__('Value')}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);

		frm.dynamic_filters = frm.doc.dynamic_filters_json && frm.doc.dynamic_filters_json.length > 2
			? JSON.parse(frm.doc.dynamic_filters_json)
			: null;

		frm.trigger('set_dynamic_filters_in_table');

		let filters = JSON.parse(frm.doc.filters_json || '[]');

		let fields = frappe.dashboard_utils.get_fields_for_dynamic_filter_dialog(
			is_document_type, filters, frm.dynamic_filters
		);

		frm.dynamic_filter_table.on('click', () => {
			let dialog = new frappe.ui.Dialog({
				title: __('Set Dynamic Filters'),
				fields: fields,
				primary_action: () => {
					let values = dialog.get_values();
					dialog.hide();
					let dynamic_filters = [];
					for (let key of Object.keys(values)) {
						if (is_document_type) {
							let [doctype, fieldname] = key.split(':');
							dynamic_filters.push([doctype, fieldname, '=', values[key]]);
						}
					}

					if (is_document_type) {
						frm.set_value('dynamic_filters_json', JSON.stringify(dynamic_filters));
					} else {
						frm.set_value('dynamic_filters_json', JSON.stringify(values));
					}
					frm.trigger('set_dynamic_filters_in_table');
				},
				primary_action_label: "Set"
			});

			dialog.show();
			dialog.set_values(frm.dynamic_filters);
		});
	},

	set_dynamic_filters_in_table: function(frm) {
		frm.dynamic_filters =  frm.doc.dynamic_filters_json && frm.doc.dynamic_filters_json.length > 2
			? JSON.parse(frm.doc.dynamic_filters_json)
			: null;

		if (!frm.dynamic_filters) {
			const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
				${__("Click to Set Dynamic Filters")}</td></tr>`);
			frm.dynamic_filter_table.find('tbody').html(filter_row);
		} else {
			let filter_rows = '';
			if ($.isArray(frm.dynamic_filters)) {
				frm.dynamic_filters.forEach(filter => {
					filter_rows +=
						`<tr>
							<td>${filter[1]}</td>
							<td>${filter[2] || ""}</td>
							<td>${filter[3]}</td>
						</tr>`;
				});
			} else {
				let condition = '=';
				for (let [key, val] of Object.entries(frm.dynamic_filters)) {
					filter_rows +=
						`<tr>
							<td>${key}</td>
							<td>${condition}</td>
							<td>${val || ""}</td>
						</tr>`
					;
				}
			}

			frm.dynamic_filter_table.find('tbody').html(filter_rows);
		}
	},

	set_parent_document_type: async function(frm) {
		let document_type = frm.doc.document_type;
		let doc_is_table = document_type &&
			(await frappe.db.get_value('DocType', document_type, 'istable')).message.istable;

		frm.set_df_property('parent_document_type', 'hidden', !doc_is_table);

		if (document_type && doc_is_table) {
			let parent = await frappe.db.get_list('DocField', {
				filters: {
					'fieldtype': 'Table',
					'options': document_type
				},
				fields: ['parent']
			});

			parent && frm.set_query('parent_document_type', function() {
				return {
					filters: {
						"name": ['in', parent.map(({ parent }) => parent)]
					}
				};
			});

			if (parent.length === 1) {
				frm.set_value('parent_document_type', parent[0].parent);
			}
		}
	}
});


