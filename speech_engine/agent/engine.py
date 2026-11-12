from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_SCENARIO_PATH = Path(__file__).resolve().parents[2] / "scenarios" / "cold_sales.json"


@dataclass(frozen=True)
class AgentReply:
    text: str
    next_step: str
    intent: str
    status: str
    handoff: bool = False
    finish: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "next_step": self.next_step,
            "intent": self.intent,
            "status": self.status,
            "handoff": self.handoff,
            "finish": self.finish,
        }


class AgentEngine:
    """Small rule-based scenario engine for a first call-agent MVP."""

    def __init__(self, scenario_path: str | Path = DEFAULT_SCENARIO_PATH) -> None:
        self.scenario_path = Path(scenario_path)
        self.scenario = self._load_scenario(self.scenario_path)
        self.default_step = str(self.scenario.get("start_step", "greeting"))
        self.fallback_intent = str(self.scenario.get("fallback_intent", "fallback"))

    def start(self) -> AgentReply:
        step = self._get_step(self.default_step)
        return AgentReply(
            text=str(step["say"]),
            next_step=self.default_step,
            intent="start",
            status=str(step.get("status", "started")),
            handoff=bool(step.get("handoff", False)),
            finish=bool(step.get("finish", False)),
        )

    def respond(self, customer_text: str, current_step: Optional[str] = None) -> AgentReply:
        step_id = current_step or self.default_step
        step = self._get_step(step_id)
        normalized_text = self._normalize(customer_text)

        intent_id = self._match_intent(normalized_text, step)
        transition = self._get_transition(step, intent_id)
        if transition is None and intent_id != self.fallback_intent:
            intent_id = self.fallback_intent
            transition = self._get_transition(step, intent_id)

        if transition is None:
            transition = {
                "next_step": step_id,
                "status": str(step.get("status", "in_progress")),
            }

        next_step_id = str(transition.get("next_step", step_id))
        next_step = self._get_step(next_step_id)

        return AgentReply(
            text=str(transition.get("say") or next_step["say"]),
            next_step=next_step_id,
            intent=intent_id,
            status=str(transition.get("status") or next_step.get("status", "in_progress")),
            handoff=bool(transition.get("handoff", next_step.get("handoff", False))),
            finish=bool(transition.get("finish", next_step.get("finish", False))),
        )

    def _load_scenario(self, scenario_path: Path) -> Dict[str, Any]:
        if not scenario_path.is_file():
            raise FileNotFoundError(f"Scenario file not found: {scenario_path}")

        with scenario_path.open("r", encoding="utf-8") as file:
            scenario = json.load(file)

        if "steps" not in scenario or not isinstance(scenario["steps"], dict):
            raise ValueError("Scenario must contain a 'steps' object.")

        return scenario

    def _get_step(self, step_id: str) -> Dict[str, Any]:
        steps = self.scenario["steps"]
        if step_id not in steps:
            raise ValueError(f"Scenario step not found: {step_id}")
        step = steps[step_id]
        if "say" not in step:
            raise ValueError(f"Scenario step has no 'say' text: {step_id}")
        return step

    def _match_intent(self, normalized_text: str, step: Dict[str, Any]) -> str:
        intents: Dict[str, List[str]] = self.scenario.get("intents", {})
        allowed_intents = list(step.get("transitions", {}).keys())
        allowed_intents = sorted(
            allowed_intents,
            key=lambda intent_id: self._intent_priority(intent_id),
        )

        for intent_id in allowed_intents:
            patterns = intents.get(intent_id, [])
            for pattern in patterns:
                if self._pattern_matches(normalized_text, pattern):
                    return intent_id

        return self.fallback_intent

    def _intent_priority(self, intent_id: str) -> int:
        priorities = {
            "negative": 0,
            "callback": 1,
            "human": 2,
            "price": 3,
            "positive": 4,
            self.fallback_intent: 99,
        }
        return priorities.get(intent_id, 50)

    def _get_transition(self, step: Dict[str, Any], intent_id: str) -> Optional[Dict[str, Any]]:
        transition = step.get("transitions", {}).get(intent_id)
        if transition is None:
            return None
        if isinstance(transition, str):
            return {"next_step": transition}
        if not isinstance(transition, dict):
            raise ValueError(f"Invalid transition for intent '{intent_id}'.")
        return transition

    def _pattern_matches(self, normalized_text: str, pattern: str) -> bool:
        if pattern.startswith("re:"):
            return re.search(pattern[3:], normalized_text, flags=re.IGNORECASE) is not None
        return pattern.casefold() in normalized_text

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.casefold()).strip()
