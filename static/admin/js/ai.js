// ai.js - AI設定

async function loadAiEnv() {
  document.getElementById('ai-loading').style.display = '';
  document.getElementById('ai-content').style.display = 'none';
  try {
    const res = await fetch('/admin/api/ai_env');
    const groups = await res.json();
    renderEnvGroups(groups, 'ai-content');
    document.getElementById('ai-loading').style.display = 'none';
    document.getElementById('ai-content').style.display = '';
    // モデルフィールドにチェックUIを注入
    _injectModelCheckers();
  } catch(e) { toast('読み込み失敗: ' + e.message, 'err'); }
}

async function saveAiEnv() {
  try {
    const res = await fetch('/admin/api/ai_env', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(collectEnvValues('ai-content'))
    });
    const data = await res.json();
    if (data.ok) toast('✅ 保存しました（サーバー再起動で反映）');
    else toast('❌ 保存失敗: ' + data.error, 'err');
  } catch(e) { toast('❌ 通信エラー: ' + e.message, 'err'); }
}

// ── MLXモデルチェック UI の注入 ──────────────────────────

function _injectModelCheckers() {
  // MLXモデルチェックが必要なフィールド
  ['AI_CHAT_MODEL', 'AI_SUMMARY_MODEL'].forEach(key => {
    const input = document.querySelector(`[data-key="${key}"]`);
    if (!input) return;

    // ラッパーをflexにしてボタンを横に並べる
    const field = input.closest('.field');
    input.style.flex = '1';

    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex; gap:8px; align-items:center;';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    // ステータス表示
    const status = document.createElement('span');
    status.id = `mlx-status-${key}`;
    status.style.cssText = 'font-size:13px; white-space:nowrap; min-width:24px;';
    wrap.appendChild(status);

    // ダウンロードボタン
    const btn = document.createElement('button');
    btn.id = `mlx-btn-${key}`;
    btn.className = 'btn-secondary btn-sm';
    btn.textContent = '📥 DL';
    btn.style.display = 'none';
    btn.onclick = () => _startDownload(key);
    wrap.appendChild(btn);

    // 入力変更時に再チェック
    input.addEventListener('change', () => _checkModel(key));
    input.addEventListener('blur',   () => _checkModel(key));

    // 初回チェック
    _checkModel(key);
  });
}

async function _checkModel(key) {
  const input  = document.querySelector(`[data-key="${key}"]`);
  const status = document.getElementById(`mlx-status-${key}`);
  const btn    = document.getElementById(`mlx-btn-${key}`);
  if (!input || !status) return;

  const model = input.value.trim();
  if (!model) { status.textContent = ''; btn.style.display = 'none'; return; }

  status.textContent = '⏳';
  try {
    const res  = await fetch(`/admin/api/mlx/check?model=${encodeURIComponent(model)}`);
    const data = await res.json();

    if (data.status === 'downloading') {
      status.textContent = '⏳ DL中...';
      btn.style.display = 'none';
      // ポーリング継続
      setTimeout(() => _checkModel(key), 3000);
    } else if (data.cached) {
      status.textContent = '✅';
      btn.style.display = 'none';
    } else {
      status.innerHTML = '<span style="color:var(--danger)">❌ 未DL</span>';
      btn.style.display = '';
    }
  } catch(e) {
    status.textContent = '⚠️';
  }
}

async function _startDownload(key) {
  const input  = document.querySelector(`[data-key="${key}"]`);
  const status = document.getElementById(`mlx-status-${key}`);
  const btn    = document.getElementById(`mlx-btn-${key}`);
  const model  = input?.value.trim();
  if (!model) return;

  btn.style.display = 'none';
  status.textContent = '⏳ DL中...';

  try {
    await fetch('/admin/api/mlx/download', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ model })
    });
    // 3秒ごとにポーリング
    const poll = setInterval(async () => {
      const res  = await fetch(`/admin/api/mlx/check?model=${encodeURIComponent(model)}`);
      const data = await res.json();
      if (data.cached) {
        status.textContent = '✅';
        btn.style.display = 'none';
        clearInterval(poll);
        toast('✅ ダウンロード完了: ' + model);
      } else if (data.status === 'error') {
        status.innerHTML = '<span style="color:var(--danger)">❌ DL失敗</span>';
        btn.style.display = '';
        clearInterval(poll);
        toast('❌ ダウンロード失敗', 'err');
      }
    }, 3000);
  } catch(e) {
    toast('❌ 通信エラー: ' + e.message, 'err');
  }
}
