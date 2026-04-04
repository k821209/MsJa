// Copy buttons — copy to clipboard
document.addEventListener('click', (e) => {
  const btn = e.target.closest('.btn-copy');
  if (!btn) return;
  const text = btn.dataset.text;
  const original = btn.textContent;
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = original;
      btn.classList.remove('copied');
    }, 1500);
  });
});

// Quick-start buttons — open terminal and send command
document.addEventListener('click', (e) => {
  const btn = e.target.closest('.btn-quick');
  if (!btn || btn.disabled) return;
  const command = btn.dataset.text;
  // Send to parent shell.html to open terminal and type the command
  window.parent.postMessage({ type: 'terminal-send', command: command }, '*');
});

// Listen for terminal state from parent shell.html
window.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'terminal-busy') {
    document.querySelectorAll('.btn-quick').forEach(btn => {
      btn.disabled = e.data.busy;
      btn.title = e.data.busy ? 'Terminal is already in use' : '';
    });
  }
});

// Ask parent for terminal state on load
window.parent.postMessage({ type: 'terminal-status-request' }, '*');
