'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const token = $('meta[name="mvp-token"]').content;
const state = { sessions: [], lessons: [], active: null, lesson: 'powershell', step: 0, socket: null, busy: false, kind: 'local', fingerprint: '' };
let toastTimer;

function toast(message) {
  $('#toast').textContent = message;
  $('#toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 5000);
}

async function api(path, options = {}) {
  const headers = { 'X-MVP-Token': token, ...options.headers };
  if (options.body !== undefined && typeof options.body !== 'string') {
    options.body = JSON.stringify(options.body);
    headers['Content-Type'] = 'application/json';
  }
  const response = await fetch('/api' + path, { ...options, headers });
  if (!response.ok) {
    let data;
    try { data = await response.json(); } catch { data = {}; }
    const detail = Array.isArray(data.detail) ? data.detail.map(item => item.msg).join('；') : data.detail;
    const error = new Error(detail || `请求失败 (${response.status})`);
    error.data = data;
    throw error;
  }
  return response;
}

async function json(path, options) { return (await api(path, options)).json(); }
function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function guardBusy() {
  if (!state.busy) return false;
  toast('请等待当前回答完成后再切换会话或课程。');
  return true;
}

let terminal, fit;
function initTerminal() {
  if (!window.Terminal || !window.FitAddon) throw new Error('终端资源未加载，请检查 static/vendor 文件。');
  terminal = new Terminal({
    fontFamily: '"Cascadia Code", "Cascadia Mono", Consolas, monospace', fontSize: 13,
    lineHeight: 1.25, cursorBlink: true, cursorStyle: 'bar', scrollback: 4000,
    theme: { background: '#18251f', foreground: '#d3dfcc', cursor: '#bcdfad', selectionBackground: '#446d4f',
      black: '#18251f', red: '#e9a197', green: '#a6cc8b', yellow: '#dace94', blue: '#a1bcd5',
      magenta: '#c5acd7', cyan: '#98cac2', white: '#d8e1d1', brightBlack: '#6d8871' },
    allowProposedApi: false,
  });
  fit = new FitAddon.FitAddon();
  terminal.loadAddon(fit);
  terminal.open($('#terminal'));
  terminal.onData(data => {
    if (state.socket?.readyState === WebSocket.OPEN) state.socket.send(JSON.stringify({ type: 'input', data }));
  });
  terminal.onResize(size => {
    if (state.socket?.readyState === WebSocket.OPEN) state.socket.send(JSON.stringify({ type: 'resize', ...size }));
  });
  new ResizeObserver(() => { requestAnimationFrame(() => { try { fit.fit(); } catch {} }); }).observe($('#terminal'));
}

function current() { return state.sessions.find(item => item.id === state.active); }
function lesson() { return state.lessons.find(item => item.id === state.lesson); }

async function refreshSessions() {
  state.sessions = await json('/sessions');
  renderSessions();
}

function renderSessions() {
  const list = $('#session-list');
  list.replaceChildren();
  if (!state.sessions.length) list.append(node('p', 'nav-empty', '还没有终端会话'));
  state.sessions.forEach(item => {
    const button = node('button', 'session-item' + (item.id === state.active ? ' active' : ''));
    button.title = item.target + (item.connected ? '' : ' · 已结束，可查看学习记录');
    button.append(node('span', 'status-dot' + (item.connected ? '' : ' inactive')), node('span', 'session-name', item.label), node('span', 'session-kind', item.kind === 'local' ? 'PS' : item.kind));
    button.onclick = () => selectSession(item.id).catch(error => toast(error.message));
    list.append(button);
  });
}

function renderLessons() {
  const list = $('#lesson-list');
  list.replaceChildren();
  state.lessons.forEach((item, index) => {
    const button = node('button', 'lesson-nav' + (item.id === state.lesson ? ' active' : ''));
    button.append(node('span', 'lesson-number', String(index + 1).padStart(2, '0')));
    const label = node('div');
    label.append(node('strong', '', item.title), node('small', '', item.tag));
    button.append(label);
    button.onclick = () => selectLesson(item.id).catch(error => toast(error.message));
    list.append(button);
  });
}

function renderExercise() {
  const item = lesson();
  if (!item) return;
  const completed = current()?.completed?.[item.id] || [];
  state.step = Math.min(state.step, item.steps.length - 1);
  const step = item.steps[state.step];
  $('#breadcrumb-lesson').textContent = item.title;
  $('#lesson-title').replaceChildren(document.createTextNode(item.title), node('span', 'heading-decoration', '.'));
  $('#lesson-description').textContent = item.description;
  $('#progress-number').textContent = `${completed.length} / ${item.steps.length}`;
  $('#step-count').textContent = `步骤 ${state.step + 1} / ${item.steps.length}`;
  $('#step-title').textContent = step.title;
  $('#step-goal').textContent = step.goal;
  $('#command-examples').hidden = true;
  $('#show-example').textContent = '查看参考命令';
  $('#complete-step').textContent = completed.includes(state.step) ? '已完成 · 点击取消 ✓' : '我已完成这一步 ✓';
  $('#step-dots').replaceChildren();
  item.steps.forEach((step, index) => {
    const button = node('button', (index === state.step ? 'current ' : '') + (completed.includes(index) ? 'done' : ''));
    button.title = `${index + 1}. ${step.title}`;
    button.setAttribute('aria-label', button.title);
    button.onclick = () => { state.step = index; renderExercise(); };
    $('#step-dots').append(button);
  });
}

async function selectLesson(id) {
  if (guardBusy()) return;
  state.lesson = id;
  if (state.active) {
    const updated = await json(`/sessions/${state.active}/progress`, { method: 'PUT', body: { lesson_id: id } });
    Object.assign(current(), updated);
  }
  const completed = current()?.completed?.[id] || [];
  state.step = Math.max(0, lesson().steps.findIndex((_, index) => !completed.includes(index)));
  renderLessons();
  renderExercise();
}

function closeSocket() {
  const socket = state.socket;
  state.socket = null;
  if (socket) { socket.onclose = null; socket.close(); }
}

async function selectSession(sid) {
  if (guardBusy()) return;
  closeSocket();
  state.active = sid;
  const selected = current();
  state.lesson = selected.lesson_id || 'powershell';
  const completed = selected.completed?.[state.lesson] || [];
  state.step = Math.max(0, lesson().steps.findIndex((_, index) => !completed.includes(index)));
  renderSessions();
  renderLessons();
  renderExercise();
  terminal.reset();
  $('#terminal-empty').hidden = true;
  $('#terminal-title').textContent = selected.label;
  $('#terminal-state').textContent = selected.connected ? '连接中…' : '已结束';
  $('#terminal-state').className = 'terminal-state';
  $('#bound-session-label').textContent = `当前会话 · ${selected.label}`;
  $('#chat-status').textContent = '';
  await loadMessages(sid);
  await refreshContext();
  if (state.active !== sid) return;
  if (selected.connected) {
    const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${scheme}//${location.host}/ws/${sid}`, ['termtutor', token]);
    state.socket = socket;
    socket.onopen = () => {
      if (state.active !== sid) return;
      $('#terminal-state').textContent = '● 已连接';
      $('#terminal-state').className = 'terminal-state connected';
      fit.fit();
      socket.send(JSON.stringify({ type: 'resize', cols: terminal.cols, rows: terminal.rows }));
    };
    socket.onmessage = event => {
      if (state.active !== sid) return;
      const data = JSON.parse(event.data);
      if (data.type === 'output') terminal.write(data.data);
      if (data.type === 'closed') {
        $('#terminal-state').textContent = '已结束';
        terminal.write('\r\n\x1b[90m[会话已结束，学习记录保留在本机]\x1b[0m\r\n');
        refreshSessions().catch(() => {});
      }
    };
    socket.onclose = () => {
      if (state.active !== sid) return;
      $('#terminal-state').textContent = '连接已断开';
      $('#terminal-state').className = 'terminal-state';
      refreshSessions().catch(() => {});
    };
    socket.onerror = () => { if (state.active === sid) toast('终端连接失败。请刷新页面或重新建立连接。'); };
  } else {
    terminal.write('\x1b[90m这是已结束的会话。对话和学习进度仍可查看；原始终端输出未持久保存。\r\n新建连接可继续练习。\x1b[0m');
  }
}

async function refreshContext() {
  const sid = state.active;
  if (!sid) return;
  const data = await json(`/sessions/${sid}/context`);
  if (state.active !== sid) return;
  $('#context-target').textContent = data.target || '—';
  $('#context-cwd').textContent = data.cwd || '目录未知';
  $('#context-cwd').title = `${data.cwd || '目录未知'}\n${data.cwd_note || ''}`;
}

async function connect(body) {
  if (guardBusy()) return;
  const desiredLesson = state.lesson;
  const created = await json('/sessions', { method: 'POST', body });
  await json(`/sessions/${created.id}/progress`, { method: 'PUT', body: { lesson_id: desiredLesson } });
  await refreshSessions();
  $('#connection-dialog').close();
  await selectSession(created.id);
  toast('终端已就绪。请直接在终端中输入命令。');
}

async function quickLocal() {
  const button = $('#quick-local');
  button.disabled = true;
  try { await connect({ kind: 'local' }); }
  catch (error) { toast(error.message); }
  finally { button.disabled = false; }
}

function openConnection() {
  if (guardBusy()) return;
  $('#connection-form').reset();
  state.fingerprint = '';
  $('#host-key-box').hidden = true;
  $('#connection-error').textContent = '';
  chooseKind('local');
  $('#connection-dialog').showModal();
}

function chooseKind(kind) {
  state.kind = kind;
  $$('[data-kind]').forEach(button => button.classList.toggle('selected', button.dataset.kind === kind));
  ['local', 'ssh', 'serial'].forEach(name => { $(`#${name}-fields`).hidden = name !== kind; });
  $('#connection-error').textContent = '';
  if (kind === 'serial') refreshPorts().catch(error => { $('#connection-error').textContent = error.message; });
}

async function refreshPorts() {
  const ports = await json('/serial/ports');
  $('#serial-device').replaceChildren();
  if (!ports.length) $('#serial-device').append(new Option('未发现串口设备', ''));
  ports.forEach(port => $('#serial-device').append(new Option(`${port.device} · ${port.description}`, port.device)));
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast('命令已复制，请检查后自行粘贴到终端。');
  } catch { toast('复制失败，请手动选择命令文本复制。'); }
}

