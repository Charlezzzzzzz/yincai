// A single cockpit instance retains its WebGL context while other workspaces are open.
window.YincaiRoundtable = {
 create({steps, names, getQuote, onStep, renderDetail, initialFlat}) {
  const root = document.querySelector('#roundtable-template').content.firstElementChild.cloneNode(true);
  const $ = id => root.querySelector('#' + id);
  const titles = ['定位漏乘的一项', '核对错因与证据', '确定教学策略', '写出第一版教案', '退回泄露答案的初稿', '把答案改成验算提示', '复核同一段提示', '交任课教师批阅'];
  const tasks = ['对照原题与运算步骤，校验这项诊断。', '据此设计能让学生发现漏乘的教学活动。', '把全项同乘与代入检验写成分步提示。', '检查学生能看到的文字和旁白是否泄露答案。', '改写第 2 步说明及旁白，保留学生自主检验的机会。', '逐项确认修改回应了退回批注。', '整理复核后的提示及证据，提交教师批阅。', '逐条审阅待定建议，由任课教师决定采纳、修改或否决。'];
  const roleKeys = Object.keys(names).filter(role => role !== 'teacher');
  const stageButtons = [], roleButtons = [], actorButtons = [];
  const camera = fetch('roundtable/camera.json').then(response => {
    if (!response.ok) throw new Error('场景相机不可用');
    return response.json();
  });
  let step = 1, flat = initialFlat, orbit = false, viewer, loadViewer;
  function createButton(parent, label, onClick) {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = label; button.addEventListener('click', onClick); parent.append(button);
    return button;
  }
  steps.forEach(row => {
    const button = createButton($('steps'), '', () => onStep(row.seq));
    const number = document.createElement('span');
    number.className = 'folio-number';
    number.textContent = String(row.seq).padStart(2, '0');
    const title = document.createElement('span');
    title.className = 'folio-name'; title.textContent = row.stage;
    button.append(number, title);
    button.setAttribute('aria-controls', 'step-record');
    button.setAttribute('aria-label', '第' + row.seq + '步，' + row.stage + '，' + names[row.sender]);
    button.dataset.step = row.seq; stageButtons.push(button);
  });
  function selectRole(role) {
    const choices = steps.filter(row => row.sender === role);
    const activeIndex = choices.findIndex(row => row.seq === step);
    onStep(choices[(activeIndex + 1) % choices.length].seq);
  }
  roleKeys.forEach(role => {
    const button = createButton($('roles'), names[role], () => selectRole(role));
    button.dataset.role = role; roleButtons.push(button);
  });
  function syncRoles() {
    const row = steps[step - 1];
    [...roleButtons, ...actorButtons].forEach(button => {
      button.setAttribute('aria-pressed', String((button.dataset.role || button.dataset.actor) === row.sender));
    });
    const active = actorButtons.find(button => button.dataset.actor === row.sender);
    if (active) {
      const marker = $('active-actor');
      marker.style.left = active.dataset.center;
      marker.style.top = active.style.top;
      marker.hidden = false;
    }
    if (viewer && orbit) viewer.highlight(row.sender);
  }
  function placeTarget(button, target) {
    const [left, top, right, bottom] = target.bounds;
    Object.assign(button.style, {
      left: left * 100 + '%', top: top * 100 + '%',
      width: (right - left) * 100 + '%', height: (bottom - top) * 100 + '%'
    });
    // Each contour follows only the visible surface. A click on the table edge
    // must not reach the overlapping rectangle of a figure behind it.
    if (target.hitPolygon) {
      const points = target.hitPolygon.map(([x, y]) => x * 100 + '% ' + y * 100 + '%');
      button.style.clipPath = 'polygon(' + points.join(', ') + ')';
    }
    button.dataset.center = ((left + right) * 50) + '%';
  }
  camera.then(data => {
    for (const role of roleKeys) {
      const button = createButton($('actors'), '', () => selectRole(role));
      button.className = 'actor'; button.dataset.actor = role;
      button.title = names[role];
      button.setAttribute('aria-label', '查看' + names[role] + '经手的书页');
      placeTarget(button, data.projectedActors[role]);
      actorButtons.push(button);
    }
    if (data.bookPage?.bounds) {
      placeTarget($('book-hotspot'), data.bookPage);
      $('book-hotspot').hidden = false;
    }
    syncRoles();
  }).catch(() => {$('orbit').hidden = true;});
  function display(n) {
    step = n;
    const row = steps[n - 1];
    $('old-quote').textContent = getQuote(4);
    $('new-quote').textContent = getQuote(6);
    $('ask-seat').href = '#chat/' + row.sender;
    $('view-seat').href = '#cast/' + row.sender;
    const toTeacher = row.recipient === 'teacher';
    $('flow-from-image').src = 'avatars/' + row.sender + '.webp';
    $('flow-from').textContent = names[row.sender];
    $('flow-to').textContent = names[row.recipient];
    $('teacher-mark').hidden = !toTeacher;
    $('flow-to-image').hidden = toTeacher;
    if (!toTeacher) $('flow-to-image').src = 'avatars/' + row.recipient + '.webp';
    const handoffLink = $('flow-to-link');
    handoffLink.href = toTeacher ? $('teacher').href : '#cockpit/' + (n + 1);
    handoffLink.setAttribute('aria-label', toTeacher ? '交给任课教师，打开正式教师批阅' :
      '转交' + names[row.recipient] + '，查看' + steps[n].stage);
    $('folio').textContent = '教案手记  /  ' + String(n).padStart(2,'0') + ' · ' + row.stage;
    $('evidence-title').textContent = titles[n - 1];
    $('owner').textContent = names[row.sender] + ' 留下的' + (row.sender === 'checker' ? '批注' : '记录');
    $('excerpt').textContent = getQuote(n);
    $('recipient').textContent = '转交' + names[row.recipient];
    $('assignment').textContent = tasks[n - 1];
    $('warning').hidden = ![4,5].includes(n);
    $('comparison').hidden = ![4,5,6,7].includes(n);
    $('next').hidden = n === 8; $('teacher').hidden = n !== 8;
    $('book-hotspot').title = n < 8 ? '翻到' + steps[n].stage : '打开教师批阅';
    $('book-hotspot').setAttribute('aria-label', '桌上备课簿，' + $('book-hotspot').title);
    if (n < 8) $('next').textContent = '翻到' + steps[n].stage + ' →';
    stageButtons.forEach((button,index) => {
      if (index + 1 === n) button.setAttribute('aria-current','step');
      else button.removeAttribute('aria-current');
    });
    syncRoles();
    if ($('record-more').open) updateDetail();
  }
  function turnPage() {
    if (step === 8) $('teacher').click();
    else onStep(step + 1);
  }
  $('book-hotspot').addEventListener('click', turnPage);
  $('flow-to-link').addEventListener('click', event => {
    if (step < 8 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      event.preventDefault();
      turnPage();
    }
  });
  function updateDetail() {
    const full = $('dossier-content').querySelector('.transcript')?.open;
    const provenance = $('dossier-content').querySelector('.provenance')?.open;
    $('dossier-content').innerHTML = renderDetail();
    if (full && $('dossier-content').querySelector('.transcript')) $('dossier-content').querySelector('.transcript').open = true;
    if (provenance) $('dossier-content').querySelector('.provenance').open = true;
  }
  $('record-more').addEventListener('toggle', () => {if ($('record-more').open) updateDetail();});
  function switchOrbit(enabled) {
    orbit = enabled; $('model').hidden = !enabled; $('actors').hidden = enabled; $('hero').hidden = enabled;
    $('orbit').setAttribute('aria-pressed',String(enabled));
    $('orbit').textContent = enabled ? '回到定镜 ↶' : '转动模型 ↗';
    $('viewer-status').textContent = enabled ? '拖动转动模型 · 点角色查页 · Home 复位' : '';
  }
  $('orbit').addEventListener('click', async () => {
    if (orbit) {switchOrbit(false); return;}
    $('orbit').disabled = true; $('viewer-status').textContent = '正在载入本地模型…';
    try {
      if (!loadViewer) loadViewer = Promise.all([import('./roundtable/scene.mjs'),camera]).then(async ([module,pose]) => {
        const instance = module.createViewer($('model'),pose, target => {
          if (target === 'book') turnPage();
          else selectRole(target);
        });
        try { await instance.load(); return instance; }
        catch (error) { instance.dispose(); throw error; }
      });
      viewer = await loadViewer;
      if (!flat && root.isConnected) {switchOrbit(true); viewer.reset(); syncRoles(); $('model').focus({preventScroll:true});}
    } catch {
      loadViewer = null; switchOrbit(false); $('viewer-status').textContent = '三维视图暂不可用，可点选定镜中的角色继续阅读。';
    } finally { $('orbit').disabled = false; }
  });
  function setFlat(enabled) {
    flat = enabled; switchOrbit(false);
    $('workspace').classList.toggle('flat', flat);
    $('flat').setAttribute('aria-pressed', String(flat));
    $('flat').textContent = flat ? '返回圆桌' : '平面阅读';
  }
  $('flat').addEventListener('click', () => setFlat(!flat));
  setFlat(flat);
  $('steps').addEventListener('keydown', event => {
    const button = event.target.closest('button[data-step]');
    if (!button) return;
    const current = Number(button.dataset.step);
    const target = {ArrowLeft:Math.max(1,current-1), ArrowRight:Math.min(8,current+1), Home:1, End:8}[event.key];
    if (!target) return;
    event.preventDefault(); onStep(target); stageButtons[target-1].focus();
  });
  return {
    mount(host, n) { if (root.parentNode !== host) host.replaceChildren(root); display(n); },
    dropTarget(role) {
      const actor = !flat && !orbit && actorButtons.find(button => button.dataset.actor === role);
      return actor || roleButtons.find(button => button.dataset.role === role);
    },
    leave() { switchOrbit(false); }
  };
 }
};
