const btn = document.getElementById('scrapeBtn');
const ta = document.getElementById('urls');
const statusEl = document.getElementById('status');
const tbody = document.querySelector('#results tbody');

function textCell(text) {
  const td = document.createElement('td');
  td.textContent = text === null || text === undefined ? 'N/A' : String(text);
  return td;
}

function addRow(obj, idx) {
  const tr = document.createElement('tr');

  tr.appendChild(textCell(idx + 1));

  // Input URL as plain text (not hyperlink)
  tr.appendChild(textCell(obj.input_url || 'N/A'));

  tr.appendChild(textCell(obj.title || 'N/A'));
  tr.appendChild(textCell(obj.duration_seconds || 'N/A'));
  tr.appendChild(textCell(obj.duration_hhmmss || 'N/A'));
  tr.appendChild(textCell(obj.views || 'N/A'));
  tr.appendChild(textCell(obj.upload_date || 'N/A'));
  tr.appendChild(textCell(obj.channel_url || 'N/A'));
  tr.appendChild(textCell(obj.channel_name || 'N/A'));
  tr.appendChild(textCell(obj.subscribers || 'N/A'));

  const st = document.createElement('td');
  st.textContent = obj.status || 'Error';
  st.className = (obj.status === 'Success') ? 'status-ok' : 'status-err';
  if (obj.error) st.title = obj.error;
  tr.appendChild(st);

  tbody.appendChild(tr);
}

btn.addEventListener('click', async () => {
  const lines = ta.value.split(/\n+/).map(s => s.trim()).filter(Boolean);
  if (!lines.length) {
    alert('Please paste at least one VK/VKvideo URL.');
    return;
  }
  // reset
  btn.disabled = true;
  tbody.innerHTML = '';
  statusEl.textContent = 'Scraping...';

  try {
    // progressive UX: we still POST all, then append rows in order we receive
    const res = await fetch('/api/scrape', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ urls: lines })
    });
    if (!res.ok) throw new Error('Request failed: ' + res.status);
    const json = await res.json();
    const arr = json.results || [];
    arr.forEach((r, i) => addRow(r, i));
    statusEl.textContent = `Done. ${arr.length} URL(s).`;
  } catch (e) {
    console.error(e);
    statusEl.textContent = 'Error: ' + e.message;
  } finally {
    btn.disabled = false;
  }
});
