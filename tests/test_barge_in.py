"""Tests para BargeInHandler (Gap #19)"""
import time
import threading
import pytest
from src.conversation.barge_in_handler import BargeInHandler, BargeInState
from src.conversation.interruption_detector import InterruptionDetector


@pytest.fixture
def handler():
    return BargeInHandler(interruption_threshold_s=0.3, false_positive_guard_s=0.05)


class TestBargeInStates:
    def test_initial_state_idle(self, handler):
        assert handler.get_state() == BargeInState.IDLE

    def test_state_agent_speaking_after_start(self, handler):
        handler.start_agent_speech("Hola, ¿en que puedo ayudarle?")
        assert handler.get_state() == BargeInState.AGENT_SPEAKING
        handler.wait_for_completion(timeout=5.0)

    def test_state_idle_after_completion(self, handler):
        handler.start_agent_speech("Ok.")
        handler.wait_for_completion(timeout=5.0)
        assert handler.get_state() == BargeInState.IDLE

    def test_state_processing_after_interrupt(self, handler):
        handler.start_agent_speech("Texto largo para que haya tiempo de interrumpir")
        time.sleep(0.1)
        handler.signal_user_speech()
        assert handler.get_state() in (BargeInState.USER_INTERRUPTING, BargeInState.PROCESSING)

    def test_is_agent_speaking_true(self, handler):
        handler.start_agent_speech("Hablando...")
        assert handler.is_agent_speaking() is True
        handler.wait_for_completion(timeout=5.0)

    def test_is_agent_speaking_false_initially(self, handler):
        assert handler.is_agent_speaking() is False


class TestInterruption:
    def test_signal_user_speech_cancels_tts(self, handler):
        handler.start_agent_speech("Texto muy largo " * 20)
        time.sleep(0.05)
        handler.signal_user_speech()
        assert handler.tts_active is False

    def test_interrupt_count_increments(self, handler):
        handler.start_agent_speech("A")
        time.sleep(0.05)
        handler.signal_user_speech()
        handler.start_agent_speech("B")
        time.sleep(0.05)
        handler.signal_user_speech()
        metrics = handler.get_metrics()
        assert metrics["interruption_count"] == 2

    def test_signal_no_tts_active_ignored(self, handler):
        handler.signal_user_speech()  # no hay TTS activo
        assert handler.get_metrics()["interruption_count"] == 0

    def test_callback_called_on_interrupt(self, handler):
        called = threading.Event()
        handler.set_interruption_callback(lambda: called.set())
        handler.start_agent_speech("Texto largo " * 20)
        time.sleep(0.05)
        handler.signal_user_speech()
        called.wait(timeout=2.0)
        assert called.is_set()

    def test_cancel_current_speech(self, handler):
        handler.start_agent_speech("Texto " * 50)
        time.sleep(0.05)
        handler.cancel_current_speech()
        assert handler.tts_active is False


class TestMetrics:
    def test_metrics_dict_structure(self, handler):
        metrics = handler.get_metrics()
        assert "interruption_count" in metrics
        assert "avg_response_ms" in metrics
        assert "meets_slo" in metrics
        assert "current_state" in metrics

    def test_meets_slo_initially(self, handler):
        metrics = handler.get_metrics()
        assert metrics["meets_slo"] is True

    def test_avg_response_ms_zero_initially(self, handler):
        metrics = handler.get_metrics()
        assert metrics["avg_response_ms"] == 0.0


class TestInterruptionDetector:
    def test_silence_not_interrupt(self):
        detector = InterruptionDetector()
        silent = b"\x00" * 3200
        is_interrupt, energy = detector.process_audio_chunk(silent)
        assert is_interrupt is False
        assert energy == pytest.approx(0.0)

    def test_reset_clears_duration(self):
        detector = InterruptionDetector()
        detector._current_speech_duration = 1.5
        detector.reset()
        assert detector._current_speech_duration == 0.0

    def test_set_thresholds(self):
        detector = InterruptionDetector()
        detector.set_thresholds(energy=0.05, duration=0.5)
        assert detector.energy_threshold == 0.05
        assert detector.duration_threshold == 0.5
