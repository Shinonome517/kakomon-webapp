'use strict';
function math(root) {
  if (window.renderMathInElement) window.renderMathInElement(root, {
    delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],
    trust:false, strict:'error', throwOnError:false, maxExpand:1000, maxSize:20
  });
}
math(document.querySelector('main'));
const form = document.querySelector('#answer-form');
if (form) {
  let selected = null;
  let pending = false;
  const status = document.querySelector('#send-status');
  const retry = document.querySelector('#retry');
  async function send() {
    if (pending || selected === null) return;
    pending = true;
    form.querySelectorAll('.choice').forEach(button => button.disabled = true);
    retry.hidden = true;
    status.textContent = '送信中…';
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const data = new FormData(form);
      data.set('choice', selected);
      const response = await fetch(form.action, {method:'POST', body:data, headers:{Accept:'application/json'}, signal:controller.signal});
      const result = await response.json();
      if (result.saved && result.html) {
        const target = document.querySelector('#result');
        target.innerHTML = result.html;
        math(target);
        target.focus();
        status.textContent = result.error || '保存しました。解説を読んでから次へ進めます。';
        selected = null;
      } else if ([400,401,403,404,409].includes(response.status)) {
        status.textContent = result.error || 'ページを再読み込みしてください。';
      } else throw new Error('Unknown save state');
    } catch {
      status.textContent = '保存状況を確認できません。同じ回答を再送します。';
      retry.hidden = false;
    } finally {
      clearTimeout(timer);
      pending = false;
    }
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (pending || selected !== null || !event.submitter) return;
    selected = event.submitter.value;
    send();
  });
  retry.addEventListener('click', send);
}
// A choice image gets a separate zoom control so tapping the choice still answers.
document.querySelectorAll('.choice img').forEach(img => {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'figure choice-zoom';
  button.textContent = '選択肢の図を拡大: ' + img.alt;
  button.dataset.src = img.src;
  button.dataset.alt = img.alt;
  img.closest('.choice').after(button);
});
const dialog = document.querySelector('#image-dialog');
const zoom = document.querySelector('#zoom');
const large = document.querySelector('#large-image');
let opener = null;
let imageWidth = 0;
document.addEventListener('click', event => {
  const button = event.target.closest('.figure');
  if (!button) return;
  opener = button;
  const img = button.querySelector('img');
  large.src = img ? img.src : button.dataset.src;
  large.alt = img ? img.alt : button.dataset.alt;
  zoom.value = '100';
  dialog.showModal();
  imageWidth = dialog.querySelector('.zoom-area').clientWidth;
  large.style.width = imageWidth + 'px';
});
zoom.addEventListener('input', () => large.style.width = imageWidth * Number(zoom.value) / 100 + 'px');
document.querySelector('#close-image').addEventListener('click', () => dialog.close());
dialog.addEventListener('close', () => opener?.focus());
