(() => {
'use strict';
const agents=[
 ['analyst','学情分析师','诊断','从模拟作答中提取错误步骤，给出错因和依据。',[1]],
 ['expert','学科专家','校验','核对算式、知识点与错因诊断。',[2]],
 ['designer','教学设计师','设计','将诊断转成教学策略、图示计划和迁移练习。',[3]],
 ['producer','多模态制作人','制作','根据教学策略写初稿，并按核查意见重做。',[4,6]],
 ['checker','核查员','核查','逐句核查讲解，标出答案泄露并审阅修订稿。',[5,7]],
 ['assistant','教师助理','交付','汇总经核查的材料，把建议和证据交给任课教师。',[8]]
];
const teachers=[['teacher-female','任课教师','女教师','逐条审阅、修改、采纳或否决建议，保有最终决定权。',[]],['teacher-male','任课教师','男教师','逐条审阅、修改、采纳或否决建议，保有最终决定权。',[]]];
const cast=[...agents,...teachers], names=['诊断','校验','设计','初稿','核查退回','修订','复核通过','交付'], roles=[0,1,2,3,4,3,4,5];
const defaultModel='checker';
const store={view:'cockpit',step:5,mss:4,flat:matchMedia('(max-width:720px), (prefers-reduced-motion:reduce)').matches,model:defaultModel,teacher:'teacher-female',round:526.8,records:{},modelHandle:null};
try{const saved=localStorage.getItem('yincai.teacher.appearance');if(teachers.some(t=>t[0]===saved))store.teacher=saved;}catch{}
function changeTeacher(id){if(!teachers.some(t=>t[0]===id))return;store.teacher=id;try{localStorage.setItem('yincai.teacher.appearance',id)}catch{}}
const work=document.querySelector('#work');
let roundtable;
let previousWorkspace='cover', currentWorkspace='cover';
const e=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=n=>String(n).padStart(2,'0');const src=n=>window.SOURCE['s'+num(n)];const rec=n=>store.records[num(n)]||window.EVIDENCE['s'+num(n)];const sec=n=>(src(n).ms/1000).toFixed(1);
function announce(msg){document.querySelector('#announce').textContent=msg;}
function modelImage(id){return 'models/'+id+'.png'}
function avatar(id){return id.startsWith('teacher-')?'models/'+id+'-avatar.png':'avatars/'+id+'.webp'}
function stopModel(){store.modelHandle?.dispose();store.modelHandle=null;}
function baseNav(view){document.querySelectorAll('#main-nav button').forEach(b=>{if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});}
function route(path,{top=true,push=true}={}){
 const [page,...parts]=path.split('/');
 const views=['cover','student','cockpit','teacher','chat','cast','settings'];
 const view=views.includes(page)?page:'cover';
 const role=view==='chat'&&parts.length===1&&agents.some(a=>a[0]===parts[0])?parts[0]:undefined;
 const castId=parts[0]==='teacher'?store.teacher:parts[0];
 const model=view==='cast'&&parts.length===1&&cast.some(a=>a[0]===castId)?castId:'';
 if(store.view==='teacher'&&view!=='teacher'&&window.YincaiReview?.blocked()){announce('请先保存或取消当前修改。');return false;}
 if(view==='settings'&&store.view!=='settings')previousWorkspace=currentWorkspace;
 if(store.view==='settings')window.YincaiSettings?.leave();
 if(store.view==='cover')window.YincaiCover?.leave();
 if(store.view==='cockpit' && view!=='cockpit')roundtable?.leave();
 if(store.view==='chat')window.YincaiChat?.leave();
 if(view==='cast')store.model=model||defaultModel;
 stopModel();store.view=view;baseNav(view);document.body.dataset.view=view;
 const requestedStep=view==='cockpit' && parts.length===1 && /^[1-8]$/.test(parts[0]) ? Number(parts[0]) : null;
 if(requestedStep){store.step=requestedStep;store.mss=store.step>=6?6:4;}
 const detail=view==='cockpit' ? store.step : model||role;
 currentWorkspace=view+(detail?'/'+detail:'');
 const hash='#'+currentWorkspace;
 if(location.hash!==hash){if(push)history.pushState(null,'',hash);else history.replaceState(null,'',hash);}
 document.title='因才 · '+({settings:'模型设置',cover:'教研工作台',chat:'智能体对话',teacher:'教师批阅',student:'学生研习',cast:'人物手册',cockpit:'协作圆桌'})[view];
 const settingsLink=document.querySelector('.model-settings-link');
 if(view==='settings')settingsLink.setAttribute('aria-current','page');else settingsLink.removeAttribute('aria-current');
 if(view==='settings'){
   window.YincaiSettings.render(work,()=>route(previousWorkspace));
 }else if(view==='cover'){
   window.YincaiCover.render(work,{enter:()=>route('cockpit/1'),chat:id=>route(agents.some(a=>a[0]===id)?'chat/'+id:'chat')});
 }else if(view==='chat'){
   window.YincaiChat.render(work,{role,openModel,openStep:n=>{
     if(!Number.isInteger(n)||n<1||n>8)return;
     store.step=n;if(n>=4&&n<=7)store.mss=n>=6?6:4;
     route('cockpit');
   },onRoleChange:id=>{
     currentWorkspace='chat/'+id;
     if(store.view==='chat'&&agents.some(a=>a[0]===id)&&location.hash!=='#chat/'+id)history.pushState(null,'','#chat/'+id);
   }});
 }else if(view==='student')window.YincaiStudent.render(work,{openCockpit:()=>{store.step=5;store.mss=4;route('cockpit')},openModel});
 else if(view==='teacher')window.YincaiReview.render(work);
 else if(view==='cast')renderCast();else renderCockpit();
 if(top)window.scrollTo(0,0);return true;
}
function openModel(id){route('cast/'+id);}
const transitions=['作答记录 → 错因诊断','诊断依据 → 学科校验','校验结论 → 教学策略','教学策略 → 讲解初稿','初稿泄露答案 → 退回制作人','退回意见 → 讲解修订稿','修订稿 → 核查通过','已复核材料 → 教师决定'];
function manuscripts(){const revised=store.mss===6,r=rec(store.mss),cause=rec(revised?7:5),leak='正确答案是13。'; const current=store.step;
 return `<article class="manuscript" aria-label="同段版本审阅"><div class="folio-heading"><div><span class="eyebrow">教案批注 ○</span><h2>${e(r.title)}</h2></div><div class="switch-pair" aria-label="教案版本"><button data-variant="4" aria-pressed="${!revised}">初稿</button><button data-variant="6" aria-pressed="${revised}">修订稿</button></div></div><div class="margin-grid"><section class="annotated"><h3>第 2 步 · 代入检验 <small>○ ${num(store.mss)} 制作人</small></h3><p>${e(r.steps[1].replace(/^2\.\s*代入检验[：:]/,'' )).replace(leak,`<mark>${leak}</mark>`)}</p>${revised?`<div class="counter"><del>${leak}</del> <small>演示用反例 · 04 初稿原句</small></div>`:'<div class="counter"><small>演示用反例 · 初稿直接泄露答案</small></div>'}</section><aside class="proof"><span class="proof-index">${revised?'②':'①'}</span><div><h3>${revised?'07 复核通过':'05 核查退回'}　○ <small>${sec(revised?7:5)} 秒</small></h3><p>${e(cause.reason)}</p></div></aside></div><div class="folio-acts"><button class="ink-link" data-variant="${revised?4:6}">${revised?'对照被退回的原句':'对照修订后的同一句'}　⇄</button><button class="ink-link" data-step="${current===7?8:revised?7:6}">${current===7?'查看交付':revised?'进入复核':'移交制作人'}　→</button></div><details class="transcript"><summary>教案全文与旁白　○</summary><div><h3>教学步骤 ○</h3>${r.steps.map(t=>`<p>${e(t).replace(leak,'<mark>'+leak+'</mark>')}</p>`).join('')}<h3>语音旁白 ○ ${!revised?'· 含演示用反例':''}</h3><p>${e(r.voiceover).replace('正确答案是13哦。','<mark>正确答案是13哦。</mark>')}</p><h3>摘要与说明 ○</h3><p>${e(r.summary)}</p><p>${e(r.student_safe_diagnosis)}</p><h3>图示计划 ○</h3>${r.visual_plan.map(t=>`<p>${e(t)}</p>`).join('')}<h3>迁移练习 ○</h3><p>${e(r.migration_question)}</p></div></details></article>`;
}
function plainRecord(){const n=store.step,r=rec(n);const fields=n===1?[['错因',r.misconception_id],['诊断依据',r.evidence],['学习状态',r.learner_state]]:n===2?[['校验',r.valid?'通过':'待复核'],['学科依据',r.evidence],['涉及的知识点',r.knowledge_points]]:n===3?[['策略名称',r.strategy_name],['选择依据',r.rationale],['教学步骤',r.steps],['媒体形式',r.media_form]]:[['教学建议',r.recommendation],['学情摘要',r.teacher_summary],['依据',r.evidence]];
 const asText=v=>Array.isArray(v)?v.join('　·　'):typeof v==='object'?Object.values(v).join('　·　'):v;
 return `<article class="manuscript trace-text"><div class="folio-heading"><div><span class="eyebrow">${agents[roles[n-1]][1]}　○ ${sec(n)} 秒</span><h2>${n===8?'送交教师的教学建议':transitions[n-1].split(' → ')[1]}</h2></div>${n===8?'<button class="solid" data-view="teacher">交给任课教师　→</button>':''}</div>${fields.map(([k,v])=>`<section><h3>${k} ○</h3><p>${e(asText(v))}</p></section>`).join('')}</article>`;}
function handoffDescription(n){
 const event=store.handoffs?.[n-1];if(!event)return '';
 const name=id=>agents.find(a=>a[0]===id)?.[1]||'任课教师';
 return `<p><b>交接记录 ${num(event.seq)}</b>　${e(name(event.sender))} → ${e(name(event.recipient))}　·　${e(event.stage)}</p><small>□ 岗位流向按八步规则　·　○ 真实缓存　·　文件 SHA-256</small><code>${e(event.file_sha256)}</code>`;
}
function quoteForStep(n) {
 const record=rec(n);
 switch(n) {
   case 1: case 2: return record.evidence.split('。')[0]+'。';
   case 3: return record.strategy_name;
   case 4: return record.steps[1].match(/[^。]+。?$/)?.[0] || record.steps[1];
   case 5: case 7: return record.reason.split('。')[0]+'。';
   case 6: return record.steps[1];
   case 8: return record.recommendation;
 }
}
function dossier() {
 const n=store.step;
 return (n>=4 && n<=7 ? manuscripts() : plainRecord()) +
   `<details class="provenance"><summary>本步缓存记录与来源 ○</summary>
   <p>${e(src(n).model)}　·　${sec(n)} 秒</p>
   <small>模拟学生姓名使用当前展示名，来源文件保留生成时的记录。</small>
   ${handoffDescription(n)}<code>${e(src(n).file)}</code><pre>${e(JSON.stringify(rec(n),null,2))}</pre></details>`;
}
function renderCockpit() {
 if (!roundtable) {
   const steps=names.map((stage,i)=>({
     seq:i+1, stage, sender:agents[roles[i]][0],
     recipient:i===7?'teacher':agents[roles[i+1]][0]
   }));
   const labels=Object.fromEntries(agents.map(([id,name])=>[id,name]));
   labels.teacher='任课教师';
   roundtable=window.YincaiRoundtable.create({
     steps,names:labels,getQuote:quoteForStep,elapsed:()=>store.round,
     onStep:setStep,renderDetail:dossier,initialFlat:matchMedia('(prefers-reduced-motion: reduce)').matches
   });
 }
 roundtable.mount(work,store.step);
}
function setStep(n,focus) {
 if(!Number.isInteger(n)||n<1||n>8)return;
 store.step=n;
 if(n>=4&&n<=7)store.mss=n>=6?6:4;
 currentWorkspace='cockpit/'+n;
 history.replaceState(null,'','#'+currentWorkspace);
 renderCockpit();
 if(focus) work.querySelector(focus)?.focus({preventScroll:true});
 announce(`${num(n)} ${names[n-1]} · ${agents[roles[n-1]][1]}`);
}
function renderCast(){stopModel();const index=cast.findIndex(a=>a[0]===store.model),[id,name,job,desc,steps]=cast[index];const human=id.startsWith('teacher');if(human)changeTeacher(id);
 work.innerHTML=`<div class="wrap castroom"><div class="page-top"><div><span class="eyebrow">六个智能体　/　一位任课教师 · 两款形象</span><h1>人物手册</h1></div></div><div class="sculpture-ground"><div class="sculpture-view"><div class="turn-ring" aria-hidden="true"></div><img class="standin" src="${modelImage(id)}" alt="${name}的 Q 版模型渲染"><canvas id="gl-model" tabindex="0" aria-label="${name}三维模型，拖动或方向键旋转"></canvas><div class="rotate-keys"><button data-rot="-25" aria-label="向左旋转">↶</button><button data-zoom="1.15" aria-label="放大模型">＋</button><button data-zoom="0.87" aria-label="缩小模型">−</button><button data-rot="25" aria-label="向右旋转">↷</button><button data-reset>复位</button></div></div><div class="casting-notes"><span class="eyebrow">${human?'人工教师':'教研智能体'}　/　${job}${id==='assistant'?'　/　男生':''}</span><h2>${name}</h2><p class="role-desc">${desc}</p><div class="likeness"><img src="${avatar(id)}" alt="${name}对应头像"><div><b>${human?'同款正面头像':'原设头像'}</b><small>${human?'任课教师 · 原创角色':'角色原稿与 Q 版模型对照'}</small></div></div><p id="model-status" role="status">正在载入模型…</p><div class="cast-acts">${human?'':`<button class="solid" data-view="chat/${id}">与${name}对话</button>`}<a class="ink-link" href="models/${id}.glb" download>下载此角色 GLB　↓</a>${steps.length?`<button class="ink-link" data-duty="${steps[0]}">进入经手步骤 ${steps.map(num).join(' / ')}　→</button>`:'<button class="ink-link" data-view="teacher">进入教师批阅　→</button>'}</div></div></div><nav class="casting-strip" aria-label="选择三维角色">${cast.map(a=>`<button data-cast="${a[0]}" aria-pressed="${id===a[0]}"><img src="${avatar(a[0])}" alt=""><span>${a[0].startsWith('teacher')?a[2]:a[1]}</span></button>`).join('')}</nav></div>`;
 const canvas=document.querySelector('#gl-model'),container=canvas.parentElement,status=document.querySelector('#model-status');const keys=container.querySelector('.rotate-keys');keys.querySelectorAll('button').forEach(b=>b.disabled=true);
 store.modelHandle=window.YincaiViewer.mount(canvas,{src:'models/'+id+'.glb',onReady:()=>{container.classList.add('ready');keys.querySelectorAll('button').forEach(b=>b.disabled=false);status.textContent='三维模型 · 拖动或使用方向键旋转';canvas.dataset.render='webgl'},onError:()=>{container.classList.remove('ready');canvas.dataset.render='image';status.textContent=location.protocol==='file:'?'静态造型 · 启动本地工作台后可旋转':'静态造型 · 当前设备未能显示 WebGL';keys.querySelectorAll('button').forEach(b=>b.disabled=true)}});
}
function action(ev){const b=ev.target.closest('button');if(!b)return;if(b.dataset.view){route(b.dataset.view);return;}if(b.hasAttribute('data-pass')){advance();return;}if(b.dataset.openModel){openModel(b.dataset.openModel);return;}if(b.dataset.step&&b.closest('#dossier-content')){setStep(+b.dataset.step);return;}if(b.dataset.variant){const variant=+b.dataset.variant;setStep(variant===4?5:6,`.switch-pair [data-variant="${variant}"]`);return;}if(b.dataset.cast){if(route('cast/'+b.dataset.cast,{top:false}))work.querySelector(`[data-cast="${store.model}"]`).focus({preventScroll:true});return;}if(b.dataset.duty){route('cockpit');setStep(+b.dataset.duty);return;}if(b.dataset.rot)store.modelHandle?.rotate(+b.dataset.rot);if(b.dataset.zoom)store.modelHandle?.zoom(+b.dataset.zoom);if(b.hasAttribute('data-reset'))store.modelHandle?.reset();}
function advance(){if(store.step===8)route('teacher');else setStep(store.step+1,store.step===7?'#teacher':'[data-pass]');}
work.addEventListener('dragstart',event=>{
 const slip=event.target.closest('[data-pass]');
 if(!slip)return;
 event.dataTransfer.setData('text/plain','因才文稿-'+store.step);
 event.dataTransfer.effectAllowed='move';
 const target=store.step<8?roundtable.dropTarget(agents[roles[store.step]][0]):document.querySelector('#main-nav [data-view="teacher"]');
 target?.classList.add('drop-target');
});
document.addEventListener('dragover',event=>{if(event.target.closest('.drop-target')){event.preventDefault();event.dataTransfer.dropEffect='move'}});
document.addEventListener('drop',event=>{if(event.target.closest('.drop-target')&&event.dataTransfer.getData('text/plain')==='因才文稿-'+store.step){event.preventDefault();document.querySelector('.drop-target')?.classList.remove('drop-target');advance();}});
document.addEventListener('dragend',()=>document.querySelector('.drop-target')?.classList.remove('drop-target'));
document.addEventListener('click',action);document.querySelector('.signature').addEventListener('click',ev=>{ev.preventDefault();route('cover')});window.addEventListener('hashchange',()=>{if(!route(location.hash.slice(1),{push:false}))history.replaceState(null,'','#teacher')});
route(location.hash.slice(1),{push:false});
if(location.protocol!=='file:')fetch('/api/cockpit/comparison').then(r=>{if(!r.ok)throw Error();return r.json()}).then(data=>{const p=data.protocol;if(p?.steps&&Object.keys(p.steps).length===8&&Number.isFinite(p.cache_round_elapsed_seconds)){store.handoffs=data.handoffs;store.records=p.steps;store.round=p.cache_round_elapsed_seconds;if(store.view==='cockpit')renderCockpit();}}).catch(()=>{});
})();
