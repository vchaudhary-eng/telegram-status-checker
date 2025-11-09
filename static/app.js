const btn = document.getElementById('scrapeBtn');
const ta = document.getElementById('urls');
const statusEl = document.getElementById('status');
const tbody = document.querySelector('#results tbody');

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

function addRow(obj, idx){
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td>${idx+1}</td>
    <td><div class="mono nowrap">${escapeHtml(obj.input_url)}</div></td>
    <td>${obj.title}</td>
    <td>${obj.duration_seconds}</td>
    <td>${obj.duration_hhmmss}</td>
    <td>${obj.views}</td>
    <td>${obj.upload_date}</td>
    <td>${obj.channel_url !== 'N/A' ? `<span class="mono nowrap">${escapeHtml(obj.channel_url)}</span>` : 'N/A'}</td>
    <td>${obj.channel_name}</td>
    <td>${obj.subscribers}</td>
    <td>${obj.status}${obj.error ? ' - ' + obj.error : ''}</td>
  `;
  tbody.appendChild(tr);
}

btn.addEventListener('click', async () => {
  const lines = ta.value.split(/\n+/).map(s => s.trim()).filter(Boolean);
  if(!lines.length){ alert('Please paste at least one VK video URL.'); return; }
  btn.disabled = true; tbody.innerHTML=''; statusEl.textContent = 'Scraping...';
  try{
    const res = await fetch('/api/scrape', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
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
