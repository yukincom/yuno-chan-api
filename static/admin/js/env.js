// env.js - 設定（.env）

async function loadEnv() {
  document.getElementById('env-loading').style.display = '';
  document.getElementById('env-content').style.display = 'none';
  try {
    const res = await fetch('/admin/api/env');
    const groups = await res.json();
    renderEnvGroups(groups, 'env-content');
    document.getElementById('env-loading').style.display = 'none';
    document.getElementById('env-content').style.display = '';
  } catch(e) { toast('読み込み失敗: ' + e.message, 'err'); }
}

async function saveEnv() {
  try {
    const res = await fetch('/admin/api/env', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(collectEnvValues('env-content'))
    });
    const data = await res.json();
    if (data.ok) toast('✅ 保存しました（サーバー再起動で反映）');
    else toast('❌ 保存失敗: ' + data.error, 'err');
  } catch(e) { toast('❌ 通信エラー: ' + e.message, 'err'); }
}
