(() => {
'use strict';
const ids=['S1','S2','S3'];const aliases=['小川','小禾','小远'];const causes=['M2','M4','M1'];const cacheKeys=['plan_xiaoan','plan_xiaohe','plan_xiaoyuan'];const labels={pending:'待定',modified:'已修改',adopted:'已采纳',rejected:'已否决'};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const http=location.protocol!=='file:';
let host,options,active=0,editing=false,busy=false,draft='',version=null,notice='',loadState='preview',cycle=0;
let records=[],plans=cacheKeys.map(k=>window.EVIDENCE[k]);
let classroom={total_people:30,top_three_count:23,cause_distribution:[['M2',8],['M1',8],['M4',7],['M3',4],['M10',3]].map(([cause_id,count])=>({cause_id,count}))};
function blocked(){return editing||busy;}
function row(){return records.find(r=>r.student_id===ids[active]);}
function isHere(){return host&&document.body.dataset.view==='teacher'}
function textBody(){return row()?.current??plans[active].recommendation}
async function request(path,init={}){const res=await fetch(path,{cache:'no-store',...init});if(!res.ok){let msg='服务响应 '+res.status;try{const d=await res.json();if(typeof d.detail==='string')msg=d.detail}catch{}const err=new Error(msg);err.status=res.status;throw err;}return res.json();}
async function refresh(){
 if(blocked()||!http)return;
 const ticket=++cycle;loadState='loading';paint();
 try{const [saved,overview]=await Promise.all([request('/api/v7/reviews'),request('/api/teacher/overview')]);
 if(ticket!==cycle)return;
 if(!saved.teacher_only||!ids.every(id=>saved.reviews.some(r=>r.student_id===id)&&overview.plans.some(p=>p.student_id===id)))throw Error('审阅记录不完整');
 classroom=overview.classroom;records=saved.reviews;plans=ids.map(id=>overview.plans.find(p=>p.student_id===id));loadState='ready';}
 catch(err){if(ticket!==cycle)return;loadState='failed';notice='未能读取本机审阅记录。请重试。';}
 if(isHere())paint();}
function beginEdit(){if(busy||editing)return;version=row()?{hash:row().source_hash,rev:row().revision}:null;draft=textBody();editing=true;notice='';paint();host.querySelector('textarea').focus({preventScroll:true});}
async function save(action){
 if(busy||loadState!=='ready'||!row())return;
 if(action==='modified'&&!draft.trim()){notice='请先填写修改后的建议。';paint();host.querySelector('textarea')?.focus();return;}
 const original=row(),idx=active;const expected=action==='modified'?version:{hash:original.source_hash,rev:original.revision};
 if(!expected)return;busy=true;notice='正在核对本机记录…';paint();
 const payload={student_id:ids[idx],source_hash:expected.hash,expected_revision:expected.rev,action};if(action==='modified')payload.current=draft;
 let receipt;
 try{
  receipt=(await request('/api/v7/reviews',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})).review;
  const saved=await request('/api/v7/reviews');const result=saved.reviews.find(r=>r.student_id===ids[idx]);
  if(!saved.teacher_only||result?.revision!==receipt.revision||result.source_hash!==receipt.source_hash||result.action!==action||result.current!==receipt.current)throw Error('最新记录与写入回执不一致');
  records=saved.reviews;editing=false;version=null;draft='';notice=aliases[idx]+' · '+labels[action]+'，已从教师本机记录读回。';
  if(action==='adopted'||action==='rejected'){const others=[...ids.slice(idx+1),...ids.slice(0,idx)];const next=others.find(id=>records.find(r=>r.student_id===id)?.action==='pending');if(next)active=ids.indexOf(next);}
 }catch(err){
  if(err.status===409||receipt){notice=(receipt?'收到写入回执，但未能核对最新记录。':'该建议已由其他窗口更新。')+(editing?'当前草稿已保留，可先复制后取消，再重读。':'请重新读取记录。');loadState='stale';}
  else notice='未确认保存。'+err.message+'。'+(editing?'当前草稿已保留。':'');
 }finally{busy=false;paint();}
}
function paint(){if(!isHere())return;
 document.querySelectorAll('#main-nav [data-view]').forEach(b=>{b.disabled=blocked()&&b.dataset.view!=='teacher';b.title=b.disabled?'先保存或取消当前修改':'';});const p=plans[active],r=row(),ready=loadState==='ready';const proof=Array.isArray(p.evidence)?p.evidence:[];const lady=options.teacher==='teacher-female';
 const pending=ready?records.filter(x=>x.action==='pending').length:3;
 const state=editing?'正在修改 · 尚未保存':ready?labels[r.action]:loadState==='loading'?'读取中':loadState==='preview'?'待定 · 离线预览':'状态待核实';
 const status=ready?'教师本机记录':loadState==='preview'?'离线预览 · 写入未启用':loadState==='loading'?'正在读取教师记录':'本机记录待重读';
 host.innerHTML=`<div class="wrap reviewroom"><div class="page-top"><div><span class="eyebrow">□ 模拟班级 · ${esc(classroom.total_people)} 人　/　主要错因属前三类 ${esc(classroom.top_three_count)} 人</span><h1>教师批阅</h1></div><span class="toolbar">${esc(status)}</span></div><section class="teacher-desk" aria-label="任课教师批阅桌"><div class="teacher-intro"><span class="eyebrow">人工决定</span><h2>任课教师</h2><div class="teacher-outfits" aria-label="教师外观"><button data-look="teacher-female" aria-pressed="${lady}">女教师</button><button data-look="teacher-male" aria-pressed="${!lady}">男教师</button></div><button data-show-teacher class="ink-link" ${blocked()?'disabled':''}>查看 Q 版模型　↗</button></div><div class="human-image"><img id="teacher-puppet" src="models/${esc(options.teacher)}.png" alt="任课教师的Q版形象"></div><div class="review-ledger"><span class="eyebrow">建议审阅进度</span><strong>${ready||loadState==='preview'?String(3-pending).padStart(2,'0'):'—'}<small> / 03</small></strong><span>${ready||loadState==='preview'?'待定 '+pending+' 条':esc(state)}</span></div></section>
 <nav class="bookmarks" aria-label="逐条建议">${ids.map((id,i)=>{const saved=records.find(x=>x.student_id===id);return `<button data-student="${i}" aria-pressed="${i===active}" ${blocked()?'disabled':''}><small>${String(i+1).padStart(2,'0')}</small> ${aliases[i]} □ <span>${ready?labels[saved?.action]:(loadState==='preview'?'待定 · 预览':'待读取')}</span></button>`}).join('')}</nav>
 <article class="review-leaf"><div class="review-heading"><div><span class="eyebrow">${active+1} / 3　·　教师助理建议 ○</span><h2>${aliases[active]}的教学建议</h2><p>${aliases[active]} □　·　针对 ${causes[active]} ${active===2?'□ 模拟设定':'○ 诊断缓存'}</p></div><strong class="written-state ${ready&&r.action==='adopted'?'accepted':''}">${esc(state)}</strong></div>
 ${active===2?'<p class="math-note">小远第三段微课的旁白与公式仍待复核。</p>':''}<section class="review-copy"><h3>${editing?'原位修改':ready&&r.action==='modified'?'当前教师稿':'当前建议'} ${editing?'':r&&r.current!==r.original?'· 教师编辑':'○'}</h3>${editing?`<label class="screen-reader" for="revision-text">教师建议修改稿</label><textarea id="revision-text" maxlength="12000" ${busy?'readonly':''}>${esc(draft)}</textarea>`:`<p>${esc(textBody())}</p>`}</section>
 <details class="review-source" ${editing?'open':''}><summary>原建议与 ${proof.length} 条依据 ○</summary><p>${esc(r?.original||p.recommendation)}</p><h3>学情摘要 ○</h3><p>${esc(p.teacher_summary)}</p><ul>${proof.map(s=>`<li>${esc(s)}</li>`).join('')}</ul></details>
 <div class="decision-rail">${editing?`<button class="solid" data-save="modified" ${!ready||busy?'disabled':''}>保存修改</button><button class="quiet" data-cancel ${busy?'disabled':''}>取消</button>`:`<button class="adopt" data-save="adopted" ${!ready||busy?'disabled':''}>采纳</button><button class="quiet" data-edit ${busy||loadState==='loading'?'disabled':''}>修改</button><button class="quiet" data-save="rejected" ${!ready||busy?'disabled':''}>否决</button>${ready&&r.action!=='pending'?'<button class="ink-link" data-save="pending" '+(busy?'disabled':'')+'>撤回决定</button>':''}`}<span>${ready?'仅保存到教师端':esc(status)}</span></div>
 <div class="readback" role="status">${esc(notice)} ${http&&!editing&&!busy?'<button class="ink-link" data-read>重新读取</button>':''}</div></article><details class="provenance"><summary>班级错因分布 □</summary><p>${['M2','M1','M4','M3','M10'].map(key=>classroom.cause_distribution.find(item=>item.cause_id===key)).filter(Boolean).map(item=>esc(item.cause_id)+'　'+esc(item.count)+' 人').join('　·　')}</p></details></div>`;
 options.drawFigure?.(host.querySelector('.human-image'),options.teacher);
 host.querySelectorAll('[data-look]').forEach(b=>b.onclick=()=>{const id=b.dataset.look;options.teacher=id;options.onAppearance(id);host.querySelector('#teacher-puppet').src='models/'+id+'.png';host.querySelector('.human-image').classList.remove('has-mesh');options.drawFigure?.(host.querySelector('.human-image'),id);host.querySelectorAll('[data-look]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));});
 host.querySelector('[data-show-teacher]').onclick=()=>options.openModel(options.teacher);
 host.querySelectorAll('[data-student]').forEach(b=>b.onclick=()=>{if(blocked())return;active=+b.dataset.student;notice='';paint();host.querySelector(`[data-student="${active}"]`)?.focus({preventScroll:true})});
 host.querySelector('[data-edit]')?.addEventListener('click',beginEdit);host.querySelector('[data-cancel]')?.addEventListener('click',()=>{editing=false;version=null;draft='';notice='已取消未保存的改动。';paint();host.querySelector('[data-edit]')?.focus({preventScroll:true})});
 host.querySelector('textarea')?.addEventListener('input',ev=>draft=ev.target.value);host.querySelectorAll('[data-save]').forEach(b=>b.onclick=()=>save(b.dataset.save));host.querySelector('[data-read]')?.addEventListener('click',()=>{notice='';refresh()});}
window.addEventListener('beforeunload',ev=>{if(blocked()){ev.preventDefault();ev.returnValue=''}});
window.YincaiReview={blocked,render(container,settings){host=container;options=settings;if(!blocked()&&http)refresh();else paint();}};
})();
