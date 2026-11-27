const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {prepareExport} = require('./validate-export.cjs');
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname,'synthetic-export.json')));
const nodes=[], connections={};
function node(name, type, version, xy, parameters, other={}) {
  nodes.push({name,id:crypto.createHash('sha256').update(name).digest('hex').slice(0,32).replace(/^(.{8})(.{4})(.{4})(.{4})(.{12})$/,'$1-$2-$3-$4-$5'),type:'n8n-nodes-base.'+type,typeVersion:version,position:xy,parameters,...other});
}
function link(a,b){connections[a]={main:[[{node:b,type:'main',index:0}]]};}
node('Try the synthetic export','manualTrigger',1,[0,0],{});
node('Synthetic supplier bundle','code',2,[220,0],{jsCode:'return [{json:'+JSON.stringify(fixture)+'}];'});
const validate=supplier=>prepareExport.toString()+'\nreturn [{json:prepareExport($input.first().json,'+JSON.stringify(supplier)+')}];';
node('Preview the child input','code',2,[440,0],{jsCode:validate('SYNTHETIC-ORCHARD')});
link('Try the synthetic export','Synthetic supplier bundle');link('Synthetic supplier bundle','Preview the child input');
node('Receive trusted retailer trigger','executeWorkflowTrigger',1.1,[0,280],{inputSource:'passthrough'});
node('Read one authorized completed export','httpRequest',4.2,[220,280],{
  method:'GET',url:'https://supplier.example.invalid/authorized/catalog-export',authentication:'genericCredentialType',genericAuthType:'httpHeaderAuth',
  options:{redirect:{redirect:{followRedirects:false}},timeout:15000,response:{response:{responseFormat:'json'}}}
});
node('Check retailer supplier binding','code',2,[440,280],{jsCode:validate('REPLACE_WITH_RETAILER_SUPPLIER_ID')});
node('Run the configured Supplier child','executeWorkflow',1.2,[660,280],{source:'database',workflowId:{__rl:true,value:'SELECT_YOUR_PRIVATE_SUPPLIER_CHILD',mode:'id'},options:{waitForSubWorkflow:true}});
link('Receive trusted retailer trigger','Read one authorized completed export');link('Read one authorized completed export','Check retailer supplier binding');link('Check retailer supplier binding','Run the configured Supplier child');
node('Connection and cost','stickyNote',1,[0,-300],{width:850,height:200,content:'## Supplier price list comparison\nManual test stops at a synthetic preview. Production needs a retailer-approved fixed HTTPS endpoint, source credential, isolated child and explicit spending cap. A completed custom audit can cost $0.85. Configure a separate private copy per retailer and supplier. Set the URL and supplier ID in that copy.'});
fs.writeFileSync(path.join(__dirname,'supplier-export-parent.json'),JSON.stringify({name:'Compare supplier price lists from an authorized export',active:false,nodes,connections,settings:{executionOrder:'v1',callerPolicy:'workflowsFromSameOwner',saveManualExecutions:false,saveDataErrorExecution:'none',saveDataSuccessExecution:'none',saveExecutionProgress:false,executionTimeout:180}},null,2)+'\n');
