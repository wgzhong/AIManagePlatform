/**
 * AIManagePlatform 控制台脚本
 * 管理面板的核心交互逻辑
 */

/* ===== 常量与存储 ===== */
const API_KEY_STORAGE = 'ai_platform_api_key';
const API_URL_STORAGE = 'ai_platform_api_url';
const MODEL_STORAGE = 'ai_platform_model';
const CUSTOM_MODELS_STORAGE = 'ai_platform_custom_models';
const DEFAULT_API_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions';

const DEFAULT_MODELS = [
  { id: 'glm-5.1', name: 'GLM-5.1' },
  { id: 'glm-4.5-air', name: 'GLM-4.5-Air' },
  { id: 'glm-4.6v', name: 'GLM-4.6V' },
  { id: 'deepseek-chat', name: 'DeepSeek-Chat' },
  { id: 'qwen3-turbo', name: 'Qwen3-Turbo' }
];

let usersList = [];
let usersConfigMap = {};

/* ===== HTML 安全辅助 ===== */
function escapeHtml(str) {
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

function safeContent(content) {
  if (typeof content !== 'string') return '';
  return escapeHtml(content);
}

/* ===== 初始化 ===== */
document.addEventListener('DOMContentLoaded', async function() {
  await checkAuth();
  loadStoredConfig();
  loadStats();
  checkHealth();
  setInterval(loadStats, 30000);
  setInterval(checkHealth, 10000);
});

/* ===== 认证 ===== */
async function checkAuth() {
  var token = localStorage.getItem('access_token');
  if (!token) {
    window.location.href = '/login';
    return;
  }
  try {
    var response = await fetch('/auth/me', {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (!response.ok) {
      throw new Error('未授权');
    }
    await loadUserInfo();
  } catch (error) {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('username');
    localStorage.removeItem('email');
    localStorage.removeItem('is_superuser');
    window.location.href = '/login';
  }
}

/* ===== 配置加载 ===== */
function loadStoredConfig() {
  var storedKey = localStorage.getItem(API_KEY_STORAGE) || '';
  var storedUrl = localStorage.getItem(API_URL_STORAGE) || DEFAULT_API_URL;
  var storedModel = localStorage.getItem(MODEL_STORAGE) || 'glm-4.6v';

  document.getElementById('apiKeyInput').value = storedKey;
  document.getElementById('apiUrlInput').value = storedUrl;

  loadCustomModels();

  var modelSelect = document.getElementById('modelSelect');
  modelSelect.value = storedModel;

  if (storedKey) {
    document.getElementById('apiKeyInput').classList.add('success');
  }
}

function loadCustomModels() {
  var customModels = getCustomModels();
  var modelSelect = document.getElementById('modelSelect');
  var existingOptions = Array.from(modelSelect.options).map(function(o) { return o.value; });

  customModels.forEach(function(model) {
    if (existingOptions.indexOf(model.id) === -1) {
      var option = document.createElement('option');
      option.value = model.id;
      option.textContent = model.name;
      modelSelect.appendChild(option);
    }
  });
}

function getCustomModels() {
  try {
    var stored = localStorage.getItem(CUSTOM_MODELS_STORAGE);
    return stored ? JSON.parse(stored) : [];
  } catch (e) {
    return [];
  }
}

function getModelDisplayName(modelId) {
  if (!modelId) return '-';
  var found = DEFAULT_MODELS.find(function(m) { return m.id === modelId; });
  if (found) return found.name;
  var custom = getCustomModels().find(function(m) { return m.id === modelId; });
  if (custom) return custom.name;
  return modelId;
}

function saveCustomModels(models) {
  localStorage.setItem(CUSTOM_MODELS_STORAGE, JSON.stringify(models));
}

/* ===== 模型管理 ===== */
function showModelManager() {
  var customModels = getCustomModels();
  var list = document.getElementById('customModelsList');

  if (customModels.length === 0) {
    list.innerHTML = '<div class="model-manager-empty">暂无自定义模型</div>';
  } else {
    list.innerHTML = customModels.map(function(model) {
      return '<div class="model-item">' +
        '<div>' +
          '<div class="model-name">' + safeContent(model.name) + '</div>' +
          '<div class="model-id">' + safeContent(model.id) + '</div>' +
        '</div>' +
        '<div class="actions">' +
          '<button class="btn-default" onclick="setAsDefault(\'' + escapeHtml(model.id) + '\')">设为默认</button>' +
          '<button class="btn-delete" onclick="deleteModel(\'' + escapeHtml(model.id) + '\')">删除</button>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  document.getElementById('modelManagerOverlay').classList.add('show');
}

function closeModelManager() {
  document.getElementById('modelManagerOverlay').classList.remove('show');
}

function addCustomModel() {
  var modelId = document.getElementById('newModelId').value.trim();
  var modelName = document.getElementById('newModelName').value.trim();

  if (!modelId || !modelName) {
    alert('请填写模型 ID 和名称');
    return;
  }

  var existingIds = DEFAULT_MODELS.map(function(m) { return m.id; }).concat(getCustomModels().map(function(m) { return m.id; }));
  if (existingIds.indexOf(modelId) !== -1) {
    alert('该模型 ID 已存在');
    return;
  }

  var customModels = getCustomModels();
  customModels.push({ id: modelId, name: modelName });
  saveCustomModels(customModels);
  saveConfigToBackend({ custom_models: JSON.stringify(customModels) });

  var modelSelect = document.getElementById('modelSelect');
  var option = document.createElement('option');
  option.value = modelId;
  option.textContent = modelName;
  modelSelect.appendChild(option);

  document.getElementById('newModelId').value = '';
  document.getElementById('newModelName').value = '';

  showModelManager();
}

function deleteModel(modelId) {
  if (!confirm('确定要删除模型 "' + modelId + '" 吗？')) return;

  var customModels = getCustomModels().filter(function(m) { return m.id !== modelId; });
  saveCustomModels(customModels);
  saveConfigToBackend({ custom_models: JSON.stringify(customModels) });

  var modelSelect = document.getElementById('modelSelect');
  for (var i = modelSelect.options.length - 1; i >= 0; i--) {
    if (modelSelect.options[i].value === modelId) {
      modelSelect.remove(i);
      break;
    }
  }

  showModelManager();
}

function setAsDefault(modelId) {
  localStorage.setItem(MODEL_STORAGE, modelId);
  document.getElementById('modelSelect').value = modelId;
  saveConfigToBackend({ default_model: modelId });
  closeModelManager();
}

/* ===== 输入校验与保存 ===== */
function validateKey() {
  var input = document.getElementById('apiKeyInput');
  var value = input.value.trim();
  if (value) {
    input.classList.remove('error');
    input.classList.add('success');
    localStorage.setItem(API_KEY_STORAGE, value);
    saveConfigToBackend({ api_key: value });
  } else {
    input.classList.remove('error', 'success');
  }
}

function validateUrl() {
  var input = document.getElementById('apiUrlInput');
  var value = input.value.trim();
  if (value) {
    localStorage.setItem(API_URL_STORAGE, value);
    saveConfigToBackend({ api_url: value });
  }
}

function saveModel() {
  var model = document.getElementById('modelSelect').value;
  localStorage.setItem(MODEL_STORAGE, model);
  saveConfigToBackend({ default_model: model });
}

async function saveConfigToBackend(configData) {
  var token = localStorage.getItem('access_token');
  if (!token) return;
  try {
    await fetch('/auth/config', {
      method: 'PUT',
      headers: {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(configData)
    });
  } catch (e) {
    console.error('保存配置失败:', e);
  }
}

/* ===== 页面导航 ===== */
async function navigateTo(path) {
  var apiKey = document.getElementById('apiKeyInput').value.trim();
  if (!apiKey && path !== '/chat') {
    document.getElementById('apiKeyInput').classList.add('error');
    document.getElementById('apiKeyInput').focus();
    return;
  }

  var model = document.getElementById('modelSelect').value;
  var url = document.getElementById('apiUrlInput').value.trim() || DEFAULT_API_URL;

  if (apiKey) {
    localStorage.setItem(API_KEY_STORAGE, apiKey);
  }
  await saveConfigToBackend({ api_key: apiKey || '', api_url: url, default_model: model });

  var chatConfig = {
    mode: 'custom',
    url: url,
    key: apiKey,
    model: model,
    timestamp: Date.now()
  };
  localStorage.setItem('ai_chat_config', JSON.stringify(chatConfig));

  window.location.href = path;
}

/* ===== 统计数据 ===== */
async function loadStats() {
  var token = localStorage.getItem('access_token');
  try {
    var res = await fetch('/auth/stats', {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    var data = await res.json();

    document.getElementById('dailyRequests').textContent = data.daily_requests || 0;
    document.getElementById('totalRequests').textContent = data.total_requests || 0;

    document.getElementById('todayTokens').textContent = (data.today_input_tokens || 0) + (data.today_output_tokens || 0);
    document.getElementById('todayInputTokens').textContent = data.today_input_tokens || 0;
    document.getElementById('todayOutputTokens').textContent = data.today_output_tokens || 0;
    document.getElementById('totalTokensAll').textContent = (data.total_input_tokens || 0) + (data.total_output_tokens || 0);
    document.getElementById('totalInputTokens').textContent = data.total_input_tokens || 0;
    document.getElementById('totalOutputTokens').textContent = data.total_output_tokens || 0;

    var elOutput = document.getElementById('outputTokens');
    if (elOutput) elOutput.textContent = data.today_output_tokens || 0;
    var elMonthly = document.getElementById('monthlyTokens');
    if (elMonthly) elMonthly.textContent = data.total_output_tokens || 0;
    document.getElementById('toolCalls').textContent = (data.tool_calls && data.tool_calls.total) || 0;
    document.getElementById('toolTime').textContent = (data.tool_calls && data.tool_calls.get_time) || 0;
    document.getElementById('toolCalc').textContent = (data.tool_calls && data.tool_calls.calculate) || 0;
    document.getElementById('toolWeather').textContent = (data.tool_calls && data.tool_calls.get_weather) || 0;

    document.getElementById('onlineCount').textContent = data.total_devices || 0;

    var totalTokens = (data.today_input_tokens || 0) + (data.today_output_tokens || 0);
    var maxDaily = 500000;
    var progress = Math.min((totalTokens / maxDaily) * 100, 100);
    document.getElementById('tokenProgress').style.width = progress + '%';

    updateMiniChart(data.daily_records || []);

  } catch (err) {
    console.error('加载统计数据失败:', err);
  }
}

function updateMiniChart(records) {
  if (!records || records.length === 0) return;

  var maxCount = Math.max.apply(null, records.map(function(r) { return r.count; }).concat([1]));
  var bars = document.querySelectorAll('#reqChart .mini-bar');

  records.forEach(function(record, index) {
    if (bars[index]) {
      bars[index].style.height = (record.count / maxCount * 100) + '%';
      bars[index].className = index === records.length - 1 ? 'mini-bar highlight' : 'mini-bar';
    }
  });
}

/* ===== 健康检查 ===== */
async function checkHealth() {
  try {
    var res = await fetch('/api/health');
    var data = await res.json();

    var dot = document.getElementById('statusDot');
    var tooltipStatus = document.getElementById('tooltipStatus');
    var tooltipLatency = document.getElementById('tooltipLatency');

    switch (data.status_color) {
      case 'green':
        dot.className = 'status-dot';
        tooltipStatus.textContent = '在线';
        break;
      case 'orange':
        dot.className = 'status-dot orange';
        tooltipStatus.textContent = '限流';
        break;
      case 'red':
        dot.className = 'status-dot red';
        tooltipStatus.textContent = '离线';
        break;
    }

    tooltipLatency.textContent = data.latency ? data.latency + 'ms' : '-';

  } catch (err) {
    document.getElementById('statusDot').className = 'status-dot red';
  }
}

function toggleStatusTooltip() {
  document.getElementById('statusTooltip').classList.toggle('show');
}

/* ===== 弹窗与工具 ===== */
function exportConfig() {
  var config = {
    apiKey: document.getElementById('apiKeyInput').value,
    apiUrl: document.getElementById('apiUrlInput').value,
    model: document.getElementById('modelSelect').value,
    exportedAt: new Date().toISOString()
  };
  var blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'ai_config.json';
  a.click();
}

function showLogs() {
  document.getElementById('modalTitle').textContent = '📋 系统日志';
  document.getElementById('modalBody').innerHTML =
    '<h4 class="stat-model-config-h4">AI 对话日志</h4>' +
    '<p>所有会话记录、Token 消耗统计已记录在服务器端。</p>' +
    '<h4 class="stat-model-config-h4 stat-model-config-mt">硬件设备日志</h4>' +
    '<p>设备上下线事件、连接状态变更已记录。</p>' +
    '<h4 class="stat-model-config-h4 stat-model-config-mt">API 调用日志</h4>' +
    '<p>所有 API 请求、错误信息已记录，支持关键词检索。</p>';
  document.getElementById('modalOverlay').classList.add('show');
}

function showDoc(type) {
  var docs = {
    esp32: {
      title: '📱 ESP32 设备接入教程',
      content: '<h4 class="stat-model-config-h4">1. 注册设备</h4>' +
        '<p>在「硬件设备管理」页面注册设备，获取设备码。</p>' +
        '<h4 class="stat-model-config-h4 stat-model-config-mt">2. ESP32 代码示例</h4>' +
        '<pre><code>#include &lt;HTTPClient.h&gt;\n\n' +
        'void sendChat(String deviceCode, String message) {\n' +
        '  HTTPClient http;\n' +
        '  http.begin("http://your-server:8002/chat");\n' +
        '  http.addHeader("Content-Type", "application/json");\n' +
        '  \n' +
        '  String payload = "{\\"device_code\\":\\"" + deviceCode + "\\",\\"messages\\":[{\\"role\\":\\"user\\",\\"content\\":\\"" + message + "\\"}]}";\n' +
        '  int httpCode = http.POST(payload);\n' +
        '  \n' +
        '  if (httpCode == HTTP_CODE_OK) {\n' +
        '    String response = http.getString();\n' +
        '    Serial.println(response);\n' +
        '  }\n' +
        '  http.end();\n' +
        '}</code></pre>' +
        '<h4 class="stat-model-config-h4 stat-model-config-mt">3. 设备码格式</h4>' +
        '<p>设备码为 8 位十六进制字符串，如：<code>FF0958EC</code></p>'
    },
    skills: {
      title: '🧠 技能说明',
      content: '<h4 class="stat-model-config-h4">工具类技能</h4>' +
        '<ul style="margin-left:20px;color:var(--text-sub);margin-bottom:16px;">' +
          '<li><code>get_time</code> - 获取当前系统时间</li>' +
          '<li><code>calculate</code> - 数学计算</li>' +
          '<li><code>get_weather</code> - 获取城市天气信息</li>' +
        '</ul>' +
        '<h4 class="stat-model-config-h4 stat-model-config-mt">情感响应技能</h4>' +
        '<ul style="margin-left:20px;color:var(--text-sub);margin-bottom:16px;">' +
          '<li><code>anger_response</code> - 愤怒情绪响应</li>' +
          '<li><code>cheerful_response</code> - 开心情绪响应</li>' +
          '<li><code>disgust_response</code> - 厌恶情绪响应</li>' +
          '<li><code>fear_response</code> - 恐惧情绪响应</li>' +
          '<li><code>happy_response</code> - 快乐情绪响应</li>' +
          '<li><code>sad_response</code> - 悲伤情绪响应</li>' +
          '<li><code>surprise_response</code> - 惊讶情绪响应</li>' +
        '</ul>' +
        '<h4 class="stat-model-config-h4 stat-model-config-mt">技能配置</h4>' +
        '<p>每个技能支持配置：启用状态、自动触发、触发关键词等。</p>'
    },
    api: {
      title: '📡 OpenAI 兼容接口文档',
      content: '<h4 class="stat-model-config-h4">POST /chat</h4>' +
        '<p>流式聊天接口，兼容 OpenAI API 格式。</p>' +
        '<pre><code>{\n' +
        '  "messages": [{"role": "user", "content": "你好"}],\n' +
        '  "api_key": "your-api-key",\n' +
        '  "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",\n' +
        '  "model": "glm-5.1",\n' +
        '  "device_code": "可选的设备码"\n' +
        '}</code></pre>' +
        '<h4 class="stat-model-config-h4 stat-model-config-mt">GET /api/stats</h4>' +
        '<p>获取系统统计数据。</p>' +
        '<h4 class="stat-model-config-h4 stat-model-config-mt">GET /api/health</h4>' +
        '<p>健康检查接口。</p>' +
        '<h4 class="stat-model-config-h4 stat-model-config-mt">POST /api/devices/register</h4>' +
        '<p>注册新设备。</p>'
    }
  };

  var doc = docs[type];
  if (doc) {
    document.getElementById('modalTitle').textContent = doc.title;
    document.getElementById('modalBody').innerHTML = doc.content;
    document.getElementById('modalOverlay').classList.add('show');
  }
}

function closeModal() {
  document.getElementById('modalOverlay').classList.remove('show');
}

/* ===== 用户菜单 ===== */
function toggleUserMenu() {
  var menu = document.getElementById('userMenu');
  menu.classList.toggle('show');
}

document.addEventListener('click', function(event) {
  var menu = document.getElementById('userMenu');
  var profile = document.getElementById('userProfile');
  if (menu && !menu.contains(event.target) && !profile.contains(event.target)) {
    menu.classList.remove('show');
  }
});

async function logout() {
  if (!confirm('确定要登出吗？')) return;
  try {
    await fetch('/auth/logout', { method: 'POST' });
  } catch (error) {
    console.error('登出失败:', error);
  }
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_id');
  localStorage.removeItem('username');
  localStorage.removeItem('email');
  localStorage.removeItem('is_superuser');
  window.location.href = '/login';
}

async function loadUserInfo() {
  var token = localStorage.getItem('access_token');
  if (!token) return;

  try {
    var response = await fetch('/auth/me', {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (response.ok) {
      var user = await response.json();
      var userName = user.username;
      var userRole = user.is_superuser ? '超级管理员' : '普通用户';
      document.getElementById('userName').textContent = userName;
      document.getElementById('userAvatar').textContent = userName.charAt(0).toUpperCase();
      document.getElementById('userRole').textContent = userRole;
      document.getElementById('menuUserName').textContent = userName;
      document.getElementById('menuAvatar').textContent = userName.charAt(0).toUpperCase();
      document.getElementById('menuUserRole').textContent = userRole;
      localStorage.setItem('is_superuser', user.is_superuser);

      if (user.is_superuser) {
        document.getElementById('menuManageAccount').style.display = 'flex';
      }
    }
  } catch (error) {
    console.error('加载用户信息失败:', error);
  }
}

/* ===== 用户管理 ===== */
function showUserManager() {
  document.getElementById('userModalOverlay').classList.add('show');
  loadUsers();
  loadAllUserConfigs();
}

async function loadAllUserConfigs() {
  var token = localStorage.getItem('access_token');
  try {
    var response = await fetch('/auth/admin/user-configs', {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (response.ok) {
      var configs = await response.json();
      configs.forEach(function(c) {
        usersConfigMap[c.user_id] = c;
      });
      renderUserList();
    }
  } catch (e) {
    console.error('加载用户配置失败:', e);
  }
}

function closeUserManager() {
  document.getElementById('userModalOverlay').classList.remove('show');
}

function viewUserConfig(userId) {
  var config = usersConfigMap[userId];
  if (!config) {
    alert('该用户暂无配置');
    return;
  }
  var user = usersList.find(function(u) { return u.id === userId; });
  var customModelsStr = Array.isArray(config.custom_models)
    ? config.custom_models.map(function(m) { return safeContent(m.name) + ' (' + safeContent(m.id) + ')'; }).join(', ')
    : '无';

  document.getElementById('modalTitle').textContent = '📋 ' + (user ? user.username : '用户') + ' 的配置';
  document.getElementById('modalBody').innerHTML =
    '<div class="tooltip-row"><span class="tooltip-label">默认模型</span><span class="tooltip-value">' + safeContent(getModelDisplayName(config.default_model)) + '</span></div>' +
    '<div class="tooltip-row"><span class="tooltip-label">心情</span><span class="tooltip-value">' + safeContent(config.mood || '-') + '</span></div>' +
    '<div class="tooltip-row"><span class="tooltip-label">API URL</span><span class="tooltip-value" style="font-size:11px;">' + safeContent(config.api_url || '-') + '</span></div>' +
    '<div class="tooltip-row"><span class="tooltip-label">API Key</span><span class="tooltip-value" style="font-size:11px;">' + (config.api_key ? '***' + escapeHtml(config.api_key.slice(-4)) : '-') + '</span></div>' +
    '<div class="tooltip-row"><span class="tooltip-label">自定义模型</span><span class="tooltip-value" style="font-size:11px;">' + safeContent(customModelsStr) + '</span></div>';
  document.getElementById('modalOverlay').classList.add('show');
  document.getElementById('userModalOverlay').classList.remove('show');
}

async function loadUsers() {
  var token = localStorage.getItem('access_token');
  try {
    var response = await fetch('/auth/users', {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (response.ok) {
      usersList = await response.json();
      renderUserList();
    }
  } catch (error) {
    console.error('加载用户列表失败:', error);
  }
}

function renderUserList() {
  var tbody = document.getElementById('usersTableBody');
  tbody.innerHTML = '';

  usersList.forEach(function(user) {
    var userConfig = usersConfigMap[user.id] || {};
    var row = document.createElement('tr');
    var apiKeyDisplay = userConfig.api_key ? '***' + userConfig.api_key.slice(-4) : '-';
    var contribCount = user.contributed_skills_count || 0;
    row.innerHTML =
      '<td style="color:var(--text-sub);font-size:11px;">' + user.id + '</td>' +
      '<td><strong>' + safeContent(user.username) + '</strong></td>' +
      '<td style="color:var(--text-sub);">' + safeContent(user.email) + '</td>' +
      '<td><span class="status-badge ' + (user.is_active ? 'active' : 'inactive') + '">' + (user.is_active ? '激活' : '禁用') + '</span></td>' +
      '<td><span class="role-badge ' + (user.is_superuser ? 'admin' : 'user') + '">' + (user.is_superuser ? '超级管理员' : '普通用户') + '</span></td>' +
      '<td style="color:var(--accent-cyan);font-size:12px;">' + safeContent(userConfig.default_model ? getModelDisplayName(userConfig.default_model) : '-') + '</td>' +
      '<td style="color:var(--text-sub);font-size:11px;font-family:monospace;">' + escapeHtml(apiKeyDisplay) + '</td>' +
      '<td style="color:var(--text-sub);font-size:11px;">' + (user.created_at ? new Date(user.created_at).toLocaleString('zh-CN') : '-') + '</td>' +
      '<td><span style="background:rgba(135,232,232,0.1);color:var(--accent-cyan);padding:2px 10px;border-radius:10px;font-size:11px;font-weight:600;">🎁 ' + contribCount + '</span></td>' +
      '<td>' +
        '<button onclick="editUser(' + user.id + ')" class="btn-action">编辑</button>' +
        '<button onclick="viewUserConfig(' + user.id + ')" class="btn-action" style="background:rgba(114,224,224,0.1);color:var(--accent-cyan);">配置</button>' +
        '<button onclick="deleteUserConfirm(' + user.id + ', \'' + escapeHtml(user.username) + '\')" class="btn-action danger">删除</button>' +
      '</td>';
    tbody.appendChild(row);
  });
}

async function deleteUserConfirm(userId, username) {
  if (!confirm('确定要删除用户 "' + username + '" 吗？此操作不可撤销。')) return;

  var token = localStorage.getItem('access_token');
  try {
    var response = await fetch('/auth/users/' + userId, {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (response.ok) {
      alert('用户删除成功');
      loadUsers();
    } else {
      var data = await response.json();
      alert(data.detail || '删除失败');
    }
  } catch (error) {
    console.error('删除用户失败:', error);
    alert('删除失败');
  }
}

function editUser(userId) {
  var user = usersList.find(function(u) { return u.id === userId; });
  if (!user) return;

  document.getElementById('editUserId').value = user.id;
  document.getElementById('editUsername').value = user.username;
  document.getElementById('editEmail').value = user.email;
  document.getElementById('editIsActive').checked = user.is_active;
  document.getElementById('editIsSuperuser').checked = user.is_superuser;

  document.getElementById('userModalOverlay').classList.remove('show');
  document.getElementById('editUserModalOverlay').classList.add('show');
}

async function saveUserEdit() {
  var userId = document.getElementById('editUserId').value;
  var username = document.getElementById('editUsername').value;
  var email = document.getElementById('editEmail').value;
  var isActive = document.getElementById('editIsActive').checked;
  var isSuperuser = document.getElementById('editIsSuperuser').checked;

  var token = localStorage.getItem('access_token');
  try {
    var response = await fetch('/auth/users/' + userId, {
      method: 'PUT',
      headers: {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: new URLSearchParams({
        username: username,
        email: email,
        is_active: isActive,
        is_superuser: isSuperuser
      })
    });
    if (response.ok) {
      alert('用户信息更新成功');
      document.getElementById('editUserModalOverlay').classList.remove('show');
      showUserManager();
    } else {
      var data = await response.json();
      alert(data.detail || '更新失败');
    }
  } catch (error) {
    console.error('更新用户失败:', error);
    alert('更新失败');
  }
}

function closeEditUserModal() {
  document.getElementById('editUserModalOverlay').classList.remove('show');
}

/* ===== 设备警告提示 ===== */
function showDeviceWarning() {
  document.getElementById('modalTitle').textContent = '⚠️ 设备通信异常';
  document.getElementById('modalBody').innerHTML =
    '<div style="padding:16px;border-radius:12px;background:rgba(250,204,21,0.08);border:1px solid rgba(250,204,21,0.2);margin-bottom:16px;">' +
    '  <p style="color:#fde047;font-size:14px;line-height:1.7;">' +
    '    检测到 ESP32 端设备存在通信错误。可能的原因包括：' +
    '  </p>' +
    '  <ul style="margin-left:20px;color:#facc15;font-size:13px;line-height:1.9;">' +
    '    <li>API Key 配置错误或已过期</li>' +
    '    <li>设备网络连接中断</li>' +
    '    <li>设备固件版本不兼容</li' +
    '    ><li>服务器端端口被防火墙拦截</li>' +
    '  </ul>' +
    '</div>' +
    '<h4 class="stat-model-config-h4">建议操作步骤</h4>' +
    '<ol style="margin-left:20px;color:var(--text-sub);font-size:13px;line-height:1.9;">' +
    '  <li>前往「硬件设备管理」页面检查设备状态</li>' +
    '  <li>验证 API Key 是否正确且未过期</li>' +
    '  <li>确认设备网络连接正常（WiFi/以太网）</li>' +
    '  <li>重启 ESP32 设备后重新连接</li>' +
    '</ol>';
  document.getElementById('modalOverlay').classList.add('show');
}

/* ===== 增强用户信息加载（同步悬浮头像）===== */
var _originalLoadUserInfo = loadUserInfo;
loadUserInfo = async function() {
  await _originalLoadUserInfo();
  // 同步右下角悬浮头像
  var userName = localStorage.getItem('username') || '';
  var floatingFallback = document.getElementById('floatingAvatarFallback');
  if (floatingFallback && userName) {
    floatingFallback.textContent = userName.charAt(0).toUpperCase();
    document.getElementById('floatingAvatarFallback').style.display = 'flex';
  }
};
