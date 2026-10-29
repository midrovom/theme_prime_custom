// Ejecución independiente: node tests/js/test_dashboard_grouping.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../static/src/dashboard/dashboard.js'), 'utf8')
    .replace(/^import .*;\s*$/gm, '')
    .replace('export class ExpenseBudgetDashboard', 'class ExpenseBudgetDashboard')
    + '\nglobalThis.DashboardUnderTest = ExpenseBudgetDashboard;';
const vmContext = {
    Component: class {},
    useState: (value) => value,
    onWillStart: () => {},
    useService: (name) => name === 'orm' ? {call: async () => ({})} : {},
    registry: {category: () => ({add: () => {}})},
    Intl, Math, Map, Number, Array, Object, String,
};
vm.createContext(vmContext);
vm.runInContext(source, vmContext);
const dash = new vmContext.DashboardUnderTest();
dash.setup();
dash.state.data = {
    month_names: ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'],
    currency: '$', decimal_digits: 2,
    accounts: [{id: 1, name: 'Luz', category_id: 10}, {id: 2, name: 'Fletes', category_id: 20}],
    categories: [{id: 10, name: 'Servicios'}, {id: 20, name: 'Transporte'}],
    cost_centers: [{id: 100, name: 'Operaciones'}, {id: 200, name: 'Administración'}],
    breakdown: [
        {center_id: 100, center_name: 'Operaciones', category_id: 10, category_name: 'Servicios', account_id: 1, account_name: 'Luz', months: [10, 20, ...Array(10).fill(0)]},
        {center_id: 200, center_name: 'Administración', category_id: 10, category_name: 'Servicios', account_id: 1, account_name: 'Luz', months: [30, 0, ...Array(10).fill(0)]},
        {center_id: 100, center_name: 'Operaciones', category_id: 20, category_name: 'Transporte', account_id: 2, account_name: 'Fletes', months: [20, 0, ...Array(10).fill(0)]},
    ],
};
dash.state.year = '2089';
dash.state.chartGroup = 'center';
const cents = dash.distributionRows;
assert.equal(cents.length, 2);
assert.equal(cents.find((row) => row.id === 100).amount, 50);
assert.equal(cents.find((row) => row.id === 200).amount, 30);
assert.equal(dash.totalSpent, 80);
assert.equal(dash.pieSlices.reduce((sum, p) => sum + p.percentage, 0), 100);
assert.equal(dash.pieSlices.find((slice) => slice.id === 100).percentage, 62.5);

dash.state.categoryId = '10';
assert.equal(dash.totalSpent, 60);
assert.equal(dash.distributionRows.find((row) => row.id === 100).amount, 30);
assert.equal(dash.distributionRows.find((row) => row.id === 200).amount, 30);
assert.equal(dash.pieSlices.find((row) => row.id === 100).percentage, 50);

dash.state.selectedMonth = 0;
assert.equal(dash.totalSpent, 40);
assert.equal(dash.distributionRows.find((row) => row.id === 100).amount, 10);
assert.equal(dash.pieSlices.find((row) => row.id === 100).percentage, 25);

dash.state.chartGroup = 'account';
assert.equal(dash.distributionRows.length, 1);
assert.equal(dash.distributionRows[0].name, 'Luz');
assert.equal(dash.pieSlices[0].percentage, 100);

dash.state.categoryId = '';
dash.state.chartGroup = 'category';
assert.equal(dash.distributionRows.find((r) => r.id === 20).amount, 20);
assert.equal(dash.pieSlices.find((r) => r.id === 20).percentage, 33.33);

dash.state.chartGroup = 'month';
assert.equal(dash.distributionRows.length, 1);
assert.equal(dash.distributionRows[0].name, 'Enero');
assert.equal(dash.distributionRows[0].amount, 60);
console.log('Dashboard JS: agrupación, filtro por rubro, mes y porcentajes OK');

// El cambio de centro conserva los filtros y descarta respuestas obsoletas.
(async () => {
    dash.state.chartGroup = 'center';
    dash.state.categoryId = '10';
    dash.state.accountId = '1';
    dash.state.selectedMonth = 0;
    const catalog = dash.state.data;
    dash.orm = {call: async (_model, _method, args) => ({
        ...catalog, company_id: 3, year: 2089, cost_center_id: args[2] || false,
        breakdown: catalog.breakdown.filter((line) => line.center_id === Number(args[2])),
    })};
    await dash.load(3, 2089, 100);
    assert.equal(dash.state.costCenterId, '100');
    assert.equal(dash.state.categoryId, '10');
    assert.equal(dash.state.accountId, '1');
    assert.equal(dash.state.selectedMonth, 0);
    assert.equal(dash.distributionRows.find((r) => r.id === 100).amount, 10);
    dash.state.chartGroup = 'account';
    assert.equal(dash.distributionRows[0].name, 'Luz');
    assert.equal(dash.totalSpent, 10);
    console.log('Dashboard JS: cambio de centro conserva rubro, cuenta y mes OK');
})().catch((error) => { console.error(error); process.exitCode = 1; });
