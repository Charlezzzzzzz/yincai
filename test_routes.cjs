/* Exercise the application router, including real startup and the evidence refresh. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function startAt(hash) {
  const handlers = new Map();
  const steps = [];
  const location = {protocol:'http:', hash};
  const history = {
    replaceState(_state, _title, next) { location.hash = next; },
    pushState(_state, _title, next) { location.hash = next; }
  };
  const element = {
    dataset:{}, classList:{add(){}, remove(){}}, setAttribute(){}, removeAttribute(){},
    querySelector(){return element;}, querySelectorAll(){return [];}, addEventListener(){}
  };
  element.parentElement = element;
  let deliverComparison;
  const comparison = new Promise(resolve => {deliverComparison = resolve;});
  const page = {
    location, history, document:{
      body:{dataset:{}}, querySelector(){return element;}, querySelectorAll(){return [];},
      createElement(){return {...element};}, addEventListener(){}
    },
    addEventListener(type, callback){handlers.set(type, callback);},
    fetch(url){assert.equal(url, '/api/cockpit/comparison'); return comparison;},
    matchMedia(){return {matches:false};}, scrollTo(){},
    YincaiViewer:{mount(){return {dispose(){}};}},
    YincaiRoundtable:{create(){return {mount(_work,n){steps.push(n);}, leave(){}};}}
  };
  page.window = page;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'app.js'),'utf8'),page);
  return {
    location, steps,
    go(next){location.hash = next; handlers.get('hashchange')();},
    async resolveEvidence() {
      deliverComparison({ok:true, json:async()=>({protocol:{
        steps:Object.fromEntries(Array.from({length:8},(_,i)=>[i+1,{}])),
        cache_round_elapsed_seconds:526.8
      }})});
      await new Promise(resolve => setImmediate(resolve));
    }
  };
}

test('a direct step link survives startup and the subsequent evidence fetch', async()=>{
  const page = startAt('#cockpit/6');
  assert.equal(page.location.hash,'#cockpit/6');
  assert.deepEqual(page.steps,[6]);
  await page.resolveEvidence();
  assert.equal(page.location.hash,'#cockpit/6');
  assert.deepEqual(page.steps,[6,6]);
});

test('same-document navigation from cast preserves the selected step and its canonical link', async()=>{
  const page = startAt('#cast/checker');
  page.go('#cockpit/6');
  assert.equal(page.location.hash,'#cockpit/6');
  assert.deepEqual(page.steps,[6]);
  page.go('#cast/producer');
  page.go('#cockpit');
  assert.equal(page.location.hash,'#cockpit/6');
  page.go('#cockpit/8');
  await page.resolveEvidence();
  assert.equal(page.location.hash,'#cockpit/8');
  assert.equal(page.steps.at(-1),8);
});

test('the cast handbook still resolves the last selected teacher appearance', ()=>{
  const page = startAt('#cast/teacher-male');
  page.go('#cast/expert');
  page.go('#cast/teacher');
  assert.equal(page.location.hash,'#cast/teacher-male');
});
