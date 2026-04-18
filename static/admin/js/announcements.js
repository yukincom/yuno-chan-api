// announcements.js - 定時コール

let annData = [];

async function loadAnnouncements() {
  document.getElementById('ann-loading').style.display = '';
  document.getElementById('ann-content').style.display = 'none';
  try {
    const res = await fetch('/admin/api/announcements');
    annData = await res.json();
    renderAnnouncements();
  } catch(e) {
    toast('読み込み失敗: ' + e.message, 'err');
  }
}

function renderAnnouncements() {
  const container = document.getElementById('ann-content');
  const sorted = [...annData].sort((a, b) => a.hour * 60 + a.minute - (b.hour * 60 + b.minute));
  container.innerHTML = sorted.map((item, idx) => buildAnnCard(item, idx)).join('');
  document.getElementById('ann-loading').style.display = 'none';
  document.getElementById('ann-content').style.display = '';
}

function buildAnnCard(item, idx) {
  const hh = String(item.hour).padStart(2, '0');
  const mm = String(item.minute).padStart(2, '0');
  const wOnly   = item.weekday_only  ? 'on' : '';
  const holOnly = item.holiday_only  ? 'on' : '';
  const weather = item.with_weather  ? 'on' : '';
  const wtTarget = item.weather_target === 'tomorrow' ? 'on' : '';

  return `
    <div class="ann-card" data-idx="${idx}">
      <div class="ann-card-head">
        <span class="ann-time-badge">🕐 ${hh}:${mm}</span>
        <button class="btn-danger btn-sm" onclick="removeAnnouncement(${idx})">削除</button>
      </div>
      <div class="grid-2" style="margin-bottom:10px">
        <div class="field">
          <label>時（0〜23）</label>
          <input type="number" min="0" max="23" value="${esc(item.hour)}"
            oninput="updateAnn(${idx}, 'hour', +this.value); refreshAnnTimeBadge(this, ${idx})">
        </div>
        <div class="field">
          <label>分（0〜59）</label>
          <input type="number" min="0" max="59" value="${esc(item.minute)}"
            oninput="updateAnn(${idx}, 'minute', +this.value); refreshAnnTimeBadge(this, ${idx})">
        </div>
      </div>
      <div class="field">
        <label>メッセージ</label>
        <textarea oninput="updateAnn(${idx}, 'message', this.value)">${esc(item.message)}</textarea>
      </div>
      <div class="ann-flags">
        <span class="ann-flag ${wOnly}"   onclick="toggleAnnFlag(this, ${idx}, 'weekday_only')">📅 平日のみ</span>
        <span class="ann-flag ${holOnly}" onclick="toggleAnnFlag(this, ${idx}, 'holiday_only')">🎌 祝日のみ</span>
        <span class="ann-flag ${weather}" onclick="toggleAnnWeather(this, ${idx})">☀️ 天気を追加</span>
        <span class="ann-flag ${wtTarget}" id="ann-tomorrow-${idx}"
          style="display:${weather ? 'inline-flex' : 'none'}"
          onclick="toggleAnnFlag(this, ${idx}, 'weather_target', 'tomorrow', '')">
          🌅 明日の天気
        </span>
      </div>
    </div>
  `;
}

function updateAnn(idx, key, value) { annData[idx][key] = value; }

function refreshAnnTimeBadge(input, idx) {
  const badge = input.closest('.ann-card').querySelector('.ann-time-badge');
  const hh = String(annData[idx].hour ?? 0).padStart(2, '0');
  const mm = String(annData[idx].minute ?? 0).padStart(2, '0');
  badge.textContent = `🕐 ${hh}:${mm}`;
}

function toggleAnnFlag(el, idx, key, onVal = true, offVal = false) {
  annData[idx][key] = el.classList.toggle('on') ? onVal : offVal;
}

function toggleAnnWeather(el, idx) {
  const isOn = el.classList.toggle('on');
  annData[idx].with_weather = isOn;
  const tb = document.getElementById(`ann-tomorrow-${idx}`);
  if (tb) tb.style.display = isOn ? 'inline-flex' : 'none';
  if (!isOn) {
    delete annData[idx].weather_target;
    if (tb) tb.classList.remove('on');
  }
}

function addAnnouncement() {
  annData.push({hour: 8, minute: 0, message: '', with_weather: false, weekday_only: false});
  renderAnnouncements();
  const cards = document.querySelectorAll('.ann-card');
  if (cards.length) cards[cards.length - 1].scrollIntoView({behavior: 'smooth', block: 'center'});
}

function removeAnnouncement(idx) {
  if (!confirm('この定時コールを削除しますか？')) return;
  annData.splice(idx, 1);
  renderAnnouncements();
}

async function saveAnnouncements() {
  try {
    const res = await fetch('/admin/api/announcements', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(annData)
    });
    const data = await res.json();
    if (data.ok) toast('✅ 保存しました');
    else toast('❌ 保存失敗: ' + data.error, 'err');
  } catch(e) {
    toast('❌ 通信エラー: ' + e.message, 'err');
  }
}
