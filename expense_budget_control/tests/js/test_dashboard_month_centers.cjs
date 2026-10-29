// Ejecutar: node tests/js/test_dashboard_month_centers.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '../..');
const js = fs.readFileSync(path.join(root, 'static/src/dashboard/dashboard.js'), 'utf8');
const xml = fs.readFileSync(path.join(root, 'static/src/dashboard/dashboard.xml'), 'utf8');
const css = fs.readFileSync(path.join(root, 'static/src/dashboard/dashboard.scss'), 'utf8');
assert(xml.includes('this.monthlyCenterGroups') && xml.includes('this.pieSlices'));
assert(xml.includes('o_ebd_center_bar_name') && xml.includes('month.centers'));
assert(!xml.includes('chartGroup') && !xml.includes('distributionRows'), 'Sin nuevos selectores');
assert(css.includes('.o_ebd_grouped_scroll') && css.includes('.o_ebd_bar'));
assert(css.includes('width: 28px; max-width: 100%; margin-inline: auto;'), 'Barras delgadas centradas');
assert(css.includes('.o_ebd_center_bar_item .o_ebd_bar { width: 22px; }'), 'Barras delgadas en móvil');
const source = js.replace(/^import .*;\s*$/gm,'')
  .replace('export class ExpenseBudgetDashboard','class ExpenseBudgetDashboard')
  + '\nglobalThis.DashboardUnderTest = ExpenseBudgetDashboard;';
const ctx = {
  Component: class {}, useState: v => v, onWillStart: () => {}, onMounted: () => {},
  useService: () => ({}), registry: {category: () => ({add: () => {}})},
  Intl, Math, Map, Number, Array, Object, String,
};
vm.createContext(ctx);
vm.runInContext(source, ctx);
const dash = new ctx.DashboardUnderTest();
dash.setup();
const m = (jan, feb, mar = 0) => [jan, feb, mar, ...Array(9).fill(0)];
const sourceRows = [
  {center_id:1,center_name:'Administración',category_id:10,account_id:100,account_name:'Luz', months:m(100,120)},
  {center_id:1,center_name:'Administración',category_id:10,account_id:101,account_name:'Agua', months:m(50,60)},
  {center_id:2,center_name:'Bodega ABS',category_id:10,account_id:100,account_name:'Luz', months:m(200,10)},
  {center_id:3,center_name:'Bodega ANT',category_id:10,account_id:102,account_name:'Internet', months:m(300,30)},
  {center_id:4,center_name:'Operaciones',category_id:10,account_id:101,account_name:'Agua', months:m(400,40)},
  {center_id:5,center_name:'Ventas',category_id:10,account_id:102,account_name:'Internet', months:m(500,50)},
  {center_id:5,center_name:'Ventas',category_id:20,account_id:103,account_name:'Fletes', months:m(600,90)},
];
const expectedBase = 1550; // enero Servicio Básico, cinco centros
function payload(center) {
  const breakdown = sourceRows.filter(r => !center || String(r.center_id) === String(center));
  return {
    company_id:1, year:2026, cost_center_id:center||false,
    companies:[{id:1,name:'My Company'}], years:[2026],
    month_names:['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'],
    cost_centers:[1,2,3,4,5].map(id=>({id,name:sourceRows.find(r=>r.center_id===id).center_name})),
    categories:[{id:10,name:'Servicio Básico'},{id:20,name:'Transporte'}],
    accounts:[
      {id:100,name:'Luz',category_id:10}, {id:101,name:'Agua',category_id:10},
      {id:102,name:'Internet',category_id:10}, {id:103,name:'Fletes',category_id:20},
    ],
    breakdown, currency:'$',decimal_digits:2,
  };
}
function close(actual, expected) { assert(Math.abs(actual-expected)<1e-7, `${actual} != ${expected}`); }
function totalBar(month) {return month.centers.reduce((sum,c)=>sum+c.amount,0);}
(async () => {
  dash.orm={call: async (_model,_method,args) => payload(args[2])};
  await dash.load(1,2026,false,false);
  dash.onCategoryChange({target:{value:'10'}});
  assert.equal(dash.chartTitle,'Gastos por mes y centro de costo');
  assert.equal(dash.monthlyCenterGroups.length,12, 'Deben aparecer los 12 meses');
  const jan=dash.monthlyCenterGroups[0], feb=dash.monthlyCenterGroups[1];
  assert.equal(jan.name,'Enero');
  assert.equal(jan.centers.length,5, 'Cinco centros = cinco barras en enero');
  assert(jan.centers.every(c=>c.name),'Nombre en cada barra');
  close(totalBar(jan),expectedBase);
  close(totalBar(feb),310);
  close(dash.totalSpent,1860);
  assert.equal(dash.pieSlices.length,5, 'Pastel por centros');
  close(dash.pieSlices.reduce((v,s)=>v+s.percentage,0),100);
  // Filtrar cuenta sin eliminar mes o centros.
  dash.onAccountChange({target:{value:'100'}});
  assert.equal(dash.monthlyCenterGroups.length,12);
  assert.equal(dash.monthlyCenterGroups[0].centers.length,2);
  close(totalBar(dash.monthlyCenterGroups[0]),300);
  close(dash.totalSpent,430);
  dash.onAccountChange({target:{value:''}});
  // Mes seleccionado conserva todos los meses, resalta elegido y total/pastel filtrados.
  dash.onMonthChange({target:{value:'0'}});
  assert.equal(dash.monthlyCenterGroups.length,12);
  assert.equal(dash.monthlyCenterGroups[0].active,true);
  assert.equal(dash.monthlyCenterGroups[1].muted,true);
  close(dash.totalSpent,1550);
  close(dash.pieSlices.reduce((sum,s)=>sum+s.amount,0),1550);
  // La barra de centro y mes permite entrar conservando rubro y cuenta.
  await dash.selectMonthCenter(1,'2');
  assert.equal(dash.state.costCenterId,'2');
  assert.equal(dash.state.categoryId,'10');
  assert.equal(dash.state.selectedMonth,1);
  assert.equal(dash.monthlyCenterGroups.length,12);
  assert.equal(dash.monthlyCenterGroups[0].centers.length,1);
  assert.equal(dash.monthlyCenterGroups[0].centers[0].name,'Bodega ABS');
  close(dash.totalSpent,10);
  assert.equal(dash.chartByCenter,false);
  assert.equal(dash.pieSlices.length,1,'Pastel sigue por cuentas del centro seleccionado');
  // Todos los centros vuelve a recuperar cinco barras por mes.
  await dash.load(1,2026,false);
  assert.equal(dash.state.categoryId,'10');
  assert.equal(dash.state.selectedMonth,1);
  assert.equal(dash.monthlyCenterGroups[0].centers.length,5);
  // Todos los rubros incluye Transporte sin duplicar centro Ventas.
  dash.onCategoryChange({target:{value:''}});
  assert.equal(dash.monthlyCenterGroups[0].centers.length,5);
  close(totalBar(dash.monthlyCenterGroups[0]),2150);
  close(dash.monthlyCenterGroups.slice(0,12).reduce((sum,mo)=>sum+totalBar(mo),0),2550);
  console.log('OK: 12 meses, centros por mes, filtros, pastel, importes, click y nombres.');
})().catch(err=>{console.error(err);process.exitCode=1;});
