"""
The background update-check fetches the cc repo on (almost) every command. It
must be fully non-interactive so a private/auth'd remote never pops the OS
keychain or blocks on a prompt.
"""
from cc.utils import update_checker


def test_git_env_disables_all_prompts():
    env = update_checker._git_env()
    assert env["GIT_TERMINAL_PROMPT"] == "0"   # no HTTP user/pass prompt
    assert env["GIT_ASKPASS"]                   # askpass yields nothing → no GUI
    assert "BatchMode=yes" in env["GIT_SSH_COMMAND"]  # no SSH passphrase prompt


def test_noprompt_clears_credential_helper():
    # `-c credential.helper=` resets the helper chain → keychain helper can't run.
    assert "credential.helper=" in update_checker._NOPROMPT
    assert "credential.interactive=false" in update_checker._NOPROMPT
