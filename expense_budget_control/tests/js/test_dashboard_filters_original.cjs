// Ejecución sin Odoo: node tests/js/test_dashboard_filters_original.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '../..');
const js = fs.readFileSync(path.join(root, 'static/src/dashboard/dashboard.js'), 'utf8');
const xml = fs.readFileSync(path.join(root, 'static/src/dashboard/dashboard.xml'), 'utf8');
const css = fs.readFileSync(path.join(root, 'static/src/dashboard/dashboard.scss'), 'utf8');
assert(xml.includes('this.monthlyCenterGroups') && xml.includes('this.pieSlices'), 'Conservar barras y pastel con desglose mensual');
assert(xml.includes('o_ebd_center_bar_name'), 'Etiquetar cada barra por centro de costo');
assert(!xml.includes('chartGroup') && !xml.includes('distributionRows'), 'No añadir nuevos controles de agrupación');
assert(css.includes('.o_ebd_bar_chart') && css.includes('.o_ebd_pie_layout'), 'Mantener estilos originales');
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
const rows = [
    {center_id: 10, center_name: 'Administración', category_id: 100, category_name: 'Servicio Basico', account_id: 101, account_name: 'Energía Eléctrica', months: months(1500,400)},
    {center_id: 10, center_name: 'Administración', category_id: 100, category_name: 'Servicio Basico', account_id: 102, account_name: 'Agua', months: months(200,100)},
    {center_id: 20, center_name: 'Operaciones', category_id: 100, category_name: 'Servicio Basico', account_id: 101, account_name: 'Energía Eléctrica', months: months(500,632.58)},
    {center_id: 20, center_name: 'Operaciones', category_id: 100, category_name: 'Servicio Basico', account_id: 102, account_name: 'Agua', months: months(0,360.16)},
    {center_id: 20, center_name: 'Operaciones', category_id: 100, category_name: 'Servicio Basico', account_id: 103, account_name: 'Servicio de Internet', months: months(430,0)},
    {center_id: 10, center_name: 'Administración', category_id: 200, category_name: 'Transporte', account_id: 201, account_name: 'Fletes', months: months(125,0)},
];
const makePayload = (center, company=1, year=2026) => {
    const breakdown = rows.filter(row => !center || String(row.center_id) === String(center));
    const acc = new Map();
    for (const row of breakdown) {
        if (!acc.has(row.account_id)) acc.set(row.account_id, {id:row.account_id, name:row.account_name, category_id:row.category_id, months:Array(12).fill(0)});
        row.months.forEach((v,i) => acc.get(row.account_id).months[i]+=v);
    }
    return {
        company_id:company, year, cost_center_id:center||false, years:[2026],
        companies:[{id:1,name:'My Company'}],currency:'$', decimal_digits:2,
        month_names:['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'],
        cost_centers:[{id:10,name:'Administración'},{id:20,name:'Operaciones'}],
        categories:[{id:100,name:'Servicio Basico'},{id:200,name:'Transporte'}],
        accounts:[...acc.values()],breakdown,
    };
};
const close=(got,want)=>assert(Math.abs(got-want)<1e-7,`${got} != ${want}`);
const centerTotal=()=>dash.chartGroups.reduce((sum,group)=>sum+group.amount,0);
const detailsTotal=()=>dash.accountDetail.reduce((sum,group)=>sum+group.amount,0);
const percentTotal=()=>dash.pieSlices.reduce((sum,slice)=>sum+slice.percentage,0);
(async()=>{
    dash.orm={call:async(_m,_f,args)=>makePayload(args[2])};
    await dash.load(1,2026,false,false);
    // Captura: Rubro Servicio Basico, Todos los centros, Todos los meses.
    dash.onCategoryChange({target:{value:'100'}});
    assert.equal(dash.chartTitle,'Gastos por mes y centro de costo');
    assert.equal(dash.monthlyCenterGroups.length,12);
    assert.equal(dash.monthlyCenterGroups[0].centers.length,2);
    assert.equal(dash.pieSlices.length,2);
    close(dash.totalSpent,4122.74);
    close(centerTotal(),4122.74);
    close(detailsTotal(),4122.74);
    close(dash.chartGroups.find(r=>r.id==='10').amount,2200);
    close(dash.chartGroups.find(r=>r.id==='20').amount,1922.74);
    close(percentTotal(),100);
    assert.equal(dash.monthlyCenterGroups[0].centers.find(r=>r.id==='10').name,'Administración');
    assert.equal(dash.pieSlices.find(r=>r.id==='20').name,'Operaciones');
    // Con cuenta seleccionada, el gráfico sigue distribuyendo la cuenta entre centros.
    dash.onAccountChange({target:{value:'101'}});
    close(dash.totalSpent,3032.58);
    close(centerTotal(),3032.58);
    assert.equal(dash.pieSlices.length,2);
    close(percentTotal(),100);
    // Mes elegido mantiene centros, pero calcula solo ese mes.
    dash.onAccountChange({target:{value:''}});
    dash.onMonthChange({target:{value:'0'}});
    close(dash.totalSpent,2630);
    close(dash.chartGroups.find(r=>r.id==='10').amount,1700);
    close(dash.chartGroups.find(r=>r.id==='20').amount,930);
    assert.equal(dash.monthlyCenterGroups.length,12);
    assert.equal(dash.monthlyCenterGroups[0].centers.length,2);
    close(percentTotal(),100);
    // Entrar a un centro desde una barra o pastel conserva rubro y mes;
    // presenta cuentas controladas y mantiene dibujo original.
    await dash.selectChartGroup('10');
    assert.equal(dash.state.costCenterId,'10');
    assert.equal(dash.state.categoryId,'100');
    assert.equal(dash.state.selectedMonth,0);
    assert.equal(dash.chartTitle,'Gastos por mes y centro de costo');
    assert.equal(dash.accountBars.length,2);
    assert.equal(dash.pieSlices.length,2);
    close(dash.totalSpent,1700);
    close(centerTotal(),1700);
    close(percentTotal(),100);
    // Vuelve a Todos los centros; los filtros se preservan.
    await dash.load(1,2026,false);
    assert.equal(dash.state.categoryId,'100');
    assert.equal(dash.state.selectedMonth,0);
    close(dash.totalSpent,2630);
    // Centro específico sin mes: barras verticales por cuenta, pastel por cuenta.
    await dash.load(1,2026,20);
    dash.onMonthChange({target:{value:'-1'}});
    assert.equal(dash.monthlyCenterGroups.length,12);
    assert.equal(dash.monthlyCenterGroups[0].centers.length,1);
    close(dash.totalSpent,1922.74);
    close(centerTotal(),1922.74);
    close(percentTotal(),100);
    dash.onAccountChange({target:{value:'103'}});
    close(dash.totalSpent,430);
    assert.equal(dash.chartGroups.length,1);
    close(dash.pieSlices[0].percentage,100);
    // Elegir Todos los rubros suma gastos de todas las cuentas y centros.
    await dash.load(1,2026,false);
    dash.onCategoryChange({target:{value:''}});
    close(dash.totalSpent,4247.74);
    close(centerTotal(),4247.74);
    close(detailsTotal(),4247.74);
    // Manejo de reversos: el pastel no debe ocultar negativos para fingir 100%.
    dash.state.data.breakdown.push({...rows[0],center_id:30,center_name:'Reverso',months:months(-100,0)});
    assert.equal(dash.pieSlices.length,0);
    assert(dash.pieEmptyMessage.includes('negativos'));
    // Respuestas obsoletas no cambian la selección más reciente.
    let resolveSlow;
    dash.orm={call:async(_m,_f,args)=>args[2]===10
        ? new Promise(resolve=>{resolveSlow=resolve;}) : makePayload(args[2])};
    const slow=dash.load(1,2026,10);
    const fast=dash.load(1,2026,20);
    await fast;
    resolveSlow(makePayload(10));
    await slow;
    assert.equal(dash.state.costCenterId,'20');
    console.log('OK: barras por 12 meses/centros, pastel por centros/cuentas, filtros, totales y porcentajes.');
})().catch(err=>{console.error(err);process.exitCode=1;});
