// andy.js - Mindcraft / アンディ

let andyJson = null;

async function loadAndy() {
  document.getElementById('andy-loading').style.display = '';
  document.getElementById('andy-content').style.display = 'none';
  try {
    const [jsonRes, envRes] = await Promise.all([
      fetch('/admin/api/andy'),
      fetch('/admin/api/andy_env'),
    ]);
    andyJson = await jsonRes.json();
    const andyEnvGroups = await envRes.json();

    document.getElementById('andy-name').value        = andyJson.name ?? '';
    document.getElementById('andy-model').value       = andyJson.model ?? '';
    document.getElementById('andy-embed-api').value   = andyJson.embedding?.api ?? '';
    document.getElementById('andy-embed-model').value = andyJson.embedding?.model ?? '';
    document.getElementById('andy-speak').value       = andyJson.speak ?? '';

    renderEnvGroups(andyEnvGroups, 'andy-env-content');

    document.getElementById('andy-loading').style.display = 'none';
    document.getElementById('andy-content').style.display = '';
  } catch(e) {
    toast('読み込み失敗: ' + e.message, 'err');
  }
}

async function saveAndy() {
  try {
    andyJson.name  = document.getElementById('andy-name').value;
    andyJson.model = document.getElementById('andy-model').value;
    andyJson.embedding = {
      api:   document.getElementById('andy-embed-api').value,
      model: document.getElementById('andy-embed-model').value,
    };
    andyJson.speak = document.getElementById('andy-speak').value;

    const envUpdates = collectEnvValues('andy-env-content');
    const [jsonRes, envRes] = await Promise.all([
      fetch('/admin/api/andy', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(andyJson)
      }),
      fetch('/admin/api/andy_env', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(envUpdates)
      }),
    ]);
    const jd = await jsonRes.json();
    const ed = await envRes.json();
    if (jd.ok && ed.ok) toast('✅ 保存しました');
    else toast('❌ 保存失敗', 'err');
  } catch(e) { toast('❌ 通信エラー: ' + e.message, 'err'); }
}
