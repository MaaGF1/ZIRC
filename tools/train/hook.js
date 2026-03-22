// debuff_hook.js

// ----------------------------------------------------------------
// Offsets Directory 
// ----------------------------------------------------------------
// 仅保留最稳定、经过你亲自验证的终极函数
var rva_GetDamage = 0x2818630; // CharacterSkillImpl$$GetDamage
var rva_GetTeamId = 0x281A280; // CharacterSkillImpl$$GetTeamId

// ----------------------------------------------------------------
// Debuff Configuration (负重训练系数配置)
// ----------------------------------------------------------------
var DEBUFF = {
    ENABLED: true,
    
    // 我方攻击时生效的 Debuff
    HIT:   { num: 5, den: 10 },  // 命中减半 (50% 概率将原有的命中强制改为 Miss)
    CRIT:  { num: 0, den: 10 },  // 暴击降至0倍 (没收暴击，并额外压制 40% 伤害)
    DMG:   { num: 5, den: 10 },  // 最终基础伤害减半
    
    // 敌方攻击时生效的 Debuff (挨打模拟)
    ARMOR: { num: 10, den: 10 },  // 护甲降至70% (正常受到的伤害放大 1.42 倍)
    DODGE: { num: 5, den: 10 },  // 回避降至0 (100% 概率没收我方闪避)
    
    // 【核心机制】：当我们强行没收闪避时，设定的强制扣血量 (真伤)
    // 建议设置为 30~60 之间，足以让高闪避的 SMG/HG 快速掉血
    PENALTY_DAMAGE: 45 
};

// ----------------------------------------------------------------
// 遥测日志 (Telemetry)
// ----------------------------------------------------------------
var logLimits = { HIT: 0, DODGE: 0, CRIT: 0, ARMOR: 0, DMG: 0 };
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

    send({ type: "info", payload: "[JS] Weight Training V7 (Outcome & Penalty Damage) Online." });

    var ptr_GetDamage = gameAssembly.add(rva_GetDamage);
    var GetTeamId = new NativeFunction(gameAssembly.add(rva_GetTeamId), 'int32', ['pointer', 'pointer']);

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
                    // 我方攻击：施加 DMG, HIT, CRIT
                    // ============================================
                    var debuffedDmg = Math.floor(calcDamage * DEBUFF.DMG.num / DEBUFF.DMG.den);

                    // 1. 削弱命中：强行变 Miss
                    if (isMiss === 0) {
                        var hitPower = DEBUFF.HIT.num / DEBUFF.HIT.den;
                        if (Math.random() > hitPower) {
                            this.ptrIsMiss.writeU8(1); 
                            isMiss = 1;
                            debuffedDmg = 0; // 必须同时把伤害归0，才能完美呈现Miss
                            logThrottled("HIT", "Forced a MISS! Target evaded our attack.");
                        }
                    }

                    // 2. 削弱暴击：撤销 UI 暴击，并且重砍伤害！
                    if (isMiss === 0 && isCrit === 1) {
                        var critPower = DEBUFF.CRIT.num / DEBUFF.CRIT.den;
                        if (Math.random() > critPower) {
                            this.ptrIsCrit.writeU8(0); 
                            // 【暴击修复核心】：不仅不显示暴击，而且把现有伤害强行再打个 6 折！
                            debuffedDmg = Math.floor(debuffedDmg * 0.6); 
                            logThrottled("CRIT", "Crit nullified! Massive damage multiplier crushed.");
                        }
                    }

                    // 3. 最终写入伤害
                    if (debuffedDmg !== calcDamage) {
                        retval.replace(debuffedDmg);
                        if (debuffedDmg > 0) {
                            logThrottled("DMG", "Damage nerfed: " + calcDamage + " -> " + debuffedDmg);
                        }
                    }

                } else {
                    // ============================================
                    // 敌方攻击：施加 ARMOR, DODGE (模拟靶场挨打)
                    // ============================================
                    
                    // 1. 削弱护甲：放大我们受到的伤害
                    if (isMiss === 0 && calcDamage > 0) {
                        var armorFactor = DEBUFF.ARMOR.den / DEBUFF.ARMOR.num; 
                        var amplifiedDmg = Math.floor(calcDamage * armorFactor);
                        if (amplifiedDmg !== calcDamage) {
                            retval.replace(amplifiedDmg);
                            logThrottled("ARMOR", "Incoming damage amplified: " + calcDamage + " -> " + amplifiedDmg);
                        }
                    }

                    // 2. 削弱闪避：强制没收 Miss，并施加【真伤惩罚】！
                    if (isMiss === 1) {
                        var dodgePower = DEBUFF.DODGE.num / DEBUFF.DODGE.den; // 此时为 0
                        if (Math.random() > dodgePower) {
                            // 【闪避修复核心】
                            this.ptrIsMiss.writeU8(0); // 取消闪避UI
                            retval.replace(DEBUFF.PENALTY_DAMAGE); // 强行塞入真实的扣血量！
                            logThrottled("DODGE", "Dodge failed! Took " + DEBUFF.PENALTY_DAMAGE + " penalty true damage!");
                        }
                    }
                }
            } catch (e) {}
        }
    });

    send({ type: "info", payload: "[JS] V7 System Armed. God Mode inverted into Hell Mode successfully." });
}

setTimeout(hook, 1000);