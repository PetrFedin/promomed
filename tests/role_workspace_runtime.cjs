const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element{
  constructor(){this.children=[];this.listeners={};this.dataset={};this.value='';this.textContent='';this.hidden=false;this.disabled=false;this.classList={toggle(){}};}
  addEventListener(name,fn){this.listeners[name]=fn;}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=items;}
  setAttribute(){}remove(){}querySelectorAll(){return [];}
  click(){return this.listeners.click?.({preventDefault(){}});}
}
function fixture(fetcher){
  const elements=new Map(),downloads=[];let intervals=[];
  const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const document={getElementById:get,createElement(tag){const node=new Element();if(tag==='a')node.click=()=>downloads.push(node);return node;},createTextNode:text=>({textContent:text}),body:new Element(),addEventListener(){}};
  const context={document,window:{addEventListener(){}},fetch:fetcher,AbortController,setTimeout:()=>0,clearTimeout(){},setInterval:fn=>intervals.push(fn),Blob,URL:{createObjectURL:()=> 'blob:synthetic',revokeObjectURL(){}},console,Intl,Date};
  let source=fs.readFileSync('public/personal/workspace.js','utf8');
  source=source.replace('showAuthMode("login");updateCount();\n})();','globalThis.qa={state,bookAvailable,clearSession};\n})();');
  vm.runInNewContext(source,context);context.qa.state.token='synthetic';
  context.qa.state.availabilityOrg='ORG';get('available-organization').value='ORG';
  return {...context,get,downloads};
}
const response=(body,status=200)=>({ok:status<400,status,json:async()=>body});
const slot={id:'s',version:4,startsAt:2000000000,endsAt:2000001800,availableSeats:1,myStatus:null,knownConflicts:[]};
const available=s=>({organization:{id:'ORG',name:'Synthetic'},slots:[s],conflictsComplete:true});
async function main(){
  for(const changed of [{...slot,availableSeats:0},{...slot,startsAt:slot.startsAt+60}]){
    let posts=0;const f=fixture(async(url,opts)=>{if(opts.method==='POST')posts++;return response(available(changed));});
    await f.qa.bookAvailable('ORG',slot,{checked:true},{dataset:{}});assert.equal(posts,0);
    assert.match(f.get('notice').textContent,/изменились/);
  }
  let finish,posts=0;const withdrawn=fixture(async(url,opts)=>{if(opts.method==='POST')posts++;return new Promise(r=>finish=r);});
  const consent={checked:true};const checking=withdrawn.qa.bookAvailable('ORG',slot,consent,{dataset:{}});consent.checked=false;finish(response(available(slot)));await checking;assert.equal(posts,0);
  const conflict={...slot,knownConflicts:[{slotId:'other',title:'Other',overlapSeconds:600}]};
  let conflictPosts=0;const f=fixture(async(url,opts)=>{if(opts.method==='POST'){conflictPosts++;assert.equal(JSON.parse(opts.body).expected_version,4);return response({error:'unavailable'},503);}return response(available(conflict));});
  const button={dataset:{}};await f.qa.bookAvailable('ORG',slot,{checked:true},button);assert.equal(conflictPosts,0);
  await f.qa.bookAvailable('ORG',slot,{checked:true},button);assert.equal(conflictPosts,1);
  const agenda={items:[{calendarEligible:true}],calendarIcs:'fresh-calendar'};
  let reads=0;const calendar=fixture(async()=>{reads++;return response(agenda);});calendar.qa.state.agenda={calendarIcs:'old-calendar'};
  await calendar.get('agenda-export').click();assert.equal(reads,1);assert.equal(calendar.downloads.length,1);
  const revoked=fixture(async()=>response({error:'unauthorized'},401));revoked.qa.state.agenda={calendarIcs:'old-calendar'};
  await revoked.get('agenda-export').click();assert.equal(revoked.downloads.length,0);assert.equal(revoked.qa.state.token,null);
  let resolveExport;const logout=fixture(async()=>new Promise(r=>resolveExport=r));const exportTask=logout.get('agenda-export').click();logout.qa.clearSession();resolveExport(response(agenda));await exportTask;assert.equal(logout.downloads.length,0);
  console.log('PASS: changed availability, revoked consent, conflict confirmation, version payload, fresh export, revocation and logout fencing');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
