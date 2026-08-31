from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
UI = ROOT / "ui.py"
MARKER = "# v30 SECOND-MATCH CLEANUP PATCH"

def fail(message: str) -> None:
    print()
    print("PATCH NOT APPLIED")
    print(message)
    print()
    input("Press Enter to close...")
    raise SystemExit(1)

if not UI.exists() or not (ROOT / "main.py").exists():
    fail("Put this patch in the same folder as main.py and ui.py.")

text = UI.read_text(encoding="utf-8")

if MARKER in text:
    print()
    print("The v30 Second-Match Cleanup Patch is already applied.")
    print()
    input("Press Enter to close...")
    raise SystemExit(0)

old_finish = '''    def finish_connection(mode: str, peer: SecurePeer, player: int) -> tuple[str, SecurePeer, int]:
        pairing_discovery.close()
        if SOUND is not None:
            SOUND.play("connect")
        return mode, peer, player
'''

new_finish = '''    # v30 SECOND-MATCH CLEANUP PATCH
    def _stop_connect_job(job: Optional[ConnectJob], keep_peer: Optional[SecurePeer] = None) -> None:
        # Stop an unused listener/join job before leaving the lobby.
        # The lobby deliberately keeps its host listener alive while attempting
        # an outgoing JOIN so simultaneous joins can be resolved. Once a
        # connection has actually been chosen, that extra listener must be
        # cancelled or it can keep DEFAULT_ONLINE_PORT bound during the match
        # and block Game 2.
        if job is None:
            return

        job.cancel.set()

        thread = getattr(job, "thread", None)
        if thread is not None and thread.is_alive():
            # Host accept() wakes every 0.25 s, so this gives it time to close
            # the listener and release the port cleanly.
            thread.join(timeout=0.75)

        extra_peer = getattr(job.result, "peer", None)
        if extra_peer is not None and extra_peer is not keep_peer:
            try:
                extra_peer.close()
            except Exception:
                pass

    def _cleanup_online_lobby(keep_peer: Optional[SecurePeer] = None) -> None:
        pairing_discovery.close()
        _stop_connect_job(host_job, keep_peer)
        _stop_connect_job(joining_job, keep_peer)

    def finish_connection(mode: str, peer: SecurePeer, player: int) -> tuple[str, SecurePeer, int]:
        # Critical Game-2 fix: when we JOIN somebody else, our own host listener
        # was previously left running in the background. Stop all unused lobby
        # jobs but preserve the one SecurePeer selected for the match.
        _cleanup_online_lobby(peer)
        if SOUND is not None:
            SOUND.play("connect")
        return mode, peer, player
'''

if old_finish not in text:
    fail(
        "Could not find the expected online-lobby finish_connection block. "
        "This patch expects the v30/v30-patched ui.py."
    )

text = text.replace(old_finish, new_finish, 1)

old_quit = '''            if event.type == pygame.QUIT:
                host_job.cancel.set()
                if joining_job:
                    joining_job.cancel.set()
                pairing_discovery.close()
                return None
'''
new_quit = '''            if event.type == pygame.QUIT:
                _cleanup_online_lobby()
                return None
'''
if old_quit not in text:
    fail("Could not find the expected online-lobby QUIT cleanup block.")
text = text.replace(old_quit, new_quit, 1)

old_escape = '''            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                host_job.cancel.set()
                if joining_job:
                    joining_job.cancel.set()
                pairing_discovery.close()
                return None
'''
new_escape = '''            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                _cleanup_online_lobby()
                return None
'''
if old_escape not in text:
    fail("Could not find the expected online-lobby ESC cleanup block.")
text = text.replace(old_escape, new_escape, 1)

needle = '''    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        for event in game_events():
'''
replacement = '''    while running:
        # If the remote endpoint is gone, finish this online session cleanly.
        # Local/CPU modes return earlier and never reach this loop.
        if peer is not None and not peer.alive:
            running = False
            break

        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        for event in game_events():
'''

online_anchor = '    session = RollbackSession(local_player, peer, is_host=(mode == "host"))'
anchor_pos = text.find(online_anchor)
if anchor_pos < 0:
    fail("Could not locate the online match loop.")

loop_pos = text.find(needle, anchor_pos)
if loop_pos < 0:
    fail("Could not locate the online match loop body.")

text = text[:loop_pos] + text[loop_pos:].replace(needle, replacement, 1)

backup = UI.with_name(UI.name + ".before_second_match_patch")
if not backup.exists():
    shutil.copy2(UI, backup)

UI.write_text(text, encoding="utf-8")

try:
    compile(text, str(UI), "exec")
except Exception as exc:
    shutil.copy2(backup, UI)
    fail(f"Syntax check failed; ui.py was restored: {exc}")

print()
print("==========================================")
print(" v30 SECOND-MATCH CLEANUP PATCH APPLIED")
print("==========================================")
print()
print("Fixed:")
print("  - unused host listener is cancelled after JOIN")
print("  - lobby waits for old listener to release the port")
print("  - unused simultaneous-join peer is closed")
print("  - dead online matches return cleanly")
print()
print("This does NOT change TCP/TLS, rollback, physics, controls,")
print("story mode, protocol 29, or the 30-frame input buffer.")
print()
print("Both players should apply it.")
print()
print("Backup created:")
print("  ui.py.before_second_match_patch")
print()
print("Test:")
print("  Game 1 -> both return to menu -> Game 2 without restarting")
print()
input("Press Enter to close...")
