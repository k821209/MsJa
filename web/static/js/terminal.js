// Terminal panel — xterm.js + WebSocket PTY
let term = null;
let ws = null;
let fitAddon = null;
let termOpen = false;
let fitTimeout = null;

function toggleTerminal() {
  const panel = document.getElementById('terminal-panel');
  const icon = document.getElementById('term-icon');
  termOpen = !termOpen;

  if (termOpen) {
    panel.classList.remove('hidden');
    icon.textContent = '⏹';
    if (!term) {
      // Delay init so the panel has layout dimensions
      requestAnimationFrame(() => {
        requestAnimationFrame(() => initTerminal());
      });
    } else {
      debouncedFit();
    }
  } else {
    panel.classList.add('hidden');
    icon.textContent = '▶';
  }
  broadcastTerminalState();
}

function debouncedFit() {
  if (fitTimeout) clearTimeout(fitTimeout);
  fitTimeout = setTimeout(() => {
    if (fitAddon && term && termOpen) {
      try { fitAddon.fit(); } catch(e) {}
    }
  }, 50);
}

function initTerminal() {
  const container = document.getElementById('terminal-container');

  term = new Terminal({
    cursorBlink: true,
    allowProposedApi: true,
    fontSize: 13,
    fontFamily: "'Noto Sans Mono', 'SF Mono', 'Monaco', 'Menlo', 'Courier New', monospace",
    scrollback: 5000,
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

  // Unicode 11 addon for correct CJK (Korean/Japanese/Chinese) character widths
  if (typeof Unicode11Addon !== 'undefined') {
    const u11 = new Unicode11Addon.Unicode11Addon();
    term.loadAddon(u11);
    term.unicode.activeVersion = '11';
  }

  term.open(container);

  // Fit after open with a small delay for layout to settle
  setTimeout(() => {
    fitAddon.fit();
    connectWebSocket();
  }, 100);

  // Resize observer — debounced to avoid thrashing
  const resizeObserver = new ResizeObserver(() => debouncedFit());
  resizeObserver.observe(container);

  // Send resize to PTY
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
    // Send initial size after connection
    setTimeout(() => {
      if (fitAddon) {
        fitAddon.fit();
        const dims = fitAddon.proposeDimensions();
        if (dims) {
          ws.send(JSON.stringify({ type: 'resize', cols: dims.cols, rows: dims.rows }));
        }
      }
    }, 150);
  };

  // Buffer incoming data and write in animation frames to reduce flicker
  let writeBuf = [];
  let writeScheduled = false;

  function flushWrites() {
    if (writeBuf.length > 0 && term) {
      const combined = writeBuf.join('');
      writeBuf = [];
      term.write(combined);
    }
    writeScheduled = false;
  }

  ws.onmessage = (event) => {
    if (event.data instanceof Blob) {
      event.data.text().then(text => {
        writeBuf.push(text);
        if (!writeScheduled) {
          writeScheduled = true;
          requestAnimationFrame(flushWrites);
        }
      });
    } else {
      writeBuf.push(event.data);
      if (!writeScheduled) {
        writeScheduled = true;
        requestAnimationFrame(flushWrites);
      }
    }
  };

  ws.onclose = () => {
    term.write('\r\n\x1b[31m[Connection closed]\x1b[0m\r\n');
  };

  ws.onerror = () => {
    term.write('\r\n\x1b[31m[Connection error]\x1b[0m\r\n');
  };

  term.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', data }));
    }
  });
}

// Keyboard shortcut: Ctrl+`
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === '`') {
    e.preventDefault();
    toggleTerminal();
  }
});

// Send command to terminal from iframe (e.g. quick-start buttons)
function sendToTerminal(command) {
  if (!termOpen) toggleTerminal();
  // Wait for terminal + websocket to be ready, then send
  const trySend = () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', data: command + '\n' }));
    } else {
      setTimeout(trySend, 200);
    }
  };
  // Small delay to let terminal open if it wasn't
  setTimeout(trySend, termOpen ? 0 : 500);
}

// Notify iframe of terminal busy state
function broadcastTerminalState() {
  const iframe = document.getElementById('content-frame');
  if (iframe && iframe.contentWindow) {
    iframe.contentWindow.postMessage({ type: 'terminal-busy', busy: termOpen }, '*');
  }
}

window.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'terminal-send' && e.data.command) {
    sendToTerminal(e.data.command);
    // Notify iframe that terminal is now busy
    setTimeout(broadcastTerminalState, 600);
  }
  if (e.data && e.data.type === 'terminal-status-request') {
    broadcastTerminalState();
  }
});
