context('Form', () => {
	before(() => {
		cy.login();
		cy.visit('/desk');
		cy.window().its('frappe').then(frappe => {
			frappe.call("frappe.tests.ui_test_helpers.create_contact_records");
		});
	});
	beforeEach(() => {
		cy.visit('/desk');
	});
	it('create a new form', () => {
		cy.visit('/app/todo/new');
		cy.get_field('description', 'Text Editor').type('this is a test todo', {force: true}).wait(200);
		cy.get('.page-title').should('contain', 'Not Saved');
		cy.get('.primary-action').click();
		cy.wait('@form_save').its('response.statusCode').should('eq', 200);

		cy.visit('/app/todo');
		cy.get('.page-head').findByTitle('To Do').should('exist');
		cy.get('.list-row').should('contain', 'this is a test todo');
	});

	it('navigates between documents with child table list filters applied', () => {
		cy.visit('/app/contact');

		cy.clear_filters();
		cy.get('.standard-filter-section [data-fieldname="name"] input').type('Test Form Contact 3').blur();
		cy.click_listview_row_item_with_text('Test Form Contact 3');

		cy.get('#page-Contact .page-head').findByTitle('Test Form Contact 3').should('exist');
		cy.get('.prev-doc').should('be.visible').click();
		cy.get('.msgprint-dialog .modal-body').contains('No further records').should('be.visible');
		cy.hide_dialog();

		cy.get('#page-Contact .page-head').findByTitle('Test Form Contact 3').should('exist');
		cy.get('.next-doc').should('be.visible').click();
		cy.get('.msgprint-dialog .modal-body').contains('No further records').should('be.visible');
		cy.hide_dialog();

		cy.get('#page-Contact .page-head').findByTitle('Test Form Contact 3').should('exist');

		// clear filters
		cy.window().its('frappe').then((frappe) => {
			let list_view = frappe.get_list_view('Contact');
			list_view.filter_area.filter_list.clear_filters();
		});
	});

	it('validates behaviour of Data options validations in child table', () => {
		// test email validations for set_invalid controller
		let website_input = 'website.in';
		let expectBackgroundColor = 'rgb(255, 220, 220)';

		cy.visit('/desk#Form/Contact/New Contact 1');
		cy.get('.frappe-control[data-fieldname="email_ids"]').as('table');
		cy.get('@table').find('button.grid-add-row').click();
		cy.get('.grid-body .rows [data-fieldname="email_id"]').click();
		cy.get('@table').find('input.input-with-feedback.form-control').as('email_input');
		cy.get('@email_input').type(website_input, { waitForAnimations: false });
		cy.fill_field('company_name', 'Test Company');
		cy.get('@email_input').should($div => {
			const style = window.getComputedStyle($div[0]);
			expect(style.backgroundColor).to.equal(expectBackgroundColor);
		});
	});
});
