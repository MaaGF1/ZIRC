// hook.js

// "Signature": "System_Byte_array* AC_AuthCode__DecodeWithGzip (System_String_o* source, System_String_o* key, const MethodInfo* method);",
var addr_DecodeWithGzip = 28342768;
// "Signature": "System_String_o* AC_AuthCode__Encode (System_String_o* source, System_String_o* key, const MethodInfo* method);",
var addr_Encode = 28343008;

var ptrSize = Process.pointerSize;
var arrayDataOffset = ptrSize === 8 ? 0x20 : 0x10;
var arrayLenOffset = ptrSize === 8 ? 0x18 : 0x0C;

// Helper: Read C# Byte Array
function getCSharpByteArray(ptr) {
    if (ptr.isNull()) return null;
    try {
        var len = ptr.add(arrayLenOffset).readU32();
        if (len === 0) return null;
        return ptr.add(arrayDataOffset).readByteArray(len);
    } catch (e) {
        return null;
    }
}

function hook() {
    var modGameAssembly = Process.findModuleByName("GameAssembly.dll");
    if (!modGameAssembly) {
        setTimeout(hook, 1000);
        return;
    }

    // --- Hook S2C (Read-Only) ---
    var targetS2C = modGameAssembly.base.add(addr_DecodeWithGzip);
    Interceptor.attach(targetS2C, {
        onLeave: function(retval) {
            if (retval.isNull()) return;

            var data = getCSharpByteArray(retval);
            if (data) {
                // Async send, game thread does NOT wait
                send({ id: "S2C" }, data);
            }
        }
    });

    // --- Hook C2S (Silent Monitor) ---
    var targetC2S = modGameAssembly.base.add(addr_Encode);
    Interceptor.attach(targetC2S, {
        onEnter: function(args) {
            // Unused but kept if you need future logging
        }
    });

    console.log("[JS] Hook installed! Running in Safe Read-Only Mode.");
}

setTimeout(hook, 1000);