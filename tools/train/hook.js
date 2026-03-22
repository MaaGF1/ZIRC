// debuff_hook.js

// ----------------------------------------------------------------
// Offsets Directory 
// ----------------------------------------------------------------
// 我们只需要这两个最顶层、最可靠的函数！放弃底层结构体！
var rva_GetDamage = 0x2818630; // CharacterSkillImpl$$GetDamage
var rva_GetTeamId = 0x281A280; // CharacterSkillImpl$$GetTeamId

// ----------------------------------------------------------------
// Debuff Configuration (负重训练系数配置)
// 现在采用概率机制：num / den = 实际发挥的实力比例
// ----------------------------------------------------------------
var DEBUFF = {
    ENABLED: true,
    HIT:   { num: 5, den: 10 },  // 命中减半 (50% 概率将原有的命中强制改为 Miss)
    DODGE: { num: 5, den: 10 },  // 回避减半 (50% 概率将敌方的 Miss 强制改判为命中)
    CRIT:  { num: 0, den: 10 },  // 暴击降至0倍 (100% 没收暴击)
    ARMOR: { num: 7, den: 10 },  // 护甲降至70% (受到的伤害放大 10/7 倍)
    DMG:   { num: 5, den: 10 }   // 最终伤害减半
};

// ----------------------------------------------------------------
// 遥测日志 (Telemetry)
// ----------------------------------------------------------------
var logLimits = { HIT: 0, DODGE: 0, CRIT: 0, ARMOR: 0, DMG: 0, ERR: 0 };
var MAX_LOGS = 20;

function logThrottled(type, message) {
    if (logLimits[type] < MAX_LOGS) {
        send({ type: "info", payload: "[JS] [" + type + "] " + message });
        logLimits[type]++;
    }
}

function getModuleBase(name) {
    var mod = Process.findModuleByName(name);
    return mod ? mod.base : null;
}

function hook() {
    var gameAssembly = getModuleBase("GameAssembly.dll");
    if (!gameAssembly) {
        send({ type: "error", payload: "GameAssembly.dll not found." });
        return;
    }

    send({ type: "info", payload: "[JS] Weight Training V4 (Outcome Manipulation) Online." });

    var ptr_GetDamage = gameAssembly.add(rva_GetDamage);
    var GetTeamId = new NativeFunction(gameAssembly.add(rva_GetTeamId), 'int32', ['pointer', 'pointer']);

    // ----------------------------------------------------------------
    // 核心挂钩：篡改结果指针
    // ----------------------------------------------------------------
    Interceptor.attach(ptr_GetDamage, {
        onEnter: function(args) {
            // Il2Cpp x64 调用约定：
            // args[0] = this
            // args[1] = target
            // args[2] = skillCfg
            // args[3] = hurtCfg
            // args[4] = out bool isCrit (指针)
            // args[5] = out bool isMiss (指针)

            this.pAttacker = args[0];
            this.ptrIsCrit = args[4];
            this.ptrIsMiss = args[5];

            try {
                var attackerTeamId = GetTeamId(this.pAttacker, ptr(0));
                this.isEnemy = (attackerTeamId > 1000 || attackerTeamId < 0);
            } catch (e) {
                this.isEnemy = false;
            }
        },
        onLeave: function(retval) {
            if (!DEBUFF.ENABLED) return;

            try {
                var calcDamage = retval.toInt32();
                var isCrit = this.ptrIsCrit.readU8(); // 0 = false, 1 = true
                var isMiss = this.ptrIsMiss.readU8(); // 0 = false, 1 = true

                if (!this.isEnemy) {
                    // ============================================
                    // 我方攻击：施加 DMG, HIT, CRIT 负重
                    // ============================================
                    var debuffedDmg = Math.floor(calcDamage * DEBUFF.DMG.num / DEBUFF.DMG.den);

                    // 1. 削弱命中：如果引擎判定打中了，我们按概率强制让它丢失
                    if (isMiss === 0) {
                        var hitPower = DEBUFF.HIT.num / DEBUFF.HIT.den;
                        if (Math.random() > hitPower) {
                            this.ptrIsMiss.writeU8(1); // 内存覆写：强制设为 Miss
                            isMiss = 1;
                            debuffedDmg = 0; // Miss 时伤害强制归 0
                            logThrottled("HIT", "Forced a MISS! Target evaded our attack.");
                        }
                    }

                    // 2. 削弱暴击：如果引擎判定暴击了，我们按概率强制没收
                    if (isMiss === 0 && isCrit === 1) {
                        var critPower = DEBUFF.CRIT.num / DEBUFF.CRIT.den;
                        if (Math.random() > critPower) {
                            this.ptrIsCrit.writeU8(0); // 内存覆写：取消暴击
                            logThrottled("CRIT", "Crit nullified by debuff.");
                        }
                    }

                    // 3. 修改伤害
                    if (isMiss === 1) {
                        retval.replace(0);
                    } else if (debuffedDmg !== calcDamage) {
                        retval.replace(debuffedDmg);
                        logThrottled("DMG", "Damage nerfed: " + calcDamage + " -> " + debuffedDmg);
                    }

                } else {
                    // ============================================
                    // 敌方攻击：施加 DODGE, ARMOR 负重 (挨打模拟)
                    // ============================================
                    
                    // 1. 削弱回避：如果敌人打空了，我们按概率强行撞上去挨打！
                    if (isMiss === 1) {
                        var dodgePower = DEBUFF.DODGE.num / DEBUFF.DODGE.den;
                        if (Math.random() > dodgePower) {
                            this.ptrIsMiss.writeU8(0); // 内存覆写：强制吃下这一击
                            logThrottled("DODGE", "Forced to take a HIT due to Dodge debuff!");
                        }
                    }

                    // 2. 削弱护甲：放大我们受到的伤害
                    // 逻辑：如果护甲降为0.7，意味着敌人伤害乘以 1/0.7 (即 1.42倍)
                    var armorFactor = DEBUFF.ARMOR.den / DEBUFF.ARMOR.num; 
                    var amplifiedDmg = Math.floor(calcDamage * armorFactor);
                    if (amplifiedDmg !== calcDamage) {
                        retval.replace(amplifiedDmg);
                        logThrottled("ARMOR", "Incoming damage amplified (Armor nerf): " + calcDamage + " -> " + amplifiedDmg);
                    }
                }
            } catch (e) {
                // 防止指针访问越界导致崩溃
            }
        }
    });

    send({ type: "info", payload: "[JS] Outcome Manipulation Injectors armed. Let the battle begin." });
}

setTimeout(hook, 1000);