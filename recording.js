/* Only nonsecret counters and a local configuration acknowledgement belong here. */
(() => {
  'use strict';
  const enabled = new URLSearchParams(location.search).get('recording') === '1';
  const prefix = 'yincai.recording.1.';
  const limit = 2;

  function read() {
    const used = Number(sessionStorage.getItem(prefix + 'used') || 0);
    if (!Number.isInteger(used) || used < 0 || used > limit) throw Error('录制次数记录异常，请新开独立演示标签页。');
    return {used, ready: sessionStorage.getItem(prefix + 'ready') === '1', failed: sessionStorage.getItem(prefix + 'failed') === '1'};
  }
  function confirmSettings() {
    if (enabled) sessionStorage.setItem(prefix + 'ready', '1');
  }
  function unavailable(state) {
    if (!state.ready) return '请先在模型设置中保存云端配置。';
    if (state.failed) return '上次请求未完成，本次演示已暂停发送。';
    if (state.used >= limit) return '本次演示的两次对话均已使用。';
    return '';
  }
  function status() {
    if (!enabled) return '';
    try {
      const state = read();
      return unavailable(state);
    } catch {return '无法读取本次录制的请求次数，已暂停发送。';}
  }
  function canSend() {
    if (!enabled) return true;
    try {return !unavailable(read());} catch {return false;}
  }
  function reserve() {
    if (!enabled) return;
    const state = read(), reason = unavailable(state);
    if (reason) throw Error(reason);
    sessionStorage.setItem(prefix + 'used', String(state.used + 1));
  }
  function pauseAfterFailure() {
    if (enabled) sessionStorage.setItem(prefix + 'failed', '1');
  }
  window.YincaiRecording = Object.freeze({enabled, confirmSettings, status, canSend, reserve, pauseAfterFailure});
})();
