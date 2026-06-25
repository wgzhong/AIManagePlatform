/*
 * ESP32 AI Chat Client
 * 用于连接 AIManagePlatform 后端进行 AI 推理
 * 
 * 需要安装的库：
 * - WiFi.h (内置)
 * - HTTPClient.h (内置)
 * - ArduinoJson.h (需要安装)
 * 
 * 安装 ArduinoJson:
 * Arduino IDE -> 工具 -> 管理库 -> 搜索 "ArduinoJson" -> 安装
 * 
 * 配置步骤：
 * 1. 在网页端注册设备，获取设备码
 * 2. 修改下面的 DEVICE_CODE 为你的设备码
 * 3. 修改 WiFi 信息
 * 4. 修改服务器地址 SERVER_URL
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ============ 配置区 ============

// WiFi 配置
const char* WIFI_SSID = "你的WiFi名称";
const char* WIFI_PASSWORD = "你的WiFi密码";

// 服务器配置
const char* SERVER_URL = "http://你的服务器IP:8002";  // 修改为你的服务器地址

// 设备码（在网页端注册后获取）
const char* DEVICE_CODE = "你的设备码";  // 例如: "A1B2C3D4"

// ============ 函数声明 ============
void setupWiFi();
String sendChatMessage(const char* message);
String makeRequest(const char* endpoint, const char* method, const char* body);
void printResponse(String response);

// ============ 设置 ============
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("===========================================");
  Serial.println("ESP32 AI Chat Client");
  Serial.println("===========================================");
  
  // 连接 WiFi
  setupWiFi();
  
  // 测试连接
  Serial.println("\n测试服务器连接...");
  String result = makeRequest("/api/devices", "GET", nullptr);
  if (result.length() > 0) {
    Serial.println("服务器连接成功！");
  } else {
    Serial.println("警告：服务器连接失败，请检查服务器地址");
  }
}

// ============ 主循环 ============
void loop() {
  // 检查 WiFi 连接
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi 断开，重新连接...");
    setupWiFi();
  }
  
  // 示例：发送测试消息
  // 在实际应用中，可以通过按键、串口命令等方式触发
  static bool sent = false;
  if (!sent && WiFi.status() == WL_CONNECTED) {
    sent = true;
    
    Serial.println("\n========== 发送测试消息 ==========");
    
    // 简单的中文对话测试
    const char* testMessage = "你好，请介绍一下你自己";
    Serial.printf("发送: %s\n", testMessage);
    
    String response = sendChatMessage(testMessage);
    printResponse(response);
    
    Serial.println("=======================================\n");
  }
  
  delay(1000);
}

// ============ WiFi 连接 ============
void setupWiFi() {
  Serial.print("正在连接 WiFi: ");
  Serial.println(WIFI_SSID);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi 连接成功!");
    Serial.print("IP 地址: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi 连接失败!");
  }
}

// ============ 发送聊天消息 ============
String sendChatMessage(const char* message) {
  // 构建请求体（使用 DynamicJsonDocument 支持较大消息）
  DynamicJsonDocument requestDoc(2048);
  requestDoc["device_code"] = DEVICE_CODE;
  requestDoc["model"] = "glm-5.1";
  requestDoc["max_tokens"] = 512;
  requestDoc["temperature"] = 0.7;
  requestDoc["enable_think"] = false;
  
  JsonArray messages = requestDoc.createNestedArray("messages");
  JsonObject systemMsg = messages.createNestedObject();
  systemMsg["role"] = "system";
  systemMsg["content"] = "你是一个友好的AI助手，请用简洁的语言回答问题。";
  
  JsonObject userMsg = messages.createNestedObject();
  userMsg["role"] = "user";
  userMsg["content"] = message;
  
  char jsonBuffer[2048];
  serializeJson(requestDoc, jsonBuffer);
  
  Serial.println("发送请求到服务器...");
  
  String response = makeRequest("/chat", "POST", jsonBuffer);
  
  if (response.length() == 0) {
    return "错误：服务器无响应";
  }
  
  // 解析 SSE 响应
  return parseSSEResponse(response);
}

// ============ 解析 SSE 响应 ============
String parseSSEResponse(const String& sseData) {
  String fullResponse = "";
  
  // 按行分割 SSE 数据
  int start = 0;
  while (start < sseData.length()) {
    int lineEnd = sseData.indexOf('\n', start);
    if (lineEnd == -1) lineEnd = sseData.length();
    
    String line = sseData.substring(start, lineEnd);
    start = lineEnd + 1;
    
    // 跳过空行和 [DONE]
    if (line.length() == 0 || line.startsWith("data: [DONE]")) {
      continue;
    }
    
    // 提取 JSON 数据
    if (line.startsWith("data: ")) {
      String jsonStr = line.substring(6);
      
      // 尝试解析 JSON
      StaticJsonDocument<1024> doc;
      DeserializationError error = deserializeJson(doc, jsonStr);
      
      if (!error) {
        // 检查是否有错误
        if (doc.containsKey("error")) {
          return "错误: " + doc["error"].as<String>();
        }
        
        // 提取内容
        if (doc.containsKey("content")) {
          fullResponse += doc["content"].as<String>();
        }
      }
    }
  }
  
  return fullResponse;
}

// ============ HTTP 请求 ============
String makeRequest(const char* endpoint, const char* method, const char* body) {
  HTTPClient http;
  String url = String(SERVER_URL) + endpoint;
  
  Serial.printf("请求 URL: %s\n", url.c_str());
  
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(30000); // 30秒超时
  
  String response = "";
  
  if (strcmp(method, "POST") == 0) {
    int httpCode = http.POST(body);
    
    if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_MOVED_PERMANENTLY) {
      response = http.getString();
    } else {
      Serial.printf("HTTP POST 错误: %d\n", httpCode);
    }
  } else {
    int httpCode = http.GET();
    
    if (httpCode == HTTP_CODE_OK) {
      response = http.getString();
    } else {
      Serial.printf("HTTP GET 错误: %d\n", httpCode);
    }
  }
  
  http.end();
  return response;
}

// ============ 打印响应 ============
void printResponse(String response) {
  Serial.println("收到回复:");
  Serial.println("-------------------------------------------");
  Serial.println(response);
  Serial.println("-------------------------------------------");
  Serial.printf("回复长度: %d 字符\n", response.length());
}
