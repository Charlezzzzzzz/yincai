(() => {
'use strict';
const ids=['S1','S2','S3'];const aliases=['小川','小禾','小远'];const causes=['M2','M4','M1'];const cacheKeys=['plan_xiaoan','plan_xiaohe','plan_xiaoyuan'];const labels={pending:'待定',modified:'已修改',adopted:'已采纳',rejected:'已否决'};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const http=location.protocol!=='file:';
let host,active=0,editing=false,busy=false,draft='',version=null,notice='',loadState='preview',cycle=0;
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
 document.querySelectorAll('#main-nav [data-view]').forEach(b=>{b.disabled=blocked()&&b.dataset.view!=='teacher';b.title=b.disabled?'先保存或取消当前修改':'';});const p=plans[active],r=row(),ready=loadState==='ready';const proof=Array.isArray(p.evidence)?p.evidence:[];
 const pending=ready?records.filter(x=>x.action==='pending').length:loadState==='preview'?ids.length:null;
 const state=editing?'正在修改 · 尚未保存':ready?labels[r.action]:loadState==='loading'?'读取中':loadState==='preview'?'待定 · 离线预览':'状态待核实';
 const status=ready?'教师本机记录':loadState==='preview'?'离线预览 · 写入未启用':loadState==='loading'?'正在读取教师记录':'本机记录待重读';
 const bookmarks=ids.map((id,i)=>{
   const saved=records.find(record=>record.student_id===id);
   const statusLabel=ready?labels[saved.action]:loadState==='preview'?'待定 · 预览':'待读取';
   return `<button type="button" data-student="${i}" aria-pressed="${i===active}" aria-controls="review-paper" ${blocked()?'disabled':''}>
     <small>${String(i+1).padStart(2,'0')}</small><b>${aliases[i]}</b><span>${statusLabel}</span></button>`;
 }).join('');
 const actions=editing?
   `<button class="solid" data-save="modified" ${!ready||busy?'disabled':''}>保存修改</button><button class="quiet" data-cancel ${busy?'disabled':''}>取消</button>`:
   `<button class="adopt" data-save="adopted" ${!ready||busy?'disabled':''}>采纳</button>
    <button class="quiet" data-edit ${busy||loadState==='loading'?'disabled':''}>修改</button>
    <button class="quiet" data-save="rejected" ${!ready||busy?'disabled':''}>否决</button>
    ${ready&&r.action!=='pending'?'<button class="ink-link" data-save="pending" '+(busy?'disabled':'')+'>撤回决定</button>':''}`;
 const changed=r&&r.current!==r.original;
 const copyLabel=editing?'原位修改':changed?'教师修改稿':'教师助理建议 ○';
 const distribution=['M2','M1','M4','M3','M10'].map(key=>classroom.cause_distribution.find(item=>item.cause_id===key)).filter(Boolean);
 host.innerHTML=`<div class="reviewroom"><header class="review-top">
   <div><p class="review-kicker">任课教师 · 最终决定</p><h1>教师批阅</h1></div>
   <div class="review-count"><strong>${pending===null?'待审 — 条':'待审 '+pending+' 条'}</strong>
     <div class="review-progress" aria-hidden="true">${ids.map(id=>{
       const saved=ready&&records.find(item=>item.student_id===id);
       return '<i class="'+(saved&&saved.action!=='pending'?'reviewed':'')+'"></i>';
     }).join('')}</div><span>${esc(status)}</span></div></header>
   <nav class="bookmarks" aria-label="三份模拟学生建议">${bookmarks}</nav>
   <article class="review-paper" id="review-paper" aria-labelledby="review-title">
     <div class="review-main"><header class="review-heading">
       <p class="review-kicker">备课手记　/　${String(active+1).padStart(2,'0')}</p>
       <strong class="written-state ${ready&&r.action==='adopted'?'accepted':''}">${esc(state)}</strong>
       <h2 id="review-title">${aliases[active]}的教学建议</h2>
     </header>
     <section class="review-copy" aria-labelledby="copy-label"><h3 id="copy-label">${copyLabel}</h3>
       ${editing?`<label class="screen-reader" for="revision-text">教师建议修改稿</label><textarea id="revision-text" maxlength="12000" ${busy?'readonly':''}>${esc(draft)}</textarea>`:`<p>${esc(textBody())}</p>`}</section>
     ${active===2?'<p class="math-note">小远第三段微课的旁白与公式仍待复核。</p>':''}
     <footer class="decision-rail"><div class="decision-buttons" aria-label="教师决定">${actions}</div>
       <span>${ready?'仅保存到教师端':esc(status)}</span></footer>
     <div class="readback" role="status"><span>${esc(notice)}</span>${http&&!editing&&!busy?'<button class="ink-link" data-read>重新读取</button>':''}</div></div>
     <aside class="review-margin" aria-labelledby="review-evidence"><p class="review-kicker">□ 模拟学生 · ${aliases[active]}</p>
       <h3 id="review-evidence">批阅依据</h3>
       <p class="cause-line">${esc(causes[active])}　${active===2?'□ 模拟设定':'○ 诊断缓存'}</p>
       <h4>学情摘要 ○</h4><p class="margin-summary">${esc(p.teacher_summary)}</p>
       <details class="review-source" ${editing?'open':''}><summary>原建议与 ${proof.length} 条依据 ○</summary>
         <p>${esc(r?.original||p.recommendation)}</p><ul>${proof.map(item=>`<li>${esc(item)}</li>`).join('')}</ul></details>
       <details class="review-class"><summary>班级错因分布 □</summary>
         <p>模拟班级 ${esc(classroom.total_people)} 人，前三类错因共 ${esc(classroom.top_three_count)} 人。</p>
         <dl>${distribution.map(item=>`<div><dt>${esc(item.cause_id)}</dt><dd>${esc(item.count)} 人</dd></div>`).join('')}</dl></details>
     </aside>
   </article></div>`;
 host.querySelectorAll('[data-student]').forEach(b=>b.onclick=()=>{if(blocked())return;active=+b.dataset.student;notice='';paint();host.querySelector(`[data-student="${active}"]`)?.focus({preventScroll:true})});
 host.querySelector('[data-edit]')?.addEventListener('click',beginEdit);host.querySelector('[data-cancel]')?.addEventListener('click',()=>{editing=false;version=null;draft='';notice='已取消未保存的改动。';paint();host.querySelector('[data-edit]')?.focus({preventScroll:true})});
 host.querySelector('textarea')?.addEventListener('input',ev=>draft=ev.target.value);host.querySelectorAll('[data-save]').forEach(b=>b.onclick=()=>save(b.dataset.save));host.querySelector('[data-read]')?.addEventListener('click',()=>{notice='';refresh()});}
window.addEventListener('beforeunload',ev=>{if(blocked()){ev.preventDefault();ev.returnValue=''}});
window.YincaiReview={blocked,render(container){host=container;if(!blocked()&&http)refresh();else paint();}};
})();
