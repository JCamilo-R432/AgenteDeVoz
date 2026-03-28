"""Tests para Gap #10: Call Recording."""
import pytest
from src.recording.call_recording import CallRecordingManager, RecordingStatus
from src.recording.secure_storage import SecureRecordingStorage
from src.recording.consent_recording import ConsentRecordingManager
from src.recording.recording_retention import (
    RecordingRetentionManager,
    RetentionPolicy,
)
from datetime import datetime, timedelta


class TestCallRecordingManager:
    @pytest.fixture
    def manager(self):
        return CallRecordingManager(storage_path="/tmp/recordings", retention_days=90)

    def test_request_consent_spanish(self, manager):
        msg = manager.request_consent("session1", language="es")
        assert "grabar" in msg.lower() or "grabada" in msg.lower()

    def test_request_consent_english(self, manager):
        msg = manager.request_consent("session1", language="en")
        assert "record" in msg.lower()

    def test_process_consent_affirmative(self, manager):
        result = manager.process_consent_response("session1", "si", language="es")
        assert result is True

    def test_process_consent_negative(self, manager):
        result = manager.process_consent_response("session2", "no", language="es")
        assert result is False

    def test_start_recording_with_consent(self, manager):
        rec = manager.start_recording("session3", "user1", consent_obtained=True)
        assert rec is not None
        assert rec.status == RecordingStatus.RECORDING

    def test_start_recording_without_consent_returns_none(self, manager):
        rec = manager.start_recording("session4", "user2", consent_obtained=False)
        assert rec is None

    def test_stop_recording(self, manager):
        rec = manager.start_recording("session5", "user3", consent_obtained=True)
        assert rec is not None
        stopped = manager.stop_recording(rec.recording_id)
        assert stopped.status == RecordingStatus.COMPLETED

    def test_pause_and_resume(self, manager):
        rec = manager.start_recording("session6", "user4", consent_obtained=True)
        paused = manager.pause_recording(rec.recording_id)
        assert paused is True
        resumed = manager.resume_recording(rec.recording_id)
        assert resumed is True

    def test_delete_recording(self, manager):
        rec = manager.start_recording("session7", "user5", consent_obtained=True)
        deleted = manager.delete_recording(rec.recording_id, reason="gdpr_erasure")
        assert deleted is True
        rec2 = manager.get_recording(rec.recording_id)
        assert rec2.status == RecordingStatus.DELETED

    def test_get_stats(self, manager):
        manager.start_recording("s8", "u6", consent_obtained=True)
        manager.start_recording("s9", "u7", consent_obtained=False)
        stats = manager.get_stats()
        assert stats["total_recordings"] >= 1

    def test_get_session_recordings(self, manager):
        rec = manager.start_recording("session_unique", "u8", consent_obtained=True)
        recs = manager.get_session_recordings("session_unique")
        assert len(recs) == 1

    def test_consent_affirmatives_english(self, manager):
        for word in ["yes", "ok", "sure"]:
            result = manager.process_consent_response("s", word, language="en")
            assert result is True

    def test_recording_has_file_path(self, manager):
        rec = manager.start_recording("s10", "u9", consent_obtained=True)
        assert rec.file_path is not None
        assert ".enc" in rec.file_path

    def test_recording_duration_after_stop(self, manager):
        rec = manager.start_recording("s11", "u10", consent_obtained=True)
        stopped = manager.stop_recording(rec.recording_id)
        assert stopped.duration_seconds >= 0


class TestSecureRecordingStorage:
    @pytest.fixture
    def storage(self):
        import os
        key = os.urandom(32)
        return SecureRecordingStorage(encryption_key=key)

    def test_encrypt_returns_bytes(self, storage):
        data = b"Hello voice recording"
        encrypted = storage.encrypt(data)
        assert isinstance(encrypted, bytes)
        assert encrypted != data

    def test_encrypt_decrypt_roundtrip(self, storage):
        data = b"Test audio data 1234567890"
        encrypted = storage.encrypt(data, metadata="test")
        decrypted = storage.decrypt(encrypted, metadata="test")
        assert decrypted == data

    def test_encrypted_has_magic_header(self, storage):
        data = b"audio"
        encrypted = storage.encrypt(data)
        assert encrypted[:6] == b"AVREC1"

    def test_checksum(self, storage):
        data = b"important audio"
        checksum = storage.compute_checksum(data)
        assert isinstance(checksum, str)
        assert len(checksum) == 64

    def test_verify_checksum(self, storage):
        data = b"audio data"
        checksum = storage.compute_checksum(data)
        assert storage.verify_checksum(data, checksum) is True
        assert storage.verify_checksum(b"different", checksum) is False

    def test_invalid_key_length_raises(self):
        with pytest.raises(ValueError):
            SecureRecordingStorage(encryption_key=b"short")

    def test_decrypt_invalid_format_raises(self, storage):
        with pytest.raises(ValueError):
            storage.decrypt(b"invalid_format_data")


