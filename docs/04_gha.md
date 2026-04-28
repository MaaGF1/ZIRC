<!-- docs/04_gha.md -->

# GitHub Action Mechanic

This Document show the architecture and design of `src/gha` which allow you run the demo of `gflzirc` via **GitHub Action (GHA)** not only on local PC.

Alternatively, we provided another bash file -- `gfl_farm.sh` -- to allow you call "GHA" on your own server not only via GHA.

## 1. Design Logic

We design all GHA workflow based on **Let it wrong**, simply, we **DO NOT** take and boundary checks while let game server throw error code like: `Error: Unexpected plaintext response`, which makes our architecture simpler and clearer.

The project architecture is as follows:

```sh
# workflow 
.github/workflows/gfl_farm.yml
# or bash
.gfl_farm.sh

# Python
src/gha/.
├── agent.py
├── missions
│   ├── base.py
│   ├── epa.py
│   ├── f2p_pr.py
│   ├── f2p.py
│   ├── __init__.py
│   ├── pick_and_train.py
│   └── pick_coin.py
├── parser
│   ├── base.py
│   ├── coin.py
│   ├── index_to_epa.py
│   ├── __init__.py
│   └── skill.py
└── request
    ├── base.py
    ├── index.py
    └── __init__.py
```

### 1.1 agent.py

This class is the "entrance" of the farm workflow, it accepts the user's task selections and configures them into the environment.

TODO

### 1.2 missions

TODO

### 1.3 parser

TODO

### 1.4 request

TODO

