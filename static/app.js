const btn = document.getElementById('scrapeBtn');
const ta = document.getElementById('urls');
const statusEl = document.getElementById('status');
const tbody = document.querySelector('#results tbody');

function addRow(obj, idx){
  const tr = document.createElement('tr');
  // input URL plain text (no hyperlink)
  const inputCell = `<td>${idx+1}</td><td class="mono">${(obj.input_url||'').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</td>`;
  tr.innerHTML = `
    ${inputCell}
    <td>${obj.title ?? 'N/A'}</td>
    <td>${obj.duration_seconds ?? 'N/A'}</td>
    <td>${obj.duration_hhmmss ?? 'N/A'}</td>
    <td>${obj.views ?? 'N/A'}</td>
    <td>${obj.upload_date ?? 'N/A'}</td>
    <td>${obj.channel_url && obj.channel_url !== 'N/A' ? `<a href="${obj.channel_url}" target="_blank" rel="noopener">${obj.channel_url}</a>` : 'N/A'}</td>
    <td>${obj.channel_name ?? 'N/A'}</td>
    <td>${obj.subscribers ?? 'N/A'}</td>
    <td>${obj.status}${obj.error ? ' - ' + obj.error : ''}</td>
  `;
  tbody.appendChild(tr);
}

btn.addEventListener('click', async () => {
  const lines = ta.value.split(/\n+/).map(s => s.trim()).filter(Boolean);
  if(!lines.length){
    alert('Please paste at least one VK/VKvideo URL.');
    return;
  }
  btn.disabled = true; tbody.innerHTML=''; statusEl.textContent = 'Scraping...';
  try{
    const res = await fetch('/api/scrape', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ urls: lines })
    });
    const json = await res.json();
    (json.results || []).forEach((r, i) => addRow(r, i));
    statusEl.textContent = `Done. ${json.results?.length || 0} URL(s).`;
  }catch(e){
    console.error(e);
    statusEl.textContent = 'Error: ' + e.message;
  }finally{
    btn.disabled = false;
  }
});
