(() => {
  'use strict';
  let cleanup;

  async function api(path, body, signal) {
    const response = await fetch('/api/chat/settings' + path, {
      method: body ? 'POST' : 'GET', signal, cache: 'no-store',
      headers: body ? {'Content-Type':'application/json'} : {},
      body: body ? JSON.stringify(body) : undefined
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请求未完成。');
    return data;
  }

  function leave() {
    cleanup?.();
    cleanup = null;
  }

  async function render(work, back) {
    leave();
    const controller = new AbortController();
    const recording = window.YincaiRecording;
    work.innerHTML = `<article class="model-settings">
      <header class="ms-heading"><div><button type="button" class="ms-back">← 返回工作区</button><h1>模型设置</h1>
      <p>为六位智能体选择对话模型。</p></div><div class="ms-current" hidden><span>当前使用</span><strong></strong><small></small></div></header>
      <div class="ms-private-intro"><div><h2>连接你的模型</h2><p>选择服务商与模型，在本机输入密钥。保存只更新配置。</p></div>
      <button type="button" data-private-config disabled>配置模型连接</button></div>
      <p class="ms-feedback" role="status" aria-live="polite">正在读取本机配置…</p>
      <button type="button" class="ms-reload" hidden>重新读取设置</button>
      <dialog id="ms-private-dialog" aria-labelledby="ms-dialog-title"><div class="ms-dialog-heading"><h2 id="ms-dialog-title">私密连接设置</h2>
      <button type="button" class="ms-close" aria-label="关闭私密连接设置">关闭</button></div>
      <p class="ms-disclosure">请在暂停录屏和屏幕共享后输入密钥。发起云端对话时，所选服务商会收到相应角色的提问、近期对话及教学证据，可能按量计费。</p>
      <form class="ms-form" autocomplete="off">
        <section class="ms-provider"><h2>模型服务</h2><label for="ms-provider">服务商</label>
        <select id="ms-provider" required></select><p class="ms-note"></p>
        <a class="ms-docs" target="_blank" rel="noopener noreferrer" hidden>查看官方文档 ↗</a></section>
        <section class="ms-fields"><h2>连接配置</h2>
        <label for="ms-model">模型 ID</label><div class="ms-model-line">
        <input id="ms-model" required maxlength="256" spellcheck="false" autocapitalize="none">
        <select id="ms-model-picker" aria-label="选择预设模型"></select></div><small>可选预设，也可输入账户中已开通的模型 ID。</small>
        <label for="ms-base">API 根地址</label><input id="ms-base" type="url" required maxlength="1024" spellcheck="false" autocapitalize="none" placeholder="https://…/v1">
        <div class="ms-key"><label for="ms-key">API 密钥</label><input id="ms-key" type="password" autocomplete="off" maxlength="4096" spellcheck="false" autocapitalize="none">
        <small class="ms-key-hint"></small></div>
        <div class="ms-actions"><button type="button" class="ms-test">测试连接</button><button type="submit" class="ms-save">保存设置</button></div>
        <small class="ms-test-hint"></small></section></form>
      <p class="ms-feedback ms-dialog-feedback" role="status" aria-live="polite"></p></dialog></article>`;
    const section = work.querySelector('.model-settings');
    const q = s => section.querySelector(s);
    const form = q('form'), vendor = q('#ms-provider'), model = q('#ms-model'), base = q('#ms-base'), key = q('#ms-key');
    const feedback = q('.ms-feedback'), test = q('.ms-test'), save = q('.ms-save');
    const reload = q('.ms-reload'), modelPicker = q('#ms-model-picker');
    const dialog = q('dialog'), opener = q('[data-private-config]'), close = q('.ms-close');
    let providers, active;
    test.hidden = recording.enabled;
    cleanup = () => {controller.abort(); form.reset(); key.value = ''; if(dialog.open) dialog.close();};
    q('.ms-back').onclick = back;
    function report(message, failed = false) {
      const destination = dialog.open ? q('.ms-dialog-feedback') : feedback;
      destination.textContent = message;
      destination.classList.toggle('ms-error', failed);
    }
    function showCurrent() {
      const profile = providers.find(p => p.id === active.provider);
      q('.ms-current').hidden = false;
      q('.ms-current strong').textContent = profile?.label || active.provider;
      q('.ms-current small').textContent = active.model || '待配置';
    }
    function sameEndpoint() {
      return active.provider === vendor.value && active.base_url.replace(/\/+$/, '') === base.value.trim().replace(/\/+$/, '');
    }
    function keyHint() {
      const retained = sameEndpoint() && active.has_key;
      key.placeholder = retained ? '留空以沿用当前密钥' : '请输入此服务的密钥';
      q('.ms-key-hint').textContent = (retained && active.key_source === 'environment' ? '该端点已从启动环境取得密钥。' : '') +
        '网页输入的密钥仅在本次服务运行期间有效，重启后请重新填写。';
    }
    function showProvider() {
      const p = providers.find(row => row.id === vendor.value);
      const selected = active.provider === p.id;
      key.value = '';
      base.value = selected ? active.base_url : p.base_url;
      base.readOnly = !['custom','ollama'].includes(p.id);
      model.value = selected ? active.model : p.models[0] || '';
      modelPicker.replaceChildren(new Option('选预设', ''), ...p.models.map(id => new Option(id, id)));
      modelPicker.hidden = !p.models.length;
      const docs = q('.ms-docs');
      docs.hidden = !p.docs_url; docs.href = p.docs_url || '';
      q('.ms-note').textContent = p.note || '使用该厂商的官方兼容接口。';
      q('.ms-key').hidden = p.id === 'ollama';
      keyHint();
      q('.ms-test-hint').textContent = recording.enabled ? '录制模式最多发送两次对话。保存设置不会向服务商发送请求。' : p.id === 'ollama' ? '测试会向本机模型发送一条简短消息。' :
        '测试会向所填地址发送一条简短消息，云端服务可能计费。对话会发送当前角色的提问、近期对话和对应教学证据。切换模型或端点后需新开会话。';
      report('');
    }
    async function load() {
      reload.hidden = true; report('正在读取本机配置…');
      try {
        const data = await api('', null, controller.signal);
        providers = data.providers; active = data.active;
        if (!providers?.some(p => p.id === active?.provider)) throw Error('配置不完整。');
        const choices = providers.filter(p => !recording.enabled || p.id !== 'ollama');
        vendor.replaceChildren(...choices.map(p => new Option(p.label, p.id)));
        showCurrent(); report(''); opener.disabled = false;
      } catch {
        if (!controller.signal.aborted) { report('无法读取模型设置，请从本机工作台服务打开此页。', true); reload.hidden = false; }
      }
    }
    opener.onclick = () => {
      section.dataset.configSaved = 'false';
      vendor.value = recording.enabled && active.provider === 'ollama' ? vendor.options[0].value : active.provider;
      dialog.showModal(); showProvider(); vendor.focus();
    };
    function clearDialog() {
      form.reset();
      key.value = '';
      q('.ms-dialog-feedback').textContent = '';
    }
    close.onclick = () => { if (!save.disabled) {clearDialog(); dialog.close();} };
    dialog.addEventListener('cancel', e => {if (save.disabled) e.preventDefault(); else clearDialog();});
    function setBusy(busy) {
      for (const field of [vendor,model,modelPicker,base,key,test,save,close]) field.disabled = busy;
      form.setAttribute('aria-busy', String(busy));
    }
    async function submit(probe) {
      if (!dialog.open || (probe && recording.enabled) || !form.reportValidity() || save.disabled) return;
      const payload = {provider:vendor.value,base_url:base.value.trim(),model:model.value.trim()};
      if (recording.enabled && (payload.provider === 'ollama' || !payload.base_url.startsWith('https://'))) {
        report('录制云端对话时，请选择使用 HTTPS 的服务。', true); return;
      }
      if (key.value) payload.api_key = key.value;
      setBusy(true); report(probe ? '正在等待模型返回测试回复…' : '正在保存到本机…');
      try {
        const data = await api(probe ? '/test' : '', payload, controller.signal);
        if (probe) {
          if (data.ok !== true || data.source !== 'live') throw Error('未取得模型回复。');
          report('测试成功 · '+ data.model +' 已返回正文。'+ (!sameEndpoint() || active.model !== model.value || key.value ? '点击保存设置后生效。':''));
        } else {
          if (!data.active?.configured) throw Error('连接配置尚未就绪，请核对模型与密钥。');
          active = data.active;
          clearDialog(); dialog.close();
          recording.confirmSettings();
          section.dataset.configSaved = 'true';
          showCurrent(); report('本机配置已保存，后续对话将使用 '+active.model+'。');
        }
      } catch (error) {
        if (!controller.signal.aborted) report(error instanceof TypeError ? '无法连接本机工作台，请检查服务后重试。' : error.message, true);
      } finally {setBusy(false);}
    }
    vendor.addEventListener('change', showProvider);
    modelPicker.addEventListener('change', () => {
      if (modelPicker.value) model.value = modelPicker.value;
      modelPicker.value = ''; report(''); model.focus();
    });
    base.addEventListener('input', () => {key.value = ''; keyHint();});
    form.addEventListener('input', () => report(''));
    form.addEventListener('submit', e => {e.preventDefault(); submit(false);});
    test.onclick = () => submit(true);
    reload.onclick = load;
    await load();
  }
  window.YincaiSettings = Object.freeze({render, leave});
})();
