from app.models import ConversationState


def test_enable_chat_sets_ai_enabled(storage):
    storage.set_chat_enabled(101, True)
    row = storage.conversation(101)
    assert row["ai_enabled"] == 1
    assert row["state"] == ConversationState.IDLE


def test_disable_chat_clears_buffer_and_jobs(storage):
    storage.set_chat_enabled(101, True)
    version = storage.buffer_message(101, 1, "pesan rahasia", 5)
    assert version == 2
    assert storage.conversation(101)["state"] == ConversationState.WAITING

    storage.set_chat_enabled(101, False)
    row = storage.conversation(101)
    assert row["ai_enabled"] == 0
    assert row["state"] == ConversationState.AI_DISABLED
    assert storage.messages(101, 100) == ""


def test_old_job_cannot_send_after_manual_reply(storage):
    storage.set_chat_enabled(7, True)
    version = storage.buffer_message(7, 10, "halo", 5)
    job = storage.create_job(7, version, "2099-01-01T00:00:00+00:00")
    assert storage.claim_job(job, 7, version)
    storage.human_handoff(7)
    assert not storage.can_send(job, 7, version)
    assert storage.conversation(7)["state"] == ConversationState.HUMAN_ACTIVE


def test_duplicate_message_is_not_buffered_twice(storage):
    storage.set_chat_enabled(3, True)
    storage.buffer_message(3, 4, "satu", 5)
    storage.buffer_message(3, 4, "satu", 5)
    assert storage.messages(3, 100) == "satu"
    assert storage.is_duplicate_message(3, 4, "satu")


def test_deleted_message_invalidates_job(storage):
    storage.set_chat_enabled(9, True)
    version = storage.buffer_message(9, 11, "hapus saya", 5)
    job = storage.create_job(9, version, "2099-01-01T00:00:00+00:00")
    assert storage.delete_messages(9, [11])
    assert not storage.claim_job(job, 9, version)
    assert storage.messages(9, 100) == ""


def test_resume_restores_idle_when_ai_enabled(storage):
    storage.set_chat_enabled(20, True)
    storage.human_handoff(20, "ADMIN_PAUSED")
    assert storage.conversation(20)["state"] == ConversationState.HUMAN_ACTIVE
    storage.resume(20)
    assert storage.conversation(20)["state"] == ConversationState.IDLE


def test_resume_keeps_disabled_when_ai_not_enabled(storage):
    storage.set_chat_enabled(21, False)
    storage.resume(21)
    assert storage.conversation(21)["state"] == ConversationState.AI_DISABLED


def test_manual_reply_pauses_ai_temporarily(storage):
    """Manual reply mengeset state=HUMAN_ACTIVE, ai_enabled tetap 1."""
    storage.set_chat_enabled(100, True)
    version = storage.buffer_message(100, 1, "pesan", 5)
    job = storage.create_job(100, version, "2099-01-01T00:00:00+00:00")
    assert storage.claim_job(job, 100, version)
    
    # Manual reply
    storage.human_handoff(100, "HUMAN_REPLY")
    row = storage.conversation(100)
    assert row["ai_enabled"] == 1  # tetap enabled
    assert row["state"] == ConversationState.HUMAN_ACTIVE
    assert storage.messages(100, 100) == ""


def test_auto_resume_from_human_active(storage):
    """auto_resume mengubah state dari HUMAN_ACTIVE ke IDLE."""
    storage.set_chat_enabled(101, True)
    storage.human_handoff(101, "HUMAN_REPLY")
    assert storage.conversation(101)["state"] == ConversationState.HUMAN_ACTIVE
    
    # Auto resume
    storage.auto_resume(101)
    row = storage.conversation(101)
    assert row["state"] == ConversationState.IDLE
    assert row["ai_enabled"] == 1  # masih enabled


def test_admin_pause_still_uses_resume(storage):
    """pause-chat dengan resume-chat harus tetap bekerja normal."""
    storage.set_chat_enabled(103, True)
    storage.human_handoff(103, "ADMIN_PAUSED")
    row = storage.conversation(103)
    assert row["state"] == ConversationState.HUMAN_ACTIVE
    assert row["ai_enabled"] == 1  # masih enabled
    
    # resume mengembalikan ke IDLE
    storage.resume(103)
    assert storage.conversation(103)["state"] == ConversationState.IDLE


def test_default_enabled_and_global_switch_persists(storage):
    assert storage.conversation(200)["ai_enabled"] == 1
    assert storage.global_enabled()
    storage.set_global_enabled(False)
    version = storage.buffer_message(200, 1, "halo", 5)
    job = storage.create_job(200, version, "2099-01-01T00:00:00+00:00")
    assert not storage.claim_job(job, 200, version)
    storage.set_global_enabled(True)
    storage.set_chat_enabled(201, False)
    assert storage.conversation(201)["ai_enabled"] == 0


def test_global_disable_invalidates_processing_job(storage):
    version = storage.buffer_message(202, 1, "halo", 5)
    job = storage.create_job(202, version, "2099-01-01T00:00:00+00:00")
    assert storage.claim_job(job, 202, version)
    storage.set_global_enabled(False)
    storage.set_global_enabled(True)
    assert not storage.can_send(job, 202, version)


def test_migration_preserves_owner_disabled_and_enables_unconfigured(storage):
    storage.set_chat_enabled(203, False)
    storage.ensure_chat(204)
    storage._db.execute("UPDATE conversations SET ai_enabled=0,state='AI_DISABLED' WHERE chat_id=204")
    storage._db.commit()
    storage.migrate()
    assert storage.conversation(203)["ai_enabled"] == 0
    assert storage.conversation(204)["ai_enabled"] == 1
    storage.migrate()
    assert storage.conversation(203)["ai_enabled"] == 0
