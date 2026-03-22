// hook.js

// ----------------------------------------------------------------
// Offsets 
// ----------------------------------------------------------------

/* 
    Damage & IFF

    // Namespace: GF.Battle
    public class CharacterSkillImpl : SkillImpl
        public override int GetDamage(BattleCharacterData target, BattleSkillCfgEx skillCfg, BattleHurtCfg hurtCfg, out bool isCrit, out bool isMiss, out FP defPercent, out ArmorDefenseType adType) { }
        public override int GetTeamId() { }
*/
var rva_GetDamage       = 0x2818630; // CharacterSkillImpl$$GetDamage
var rva_GetTeamId       = 0x281A280; // CharacterSkillImpl$$GetTeamId

// ----------------------------------------------------------------
// Debuff Configuration (负重训练系数)
// ----------------------------------------------------------------
var DEBUFF = {
    ENABLED: true,
    
/* --- Part I --- */
    HIT:   { num: 5, den: 10 },     // 命中率
    DMG:   { num: 5, den: 10 },     // (最终?)伤害
    ARMOR: { num: 7, den: 10 },     // 护甲

/* --- Part I (存疑部分) --- */
    CRIT:  { num: 0, den: 10 },     // 暴击率
    // 当暴击发生时，写一个固定的百分比模拟未暴击，后续还需要调整
    CRTI_DAMAGE: 0.8,

    DODGE: { num: 5, den: 10 },     // 闪避率
    /* 
    游戏通过`retval`来统一管理伤害和Miss: 
    当retval=0时，UI显示Miss；当retval>0时，显示伤害
    这里我们暂时写入一个固定值来模拟闪避失败，后续需要反向寻找完整的伤害计算逻辑
    */
    PENALTY_DAMAGE: 45              
};

// ----------------------------------------------------------------
// Logs
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
                    // T-Dolls: Applying DMG, HIT, CRIT
                    // ============================================
                    var debuffedDmg = Math.floor(calcDamage * DEBUFF.DMG.num / DEBUFF.DMG.den);

                    // 1. Hit Rate
                    if (isMiss === 0) {
                        var hitPower = DEBUFF.HIT.num / DEBUFF.HIT.den;
                        if (Math.random() > hitPower) {
                            this.ptrIsMiss.writeU8(1); 
                            // Miss's Label
                            isMiss = 1;
                            // Dmg set to zero to show `Miss`
                            debuffedDmg = 0;
                            logThrottled("HIT", "Forced a MISS! Target evaded our attack.");
                        }
                    }

                    // 2. Critical Rate
                    if (isMiss === 0 && isCrit === 1) {
                        var critPower = DEBUFF.CRIT.num / DEBUFF.CRIT.den;
                        if (Math.random() > critPower) {
                            this.ptrIsCrit.writeU8(0); 
                            // 【暴击修复核心】：不仅不显示暴击，而且把现有伤害强行再打个 6 折！
                            debuffedDmg = Math.floor(debuffedDmg * DEBUFF.CRTI_DAMAGE); 
                            logThrottled("CRIT", "Crit nullified! Massive damage multiplier crushed.");
                        }
                    }

                    // 3. (Final?) Dmg
                    if (debuffedDmg !== calcDamage) {
                        retval.replace(debuffedDmg);
                        if (debuffedDmg > 0) {
                            logThrottled("DMG", "Damage nerfed: " + calcDamage + " -> " + debuffedDmg);
                        }
                    }

                } else {
                    // ============================================
                    // Enemy：ARMOR, DODGE
                    // ============================================
                    
                    // 1. Armor (Dmg Amplifier)
                    if (isMiss === 0 && calcDamage > 0) {
                        var armorFactor = DEBUFF.ARMOR.den / DEBUFF.ARMOR.num; 
                        var amplifiedDmg = Math.floor(calcDamage * armorFactor);
                        if (amplifiedDmg !== calcDamage) {
                            retval.replace(amplifiedDmg);
                            logThrottled("ARMOR", "Incoming damage amplified: " + calcDamage + " -> " + amplifiedDmg);
                        }
                    }

                    // 2. Dodge (Confiscate Miss and inflict [PENALTY_DAMAGE])
                    if (isMiss === 1) {
                        var dodgePower = DEBUFF.DODGE.num / DEBUFF.DODGE.den;
                        if (Math.random() > dodgePower) {
                            this.ptrIsMiss.writeU8(0);
                            retval.replace(DEBUFF.PENALTY_DAMAGE); // 暂时写入固定值
                            logThrottled("DODGE", "Dodge failed! Took " + DEBUFF.PENALTY_DAMAGE + " penalty true damage!");
                        }
                    }
                }
            } catch (e) {}
        }
    });

    send({ type: "info", payload: "[JS] System Armed. God Mode inverted into Hell Mode successfully." });
}

setTimeout(hook, 1000);