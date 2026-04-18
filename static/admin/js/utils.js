// utils.js - 共通ユーティリティ

function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  el.classList.add('active');
}

function toast(msg, type = 'ok') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = type;
  setTimeout(() => { el.className = ''; el.textContent = ''; }, 3000);
}

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ===== envレンダリング共通関数 =====
function renderEnvGroups(groups, containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';

  for (const group of groups) {
    const section = document.createElement('div');
    section.className = 'env-group';
    section.innerHTML = `<div class="env-group-title">${esc(group.group)}</div>`;

    const grid = document.createElement('div');
    grid.className = 'grid-2';

    for (const item of group.items) {
      const field = document.createElement('div');
      field.className = 'field';

      if (item.type === 'empty') {
        // 空のdivでグリッドの穴埋め
      } else if (item.type === 'datalist') {
        const isVoicevox = item.key === 'VOICEVOX_SPEAKER_ID';
        const optionsHtml = (item.options || []).map(o => {
          const val = isVoicevox ? o.split(':')[0].trim() : o;
          const selected = val === item.value ? 'selected' : '';
          return `<option value="${esc(val)}" ${selected}>${esc(o)}</option>`;
        }).join('');
        field.innerHTML = `
          <label>${esc(item.label)} <small style="color:#aaa">${esc(item.key)}</small></label>
          <select data-key="${esc(item.key)}">${optionsHtml}</select>
        `;
      } else if (item.type === 'select') {
        const optionsHtml = (item.options || []).map(o => {
          const [val, label] = o.split(':');
          const selected = val === item.value ? 'selected' : '';
          return `<option value="${esc(val)}" ${selected}>${esc(label ?? val)}</option>`;
        }).join('');
        field.innerHTML = `
          <label>${esc(item.label)} <small style="color:#aaa">${esc(item.key)}</small></label>
          <select data-key="${esc(item.key)}">${optionsHtml}</select>
        `;
      } else if (item.type === 'textarea') {
        field.style.gridColumn = '1 / -1';
        field.innerHTML = `
          <label>${esc(item.label)} <small style="color:#aaa">${esc(item.key)}</small></label>
          <textarea data-key="${esc(item.key)}">${esc(item.value)}</textarea>
        `;
      } else {
        field.innerHTML = `
          <label>${esc(item.label)} <small style="color:#aaa">${esc(item.key)}</small></label>
          <input type="${esc(item.type)}" data-key="${esc(item.key)}" value="${esc(item.value)}"
            ${item.type === 'password' ? 'autocomplete="off"' : ''}>
        `;
      }
      grid.appendChild(field);
    }
    section.appendChild(grid);
    container.appendChild(section);
  }
}

function collectEnvValues(containerId) {
  const updates = {};
  document.querySelectorAll(`#${containerId} [data-key]`).forEach(el => {
    updates[el.dataset.key] = el.value;
  });
  return updates;
}
