(() => {
  'use strict';
  const cast = [
    ['analyst', '学情分析师'], ['expert', '学科专家'], ['designer', '教学设计师'],
    ['producer', '多模态制作人'], ['checker', '核查员'], ['assistant', '教师助理']
  ];
  let teardown;

  function leave() {
    if (teardown) teardown();
    teardown = null;
    document.body.classList.remove('yincai-cover-open');
  }
  function render(host, {enter, chat}) {
    leave();
    document.body.classList.add('yincai-cover-open');
    host.innerHTML = `
      <div class="yc-cover">
        <div class="yc-jacket-head">
          <span class="yc-jacket-brand"><i class="yc-paper-sign" aria-hidden="true"></i>因才 <span>教育多智能体架构</span></span>
          <button type="button" class="model-settings-link" data-view="settings">模型设置</button>
        </div>
        <section class="yc-jacket-scene" aria-labelledby="yc-jacket-title">
          <div class="yc-jacket-intro">
            <h1 id="yc-jacket-title">因才</h1>
            <p class="yc-jacket-description">六位智能体协作备课，<br>由任课教师逐条审阅、定稿。</p>
            <div class="yc-jacket-actions">
              <button class="yc-entry" type="button" data-cover-enter>进入协作圆桌 <span aria-hidden="true">→</span></button>
              <button class="yc-chat-entry" type="button" data-cover-chat>与智能体对话 <span aria-hidden="true">↗</span></button>
            </div>
          </div>
          <figure class="yc-tableau">
            <div class="yc-tableau-media">
              <img class="yc-tableau-still" width="1344" height="944" src="cover/studio.webp?v=8.1" fetchpriority="high"
                alt="六位 Q 版智能体围着一本打开的备课手记。">
              <video class="yc-camera-move" aria-hidden="true" muted playsinline preload="none" tabindex="-1"></video>
            </div>
          </figure>
          <button type="button" class="yc-cut" hidden>跳过动画 <span aria-hidden="true">↵</span></button>
        </section>
        <section class="yc-jacket-cast" aria-label="选择对话对象">
          <h2>选择对话对象</h2>
          <div class="yc-cast-links">
            ${cast.map(([id, role]) => `<button type="button" data-cover-role="${id}" aria-label="与${role}对话">
              <img src="avatars/${id}.webp" width="44" height="44" alt=""><span>${role}</span><i aria-hidden="true">↗</i>
            </button>`).join('')}
          </div>
        </section>
      </div>`;
    const root = host.querySelector('.yc-cover');
    const video = root.querySelector('video');
    const entry = root.querySelector('[data-cover-enter]');
    const cut = root.querySelector('.yc-cut');
    const controller = new AbortController();
    const opts = {signal:controller.signal};
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    let entering = false, closed = false, timeout, warmTimer;

    function warm() {
      if (reduced.matches || closed || location.protocol === 'file:' || video.getAttribute('src')) return;
      video.preload = 'auto';
      video.src = 'cover/enter.mp4?v=8.1';
      video.load();
    }
    function finish() {
      if (closed || !entering) return;
      entering = false;
      clearTimeout(timeout);
      enter();
    }
    function start() {
      if (entering || closed) return;
      entering = true;
      if (reduced.matches) { finish(); return; }
      warm();
      cut.hidden = false;
      root.classList.add('yc-departing');
      cut.focus({preventScroll:true});
      if (!video.src || video.readyState < 2) {
        root.classList.add('yc-fallback-camera');
        timeout = setTimeout(finish, 520);
        return;
      }
      // The clip is a real moving orthographic camera in the same scene as the opening frame.
      timeout = setTimeout(finish, 1450);
      const playback = video.play();
      if (playback) playback.catch(() => {
        if (closed || !entering) return;
        root.classList.add('yc-fallback-camera');
        clearTimeout(timeout); timeout = setTimeout(finish, 500);
      });
    }
    function goChat(role) {
      if (!entering && !closed) chat(role);
    }
    entry.addEventListener('pointerenter', warm, opts);
    entry.addEventListener('focus', warm, opts);
    entry.addEventListener('click', start, opts);
    cut.addEventListener('click', finish, opts);
    root.querySelector('[data-cover-chat]').addEventListener('click', () => goChat(), opts);
    root.querySelectorAll('[data-cover-role]').forEach(button => {
      button.addEventListener('click', () => goChat(button.dataset.coverRole), opts);
    });
    document.addEventListener('keydown', event => {
      if (entering && event.key === 'Escape') {event.preventDefault(); finish();}
    }, opts);
    video.addEventListener('playing', () => {if (entering) root.classList.add('yc-camera-playing');},opts);
    video.addEventListener('ended', finish, opts);
    reduced.addEventListener('change', () => {if (reduced.matches && entering) finish();},opts);
    warmTimer = setTimeout(warm, 450);
    teardown = () => {
      closed = true;
      clearTimeout(timeout); clearTimeout(warmTimer);
      controller.abort();
      video.pause();
      if (video.hasAttribute('src')) {video.removeAttribute('src'); video.load();}
    };
  }
  window.YincaiCover = Object.freeze({render, leave});
})();
