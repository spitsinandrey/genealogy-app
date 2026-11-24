import urllib.request
import ssl
import json

# Отключаем проверку сертификатов (только для теста)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ВСТАВЬТЕ ВАШ РЕАЛЬНЫЙ КЛЮЧ СЮДА (без русских букв)
api_key = "sk-e9a96145c5554e30a4a812b89d9e6d61" 

url = "https://api.deepseek.com/v1/chat/completions"

payload = {
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0
}

# Кодируем данные в байты вручную, чтобы избежать ошибок кодировки
data = json.dumps(payload).encode('utf-8')

req = urllib.request.Request(url, data=data, method="POST")
req.add_header("Authorization", f"Bearer {api_key}")
req.add_header("Content-Type", "application/json")

print("Пробуем подключиться к DeepSeek...")
try:
    with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
        print("УСПЕХ! Статус:", response.status)
        print("Ответ:", response.read().decode('utf-8')[:300])
except urllib.error.HTTPError as e:
    print(f"HTTP Ошибка: {e.code}")
    print("Ответ сервера:", e.read().decode('utf-8')[:300])
except Exception as e:
    print("ОШИБКА:", e)