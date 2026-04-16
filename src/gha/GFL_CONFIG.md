### Mode 1: Single Account (Legacy/Standard)

This is exactly the same as the previous version:

1. **`GFL_CONFIG`**:
    ```json
    {
        "USER_UID": "12345678",
        "MACRO_LOOPS": 9999,
        "MISSIONS_PER_RETIRE": 50,
        "SQUAD_ID": 106360,
        "TEAM_ID": 1,
        "SERVER_KEY": "M4A1"
    }
    ```
2. **`GFL_SIGN_KEY`**:
    ```text
    1234xxxxxxxx_for_account1
    ```

### Mode 2: Single Account in Array Notation

For consistency, you can also wrap a single account in JSON arrays.

1. **`GFL_CONFIG`**:
    - Looks Like:
        ```json
        [
            {
                "USER_UID": "12345678",
                "MACRO_LOOPS": 9999,
                "MISSIONS_PER_RETIRE": 50,
                "SQUAD_ID": 106360,
                "TEAM_ID": 1,
                "SERVER_KEY": "M4A1"
            }
        ]
        ```
    - In `Secret` input as:
        ```json
        [{"USER_UID":"12345678","MACRO_LOOPS":9999,"MISSIONS_PER_RETIRE":50,"SQUAD_ID":106360,"TEAM_ID":1,"SERVER_KEY":"M4A1"}]
        ```
2. **`GFL_SIGN_KEY`**:
    - Looks Like:
        ```json
        [
            "1234xxxxxxxx_for_account1"
        ]
        ```
    - In `Secret` input as:
        ```json
        ["1234xxxxxxxx_for_account1"]
        ```

### Mode 3: Multiple Accounts (New Feature)

You can farm multiple accounts simultaneously by passing arrays of configurations.

1. **`GFL_CONFIG`**:
    - Looks Like:
        ```json
        [
            {
                "USER_UID": "123",
                "MACRO_LOOPS": 9999,
                "MISSIONS_PER_RETIRE": 50,
                "SQUAD_ID": 106360,
                "TEAM_ID": 1,
                "SERVER_KEY": "M4A1"
            },
            {
                "USER_UID": "234",
                "MACRO_LOOPS": 9999,
                "MISSIONS_PER_RETIRE": 50,
                "SQUAD_ID": 106360,
                "TEAM_ID": 1,
                "SERVER_KEY": "RO635"
            }
        ]
        ```
    - In `Secret` input as:
        ```json
        [{"USER_UID":"123","MACRO_LOOPS":9999,"MISSIONS_PER_RETIRE":50,"SQUAD_ID":106360,"TEAM_ID":1,"SERVER_KEY":"M4A1"},{"USER_UID":"234","MACRO_LOOPS":9999,"MISSIONS_PER_RETIRE":50,"SQUAD_ID":106360,"TEAM_ID":1,"SERVER_KEY":"RO635"}]
        ```
2. **`GFL_SIGN_KEY`**:
    - Looks Like:
        ```json
        [
        "1234xxxxxxxx_for_account1",
        "1234xxxxxxxx_for_account2"
        ]
        ```
    - In `Secret` input as:
        ```json
        ["1234xxxxxxxx_for_account1","1234xxxxxxxx_for_account2"]
        ```