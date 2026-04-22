<!-- docs/02_gflzirc.md -->

# Demystifying gflzirc

This document delineates the architecture and internal mechanisms of the `gflzirc` package located under `src/core`. It provides the foundational APIs, cryptographic algorithms, and networking protocols requisite for orchestrating `src/demo` and `src/gha`.

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

```cpp
/**
 * @brief Sunborn's "Discuz! AuthCode"

 * @par I. Delete keyc
 * @note In standard algorithms, each encryption generates a 4-bit random character to be appended to the ciphertext header. 
 * Sunborn eliminates this step. It's Base64 is pure RC4 ciphertext, without any preceding random characters.
 * 
 * @par II. Change cryptkey
 * @note Standard: cryptkey = keya + MD5(keya + keyc)
 *       Sunborn:  cryptkey = keyb + MD5(keyb)
 * 
 * @par III. Change checksum
 * @note Standard: checksum = MD5(plaintext + keyb)[0:16] 
 *       Sunborn:  checksum = MD5(plaintext + keya)[0:16]
 */
__int64 __fastcall sub_181B06A50(__int64 a1, __int64 a2, int a3, int a4)
{
	bool v7; // r9
	__int64 v8; // rbx
	unsigned int v9; // esi
	unsigned int v10; // edi
	__int64 v11; // rax
	__int64 v12; // r15
	unsigned int v13; // edi
	__int64 v14; // rax
	__int64 v15; // r13
	__int64 v16; // rbx
	__int64 v17; // rax
	__int64 v18; // r15
	__int64 v19; // rdi
	__int64 v20; // rbx
	__int64 v21; // rbx
	__int64 v22; // rax
	__int64 v23; // rax
	__int64 v24; // rcx
	__int64 v25; // rax
	__int64 v26; // rbx
	__int64 v27; // rax
	__int64 v29; // rbx
	__int64 v30; // rbx
	__int64 v31; // rax
	__int64 v32; // rdi
	__int64 v33; // rax
	__int64 v34; // rbx
	unsigned int v35; // edi
	__int64 v36; // rax
	__int64 v37; // rdi
	unsigned int v38; // edi
	__int64 v39; // r14
	__int64 v40; // rax
	__int64 v41; // rax
	__int64 v42; // rdi
	__int64 v43; // rax
	int v44; // [rsp+40h] [rbp+0h] BYREF
	__int64 v45; // [rsp+48h] [rbp+8h]
	__int64 v46; // [rsp+50h] [rbp+10h]
	__int64 v47; // [rsp+58h] [rbp+18h]

	if ( !byte_184BF59BE )
	{
		sub_18018E100(8662);
		byte_184BF59BE = 1;
	}
	v44 = 0;
	if ( a1 )
		v7 = a2 == 0;
	else
		v7 = 1;
	if ( v7 )
		return *(_QWORD *)&Code;
	if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
		((void (*)(void))i981y4i12xrscakfbuqluj0dl_0)();
	v8 = sub_181B07E90(a2, 0);
	v9 = 16;
	v10 = 16;
	if ( !byte_184BF59B6 )
	{
		sub_18018E100(8663);
		byte_184BF59B6 = 1;
	}
	if ( !v8 )
		goto LABEL_98;
	if ( (int)sub_180546340(v8, 0) < 16 )
	{
		v11 = *(_QWORD *)&Code;
	}
	else
	{
		if ( (int)(sub_180546340(v8, 0) - 16) < 16 )
			v10 = sub_180546340(v8, 0) - 16;
		v11 = sub_180BF2920(v8, 16, v10, 0);
	}
	v12 = sub_181B07E90(v11, 0);
	v13 = 16;
	if ( !byte_184BF59B6 )
	{
		sub_18018E100(8663);
		byte_184BF59B6 = 1;
	}
	if ( (int)sub_180546340(v8, 0) < 0 )
	{
		v14 = *(_QWORD *)&Code;
	}
	else
	{
		if ( (int)sub_180546340(v8, 0) < 16 )
			v13 = sub_180546340(v8, 0);
		v14 = sub_180BF2920(v8, 0, v13, 0);
	}
	v15 = sub_181B07E90(v14, 0);
	v46 = v15;
	v45 = *(_QWORD *)&Code;
	v16 = sub_180BEAFC0(v12, *(_QWORD *)&Code, 0);
	if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
		((void (*)(void))i981y4i12xrscakfbuqluj0dl_0)();
	v17 = sub_181B07E90(v16, 0);
	/**
	 * @brief Generation of cryptkey
	 * 
	 * @note Standard: cryptkey = keya + MD5(keya + keyc)
	 * @note Sunborn:  cryptkey = keyb + MD5(keyb)
	 */
	v18 = sub_180BEAFC0(v12, v17, 0);
	v47 = v18;
	if ( a3 != 1 )
	{
		if ( a4 )
		{
			if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
				i981y4i12xrscakfbuqluj0dl_0(qword_184C71FB8);
			v44 = a4 + sub_181B07B60(0);
			v19 = sub_180D889D0(&v44, 0);
		}
		else
		{
			v19 = qword_184C410A8;
		}
		/**
		 * @brief Generation of checksum
		 *
		 * @note Standard: checksum = MD5(plaintext + keyb)[0:16]
		 * @note Sunborn:  checksum = MD5(plaintext + keya)[0:16]
		 */
		v20 = sub_180BEAFC0(a1, v15, 0);
		if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
			i981y4i12xrscakfbuqluj0dl_0(qword_184C71FB8);
		v21 = sub_181B07E90(v20, 0);
		if ( !byte_184BF59B6 )
		{
			sub_18018E100(8663);
			byte_184BF59B6 = 1;
		}
		if ( v21 )
		{
			if ( (int)sub_180546340(v21, 0) < 0 )
			{
				v22 = *(_QWORD *)&Code;
			}
			else
			{
				if ( (int)sub_180546340(v21, 0) < 16 )
					v9 = sub_180546340(v21, 0);
				v22 = sub_180BF2920(v21, 0, v9, 0);
			}
			v23 = sub_180BEB780(v19, v22, a1, 0);
			v24 = **(_QWORD **)(qword_184C71FB8 + 184);
			if ( v24 )
			{
				v25 = (*(__int64 (__fastcall **)(__int64, __int64, _QWORD))(*(_QWORD *)v24 + 712LL))(
								v24,
								v23,
								*(_QWORD *)(*(_QWORD *)v24 + 720LL));
				v26 = sub_181B07F20(v25, v18, 0);
				if ( (*(_BYTE *)(qword_184CE65C8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184CE65C8 + 216) )
					i981y4i12xrscakfbuqluj0dl_0(qword_184CE65C8);
				v27 = sub_1810306F0(v26, 0);
				return sub_180BEAFC0(v45, v27, 0);
			}
		}
LABEL_98:
		sub_1801BE340(0);
	}
	if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
		((void (*)(void))i981y4i12xrscakfbuqluj0dl_0)();
	v29 = sub_181B07270(a1, 0, 0);
	if ( (*(_BYTE *)(qword_184CE65C8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184CE65C8 + 216) )
		((void (*)(void))i981y4i12xrscakfbuqluj0dl_0)();
	v30 = sub_18102F9F0(v29, 0);
	v31 = qword_184C71FB8;
	if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
	{
		i981y4i12xrscakfbuqluj0dl_0(qword_184C71FB8);
		v31 = qword_184C71FB8;
	}
	v32 = **(_QWORD **)(v31 + 184);
	v33 = sub_181B07F20(v30, v18, 0);
	if ( !v32 )
		goto LABEL_98;
	v34 = (*(__int64 (__fastcall **)(__int64, __int64, _QWORD))(*(_QWORD *)v32 + 1000LL))(
					v32,
					v33,
					*(_QWORD *)(*(_QWORD *)v32 + 1008LL));
	v35 = 10;
	if ( !byte_184BF59B6 )
	{
		sub_18018E100(8663);
		byte_184BF59B6 = 1;
	}
	if ( !v34 )
		goto LABEL_98;
	if ( (int)sub_180546340(v34, 0) < 0 )
	{
		v36 = *(_QWORD *)&Code;
	}
	else
	{
		if ( (int)sub_180546340(v34, 0) < 10 )
			v35 = sub_180546340(v34, 0);
		v36 = sub_180BF2920(v34, 0, v35, 0);
	}
	v37 = sub_180D88D70(v36, 0);
	if ( v37 )
	{
		if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
			i981y4i12xrscakfbuqluj0dl_0(qword_184C71FB8);
		if ( v37 - (int)sub_181B07B60(0) <= 0 )
			return *(_QWORD *)&Code;
	}
	if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
		i981y4i12xrscakfbuqluj0dl_0(qword_184C71FB8);
	v38 = 16;
	if ( !byte_184BF59B6 )
	{
		sub_18018E100(8663);
		byte_184BF59B6 = 1;
	}
	if ( (int)sub_180546340(v34, 0) < 10 )
	{
		v39 = *(_QWORD *)&Code;
	}
	else
	{
		if ( (int)(sub_180546340(v34, 0) - 10) < 16 )
			v38 = sub_180546340(v34, 0) - 10;
		v39 = sub_180BF2920(v34, 10, v38, 0);
	}
	v40 = sub_181B07270(v34, 26, 0);
	v41 = sub_180BEAFC0(v40, v15, 0);
	v42 = sub_181B07E90(v41, 0);
	if ( !byte_184BF59B6 )
	{
		sub_18018E100(8663);
		byte_184BF59B6 = 1;
	}
	if ( !v42 )
		goto LABEL_98;
	if ( (int)sub_180546340(v42, 0) < 0 )
	{
		v43 = *(_QWORD *)&Code;
	}
	else
	{
		if ( (int)sub_180546340(v42, 0) < 16 )
			v9 = sub_180546340(v42, 0);
		v43 = sub_180BF2920(v42, 0, v9, 0);
	}
	if ( !(unsigned __int8)sub_180BED450(v39, v43, 0) )
		return *(_QWORD *)&Code;
	if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
		i981y4i12xrscakfbuqluj0dl_0(qword_184C71FB8);
	return sub_181B07270(v34, 26, 0);
}
```

