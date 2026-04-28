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

## 2. How to Config

### 2.1 Actions Secrets and Variables

Since we are running GHA on a **public** repository, we must absolutely avoid hardcoding credentials in the code. We manage configurations and credentials via GitHub Secrets.

#### 2.1.1 Generate Personal Access Token (PAT)

The default `GITHUB_TOKEN` provided by Actions does not have the permission to trigger other workflows (to prevent infinite loops). To enable our "Auto-Respawn" mechanism, you need to generate a PAT:

1. Click your GitHub avatar in the top right corner -> `Settings` -> Scroll to the bottom on the left -> `Developer settings` -> `Personal access tokens` -> `Tokens (classic)`.
2. Click `Generate new token (classic)`.
3. Set a descriptive name (e.g., `GFL_WORKFLOW_PAT`), and select `No expiration` for the expiration time (or customize as needed).
4. **Permissions:** Check the **`repo`** scope (Full control of private repositories).
5. After generating, copy the token string starting with `ghp_xxxxxxxxxxxx`.

#### 2.1.2 Repository Configuration

Next, configure the secrets in your forked repository:

Navigate to: `Repo -> Settings -> Secrets and variables -> Actions -> New repository secret`

Add the following 3 `secrets`:

##### Single Account (Legacy/Standard)

1. **Secret Name:** `GH_PAT`
    - **Value:** `ghp_xxxxxxxxx` (The PAT generated in step 2.1.1).
2. **Secret Name:** `GFL_CONFIG`
    - **Value:**
        ```json
        {
            "USER_UID": "12345678",
            "SERVER_KEY": "M4A1",
            "MACRO_LOOPS": 9999,
            "MISSIONS_PER_RETIRE": 50,
            "SQUAD_ID": 111111,
            "TEAM_ID": 1,
            "EPA_TEAMS": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "EPA_PER_RETIRE": 10
        }
        ```
    - **Parameter Explanations:**
        - `USER_UID`: Your in-game Commander UID.
        - `MACRO_LOOPS`: The master loop count (set extremely high, e.g., 9999, as we rely on time limits to auto-respawn).
        - `MISSIONS_PER_RETIRE`: How many runs before triggering auto-retirement for T-Dolls. Adjust based on your armory's available slots.
        - `SQUAD_ID`: The Heavy Ordnance Corps (HOC) ID used for F2P.
        - `TEAM_ID`: The standard Echelon ID used for PickCoin.
        - `SERVER_KEY`: Server designation (e.g., `"M4A1"` for CN Android Official).
3. **Secret Name:** `GFL_SIGN_KEY`
    - **Value:** The latest `SIGN_KEY` captured via running the `-c` command in the local CLI tool.
4. **Secret Name:** `GFL_USER_DEVICE`
    - **Value:** Your device fingerprint located inside the `micalog` node of the captured payload. It uses the same array slicing logic as the `SIGN_KEY`.

##### Single Account in Array Notation

For consistency, you can also wrap a single account in JSON arrays.

1. Looks like:
    ```json
    [
        {
            "USER_UID": "12345678",
            "SERVER_KEY": "M4A1",
            "MACRO_LOOPS": 9999,
            "MISSIONS_PER_RETIRE": 50,
            "SQUAD_ID": 111111,
            "TEAM_ID": 1,
            "EPA_TEAMS": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "EPA_PER_RETIRE": 10
        }
    ]
    ```
2. Input as:
    ```json
    [ { "USER_UID": "12345678", "SERVER_KEY": "M4A1", "MACRO_LOOPS": 9999, "MISSIONS_PER_RETIRE": 50, "SQUAD_ID": 111111, "TEAM_ID": 1, "EPA_TEAMS": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "EPA_PER_RETIRE": 10 } ]
    ```

##### Multiple Accounts

You can farm multiple accounts simultaneously by passing arrays of configurations.

1. Looks like:
    ```json
    [
        {
            "USER_UID": "12345678",
            "SERVER_KEY": "M4A1",
            "MACRO_LOOPS": 9999,
            "MISSIONS_PER_RETIRE": 50,
            "SQUAD_ID": 111111,
            "TEAM_ID": 1,
            "EPA_TEAMS": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "EPA_PER_RETIRE": 10
        },
        {
            "USER_UID": "12345678",
            "SERVER_KEY": "M4A1",
            "MACRO_LOOPS": 9999,
            "MISSIONS_PER_RETIRE": 50,
            "SQUAD_ID": 111111,
            "TEAM_ID": 1,
            "EPA_TEAMS": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "EPA_PER_RETIRE": 10
        }
    ]
    ```
2. Input as:
    ```json
    [ { "USER_UID": "12345678", "SERVER_KEY": "M4A1", "MACRO_LOOPS": 9999, "MISSIONS_PER_RETIRE": 50, "SQUAD_ID": 111111, "TEAM_ID": 1, "EPA_TEAMS": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "EPA_PER_RETIRE": 10 }, { "USER_UID": "12345678", "SERVER_KEY": "M4A1", "MACRO_LOOPS": 9999, "MISSIONS_PER_RETIRE": 50, "SQUAD_ID": 111111, "TEAM_ID": 1, "EPA_TEAMS": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "EPA_PER_RETIRE": 10 } ]
    ```

### 2.2 Let's run it

1. Login to the GFL game on your device and finish your daily routine.
2. Run the local proxy tool to capture a **fresh** `SIGN_KEY`.
3. On the GitHub repo, go to `Settings -> Secrets` and update the value of `GFL_SIGN_KEY`.
4. Go to the `Actions` tab and select `GFL Auto Farm Workflow` from the left sidebar.
5. Click the `Run workflow` dropdown menu on the right, select your target branch, choose `f2p` or `pick_coin`, and click the green run button.
6. **Real-time Monitoring:** By clicking on the running Job, you can open the **Summary** page (top left corner or bottom of the log screen) at any time. It dynamically generates a Markdown table showing runtime, macros completed, and total dolls collected.
7. **Infinite Idle:** After reaching the 5.5-hour soft timeout, the script will wrap up the current loop, retire dolls, and use the GitHub CLI to trigger a brand-new job in the background, achieving 24/7 unlimited farming.
8. **Auto Stop:** To stop the workflow, simply log into the game on your device. This will automatically invalidate the current `SIGN_KEY`, causing the GHA script to hit a fatal error circuit breaker and terminate without respawning. Alternatively, manually cancel the queued workflow via the Actions UI.