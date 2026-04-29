// hook.js

var STOLEN_VEHICLE_PTR = null;
var SPOOF_ENABLED = false;

function getModuleBase(name) {
    var mod = Process.findModuleByName(name);
    return mod ? mod.base : null;
}

function getIl2cppClassName(objPtr) {
    if (objPtr.isNull()) return "null";
    try {
        // objPtr -> klass -> name
        var klassPtr = objPtr.readPointer();
        var classNamePtr = klassPtr.add(0x10).readPointer();
        return classNamePtr.readUtf8String();
    } catch(e) {
        return "Unknown(Memory Access Error)";
    }
}

function initHooks() {
    var gameAssembly = getModuleBase("GameAssembly.dll");
    if (!gameAssembly) return;

    // 1. 窃取载具指针的入口点 (当你在主界面打开格纳库或梯队列表时触发)
    // 签名: void HomeTeamListBarController__InitWithVehicle (__this, Vehicle_o* ve, ...)
    var addr_InitWithVehicle = gameAssembly.add(45283408); 
    
    // 2. 靶机输出队伍给战斗引擎的出口点
    // 签名: GF_Battle_BaseTeam_o* TargetTrainGameData__get_Team (...)
    var addr_get_Team = gameAssembly.add(53264624);

    send({ type: "info", payload: "Hooks initializing..." });

    // Hook 1: 窃取载具对象
    try {
        Interceptor.attach(addr_InitWithVehicle, {
            onEnter: function(args) {
                var vehiclePtr = args[1];
                if (!vehiclePtr.isNull()) {
                    STOLEN_VEHICLE_PTR = vehiclePtr;
                    var className = getIl2cppClassName(vehiclePtr);
                    send({ type: "hook", payload: "[STEALER] Captured Vehicle Pointer: " + vehiclePtr + " | Class: " + className });
                }
            }
        });
    } catch(e) { send({ type: "error", payload: "Failed hook InitWithVehicle: " + e }); }

    // Hook 2: 在靶机发车时掉包指针
    try {
        Interceptor.attach(addr_get_Team, {
            onLeave: function(retval) {
                var originalClassName = getIl2cppClassName(retval);
                send({ type: "hook", payload: "[TargetTrain] get_Team normally returns -> " + retval + " | Class: " + originalClassName });

                if (SPOOF_ENABLED && STOLEN_VEHICLE_PTR !== null) {
                    send({ type: "hook", payload: "[INJECT] Replacing return value with Stolen Vehicle -> " + STOLEN_VEHICLE_PTR });
                    retval.replace(STOLEN_VEHICLE_PTR); // 偷天换日
                } else if (SPOOF_ENABLED && STOLEN_VEHICLE_PTR === null) {
                    send({ type: "error", payload: "[INJECT FAIL] Spoof enabled but no Vehicle pointer stolen yet!" });
                }
            }
        });
    } catch(e) { send({ type: "error", payload: "Failed hook get_Team: " + e }); }

    send({ type: "info", payload: "System Ready. Step 1: Open Vehicle Garage in game to capture pointer." });
}

rpc.exports = {
    setspoof: function(enabled) {
        SPOOF_ENABLED = enabled;
        return true;
    }
};

setTimeout(initHooks, 1000);