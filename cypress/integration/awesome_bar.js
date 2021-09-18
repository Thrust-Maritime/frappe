context('Awesome Bar', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/desk');
	});

	beforeEach(() => {
		cy.get('.navbar-header .navbar-home').click();
	});

	it('navigates to doctype list', () => {
		cy.findByPlaceholderText('Search or type a command (Ctrl + G)').type('todo', { delay: 200 });
		cy.get('.awesomplete').findByRole('listbox').should('be.visible');
		cy.findByPlaceholderText('Search or type a command (Ctrl + G)').type('{downarrow}{enter}', { delay: 100 });

		cy.get('h1').should('contain', 'To Do');

		cy.location('hash').should('eq', '#List/ToDo/List');
	});

	it('find text in doctype list', () => {
		cy.findByPlaceholderText('Search or type a command (Ctrl + G)')
			.type('test in todo{downarrow}{enter}', { delay: 200 });

		cy.get('h1').should('contain', 'To Do');

		cy.findByPlaceholderText('Name')
			.should('have.value', '%test%');
	});

	it('navigates to new form', () => {
		cy.findByPlaceholderText('Search or type a command (Ctrl + G)')
			.type('new blog post{downarrow}{enter}', { delay: 200 });

		cy.get('.title-text:visible').should('have.text', 'New Blog Post 1');
	});

	it('calculates math expressions', () => {
		cy.findByPlaceholderText('Search or type a command (Ctrl + G)')
			.type('55 + 32{downarrow}{enter}', { delay: 200 });

		cy.get('.modal-title').should('contain', 'Result');
		cy.get('.msgprint').should('contain', '55 + 32 = 87');
	});
});
