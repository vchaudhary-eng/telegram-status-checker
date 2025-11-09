const btn = document.getElementById('scrapeBtn');
const ta = document.getElementById('urls');
const statusEl = document.getElementById('status');
const tbody = document.querySelector('#results tbody');

function td(text) {
  const cell = document.createElement('td');
  cell.textContent = text;        // <-- plain text, not a hyperlink
  cell.className = 'mono';
  return cell;
}

function addRow(obj, idx){
  const tr = document.createElement('tr');

  // #
  const n = document.createElement('td');
  n.textContent = String(idx + 1);
  tr.appendChild(n);

  // Input URL (plain text)
  tr.appendChild(td(obj.input_url || ''));

  // Title (not mono)
  const t = document.createElement('td');
  t.textContent = obj.title;
  tr.appendChild(t);

  tr.appendChild(td(obj.duration_seconds));
  tr.appendChild(td(obj.duration_hhmmss));
  tr.appendChild(td(obj.views));
  tr.appendChild(td(obj.upload_date));
  tr.appendChild(td(obj.channel_url));
  tr.appendChild(td(obj.channel_name));
  tr.appendChild(td(obj.subscribers));

  const st = document.createElement('td');
