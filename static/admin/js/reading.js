// reading.js - 読み上げ辞書

let readingData = [];

async function loadReading() {
  document.getElementById('reading-loading').style.display = '';
  document.getElementById('reading-content').style.display = 'none';
  try {
    const res = await fetch('/admin/api/reading_map');
    readingData = await res.json();
    renderReading();
  } catch(e) {
    toast('読み込み失敗: ' + e.message, 'err');
  }
}

function renderReading() {
  const tbody = document.getElementById('reading-tbody');
  tbody.innerHTML = readingData.map((item, idx) => `
    <tr>
      <td><input type="text" value="${esc(item.word)}"
        oninput="readingData[${idx}].word = this.value"></td>
      <td><input type="text" value="${esc(item.reading)}"
        oninput="readingData[${idx}].reading = this.value"></td>
      <td style="text-align:center">
        <button class="btn-danger btn-sm" onclick="removeReadingRow(${idx})">削除</button>
      </td>
    </tr>
  `).join('');
  document.getElementById('reading-loading').style.display = 'none';
  document.getElementById('reading-content').style.display = '';
}

function addReadingRow() {
  readingData.push({word: '', reading: ''});
  renderReading();
  const rows = document.querySelectorAll('#reading-tbody tr');
  if (rows.length) rows[rows.length - 1].querySelector('input').focus();
}

function removeReadingRow(idx) {
  readingData.splice(idx, 1);
  renderReading();
}

async function saveReading() {
  try {
    const res = await fetch('/admin/api/reading_map', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(readingData.filter(r => r.word))
    });
    const data = await res.json();
    if (data.ok) toast('✅ 保存しました');
    else toast('❌ 保存失敗: ' + data.error, 'err');
  } catch(e) {
    toast('❌ 通信エラー: ' + e.message, 'err');
  }
}
