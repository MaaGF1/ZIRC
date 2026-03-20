// hook.js

var addr_DecodeWithGzip = 28342768; // AC.AuthCode$$DecodeWithGzip
var addr_Encode = 28343008;         // AC.AuthCode$$Encode

// Helper: Read C# Byte Array
function getCSharpByteArray(ptr) {
    if (ptr.isNull()) return null;
    var len = ptr.add(0x18).readU32();
    var dataPtr = ptr.add(0x20);
    return dataPtr.readByteArray(len);
}

// Helper: Create C# Byte Array from JS ArrayBuffer
// This is needed to return modified data back to the game
function createCSharpByteArray(data) {
    var gameAssembly = Process.findModuleByName("GameAssembly.dll");
    // We need to find the Byte[] class pointer to use Il2Cpp.Array.New (or manual allocation)
    // For simplicity in a raw Interceptor, we can just allocate memory 
    // and hope the game doesn't crash, but the correct way is to use Il2Cpp's internal array new.
    // Here we use a more stable approach: modify the content of the existing buffer if size allows,
    // or use Memory.alloc if the game handles it. 
    // However, the SAFEST way without a full Il2Cpp wrapper is to use the original pointer 
    // if our new data is smaller, but usually it's larger.
    
    // NOTE: This implementation uses a simplified allocation. 
    // In a production environment, you should resolve 'il2cpp_array_new'.
    var buffer = Memory.alloc(data.byteLength + 0x20);
    // Dummy Class Pointer (Ideally should be the actual System.Byte[] class)
    // Most GFL versions don't strictly check the class pointer for return values here
    buffer.writePointer(ptr("0x0")); 
    buffer.add(0x18).writeU32(data.byteLength);
    buffer.add(0x20).writeByteArray(data);
    return buffer;
}

function getCSharpString(ptr) {
    if (ptr.isNull()) return null;
    var len = ptr.add(0x10).readU32();
    if (len === 0) return "";
    return ptr.add(0x14).readUtf16String(len);
}

function hook() {
    var gameAssembly = Process.findModuleByName("GameAssembly.dll").base;

    // --- Hook S2C (Server To Client) ---
    var targetS2C = gameAssembly.add(addr_DecodeWithGzip);
    Interceptor.attach(targetS2C, {
        onLeave: function(retval) {
            if (retval.isNull()) return;

            var data = getCSharpByteArray(retval);
            if (data) {
                // Send to Python and WAIT for response
                send({ id: "S2C_REQ" }, data);

                var modified_ptr = retval;
                var op_completed = false;

                // Blocking receive
                recv('S2C_RES', function(msg, bin) {
                    if (msg.status === 'modified' && bin) {
                        console.log("[JS] Replacing S2C buffer with modified data from Python...");
                        modified_ptr = createCSharpByteArray(bin);
                    }
                    op_completed = true;
                });

                // Spin-lock until Python responds (Frida's recv is async but this thread is in onLeave)
                // This is generally safe in GFL as it happens on a background worker thread
                while(!op_completed) {
                    // Small delay to prevent CPU hogging
                    Thread.sleep(0.01);
                }
                
                retval.replace(modified_ptr);
            }
        }
    });

    // --- Hook C2S (Client To Server) ---
    var targetC2S = gameAssembly.add(addr_Encode);
    Interceptor.attach(targetC2S, {
        onEnter: function(args) {
            var strContent = getCSharpString(args[0]);
            if (strContent && strContent.trim().charAt(0) === '{') {
                send({ id: "C2S", content: strContent });
            }
        }
    });

    console.log("[JS] Dual-Hook with modification support installed.");
}

setTimeout(hook, 1000);