# RD: One-Time Disable pada Manual Reply

## Ringkasan

Setelah pemilik akun membalas DM secara manual, AI untuk chat tersebut otomatis
dinonaktifkan permanen. Pemilik harus menjalankan `enable-chat` ulang dari CLI
jika ingin AI aktif kembali untuk chat tersebut.

## Motivasi

- Menghindari balasan AI yang tidak relevan setelah percakapan manual diteruskan.
- Jika user offline lagi setelah reply, AI tidak ikut campur kecuali pemilik
  secara eksplisit mengaktifkannya kembali.
- Kontrol lebih jelas: pemilik memutuskan sendiri kapan AI terlibat lagi.

## Perubahan Behavior

### Sebelumnya

| Langkah | State |
|---------|-------|
| Pesan masuk → delay → AI jawab | `AI_ACTIVE` |
| Pemilik reply manual | `HUMAN_ACTIVE` (pause) |
| Pesan baru dari user | Tidak diproses |
| Lanjut AI | `resume-chat <ID>` dari CLI |

### Sesudahnya

| Langkah | State |
|---------|-------|
| Pesan masuk → delay → AI jawab | `AI_ACTIVE` |
| Pemilik reply manual | `AI_DISABLED`, `ai_enabled=0` |
| Pesan baru dari user | Tidak diproses |
| Lanjut AI | `enable-chat <ID>` dari CLI (bukan `resume-chat`) |

## Perubahan Kode

### `app/storage.py` — `human_handoff()`

Tambahkan parameter `disable_ai`:

```python
def human_handoff(
    self, chat_id: int,
    event_type: str = "HUMAN_REPLY_DISABLED",
    disable_ai: bool = False,
) -> None:
    state = ConversationState.AI_DISABLED if disable_ai else ConversationState.HUMAN_ACTIVE
    with self._lock, self._db:
        self.ensure_chat(chat_id)
        self._db.execute(
            "UPDATE conversations SET state=?,ai_enabled=?,last_manual_reply_at=?,"
            "message_version=message_version+1,updated_at=? WHERE chat_id=?",
            (state, 0 if disable_ai else 1, now(), now(), chat_id),
        )
        self._clear_chat_locked(chat_id)
        self.audit(chat_id, event_type)
```

> Pemanggil yang memakai `disable_ai=False` (default) tidak terpengaruh.

### `app/service.py` — `manual_reply()`

```python
def manual_reply(self, chat_id: int) -> None:
    self.cancel(chat_id)
    self.storage.human_handoff(chat_id, disable_ai=True)
```

### `app/admin.py` — `resume-chat`

Perintah `resume-chat` tidak lagi relevan untuk kasus manual reply karena state
sudah `AI_DISABLED`. Tetap pertahankan perintah ini untuk kasus `pause-chat`
(ADMIN_PAUSED), namun perbarui output `help` untuk memperjelas perbedaannya:

```text
pause-chat <CHAT_ID>   — jeda sementara (resume-chat untuk lanjut)
resume-chat <CHAT_ID>  — lanjutkan setelah pause-chat
enable-chat <CHAT_ID>  — aktifkan ulang AI (diperlukan setelah manual reply)
```

## Tes yang Perlu Ditambahkan

| Nama tes | Skenario |
|----------|----------|
| `test_manual_reply_disables_ai_permanently` | Pemilik reply → `ai_enabled=0`, state=`AI_DISABLED` |
| `test_ai_does_not_reply_after_manual_reply` | Pesan baru masuk setelah manual reply → tidak ada balasan AI |
| `test_enable_chat_restores_ai_after_manual_reply` | `enable-chat` → AI aktif kembali untuk pesan baru |
| `test_resume_chat_does_not_restore_after_manual_reply` | `resume-chat` setelah manual reply → state tetap `AI_DISABLED` |
| `test_admin_pause_still_uses_resume` | `pause-chat` + `resume-chat` → tetap berjalan normal |

## Audit

Event yang dicatat di tabel `audit_events`:

| Kondisi | `event_type` |
|---------|--------------|
| Manual reply (baru) | `HUMAN_REPLY_DISABLED` |
| Admin pause | `ADMIN_PAUSED` |

## Dampak

- `resume-chat` hanya relevan untuk `ADMIN_PAUSED`, bukan untuk manual reply.
- Pemilik perlu mengingat bahwa setelah membalas secara manual, AI mati dan
  harus diaktifkan ulang dengan `enable-chat`.
- README perlu diperbarui untuk menjelaskan behavior baru ini.

## File yang Diubah

```text
app/storage.py
app/service.py
app/admin.py         (update help text)
tests/test_service.py
tests/test_storage.py
README.md
```
