// debuff_hook.js

// ----------------------------------------------------------------
// Offsets Directory 
// ----------------------------------------------------------------
var rva_GetDamage            = 0x2818630; // CharacterSkillImpl$$GetDamage
var rva_GetTeamId            = 0x281A280; // CharacterSkillImpl$$GetTeamId
var rva_get_realtimeDodge    = 0x1DF9DF0; // BattleCharacterManager::get_realtimeDodge

// ----------------------------------------------------------------
// Debuff Configuration (负重训练系数配置)
// ----------------------------------------------------------------
var DEBUFF = {
    ENABLED: true,
    HIT:   { num: 5, den: 10 },  // 命中减半 (50% 概率强行丢失)
    DODGE: { num: 0, den: 10 },  // 回避降至0 (全局物理拦截：底层属性直接归0)
    CRIT:  { num: 0, den: 10 },  // 暴击降至0 (没收暴击，并撤销 1.5x 伤害加成)
    ARMOR: { num: 7, den: 10 },  // 护甲降至70% (承伤放大 1.42 倍)
    DMG:   { num: 10, den: 10 }   // 最终伤害减半
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

// 工具函数：定点数(FP/Int64)安全分数运算
function applyFPCoefficient(nativePtr, num, den) {
    if (num === den) return nativePtr;
    try {
        var val = int64(nativePtr.toString()); 
        var newVal = val.mul(num).div(den);
        return ptr(newVal.toString()); 
    } catch (e) {
        return nativePtr; 
    }
}

function hook() {
    var gameAssembly = getModuleBase("GameAssembly.dll");
    if (!gameAssembly) {
        send({ type: "error", payload: "GameAssembly.dll not found." });
        return;
    }

    send({ type: "info", payload: "[JS] Weight Training V5 (Hybrid Manipulation) Online." });

    var ptr_GetDamage = gameAssembly.add(rva_GetDamage);
    var GetTeamId = new NativeFunction(gameAssembly.add(rva_GetTeamId), 'int32', ['pointer', 'pointer']);

    // ----------------------------------------------------------------
    // 拦截层 1：底层属性无条件剥夺 (解决 DODGE 无伤害问题)
    // ----------------------------------------------------------------
    Interceptor.attach(gameAssembly.add(rva_get_realtimeDodge), {
        onLeave: function(retval) {
            if (!DEBUFF.ENABLED) return;
            var origVal = retval.toString();
            if (origVal !== "0x0") {
                // 全局无条件削弱回避。所有人(包括敌人)回避下降。
                // 这完美达成了"让我们的人物挨打"的训练目的。
                var newVal = applyFPCoefficient(retval, DEBUFF.DODGE.num, DEBUFF.DODGE.den);
                retval.replace(newVal);
                logThrottled("DODGE", "Base Dodge attribute nerfed: " + origVal + " -> " + newVal);
            }
        }
    });

    // ----------------------------------------------------------------
    // 拦截层 2：结算结果篡改 (解决 DMG, ARMOR, HIT, CRIT)
    // ----------------------------------------------------------------
    Interceptor.attach(ptr_GetDamage, {
        onEnter: function(args) {
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
                var isCrit = this.ptrIsCrit.readU8(); 
                var isMiss = this.ptrIsMiss.readU8(); 

                if (!this.isEnemy) {
                    // ============================================
                    // 我方攻击：施加 DMG, HIT, CRIT 负重
                    // ============================================
                    var debuffedDmg = Math.floor(calcDamage * DEBUFF.DMG.num / DEBUFF.DMG.den);

                    // 1. 削弱命中：强行变 Miss 并抹除伤害
                    if (isMiss === 0) {
                        var hitPower = DEBUFF.HIT.num / DEBUFF.HIT.den;
                        if (Math.random() > hitPower) {
                            this.ptrIsMiss.writeU8(1); 
                            isMiss = 1;
                            debuffedDmg = 0; 
                            logThrottled("HIT", "Forced a MISS! Target evaded our attack.");
                        }
                    }

                    // 2. 削弱暴击：撤销暴击状态，【并剥离伤害加成】
                    if (isMiss === 0 && isCrit === 1) {
                        var critPower = DEBUFF.CRIT.num / DEBUFF.CRIT.den;
                        if (Math.random() > critPower) {
                            this.ptrIsCrit.writeU8(0); 
                            // 【核心修复】：少前基础暴击伤害通常是 1.5 倍，我们强行把伤害除以 1.5 还原！
                            // 即使带了装备导致不止1.5倍，除以 1.5 也能极大削弱它的数值，达到负重目的。
                            debuffedDmg = Math.floor(debuffedDmg / 1.5); 
                            logThrottled("CRIT", "Crit nullified & math reverted! Damage scaled down.");
                        }
                    }

                    // 3. 最终写入伤害
                    if (isMiss === 1) {
                        retval.replace(0);
                    } else if (debuffedDmg !== calcDamage) {
                        retval.replace(debuffedDmg);
                        logThrottled("DMG", "Damage nerfed: " + calcDamage + " -> " + debuffedDmg);
                    }

                } else {
                    // ============================================
                    // 敌方攻击：施加 ARMOR 负重 (挨打模拟)
                    // ============================================
                    
                    // 削弱护甲：放大我们受到的伤害
                    // 如果敌人打出了 0 伤害(例如护甲完全防御或闪避)，我们不放大。
                    if (calcDamage > 0) {
                        var armorFactor = DEBUFF.ARMOR.den / DEBUFF.ARMOR.num; 
                        var amplifiedDmg = Math.floor(calcDamage * armorFactor);
                        if (amplifiedDmg !== calcDamage) {
                            retval.replace(amplifiedDmg);
                            logThrottled("ARMOR", "Incoming damage amplified: " + calcDamage + " -> " + amplifiedDmg);
                        }
                    }
                }
            } catch (e) {}
        }
    });

    send({ type: "info", payload: "[JS] Hybrid Manipulation Armed. Target attributes compromised." });
}

setTimeout(hook, 1000);