function inlineText(parent, text) {
  // All untrusted content becomes text nodes. No HTML, remote images or executable links.
  const pattern = /(\*\*([^*]+)\*\*|`([^`]+)`)/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    parent.append(document.createTextNode(text.slice(last, match.index)));
    parent.append(match[2] ? node('strong', '', match[2]) : node('code', 'inline-code', match[3]));
    last = match.index + match[0].length;
  }
  parent.append(document.createTextNode(text.slice(last)));
}

function markdown(parent, text) {
  parent.replaceChildren();
  const parts = text.split(/```([^\n`]*)\n([\s\S]*?)(?:```|$)/g);
  for (let index = 0; index < parts.length; index += 3) {
    for (const para of parts[index].split(/\n\s*\n/)) {
      if (!para.trim()) continue;
      const heading = para.match(/^#{1,4}\s+([\s\S]*)$/);
      const element = node(heading ? 'h3' : 'p');
      inlineText(element, heading ? heading[1] : para);
      parent.append(element);
    }
    if (parts[index + 2] !== undefined) {
      const block = node('div', 'code-block');
      const top = node('div', 'code-top');
      const button = node('button', 'copy-button', '复制');
      const code = parts[index + 2].trimEnd();
      button.onclick = () => copy(code);
      top.append(node('span', '', parts[index + 1].trim() || 'command'), button);
      block.append(top, node('pre', '', code));
      parent.append(block);
    }
  }
}

