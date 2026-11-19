/* Offline regression tests. No browser, provider, real credential or network access. */
const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');

function tab(search = '?recording=1', saved = new Map()) {
  const page = {window: {}, location: {search}, URLSearchParams, AbortController,
    sessionStorage: {getItem: k => saved.get(k) ?? null, setItem: (k,v) => saved.set(k,v)}};
  load('recording.js', page);
  load('attachments.js', page);
  return page;
}
function load(file, page) {
  runInNewContext(readFileSync(join(__dirname, file), 'utf8'), page, {filename: file});
}

test('recording requires manual setup and allows two requests across reloads', () => {
  const saved = new Map(), recording = tab('?recording=1', saved).window.YincaiRecording;
  assert.equal(recording.canSend(), false);
  assert.throws(() => recording.reserve(), /云端配置/);
  recording.confirmSettings(); recording.reserve();
  const restored = tab('?recording=1', saved).window.YincaiRecording;
  assert.match(restored.status(), /还可发送 1 次/);
  restored.reserve();
  assert.equal(restored.canSend(), false);
  assert.throws(() => restored.reserve(), /两次/);
});
test('failed recording stops other requests and ordinary usage remains available', () => {
  const saved = new Map(), recording = tab('?recording=1', saved).window.YincaiRecording;
  recording.confirmSettings(); recording.reserve(); recording.pauseAfterFailure();
  assert.equal(recording.canSend(), false);
  assert.throws(() => recording.reserve(), /暂停/);
  const ordinary = tab('', saved).window.YincaiRecording;
  for(let i=0; i<3; i++) ordinary.reserve();
  assert.equal(ordinary.canSend(), true);
});

function settingsFixture() {
  const fields = new Map();
  const control = selector => {
    if (!fields.has(selector)) fields.set(selector, {
      value: '', disabled: false, dataset: {}, classList: {toggle() {}},
      focus() {}, setAttribute() {}, addEventListener(type, fn) {this['on' + type] = fn;},
      replaceChildren(...options) {this.options = options;},
      showModal() {this.open = true;}, close() {this.open = false;}
    });
    return fields.get(selector);
  };
  control('form').reportValidity = () => true;
  control('form').reset = () => {for (const [s, c] of fields) if (s.startsWith('#')) c.value = '';};
  control('.model-settings').querySelector = control;
  const saved = new Map(), page = tab('?recording=1', saved);
  page.Option = class {constructor(text, value){this.text = text; this.value = value;}};
  const cloud = {id:'deepseek', label:'DeepSeek', base_url:'https://example.invalid/v1', models:['fixture-model']};
  const local = {id:'ollama', label:'本机', base_url:'http://localhost', models:['fixture-local']};
  let active = {provider:'ollama', model:local.models[0], base_url:local.base_url, configured:true};
  const calls = [];
  page.fetch = async (url, req) => {
    calls.push([url, req.method]);
    if (req.method === 'POST'){
      const config = JSON.parse(req.body);
      assert.equal(config.api_key, 'offline-test-value');
      active = {provider:config.provider, base_url:config.base_url, model:config.model, configured:true, has_key:true};
    }
    return {ok:true, json:async () => ({providers:[local,cloud], active})};
  };
  load('settings.js', page);
  return {page,control,calls,saved};
}

test('private dialog: saving closes it, clears inputs and sends only a local settings request', async () => {
  const {page,control,calls,saved} = settingsFixture();
  await page.window.YincaiSettings.render({querySelector:control}, () => {});
  control('[data-private-config]').onclick();
  assert.equal(control('dialog').open, true);
  assert.deepEqual(Array.from(control('#ms-provider').options, x=>x.value), ['deepseek']);
  assert.equal(control('.ms-test').hidden, true);
  await control('.ms-test').onclick();
  control('#ms-key').value = 'offline-test-value';
  control('form').onsubmit({preventDefault(){}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(calls, [['/api/chat/settings','GET'],['/api/chat/settings','POST']]);
  assert.equal(control('dialog').open, false);
  assert.equal(control('#ms-key').value, '');
  assert.equal(control('#ms-base').value, '');
  assert.equal(control('.model-settings').dataset.configSaved, 'true');
  assert.equal(control('.ms-current strong').textContent, 'DeepSeek');
  assert.equal(control('.ms-current small').textContent, 'fixture-model');
  assert.deepEqual([...saved.values()], ['1']);
  assert.match(page.window.YincaiRecording.status(), /还可发送 2 次/);
});
test('closing without saving clears the form and never authorizes a recording', async () => {
  const {page,control,calls} = settingsFixture();
  await page.window.YincaiSettings.render({querySelector:control}, () => {});
  control('[data-private-config]').onclick();
  control('#ms-key').value = 'discarded example';
  control('.ms-close').onclick();
  assert.equal(control('dialog').open, false);
  assert.equal(control('#ms-key').value, '');
  assert.equal(page.window.YincaiRecording.canSend(), false);
  assert.deepEqual(calls, [['/api/chat/settings','GET']]);
});

test('an explicit question and a handoff carry independent model receipts; a third question is blocked', async () => {
  const page = tab();
  page.window.YincaiRecording.confirmSettings();
  const controls = new Map();
  function field(selector) {
    if (!controls.has(selector)) controls.set(selector, {
      value:'', style:{}, dataset:{}, isConnected:true, contains:()=>true, focus(){}, setAttribute(){},
      addEventListener(e, fn){this['on'+e] = fn;}, querySelector:field
    });
    return controls.get(selector);
  }
  page.document = {createElement: () => field('panel')};
  page.localStorage = {getItem: () => null};
  page.crypto = require('node:crypto');
  page.matchMedia = () => ({matches:true});
  const messages = [];
  page.fetch = async (url, options) => {
    if (url === '/api/chat/status') return {ok:true, json:async()=>({configured:true,provider:'compatible',model:'fixture'})};
    assert.equal(url, '/api/chat');
    const request = JSON.parse(options.body);
    messages.push(request);
    return {ok:true, json:async()=>({source:'live', provider:'compatible', vendor:'deepseek', model:'fixture',
      elapsed_ms:3412, reply:'离线单元测试回复', conversation_id:'offline-id', role:request.role,
      generated_at:'2026-11-19T03:00:00Z', request_id:request.request_id, replayed:false})};
  };
  load('chat.js', page);
  page.window.YincaiChat.render({replaceChildren(){}}, {role:'analyst'});
  function send(text) {
    const input = field('textarea'); input.tagName='TEXTAREA'; input.value=text;
    field('panel').oninput({target:input});
    field('.cc-compose').onsubmit({preventDefault(){}});
  }
  assert.equal(messages.length,0);
  send('测试提问');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(messages.length,1);
  assert.equal(messages[0].role,'analyst');
  assert.match(field('.cc-log').innerHTML, /● 实时生成 · DeepSeek · fixture · 3\.41 秒/);
  const handoff={dataset:{handoff:'expert',receipt:messages[0].request_id}};
  field('panel').onclick({target:{closest:()=>handoff}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(messages.length,2);
  assert.equal(messages[1].role,'expert');
  assert.equal(messages[1].handoff_from,messages[0].request_id);
  assert.match(field('.cc-log').innerHTML, /data-model-receipt/);
  send('第三次');
  assert.equal(field('.cc-send').disabled,true);
  assert.equal(messages.length,2);
});
