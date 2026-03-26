// hook_dual.js

// === 替换后的 TeamID ===
var TARGET_ENEMY_ID = 2150; 

var addr_DecodeWithGzip = 28342768;
var addr_Encode = 28343008;

// Global to avoid GC
var memoryPool = [];

// Read C# Byte Array
function getCSharpByteArray(ptr) {
    if (ptr.isNull()) return null;
    try {
        var len = ptr.add(0x18).readU32();
        var dataPtr = ptr.add(0x20);
        if (len === 0) return null;
        return dataPtr.readByteArray(len);
    } catch (e) {
        return null;
    }
}

// Read C# String
function getCSharpString(ptr) {
    if (ptr.isNull()) return null;
    try {
        var len = ptr.add(0x10).readU32();
        if (len === 0) return "";
        return ptr.add(0x14).readUtf16String(len);
    } catch (e) {
        return null;
    }
}

// === Create C# String ===
function createFakeCSharpString(origStrPtr, newJsonStr) {
    try {
        var size = 0x14 + (newJsonStr.length * 2) + 2;
        var fakePtr = Memory.alloc(size);
        
        memoryPool.push(fakePtr);
        if (memoryPool.length > 20) memoryPool.shift(); 

        // 1. Copy object header
        fakePtr.writePointer(origStrPtr.readPointer());
        fakePtr.add(8).writePointer(origStrPtr.add(8).readPointer());
        
        // 2. Write length (Offset 0x10)
        fakePtr.add(0x10).writeU32(newJsonStr.length);
        
        // 3. Write string (Offset 0x14)
        fakePtr.add(0x14).writeUtf16String(newJsonStr);
        
        return fakePtr;
    } catch (e) {
        send({ id: "ERROR", content: "Fake string creation failed: " + e.message });
        return ptr(0);
    }
}

function getModuleBase(name) {
    var mod = Process.findModuleByName(name);
    return mod ? mod.base : null;
}

function hook() {
    try {
        var gameAssembly = getModuleBase("GameAssembly.dll");
        if (!gameAssembly) {
            send({ id: "LOG", content: "GameAssembly.dll not found. Retrying..." });
            setTimeout(hook, 1000);
            return;
        }

        send({ id: "LOG", content: "GameAssembly.dll found. Applying hooks..." });

        // --- Hook S2C ---
        var targetS2C = gameAssembly.add(addr_DecodeWithGzip);
        Interceptor.attach(targetS2C, {
            onEnter: function(args) { this.is_target = true; },
            onLeave: function(retval) {
                if (this.is_target) {
                    var data = getCSharpByteArray(retval);
                    if (data) { send({ id: "S2C" }, data); }
                }
            }
        });

        // --- Hook C2S ---
        var targetC2S = gameAssembly.add(addr_Encode);
        Interceptor.attach(targetC2S, {
            onEnter: function(args) {
                var strContent = getCSharpString(args[0]);
                
                if (strContent && strContent.length > 0) {
                    var trimmed = strContent.trim();
                    var isJson = (trimmed.charAt(0) === '{' || trimmed.charAt(0) === '[');
                    
                    if (isJson) {
                        try {
                            var jsonObj = JSON.parse(trimmed);

                            // Feature recognition
                            if (jsonObj && typeof jsonObj === 'object' && "enemy_team_id" in jsonObj && "order_id" in jsonObj) {
                                send({ id: "LOG", content: "[+] Target Practice Packet Intercepted!" });
                                send({ id: "LOG", content: "    => Original ID: " + jsonObj.enemy_team_id });
                                
                                // 1. Replace TeamID
                                jsonObj.enemy_team_id = TARGET_ENEMY_ID;
                                var newJsonStr = JSON.stringify(jsonObj);
                                
                                // 2. Generate a fake C# string from the original string.
                                var fakeStrPtr = createFakeCSharpString(args[0], newJsonStr);

                                if (!fakeStrPtr.isNull()) {
                                    // change Ptr's pos
                                    args[0] = fakeStrPtr;
                                    strContent = newJsonStr;
                                    send({ id: "LOG", content: "    => Successfully Injected ID: " + TARGET_ENEMY_ID });
                                }
                            }
                        } catch (e) {
                            // if not, continue
                        }
                        send({ id: "C2S", content: strContent });
                    }
                }
            }
        });

        send({ id: "LOG", content: "Hooks installed successfully! Ready for MITM attack." });

    } catch (e) {
        send({ id: "ERROR", content: "Hook initialization failed: " + e.message });
    }
}

setTimeout(hook, 1000);