function addMessage(role, content, mode = 'model', sources = []) {
  const entry = node('article', 'message ' + role);
  const meta = node('div', 'message-meta');
  meta.append(node('span', '', role === 'user' ? '你' : '✦ 教学助手'));
  const badge = node('span', 'message-badge', mode === 'offline' ? '离线讲义' : mode === 'error' ? '生成中断' : '环境感知');
  if (role !== 'user') meta.append(badge);
  const body = node('div', 'message-body');
  markdown(body, content);
  entry.append(meta, body);
  $('#messages').append(entry);
  const result = { entry, body, badge, content, sources, sourceList: null };
  renderSources(result);
  return result;
}

function renderSources(message) {
  message.sourceList?.remove();
  if (!message.sources?.length) return;
  const list = node('div', 'source-list');
  const unique = new Map(message.sources.map(source => [source.title, source]));
  for (const source of unique.values()) {
    const chip = node('span', 'source-chip', '▤ ' + source.title);
    chip.title = `${source.source}\n${source.text || ''}`;
    list.append(chip);
  }
  message.entry.append(list);
  message.sourceList = list;
}

function scrollMessages() { $('#messages').scrollTop = $('#messages').scrollHeight; }

async function loadMessages(sid) {
  const messages = await json(`/sessions/${sid}/messages`);
  if (state.active !== sid) return;
  if (!messages.length) {
    $('#messages').replaceChildren();
    addMessage('assistant', '终端已经关联。我会结合这个会话的上下文给你提示。\n\n先试着完成左侧的当前练习。你也可以问我：“这条命令是什么意思？”或“为什么会报错？”', 'model');
  } else {
    $('#messages').replaceChildren();
    messages.forEach(message => addMessage(message.role, message.content, message.mode, message.sources));
  }
  scrollMessages();
}

