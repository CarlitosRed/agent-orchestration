# Vendor capability profiles
One file per vendor, each like `vendors/codex.md`: install/auth, a preflight check, the exact non-interactive dispatch command, what's actually been confirmed by a live call versus read from `--help`, and the known failure modes on the desk that tested it.

**Never name a file here `claude.md` (any case).** On a case-insensitive filesystem (Windows, default macOS) that is the same file as `CLAUDE.md`, which Claude Code auto-loads as project instructions - a vendor profile would silently become an instructions file for every session touching this repo. Claude's own profile lives at `claude-code.md` for this reason.
