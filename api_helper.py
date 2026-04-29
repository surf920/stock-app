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
                timeout=180
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

            # パース試行1: そのまま
            try:
                return json.loads(text), None
            except json.JSONDecodeError:
                pass

            # パース試行2: 正規表現で JSON ブロックを抽出
            m = re.search(r'\{[\s\S]*\}', text)
            if m:
                try:
                    return json.loads(m.group()), None
                except json.JSONDecodeError:
                    pass

            # パース試行3: JSON内の制御文字を修復して再試行
            try:
                cleaned = text
                if m:
                    cleaned = m.group()
                cleaned = cleaned.replace('\r\n', '\\n').replace('\r', '\\n')
                lines = cleaned.split('\n')
                cleaned = '\\n'.join(lines)
                m2 = re.search(r'\{.*\}', cleaned, re.DOTALL)
                if m2:
                    return json.loads(m2.group()), None
            except (json.JSONDecodeError, Exception):
                pass

            # パース試行4: 各キーを個別に抽出してJSONを再構築
            try:
                extracted = {}
                for key in ["analysis", "key_numbers", "verification_checklist", "limitations",
                            "logical_counters", "historical_failures", "opposing_view",
                            "smart_money_silence", "falsification_criteria", "emotional_appeal",
                            "strength_score", "strongest_response", "weakest_response",
                            "overall_verdict", "next_actions", "next_action",
                            "approach_name", "data_sources", "framework", "pitfalls"]:
                    pattern = f'"{key}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"'
                    km = re.search(pattern, text, re.DOTALL)
                    if km:
                        extracted[key] = km.group(1).replace('\\n', '\n').replace('\\"', '"')
                    else:
                        pattern2 = f'"{key}"\\s*:\\s*(\\d+)'
                        km2 = re.search(pattern2, text)
                        if km2:
                            extracted[key] = int(km2.group(1))
                        else:
                            pattern3 = f'"{key}"\\s*:\\s*\\[(.*?)\\]'
                            km3 = re.search(pattern3, text, re.DOTALL)
                            if km3:
                                try:
                                    extracted[key] = json.loads(f'[{km3.group(1)}]')
                                except Exception:
                                    extracted[key] = km3.group(1)
                if extracted:
                    return extracted, None
            except Exception:
                pass

            return None, f"JSON解析失敗: {text[:200]}"

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return None, "APIタイムアウト"
        except Exception as e:
            return None, str(e)
    return None, "リトライ上限"