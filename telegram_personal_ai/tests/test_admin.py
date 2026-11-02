import asyncio

from app.admin import AdminCli
from app.rag import RagEngine


def test_global_commands_without_chat_id(storage, tmp_path, monkeypatch, capsys):
    storage.set_chat_enabled(1, False)
    commands = iter(["chat-disable", "list-chats", "chat-enable", "exit"])
    def read_command(prompt):
        command = next(commands, None)
        if command is None:
            raise EOFError
        return command

    monkeypatch.setattr("builtins.input", read_command)
    disconnected = []

    async def disconnect():
        disconnected.append(True)

    asyncio.run(AdminCli(storage, RagEngine(storage, tmp_path), disconnect).run())
    output = capsys.readouterr().out
    assert "AI global: nonaktif" in output
    assert "AI global aktif" in output
    assert storage.global_enabled()
    assert storage.conversation(1)["ai_enabled"] == 0
    assert disconnected
