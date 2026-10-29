// Ejecución sin Odoo: node tests/js/test_dashboard_filters_original.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '../..');
const js = fs.readFileSync(path.join(root, 'static/src/dashboard/dashboard.js'), 'utf8');
const xml = fs.readFileSync(path.join(root, 'static/src/dashboard/dashboard.xml'), 'utf8');
assert(xml.includes('this.bars'), 'Conservar barras mensuales originales');
assert(xml.includes('this.accountBars'), 'Conservar barras por cuenta originales');
assert(xml.includes('this.pieSlices'), 'Conservar pastel original');
assert(!xml.includes('chartGroup') && !xml.includes('distributionRows'), 'No añadir selectores ni agrupaciones nuevos');

const source = js.replace(/^import .*;\s*$/gm, '')
    .replace('export class ExpenseBudgetDashboard', 'class ExpenseBudgetDashboard')
    + '\nglobalThis.DashboardUnderTest = ExpenseBudgetDashboard;';
const context = {
    Component: class {}, useState: v => v, onWillStart: () => {},
    useService: () => ({}), registry: {category: () => ({add: () => {}})},
    Intl, Math, Map, Number, Array, Object, String,
};
vm.createContext(context);
vm.runInContext(source, context);
const dash = new context.DashboardUnderTest();
dash.setup();

const months = (jan, feb) => [jan, feb, ...Array(10).fill(0)];
const makePayload = (center, company=1, year=2089) => {
    const centers = {
        '': [[100, 50], [40, 25], [40, 0]],
        '10': [[40, 30], [10, 20], [15, 0]],
        '20': [[60, 20], [30, 5], [25, 0]],
    };
    const amounts = centers[String(center)] || centers[''];
    return {
        company_id: company, year, cost_center_id: center || false,
        years: [2089], companies: [{id: 1, name: 'Empresa 1'}],
        currency: '$', decimal_digits: 2,
        month_names: ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'],
        cost_centers: [{id: 10, name: 'Administración'}, {id: 20, name: 'Operaciones'}],
        categories: [{id: 100, name: 'Servicio Básico'}, {id: 200, name: 'Transporte'}],
        accounts: [
            {id: 101, name: 'Luz', category_id: 100, months: months(...amounts[0])},
            {id: 102, name: 'Agua', category_id: 100, months: months(...amounts[1])},
            {id: 201, name: 'Fletes', category_id: 200, months: months(...amounts[2])},
        ],
    };
};
const close = (got, want) => assert(Math.abs(got - want) < 0.00001, `${got} != ${want}`);

(async () => {
    dash.orm = {call: async (_model, _method, args) => makePayload(args[2])};
    await dash.load(1, 2089, false, false);
    assert.equal(dash.bars.length, 12, 'Gráfico de barras sigue mensual');
    assert.equal(dash.chartTitle, 'Gastos por mes');
    close(dash.monthlyAmounts[0], 180);
    close(dash.totalSpent, 255);
    close(dash.pieSlices.reduce((s, row) => s + row.percentage, 0), 100);

    // Rubro en todos los centros -> pastel por cuentas del rubro; no cambia diseño.
    dash.onCategoryChange({target: {value: '100'}});
    dash.onMonthChange({target: {value: '0'}});
    close(dash.totalSpent, 140);
    assert.equal(dash.chartTitle, 'Gastos por cuenta controlada · Enero');
    assert.equal(dash.accountBars.length, 2);
    assert.equal(dash.pieSlices.length, 2);
    close(dash.pieSlices[0].percentage, 71.4);
    dash.onAccountChange({target: {value: '101'}});
    close(dash.totalSpent, 100);

    // Cambiar centro mantiene cuenta, rubro y mes; los datos se recalculan.
    await dash.load(1, 2089, 10);
    assert.equal(dash.state.costCenterId, '10');
    assert.equal(dash.state.categoryId, '100');
    assert.equal(dash.state.accountId, '101');
    assert.equal(dash.state.selectedMonth, 0);
    close(dash.totalSpent, 40);
    close(dash.accountBars[0].amount, 40);
    close(dash.pieSlices[0].percentage, 100);

    // Cambiar el centro con el rubro seleccionado y todas sus cuentas.
    dash.onAccountChange({target: {value: ''}});
    await dash.load(1, 2089, 20);
    close(dash.totalSpent, 90);
    assert.equal(dash.pieSlices.length, 2);
    close(dash.pieSlices.find(s => s.id === 101).percentage, 66.7);
    await dash.load(1, 2089, false);
    close(dash.totalSpent, 140);
    assert.equal(dash.state.categoryId, '100');
    assert.equal(dash.state.selectedMonth, 0);

    // Respuesta obsoleta no sustituye al centro solicitado después.
    let resolveSlow;
    dash.orm = {call: async (_model, _method, args) => {
        if (args[2] === 10) { return new Promise(resolve => {resolveSlow = resolve;}); }
        return makePayload(args[2]);
    }};
    const slow = dash.load(1, 2089, 10);
    const fast = dash.load(1, 2089, 20);
    await fast;
    resolveSlow(makePayload(10));
    await slow;
    assert.equal(dash.state.costCenterId, '20');
    close(dash.totalSpent, 90);

    // Cambiar empresa sí restablece los filtros del contexto anterior.
    await dash.onCompanyChange({target: {value: '2'}});
    assert.equal(dash.state.categoryId, '');
    assert.equal(dash.state.accountId, '');
    assert.equal(dash.state.selectedMonth, -1);
    console.log('OK: gráficos originales, filtros combinados, todos los centros y respuestas obsoletas.');
})().catch(err => {console.error(err); process.exitCode=1;});
