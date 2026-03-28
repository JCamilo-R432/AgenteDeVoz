"""Tests para EmotionDetector y FrustrationTracker (Gap #20)"""
import pytest
from src.nlp.emotion_detector import EmotionDetector, Emotion, EmotionResult
from src.nlp.frustration_tracker import FrustrationTracker


@pytest.fixture
def detector():
    return EmotionDetector(frustration_threshold=0.6)


@pytest.fixture
def tracker():
    return FrustrationTracker(session_id="test_session")


class TestTextEmotionAnalysis:
    def test_joy_detected(self, detector):
        result = detector.detect_emotion("Estoy muy feliz, excelente servicio")
        assert result.primary_emotion == Emotion.JOY

    def test_anger_detected(self, detector):
        result = detector.detect_emotion("Estoy furioso, esto es inaceptable e insoportable")
        assert result.primary_emotion == Emotion.ANGER

    def test_neutral_when_no_keywords(self, detector):
        result = detector.detect_emotion("necesito informacion sobre mi cuenta")
        assert result.primary_emotion == Emotion.NEUTRAL

    def test_sadness_detected(self, detector):
        result = detector.detect_emotion("me siento muy triste y desanimado, que pena")
        assert result.primary_emotion == Emotion.SADNESS

    def test_confidence_between_0_and_1(self, detector):
        result = detector.detect_emotion("que maravilloso, encantado de hablar con ustedes")
        assert 0.0 <= result.confidence <= 1.0


class TestEmotionResult:
    def test_intensities_has_all_emotions(self, detector):
        result = detector.detect_emotion("texto neutral")
        for emotion in Emotion:
            assert emotion.value in result.intensities

    def test_valence_positive_for_joy(self, detector):
        result = detector.detect_emotion("feliz contento alegre genial maravilloso")
        assert result.valence > 0

    def test_valence_negative_for_anger(self, detector):
        result = detector.detect_emotion("furioso enojado rabia odio molesto")
        assert result.valence < 0

    def test_arousal_range(self, detector):
        result = detector.detect_emotion("cualquier texto")
        assert 0.0 <= result.arousal <= 1.0

    def test_to_dict_keys(self, detector):
        result = detector.detect_emotion("hola")
        d = result.to_dict()
        assert "primary_emotion" in d
        assert "frustration_level" in d
        assert "should_escalate" in d


class TestFrustration:
    def test_frustration_low_for_positive_text(self, detector):
        result = detector.detect_emotion("todo funciona perfectamente, estoy satisfecho")
        assert result.frustration_level < 0.5

    def test_frustration_high_for_negative_text(self, detector):
        result = detector.detect_emotion("esto no funciona nunca, terrible pesimo horrible")
        assert result.frustration_level > 0.0

    def test_should_escalate_when_frustrated(self, detector):
        result = detector.detect_emotion(
            "furioso inaceptable insoportable, no funciona, imposible, estoy harto de esto"
        )
        if result.frustration_level >= detector.frustration_threshold:
            assert result.should_escalate is True

    def test_is_frustrated_method(self, detector):
        result = detector.detect_emotion("texto normal")
        is_frustrated = detector.is_frustrated(result)
        assert isinstance(is_frustrated, bool)


class TestEmotionHistory:
    def test_history_grows(self, detector):
        for text in ["feliz", "triste", "enojado"]:
            detector.detect_emotion(text)
        assert len(detector.emotion_history) == 3

    def test_history_capped_at_100(self, detector):
        for i in range(110):
            detector.detect_emotion(f"texto {i}")
        assert len(detector.emotion_history) <= 100

    def test_trend_insufficient_data(self, detector):
        trend = detector.get_emotion_trend()
        assert trend == "insufficient_data"

    def test_statistics_structure(self, detector):
        for _ in range(5):
            detector.detect_emotion("texto de prueba")
        stats = detector.get_statistics()
        assert "total_detections" in stats
        assert "emotion_distribution" in stats
        assert "avg_frustration" in stats


class TestAudioFeatures:
    def test_audio_features_combined(self, detector):
        audio = {"pitch": 0.8, "energy": 0.9, "speech_rate": 1.3}
        result = detector.detect_emotion("Que bueno", audio_features=audio)
        assert isinstance(result, EmotionResult)

    def test_without_audio_features(self, detector):
        result = detector.detect_emotion("hola")
        assert isinstance(result, EmotionResult)


class TestFrustrationTracker:
    def test_initial_level_zero(self, tracker):
        assert tracker.get_current_level() == 0.0

    def test_update_returns_summary(self, tracker):
        summary = tracker.update(0.3, "problema con servicio")
        assert summary is not None
        assert summary.session_id == "test_session"

    def test_escalation_phrase_increases_level(self, tracker):
        summary = tracker.update(0.0, "quiero hablar con un humano ya")
        assert summary.current_level > 0.0

    def test_high_frustration_triggers_escalate(self, tracker):
        for _ in range(5):
            tracker.update(0.8, "esto no funciona nunca jamas")
        summary = tracker.get_summary()
        assert summary.should_escalate is True

    def test_trend_escalating(self, tracker):
        for i in range(6):
            tracker.update(0.1 + i * 0.15)
        summary = tracker.get_summary()
        assert summary.trend in ("escalating", "stable", "insufficient_data", "decreasing")

    def test_history_grows(self, tracker):
        for _ in range(3):
            tracker.update(0.2)
        history = tracker.get_history()
        assert len(history) == 3

    def test_reset_reduces_level(self, tracker):
        for _ in range(5):
            tracker.update(0.9)
        before = tracker.get_current_level()
        tracker.reset()
        assert tracker.get_current_level() < before
