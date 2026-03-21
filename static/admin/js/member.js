// member.js - メンバー管理

let memberData = null;

async function loadMember() {
  document.getElementById('member-loading').style.display = '';
  document.getElementById('member-content').style.display = 'none';
  try {
    const res = await fetch('/admin/api/member');
    memberData = await res.json();
    renderMember();
  } catch(e) {
    toast('読み込み失敗: ' + e.message, 'err');
  }
}

function renderMember() {
  const container = document.getElementById('member-content');
  container.innerHTML = '';
  const sections = [
    { key: 'children', label: '学習者',     badge: 'child',  icon: '👶' },
    { key: 'family',   label: '家族',     badge: 'family', icon: '👨‍👩‍👦' },
    { key: 'friends',  label: 'フレンド', badge: 'friend', icon: '🤝' },
  ];
  for (const sec of sections) {
    const members = memberData[sec.key] ?? [];
    const sh = document.createElement('div');
    sh.style.cssText = 'display:flex; align-items:center; justify-content:space-between; margin:20px 0 8px;';
    sh.innerHTML = `
      <div class="section-label" style="margin:0">${sec.icon} ${sec.label}</div>
      <button class="btn-secondary btn-sm" onclick="addMember('${sec.key}')">＋ 追加</button>
    `;
    container.appendChild(sh);
    if (members.length === 0) {
      const empty = document.createElement('p');
      empty.style.cssText = 'color:var(--muted); font-size:13px; padding:8px 0;';
      empty.textContent = 'メンバーがいません';
      container.appendChild(empty);
    }
    members.forEach((m, idx) => container.appendChild(buildMemberCard(sec.key, idx, m, sec.badge)));
  }
  document.getElementById('member-loading').style.display = 'none';
  document.getElementById('member-content').style.display = '';
}

function buildMemberCard(category, idx, m, badgeClass) {
  const card = document.createElement('div');
  card.className = 'member-card';
  card.dataset.category = category;
  card.dataset.idx = idx;
  const displayName = Array.isArray(m.name) ? m.name[0] : (m.name ?? '新しいメンバー');
  const badgeLabel = { child: '学習者', family: '家族', friend: 'フレンド' }[badgeClass] ?? '';
  card.innerHTML = `
    <div class="member-head" onclick="toggleCard(this)">
      <div class="member-title">
        <span class="member-badge badge-${badgeClass}">${badgeLabel}</span>
        <span class="name-display">${esc(displayName)}</span>
      </div>
      <div style="display:flex; gap:8px; align-items:center">
        <button class="btn-danger btn-sm" onclick="event.stopPropagation(); removeMember('${category}', ${idx})">削除</button>
        <span class="chevron">▼</span>
      </div>
    </div>
    <div class="member-body">${buildMemberForm(category, idx, m, badgeClass)}</div>
  `;
  return card;
}

function buildMemberForm(category, idx, m, badgeClass) {
  const isFriend = badgeClass === 'friend';
  const nameVal = Array.isArray(m.name) ? m.name.join(', ') : (m.name ?? '');
  const callVal = Array.isArray(m.call) ? m.call.join(', ') : (m.call ?? '');
  let html = `
    <div class="grid-2">
      <div class="field">
        <label>名前（複数はカンマ区切り）</label>
        <input type="text" value="${esc(nameVal)}"
          oninput="updateMemberField('${category}', ${idx}, 'name', this.value)">
      </div>
      <div class="field">
        <label>呼び方（複数はカンマ区切り）</label>
        <input type="text" value="${esc(callVal)}"
          oninput="updateMemberField('${category}', ${idx}, 'call', this.value)">
      </div>
    </div>
    <div class="field">
      <label>発話パターン（Enterで追加）</label>
      ${buildTagInput(category, idx, 'speech_patterns', m.speech_patterns ?? [])}
    </div>
  `;
  if (!isFriend) {
    html += `
    <div class="field">
      <label>備考（LLMへのヒント）</label>
      <input type="text" value="${esc(m.notes ?? '')}"
        oninput="updateMemberField('${category}', ${idx}, 'notes', this.value)">
    </div>
    <div class="field">
      <label>好きなこと（Enterで追加）</label>
      ${buildTagInput(category, idx, 'interests', m.interests ?? [])}
    </div>
    <div class="grid-2">
      <div class="field">
        <label>LINE ユーザーID</label>
        <input type="text" value="${esc(m.line_user_id ?? '')}"
          oninput="updateMemberField('${category}', ${idx}, 'line_user_id', this.value)">
      </div>
      <div class="field">
        <label>Discord ユーザーID</label>
        <input type="text" value="${esc(m.discord_user_id ?? '')}"
          oninput="updateMemberField('${category}', ${idx}, 'discord_user_id', this.value)">
      </div>
    </div>`;
  }
  return html;
}

