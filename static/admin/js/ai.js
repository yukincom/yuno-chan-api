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
