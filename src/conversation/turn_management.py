"""
Turn Management - Gestion de turnos de conversacion
"""
import logging
import time
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class TurnOwner(Enum):
    AGENT = "agent"
    USER = "user"
    NONE = "none"


@dataclass
class ConversationTurn:
    owner: TurnOwner
    content: str
    start_time: float
    end_time: Optional[float] = None
    was_interrupted: bool = False
    duration_ms: float = 0.0


class TurnManager:
    """
    Gestiona los turnos de conversacion para evitar solapamiento.
    Asegura que solo uno habla a la vez y maneja transiciones suaves.
    """

    def __init__(self, min_turn_duration_s: float = 0.5):
        self.current_owner = TurnOwner.NONE
        self.min_turn_duration = min_turn_duration_s
        self._turns: List[ConversationTurn] = []
        self._current_turn: Optional[ConversationTurn] = None
        logger.info("TurnManager inicializado")

    def start_agent_turn(self, content: str) -> bool:
        """Inicia el turno del agente. Retorna False si el usuario esta hablando."""
        if self.current_owner == TurnOwner.USER:
            logger.debug("No se puede iniciar turno del agente: usuario hablando")
            return False
        self._start_turn(TurnOwner.AGENT, content)
        return True

    def start_user_turn(self, content: str = "") -> bool:
        """Inicia el turno del usuario (puede interrumpir al agente)."""
        if self._current_turn and self.current_owner == TurnOwner.AGENT:
            self._current_turn.was_interrupted = True
            self.end_current_turn()
            logger.info("Turno del agente interrumpido por usuario")
        self._start_turn(TurnOwner.USER, content)
        return True

    def _start_turn(self, owner: TurnOwner, content: str) -> None:
        if self._current_turn:
            self.end_current_turn()
        self.current_owner = owner
        self._current_turn = ConversationTurn(
            owner=owner, content=content, start_time=time.time()
        )
        logger.debug("Turno iniciado: %s", owner.value)

    def end_current_turn(self) -> Optional[ConversationTurn]:
        if not self._current_turn:
            return None
        turn = self._current_turn
        turn.end_time = time.time()
        turn.duration_ms = (turn.end_time - turn.start_time) * 1000
        self._turns.append(turn)
        self._current_turn = None
        self.current_owner = TurnOwner.NONE
        logger.debug("Turno finalizado: %s (%.0f ms)", turn.owner.value, turn.duration_ms)
        return turn

    def get_turn_history(self) -> List[ConversationTurn]:
        return list(self._turns)

    def get_stats(self) -> dict:
        agent_turns = [t for t in self._turns if t.owner == TurnOwner.AGENT]
        user_turns = [t for t in self._turns if t.owner == TurnOwner.USER]
        interruptions = sum(1 for t in self._turns if t.was_interrupted)
        return {
            "total_turns": len(self._turns),
            "agent_turns": len(agent_turns),
            "user_turns": len(user_turns),
            "interruptions": interruptions,
            "avg_agent_turn_ms": (
                sum(t.duration_ms for t in agent_turns) / len(agent_turns)
                if agent_turns else 0
            ),
        }