function buildTagInput(category, idx, field, tags) {
  return `
    <div class="tags-wrap" id="tags-${category}-${idx}-${field}">
      ${tags.map(t => `
        <span class="tag">${esc(t)}
          <span class="tag-del" onclick="removeTag('${category}', ${idx}, '${field}', '${esc(t)}')">×</span>
        </span>`).join('')}
      <input class="tag-input" type="text" placeholder="例：ただいま"
        onkeydown="handleTagKey(event, '${category}', ${idx}, '${field}', this)">
    </div>
  `;
}

function handleTagKey(e, category, idx, field, input) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault();
    const val = input.value.trim().replace(/,/g, '');
    if (!val) return;
    const arr = memberData[category][idx][field] ?? [];
    if (!arr.includes(val)) { arr.push(val); memberData[category][idx][field] = arr; }
    input.value = '';
    reRenderTagsWrap(category, idx, field);
  }
}

function removeTag(category, idx, field, tag) {
  memberData[category][idx][field] = (memberData[category][idx][field] ?? []).filter(t => t !== tag);
  reRenderTagsWrap(category, idx, field);
}

function reRenderTagsWrap(category, idx, field) {
  const wrap = document.getElementById(`tags-${category}-${idx}-${field}`);
  if (!wrap) return;
  const tags = memberData[category][idx][field] ?? [];
  const savedVal = wrap.querySelector('.tag-input')?.value ?? '';
  wrap.innerHTML = tags.map(t => `
    <span class="tag">${esc(t)}
      <span class="tag-del" onclick="removeTag('${category}', ${idx}, '${field}', '${esc(t)}')">×</span>
    </span>`).join('') + `
    <input class="tag-input" type="text" placeholder="例：ただいま" value="${esc(savedVal)}"
      onkeydown="handleTagKey(event, '${category}', ${idx}, '${field}', this)">
  `;
}

function updateMemberField(category, idx, field, value) {
  if (field === 'name' || field === 'call') {
    const parts = value.split(',').map(s => s.trim()).filter(Boolean);
    memberData[category][idx][field] = parts.length === 1 ? parts[0] : parts;
    const card = document.querySelector(`.member-card[data-category="${category}"][data-idx="${idx}"]`);
    if (card) {
      const newName = Array.isArray(memberData[category][idx].name)
        ? memberData[category][idx].name[0] : (memberData[category][idx].name ?? '');
      const disp = card.querySelector('.name-display');
      if (disp) disp.textContent = newName;
    }
  } else {
    memberData[category][idx][field] = value;
  }
}

function toggleCard(head) {
  head.nextElementSibling.classList.toggle('open');
  head.querySelector('.chevron').classList.toggle('open');
}

function addMember(category) {
  if (!memberData[category]) memberData[category] = [];
  const t = { name: '新しいメンバー', call: '', speech_patterns: [], notes: '', interests: [], line_user_id: '', discord_user_id: '' };
  if (category === 'friends') { delete t.line_user_id; delete t.discord_user_id; }
  memberData[category].push(t);
  renderMember();
  const cards = document.querySelectorAll(`.member-card[data-category="${category}"]`);
  const last = cards[cards.length - 1];
  if (last) { toggleCard(last.querySelector('.member-head')); last.scrollIntoView({behavior:'smooth',block:'center'}); }
}

function removeMember(category, idx) {
  if (!confirm('このメンバーを削除しますか？')) return;
  memberData[category].splice(idx, 1);
  renderMember();
}

async function saveMember() {
  try {
    const res = await fetch('/admin/api/member', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(memberData)
    });
    const data = await res.json();
    if (data.ok) toast('✅ 保存しました');
    else toast('❌ 保存失敗: ' + data.error, 'err');
  } catch(e) { toast('❌ 通信エラー: ' + e.message, 'err'); }
}
