"""Tests para SpeakerVerification (Gap #18)"""
import pytest
from src.security.speaker_verification import SpeakerVerification


@pytest.fixture
def sv():
    return SpeakerVerification()


def make_audio(seed: int = 0) -> bytes:
    """Genera audio sintetico para tests."""
    import struct
    samples = [(seed + i) % 256 for i in range(1024)]
    return struct.pack(f"{len(samples)}B", *samples)


class TestEnrollment:
    def test_enroll_success(self, sv):
        samples = [make_audio(i) for i in range(3)]
        result = sv.enroll_user("user_001", samples)
        assert result is True

    def test_enroll_stores_profile(self, sv):
        samples = [make_audio(i) for i in range(3)]
        sv.enroll_user("user_002", samples)
        assert "user_002" in sv.voice_profiles

    def test_enroll_minimum_samples_required(self, sv):
        samples = [make_audio(0), make_audio(1)]  # solo 2, minimo es 3
        result = sv.enroll_user("user_003", samples)
        assert result is False

    def test_enroll_empty_samples(self, sv):
        result = sv.enroll_user("user_004", [])
        assert result is False

    def test_enroll_sets_locked_false(self, sv):
        samples = [make_audio(i) for i in range(3)]
        sv.enroll_user("user_005", samples)
        assert sv.voice_profiles["user_005"].is_locked is False


class TestVerification:
    def test_verify_enrolled_user(self, sv):
        samples = [make_audio(i) for i in range(5)]
        sv.enroll_user("user_v01", samples)
        verified, score = sv.verify_speaker("user_v01", make_audio(2))
        assert isinstance(verified, bool)
        assert 0.0 <= score <= 1.0

    def test_verify_unknown_user(self, sv):
        verified, score = sv.verify_speaker("user_unknown", make_audio(0))
        assert verified is False
        assert score == 0.0

    def test_verify_increments_count(self, sv):
        samples = [make_audio(i) for i in range(3)]
        sv.enroll_user("user_v02", samples)
        sv.verify_speaker("user_v02", make_audio(0))
        sv.verify_speaker("user_v02", make_audio(1))

    def test_lockout_after_max_failures(self, sv):
        samples = [make_audio(i) for i in range(3)]
        sv.enroll_user("user_v03", samples)
        # Forzar fallos con audio muy diferente
        for _ in range(sv.max_failed_attempts + 1):
            sv.verify_speaker("user_v03", b"\x00" * 128)
        assert sv.voice_profiles["user_v03"].is_locked is True

    def test_locked_user_cannot_verify(self, sv):
        samples = [make_audio(i) for i in range(3)]
        sv.enroll_user("user_v04", samples)
        sv.voice_profiles["user_v04"].is_locked = True
        verified, score = sv.verify_speaker("user_v04", make_audio(2))
        assert verified is False


class TestProfileManagement:
    def test_delete_user(self, sv):
        samples = [make_audio(i) for i in range(3)]
        sv.enroll_user("user_d01", samples)
        result = sv.delete_user("user_d01")
        assert result is True
        assert "user_d01" not in sv.voice_profiles

    def test_delete_nonexistent_user(self, sv):
        result = sv.delete_user("nonexistent")
        assert result is False

    def test_update_voice_profile(self, sv):
        samples = [make_audio(i) for i in range(3)]
        sv.enroll_user("user_u01", samples)
        result = sv.update_voice_profile("user_u01", make_audio(10))
        assert result is True

    def test_get_verification_stats(self, sv):
        samples = [make_audio(i) for i in range(3)]
        sv.enroll_user("user_s01", samples)
        stats = sv.get_verification_stats("user_s01")
        assert stats is not None
        assert "user_id" in stats
        assert "threshold" in stats

    def test_get_stats_unknown_user(self, sv):
        stats = sv.get_verification_stats("unknown")
        assert stats is None
