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
  const files=window.YincaiAttachments;
  const defaultFileQuestion='请结合附件给出备课建议。';
  const storageKey='yincai.v8.role-dialogues.1'+(recording.enabled?'.recording':''), limit=2000;
  const emptyThread = () => ({id:null, draft:'', draftFiles:[], turns:[], flight:false, reading:false, fileError:''});
  const threads = Object.fromEntries(people.map(p => [p.id,emptyThread()]));
  let selected='analyst', panel=null, hooks={}, service=null, serviceCheck=null, showConnection=false;
  const allowed = new Set(['waiting','failed','live','expired']);
  const escape = v => String(v??'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const uuid = () => crypto.randomUUID();
  const current=()=>threads[selected];
  const formatMessage=text=>window.YincaiMarkdown?.render(text) ?? escape(text);
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
        t.draftFiles=Array.isArray(s.draftFiles)?s.draftFiles:[];
        t.turns=s.turns.slice(-50).filter(v=>v && typeof v.key==='string' && typeof v.text==='string' && allowed.has(v.state));
        for(const turn of t.turns) {
          if(turn.state==='live')turn.restored=true;
          if(turn.state==='waiting'){
            turn.state='failed';turn.error='页面已重新载入，请重试以核对这次请求。';
            if(!t.draft && !t.draftFiles.length){t.draft=turn.text;t.draftFiles=turn.attachments||[];}
          }
        }
      }
    } catch { /* Storage can be unavailable in private contexts. */ }
  }
  function persist(){
    try{ sessionStorage.setItem(storageKey,JSON.stringify({selected,threads})); }catch{}
  }
  function releaseFiles() {
    const keep=[];
    for(const t of Object.values(threads)){
      keep.push(...t.draftFiles);
      for(const turn of t.turns)if(turn.state==='waiting' || turn===t.turns.at(-1) && ['failed','expired'].includes(turn.state))keep.push(...(turn.attachments||[]));
    }
    files.prune(keep);
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
        state:'live',restored:true,attachments:row.attachments||[],handoffRole:row.handoff?.from,handoffFrom:row.handoff?.source_request_id}));
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
    attachmentNotice();
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
      <form class="cc-compose"><div class="cc-files" aria-live="polite"></div><p class="cc-file-notice" hidden></p>
        <p class="cc-file-error" role="status" hidden></p><div class="cc-entry">
        <input type="file" data-files-picker multiple accept="${files.accept}" hidden>
        <button type="button" class="cc-attach" data-cc="attach" aria-label="添加文件或图片" title="添加图片、PDF、DOCX 或文本。最多 3 份，单份 3 MiB，合计 6 MiB。">＋</button>
        <textarea aria-label="给${p.name}写消息" rows="1" maxlength="${limit}" placeholder="给${p.name}发消息…"></textarea>
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
      if(turn.state==='live')reply=`<div class="cc-in">${avatar(p.id)}<div><div class="cc-bubble cc-answer cc-rich" dir="auto">${formatMessage(turn.reply)}</div>
        ${/(?:23|二十三)\s*(?:名|位|人)|(?:前|排名)\s*(?:23|二十三)/.test(turn.reply) ? '<p class="cc-case-note">□ 模拟班级口径：全班 30 人，前三类错因合计涉及 23 人。</p>' : ''}
        <small class="cc-meta" data-model-receipt>${receipt(turn)}</small><div class="cc-handoffs">${handoffButtons(p.id,turn)}</div></div></div>`;
      else if(turn.state==='waiting')reply=`<div class="cc-in">${avatar(p.id)}<div><div class="cc-typing" aria-hidden="true"><i></i><i></i><i></i></div><small class="cc-meta">正在等待模型回复</small></div></div>`;
      else reply=`<div class="cc-error" role="status"><strong>${turn.state==='expired'?'会话已过期':'未收到回复'}</strong><span>${escape(turn.error)}</span>${i===t.turns.length-1?`<div><button type="button" data-cc="retry" ${recording.canSend()?'':'disabled'}>${turn.state==='expired'?'在新会话重试':'重试'}</button><button type="button" data-cc="revise">编辑问题</button><button type="button" data-cc="settings">连接设置</button></div>`:''}</div>`;
      const attached=(turn.attachments||[]).map(row=>`<span class="cc-sent-file">${escape(row.name)} · ${escape(files.sizeLabel(row.size))}</span>`).join('');
      return `<div class="cc-turn">${turn.fresh?'<div class="cc-divider">新会话</div>':''}<div class="cc-out">${turn.handoffRole&&byId[turn.handoffRole]?`<small class="cc-meta">转自${byId[turn.handoffRole].name} · 先前生成的回复 ○</small>`: ''}<div class="cc-bubble cc-rich" dir="auto">${formatMessage(turn.text)}</div>${attached}<small class="cc-meta">我 · ${time(turn.when)}</small></div>${reply}</div>`;
    }).join('');
    log.scrollTop=log.scrollHeight;
  }
  function syncComposer(){
    const input=q('textarea'),send=q('.cc-send');if(!send)return;
    const t=current(), missing=t.draftFiles.some(row=>!files.available(row));
    send.disabled=t.flight||t.reading||missing||(!input.value.trim()&&!t.draftFiles.length)||!recording.canSend();
    q('[data-cc="attach"]').disabled=t.reading||t.flight;
    input.placeholder=t.draftFiles.length?defaultFileQuestion:'给'+byId[selected].name+'发消息…';
    input.style.height='auto';input.style.height=Math.min(116,input.scrollHeight)+'px';
  }
  function attachmentNotice(){
    const notice=q('.cc-file-notice');if(!notice)return;
    const t=current();notice.hidden=!t.draftFiles.length;
    if(notice.hidden)return;
    const where=service?.provider==='ollama'?'当前本机模型':service?.provider==='compatible'?'所配置的模型 API':'当前配置的模型服务';
    notice.textContent='点击发送后，图片及文档提取的正文将交给'+where+(service?.model?'（'+service.model+'）':'')+'处理。'+(service?.provider==='ollama'?'':'使用云端接口时，服务商会收到这些内容。');
    if(t.draftFiles.some(row=>!files.available(row)))notice.textContent+=' 页面已刷新，请重新选择标记的原文件，或明确移除后再发送。';
  }
  function showFiles(){
    const box=q('.cc-files');if(!box)return;
    const t=current();
    box.innerHTML=t.draftFiles.map((row,i)=>{
      const preview=files.thumbnail(row), label=files.available(row)?files.sizeLabel(row.size):'请重新选择原文件';
      return `<div class="cc-file">${preview?`<img alt="" src="${escape(preview)}">`:''}<span><b>${escape(row.name)}</b><small>${escape(label)}</small></span><button type="button" data-remove-file="${i}" aria-label="移除 ${escape(row.name)}" ${t.reading||t.flight?'disabled':''}>×</button></div>`;
    }).join('');
    const status=q('.cc-file-error');status.hidden=!t.fileError&&!t.reading;
    status.textContent=t.reading?'正在本机读取附件…':t.fileError;
    attachmentNotice();syncComposer();
  }
  async function addFiles(id,picked){
    const t=threads[id];if(!picked.length||t.reading||t.flight)return;
    t.reading=true;t.fileError='';if(id===selected)showFiles();
    try{t.draftFiles=await files.select(t.draftFiles,picked);}
    catch(e){t.fileError=e.message||'文件读取失败，请重新选择。';}
    finally{t.reading=false;persist();if(id===selected&&panel?.isConnected)showFiles();}
  }
  function showThread(){
    const target=q('.cc-detail'); target.innerHTML=threadMarkup(); q('textarea').value=current().draft;
    roster();chatLog();showFiles();updateConnection();recover(selected);
    q('.cc-compose').addEventListener('submit',e=>{ e.preventDefault();sendDraft(); });
    const owner=selected;
    q('[data-files-picker]').addEventListener('change',e=>{
      const picked=Array.from(e.target.files||[]);e.target.value='';addFiles(owner,picked);
    });
  }
  function refreshThread(id){
    if(!panel?.isConnected)return;
    roster();if(id===selected){
      chatLog();showFiles();
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
    const t=threads[id];if(t.flight||t.reading||!recording.canSend())return;
    if(t.draftFiles.length && t.draftFiles.every(files.available) && files.same(t.draftFiles,turn.attachments)){
      turn.attachments=t.draftFiles.slice();
    }
    const original=turn.attachments||[];
    const draftText=t.draft.trim()||(t.draftFiles.length?defaultFileQuestion:'');
    if(original.length && (draftText!==turn.text || !files.same(t.draftFiles,original))){
      if(!t.draft && !t.draftFiles.length){t.draft=turn.text;t.draftFiles=original.slice();q('textarea').value=t.draft;}
      t.fileError='请先核对草稿与附件，点击发送将按当前草稿处理。';
      showFiles();persist();return;
    }
    if(original.some(row=>!files.available(row))){
      if(!t.draft && !t.draftFiles.length){t.draft=turn.text;t.draftFiles=original.slice();q('textarea').value=t.draft;}
      t.fileError='本条请求需要原文件。请在草稿中重新选择相同附件，或编辑问题后以新消息发送。';
      showFiles();persist();return;
    }
    if(turn.state==='expired'){t.id=null;turn.key=uuid();turn.fresh=true;}
    if(draftText===turn.text && files.same(t.draftFiles,original)){
      t.draftFiles=[];t.fileError='';
      t.draft='';if(panel?.isConnected && selected===id){q('textarea').value='';syncComposer();}
    }
    transmit(id,turn);
  }
  async function transmit(id,turn){
    const t=threads[id];if(t.flight)return;
    t.flight=true;turn.state='waiting';persist();refreshThread(id);
    let reserved=false;
    try{
      const attachments=turn.attachments?.length?await files.packet(turn.attachments):[];
      recording.reserve();reserved=true;
      updateConnection();
      const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        role:id, message:turn.text, conversation_id:t.id, request_id:turn.key, handoff_from:turn.handoffFrom||null,attachments
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
      if(Array.isArray(body.attachments))turn.attachments=body.attachments.map(({name,mime,kind,size})=>({name,mime,kind,size}));
    }catch(err){
      if(reserved)recording.pauseAfterFailure();
      if(turn.state!=='expired')turn.state='failed';
      if(!t.draft && !t.draftFiles.length){
        t.draft=turn.text;t.draftFiles=(turn.attachments||[]).slice();
        if(panel?.isConnected && selected===id){q('textarea').value=t.draft;}
      }
      turn.error=err instanceof TypeError?'连接中断，请检查本机工作台后重试。':err.message;
    }finally{
      t.flight=false;releaseFiles();persist();refreshThread(id);updateConnection();
    }
  }
  function sendDraft(){
    const t=current(),text=t.draft.trim()||(t.draftFiles.length?defaultFileQuestion:'');
    if(t.flight||t.reading||!text||text.length>limit||!recording.canSend()||t.draftFiles.some(row=>!files.available(row)))return;
    const last=t.turns.at(-1);
    if(last && (last.state==='failed'||last.state==='expired') && last.text===text && files.same(t.draftFiles,last.attachments)){retryTurn(selected,last);return;}
    const turn={key:uuid(),text,when:Date.now(),state:'waiting',attachments:t.draftFiles};
    t.turns.push(turn);if(t.turns.length>50)t.turns.shift();
    t.draft='';t.draftFiles=[];t.fileError='';q('textarea').value='';showFiles();
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
    if(b.dataset.removeFile!==undefined){
      const t=current(), i=Number(b.dataset.removeFile);
      if(!t.flight&&!t.reading&&Number.isInteger(i)&&i>=0&&i<t.draftFiles.length){
        t.draftFiles.splice(i,1);t.fileError='';releaseFiles();persist();showFiles();
      }
      return;
    }
    switch(b.dataset.cc){
      case 'attach':q('[data-files-picker]').click();break;
      case 'model': hooks.openModel?.(selected);break;
      case 'record':{
        const record=q('.cc-evidence');record.hidden=!record.hidden;b.setAttribute('aria-expanded',String(!record.hidden));break;
      }
      case 'settings':showConnection=b.classList.contains('cc-connect-btn')?!showConnection:true;updateConnection();if(showConnection&&!b.classList.contains('cc-connect-btn'))q('.cc-connect-btn').focus();break;
      case 'refresh':checkService();break;
      case 'prompt':setDraft(byId[selected].prompt);break;
      case 'revise':{const t=current(),turn=t.turns.at(-1);
        if(!turn||t.flight||t.reading)break;
        if((t.draft && t.draft!==turn.text)||(t.draftFiles.length&&!files.same(t.draftFiles,turn.attachments))){
          t.fileError='草稿中已有其他内容。请先处理当前草稿。';showFiles();break;
        }
        t.draftFiles=(turn.attachments||[]).slice();setDraft(turn.text);showFiles();break;}
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
