FROM python:3.12-slim

RUN apt-get update && apt-get install -y git postgresql-client zsh sqlite3 && rm -rf /var/lib/apt/lists/*

# Create a user with zsh
RUN useradd -m -s /bin/zsh devuser
USER devuser
WORKDIR /home/devuser

# Simulate an Odoo directory structure with odoo-bin
RUN mkdir -p ~/odoo/17/odoo ~/odoo/17/enterprise ~/odoo/17/design-themes ~/odoo/17/stack/addons \
    && mkdir -p ~/odoo/18/odoo ~/odoo/18/enterprise ~/odoo/18/design-themes ~/odoo/18/stack/addons \
    && mkdir -p ~/odoo/19/odoo ~/odoo/19/enterprise ~/odoo/19/design-themes \
    && touch ~/odoo/17/odoo/odoo-bin ~/odoo/18/odoo/odoo-bin ~/odoo/19/odoo/odoo-bin \
    && chmod +x ~/odoo/17/odoo/odoo-bin ~/odoo/18/odoo/odoo-bin ~/odoo/19/odoo/odoo-bin

# Init git repos so branch detection works
RUN cd ~/odoo/17/odoo && git init && git checkout -b 17.0 \
    && cd ~/odoo/18/odoo && git init && git checkout -b 18.0 \
    && cd ~/odoo/19/odoo && git init && git checkout -b 19.0

# Simulate an old pip install
RUN python3 -m pip install --user --break-system-packages rich 2>/dev/null || true

# Simulate old cc install: fake binary, old shell integration, old .zshrc entries
RUN mkdir -p ~/.local/bin ~/.cc-cli/shell \
    && echo '#!/bin/bash' > ~/.local/bin/_cc_internal \
    && echo 'echo "OLD CC v3.1.0"' >> ~/.local/bin/_cc_internal \
    && chmod +x ~/.local/bin/_cc_internal \
    && printf 'function cc() {\n  /home/devuser/.local/bin/_cc_internal "$@"\n}\n' > ~/.cc-cli/shell/cc.zsh

RUN echo '# existing zshrc stuff' > ~/.zshrc \
    && echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc \
    && echo 'source "/home/devuser/.cc-cli/shell/cc.zsh"  # cc shell integration' >> ~/.zshrc \
    && echo '/home/devuser/.local/bin/_cc_internal stat -s 2>/dev/null  # cc status' >> ~/.zshrc \
    && echo '# other user stuff' >> ~/.zshrc

COPY --chown=devuser:devuser . /home/devuser/cc
