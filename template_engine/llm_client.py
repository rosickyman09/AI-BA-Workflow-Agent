"""
llm_client.py
=============
負責與 LLM 溝通：
- 將模板結構 + 用戶文件組合成 Prompt
- 要求 LLM 輸出結構化 JSON
- 處理返回結果及錯誤
支援: Anthropic Claude / OpenAI GPT / OpenRouter / DeepSeek
"""

import os
import json
import re
from typing import Optional


class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "openrouter",   # "anthropic" | "openai" | "openrouter" | "deepseek"
        model: Optional[str] = None,
    ):
        self.provider = provider
        self.api_key = api_key or self._resolve_api_key()
        self.model = model or self._default_model()

    def _resolve_api_key(self) -> str:
        """Resolve API key from environment based on provider"""
        key_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }
        env_var = key_map.get(self.provider)
        if env_var:
            key = os.environ.get(env_var)
            if key:
                return key

        # Fallback chain: try all available keys
        for var in ["OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]:
            key = os.environ.get(var)
            if key:
                return key

        return ""

    def _default_model(self) -> str:
        models = {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4o",
            "openrouter": os.environ.get("OPENROUTER_MODELS", "openai/gpt-4o").split(",")[0].strip(),
            "deepseek": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        }
        return models.get(self.provider, "openai/gpt-4o")

    # ──────────────────────────────────────────────────────────────
    # 主要入口：傳入模板結構 + 文件內容，返回填寫資料
    # ──────────────────────────────────────────────────────────────
    def extract_data(self, template_structure: dict, document_content: str) -> dict:
        """
        核心方法：
        1. 根據模板結構建立 Prompt
        2. 呼叫 LLM
        3. 解析返回 JSON
        """
        system_prompt = self._build_system_prompt(template_structure)
        user_prompt = self._build_user_prompt(template_structure, document_content)

        print(f"  → 使用模型：{self.provider}/{self.model}")
        raw_response = self._call_llm(system_prompt, user_prompt)
        extracted = self._parse_response(raw_response)

        # 若 LLM 返回的是純 fields，包裝成標準格式
        if "fields" not in extracted:
            extracted = {"fields": extracted, "tables": {}}

        return extracted

    # ──────────────────────────────────────────────────────────────
    # Prompt 建構
    # ──────────────────────────────────────────────────────────────
    def _build_system_prompt(self, template_structure: dict) -> str:
        return """你係一個專業文件分析助手。你的任務是：
1. 分析用戶提供的文件內容
2. 根據 Word 模板的結構，提取對應的資料
3. 以嚴格的 JSON 格式輸出結果

## 輸出規則（非常重要）：
- 只輸出 JSON，不要有任何前置說明或後置說明
- 不要用 markdown 代碼塊（```json）包裹
- 如果某個欄位在文件中找不到對應資料，值設為 null
- 日期統一格式為：YYYY-MM-DD
- 金額統一格式為：數字+貨幣（例如：HK$50,000）
- 表格重複行資料以 JSON 陣列格式提供
- 如果表格某個 section 在文件中找不到任何對應資料，該表格的陣列設為空 []
- 絕對不要重複 placeholder 行 — 每筆資料只出現一次

## 表格資料規則（防止重複行）：
- 每個表格的資料必須是一個 JSON 陣列 []
- 陣列中每個元素代表表格的一行資料
- 如果找不到資料，返回空陣列 [] （不要返回帶有 placeholder 的行）
- 不要將同一筆資料重複多次

## 輸出 JSON 結構：
{
  "fields": {
    "欄位名": "對應值"
  },
  "tables": {
    "表格索引（數字）": [
      {"欄1": "值1", "欄2": "值2"},
      {"欄1": "值3", "欄2": "值4"}
    ]
  }
}"""

    def _build_user_prompt(self, template_structure: dict, document_content: str) -> str:
        mode = template_structure.get("mode", "table_only")
        fill_instructions = template_structure.get("fill_instructions", "")

        # 簡化模板結構傳給 LLM（避免 token 過多）
        simplified_structure = self._simplify_structure(template_structure)

        prompt = f"""## 模板結構說明：
{fill_instructions}

## 模板詳細結構（JSON）：
{json.dumps(simplified_structure, ensure_ascii=False, indent=2)}

## 用戶文件內容：
{document_content[:8000]}  

請根據以上資料，提取所有欄位的對應值，以 JSON 格式輸出。"""

        return prompt

    def _simplify_structure(self, structure: dict) -> dict:
        """簡化結構，只保留 LLM 需要的資訊"""
        simplified = {
            "mode": structure["mode"],
            "placeholders": structure["placeholders"],
            "tables": []
        }
        for table in structure["tables"]:
            simplified["tables"].append({
                "table_index": table["table_index"],
                "header_row": [c["text"] for c in table["header_row"] if c["text"]],
                "is_repeating": table["is_repeating"],
                "placeholders": table["all_placeholders"]
            })
        return simplified

    # ──────────────────────────────────────────────────────────────
    # LLM 呼叫（支援多個 Provider）
    # ──────────────────────────────────────────────────────────────
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        if self.provider == "anthropic":
            return self._call_anthropic(system_prompt, user_prompt)
        elif self.provider == "openai":
            return self._call_openai(system_prompt, user_prompt)
        elif self.provider == "openrouter":
            return self._call_openrouter(system_prompt, user_prompt)
        elif self.provider == "deepseek":
            return self._call_deepseek(system_prompt, user_prompt)
        else:
            raise ValueError(f"不支援的 Provider：{self.provider}")

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        try:
            import anthropic
        except ImportError:
            raise ImportError("請安裝：pip install anthropic")

        client = anthropic.Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return message.content[0].text

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("請安裝：pip install openai")

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},  # 強制 JSON 輸出
            max_tokens=4096
        )
        return response.choices[0].message.content

    def _call_openrouter(self, system_prompt: str, user_prompt: str) -> str:
        """OpenRouter uses OpenAI-compatible API at https://openrouter.ai/api/v1"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("請安裝：pip install openai")

        client = OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=4096
        )
        return response.choices[0].message.content

    def _call_deepseek(self, system_prompt: str, user_prompt: str) -> str:
        """DeepSeek 用 OpenAI 相容 API"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("請安裝：pip install openai")

        client = OpenAI(
            api_key=self.api_key or os.environ.get("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=4096
        )
        return response.choices[0].message.content

    # ──────────────────────────────────────────────────────────────
    # JSON 解析（容錯處理）
    # ──────────────────────────────────────────────────────────────
    def _parse_response(self, raw: str) -> dict:
        """解析 LLM 輸出，容錯處理各種格式"""
        # 移除可能的 markdown 代碼塊
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
        cleaned = cleaned.rstrip("`").strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # 嘗試提取 JSON 部分
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

            print(f"  ⚠️  警告：無法解析 LLM 輸出，返回空結果")
            print(f"  原始輸出：{raw[:200]}...")
            return {"fields": {}, "tables": {}}
