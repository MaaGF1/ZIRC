<!-- docs/02_gflzirc.md -->

# Interpretation of gflzirc

This document will describe the PyPI packet under `src/core`, namely `gflzirc`, which provides basic API for algorithms, constants, etc. for `src/demo` and `src/gha`.

## 1. Architecture

```sh
.
├── gflzirc                 # Packet Name - gflzirc
│   ├── client.py
│   ├── constants.py
│   ├── crypto.py
│   ├── __init__.py
│   └── proxy.py
├── pyproject.toml          # PyPI's toml file
└── README.md               # Readme of gflzirc
```

