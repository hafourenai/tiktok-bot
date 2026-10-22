from __future__ import annotations

import asyncio
import queue
import threading

from .rag import RagEngine
from .storage import Storage


class AdminCli:
    def __init__(self, storage: Storage, rag: RagEngine, disconnect):
        self.storage = storage
        self.rag = rag
        self.disconnect = disconnect

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
                    print("status | enable | disable | set-delay N | list-chats | pause-chat ID | resume-chat ID | reindex | exit")
                elif command[0] == "status":
                    print(f"enabled={self.storage.global_enabled()}")
                elif command[0] in {"enable", "disable"}:
                    self.storage.set_global(command[0] == "enable")
                    print("OK")
                elif command[0] == "set-delay" and len(command) == 2:
                    self.storage.set_delay(int(command[1]))
                    print("OK")
                elif command[0] == "list-chats":
                    for row in self.storage.list_chats():
                        print(dict(row))
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
