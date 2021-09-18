context('Recorder', () => {
	before(() => {
		cy.login();
	});

	it('Navigate to Recorder', () => {
		cy.visit('/desk');
		cy.awesomebar('recorder');
		cy.findByTitle('Recorder').should('exist');
		cy.url().should('include', '/recorder/detail');
	});

	it('Recorder Empty State', () => {
		cy.findByTitle('Recorder').should('exist');

		cy.get('.indicator').should('contain', 'Inactive').should('have.class', 'red');

		cy.findByRole('button', {name: 'Start'}).should('exist');
		cy.findByRole('button', {name: 'Clear'}).should('exist');

		cy.get('.msg-box').should('contain', 'Inactive');
		cy.findByRole('button', {name: 'Start Recording'}).should('exist');
	});

	it('Recorder Start', () => {
		cy.findByRole('button', {name: 'Start'}).click();
		cy.get('.indicator-pill').should('contain', 'Active').should('have.class', 'green');

		cy.get('.msg-box').should('contain', 'No Requests');

		cy.server();
		cy.visit('/desk#List/DocType/List');
		cy.route('POST', '/api/method/frappe.desk.reportview.get').as('list_refresh');
		cy.wait('@list_refresh');

		cy.get('.title-text').should('contain', 'DocType');
		cy.get('.list-count').should('contain', '20 of ');

		cy.visit('/app/recorder');
		cy.findByTitle('Recorder').should('exist');
		cy.get('.result-list').should('contain', '/api/method/frappe.desk.reportview.get');

		cy.get('#page-recorder .primary-action').should('contain', 'Stop').click();
		cy.wait(500);
		cy.get('#page-recorder .btn-secondary').should('contain', 'Clear').click();
		cy.get('.msg-box').should('contain', 'Inactive');
	});

	it('Recorder View Request', () => {
		cy.findByRole('button', {name: 'Start'}).click();

		cy.server();
		cy.visit('/desk#List/DocType/List');
		cy.route('POST', '/api/method/frappe.desk.reportview.get').as('list_refresh');
		cy.wait('@list_refresh');

		cy.get('.title-text').should('contain', 'DocType');
		cy.get('.list-count').should('contain', '20 of ');

		cy.visit('/desk#recorder');

		cy.contains('.list-row-container span', 'frappe.desk.reportview.get').click();

		cy.location('hash').should('contain', '#recorder/request/');
		cy.get('form').should('contain', 'frappe.desk.reportview.get');

		cy.get('#page-recorder .primary-action').should('contain', 'Stop').click();
		cy.wait(200);
		cy.get('#page-recorder .btn-secondary').should('contain', 'Clear').click();
		cy.location('hash').should('eq', '#recorder');
	});
});