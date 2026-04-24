# GFLZIRC

Fundamentally, `gflzirc` reverse-engineers the `AC.AuthCode$$Authcode` methodology. This emancipation allows us to directly forge data packets and communicate with the game servers, seamlessly circumventing the native client.

## 1. Architecture

The repository is structured to encapsulate diverse functionalities—ranging from low-level cryptographic operations to high-level HTTP client abstractions.

```sh
.
├── gflzirc                 # Core Package: gflzirc
│   ├── __init__.py             # Public API exports
│   ├── client.py               # High-level HTTP client mimicking Unity requests
│   ├── constants.py            # System constants, endpoints, and static keys
│   ├── crypto.py               # Bespoke encryption/decryption algorithms
│   └── proxy.py                # MITM proxy with robust HTTP stream parsing
├── pyproject.toml          # PyPI configuration
└── README.md               # Package documentation
```

## 2. Crypto

The cryptographic mechanism bifurcates into "Encode" and "Decode," though our primary focus remains on the former for payload forgery. The algorithm is a highly idiosyncratic variant of `Discuz! AuthCode`. 

Below is the conceptual breakdown reverse-engineered via IDA Free.

### 2.1 External

This module serves as the interface between the game's Il2Cpp environment and the core cryptographic functions.

> **Signature:** `System_String_o* AC_AuthCode__Encode (System_String_o* source, System_String_o* key, const MethodInfo* method);`

It conducts class initialization and type-checking within Il2Cpp before invoking the underlying AuthCode implementation, defaulting to an expiry time of 3600 seconds (1 hour).

```cpp
/**
 * @brief "Signature": "System_String_o* AC_AuthCode__Encode (System_String_o* source, System_String_o* key, const MethodInfo* method);",
 *
 * @note An external call of encode or decode.
 */
__int64 __fastcall sub_181B07AE0(__int64 a1, __int64 a2)
{
	/**
	 * @brief Class initialization and type checking in Il2Cpp
	 * 
	 * @note It's doesn't matter.
	 */
	if ( !byte_184BF59BC )
  	{
    	sub_18018E100(8668);
    	byte_184BF59BC = 1;
	}
	if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
		i981y4i12xrscakfbuqluj0dl_0();

	/**
	 * @brief Call AC.AuthCode$$Authcode (source, key, operation=0, expiry=3600)
	 * 
	 * @param operation, 0 encode, 1 decode.
	 * @param expiry, 1 hour i.e. 3600 seconds.
	 */
	return sub_181B06A50(a1, a2, 0, 3600, 0);
}
```

### 2.2 Encode

Sunborn implements a proprietary modification of the standard `Discuz! AuthCode`. The salient deviations are as follows:

1. **Eradication of `keyc` (Random Prefix):** Standard algorithms append a 4-bit random character to the ciphertext header to guarantee uniqueness. Sunborn deliberately omits this. The resulting Base64 string is pure RC4 ciphertext devoid of any random prefix.
2. **Cryptkey Derivation:** 
    - *Standard:* `cryptkey = keya + MD5(keya + keyc)`
    - *Sunborn:* `cryptkey = keyb + MD5(keyb)`
3. **Checksum Shift:**
    - *Standard:* `checksum = MD5(plaintext + keyb)[0:16]`
    - *Sunborn:* `checksum = MD5(plaintext + keya)[0:16]`

### 2.3 Decode

The decoding sequence accurately reverses the aforementioned operations, explicitly managing the idiosyncratic 26-byte payload alignment and verifying the modified checksum. Additionally, the Python implementation accommodates GZIP decompression, as the server frequently compresses the underlying JSON payload before RC4 encryption.

## 3. Constants

The `constants.py` module acts as the central taxonomy for the game's static data, dictating routing, authentication bootstraps, and API endpoints.

1. **Server Routing (`SERVERS`):** Maps server codenames (e.g., `M4A1`, `EN`, `M16`) to their respective base URLs, facilitating cross-region compatibility.
2. **Cryptographic Keys:**
    - `STATIC_KEY` (`"yundoudou"`): The pivotal bootstrap key. The server enforces this static key to decrypt the initial handshake. 
    - `DEFAULT_SIGN`: An initial pseudo-random sequence utilized prior to the acquisition of a dynamic session key.
3. **API Endpoints:** Categorizes over a dozen server endpoints into logical domains such as Mission operations (`API_MISSION_START`, `API_MISSION_TEAM_MOVE`), Index queries, Gun management, and Daily resets.
4. **Macro Configurations:** Embeds hardcoded sequences (e.g., `GUIDE_COURSE_11880`) imperative for automated tactical maneuvering.

## 4. Proxy

To facilitate debugging and real-time telemetry analysis—especially for Windows users—the `proxy.py` module deploys a robust Man-in-the-Middle (MITM) architecture. 

1. **Robust Stream Parsing:** The bespoke `HttpStreamDecoder` handles raw socket traffic. It flawlessly mitigates TCP fragmentation by resolving `Content-Length` constraints and decoding `Chunked Transfer-Encoding` on the fly.
2. **Traffic Interception & Analysis:** It filters outbound requests to the `index.php` API, decrypts the `outdatacode` payload in real-time, and triggers user-defined callbacks (`C2S` and `S2C` events).
3. **Dynamic Key Upgrade Mechanism:** Crucially, the proxy scrutinizes incoming server responses. When the server provisions a new dynamic `sign` key, the proxy autonomously captures it (`SYS_KEY_UPGRADE` event) and overwrites the active cryptographic key to ensure uninterrupted decryption of subsequent packets.
4. **System Integration:** Exposes `set_windows_proxy` which directly manipulates the Windows Registry (`winreg`) and leverages `ctypes` to flush `wininet` options, seamlessly routing OS-level traffic into our python-based interceptor.

## 5. Client

The `GFLClient` (`client.py`) is an autonomous, high-level abstraction built atop the `requests` library, designed to orchestrate direct server communications without proxy dependencies.

1. **Header Spoofing:** Automatically injects `User-Agent` and `X-Unity-Version` headers to mimic the intrinsic Unity engine behavior meticulously.
2. **State Management:** Maintains an active HTTP session, deliberately bypassing global proxy variables to prevent loopback errors.
3. **Transparent Cryptography:** Completely abstracts the AuthCode complexity. It inherently serializes Python dictionaries into JSON, executes the RC4 variant encryption using the current `sign_key`, and structures the HTTP POST `outdatacode` parameters.
4. **Resilience & Decryption:** It parses the idiosyncratic server responses (often prefixed with `#`), decrypts the payload, and provides built-in retry mechanisms with configurable timeouts to mitigate transient network failures.