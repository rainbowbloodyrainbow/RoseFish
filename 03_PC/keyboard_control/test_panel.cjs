// Exercise the actual page script with a small DOM and HTTP stub; no ROS/network.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(__dirname + '/panel.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = {};
for (const id of ['arm','stop','mode','status','velocity','linear','angular','lv','av']) {
  elements[id] = {value: id==='linear'?'0.03':'0.4', blur(){}, classList:{toggle(){}}};
}
const documentHandlers = {}, windowHandlers = {};
let backend = {armed:false,connected:true,reason:'test',v:0,w:0,preview:true};
let fail = false;
const context = vm.createContext({
  document: {hidden:false, getElementById:id=>elements[id],querySelectorAll:()=>[],
             addEventListener:(key,handler)=>{documentHandlers[key]=handler;}},
  window: {addEventListener:(key,handler)=>{windowHandlers[key]=handler;}},
  setInterval(){}, Date, Set, Number, Boolean, Error, AbortSignal,
  async fetch(url, options) {
    if(fail)throw Error('offline');
    if(url==='/input') {
      const p=JSON.parse(options.body);
      if(p.type==='arm')backend.armed=true;
      if(p.type==='stop'){backend.armed=false;backend.v=backend.w=0;}
      if(p.type==='command'){backend.v=backend.armed?p.v:0;backend.w=backend.armed?p.w:0;}
    }
    return {ok:true,json:async()=>({...backend})};
  }
});
const evaluate = code=>vm.runInContext(code, context);
const flush = ()=>new Promise(resolve=>setImmediate(resolve));
const key = (type, code, repeat=false)=>documentHandlers[type]({code,repeat,preventDefault(){}});
async function arm(){elements.arm.onclick();await flush();await evaluate('tick()');}
async function main(){
  vm.runInContext(script,context);await flush();
  await arm();
  key('keydown','KeyW');await evaluate('tick()');assert.equal(backend.v,0.03);
  key('keydown','ArrowUp');key('keyup','KeyW');await flush();assert.equal(backend.v,0.03);
  key('keyup','ArrowUp');await flush();assert.equal(backend.v,0);
  key('keydown','KeyS');await evaluate('tick()');assert.equal(backend.v,-0.03);
  key('keyup','KeyS');key('keydown','KeyA');await evaluate('tick()');assert.equal(backend.w,0.4);
  key('keydown','KeyD');await evaluate('tick()');assert.equal(backend.w,0);
  windowHandlers.blur();await flush();assert.equal(backend.armed,false);
  await arm();key('keydown','KeyW',true);await evaluate('tick()');assert.equal(backend.v,0);
  key('keydown','KeyW');await evaluate('tick()');assert.equal(backend.v,0.03);
  key('keydown','Space');await flush();assert.equal(backend.armed,false);assert.equal(backend.v,0);
  await arm();context.document.hidden=true;documentHandlers.visibilitychange();await flush();
  assert.equal(backend.armed,false);context.document.hidden=false;
  await arm();backend.armed=false;await evaluate('tick()');assert.equal(evaluate('armed'),false);
  backend.armed=true;await evaluate('tick()');assert.equal(evaluate('armed'),false);
  backend.armed=false;backend.connected=false;await evaluate('tick()');
  assert.equal(elements.arm.disabled,false);
  await arm();key('keydown','KeyW');await evaluate('tick()');
  assert.equal(evaluate('armed'),true);assert.equal(backend.v,0.03);
  key('keyup','KeyW');await flush();assert.equal(backend.v,0);
  await arm();fail=true;await evaluate('tick()');assert.equal(evaluate('armed'),false);
  console.log('PASS: key-down/up, aliases, opposing keys, reverse/turn, focus loss, Space, hidden page, repeat suppression, no automatic re-arm, feedback loss does not lock, HTTP failure');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
