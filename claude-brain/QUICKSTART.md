# Quickstart (the 60-second version)

```sh
# 1. Install Obsidian -> enable "Local REST API" community plugin -> copy API key.

# 2. Install the MCP server.
brew install pipx && pipx ensurepath
pipx install mcp-obsidian

# 3. Run the bootstrap.
./bootstrap.sh

# 4. Fully relaunch Claude Code. Ask: "search my obsidian vault for anything."

# 5. Open a fresh Claude Code session and paste the contents of
#    profile-interview.md to build your personal profile in auto-memory.
```

That's it. See `README.md` for details, `PROFILE-GUIDE.md` for the profile
layer, and the scripts/ folder for the optional extraction pipeline.