async function sendMessage(text) {
  text = text.trim();
  if (!text || state.busy) return;
  if (!state.active || !current()?.connected) { toast('请先新建或选择一个已连接的终端。'); return; }
  const sid = state.active;
  state.busy = true;
  $('#send-message').disabled = true;
  $('#chat-input').value = '';
  addMessage('user', text, 'user');
  const message = addMessage('assistant', '', 'model');
  $('#chat-status').textContent = '正在收集当前会话上下文…';
  scrollMessages();
  try {
    const response = await api(`/sessions/${sid}/chat`, { method: 'POST', body: { message: text, attach_output: $('#attach-output').checked } });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let doneEvent = false;
    const consume = line => {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      if (event.type === 'delta') { message.content += event.text; markdown(message.body, message.content); }
      if (event.type === 'status') $('#chat-status').textContent = event.text;
      if (event.type === 'mode') message.badge.textContent = event.mode === 'offline' ? '离线讲义' : '本地模型';
      if (event.type === 'sources') { message.sources = event.sources; renderSources(message); }
      if (event.type === 'tool') $('#chat-status').textContent = `只读探索 · ${event.name === 'inspect_environment' ? '观察当前环境' : '检索本地资料'} · ${event.status}`;
      if (event.type === 'error') toast(event.text);
      if (event.type === 'done') doneEvent = true;
      scrollMessages();
    };
    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      lines.forEach(consume);
      if (chunk.done) break;
    }
    if (buffer.trim()) consume(buffer);
    if (!doneEvent) throw new Error('回答流已中断，请重试。');
    $('#chat-status').textContent = '已结合当前会话作答 · 请自行核对并执行建议命令';
  } catch (error) {
    if (!message.content) markdown(message.body, '发送失败：' + error.message);
    message.badge.textContent = '请求异常';
    $('#chat-status').textContent = error.message;
    toast(error.message);
  } finally {
    state.busy = false;
    $('#send-message').disabled = false;
  }
}

async function openSettings() {
  const config = await json('/model');
  const form = $('#settings-form');
  form.elements.base_url.value = config.base_url;
  form.elements.model.value = config.model;
  form.elements.enabled.checked = config.enabled;
  form.elements.api_key.value = '';
  form.elements.api_key.placeholder = config.has_api_key ? '已设置；不填写则保留，Key 不会回显' : '本机服务可留空';
  $('#settings-result').textContent = '';
  $('#settings-dialog').showModal();
}

