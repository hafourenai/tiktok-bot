from app.models import ConversationState


def test_consent_is_persistent_and_revoke_clears_buffer(storage):
    storage.set_consent(101, True)
    version = storage.buffer_message(101, 1, "pesan rahasia", 5)
    assert version == 2
    assert storage.conversation(101)["state"] == ConversationState.WAITING

    storage.set_consent(101, False)
    row = storage.conversation(101)
    assert row["consent_status"] == 0
    assert row["state"] == ConversationState.AI_DISABLED
    assert storage.messages(101, 100) == ""


def test_old_job_cannot_send_after_manual_reply(storage):
    storage.set_consent(7, True)
    version = storage.buffer_message(7, 10, "halo", 5)
    job = storage.create_job(7, version, "2099-01-01T00:00:00+00:00")
    assert storage.claim_job(job, 7, version)
    storage.human_handoff(7)
    assert not storage.can_send(job, 7, version)
    assert storage.conversation(7)["state"] == ConversationState.HUMAN_ACTIVE


def test_duplicate_message_is_not_buffered_twice(storage):
    storage.set_consent(3, True)
    storage.buffer_message(3, 4, "satu", 5)
    storage.buffer_message(3, 4, "satu", 5)
    assert storage.messages(3, 100) == "satu"
    assert storage.is_duplicate_message(3, 4, "satu")


def test_deleted_message_invalidates_job(storage):
    storage.set_consent(9, True)
    version = storage.buffer_message(9, 11, "hapus saya", 5)
    job = storage.create_job(9, version, "2099-01-01T00:00:00+00:00")
    assert storage.delete_messages(9, [11])
    assert not storage.claim_job(job, 9, version)
    assert storage.messages(9, 100) == ""
