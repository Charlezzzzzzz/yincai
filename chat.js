/* The browser keeps one private conversation per role for the lifetime of this tab. */
(() => {
  'use strict';

  const people = [
    {id:'analyst', name:'学情分析师', duty:'学情诊断', prompt:'小川去分母时漏乘了哪一项？', next:'如何判断这是漏乘而不是移项错误？', steps:[1]},
    {id:'expert', name:'学科专家', duty:'学科校验', prompt:'如何检验同乘 6 后的等式？', next:'能逐项解释等式两边的变化吗？', steps:[2]},
    {id:'designer', name:'教学设计师', duty:'教学设计', prompt:'能设计一个不直接给出答案的追问吗？', next:'怎样把这个追问改成一道迁移练习？', steps:[3]},
    {id:'producer', name:'多模态制作人', duty:'初稿与修订', prompt:'怎样把代入检验讲成一句微课旁白？', next:'把这句旁白改成学生可以自己操作的指令。', steps:[4,6]},
    {id:'checker', name:'核查员', duty:'核查与复核', prompt:'为什么第 4 步的初稿被退回？', next:'修订之后，哪些地方还要再核查？', steps:[5,7]},
    {id:'assistant', name:'教师助理', duty:'整理与交付', prompt:'这份教案有哪些决定需要任课教师来做？', next:'帮我整理一份课前复核清单。', steps:[8]}
  ];
  const steps = [
    ['诊断','evidence'],['校验','evidence'],['设计','rationale'],['初稿 · 泄露答案演示反例','summary'],
    ['核查退回','reason'],['修订','summary'],['复核通过','reason'],['交付教师','recommendation']
  ];
  const byId = Object.fromEntries(people.map(p => [p.id,p]));
  const recording=window.YincaiRecording;
  const storageKey='yincai.v8.role-dialogues.1'+(recording.enabled?'.recording':''), limit=2000;
  const emptyThread = () => ({id:null, draft:'', turns:[], flight:false});
  const threads = Object.fromEntries(people.map(p => [p.id,emptyThread()]));
  let selected='analyst', panel=null, hooks={}, service=null, serviceCheck=null, showConnection=false;
  const allowed = new Set(['waiting','failed','live','expired']);
  const escape = v => String(v??'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const uuid = () => crypto.randomUUID();
  const current=()=>threads[selected];
  const q=s=>panel?.querySelector(s);
  const avatar=(id,cls='')=>`<img class="cc-avatar ${cls}" src="avatars/${id}.webp" alt="" width="48" height="48">`;
  function restore() {
    try {
      const data=JSON.parse(sessionStorage.getItem(storageKey)||'{}');
      if (byId[data.selected]) selected=data.selected;
      for (const {id} of people) {
        const s=data.threads?.[id]; if(!s || !Array.isArray(s.turns))continue;
        const t=threads[id];t.id=typeof s.id==='string'?s.id:null;
        t.draft=typeof s.draft==='string'?s.draft.slice(0,limit):'';
        t.turns=s.turns.slice(-50).filter(v=>v && typeof v.key==='string' && typeof v.text==='string' && allowed.has(v.state));
        for(const turn of t.turns) {
          if(turn.state==='live')turn.restored=true;
          if(turn.state==='waiting'){
            turn.state='failed';turn.error='页面已重新载入，请重试以核对这次请求。';
            if(!t.draft)t.draft=turn.text;
          }
        }
      }
    } catch { /* Storage can be unavailable in private contexts. */ }
  }
  function persist(){
    try{ sessionStorage.setItem(storageKey,JSON.stringify({selected,threads})); }catch{}
  }
  const handoffTargets = {analyst:['expert'],expert:['designer'],designer:['producer'],
    producer:['checker'],checker:['producer','assistant'],assistant:[]};
  const memoryKey = id => 'yincai.v82.conversation.'+(recording.enabled?'recording.':'')+id;
  const loadingMemory = new Set();
  async function recover(id){
    const t=threads[id];
    if(t.id || t.turns.length || t.flight || loadingMemory.has(id))return;
    let cid;
    try{cid=(recording.enabled?sessionStorage:localStorage).getItem(memoryKey(id));}catch{return;}
    if(!cid || !/^[a-f0-9-]{36}$/.test(cid))return;
    loadingMemory.add(id);
    try{
      const res=await fetch('/api/chat/history/'+id+'/'+cid,{cache:'no-store'});
      if(!res.ok)return;
      const history=await res.json();
      if(t.id || t.turns.length || t.flight || history.role!==id || history.conversation_id!==cid)return;
      t.id=cid;
      t.turns=history.turns.map(row=>({key:row.request_id,text:row.question,reply:row.reply,
        completed:Date.parse(row.generated_at),when:Date.parse(row.generated_at),model:row.model,vendor:row.vendor,elapsed_ms:row.elapsed_ms,
        state:'live',restored:true,handoffRole:row.handoff?.from,handoffFrom:row.handoff?.source_request_id}));
      persist();refreshThread(id);
    } catch { /* Existing local draft stays usable when the server is offline. */ }
    finally { loadingMemory.delete(id); }
  }
  function handoffButtons(role,turn){
    return handoffTargets[role].map(to=>`<button type="button" class="cc-text-action" data-handoff="${to}"
      data-receipt="${escape(turn.key)}" ${threads[to].flight||!recording.canSend()?'disabled':''}>请${byId[to].name}接续 ↗</button>`).join('');
  }
  async function handoff(to, key){
    const sender=selected, origin=current().turns.find(turn=>turn.key===key && turn.state==='live');
    if(!origin || !recording.canSend() || !handoffTargets[sender].includes(to))return;
    const dest=threads[to];
    if(dest.flight)return;
    await recover(to);
    if(dest.flight || selected!==sender || !panel?.isConnected)return;
    const text='请按你的岗位审阅这条转交的回复，提出下一步建议。';
    const turn={key:uuid(),text,when:Date.now(),state:'waiting',handoffRole:sender,handoffFrom:key};
    dest.turns.push(turn);if(dest.turns.length>50)dest.turns.shift();
    selected=to;showConnection=false;showThread();hooks.onRoleChange?.(to);
    transmit(to,turn);
  }
  function time(value){
    return new Date(value).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false});
  }
  function receipt(turn){
    const vendors={ollama:'本机 Ollama',openai:'OpenAI',google:'Google',anthropic:'Anthropic',deepseek:'DeepSeek',
      qwen:'阿里云百炼',moonshot:'月之暗面',zhipu:'智谱',volcengine:'火山方舟',minimax:'MiniMax',custom:'自定义兼容接口'};
    const parts=[turn.replayed?'○ 先前生成 · 回执':turn.restored?'○ 历史对话 · 原为实时生成':'● 实时生成',
      vendors[turn.vendor] || turn.vendor,turn.model];
    if(Number.isFinite(turn.elapsed_ms) && turn.elapsed_ms >= 0)parts.push((turn.elapsed_ms/1000).toFixed(2)+' 秒');
    parts.push(time(turn.completed));
    return escape(parts.filter(Boolean).join(' · '));
  }
  function serviceName(){
    if(!service) return serviceCheck?'正在检查连接':'连接设置';
    if(service.configured)return '已配置 · '+(service.model||'模型 API');
    return service.provider==='unavailable'?'服务未连接':'模型待连接';
  }
  function connectionBody(){
    return `<div class="cc-settings-copy"><b>${escape(serviceName())}</b><p>${escape(service?.message||'检查本机工作台的模型配置。')}</p>
      <p>在模型设置中选择本机或云端服务、填写模型并测试连接。</p>
      <button type="button" class="cc-text-action" data-view="settings">打开模型设置 ↗</button>
      <button type="button" class="cc-text-action" data-cc="refresh">${serviceCheck?'正在检查…':'重新检查连接'}</button></div>`;
  }
  function updateConnection(){
    const button=q('[data-cc="settings"]');if(!button)return;
    const destination=q('[data-chat-destination]');
    if(destination)destination.textContent=recording.enabled?recording.status():service?.provider==='ollama'?'仅教师可见 · 本机模型':service?.provider==='compatible'?'教师私有 · 经所配置的 API 处理':'教师对话';
    button.textContent=serviceName();button.setAttribute('aria-expanded',String(showConnection));
    const box=q('.cc-settings');box.hidden=!showConnection;
    if(showConnection)box.innerHTML=connectionBody();
  }
  async function checkService(){
    if(serviceCheck)return serviceCheck;
    serviceCheck=(async()=>{
      try{
        const r=await fetch('/api/chat/status',{cache:'no-store'});
        if(!r.ok)throw Error();
        const d=await r.json();
        if(typeof d.configured!=='boolean')throw Error();
        service=d;
      }catch{ service={provider:'unavailable',configured:false,message:'请通过本机启动脚本打开工作台，并检查模型服务。'}; }
    })();
    updateConnection();try{await serviceCheck;}finally{serviceCheck=null;updateConnection();}
  }
  function roster(){
    const nav=q('.cc-roster'); if(!nav)return;
    nav.innerHTML=people.map(p=>{
      const t=threads[p.id], last=t.turns.at(-1);
      const subtitle=t.flight?'等待模型回复…':last?.state==='failed'||last?.state==='expired'?'上次请求待处理':last?.state==='live'?last.reply:p.duty;
      return `<button type="button" data-person="${p.id}" aria-pressed="${selected===p.id}">${avatar(p.id)}
      <span class="cc-person"><strong>${p.name}</strong><small>${escape(subtitle)}</small></span><span class="cc-active-mark" aria-hidden="true"></span></button>`;
    }).join('');
  }
  function evidence(id){
    return byId[id].steps.map(n=>{
      const key='s'+String(n).padStart(2,'0'), r=window.EVIDENCE?.[key], source=window.SOURCE?.[key];
      if(!r || !source || typeof r[steps[n-1][1]]!=='string')return '';
      return `<div class="cc-evidence-line"><div><b>${String(n).padStart(2,'0')}　${steps[n-1][0]}</b><small>○ 真实缓存 · ${(source.ms/1000).toFixed(1)} 秒</small></div>
        <p>${escape(r[steps[n-1][1]])}</p><button type="button" data-step-link="${n}" class="cc-text-action">回看这一步　↗</button></div>`;
    }).join('');
  }
  function threadMarkup(){
    const p=byId[selected];
    return `<section class="cc-conversation" aria-label="与${p.name}对话"><header class="cc-contact">
      <button type="button" class="cc-open-model" data-cc="model" aria-label="查看${p.name}的三维形象">${avatar(p.id)}</button>
      <div class="cc-contact-name"><h2>${p.name}</h2><small>${p.duty}${p.id==='assistant'?' · 男生':''}</small></div>
      <button type="button" class="cc-record-btn" data-cc="record" aria-expanded="false">○ 协作记录</button></header>
      <div class="cc-evidence" hidden>${evidence(p.id)}</div><div class="cc-log" role="log" aria-label="消息记录" aria-live="polite" aria-relevant="additions text"></div>
      <form class="cc-compose"><div class="cc-entry"><textarea aria-label="给${p.name}写消息" rows="1" maxlength="${limit}" placeholder="给${p.name}发消息…"></textarea>
        <button class="cc-send" type="submit" aria-label="发送消息" title="发送消息"><span aria-hidden="true">↑</span></button></div>
      <div class="cc-compose-foot"><span data-chat-destination>教师对话</span><span>Enter 发送 · Shift + Enter 换行</span></div></form></section>`;
  }
  function chatLog(){
    const p=byId[selected],t=current(),log=q('.cc-log');if(!log)return;
    if(!t.turns.length){
      log.innerHTML=`<section class="cc-quiet"><div class="cc-portrait">${avatar(p.id)}</div>
        <h3>与${p.name}聊聊</h3><p>输入自己的问题，或从下面的问题开始。</p>
        <button type="button" data-cc="prompt">${escape(p.prompt)} <span aria-hidden="true">↗</span></button></section>`;
      return;
    }
    log.innerHTML=t.turns.map((turn,i)=>{
      let reply='';
      if(turn.state==='live')reply=`<div class="cc-in">${avatar(p.id)}<div><div class="cc-bubble cc-answer" dir="auto">${escape(turn.reply)}</div>
        ${/(?:23|二十三)\s*(?:名|位|人)|(?:前|排名)\s*(?:23|二十三)/.test(turn.reply) ? '<p class="cc-case-note">□ 模拟班级口径：全班 30 人，前三类错因合计涉及 23 人。</p>' : ''}
        <small class="cc-meta" data-model-receipt>${receipt(turn)}</small><div class="cc-handoffs">${handoffButtons(p.id,turn)}</div></div></div>`;
      else if(turn.state==='waiting')reply=`<div class="cc-in">${avatar(p.id)}<div><div class="cc-typing" aria-hidden="true"><i></i><i></i><i></i></div><small class="cc-meta">正在等待模型回复</small></div></div>`;
      else reply=`<div class="cc-error" role="status"><strong>${turn.state==='expired'?'会话已过期':'未收到回复'}</strong><span>${escape(turn.error)}</span>${i===t.turns.length-1?`<div><button type="button" data-cc="retry" ${recording.canSend()?'':'disabled'}>${turn.state==='expired'?'在新会话重试':'重试'}</button><button type="button" data-cc="revise">编辑问题</button><button type="button" data-cc="settings">连接设置</button></div>`:''}</div>`;
      return `<div class="cc-turn">${turn.fresh?'<div class="cc-divider">新会话</div>':''}<div class="cc-out">${turn.handoffRole&&byId[turn.handoffRole]?`<small class="cc-meta">转自${byId[turn.handoffRole].name} · 先前生成的回复 ○</small>`: ''}<div class="cc-bubble" dir="auto">${escape(turn.text)}</div><small class="cc-meta">我 · ${time(turn.when)}</small></div>${reply}</div>`;
    }).join('');
    log.scrollTop=log.scrollHeight;
  }
  function syncComposer(){
    const input=q('textarea'),send=q('.cc-send');if(!send)return;
    send.disabled=current().flight||!input.value.trim()||!recording.canSend();
    input.style.height='auto';input.style.height=Math.min(116,input.scrollHeight)+'px';
  }
  function showThread(){
    const target=q('.cc-detail'); target.innerHTML=threadMarkup(); q('textarea').value=current().draft;
    roster();chatLog();syncComposer();updateConnection();recover(selected);
    q('.cc-compose').addEventListener('submit',e=>{ e.preventDefault();sendDraft(); });
  }
  function refreshThread(id){
    if(!panel?.isConnected)return;
    roster();if(id===selected){
      chatLog();syncComposer();
      const last=q('.cc-turn:last-child .cc-in');
      if(threads[id].turns.at(-1)?.state==='live' && last){
        const log=q('.cc-log');
        if(last.offsetHeight>log.clientHeight - 20)log.scrollTop+=last.getBoundingClientRect().top-log.getBoundingClientRect().top-10;
        if(!matchMedia('(prefers-reduced-motion: reduce)').matches)last.animate(
          [{opacity:.6,transform:'translateY(5px)'},{opacity:1,transform:'translateY(0)'}],{duration:200,easing:'ease-out'}
        );
      }
    }
  }
  function retryTurn(id,turn){
    const t=threads[id];if(t.flight||!recording.canSend())return;
    if(turn.state==='expired'){t.id=null;turn.key=uuid();turn.fresh=true;}
    if(t.draft.trim()===turn.text){
      t.draft='';if(panel?.isConnected && selected===id){q('textarea').value='';syncComposer();}
    }
    transmit(id,turn);
  }
  async function transmit(id,turn){
    const t=threads[id];if(t.flight)return;
    t.flight=true;turn.state='waiting';persist();refreshThread(id);
    let reserved=false;
    try{
      recording.reserve();reserved=true;
      updateConnection();
      const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        role:id, message:turn.text, conversation_id:t.id, request_id:turn.key, handoff_from:turn.handoffFrom||null
      })});
      const body=await res.json().catch(()=>({}));
      if(!res.ok){
        turn.state=res.status===410?'expired':'failed';
        throw Error(typeof body.detail==='string'?body.detail:'模型服务未完成本次请求，请稍后重试。');
      }
      if(body.source!=='live'||body.role!==id||body.request_id!==turn.key||typeof body.reply!=='string'||!body.reply.trim()||!body.conversation_id){
        throw Error('未能核实模型回复，请重试以核对本次请求。');
      }
      t.id=body.conversation_id;
      try{(recording.enabled?sessionStorage:localStorage).setItem(memoryKey(id),t.id);}catch{}
      Object.assign(turn,{state:'live',reply:body.reply,completed:Date.parse(body.generated_at)||Date.now(),replayed:body.replayed===true,
        model:body.model,vendor:body.vendor,elapsed_ms:body.elapsed_ms,provider:body.provider,error:''});
    }catch(err){
      if(reserved)recording.pauseAfterFailure();
      if(turn.state!=='expired')turn.state='failed';
      if(!t.draft){
        t.draft=turn.text;
        if(panel?.isConnected && selected===id){q('textarea').value=t.draft;}
      }
      turn.error=err instanceof TypeError?'连接中断，请检查本机工作台后重试。':err.message;
    }finally{
      t.flight=false;persist();refreshThread(id);updateConnection();
    }
  }
  function sendDraft(){
    const t=current(),text=t.draft.trim();if(t.flight||!text||text.length>limit||!recording.canSend())return;
    const last=t.turns.at(-1);
    if(last && (last.state==='failed'||last.state==='expired') && last.text===text){retryTurn(selected,last);return;}
    const turn={key:uuid(),text,when:Date.now(),state:'waiting'};
    t.turns.push(turn);if(t.turns.length>50)t.turns.shift();
    t.draft='';q('textarea').value='';syncComposer();
    transmit(selected,turn);q('textarea').focus({preventScroll:true});
  }
  function setDraft(value){
    current().draft=value;q('textarea').value=value;syncComposer();persist();q('textarea').focus({preventScroll:true});
  }
  function onClick(e){
    const b=e.target.closest('button');if(!b||!panel?.contains(b))return;
    if(b.dataset.person && byId[b.dataset.person]){
      selected=b.dataset.person;showConnection=false;persist();showThread();
      q(`[data-person="${selected}"]`)?.focus({preventScroll:true});hooks.onRoleChange?.(selected);return;
    }
    if(b.dataset.handoff){handoff(b.dataset.handoff,b.dataset.receipt);return;}
    if(b.dataset.stepLink){hooks.openStep?.(+b.dataset.stepLink);return;}
    switch(b.dataset.cc){
      case 'model': hooks.openModel?.(selected);break;
      case 'record':{
        const record=q('.cc-evidence');record.hidden=!record.hidden;b.setAttribute('aria-expanded',String(!record.hidden));break;
      }
      case 'settings':showConnection=b.classList.contains('cc-connect-btn')?!showConnection:true;updateConnection();if(showConnection&&!b.classList.contains('cc-connect-btn'))q('.cc-connect-btn').focus();break;
      case 'refresh':checkService();break;
      case 'prompt':setDraft(byId[selected].prompt);break;
      case 'revise':{const turn=current().turns.at(-1);if(turn&&!current().flight)setDraft(turn.text);break;}
      case 'retry':{
        const t=current(),turn=t.turns.at(-1);if(!turn||t.flight||!['expired','failed'].includes(turn.state))break;
        retryTurn(selected,turn);break;
      }
    }
  }
  function render(work,options={}){
    leave();hooks=options;if(byId[options.role])selected=options.role;
    panel=document.createElement('div');panel.className='cc-app';
    panel.innerHTML=`<div class="cc-page-top"><div><span class="cc-kicker">教师工作空间</span><h1>教研对话</h1></div><div class="cc-connect-wrap">
      <button type="button" class="cc-connect-btn" data-cc="settings" aria-expanded="false" aria-controls="cc-settings">连接设置</button>
      <aside id="cc-settings" class="cc-settings" aria-label="模型连接设置" hidden></aside></div></div>
      <div class="cc-board"><aside class="cc-side"><div class="cc-side-top"><h2>会话</h2><span>6 位智能体</span></div><nav class="cc-roster" aria-label="选择角色"></nav></aside>
      <div class="cc-detail"></div></div>`;
    work.replaceChildren(panel);panel.addEventListener('click',onClick);
    panel.addEventListener('input',e=>{if(e.target.tagName==='TEXTAREA'){current().draft=e.target.value;syncComposer();persist();}});
    panel.addEventListener('keydown',e=>{
      if(e.key==='Escape' && showConnection){showConnection=false;updateConnection();q('.cc-connect-btn')?.focus();return;}
      if(e.target.tagName==='TEXTAREA'&&e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&e.keyCode!==229){e.preventDefault();if(!e.repeat)sendDraft();}
    });
    showThread();checkService();persist();
  }
  function leave(){panel=null;hooks={};showConnection=false;}
  restore();window.YincaiChat=Object.freeze({render,leave});
})();