async function saveSettings() {
  const form = $('#settings-form');
  const data = Object.fromEntries(new FormData(form));
  data.enabled = form.elements.enabled.checked;
  data.api_key = data.api_key || null;
  const config = await json('/model', { method: 'PUT', body: data });
  updateModelBadge(config);
  return config;
}

function updateModelBadge(config) {
  $('#tutor-mode').textContent = config.enabled ? '本地模型 · 环境感知教学' : '离线讲义 · 模型未启用';
  $('#tutor-mode').title = `${config.base_url}\n${config.model || '未配置模型'}`;
  $('#model-dot').style.background = config.enabled ? '#8bc4a1' : '#a48f69';
}

async function loadKnowledge() {
  const docs = await json('/knowledge');
  $('#knowledge-list').replaceChildren();
  docs.forEach(doc => {
    const element = node('div', 'document');
    const label = node('div');
    label.append(node('strong', '', doc.title), node('small', '', `${doc.source} · ${doc.size} 字符`));
    element.append(label);
    if (doc.source.startsWith('本地导入/')) {
      const button = node('button', '', '删除');
      button.onclick = async () => { try { await json(`/knowledge/${doc.id}`, { method: 'DELETE' }); await loadKnowledge(); } catch (error) { toast(error.message); } };
      element.append(button);
    }
    $('#knowledge-list').append(element);
  });
}

