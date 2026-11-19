/* Node-only fixtures. No browser, actual credential, external model, or user document is accessed. */
const test=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {join}=require('node:path');
const {runInNewContext}=require('node:vm');
const {webcrypto}=require('node:crypto');

function storage(values=new Map()){
  return {getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v)};
}
function load(file,ctx){runInNewContext(readFileSync(join(__dirname,file),'utf8'),ctx,{filename:file});}
function setup(saved=new Map(), reject=false){
  const fields=new Map(),requests=[];
  function field(s){
    if(!fields.has(s))fields.set(s,{value:'',dataset:{},style:{},isConnected:true,contains:()=>true,focus(){},setAttribute(){},
      querySelector:field,addEventListener(k,fn){this['on'+k]=fn;}});
    return fields.get(s);
  }
  const ctx={window:{},location:{search:''},URL,URLSearchParams,btoa,crypto:webcrypto,localStorage:storage(),sessionStorage:storage(saved),
    document:{createElement:()=>field('panel')},matchMedia:()=>({matches:true})};
  const api={ctx,requests,field,fail:reject};
  ctx.fetch=async(url,init)=>{
    if(url==='/api/chat/status')return {ok:true,json:async()=>({configured:true,provider:'compatible',model:'offline-fixture'})};
    assert.equal(url,'/api/chat');
    const r=JSON.parse(init.body);requests.push(r);
    if(api.fail)return {ok:false,status:503,json:async()=>({detail:'离线测试失败'})};
    return {ok:true,json:async()=>({source:'live',role:r.role,request_id:r.request_id,conversation_id:webcrypto.randomUUID(),
      model:'fixture',reply:'**教师复核**',attachments:r.attachments.map(a=>({name:a.name,mime:a.mime,kind:'text',size:Buffer.from(a.data,'base64').length})),
      generated_at:new Date().toISOString()})};
  };
  load('recording.js',ctx);load('attachments.js',ctx);
  ctx.window.markdownit=require('./vendor/markdown-it.umd.min.js');
  load('markdown.js',ctx);load('chat.js',ctx);
  ctx.window.YincaiChat.render({replaceChildren(){}},{});
  api.click=dataset=>field('panel').onclick({target:{closest:()=>({dataset})}});
  api.text=value=>{
    const t=field('textarea');t.value=value;t.tagName='TEXTAREA';
    field('panel').oninput({target:t});
  };
  api.submit=()=>field('.cc-compose').onsubmit({preventDefault(){}});
  api.upload=async source=>{
    const picker=field('[data-files-picker]');picker.files=source;
    picker.onchange({target:picker});
    while(!field('.cc-file-error').hidden && field('.cc-file-error').textContent==='正在本机读取附件…')await tick();
  };
  return api;
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const raw='附件中的离线样例字符。';
const documentFile=()=>new File([raw],'样例.md',{type:'application/octet-stream'});

test('sending, failing, retrying and switching roles preserve the exact file message',async()=>{
  const saved=new Map(),app=setup(saved);
  await app.upload([documentFile()]);
  assert.match(app.field('.cc-files').innerHTML,/样例.md/);
  assert.match(app.field('.cc-file-notice').textContent,/offline-fixture.*云端/);
  app.click({person:'expert'});
  assert.equal(app.field('.cc-files').innerHTML,'');
  app.text('**独立问题**');app.submit();await tick();
  assert.equal(app.requests[0].role,'expert');
  assert.deepEqual(app.requests[0].attachments,[]);
  assert.match(app.field('.cc-log').innerHTML,/<strong>独立问题<\/strong>/);
  assert.match(app.field('.cc-log').innerHTML,/<strong>教师复核<\/strong>/);
  app.click({person:'analyst'});
  app.fail=true;app.submit();await tick();await tick();
  assert.equal(app.requests[1].message,'请结合附件给出备课建议。');
  assert.equal(app.requests[1].attachments[0].data,Buffer.from(raw).toString('base64'));
  assert.equal(app.requests[1].attachments[0].mime,'text/markdown');
  assert.match(app.field('.cc-log').innerHTML,/离线测试失败/);
  assert.match(app.field('.cc-files').innerHTML,/样例.md/);
  assert.ok(![...saved.values()].join('').includes(Buffer.from(raw).toString('base64')));
  assert.ok(![...saved.values()].join('').includes(raw));
  app.fail=false;app.click({cc:'retry'});await tick();await tick();
  assert.deepEqual(app.requests[2],app.requests[1]);
  assert.equal(app.field('.cc-files').innerHTML,'');
  assert.match(app.field('.cc-log').innerHTML,/cc-sent-file/);
  const restored=setup(saved);
  assert.match(restored.field('.cc-log').innerHTML,/<strong>教师复核<\/strong>/);
  assert.match(restored.field('.cc-log').innerHTML,/历史对话/);
});

test('reload requires an explicit matching file or removal; changed bytes start a new request',async()=>{
  const saved=new Map(),old=setup(saved,true);old.text('请分析');
  await old.upload([documentFile()]);old.submit();await tick();await tick();
  const id=old.requests[0].request_id;
  const restored=setup(saved);
  assert.match(restored.field('.cc-files').innerHTML,/请重新选择原文件/);
  assert.equal(restored.field('.cc-send').disabled,true);
  restored.submit();assert.equal(restored.requests.length,0);
  await restored.upload([new File(['changed'],'样例.md')]);
  assert.equal(restored.field('.cc-send').disabled,true);
  restored.click({removeFile:'0'});restored.submit();await tick();await tick();
  assert.notEqual(restored.requests[0].request_id,id);
  assert.equal(restored.requests[0].attachments[0].data,Buffer.from('changed').toString('base64'));
});

test('a successful re-selection after reload reuses the request identity with identical bytes',async()=>{
  const store=new Map(),app=setup(store,true);
  await app.upload([documentFile()]);app.submit();await tick();await tick();
  const again=setup(store);
  await again.upload([documentFile()]);again.submit();await tick();await tick();
  assert.deepEqual(again.requests[0],app.requests[0]);
});

test('invalid batch leaves the previous draft intact and thumbnails release their object URL',async()=>{
  const {ctx}=setup(),files=ctx.window.YincaiAttachments;
  const [doc]=await files.select([],[documentFile()]);
  await assert.rejects(files.select([doc],[new File(['A'],'new.md'),new File(['B'],'bad.exe')]),/支持/);
  await assert.rejects(files.select([],[new File([new Uint8Array(3*1024*1024+1)],'big.md')]),/3 MiB/);
  await assert.rejects(files.select([],[new File(['<xml/>'],'bad.png')]),/格式不符/);
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/wGUAAAAASUVORK5CYII=','base64');
  const [img]=await files.select([],[new File([png],'one.png')]);
  assert.match(files.thumbnail(img),/^blob:/);assert.equal(files.available(img),true);
  files.prune([doc]);assert.equal(files.available(img),false);assert.equal(files.thumbnail(img),'');
  assert.equal(files.available(doc),true);
});
