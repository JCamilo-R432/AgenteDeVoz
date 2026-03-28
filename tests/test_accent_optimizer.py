"""Tests para AccentOptimizer (Gap #17)"""
import pytest
from src.speech.accent_optimizer import AccentOptimizer, RegionalAccent, AccentProfile


@pytest.fixture
def optimizer():
    return AccentOptimizer()


class TestAccentDetection:
    def test_detect_colombia(self, optimizer):
        features = {"transcribed_words": ["parce", "chévere"]}
        result = optimizer.detect_accent(features)
        assert result == RegionalAccent.COLOMBIA

    def test_detect_argentina(self, optimizer):
        features = {"transcribed_words": ["che", "boludo"]}
        result = optimizer.detect_accent(features)
        assert result == RegionalAccent.ARGENTINA

    def test_detect_mexico(self, optimizer):
        features = {"transcribed_words": ["órale", "chido"]}
        result = optimizer.detect_accent(features)
        assert result == RegionalAccent.MEXICO

    def test_detect_spain(self, optimizer):
        features = {"transcribed_words": ["tío", "guay"]}
        result = optimizer.detect_accent(features)
        assert result == RegionalAccent.SPAIN

    def test_detect_default_no_words(self, optimizer):
        features = {"transcribed_words": []}
        result = optimizer.detect_accent(features)
        assert result == RegionalAccent.DEFAULT

    def test_detect_default_unknown_words(self, optimizer):
        features = {"transcribed_words": ["xyz", "abc"]}
        result = optimizer.detect_accent(features)
        assert result == RegionalAccent.DEFAULT


class TestAccentProfiles:
    def test_all_profiles_loaded(self, optimizer):
        assert len(optimizer.accent_profiles) >= 4

    def test_colombia_profile_has_phonetic_variations(self, optimizer):
        profile = optimizer.accent_profiles[RegionalAccent.COLOMBIA]
        assert isinstance(profile.phonetic_variations, dict)
        assert len(profile.phonetic_variations) > 0

    def test_colombia_confidence_threshold(self, optimizer):
        profile = optimizer.accent_profiles[RegionalAccent.COLOMBIA]
        assert 0.0 < profile.confidence_threshold <= 1.0

    def test_argentina_has_sheismo(self, optimizer):
        profile = optimizer.accent_profiles[RegionalAccent.ARGENTINA]
        assert "ll" in profile.phonetic_variations

    def test_profile_speech_rate_factor_range(self, optimizer):
        for accent, profile in optimizer.accent_profiles.items():
            assert 0.5 <= profile.speech_rate_factor <= 1.5


class TestSpeechRateAdaptation:
    def test_normal_rate(self, optimizer):
        factor = optimizer.adapt_to_speech_rate(audio_duration=10.0, expected_duration=10.0)
        assert factor == pytest.approx(1.0)

    def test_slow_speech(self, optimizer):
        factor = optimizer.adapt_to_speech_rate(audio_duration=15.0, expected_duration=10.0)
        assert factor < 1.0

    def test_fast_speech(self, optimizer):
        factor = optimizer.adapt_to_speech_rate(audio_duration=5.0, expected_duration=10.0)
        assert factor > 1.0

    def test_factor_clamped_min(self, optimizer):
        factor = optimizer.adapt_to_speech_rate(audio_duration=100.0, expected_duration=1.0)
        assert factor >= 0.5

    def test_factor_clamped_max(self, optimizer):
        factor = optimizer.adapt_to_speech_rate(audio_duration=1.0, expected_duration=100.0)
        assert factor <= 2.0

    def test_zero_audio_duration(self, optimizer):
        factor = optimizer.adapt_to_speech_rate(audio_duration=0.0, expected_duration=10.0)
        assert factor == pytest.approx(1.0)


class TestNoisyAudio:
    def test_clean_audio_passthrough(self, optimizer):
        audio = b"\x00" * 1000
        result = optimizer.handle_noisy_audio(audio, snr_db=25.0)
        assert isinstance(result, bytes)

    def test_noisy_audio_returns_bytes(self, optimizer):
        audio = b"\x01\x02\x03" * 100
        result = optimizer.handle_noisy_audio(audio, snr_db=5.0)
        assert isinstance(result, bytes)


class TestAccuracyMetrics:
    def test_returns_dict(self, optimizer):
        metrics = optimizer.get_accuracy_metrics(RegionalAccent.COLOMBIA)
        assert isinstance(metrics, dict)

    def test_has_required_keys(self, optimizer):
        metrics = optimizer.get_accuracy_metrics(RegionalAccent.MEXICO)
        assert "accent" in metrics
        assert "accuracy" in metrics
        assert "wer" in metrics

    def test_wer_range(self, optimizer):
        metrics = optimizer.get_accuracy_metrics(RegionalAccent.ARGENTINA)
        assert 0.0 <= metrics["wer"] <= 1.0