class TestConsentRecordingManager:
    @pytest.fixture
    def manager(self):
        return ConsentRecordingManager()

    def test_record_consent(self, manager):
        evidence = manager.record_consent(
            session_id="s1", user_id="u1", granted=True,
            language="es", user_response="si", ip_address="192.168.1.1",
        )
        assert evidence.consent_id.startswith("CONS-")
        assert evidence.granted is True

    def test_immutable_hash_generated(self, manager):
        evidence = manager.record_consent("s2", "u2", True, "es", "acepto")
        assert evidence.immutable_hash is not None
        assert len(evidence.immutable_hash) == 64

    def test_hash_chain(self, manager):
        e1 = manager.record_consent("s3", "u3", True, "es", "si")
        e2 = manager.record_consent("s4", "u4", False, "en", "no")
        assert e1.immutable_hash != e2.immutable_hash

    def test_verify_consent(self, manager):
        evidence = manager.record_consent("s5", "u5", True, "es", "si")
        found = manager.verify_consent(evidence.consent_id)
        assert found is not None

    def test_get_session_consent(self, manager):
        manager.record_consent("session_x", "u6", True, "es", "si")
        found = manager.get_session_consent("session_x")
        assert found is not None
        assert found.session_id == "session_x"

    def test_export_audit_trail(self, manager):
        manager.record_consent("s6", "u7", True, "es", "si")
        trail = manager.export_audit_trail()
        assert len(trail) >= 1
        assert "consent_id" in trail[0]

    def test_record_consent_with_audio(self, manager):
        audio = b"fake_audio_bytes"
        evidence = manager.record_consent("s7", "u8", True, "es", "si", audio_bytes=audio)
        assert evidence.audio_fingerprint != "no_audio"


class TestRecordingRetentionManager:
    @pytest.fixture
    def manager(self):
        return RecordingRetentionManager()

    def test_default_policies_loaded(self, manager):
        assert manager.get_policy("standard") is not None
        assert manager.get_policy("legal_hold") is not None

    def test_standard_policy_90_days(self, manager):
        policy = manager.get_policy("standard")
        assert policy.retention_days == 90

    def test_legal_hold_no_auto_delete(self, manager):
        policy = manager.get_policy("legal_hold")
        assert policy.auto_delete is False

    def test_is_expired_old_recording(self, manager):
        old_date = datetime.now() - timedelta(days=100)
        assert manager.is_expired(old_date, "standard") is True

    def test_is_not_expired_recent_recording(self, manager):
        recent_date = datetime.now() - timedelta(days=10)
        assert manager.is_expired(recent_date, "standard") is False

    def test_run_retention_check(self, manager):
        recordings = [
            {"id": "R001", "recorded_at": (datetime.now() - timedelta(days=100)).isoformat(), "policy": "standard"},
            {"id": "R002", "recorded_at": datetime.now().isoformat(), "policy": "standard"},
        ]
        result = manager.run_retention_check(recordings)
        assert result["checked"] == 2
        assert "R001" in result["deleted_ids"]
        assert "R002" not in result["deleted_ids"]

    def test_run_retention_legal_hold_not_deleted(self, manager):
        recordings = [
            {"id": "L001", "recorded_at": (datetime.now() - timedelta(days=2000)).isoformat(), "policy": "legal_hold"},
        ]
        result = manager.run_retention_check(recordings)
        assert "L001" not in result["deleted_ids"]

    def test_should_notify_expiry(self, manager):
        notify_date = datetime.now() - timedelta(days=85)  # 5 dias antes de expirar (90d policy)
        assert manager.should_notify_expiry(notify_date, "standard") is True

    def test_add_custom_policy(self, manager):
        policy = RetentionPolicy("custom", 180, ["custom_type"])
        manager.add_policy(policy)
        assert manager.get_policy("custom") is not None

    def test_list_policies(self, manager):
        policies = manager.list_policies()
        assert len(policies) >= 4

    def test_deletion_log(self, manager):
        recordings = [
            {"id": "X001", "recorded_at": (datetime.now() - timedelta(days=100)).isoformat(), "policy": "standard"},
        ]
        manager.run_retention_check(recordings)
        log = manager.get_deletion_log()
        assert len(log) >= 1
