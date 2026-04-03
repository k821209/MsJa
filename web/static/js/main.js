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
  if (!btn) return;
  const command = btn.dataset.text;
  // Send to parent shell.html to open terminal and type the command
  window.parent.postMessage({ type: 'terminal-send', command: command }, '*');
});