function bindEvents() {
  ['#new-session', '#new-session-small'].forEach(id => { $(id).onclick = openConnection; });
  $('#quick-local').onclick = quickLocal;
  $$('[data-close]').forEach(button => { button.onclick = () => button.closest('dialog').close(); });
  $$('[data-kind]').forEach(button => { button.onclick = () => chooseKind(button.dataset.kind); });
  $('#refresh-ports').onclick = () => refreshPorts().catch(error => toast(error.message));
  $('#connection-form').onsubmit = async event => {
    event.preventDefault();
    const button = $('#connect-submit');
    const form = event.target;
    const body = Object.fromEntries(new FormData(form));
    body.kind = state.kind;
    body.port = Number(body.port);
    body.baudrate = Number(body.baudrate);
    if (state.fingerprint) {
      if (!$('#trust-host').checked) { $('#connection-error').textContent = '请先通过可信渠道核对并确认主机指纹。'; return; }
      body.fingerprint = state.fingerprint;
    }
    button.disabled = true;
    button.textContent = '正在连接…';
    $('#connection-error').textContent = '';
    try {
      await connect(body);
      form.reset();
    } catch (error) {
      $('#connection-error').textContent = error.message;
      if (error.data?.code === 'HOST_KEY_REQUIRED') {
        state.fingerprint = error.data.fingerprint;
        $('#host-key-value').textContent = `${error.data.host}\n${error.data.fingerprint}`;
        $('#host-key-box').hidden = false;
      }
    } finally { button.disabled = false; button.textContent = '建立连接 ↗'; }
  };
  $('#clear-terminal').onclick = () => terminal.clear();
  $('#refresh-context').onclick = () => refreshContext().then(() => toast('当前会话的环境观察已刷新。')).catch(error => toast(error.message));
  $('#close-terminal').onclick = async () => {
    if (!state.active || guardBusy()) return;
    try {
      await json(`/sessions/${state.active}`, { method: 'DELETE' });
      await refreshSessions();
      $('#terminal-state').textContent = '已结束';
      toast('终端已关闭，学习记录已保留。');
    } catch (error) { toast(error.message); }
  };
  $('#show-example').onclick = () => {
    const box = $('#command-examples');
    box.hidden = !box.hidden;
    $('#show-example').textContent = box.hidden ? '查看参考命令' : '收起参考命令';
    box.replaceChildren();
    if (!box.hidden) lesson().steps[state.step].commands.forEach(command => {
      const row = node('div', 'command-line');
      const button = node('button', 'copy-button', '复制');
      button.onclick = () => copy(command);
      row.append(node('code', '', command), button);
      box.append(row);
    });
    requestAnimationFrame(() => fit.fit());
  };
  $('#complete-step').onclick = async () => {
    if (!state.active) { toast('请先打开一个终端会话。'); return; }
    try {
      const completed = [...(current().completed?.[state.lesson] || [])];
      const index = completed.indexOf(state.step);
      if (index >= 0) completed.splice(index, 1); else completed.push(state.step);
      const updated = await json(`/sessions/${state.active}/progress`, { method: 'PUT', body: { lesson_id: state.lesson, completed } });
      Object.assign(current(), updated);
      if (index < 0 && state.step < lesson().steps.length - 1) state.step++;
      renderExercise();
      toast(index >= 0 ? '已取消该步骤完成标记。' : '进度已保存，继续下一步。');
    } catch (error) { toast(error.message); }
  };
  $('#ask-hint').onclick = () => sendMessage(`我在学习《${lesson().title}》的“${lesson().steps[state.step].title}”。请结合终端上下文给我一点提示，先不要直接写完全部答案。`);
  $$('[data-prompt]').forEach(button => { button.onclick = () => sendMessage(button.dataset.prompt); });
  $('#chat-form').onsubmit = event => { event.preventDefault(); sendMessage($('#chat-input').value); };
  $('#chat-input').onkeydown = event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); sendMessage(event.target.value); }
  };
  $('#open-settings').onclick = () => openSettings().catch(error => toast(error.message));
  $('#settings-form').onsubmit = async event => {
    event.preventDefault();
    try { await saveSettings(); $('#settings-dialog').close(); toast('模型设置已保存，本次运行生效。'); }
    catch (error) { $('#settings-result').textContent = error.message; $('#settings-result').className = 'form-result error'; }
  };
  $('#test-model').onclick = async event => {
    event.target.disabled = true;
    $('#settings-result').className = 'form-result';
    $('#settings-result').textContent = '正在检查模型服务…';
    try {
      await saveSettings();
      const result = await json('/model/test', { method: 'POST' });
      $('#settings-result').textContent = result.model_found ? '✓ 服务已连通，已找到所选模型。' : '服务已连通，但未找到填写的模型名。请核对服务端模型 ID。';
    } catch (error) { $('#settings-result').textContent = error.message; $('#settings-result').className = 'form-result error'; }
    finally { event.target.disabled = false; }
  };
  $('#open-knowledge').onclick = async () => { try { await loadKnowledge(); $('#knowledge-dialog').showModal(); } catch (error) { toast(error.message); } };
  $('#knowledge-file').onchange = async event => {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 180000) { toast('资料过大，请导入 60,000 字符以内的文本。'); return; }
    const text = await file.text();
    if (text.length > 60000) { toast('资料最多 60,000 字符，请先裁剪。'); return; }
    $('#knowledge-form').elements.title.value = file.name.replace(/\.(md|txt)$/i, '').slice(0, 100);
    $('#knowledge-form').elements.content.value = text;
  };
  $('#knowledge-form').onsubmit = async event => {
    event.preventDefault();
    try {
      await json('/knowledge', { method: 'POST', body: Object.fromEntries(new FormData(event.target)) });
      event.target.reset();
      $('#knowledge-result').textContent = '资料已导入，可用于后续教学问答。';
      await loadKnowledge();
    } catch (error) { $('#knowledge-result').textContent = error.message; }
  };
  $('#export-record').onclick = async () => {
    if (!state.active) { toast('请先选择一个会话。'); return; }
    try {
      const response = await api(`/sessions/${state.active}/export`);
      const url = URL.createObjectURL(await response.blob());
      const link = node('a');
      link.href = url;
      link.download = `termtutor-${state.active}.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { toast(error.message); }
  };
}

async function init() {
  initTerminal();
  bindEvents();
  const [lessons, config] = await Promise.all([json('/lessons'), json('/model'), refreshSessions()]);
  state.lessons = lessons;
  updateModelBadge(config);
  renderLessons();
  renderExercise();
  const connected = state.sessions.find(item => item.connected);
  if (connected) await selectSession(connected.id);
  setInterval(() => { if (state.active && current()?.connected) refreshContext().catch(() => {}); }, 6000);
}
init().catch(error => toast('启动失败：' + error.message));
