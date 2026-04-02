// Terminal panel — xterm.js + WebSocket PTY
let term = null;
let ws = null;
let fitAddon = null;
let termOpen = false;

function toggleTerminal() {
  const panel = document.getElementById('terminal-panel');
  const icon = document.getElementById('term-icon');
  termOpen = !termOpen;

  if (termOpen) {
    panel.classList.remove('hidden');
    icon.textContent = '⏹';
    document.body.classList.add('terminal-active');
    if (!term) {
      initTerminal();
    } else {
      fitAddon.fit();
    }
  } else {
    panel.classList.add('hidden');
    icon.textContent = '▶';
    document.body.classList.remove('terminal-active');
  }
}

function initTerminal() {
  term = new Terminal({
    cursorBlink: true,
    fontSize: 13,
    fontFamily: "'SF Mono', 'Monaco', 'Menlo', 'Courier New', monospace",
    theme: {
      background: '#0d1117',
      foreground: '#e6edf3',
      cursor: '#58a6ff',
      selectionBackground: '#264f78',
      black: '#0d1117',
      red: '#f85149',
      green: '#3fb950',
      yellow: '#d29922',
      blue: '#58a6ff',
      magenta: '#bc8cff',
      cyan: '#39c5cf',
      white: '#e6edf3',
      brightBlack: '#484f58',
      brightRed: '#ff7b72',
      brightGreen: '#56d364',
      brightYellow: '#e3b341',
      brightBlue: '#79c0ff',
      brightMagenta: '#d2a8ff',
      brightCyan: '#56d4dd',
      brightWhite: '#f0f6fc',
    },
  });

  fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);

  const container = document.getElementById('terminal-container');
  term.open(container);
  fitAddon.fit();

  connectWebSocket();

  // Handle resize
  const resizeObserver = new ResizeObserver(() => {
    if (fitAddon && termOpen) fitAddon.fit();
  });
  resizeObserver.observe(container);

  term.onResize(({ cols, rows }) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'resize', cols, rows }));
    }
  });
}

function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws/terminal`);

  ws.onopen = () => {
    // Send initial size
    if (fitAddon) {
      fitAddon.fit();
      const dims = fitAddon.proposeDimensions();
      if (dims) {
        ws.send(JSON.stringify({ type: 'resize', cols: dims.cols, rows: dims.rows }));
      }
    }
  };

  ws.onmessage = (event) => {
    term.write(event.data);
  };

  ws.onclose = () => {
    term.write('\r\n\x1b[31m[Connection closed]\x1b[0m\r\n');
  };

  ws.onerror = () => {
    term.write('\r\n\x1b[31m[Connection error]\x1b[0m\r\n');
  };

  // Send keystrokes
  term.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', data }));
    }
  });
}

function newTerminal() {
  if (ws) ws.close();
  if (term) {
    term.clear();
    term.reset();
  }
  connectWebSocket();
}

function runClaude() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'input', data: 'claude\n' }));
  }
}

// Keyboard shortcut: Ctrl+`
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === '`') {
    e.preventDefault();
    toggleTerminal();
  }
});
