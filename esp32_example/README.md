# ESP32 AI Chat Client 示例

这是一个用于连接 AIManagePlatform 后端的 ESP32 示例代码。

## 硬件要求

- ESP32 开发板（如 NodeMCU-32S、ESP32-DevKitC 等）
- 已连接 WiFi 网络
- 能够访问服务器

## 软件要求

### 1. Arduino IDE

下载并安装 Arduino IDE: https://www.arduino.cc/en/software

### 2. 安装库

在 Arduino IDE 中安装以下库：

1. **ArduinoJson**
   - 菜单：工具 -> 管理库
   - 搜索 "ArduinoJson"
   - 选择最新版本并安装

### 3. 配置代码

编辑 `esp32_ai_client.ino` 文件，修改以下配置：

```cpp
// WiFi 配置
const char* WIFI_SSID = "你的WiFi名称";
const char* WIFI_PASSWORD = "你的WiFi密码";

// 服务器配置
const char* SERVER_URL = "http://你的服务器IP:8002";

// 设备码（在网页端注册后获取）
const char* DEVICE_CODE = "你的设备码";
```

## 使用步骤

### 1. 注册设备

1. 在浏览器中打开 AIManagePlatform 网页
2. 输入 API Key 并登录
3. 进入"管理与设备"页面
4. 点击"ESP32 设备管理"标签
5. 输入设备名称，点击"注册设备"
6. 复制生成的设备码（如：`A1B2C3D4`）

### 2. 配置 ESP32 代码

将上一步获得的设备码填入代码中：

```cpp
const char* DEVICE_CODE = "A1B2C3D4";  // 替换为你的设备码
```

### 3. 上传代码

1. 在 Arduino IDE 中打开 `esp32_ai_client.ino`
2. 选择正确的开发板和端口（工具 -> 开发板 -> ESP32 Arduino）
3. 点击上传按钮
4. 打开串口监视器（115200 波特率）

### 4. 查看输出

串口输出应该显示：
```
===========================================
ESP32 AI Chat Client
===========================================
正在连接 WiFi: 你的WiFi名称
WiFi 连接成功!
IP 地址: 192.168.x.x

测试服务器连接...
服务器连接成功！

========== 发送测试消息 ==========
发送: 你好，请介绍一下你自己
发送请求到服务器...
收到回复:
-------------------------------------------
你好！我是...
-------------------------------------------
回复长度: 50 字符
=======================================
```

## API 接口说明

### 发送聊天消息

**端点**: `POST /chat`

**请求体**:
```json
{
  "device_code": "设备码",
  "model": "glm-5.1",
  "max_tokens": 512,
  "temperature": 0.7,
  "enable_think": false,
  "messages": [
    {"role": "system", "content": "系统提示词"},
    {"role": "user", "content": "用户消息"}
  ]
}
```

**响应**: SSE 流格式
```
data: {"content": "AI"}

data: {"content": "回复"}

data: [DONE]
```

## 错误处理

可能的错误响应：
- `设备码未注册，请先在网页端注册设备` - 设备码无效
- `设备未分配有效的 API Key` - 服务器无可用 API Key
- `HTTP 错误` - 网络或服务器问题

## 扩展应用

### 添加按键触发

```cpp
const int BUTTON_PIN = 0;  // GPIO0 按键

void loop() {
  if (digitalRead(BUTTON_PIN) == LOW) {
    sendChatMessage("你好");
    delay(1000);
  }
}
```

### 添加语音模块

可以连接语音识别模块（如 LYRA-T、WM8960），将语音转为文字后发送。

### 添加显示屏

连接 OLED 或 LCD 显示屏，显示 AI 回复内容。

## 注意事项

1. **网络稳定性**：确保 ESP32 能够稳定访问服务器
2. **API Key 配额**：每个 API Key 最多支持 50 个设备
3. **响应时间**：AI 推理可能需要几秒钟，保持网络连接稳定
4. **内存限制**：ESP32 内存有限，避免发送过长的消息

## 故障排除

### WiFi 连接失败
- 检查 SSID 和密码是否正确
- 确保 WiFi 是 2.4GHz（ESP32 不支持 5GHz）

### 服务器连接失败
- 检查 SERVER_URL 是否正确
- 确保服务器正在运行
- 检查防火墙设置

### JSON 解析错误
- 检查 ArduinoJson 库是否正确安装
- 确保固件版本支持当前代码
