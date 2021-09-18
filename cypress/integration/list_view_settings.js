context('List View Settings', () => {
	beforeEach(() => {
		cy.login();
		cy.visit('/desk');
	});
	it('Default settings', () => {
		cy.visit('/desk#List/DocType/List');
		cy.get('.list-count').should('contain', "20 of");
		cy.get('.sidebar-stat').should('contain', "Tags");
	});
	it('disable count and sidebar stats then verify', () => {
		cy.visit('/desk#List/DocType/List');
		cy.get('.list-count').should('contain', "20 of");
		cy.get('button').contains('Menu').click();
		cy.get('.dropdown-menu li').filter(':visible').contains('Settings').click();
		cy.get('.modal-dialog').should('contain', 'Settings');

		cy.findByLabelText('Disable Count').check({ force: true });
		cy.findByLabelText('Disable Sidebar Stats').check({ force: true });
		cy.findByRole('button', {name: 'Save'}).click();

		cy.reload();

		cy.get('.list-count').should('be.empty');
		cy.get('.list-sidebar .sidebar-stat').should('not.exist');

		cy.get('.menu-btn-group button').click({ force: true });
		cy.get('.dropdown-menu li').filter(':visible').contains('List Settings').click();
		cy.get('.modal-dialog').should('contain', 'DocType Settings');
		cy.findByLabelText('Disable Count').uncheck({ force: true });
		cy.findByLabelText('Disable Sidebar Stats').uncheck({ force: true });
		cy.findByRole('button', {name: 'Save'}).click();
	});
});
