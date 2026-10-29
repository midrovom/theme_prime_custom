// Pruebas de arranque, recarga y barras compactas. node tests/js/test_dashboard_startup_compact.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname, '../..');
const js = fs.readFileSync(path.join(root, 'static/src/dashboard/dashboard.js'), 'utf8');
const xml = fs.readFileSync(path.join(root, 'static/src/dashboard/dashboard.xml'), 'utf8');
const css = fs.readFileSync(path.join(root, 'static/src/dashboard/dashboard.scss'), 'utf8');
assert(xml.includes('t-if="state.ready"'), 'Filtros visibles después de tener el resultado inicial');
assert(xml.includes('t-if="month.showCenterNames"'), 'Nombre omitido con un solo centro');
assert(xml.includes('t-att-selected="center.id == state.costCenterId"'), 'Centro sincronizado con selección real');
assert(xml.includes('t-att-selected="year == state.year"'), 'Año sincronizado con selección real');
assert(css.includes('flex: 0 0 48px'), 'Barras compactas escritorio');
assert(css.includes('flex-basis: 42px'), 'Barras compactas móvil');
assert(css.includes('width: 28px'), 'El ancho de las barras permanece igual');
let starting; let mounted;
const service = {call: async () => ({})};
const context = {
    Component: class {}, useState: v => v,
    onWillStart: cb => {starting = cb;}, onMounted: cb => {mounted = cb;},
    useService: name => name === 'orm' ? service : {},
    registry: {category: () => ({add: () => {}})},
    Intl, Math, Map, Number, Array, Object, String,
};
vm.createContext(context);
vm.runInContext(js.replace(/^import .*;\s*$/gm,'')
    .replace('export class ExpenseBudgetDashboard', 'class ExpenseBudgetDashboard')
    + '\nglobalThis.DashboardUnderTest = ExpenseBudgetDashboard;', context);
const months = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const data = (centerId=false) => ({
    company_id: 1, companies: [{id:1,name:'My Company'}], year:2026, years:[2026],
    cost_center_id:centerId, cost_centers:[{id:9,name:'CBA'}, {id:11,name:'ABS'}],
    categories:[{id:7,name:'Servicios Básicos'}], accounts:[{id:20,name:'Luz',category_id:7}],
    month_names:months,currency:'$',decimal_digits:2,
    breakdown:[
        {center_id:9,center_name:'CBA',category_id:7,account_id:20,account_name:'Luz',months:[100,...Array(11).fill(0)]},
        ...(centerId ? [] : [{center_id:11,center_name:'ABS',category_id:7,account_id:20,account_name:'Luz',months:[200,...Array(11).fill(0)]}])
    ].filter(row=>!centerId || String(row.center_id) === String(centerId))
});
const promiseNextTick = () => new Promise(resolve => setImmediate(resolve));
(async()=>{
    const dashboard = new context.DashboardUnderTest();
    dashboard.setup();
    assert.equal(dashboard.state.ready,false, 'No mostrar filtros vacíos');
    let calls=0;
    service.call = async (_m,_f,args) => { calls++; assert.equal(args.length,3); return data(args[2]); };
    await starting();
    assert.equal(dashboard.state.ready,true);
    assert.equal(dashboard.state.error,'');
    assert.equal(dashboard.state.companyId,'1');
    assert.equal(dashboard.state.year,'2026');
    assert.equal(dashboard.state.costCenterId,'');
    assert.equal(dashboard.totalSpent,300);
    assert.equal(dashboard.monthlyCenterGroups.length,12);
    assert.equal(dashboard.monthlyCenterGroups[0].showCenterNames,true);
    mounted();
    await promiseNextTick();
    assert.equal(calls,1,'Sin repetir carga al montar si fue satisfactoria');
    await dashboard.onCostCenterChange({target:{value:'9'}});
    assert.equal(dashboard.state.costCenterId,'9');
    assert.equal(dashboard.monthlyCenterGroups[0].showCenterNames,false);
    assert(dashboard.chartHint.includes('CBA'), 'Nombre del centro una sola vez');
    assert.equal(dashboard.monthlyCenterGroups[0].centers.length,1);
    assert.equal(dashboard.totalSpent,100);
    assert.equal(dashboard.monthlyCenterGroups.length,12);
    // Falla transitoria en primera apertura y recuperación automática una vez.
    const retry = new context.DashboardUnderTest(); retry.setup();
    let attempts=0;
    service.call = async () => {if (++attempts === 1) throw Error('Interrupción temporal'); return data();};
    await starting();
    assert.equal(retry.state.ready,true);
    assert.equal(retry.state.error,'Interrupción temporal');
    mounted();
    await promiseNextTick();
    assert.equal(attempts,2);
    assert.equal(retry.state.error,'');
    assert.equal(retry.state.companyId,'1');
    assert.equal(retry.totalSpent,300);
    console.log('OK: carga inicial y recuperación, selecciones, barras compactas, nombres no repetidos.');
})().catch(e=>{console.error(e);process.exitCode=1;});
