from __future__ import annotations

import asyncio
import queue
import threading

from .rag import RagEngine
from .storage import Storage


class AdminCli:
    def __init__(self, storage: Storage, rag: RagEngine, disconnect, cancel_pending=None):
        self.storage = storage
        self.rag = rag
        self.disconnect = disconnect
        self.cancel_pending = cancel_pending

    async def run(self) -> None:
        print("Admin CLI aktif. Ketik 'help' untuk daftar perintah.")
        commands: queue.Queue[str | None] = queue.Queue()

        def reader() -> None:
            while True:
                try:
                    commands.put(input("ai-admin> "))
                except (EOFError, KeyboardInterrupt):
                    commands.put(None)
                    return

        threading.Thread(target=reader, name="admin-input", daemon=True).start()
        while True:
            while True:
                try:
                    raw = commands.get_nowait()
                    break
                except queue.Empty:
                    await asyncio.sleep(0.1)
            if raw is None:
                return
            command = raw.strip().split()
            if not command:
                continue
            try:
                if command[0] == "help":
                    print(
                        "list-chats                — lihat semua chat dan statusnya\n"
                        "chat-enable               — aktifkan balasan otomatis untuk semua DM\n"
                        "chat-disable              — hentikan semua balasan otomatis\n"
                        "enable-chat <CHAT_ID>     — aktifkan AI untuk chat tersebut\n"
                        "disable-chat <CHAT_ID>    — nonaktifkan AI untuk chat tersebut\n"
                        "pause-chat <CHAT_ID>      — jeda sementara (gunakan resume-chat untuk lanjut)\n"
                        "resume-chat <CHAT_ID>     — lanjutkan setelah pause-chat\n"
                        "set-delay <DETIK>         — ubah delay balasan AI\n"
                        "reindex                   — indeks ulang knowledge\n"
                        "exit                      — matikan aplikasi"
                    )
                elif command[0] in {"chat-enable", "chat-disable"} and len(command) == 1:
                    self.storage.set_global_enabled(command[0] == "chat-enable")
                    if command[0] == "chat-disable" and self.cancel_pending:
                        await self.cancel_pending()
                    print("OK — AI global " + ("aktif" if self.storage.global_enabled() else "nonaktif"))
                elif command[0] == "list-chats":
                    print("AI global: " + ("aktif" if self.storage.global_enabled() else "nonaktif"))
                    rows = self.storage.list_chats()
                    if not rows:
                        print("Belum ada chat yang tercatat.")
                    for row in rows:
                        enabled = "aktif" if row["ai_enabled"] else "nonaktif"
                        print(
                            f"chat_id={row['chat_id']}  ai={enabled}"
                            f"  state={row['state']}  updated={row['updated_at']}"
                        )
                elif command[0] == "enable-chat" and len(command) == 2:
                    self.storage.set_chat_enabled(int(command[1]), True)
                    print("OK")
                elif command[0] == "disable-chat" and len(command) == 2:
                    self.storage.set_chat_enabled(int(command[1]), False)
                    print("OK")
                elif command[0] == "set-delay" and len(command) == 2:
                    self.storage.set_delay(int(command[1]))
                    print("OK")
                elif command[0] == "pause-chat" and len(command) == 2:
                    self.storage.human_handoff(int(command[1]), "ADMIN_PAUSED")
                    print("OK")
                elif command[0] == "resume-chat" and len(command) == 2:
                    self.storage.resume(int(command[1]))
                    print("OK")
                elif command[0] == "reindex":
                    print(f"{self.rag.reindex()} chunk diindeks")
                elif command[0] == "exit":
                    await self.disconnect()
                    return
                else:
                    print("Perintah tidak dikenal. Ketik help.")
            except (ValueError, IndexError) as exc:
                print(f"Input tidak valid: {exc}")