### 2.3 Decode

The decoding sequence accurately reverses the aforementioned operations, explicitly managing the idiosyncratic 26-byte payload alignment and verifying the modified checksum. Additionally, the Python implementation accommodates GZIP decompression, as the server frequently compresses the underlying JSON payload before RC4 encryption.

```cpp
__int64 __fastcall sub_181B07380(__int64 a1, __int64 a2)
{
	__int64 v4; // rdi
	bool v5; // al
	__int64 v6; // rbx
	unsigned int v7; // r14d
	unsigned int v8; // r15d
	__int64 v9; // rax
	__int64 v10; // r13
	unsigned int v11; // r15d
	__int64 v12; // rax
	__int64 v13; // r12
	__int64 v14; // rbx
	__int64 v15; // rax
	__int64 v16; // r15
	__int64 v17; // rbx
	__int64 v18; // rbx
	__int64 v19; // rax
	__int64 v20; // rbx
	__int64 v21; // rcx
	__int64 v22; // rsi
	unsigned int v23; // r15d
	__int64 v24; // rax
	__int64 v25; // r15
	__int64 v26; // r13
	int v27; // eax
	__int64 v28; // rax
	__int64 v29; // rcx
	int v30; // ebx
	int v31; // eax
	unsigned int v32; // ebx
	__int64 v33; // rsi
	__int64 v34; // rbx
	__int64 v35; // rax
	__int64 v37; // [rsp+C0h] [rbp+70h]

	if ( !byte_184BF59C0 )
	{
		sub_18018E100(8665);
		byte_184BF59C0 = 1;
	}
	v4 = 0;
	if ( a1 )
		v5 = a2 == 0;
	else
		v5 = 1;
	if ( !v5 )
	{
		if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
			i981y4i12xrscakfbuqluj0dl_0();
		v6 = sub_181B07E90(a2, 0);
		v7 = 16;
		v8 = 16;
		if ( !byte_184BF59B6 )
		{
			sub_18018E100(8663);
			byte_184BF59B6 = 1;
		}
		if ( !v6 )
			goto LABEL_76;
		if ( (int)sub_180546340(v6, 0) < 16 )
		{
			v9 = *(_QWORD *)&Code;
		}
		else
		{
			if ( (int)(sub_180546340(v6, 0) - 16) < 16 )
				v8 = sub_180546340(v6, 0) - 16;
			v9 = sub_180BF2920(v6, 16, v8, 0);
		}
		v10 = sub_181B07E90(v9, 0);
		v11 = 16;
		if ( !byte_184BF59B6 )
		{
			sub_18018E100(8663);
			byte_184BF59B6 = 1;
		}
		if ( (int)sub_180546340(v6, 0) < 0 )
		{
			v12 = *(_QWORD *)&Code;
		}
		else
		{
			if ( (int)sub_180546340(v6, 0) < 16 )
				v11 = sub_180546340(v6, 0);
			v12 = sub_180BF2920(v6, 0, v11, 0);
		}
		v13 = sub_181B07E90(v12, 0);
		v14 = sub_180BEAFC0(v10, *(_QWORD *)&Code, 0);
		if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
			i981y4i12xrscakfbuqluj0dl_0();
		v15 = sub_181B07E90(v14, 0);
		v16 = sub_180BEAFC0(v10, v15, 0);
		if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
			i981y4i12xrscakfbuqluj0dl_0();
		v17 = sub_181B07270(a1, 0, 0);
		if ( (*(_BYTE *)(qword_184CE65C8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184CE65C8 + 216) )
			i981y4i12xrscakfbuqluj0dl_0();
		v18 = sub_18102F9F0(v17, 0);
		if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
			i981y4i12xrscakfbuqluj0dl_0();
		v19 = sub_181B07F20(v18, v16, 0);
		v20 = v19;
		v21 = **(_QWORD **)(qword_184C71FB8 + 184);
		if ( !v21 )
			goto LABEL_76;
		v22 = (*(__int64 (__fastcall **)(__int64, __int64, _QWORD))(*(_QWORD *)v21 + 1000LL))(
						v21,
						v19,
						*(_QWORD *)(*(_QWORD *)v21 + 1008LL));
		v23 = 10;
		if ( !byte_184BF59B6 )
		{
			sub_18018E100(8663);
			byte_184BF59B6 = 1;
		}
		if ( !v22 )
			goto LABEL_76;
		if ( (int)sub_180546340(v22, 0) < 0 )
		{
			v24 = *(_QWORD *)&Code;
		}
		else
		{
			if ( (int)sub_180546340(v22, 0) < 10 )
				v23 = sub_180546340(v22, 0);
			v24 = sub_180BF2920(v22, 0, v23, 0);
		}
		v25 = sub_180D88D70(v24, 0);
		if ( !v20 )
			goto LABEL_76;
		v26 = i08z7pbms4cft6cphnj0mrydf_0(qword_184CE6BD8, (unsigned int)(*(_DWORD *)(v20 + 24) - 26));
		sub_180E6DCC0(v20, 26, v26, 0, *(_DWORD *)(v20 + 24) - 26);
		if ( !v13 )
			goto LABEL_76;
		v27 = sub_180546340(v13, 0);
		v28 = i08z7pbms4cft6cphnj0mrydf_0(qword_184CE6BD8, (unsigned int)(v27 - 26 + *(_DWORD *)(v20 + 24)));
		v37 = v28;
		if ( !v26 )
			goto LABEL_76;
		sub_180E6DCC0(v26, 0, v28, 0, *(_DWORD *)(v26 + 24));
		v29 = **(_QWORD **)(qword_184C71FB8 + 184);
		if ( !v29 )
			goto LABEL_76;
		v30 = (*(__int64 (__fastcall **)(__int64, __int64, _QWORD))(*(_QWORD *)v29 + 712LL))(
						v29,
						v13,
						*(_QWORD *)(*(_QWORD *)v29 + 720LL));
		v31 = sub_180546340(v13, 0);
		sub_180E6DCC0(v30, 0, v37, *(_DWORD *)(v26 + 24), v31);
		if ( !v25 )
			goto LABEL_79;
		if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
			i981y4i12xrscakfbuqluj0dl_0();
		if ( v25 - (int)sub_181B07B60(0) > 0 )
		{
LABEL_79:
			if ( (*(_BYTE *)(qword_184C71FB8 + 295) & 2) != 0 && !*(_DWORD *)(qword_184C71FB8 + 216) )
				i981y4i12xrscakfbuqluj0dl_0();
			v32 = 16;
			if ( !byte_184BF59B6 )
			{
				sub_18018E100(8663);
				byte_184BF59B6 = 1;
			}
			if ( (int)sub_180546340(v22, 0) < 10 )
			{
				v33 = *(_QWORD *)&Code;
			}
			else
			{
				if ( (int)(sub_180546340(v22, 0) - 10) < 16 )
					v32 = sub_180546340(v22, 0) - 10;
				v33 = sub_180BF2920(v22, 10, v32, 0);
			}
			v34 = sub_181B07D90(v37, 0);
			if ( !byte_184BF59B6 )
			{
				sub_18018E100(8663);
				byte_184BF59B6 = 1;
			}
			if ( v34 )
			{
				if ( (int)sub_180546340(v34, 0) < 0 )
				{
					v35 = *(_QWORD *)&Code;
				}
				else
				{
					if ( (int)sub_180546340(v34, 0) < 16 )
						v7 = sub_180546340(v34, 0);
					v35 = sub_180BF2920(v34, 0, v7, 0);
				}
				if ( (unsigned __int8)sub_180BED450(v33, v35, 0) )
					return v26;
				return v4;
			}
LABEL_76:
			sub_1801BE340(0);
		}
	}
	return v4;
}
```

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