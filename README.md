# DPI LTM CubeSat — mission website

Static website and mission analyses (power, link, ConOps, NASA DAS debris assessment) for a 1U PROVES Kit
CubeSat flying the AMSAT Linear Transponder Module.

- Live site: https://dudeb310vkbf8.cloudfront.net/
- Build: `python3 build.py` (Python 3.10+, numpy) → `public/`
- Deploy site: `./deploy/deploy.sh` · Deploy chatbot backend: `./deploy/deploy_chat.sh` (run with `PATH=$PWD/.venv/bin:$PATH`)
- 3D mockup: `/mockup.html` · Mission assistant: `/ask.html`
- Notes, sources and assumptions: [NOTES.md](NOTES.md)
