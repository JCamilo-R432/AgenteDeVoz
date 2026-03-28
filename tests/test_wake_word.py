"""
Tests para Wake Word Detector (Gap #31)
"""
import time
import pytest
from src.voice_activation.wake_word_detector import WakeWordDetector, WakeWordEngine


class TestWakeWordDetector:
    def setup_method(self):
        self.detector = WakeWordDetector(wake_word="agente", engine="simulated")

    def teardown_method(self):
        if self.detector._listening:
            self.detector.stop_listening()

    def test_initialization(self):
        assert self.detector.wake_word == "agente"
        assert self.detector.engine == WakeWordEngine.SIMULATED
        assert self.detector.sensitivity == 0.5
        assert not self.detector._listening

    def test_set_callback(self):
        callback_called = []
        self.detector.set_callback(lambda: callback_called.append(True))
        assert self.detector._callback is not None

    def test_adjust_sensitivity_valid(self):
        self.detector.adjust_sensitivity(0.8)
        assert self.detector.sensitivity == 0.8

    def test_adjust_sensitivity_zero(self):
        self.detector.adjust_sensitivity(0.0)
        assert self.detector.sensitivity == 0.0

    def test_adjust_sensitivity_one(self):
        self.detector.adjust_sensitivity(1.0)
        assert self.detector.sensitivity == 1.0

    def test_adjust_sensitivity_invalid_raises(self):
        with pytest.raises(ValueError):
            self.detector.adjust_sensitivity(1.5)

    def test_adjust_sensitivity_negative_raises(self):
        with pytest.raises(ValueError):
            self.detector.adjust_sensitivity(-0.1)

    def test_train_custom_wake_word_success(self):
        samples = ["path/sample1.wav", "path/sample2.wav", "path/sample3.wav"]
        result = self.detector.train_custom_wake_word(samples)
        assert result is True

    def test_train_custom_wake_word_empty_fails(self):
        result = self.detector.train_custom_wake_word([])
        assert result is False

    def test_train_custom_wake_word_few_samples_warns(self):
        # Deberia funcionar pero con advertencia
        result = self.detector.train_custom_wake_word(["sample1.wav"])
        assert result is True

    def test_get_stats(self):
        stats = self.detector.get_stats()
        assert "wake_word" in stats
        assert "engine" in stats
        assert "sensitivity" in stats
        assert "is_listening" in stats
        assert "detection_count" in stats
        assert stats["detection_count"] == 0

    def test_start_and_stop_listening(self):
        self.detector.start_listening()
        assert self.detector._listening is True
        self.detector.stop_listening()
        assert self.detector._listening is False

    def test_start_while_already_listening(self):
        self.detector.start_listening()
        self.detector.start_listening()  # No debe crear segundo hilo
        assert self.detector._thread is not None
        self.detector.stop_listening()

    def test_detection_with_callback(self):
        """Verifica que la deteccion ejecuta el callback."""
        detected = []
        self.detector.set_callback(lambda: detected.append(True))
        # Simular deteccion directa
        self.detector._on_detection()
        assert len(detected) == 1
        assert self.detector._detection_count == 1

    def test_cooldown_prevents_double_detection(self):
        """Detecciones muy rapidas no deben ejecutar el callback dos veces."""
        detected = []
        self.detector.set_callback(lambda: detected.append(True))
        self.detector._cooldown_seconds = 5.0  # Cooldown largo para el test
        self.detector._on_detection()
        self.detector._on_detection()  # Segunda deteccion inmediata - bloqueada
        assert len(detected) == 1  # Solo una ejecucion

    def test_default_wake_words(self):
        assert "agente" in WakeWordDetector.DEFAULT_WAKE_WORDS

    def test_invalid_engine_raises(self):
        with pytest.raises(ValueError):
            WakeWordDetector(engine="engine_inexistente")
