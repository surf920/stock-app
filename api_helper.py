import requests
import json
import re
import time

def call_anthropic_api(headers, payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=90
            )
            if response.status_code == 529:
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                return None, "APIサーバーが混雑中。しばらく待って再試行してください。"
            if response.status_code != 200:
                return None, f"API Error {response.status_code}: {response.text[:200]}"
            result = response.json()
            text = ""
            for block in result.get("content", []):
                if block.get("type") == "text":
                    text += block["text"]
            text = text.strip()
            if not text:
                return None, "AIからの応答が空です。"
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            try:
                return json.loads(text), None
            except json.JSONDecodeError:
                m = re.search(r'\{[\s\S]*\}', text)
                if m:
                    return json.loads(m.group()), None
                return None, f"JSON解析失敗: {text[:200]}"
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return None, "APIタイムアウト"
        except Exception as e:
            return None, str(e)
    return None, "リトライ上限"
