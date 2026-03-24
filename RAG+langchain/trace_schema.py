from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


StepName = Literal["Retriever", "Rerank", "Grader", "Rewriter", "Generator", "Init", "Finalize"]


class Step(BaseModel):
    name: StepName
    round: int = 1
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    token_usage: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    error: Optional[str] = None


class Trace(BaseModel):
    trace_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    user_question: str
    final_answer: str = ""
    passed: Optional[bool] = None
    rounds: int = 0
    steps: List[Step] = Field(default_factory=list)
    tags: Dict[str, Any] = Field(default_factory=dict)

