"""
Agent 7: Security Agent  Prompt Injection & Malicious Input Prevention
"""
import re
import html
import logging
from typing import List, Tuple

from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse

logger = logging.getLogger(__name__)

#  Injection patterns 
_INJECTION_RULES: List[Tuple[str, re.Pattern]] = [
    ("ignore_previous",  re.compile(r"ignore\s+(previous|prior|above)\s+instructions?", re.I)),
    ("system_override",  re.compile(r"(you are now|act as|pretend you|roleplay as|new\s+persona)", re.I)),
    ("jailbreak",        re.compile(r"\b(jailbreak|DAN|do\s+anything\s+now)\b", re.I)),
    ("bypass_filter",    re.compile(r"(bypass|circumvent|override)\s+(safety|filter|restriction|policy)", re.I)),
    ("reveal_prompt",    re.compile(r"(reveal|show|print|output)\s+(your\s+)?(system\s+prompt|instructions?|base\s+prompt)", re.I)),
    ("end_prompt",       re.compile(r"(</?(system|user|assistant)>|<\|im_end\|>|\[INST\]|\[\/INST\])", re.I)),
    ("disregard_rules",  re.compile(r"(disregard|forget|ignore|override)\s+(all\s+)?(rules?|guidelines?|ethics)", re.I)),
]

_XSS_RULES: List[Tuple[str, re.Pattern]] = [
    ("script_tag",    re.compile(r"<script[\s>]", re.I)),
    ("js_protocol",   re.compile(r"javascript\s*:", re.I)),
    ("event_handler", re.compile(r"\bon\w+\s*=", re.I)),
    ("iframe",        re.compile(r"<\s*iframe", re.I)),
]

_MALICIOUS_RULES: List[Tuple[str, re.Pattern]] = [
    ("sql_injection",   re.compile(r"(\bUNION\b.*\bSELECT\b|\bDROP\s+TABLE|\bINSERT\s+INTO)", re.I)),
    ("shell_injection", re.compile(r"(;\s*(rm|del|format|shutdown|reboot)\s)", re.I)),
    ("path_traversal",  re.compile(r"(\.\.[\\\\/ ]){2,}", re.I)),
]

_MAX_INPUT_LEN = 50_000


class SecurityAgent(BaseAgent):
    """Entry-point filter for prompt injection and malicious inputs."""

    def __init__(self):
        super().__init__("SecurityAgent")

    async def execute(self, request: AgentRequest) -> AgentResponse:
        try:
            raw_input = request.data.get("raw_input", "")
            if len(raw_input) > _MAX_INPUT_LEN:
                raw_input = raw_input[:_MAX_INPUT_LEN]

            sanitized = self._sanitize_input(raw_input)
            injection_result = self._detect_prompt_injection(raw_input)
            xss_result = self._detect_xss(raw_input)
            malicious = self._detect_malicious_patterns(raw_input)

            threats_detected = injection_result["flags"] + xss_result["flags"] + malicious
            is_safe = not (injection_result["detected"] or xss_result["detected"] or bool(malicious))

            if not is_safe:
                logger.warning(
                    "SecurityAgent blocked input user=%s project=%s threats=%s",
                    request.user_id, request.project_id,
                    [t["pattern_name"] for t in threats_detected],
                )

            return AgentResponse(
                agent_name=self.agent_name,
                status="success",
                output={
                    "is_safe": is_safe,
                    "is_injection": injection_result["detected"],
                    "passed": is_safe,
                    "sanitized_input": sanitized,
                    "threats_detected": threats_detected,
                },
                confidence=1.0 if is_safe else 0.0,
            )
        except Exception as e:
            return self.fallback_response(str(e))

    #  Skills 

    def _sanitize_input(self, input_str: str) -> str:
        return html.escape(input_str.replace("\x00", ""))

    def _detect_prompt_injection(self, input_str: str) -> dict:
        flags = [
            {"type": "prompt_injection", "pattern_name": name}
            for name, regex in _INJECTION_RULES if regex.search(input_str)
        ]
        return {"detected": bool(flags), "flags": flags}

    def _detect_xss(self, input_str: str) -> dict:
        flags = [
            {"type": "xss", "pattern_name": name}
            for name, regex in _XSS_RULES if regex.search(input_str)
        ]
        return {"detected": bool(flags), "flags": flags}

    def _detect_malicious_patterns(self, input_str: str) -> list:
        return [
            {"type": "malicious", "pattern_name": name}
            for name, regex in _MALICIOUS_RULES if regex.search(input_str)
        ]


