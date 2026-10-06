'use strict';
function math(root) {
  if (window.renderMathInElement) window.renderMathInElement(root, {
    delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],
    trust:false, strict:'error', throwOnError:false, maxExpand:1000, maxSize:20
  });
}
math(document.querySelector('main'));
document.querySelectorAll('input[type="password"]').forEach(input => {
  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'password-toggle';
  toggle.textContent = '表示';
  toggle.setAttribute('aria-controls', input.id);
  toggle.setAttribute('aria-pressed', 'false');
  const label = input.labels[0]?.textContent.trim().replace(/[:：]$/, '') || 'パスワード';
  toggle.setAttribute('aria-label', label + 'を表示');
  toggle.addEventListener('click', () => {
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    toggle.textContent = visible ? '非表示' : '表示';
    toggle.setAttribute('aria-label', label + (visible ? 'を非表示' : 'を表示'));
    toggle.setAttribute('aria-pressed', String(visible));
  });
  input.after(toggle);
});
const form = document.querySelector('#answer-form');
if (form) {
  let selected = null;
  let pending = false;
  const status = document.querySelector('#send-status');
  const retry = document.querySelector('#retry');
  async function send() {
    if (pending || selected === null) return;
    pending = true;
    form.querySelectorAll('button[type="submit"], button[name]').forEach(button => button.disabled = true);
    retry.hidden = true;
    status.textContent = '送信中…';
    status.classList.remove('error');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const data = new FormData(form);
      data.set(selected.name, selected.value);
      const response = await fetch(form.action, {method:'POST', body:data, headers:{Accept:'application/json'}, signal:controller.signal});
      const result = await response.json();
      if (result.saved && result.html) {
        const target = document.querySelector('#result');
        target.innerHTML = result.html;
        math(target);
        document.querySelector('#previous-unanswered')?.remove();
        target.focus({preventScroll: true});
        target.scrollIntoView({block: 'start'});
        status.textContent = result.error || '';
        status.classList.toggle('error', Boolean(result.error));
        selected = null;
      } else if ([400,401,403,404,409].includes(response.status)) {
        status.textContent = result.error || 'ページを再読み込みしてください。';
        status.classList.add('error');
      } else throw new Error('Unknown save state');
    } catch {
      status.textContent = '保存状況を確認できません。同じ回答を再送してください。';
      status.classList.add('error');
      retry.hidden = false;
    } finally {
      clearTimeout(timer);
      pending = false;
    }
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (pending || selected !== null || !event.submitter) return;
    selected = {name: event.submitter.name, value: event.submitter.value};
    send();
  });
  retry.addEventListener('click', send);
}
// A choice image gets a separate zoom control so tapping the choice still answers.
document.querySelectorAll('.choice:not(.choice-numbers-only) img').forEach(img => {
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

// Filter forms share server-rendered previews. Preserve the filters themselves and open topics.
const filterForm = document.querySelector('form[data-preview-url]');
if (filterForm) {
  const preview = document.querySelector('#filter-preview');
  const status = document.querySelector('[data-preview-status]');
  const start = filterForm.querySelector('[data-start]');
  let controller;
  let generation = 0;
  filterForm.querySelector('[data-apply]')?.setAttribute('hidden', '');
  async function updatePreview() {
    const current = ++generation;
    controller?.abort();
    const requestController = controller = new AbortController();
    const timer = setTimeout(() => requestController.abort(), 10000);
    filterForm.querySelectorAll('[data-field-errors]').forEach(container => container.textContent = '');
    filterForm.querySelectorAll('[aria-invalid]').forEach(input => input.removeAttribute('aria-invalid'));
    preview.hidden = true;
    preview.setAttribute('aria-busy', 'true');
    if (start) start.disabled = true;
    status.textContent = '条件を反映しています…';
    status.classList.remove('error');
    try {
      const query = new URLSearchParams(new FormData(filterForm));
      const response = await fetch(filterForm.dataset.previewUrl + '?' + query, {
        headers: {Accept:'application/json'}, signal:requestController.signal
      });
      const result = await response.json();
      if (current !== generation) return;
      if ((!response.ok && response.status !== 400) || typeof result.html !== 'string') throw new Error('Preview unavailable');
      filterForm.querySelectorAll('[data-field-errors]').forEach(container => {
        const errors = result.errors[container.dataset.fieldErrors] || [];
        container.textContent = errors.join(' ');
        filterForm.querySelectorAll(`[name="${container.dataset.fieldErrors}"]`).forEach(input => {
          if (errors.length) {
            input.setAttribute('aria-invalid', 'true');
            input.setAttribute('aria-describedby', container.id);
          } else {
            input.removeAttribute('aria-invalid');
            input.removeAttribute('aria-describedby');
          }
        });
      });
      const openSubjects = new Set(Array.from(preview.querySelectorAll('details[open]'), details => details.dataset.topicSubject));
      preview.innerHTML = result.html;
      preview.querySelectorAll('details[data-topic-subject]').forEach(details => {
        details.open = openSubjects.has(details.dataset.topicSubject);
      });
      preview.hidden = false;
      filterForm.querySelector('[data-apply]')?.setAttribute('hidden', '');
      if (start) start.disabled = !result.valid || result.count === 0;
      status.textContent = result.valid ? (start ? `対象 ${result.count} 問です。` : '学習の記録を更新しました。') : '選択した条件を確認してください。';
    } catch {
      if (current !== generation) return;
      status.classList.add('error');
      status.textContent = '条件を反映できませんでした。条件を変更するか、もう一度適用してください。';
      filterForm.querySelector('[data-apply]')?.removeAttribute('hidden');
    } finally {
      clearTimeout(timer);
      if (current === generation) preview.removeAttribute('aria-busy');
    }
  }
  filterForm.addEventListener('change', updatePreview);
  if (filterForm.id === 'study-settings') {
    const topics = filterForm.querySelector('#id_topics');
    if (topics) {
      const clear = document.createElement('button');
      clear.type = 'button';
      clear.textContent = 'すべて外す';
      clear.addEventListener('click', () => {
        topics.querySelectorAll('input[type="checkbox"]').forEach(input => input.checked = false);
        updatePreview();
      });
      topics.before(clear);
    }
  }
  filterForm.addEventListener('submit', event => {
    if (event.submitter?.hasAttribute('data-start')) return;
    event.preventDefault();
    filterForm.querySelector('[data-apply]')?.setAttribute('hidden', '');
    updatePreview();
  });
}
