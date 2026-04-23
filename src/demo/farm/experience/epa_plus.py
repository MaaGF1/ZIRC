import sys
import re
import time
import threading
import copy
import json
import os
from gflzirc import (
    GFLClient, GFLProxy, set_windows_proxy,
    SERVERS, STATIC_KEY, DEFAULT_SIGN,
    API_MISSION_COMBINFO, API_MISSION_START,
    API_MISSION_TEAM_MOVE, API_MISSION_END_TURN,
    API_MISSION_START_ENEMY_TURN, API_MISSION_END_ENEMY_TURN,
    API_MISSION_START_TURN, API_MISSION_ABORT, API_GUN_RETIRE,
    API_MISSION_SUPPLY, API_MISSION_BATTLE_FINISH,
)

try:
    from gflzirc import API_INDEX_INDEX
except ImportError:
    API_INDEX_INDEX = "Index/index"

# 强制覆盖装备拆解接口。
# 不再信任 gflzirc 内置常量，避免其仍然指向错误的 "3000/Equip_retire"。
API_EQUIP_RETIRE = "3000/Equip/retire"

try:
    from gflzirc import API_INDEX_HOME
except ImportError:
    API_INDEX_HOME = "3000/Index/home"

try:
    from gflzirc import API_SANGVIS_GASHA
except ImportError:
    API_SANGVIS_GASHA = "3000/Sangvis_gasha"

CONFIG = {
# === Authentication & Connection ===
    "USER_UID": "_InputYourID_",
    "SIGN_KEY": DEFAULT_SIGN,
    "BASE_URL": SERVERS["SOP"],
    "PROXY_PORT": 12335,

# === Farm Loop Settings ===
    "MACRO_LOOPS": 200,
    # 5个掉落（一关）*10次循环，拆一次（大概50-60个左右）
    "MISSIONS_PER_RETIRE": 8,

# === Mission Specific Config ===
    # EPA: EX1
    "MISSION_ID": 145,
    "START_SPOT": 97061,
    "ROUTE": [97039, 97040, 97041, 97036, 97031],

    # 当前菜单选择（后续可继续扩展为真正的关卡配置）
    "SELECTED_DIFFICULTY": None,
    "SELECTED_STAGE": None,
    "SELECTED_TARGET": None,
    "SELECTED_TARGET_LABEL": None,
    "SELECTED_BATTLE_TEMPLATE": None,
    "SINGLE_GUN_MODE": False,
    "SINGLE_GUN_INDEX": 0,
    "MODE_SELECTED_EARLY": False,
    "MODE_NAME": "single",   # single=打捞, team=练级
    "TRAIN_TEAM_COUNT": 1,
    "TRAIN_SCHEDULE_MODE": "full",   # full=当前梯队练到全满再切下一个, equal=均等练级轮转
    "CURRENT_TRAIN_TEAM_INDEX": 0,
    "STOP_ON_MAX_LEVEL": True,
    "AUTO_MONITOR_MODE": False,
    "AUTO_CAPTURE_EXPECTED_COUNT": 1,
    "INDEX_FETCH_READY": False,

    # 自动拆解保护：
    # 1) 会自动保护当前关卡菜单里“已选择目标”的配置 ID
    # 2) 也会额外保护下面手动填写的 gun_id
    "PROTECTED_DROP_GUN_IDS": [],

    # 当连续两次自动拆解后仍然提示仓库空间不足时，自动停机
    "STOP_AFTER_RETIRE_NO_SPACE_TIMES": 2,
    "ENABLE_FILTER_PROTECTION": True,

    # 下面的 TEAM_ID / FAIRY_ID / GUNS 仅为占位。
    # 实际运行时建议通过抓取并解析 Index/index 自动填充。
    # Target Device Hash 自己抓
    "USER_DEVICE": "1145141919810",

    # === Team Config ===
    # Echelon ID
    # 梯队ID
    "TEAM_ID": 1,

    # Target Fairy UID (Set to 0 or None if no fairy is equipped)
    "FAIRY_ID": 159357,

      "GUNS": [
        {"id": 11233, "life": 444},
        {"id": 44566, "life": 1130},
        {"id": 77899, "life": 420},
        {"id": 336699, "life": 300},
        {"id": 114477, "life": 248}
    ]
}

NORMAL_STAGE_OPTIONS = [f"A-{i}" for i in range(1, 11)]
EMERGENCY_STAGE_OPTIONS = [f"A-{i}" for i in range(1, 7)]
NIGHT_STAGE_OPTIONS = [f"A-{i}" for i in range(1, 7)]

NORMAL_STAGE_DATA = {
    "A-1": {
        "MISSION_ID": 135,
        "DEFAULT_START_SPOT": 89761,
        "OPTIONS": {
            "-1": {"label": "M1887&M1A1", "start_spot": 89761, "route": [89755, 89756, 89757, 89758, 89759]},
            "-2": {"label": "FN-57&FMG-9", "start_spot": 89761, "route": [89750, 89751, 89752, 89753, 89754]},
            "-3": {"label": "OTs-14&格洛克17", "start_spot": 89761, "route": [89745, 89746, 89747, 89748, 89749]},
            "-4": {"label": "PP-19&56式半", "start_spot": 89761, "route": [89740, 89741, 89742, 89743, 89744]},
            "-5": {"label": "SPP-1&M21", "start_spot": 89761, "route": [89735, 89736, 89737, 89738, 89739]},
        },
    },
    "A-2": {
        "MISSION_ID": 136,
        "DEFAULT_START_SPOT": 89790,
        "OPTIONS": {
            "-1": {"label": "UMP40&谢尔久科夫", "start_spot": 89790, "route": [89764, 89765, 89766, 89767, 89768]},
            "-2": {"label": "KLIN&S-SASS", "start_spot": 89790, "route": [89769, 89770, 89771, 89772, 89773]},
            "-3": {"label": "CZ75&M249 SAW", "start_spot": 89790, "route": [89774, 89775, 89776, 89777, 89778]},
            "-4": {"label": "ART556&RPD", "start_spot": 89790, "route": [89779, 89780, 89781, 89782, 89783]},
            "-5": {"label": "DSR-50&CZ-805", "start_spot": 89790, "route": [89784, 89785, 89786, 89787, 89788]},
        },
    },
    "A-3": {
        "MISSION_ID": 137,
        "DEFAULT_START_SPOT": 89819,
        "OPTIONS": {
            "-1": {"label": "Ak 5&6P62", "start_spot": 89819, "route": [89793, 89794, 89795, 89796, 89797]},
            "-2": {"label": "XM3&PSM", "start_spot": 89819, "route": [89798, 89799, 89800, 89801, 89802]},
            "-3": {"label": "JS05&EVO 3", "start_spot": 89819, "route": [89803, 89804, 89805, 89806, 89807]},
            "-4": {"label": "芭莉斯塔&59式", "start_spot": 89819, "route": [89808, 89809, 89810, 89811, 89812]},
            "-5": {"label": "HK21&AR70", "start_spot": 89819, "route": [89813, 89814, 89815, 89816, 89817]},
        },
    },
    "A-4": {
        "MISSION_ID": 138,
        "DEFAULT_START_SPOT": 89848,
        "OPTIONS": {
            "-1": {"label": "雷电&SCW", "start_spot": 89848, "route": [89822, 89823, 89824, 89825, 89826]},
            "-2": {"label": "蜜獾&ASh-12.7", "start_spot": 89848, "route": [89827, 89828, 89829, 89830, 89831]},
            "-3": {"label": "SRS&MT-9", "start_spot": 89848, "route": [89832, 89833, 89834, 89835, 89836]},
            "-4": {"label": "AUG&SSG 69", "start_spot": 89848, "route": [89837, 89838, 89839, 89840, 89841]},
            "-5": {"label": "TAC-50&HK45", "start_spot": 89848, "route": [89842, 89843, 89844, 89845, 89846]},
        },
    },
    "A-5": {
        "MISSION_ID": 139,
        "DEFAULT_START_SPOT": 89877,
        "OPTIONS": {
            "-1": {"label": "CZ2000&P226", "start_spot": 89877, "route": [89851, 89852, 89853, 89854, 89855]},
            "-2": {"label": "Cx4 风暴&M12", "start_spot": 89877, "route": [89856, 89857, 89858, 89859, 89860]},
            "-3": {"label": "PM-06&八一式马", "start_spot": 89877, "route": [89861, 89862, 89863, 89864, 89865]},
            "-4": {"label": "蟒蛇&TMP", "start_spot": 89877, "route": [89866, 89867, 89868, 89869, 89870]},
            "-5": {"label": "AK-74U&wz.29", "start_spot": 89877, "route": [89871, 89872, 89873, 89874, 89875]},
        },
    },
    "A-6": {
        "MISSION_ID": 140,
        "DEFAULT_START_SPOT": 89906,
        "OPTIONS": {
            "-1": {"label": "Mk 12&CZ52", "start_spot": 89906, "route": [89880, 89881, 89882, 89883, 89884]},
            "-2": {"label": "A-91&OTs-39", "start_spot": 89906, "route": [89885, 89886, 89887, 89888, 89889]},
            "-3": {"label": "M870&T65", "start_spot": 89906, "route": [89890, 89891, 89892, 89893, 89894]},
            "-4": {"label": "M82A1&HK23", "start_spot": 89906, "route": [89895, 89896, 89897, 89898, 89899]},
            "-5": {"label": "JS 9&猎豹M1", "start_spot": 89906, "route": [89900, 89901, 89902, 89903, 89904]},
        },
    },
    "A-7": {
        "MISSION_ID": 141,
        "DEFAULT_START_SPOT": 89935,
        "OPTIONS": {
            "-1": {"label": "Mk46&GSh-18", "start_spot": 89935, "route": [89909, 89910, 89911, 89912, 89913]},
            "-2": {"label": "KSVK&Model L", "start_spot": 89935, "route": [89914, 89915, 89916, 89917, 89918]},
            "-3": {"label": "P22&SM-1", "start_spot": 89935, "route": [89919, 89920, 89921, 89922, 89923]},
            "-4": {"label": "HS2000&T77", "start_spot": 89935, "route": [89924, 89925, 89926, 89927, 89928]},
            "-5": {"label": "X95&MP-443", "start_spot": 89935, "route": [89929, 89930, 89931, 89932, 89933]},
        },
    },
    "A-8": {
        "MISSION_ID": 142,
        "DEFAULT_START_SPOT": 89964,
        "OPTIONS": {
            "-1": {"label": "UKM-2000&RT-20", "start_spot": 89964, "route": [89938, 89939, 89940, 89941, 89942]},
            "-2": {"label": "SSG3000&62式", "start_spot": 89964, "route": [89943, 89944, 89945, 89946, 89947]},
            "-3": {"label": "刘易斯&OBR", "start_spot": 89964, "route": [89948, 89949, 89950, 89951, 89952]},
            "-4": {"label": "PM-9&MP-448", "start_spot": 89964, "route": [89953, 89954, 89955, 89956, 89957]},
            "-5": {"label": "R93&03式", "start_spot": 89964, "route": [89958, 89959, 89960, 89961, 89962]},
        },
    },
    "A-9": {
        "MISSION_ID": 143,
        "DEFAULT_START_SPOT": 89993,
        "OPTIONS": {
            "-1": {"label": "M1895 CB&马盖尔", "start_spot": 89993, "route": [89967, 89968, 89969, 89970, 89971]},
            "-2": {"label": "MAT-49&HK33", "start_spot": 89993, "route": [89972, 89973, 89974, 89975, 89976]},
            "-3": {"label": "沙漠之鹰&TEC-9", "start_spot": 89993, "route": [89977, 89978, 89979, 89980, 89981]},
            "-4": {"label": "ACR&侦察者", "start_spot": 89993, "route": [89982, 89983, 89984, 89985, 89986]},
            "-5": {"label": "Kord&隼", "start_spot": 89993, "route": [89987, 89988, 89989, 89990, 89991]},
        },
    },
    "A-10": {
        "MISSION_ID": 144,
        "DEFAULT_START_SPOT": 97026,
        "OPTIONS": {
            "-1": {"label": "SL8&K3", "start_spot": 97026, "route": [97020, 97021, 97022, 97023, 97024]},
            "-2": {"label": "韦伯利&T-CMS", "start_spot": 97026, "route": [97015, 97016, 97017, 97018, 97019]},
            "-3": {"label": "R5&MP41", "start_spot": 97026, "route": [97010, 97011, 97012, 97013, 97014]},
            "-4": {"label": "M82&CPS-12", "start_spot": 97026, "route": [97005, 97006, 97007, 97008, 97009]},
            "-5": {"label": "CF05&VP70", "start_spot": 97026, "route": [97000, 97001, 97002, 97003, 97004]},
        },
    },
}

EMERGENCY_STAGE_DATA = {
    "A-1": {
        "MISSION_ID": 145,
        "START_SPOTS": {"-1": 97061, "-2": 97061, "-3": 97061, "-4": 97059, "-5": 97059, "-6": 97059},
        "OPTIONS": {
            "-1": {"label": "防卫者&Vepr", "route": [97029, 97030, 97031, 97032, 97033]},
            "-2": {"label": "蒙德拉贡M1908&高标10型", "route": [97034, 97035, 97036, 97037, 97038]},
            "-3": {"label": "PM1910&CAR", "route": [97039, 97040, 97041, 97042, 97043]},
            "-4": {"label": "卢萨&英萨斯", "route": [97044, 97045, 97046, 97047, 97048]},
            "-5": {"label": "AUG SMG&Zas M76", "route": [97049, 97050, 97051, 97052, 97053]},
            "-6": {"label": "刘氏步枪&43M", "route": [97054, 97055, 97056, 97057, 97058]},
        },
    },
    "A-2": {
        "MISSION_ID": 146,
        "START_SPOTS": {"-1": 97095, "-2": 97095, "-3": 97095, "-4": 97093, "-5": 97093, "-6": 97093},
        "OPTIONS": {
            "-1": {"label": "德林加&CAR", "route": [97063, 97064, 97065, 97066, 97067]},
            "-2": {"label": "菲德洛夫&MAS-38", "route": [97068, 97069, 97070, 97071, 97072]},
            "-3": {"label": "APC556&C14", "route": [97073, 97074, 97075, 97076, 97077]},
            "-4": {"label": "VHS&43M", "route": [97078, 97079, 97080, 97081, 97082]},
            "-5": {"label": "蜂鸟&Vepr", "route": [97083, 97084, 97085, 97086, 97087]},
            "-6": {"label": "VP1915&高标10型", "route": [97088, 97089, 97090, 97091, 97092]},
        },
    },
    "A-3": {
        "MISSION_ID": 147,
        "START_SPOTS": {"-1": 97129, "-2": 97129, "-3": 97129, "-4": 97127, "-5": 97127, "-6": 97127},
        "OPTIONS": {
            "-1": {"label": "FARA 83&WKp", "route": [97097, 97098, 97099, 97100, 97101]},
            "-2": {"label": "PPQ&StG-940", "route": [97102, 97103, 97104, 97105, 97106]},
            "-3": {"label": "沙维奇99型&高标10型", "route": [97107, 97108, 97109, 97110, 97111]},
            "-4": {"label": "TKB-408&CAR", "route": [97112, 97113, 97114, 97115, 97116]},
            "-5": {"label": "SP9&MAS-38", "route": [97117, 97118, 97119, 97120, 97121]},
            "-6": {"label": "KH2002&C14", "route": [97122, 97123, 97124, 97125, 97126]},
        },
    },
    "A-4": {
        "MISSION_ID": 148,
        "START_SPOTS": {"-1": 97163, "-2": 97163, "-3": 97163, "-4": 97161, "-5": 97161, "-6": 97161},
        "OPTIONS": {
            "-1": {"label": "TF-Q&GM6 Lynx", "route": [97131, 97132, 97133, 97134, 97135]},
            "-2": {"label": "LS26&TS12", "route": [97136, 97137, 97138, 97139, 97140]},
            "-3": {"label": "MG338&MAS-38", "route": [97141, 97142, 97143, 97144, 97145]},
            "-4": {"label": "芮诺&C14", "route": [97146, 97147, 97148, 97149, 97150]},
            "-5": {"label": "斯特林&WKp", "route": [97151, 97152, 97153, 97154, 97155]},
            "-6": {"label": "QBZ-191&StG-940", "route": [97156, 97157, 97158, 97159, 97160]},
        },
    },
    "A-5": {
        "MISSION_ID": 149,
        "START_SPOTS": {"-1": 97197, "-2": 97197, "-3": 97197, "-4": 97195, "-5": 97195, "-6": 97195},
        "OPTIONS": {
            "-1": {"label": "P290&QSB-91", "route": [97165, 97166, 97167, 97168, 97169]},
            "-2": {"label": "Saiga 308&SUB-2000", "route": [97170, 97171, 97172, 97173, 97174]},
            "-3": {"label": "M327&WKp", "route": [97175, 97176, 97177, 97178, 97179]},
            "-4": {"label": "AR-18&StG-940", "route": [97180, 97181, 97182, 97183, 97184]},
            "-5": {"label": "M240L&GM6 Lynx", "route": [97185, 97186, 97187, 97188, 97189]},
            "-6": {"label": "Jatimatic&TS12", "route": [97190, 97191, 97192, 97193, 97194]},
        },
    },
    "A-6": {
        "MISSION_ID": 150,
        "START_SPOTS": {"-1": 97221, "-2": 97221, "-3": 97221, "-4": 97239, "-5": 97239, "-6": 97239},
        "OPTIONS": {
            "-1": {"label": "CMR-30&英萨斯", "route": [97199, 97200, 97201, 97202, 97203]},
            "-2": {"label": "VP9&Zas M76", "route": [97204, 97205, 97206, 97207, 97208]},
            "-3": {"label": "VRB&GM6 Lynx", "route": [97209, 97210, 97211, 97212, 97213]},
            "-4": {"label": "LAMG&TS12", "route": [97214, 97215, 97216, 97217, 97218]},
            "-5": {"label": "TPS&QSB-91", "route": [97219, 97220, 97221, 97222, 97223]},
            "-6": {"label": "P2000&SUB-2000", "route": [97224, 97225, 97226, 97227, 97228]},
        },
    },
}

NIGHT_STAGE_DATA = {
    "A-1": {
        "MISSION_ID": 151,
        "START_SPOTS": {
            "-1": 97255,
            "-2": 97255,
            "-3": 97253,
            "-4": 97253,
        },
        "OPTIONS": {
            "-1": {"label": "国家竞赛穿甲弹", "route": [97233, 97234, 97235, 97236, 97237]},
            "-2": {"label": ".300BLK高速弹", "route": [97238, 97239, 97240, 97241, 97242]},
            "-3": {"label": "Titan火控芯片", "route": [97243, 97244, 97245, 97246, 97247]},
            "-4": {"label": "GSG UX外骨骼", "route": [97248, 97249, 97250, 97251, 97252]},
        },
    },
    "A-2": {
        "MISSION_ID": 152,
        "START_SPOTS": {
            "-1": 97279,
            "-2": 97279,
            "-3": 97277,
            "-4": 97277,
        },
        "OPTIONS": {
            "-1": {"label": "Hayha记忆芯片", "route": [97257, 97258, 97259, 97260, 97261]},
            "-2": {"label": "特殊战机动护甲", "route": [97262, 97263, 97264, 97265, 97266]},
            "-3": {"label": "无限弹链箱", "route": [97267, 97268, 97269, 97270, 97271]},
            "-4": {"label": "FÉLIN系统瞄具", "route": [97272, 97273, 97274, 97275, 97276]},
        },
    },
    "A-3": {
        "MISSION_ID": 153,
        "START_SPOTS": {
            "-1": 97303,
            "-2": 97303,
            "-3": 97301,
            "-4": 97301,
        },
        "OPTIONS": {
            "-1": {"label": "APS专用枪托", "route": [97281, 97282, 97283, 97284, 97285]},
            "-2": {"label": "战术耳机", "route": [97286, 97287, 97288, 97289, 97290]},
            "-3": {"label": "星条领带", "route": [97291, 97292, 97293, 97294, 97295]},
            "-4": {"label": "7.62纳甘弹", "route": [97296, 97297, 97298, 97299, 97300]},
        },
    },
    "A-4": {
        "MISSION_ID": 154,
        "START_SPOTS": {
            "-1": 97327,
            "-2": 97327,
            "-3": 97325,
            "-4": 97325,
        },
        "OPTIONS": {
            "-1": {"label": "司登手枪弹", "route": [97305, 97306, 97307, 97308, 97309]},
            "-2": {"label": "7.63毛瑟弹", "route": [97310, 97311, 97312, 97313, 97314]},
            "-3": {"label": "pks-07瞄准镜", "route": [97315, 97316, 97317, 97318, 97319]},
            "-4": {"label": "StG瞄准镜", "route": [97320, 97321, 97322, 97323, 97324]},
        },
    },
    "A-5": {
        "MISSION_ID": 155,
        "START_SPOTS": {
            "-1": 97351,
            "-2": 97351,
            "-3": 97349,
            "-4": 97349,
        },
        "OPTIONS": {
            "-1": {"label": "G3特制弹", "route": [97329, 97330, 97331, 97332, 97333]},
            "-2": {"label": "SC特制弹", "route": [97334, 97335, 97336, 97337, 97338]},
            "-3": {"label": "牛仔帽", "route": [97339, 97340, 97341, 97342, 97343]},
            "-4": {"label": "8×42瞄准镜", "route": [97344, 97345, 97346, 97347, 97348]},
        },
    },
    "A-6": {
        "MISSION_ID": 156,
        "START_SPOTS": {
            "-1": 97368,
            "-2": 97368,
            "-3": 97368
        },
        "OPTIONS": {
            "-1": {"label": "皇家作战披风", "route": [97353, 97354, 97355, 97356, 97357]},
            "-2": {"label": "KR步枪弹", "route": [97358, 97359, 97360, 97361, 97362]},
            "-3": {"label": "PK-A内红点瞄准镜", "route": [97363, 97364, 97365, 97366, 97367]}
        }
    }
}

EQUIP_ID_OVERRIDE = {
    # 夜战专属装备 / 已确认或高置信度映射
    "国家竞赛穿甲弹": 59,
    ".300BLK高速弹": 60,
    "Titan火控芯片": 112,
    "GSG UX外骨骼": 62,

    "Hayha记忆芯片": 86,
    "特殊战机动护甲": 91,
    "无限弹链箱": 107,
    "FÉLIN系统瞄具": 119,

    # APS专用枪托 暂未最终确认，先留空
    "战术耳机": 165,
    "星条领带": 375,
    "7.62纳甘弹": 486,

    "司登手枪弹": 487,
    "7.63毛瑟弹": 488,
    "pks-07瞄准镜": 489,
    "StG瞄准镜": 490,

    "G3特制弹": 491,
    "SC特制弹": 492,
    "牛仔帽": 122,
    "8×42瞄准镜": 494,

    "皇家作战披风": 160,
    "KR步枪弹": 105,
    "PK-A内红点瞄准镜": 497,
}

def resolve_equip_id_by_name(name: str):
    if name in EQUIP_ID_OVERRIDE:
        return int(EQUIP_ID_OVERRIDE[name])
    return None


A10_SINGLE_BATTLE_TEMPLATE = {
    "1000": {
        "10": 1228,
        "11": 1228,
        "12": 1228,
        "13": 1228,
        "15": 12006,
        "16": 0,
        "17": 106,
        "33": 10018,
        "40": 15,
        "18": 0,
        "19": 0,
        "20": 0,
        "21": 0,
        "22": 0,
        "23": 0,
        "24": 3900,
        "25": 0,
        "26": 3900,
        "27": 4,
        "34": 84,
        "35": 84,
        "41": 260,
        "42": 0,
        "43": 0,
        "44": 0
    },
    "1001": {},
    "1005": {},
    "1007": {},
    "1008": {},
    "1009": {}
}

MENU_STATE = {
    "selection_unlocked": False,
    "difficulty": None,
    "stage": None,
    "awaiting_gun_mode": False,
    "awaiting_stop_on_max": False,
    "awaiting_filter_protection": False,
    "awaiting_run_confirm": False,
}

current_worker_thread = None
worker_mode = None
proxy_instance = None

stop_macro_flag = False
stop_micro_flag = False

AUTO_CAPTURE_STATE = {
    "team_id": None,
    "fairy_id": None,
    "guns": [],
    "completed": False,
}

CAPTURED_TEAM_CONFIGS = []
TEAM_SWITCH_PENDING = False
TRAIN_COMPLETED_TEAM_INDICES = set()

DROPPED_UID_TO_GUN_ID = {}
DROPPED_UID_TO_EQUIP_ID = {}
RETIRE_NO_SPACE_COUNT = 0

RUN_STATS = {
    "start_time": None,
    "end_time": None,
    "target_counts": {},
}




GUN_CATALOG_CACHE = None
GUN_NAME_ALIAS = {
    "格洛克17": "Glock17",
    "56式半": "56-1",
    "谢尔久科夫": "Serdyukov",
    "S-SASS": "SSGSSASS",
    "芭莉斯塔": "Ballista",
    "59式": "59type",
    "雷电": "Thunder",
    "蜜獾": "HoneyBadger",
    "Cx4 风暴": "Cx4Storm",
    "八一式马": "Type81R",
    "蟒蛇": "Python",
    "猎豹M1": "CheetahM1",
    "62式": "Type62",
    "刘易斯": "Lewis",
    "03式": "03type",
    "马盖尔": "Magal",
    "沙漠之鹰": "Desert Eagle",
    "侦察者": "Scout",
    "隼": "Falcon",
    "防卫者": "Defender",
    "蒙德拉贡M1908": "Mondragon M1908",
    "高标10型": "General Liu",
    "卢萨": "Lusa",
    "英萨斯": "INSAS",
    "刘氏步枪": "Liu",
    "德林加": "De Lisle",
    "菲德洛夫": "Fedorov",
    "沙维奇99型": "Savage99",
    "芮诺": "Reno",
    "斯特林": "Sterling",
    "韦伯利": "Webley",
    "CPS-12": "DP12",
    "CF05": "CF-05",
    "FN-57": "Five-seveN",
    "AK 5": "Ak 5",
    "英萨斯": "INSAS",
    "防卫者": "Defender",
    "刘氏步枪": "Liu Rifle",
    "AUG SMG": "AUG Para",
    "高标10型": "General Liu",
    "TF-Q": "TF Q",
    "6P62": "6P62",
    "Ak 5": "AK 5",
}

GUN_ID_OVERRIDE = {
    "6P62": 138,
    "Ak 5": 187,
    "AK 5": 187,
    "雷电": 202,
    "SCW": 169,
}

def load_gun_catalog():
    global GUN_CATALOG_CACHE
    if GUN_CATALOG_CACHE is not None:
        return GUN_CATALOG_CACHE

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = ["gun.json", "gun1(1).json", "gun1.json"]

    search_paths = []
    for name in candidates:
        search_paths.append(name)
        search_paths.append(os.path.join(script_dir, name))

    seen = set()
    for fp in search_paths:
        if fp in seen:
            continue
        seen.add(fp)
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    GUN_CATALOG_CACHE = json.load(f)
                    print("[*] 已加载枪械目录：%s" % fp)
                    return GUN_CATALOG_CACHE
            except Exception as e:
                print("[!] 读取枪械目录失败：%s | %s" % (fp, e))

    print("[!] 未找到 gun.json / gun1(1).json / gun1.json，自动拆解保护将无法按目标名解析。")
    GUN_CATALOG_CACHE = []
    return GUN_CATALOG_CACHE


def normalize_gun_name(name: str) -> str:
    if not name:
        return ""
    return str(name).lower().replace(" ", "").replace("-", "").replace(".", "")


def resolve_gun_id_by_name(name: str):
    candidates = [name]
    alias = GUN_NAME_ALIAS.get(name)
    if alias:
        candidates.append(alias)

    for cand in candidates:
        if cand in GUN_ID_OVERRIDE:
            return int(GUN_ID_OVERRIDE[cand])

    catalog = load_gun_catalog()
    if not catalog:
        return None

    best_id = None
    for cand in candidates:
        n = normalize_gun_name(cand)
        for gun in catalog:
            for field in ("en_name", "code", "name"):
                value = normalize_gun_name(gun.get(field, ""))
                if not value:
                    continue
                if n == value:
                    return int(gun["id"])

        for gun in catalog:
            values = [normalize_gun_name(gun.get(field, "")) for field in ("en_name", "code", "name")]
            values = [v for v in values if v]
            if any(n in value or value in n for value in values):
                gid = int(gun["id"])
                if best_id is None or gid < best_id:
                    best_id = gid

    return best_id


def get_stage_data(difficulty: str, stage: str):
    if difficulty == "普通":
        return NORMAL_STAGE_DATA.get(stage)
    if difficulty == "紧急":
        return EMERGENCY_STAGE_DATA.get(stage)
    if difficulty == "夜战":
        return NIGHT_STAGE_DATA.get(stage)
    return None


def get_stage_options(difficulty: str, stage: str):
    stage_data = get_stage_data(difficulty, stage)
    if not stage_data:
        return {}
    return stage_data.get("OPTIONS", {})


def split_target_label(label: str):
    return [part.strip() for part in str(label).split("&") if part.strip()]

def reset_auto_capture_state():
    AUTO_CAPTURE_STATE["team_id"] = None
    AUTO_CAPTURE_STATE["fairy_id"] = None
    AUTO_CAPTURE_STATE["guns"] = []
    AUTO_CAPTURE_STATE["completed"] = False


def reset_captured_team_configs():
    CAPTURED_TEAM_CONFIGS.clear()
    CONFIG["CURRENT_TRAIN_TEAM_INDEX"] = 0


def get_current_team_config():
    if CONFIG.get("MODE_NAME") == "team" and CAPTURED_TEAM_CONFIGS:
        idx = CONFIG.get("CURRENT_TRAIN_TEAM_INDEX", 0)
        idx = max(0, min(idx, len(CAPTURED_TEAM_CONFIGS) - 1))
        return CAPTURED_TEAM_CONFIGS[idx]
    return {
        "team_id": CONFIG["TEAM_ID"],
        "fairy_id": CONFIG["FAIRY_ID"],
        "guns": CONFIG["GUNS"],
    }


def get_current_team_id():
    return get_current_team_config()["team_id"]


def get_current_fairy_id():
    return get_current_team_config()["fairy_id"]


def advance_to_next_training_team():
    global TEAM_SWITCH_PENDING
    if CONFIG.get("MODE_NAME") != "team":
        return
    switch_to_next_available_training_team("当前练级梯队已全部满级")


def reset_training_progress():
    TRAIN_COMPLETED_TEAM_INDICES.clear()
    CONFIG["CURRENT_TRAIN_TEAM_INDEX"] = 0


def mark_current_training_team_completed():
    idx = CONFIG.get("CURRENT_TRAIN_TEAM_INDEX", 0)
    TRAIN_COMPLETED_TEAM_INDICES.add(idx)


def get_active_training_team_indices():
    return [i for i in range(len(CAPTURED_TEAM_CONFIGS)) if i not in TRAIN_COMPLETED_TEAM_INDICES]


def switch_to_next_available_training_team(reason: str = ""):
    global TEAM_SWITCH_PENDING, stop_macro_flag, stop_micro_flag
    if CONFIG.get("MODE_NAME") != "team":
        return

    active_indices = get_active_training_team_indices()
    if not active_indices:
        stop_macro_flag = True
        stop_micro_flag = True
        TEAM_SWITCH_PENDING = False
        print("[*] 所有已配置练级梯队均已完成，程序将安全停止。")
        return

    current_idx = CONFIG.get("CURRENT_TRAIN_TEAM_INDEX", 0)
    if current_idx not in active_indices:
        CONFIG["CURRENT_TRAIN_TEAM_INDEX"] = active_indices[0]
        TEAM_SWITCH_PENDING = False
        if reason:
            print("[*] %s，切换到梯队：%d / %d" % (
                reason,
                CONFIG["CURRENT_TRAIN_TEAM_INDEX"] + 1,
                len(CAPTURED_TEAM_CONFIGS),
            ))
        return

    pos = active_indices.index(current_idx)
    next_idx = active_indices[(pos + 1) % len(active_indices)]
    CONFIG["CURRENT_TRAIN_TEAM_INDEX"] = next_idx
    TEAM_SWITCH_PENDING = False
    if reason:
        print("[*] %s，切换到梯队：%d / %d" % (
            reason,
            next_idx + 1,
            len(CAPTURED_TEAM_CONFIGS),
        ))


def build_team_configs_from_index(payload: dict):
    if not isinstance(payload, dict):
        return []

    gun_list = payload.get("gun_with_user_info", [])
    fairy_data = payload.get("fairy_with_user_info", {})

    team_map = {}

    # Collect fairies by team_id, ignore unequipped team_id=0
    # epa_export.py confirms fairy_with_user_info is usually a dict: { "fairy_uid": { ... } }
    if isinstance(fairy_data, dict):
        fairy_iter = fairy_data.values()
    elif isinstance(fairy_data, list):
        fairy_iter = fairy_data
    else:
        fairy_iter = []

    for fairy in fairy_iter:
        if not isinstance(fairy, dict):
            continue
        team_id_raw = fairy.get("team_id", "0")
        try:
            team_id = int(team_id_raw)
        except Exception:
            continue
        if team_id < 1 or team_id > 14:
            continue
        fairy_uid = fairy.get("id") or fairy.get("fairy_with_user_id")
        try:
            fairy_uid = int(fairy_uid)
        except Exception:
            fairy_uid = 0

        team_map.setdefault(team_id, {"team_id": team_id, "fairy_id": 0, "guns": []})
        if fairy_uid > 0:
            team_map[team_id]["fairy_id"] = fairy_uid

    # Collect guns by team_id, ignore unequipped team_id=0
    if not isinstance(gun_list, list):
        gun_list = []

    for gun in gun_list:
        if not isinstance(gun, dict):
            continue
        team_id_raw = gun.get("team_id", "0")
        try:
            team_id = int(team_id_raw)
        except Exception:
            continue
        if team_id < 1 or team_id > 14:
            continue

        gun_id = gun.get("id") or gun.get("gun_id")
        life = gun.get("life")
        try:
            gun_id = int(gun_id)
            life = int(life)
        except Exception:
            continue

        team_map.setdefault(team_id, {"team_id": team_id, "fairy_id": 0, "guns": []})
        team_map[team_id]["guns"].append({"id": gun_id, "life": life})

    # Keep only effective squads: have a fairy and at least one T-Doll
    teams = []
    for team_id in sorted(team_map.keys()):
        team_cfg = team_map[team_id]
        if team_cfg["fairy_id"] and team_cfg["guns"]:
            teams.append(team_cfg)

    return teams


def try_update_auto_capture_from_index_payload(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False

    if "gun_with_user_info" not in payload or "fairy_with_user_info" not in payload:
        return False

    teams = build_team_configs_from_index(payload)
    if not teams:
        return False

    reset_captured_team_configs()

    if CONFIG.get("MODE_NAME") == "team":
        expected = max(1, min(10, int(CONFIG.get("TRAIN_TEAM_COUNT", 1))))
        selected = teams[:expected]
        for team_cfg in selected:
            CAPTURED_TEAM_CONFIGS.append({
                "team_id": team_cfg["team_id"],
                "fairy_id": team_cfg["fairy_id"],
                "guns": copy.deepcopy(team_cfg["guns"]),
            })
        if CAPTURED_TEAM_CONFIGS:
            CONFIG["TEAM_ID"] = CAPTURED_TEAM_CONFIGS[0]["team_id"]
            CONFIG["FAIRY_ID"] = CAPTURED_TEAM_CONFIGS[0]["fairy_id"]
            CONFIG["GUNS"] = copy.deepcopy(CAPTURED_TEAM_CONFIGS[0]["guns"])
        CONFIG["AUTO_CAPTURE_EXPECTED_COUNT"] = len(CAPTURED_TEAM_CONFIGS)
    else:
        first_team = teams[0]
        CAPTURED_TEAM_CONFIGS.append({
            "team_id": first_team["team_id"],
            "fairy_id": first_team["fairy_id"],
            "guns": copy.deepcopy(first_team["guns"]),
        })
        CONFIG["TEAM_ID"] = first_team["team_id"]
        CONFIG["FAIRY_ID"] = first_team["fairy_id"]
        CONFIG["GUNS"] = copy.deepcopy(first_team["guns"])
        CONFIG["AUTO_CAPTURE_EXPECTED_COUNT"] = 1

    user_info = payload.get("user_info", {})
    if isinstance(user_info, dict):
        user_id = user_info.get("user_id")
        try:
            user_id = str(int(user_id))
            if user_id:
                CONFIG["USER_UID"] = user_id
        except Exception:
            pass

    AUTO_CAPTURE_STATE["completed"] = True
    return True



def has_usable_dynamic_keys() -> bool:
    uid = str(CONFIG.get("USER_UID", "")).strip()
    sign = str(CONFIG.get("SIGN_KEY", "")).strip()
    if not uid or uid == "0":
        return False
    if not sign or sign == DEFAULT_SIGN:
        return False
    return True


def request_index_and_prepare_configs():
    if CONFIG["SIGN_KEY"] == DEFAULT_SIGN:
        print("[!] SIGN_KEY 为默认值，请先运行 -a 抓取 UID/SIGN。")
        return False

    client = GFLClient(CONFIG["USER_UID"], CONFIG["SIGN_KEY"], CONFIG["BASE_URL"])
    print("[*] 正在主动请求 Index/index……")
    payload = {
        "time": int(time.time()),
        "furniture_data": False
    }

    response = client.send_request(API_INDEX_INDEX, payload)

    if isinstance(response, dict) and "error_local" in response:
        print("[-] Index/index 本地错误: %s" % response["error_local"])
        print("    原始响应：'%s'" % response.get("raw", "N/A"))
        return False

    if isinstance(response, dict) and "error" in response:
        print("[-] Index/index 服务器错误: %s" % response["error"])
        return False

    if not isinstance(response, dict):
        print("[!] Index/index 返回格式异常。")
        return False

    try:
        with open("index_debug.json", "w", encoding="utf-8") as f:
            json.dump(response, f, indent=4, ensure_ascii=False)
        print("[*] 已保存 Index/index 响应到 index_debug.json")
    except Exception as e:
        print("[!] 保存 index_debug.json 失败：%s" % e)

    if not try_update_auto_capture_from_index_payload(response):
        print("[!] 已请求 Index/index，但未解析出有效梯队。")
        preview = str(response)[:300]
        print("    Parsed JSON preview: %s..." % preview)
        print("    请把 index_debug.json 发给我，我可以继续精确修正解析逻辑。")
        return False

    apply_auto_capture_to_config()
    if CONFIG.get("MODE_NAME") == "team":
        print("\n[AUTO] 已主动请求并解析 Index/index。")
        print("[AUTO] 共解析出 %d 个有效练级梯队：" % len(CAPTURED_TEAM_CONFIGS))
        for idx, team_cfg in enumerate(CAPTURED_TEAM_CONFIGS, start=1):
            print("[AUTO] 梯队%d -> TEAM_ID=%s | FAIRY_ID=%s | GUNS=%s" % (
                idx,
                team_cfg["team_id"],
                team_cfg["fairy_id"],
                team_cfg["guns"],
            ))
        print("[AUTO] 将默认从梯队一开始轮转。")
    else:
        print("\n[AUTO] 已主动请求并解析 Index/index。")
        print("[AUTO] TEAM_ID  = %s" % CONFIG["TEAM_ID"])
        print("[AUTO] FAIRY_ID = %s" % CONFIG["FAIRY_ID"])
        print("[AUTO] GUNS     = %s" % CONFIG["GUNS"])
        if not validate_captured_team_for_mode():
            return False

    MENU_STATE["selection_unlocked"] = True
    reset_selection_menu()
    print_main_menu()
    print_difficulty_menu()
    return True


def collect_keyed_values(obj, target_key: str):
    results = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if str(k) == target_key:
                    results.append(v)
                walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(obj)
    return results


def collect_gun_entries(obj):
    guns = []

    def walk(x):
        if isinstance(x, dict):
            if "id" in x and "life" in x:
                gun_id = x.get("id")
                life = x.get("life")
                if isinstance(gun_id, int) and isinstance(life, int):
                    guns.append({"id": gun_id, "life": life})
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(obj)

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for gun in guns:
        key = (gun["id"], gun["life"])
        if key not in seen:
            seen.add(key)
            deduped.append(gun)
    return deduped


def try_update_auto_capture_from_payload(url: str, payload):
    # 新流程不再依赖被动抓取 TEAM_ID / FAIRY_ID / GUNS。
    # 这里只保留函数壳，避免旧调用报错。
    return False


def apply_auto_capture_to_config():
    if CONFIG.get("MODE_NAME") == "team":
        if CAPTURED_TEAM_CONFIGS:
            CONFIG["TEAM_ID"] = CAPTURED_TEAM_CONFIGS[0]["team_id"]
            CONFIG["FAIRY_ID"] = CAPTURED_TEAM_CONFIGS[0]["fairy_id"]
            CONFIG["GUNS"] = copy.deepcopy(CAPTURED_TEAM_CONFIGS[0]["guns"])
    else:
        if AUTO_CAPTURE_STATE["team_id"] is not None:
            CONFIG["TEAM_ID"] = AUTO_CAPTURE_STATE["team_id"]
        if AUTO_CAPTURE_STATE["fairy_id"] is not None:
            CONFIG["FAIRY_ID"] = AUTO_CAPTURE_STATE["fairy_id"]
        if AUTO_CAPTURE_STATE["guns"]:
            CONFIG["GUNS"] = copy.deepcopy(AUTO_CAPTURE_STATE["guns"])


def stop_proxy_instance():
    global proxy_instance, worker_mode
    if proxy_instance:
        proxy_instance.stop()
        set_windows_proxy(False)
        proxy_instance = None
    worker_mode = None


def maybe_finish_auto_capture():
    return

def print_main_menu():
    print("\n================= MENU =================")
    print(" -a : 先抓 UID/SIGN，再主动请求 Index/index 并解析梯队配置")
    print(" -r : 运行自动打捞（EPA）")
    print(" -q : 当前 Macro 结束后安全停止")
    print(" -Q : 当前 Micro 结束后安全停止")
    print(" -s : 仅停止代理")
    print(" -E : Exit program")
    print("========================================\n")



def normalize_menu_input(cmd: str) -> str:
    raw = (cmd or "").strip()
    lower = raw.lower()

    alias_map = {
        "b": "-back",
        "back": "-back",

        "p": "普通",
        "普": "普通",
        "normal": "普通",

        "j": "紧急",
        "紧": "紧急",
        "urgent": "紧急",
        "em": "紧急",

        "y": "夜战",
        "夜": "夜战",
        "night": "夜战",

        "team": "-team",
        "t": "-team",
        "single": "-single",
        "s1": "-single",

        "full": "-full",
        "f": "-full",
        "equal": "-equal",
        "e": "-equal",

        "protecton": "-protecton",
        "on": "-protecton",
        "po": "-protecton",

        "protectoff": "-protectoff",
        "off": "-protectoff",
        "pf": "-protectoff",

        "stopmax": "-stopmax",
        "sm": "-stopmax",
        "stop": "-stopmax",

        "keepmax": "-keepmax",
        "km": "-keepmax",
        "keep": "-keepmax",
    }

    if lower in alias_map:
        return alias_map[lower]

    # A1 / a1 -> A-1
    if re.fullmatch(r"[aA]\d{1,2}", raw):
        return "A-" + raw[1:]

    # 1 / 2 / 3 / 4 / 5 -> -1 / -2 / ...
    if re.fullmatch(r"\d+", raw):
        return "-" + raw

    return raw


def print_difficulty_menu():
    print("\n=========== 打捞关卡菜单 ===========")
    print("请选择你要打捞的关卡难度：")
    print("  普通   （别名：普 / p）")
    print("  紧急   （别名：紧 / j）")
    print("  夜战   （别名：夜 / y）")
    print("------------------------------------")
    print("提示：输入名称或别名并回车，例如：普通 / p / 夜")
    print("====================================\n")


def print_stage_menu(difficulty: str):
    if difficulty == "普通":
        options = NORMAL_STAGE_OPTIONS
    elif difficulty == "紧急":
        options = EMERGENCY_STAGE_OPTIONS
    else:
        options = NIGHT_STAGE_OPTIONS

    print("\n=========== %s 关卡列表 ===========" % difficulty)
    print("请选择关卡：")
    print("  " + "  ".join(options))
    print("------------------------------------")
    print("提示：输入选项名称并回车，例如：A-10")
    print("提示：也可输入别名，例如：a10 / A10")
    print("提示：输入 -back 或 b 返回难度选择菜单")
    print("====================================\n")


def print_placeholder_menu(difficulty: str, stage: str):
    print("\n[!] %s %s 菜单暂未实现，当前先占位。" % (difficulty, stage))
    if difficulty == "夜战":
        print("[!] 夜战已接入装备掉落统计逻辑，但当前尚未写入该关的 MISSION_ID / START_SPOT / ROUTE / 目标装备。")
    else:
        print("[!] 你可以重新选择其他关卡，或等待后续继续补全。")


def print_target_menu(difficulty: str, stage: str):
    options = get_stage_options(difficulty, stage)
    print("\n=========== %s %s ===========" % (difficulty, stage))
    print("请选择你要打捞的目标：")
    if difficulty == "夜战":
        print("（夜战目标为装备）")
        print("（说明：夜战目前仅支持自动打捞，暂不支持自动拆解）")
    for key, item in options.items():
        print("  %s : %s" % (key, item["label"]))
    print("---------------------------------")
    print("提示：输入对应编号并回车，例如：-1")
    print("提示：也可直接输入数字，例如：1")
    print("提示：输入 -back 或 b 返回上一级菜单")
    print("=================================\n")


def print_ready_to_run_hint():
    print("[*] 已完成全部选择，请先进行运行前确认。")



def print_filter_protection_menu():
    print("\n=========== 过滤保护设置 ===========")
    print("请选择是否开启过滤保护：")
    print("  -protecton  : 开启过滤保护（默认，别名：on / po）")
    print("  -protectoff : 关闭过滤保护（别名：off / pf）")
    print("------------------------------------")
    print("提示：练级模式下关闭后可避免目标掉落长期占仓导致流程中断")
    print("提示：输入 -protecton / -protectoff，也可输入 on / off")
    print("====================================")


def print_run_confirm_menu():
    print("\n=========== 运行前确认 ===========")
    print("当前选择为：%s %s -> %s" % (
        CONFIG["SELECTED_DIFFICULTY"],
        CONFIG["SELECTED_STAGE"],
        CONFIG["SELECTED_TARGET_LABEL"],
    ))
    print("编队模式：%s" % ("打捞单人模式" if CONFIG.get("SINGLE_GUN_MODE") else "练级五人模式"))
    if CONFIG.get("MODE_NAME") == "team":
        schedule_label = "整队满级后切换" if CONFIG.get("TRAIN_SCHEDULE_MODE") == "full" else "均等练级轮转"
        print("练级调度：%s" % schedule_label)
    print("满级停机：%s" % ("是" if CONFIG.get("STOP_ON_MAX_LEVEL") else "否"))
    print("----------------------------------")
    print("提示：输入 -y 确认本次打捞配置")
    print("提示：输入 -back 或 b 返回上一级菜单重新选择")
    print("==================================\n")


def print_stop_on_max_menu():
    print("\n=========== 满级停机设置 ===========")
    print("请选择当检测到人形 EXP 为 0（满级）后的行为：")
    print("  -stopmax : 停止程序")
    print("  -keepmax : 不停止程序")
    print("------------------------------------")
    print("提示：只能输入 -stopmax 或 -keepmax")
    print("====================================\n")



def get_selected_protected_gun_ids():
    if not CONFIG.get("ENABLE_FILTER_PROTECTION", True):
        return set()

    protected_ids = set(CONFIG.get("PROTECTED_DROP_GUN_IDS", []))
    label = CONFIG.get("SELECTED_TARGET_LABEL")
    if label:
        for name in split_target_label(label):
            gun_id = resolve_gun_id_by_name(name)
            if gun_id is not None:
                protected_ids.add(gun_id)
    return protected_ids


def get_selected_target_equip_ids():
    # 夜战自动拆解功能暂未启用，当前不使用装备保护列表。
    return set()


def is_no_space_retire_failure(resp) -> bool:
    text_blob = str(resp).lower()
    keywords = [
        "full", "space", "capacity", "inventory",
        "仓库", "满", "空间", "容量", "上限", "空位"
    ]
    return any(k in text_blob for k in keywords)


def reset_run_stats():
    RUN_STATS["start_time"] = None
    RUN_STATS["end_time"] = None
    RUN_STATS["target_counts"] = {}
    RUN_STATS["target_type"] = "gun"



def get_selected_target_pairs():
    label = CONFIG.get("SELECTED_TARGET_LABEL", "")
    pairs = []
    if CONFIG.get("SELECTED_DIFFICULTY") == "夜战":
        for name in split_target_label(label):
            equip_id = resolve_equip_id_by_name(name)
            if equip_id is not None:
                pairs.append((name, equip_id))
        return pairs

    for name in split_target_label(label):
        gun_id = resolve_gun_id_by_name(name)
        if gun_id is not None:
            pairs.append((name, gun_id))
    return pairs


def init_run_target_counts():
    RUN_STATS["target_counts"] = {}
    RUN_STATS["target_type"] = "equip" if CONFIG.get("SELECTED_DIFFICULTY") == "夜战" else "gun"
    for name, item_id in get_selected_target_pairs():
        RUN_STATS["target_counts"][name] = {"item_id": item_id, "count": 0}


def record_target_drop(item_id, drop_type="gun"):
    try:
        item_id = int(item_id)
    except Exception:
        return

    if RUN_STATS.get("target_type") != drop_type:
        return

    for name, item in RUN_STATS["target_counts"].items():
        if item["item_id"] == item_id:
            item["count"] += 1


def format_duration(seconds):
    seconds = int(max(0, seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}小时{m}分{s}秒"
    if m > 0:
        return f"{m}分{s}秒"
    return f"{s}秒"


def print_run_summary():
    if RUN_STATS["start_time"] is None or RUN_STATS["end_time"] is None:
        return

    duration = RUN_STATS["end_time"] - RUN_STATS["start_time"]
    print("\n=========== 本次运行统计 ===========")
    print("运行时长：%s" % format_duration(duration))
    title = "目标装备掉落" if RUN_STATS.get("target_type") == "equip" else "目标人形掉落"
    if RUN_STATS["target_counts"]:
        print("%s：" % title)
        for name, item in RUN_STATS["target_counts"].items():
            print("  %s：%d" % (name, item["count"]))
    else:
        print("%s：当前未配置" % title)
    print("====================================\n")


def print_gun_mode_menu():
    print("\n=========== 编队模式选择 ===========")
    print("请选择运行模式：")
    print("  -team   : 练级模式，使用五人编队；满级后轮转下一个梯队（默认）")
    print("  -single : 打捞模式，使用单人编队（仅使用梯队1）")
    print("------------------------------------")
    print("提示：请选择好编队模式后，再按照要求进入游戏并配置好编队")
    print("提示：直接按回车将使用默认配置（-team）")
    print("提示：只能输入 -team 或 -single")
    print("====================================\n")


def reset_selection_menu():
    MENU_STATE["difficulty"] = None
    MENU_STATE["stage"] = None
    MENU_STATE["awaiting_gun_mode"] = False
    MENU_STATE["awaiting_stop_on_max"] = False
    MENU_STATE["awaiting_filter_protection"] = False
    MENU_STATE["awaiting_run_confirm"] = False


def reopen_stage_selection_menu():
    MENU_STATE["selection_unlocked"] = True
    reset_selection_menu()
    print_main_menu()
    print_difficulty_menu()


def validate_captured_team_for_mode() -> bool:
    guns = CONFIG.get("GUNS", []) or []
    if CONFIG.get("MODE_NAME") == "single":
        if len(guns) != 1:
            print("[!] 当前为 single 打捞模式，但本次 Index/index 解析到的梯队人数为 %d 人。" % len(guns))
            print("[!] single 模式要求仅使用梯队1，且梯队1必须配置为单人编队。")
            print("[!] 请前往游戏编队界面，将梯队1调整为仅 1 名人形后，再重新输入 -a 抓取。")
            print("[*] 提示：程序会保留你当前选择的 single 模式。调整好梯队1后，可直接再次输入 -a。")
            return False
        print("[*] single 模式校验通过：当前仅使用梯队1，且人数为 1。")
    return True


def handle_selection_input(cmd: str) -> bool:
    """Returns True if the input was consumed by the selection menu."""
    if not MENU_STATE["selection_unlocked"]:
        return False

    cmd = normalize_menu_input(cmd)

    if MENU_STATE["awaiting_filter_protection"]:
        if not cmd:
            cmd = "-protecton"
        if cmd == "-back":
            MENU_STATE["awaiting_filter_protection"] = False
            print("[*] 已返回上一层。")
            stage_data = get_stage_data(CONFIG.get("SELECTED_DIFFICULTY"), CONFIG.get("SELECTED_STAGE"))
            if stage_data:
                print_target_menu(CONFIG["SELECTED_DIFFICULTY"], CONFIG["SELECTED_STAGE"])
            return True
        if cmd == "-protecton":
            MENU_STATE["awaiting_filter_protection"] = False
            MENU_STATE["awaiting_stop_on_max"] = True
            CONFIG["ENABLE_FILTER_PROTECTION"] = True
            print("[+] 已选择：过滤保护开启。")
            print_stop_on_max_menu()
            return True
        if cmd == "-protectoff":
            MENU_STATE["awaiting_filter_protection"] = False
            MENU_STATE["awaiting_stop_on_max"] = True
            CONFIG["ENABLE_FILTER_PROTECTION"] = False
            print("[+] 已选择：过滤保护关闭。")
            print("[!] 提示：关闭后目标掉落也不会被保护，适合练级避免仓库被占满。")
            print_stop_on_max_menu()
            return True
        return False

    if MENU_STATE["awaiting_stop_on_max"]:
        if not cmd:
            cmd = "-stopmax"
        if cmd == "-back":
            MENU_STATE["awaiting_stop_on_max"] = False
            if CONFIG.get("MODE_NAME") == "team":
                MENU_STATE["awaiting_filter_protection"] = True
                print("[*] 已返回过滤保护设置菜单。")
                print_filter_protection_menu()
            else:
                print("[*] 已返回上一层。")
                stage_data = get_stage_data(CONFIG.get("SELECTED_DIFFICULTY"), CONFIG.get("SELECTED_STAGE"))
                if stage_data:
                    print_target_menu(CONFIG["SELECTED_DIFFICULTY"], CONFIG["SELECTED_STAGE"])
            return True
        if cmd == "-stopmax":
            MENU_STATE["awaiting_stop_on_max"] = False
            MENU_STATE["awaiting_run_confirm"] = True
            CONFIG["STOP_ON_MAX_LEVEL"] = True
            print("[+] 已选择：检测到满级后停止程序。")
            print_run_confirm_menu()
            return True
        if cmd == "-keepmax":
            MENU_STATE["awaiting_stop_on_max"] = False
            MENU_STATE["awaiting_run_confirm"] = True
            CONFIG["STOP_ON_MAX_LEVEL"] = False
            print("[+] 已选择：检测到满级后不停止程序。")
            print_run_confirm_menu()
            return True
        return False

    if MENU_STATE["awaiting_run_confirm"]:
        if cmd == "-back":
            MENU_STATE["awaiting_run_confirm"] = False
            MENU_STATE["awaiting_stop_on_max"] = True
            print("[*] 已返回满级停机设置菜单。")
            print_stop_on_max_menu()
            return True
        if cmd == "-y":
            MENU_STATE["awaiting_run_confirm"] = False
            print("[+] 已确认本次打捞配置。")
            print("[+] 已完成关卡参数装载。")
            print("[+] 当前模式：%s" % ("打捞单人模式" if CONFIG.get("SINGLE_GUN_MODE") else "练级五人模式"))
            if CONFIG.get("MODE_NAME") == "team":
                schedule_label = "整队满级后切换" if CONFIG.get("TRAIN_SCHEDULE_MODE") == "full" else "均等练级轮转"
                print("[+] 练级梯队总数：%d（默认从梯队一开始轮转）" % len(CAPTURED_TEAM_CONFIGS))
                print("[+] 练级调度模式：%s" % schedule_label)
                print("[+] 过滤保护：%s" % ("开启" if CONFIG.get("ENABLE_FILTER_PROTECTION", True) else "关闭"))
                if CONFIG.get("SELECTED_DIFFICULTY") == "夜战":
                    print("[!] 提示：夜战暂时没有自动拆解功能，不建议去夜战关卡练级。")
            print("[+] 满级停机设置：%s" % ("开启" if CONFIG.get("STOP_ON_MAX_LEVEL") else "关闭"))
            protected_ids = sorted(get_selected_protected_gun_ids())
            print("[+] 自动拆解保护 gun_id：%s" % (protected_ids if protected_ids else "当前未配置"))
            if CONFIG.get("SELECTED_DIFFICULTY") == "夜战":
                print("[!] 说明：夜战关卡当前仅支持自动打捞，暂不支持自动拆解。")
                print("[!] 当前版本夜战仅保留掉落统计与关卡流程。")
            print("[*] 请继续输入 -r 运行程序。")
            return True
        return False

    if MENU_STATE["difficulty"] is None:
        if cmd in ("普通", "紧急", "夜战"):
            MENU_STATE["difficulty"] = cmd
            CONFIG["SELECTED_DIFFICULTY"] = cmd
            CONFIG["SELECTED_STAGE"] = None
            CONFIG["SELECTED_TARGET"] = None
            CONFIG["SELECTED_TARGET_LABEL"] = None
            CONFIG["SELECTED_BATTLE_TEMPLATE"] = None
            print_stage_menu(cmd)
            return True
        return False

    if MENU_STATE["stage"] is None:
        if cmd == "-back":
            reset_selection_menu()
            print("[*] 当前已返回到难度选择菜单。")
            print_difficulty_menu()
            return True

        difficulty = MENU_STATE["difficulty"]
        valid_options = {
            "普通": NORMAL_STAGE_OPTIONS,
            "紧急": EMERGENCY_STAGE_OPTIONS,
            "夜战": NIGHT_STAGE_OPTIONS,
        }[difficulty]

        if cmd in valid_options:
            MENU_STATE["stage"] = cmd
            CONFIG["SELECTED_STAGE"] = cmd
            CONFIG["SELECTED_TARGET"] = None
            CONFIG["SELECTED_TARGET_LABEL"] = None
            CONFIG["SELECTED_BATTLE_TEMPLATE"] = None

            stage_data = get_stage_data(difficulty, cmd)
            if stage_data:
                print_target_menu(difficulty, cmd)
            else:
                print_placeholder_menu(difficulty, cmd)
                MENU_STATE["stage"] = None
                CONFIG["SELECTED_STAGE"] = None
                print_stage_menu(difficulty)
            return True
        return False

    stage_data = get_stage_data(CONFIG.get("SELECTED_DIFFICULTY"), CONFIG.get("SELECTED_STAGE"))
    if stage_data:
        if cmd == "-back":
            MENU_STATE["stage"] = None
            CONFIG["SELECTED_STAGE"] = None
            CONFIG["SELECTED_TARGET"] = None
            CONFIG["SELECTED_TARGET_LABEL"] = None
            CONFIG["SELECTED_BATTLE_TEMPLATE"] = None
            MENU_STATE["awaiting_stop_on_max"] = False
            MENU_STATE["awaiting_run_confirm"] = False
            print("[*] 已返回%s难度关卡列表。" % CONFIG["SELECTED_DIFFICULTY"])
            print_stage_menu(CONFIG["SELECTED_DIFFICULTY"])
            return True

        options = stage_data.get("OPTIONS", {})
        if cmd in options:
            item = options[cmd]
            CONFIG["SELECTED_TARGET"] = cmd
            CONFIG["SELECTED_TARGET_LABEL"] = item["label"]
            CONFIG["MISSION_ID"] = stage_data["MISSION_ID"]
            if "start_spot" in item:
                CONFIG["START_SPOT"] = item["start_spot"]
            else:
                CONFIG["START_SPOT"] = stage_data["START_SPOTS"][cmd]
            CONFIG["ROUTE"] = item["route"]

            if CONFIG["SELECTED_DIFFICULTY"] == "普通" and CONFIG["SELECTED_STAGE"] == "A-10":
                CONFIG["SELECTED_BATTLE_TEMPLATE"] = A10_SINGLE_BATTLE_TEMPLATE
            else:
                CONFIG["SELECTED_BATTLE_TEMPLATE"] = None

            print("[+] 已选择：%s %s -> %s" % (
                CONFIG["SELECTED_DIFFICULTY"],
                CONFIG["SELECTED_STAGE"],
                CONFIG["SELECTED_TARGET_LABEL"],
            ))
            print("[+] 当前关卡配置已写入：MISSION_ID=%s, START_SPOT=%s, ROUTE=%s" % (
                CONFIG["MISSION_ID"],
                CONFIG["START_SPOT"],
                CONFIG["ROUTE"],
            ))
            print("[+] 当前模式已在抓包前确定：%s" % ("打捞单人模式" if CONFIG.get("SINGLE_GUN_MODE") else "练级五人模式"))
            if CONFIG.get("MODE_NAME") == "team" and CONFIG.get("SELECTED_DIFFICULTY") == "夜战":
                print("[!] 提示：夜战当前暂未支持自动拆解功能，不建议用于自动练级。")
            print("[+] 当前战斗将自动调用已抓取的 TEAM_ID / FAIRY_ID / GUNS。")
            print("[+] 1002 将根据当前梯队配置自动生成，无需为每个任务单独修改。")
            print_ready_to_run_hint()
            if CONFIG.get("MODE_NAME") == "team":
                MENU_STATE["awaiting_filter_protection"] = True
                print_filter_protection_menu()
            else:
                MENU_STATE["awaiting_stop_on_max"] = True
                print_stop_on_max_menu()
            return True
        return False

    return False


def on_traffic(event_type: str, url: str, data: dict):
    event_upper = str(event_type).upper()

    if event_upper == "SYS_KEY_UPGRADE":
        CONFIG["USER_UID"] = data.get("uid")
        CONFIG["SIGN_KEY"] = data.get("sign")
        CONFIG["INDEX_FETCH_READY"] = True
        print("\n[+] 成功！密钥已自动配置：")
        print("    UID  : %s" % CONFIG['USER_UID'])
        print("    SIGN : %s" % CONFIG['SIGN_KEY'])

        if CONFIG.get("AUTO_MONITOR_MODE"):
            print("[AUTO] 动态密钥已更新。")
            print("[AUTO] 请等待游戏完全进入指挥官主界面，然后再次输入 -a。")
            print("[AUTO] 程序将停止代理并主动请求 Index/index 解析梯队。")
        else:
            print("\n[!] CRITICAL: 请等待游戏完全加载到指挥官主界面！")
            print("[!] 然后输入 '-r' 自动停止代理并开始打捞。")


def check_step_error(resp: dict, step_name: str) -> bool:
    if "error_local" in resp:
        print("[-] %s 本地错误: %s" % (step_name, resp['error_local']))
        return True
    if "error" in resp:
        print("[-] %s 服务器错误: %s" % (step_name, resp['error']))
        return True
    return False


def check_battle_drop(resp_data: dict, spot_id: int) -> list:
    collected = []
    bg = resp_data.get("battle_get_gun", [])
    if bg:
        for gun in bg:
            gun_id = int(gun.get("gun_id"))
            gun_uid = int(gun.get("gun_with_user_id"))
            print("    [+] 战斗掉落（节点 %d）！Gun ID: %s | UID: %d" %
                  (spot_id, gun_id, gun_uid))
            DROPPED_UID_TO_GUN_ID[gun_uid] = gun_id
            record_target_drop(gun_id, "gun")
            collected.append(gun_uid)
    return collected


def check_battle_equip_drop(resp_data: dict, spot_id: int):
    collected = []
    be = resp_data.get("battle_get_equip", [])
    if be:
        for equip in be:
            equip_id = int(equip.get("equip_id"))
            equip_uid = int(equip.get("id"))
            print("    [+] 战斗装备掉落（节点 %d）！Equip ID: %s | UID: %d" %
                  (spot_id, equip_id, equip_uid))
            DROPPED_UID_TO_EQUIP_ID[equip_uid] = equip_id
            record_target_drop(equip_id, "equip")
            collected.append({"equip_id": equip_id, "equip_uid": equip_uid})
    return collected


def check_battle_exp(resp_data: dict, spot_id: int):
    """Returns (any_zero, all_zero)."""
    gun_exp_list = resp_data.get("gun_exp", [])
    any_zero = False
    all_zero = False

    if gun_exp_list:
        exp_details = []
        zero_flags = []
        for item in gun_exp_list:
            gun_uid = str(item.get("gun_with_user_id", "unknown"))
            exp_val = str(item.get("exp", "0"))
            exp_details.append("%s: +%s" % (gun_uid[-4:], exp_val))

            is_zero = (exp_val == "0")
            zero_flags.append(is_zero)
            if is_zero:
                print("    [!] 警告：人形 %s 已达到满级（EXP 为 0）！" % gun_uid)
                any_zero = True

        all_zero = all(zero_flags) if zero_flags else False
        print("    [+] 节点 %d EXP | %s" % (spot_id, " | ".join(exp_details)))

    return any_zero, all_zero


def check_win_drop(resp_data: dict) -> list:
    collected = []
    win_result = resp_data.get("mission_win_result", {})
    if win_result:
        rg = win_result.get("reward_gun", [])
        for gun in rg:
            gun_id = int(gun.get("gun_id"))
            gun_uid = int(gun.get("gun_with_user_id"))
            print("    [+] 关卡结算掉落！Gun ID: %s | UID: %d" %
                  (gun_id, gun_uid))
            DROPPED_UID_TO_GUN_ID[gun_uid] = gun_id
            record_target_drop(gun_id, "gun")
            collected.append(gun_uid)
    return collected


def check_win_equip_drop(resp_data: dict):
    collected = []
    win_result = resp_data.get("mission_win_result", {})
    if win_result:
        re_list = win_result.get("reward_equip", [])
        for equip in re_list:
            equip_id = int(equip.get("equip_id"))
            equip_uid = int(equip.get("id"))
            print("    [+] 关卡结算装备掉落！Equip ID: %s | UID: %d" %
                  (equip_id, equip_uid))
            DROPPED_UID_TO_EQUIP_ID[equip_uid] = equip_id
            record_target_drop(equip_id, "equip")
            collected.append({"equip_id": equip_id, "equip_uid": equip_uid})
    return collected


def get_mvp_generator():
    idx = 0
    while True:
        guns = get_active_guns()
        if not guns:
            yield 0
            continue
        yield guns[idx % len(guns)]["id"]
        idx = (idx + 1) % len(guns)


def get_active_guns():
    guns = get_current_team_config()["guns"]
    if CONFIG.get("SINGLE_GUN_MODE"):
        idx = CONFIG.get("SINGLE_GUN_INDEX", 0)
        if 0 <= idx < len(guns):
            return [guns[idx]]
        return []
    return guns


def build_battle_guns():
    return [{"id": g["id"], "life": g["life"]} for g in get_active_guns()]


def build_battle_1002():
    """
    与原版风格尽量保持一致：
    - 单人编队时，使用抓包里验证过的座位值 1
    - 多人编队时，按原版自动生成，不需要为每个任务单独写死
    """
    result = {}
    guns = get_active_guns()

    if len(guns) == 1:
        result[str(guns[0]["id"])] = {"47": 1}
        return result

    for gun in guns:
        result[str(gun["id"])] = {"47": 0}
    return result


def farm_mission_epa(client: GFLClient, team_id: int, mvp_gen):
    global stop_macro_flag, stop_micro_flag, TEAM_SWITCH_PENDING

    mission_id = CONFIG["MISSION_ID"]
    start_spot = CONFIG["START_SPOT"]
    route = CONFIG["ROUTE"]

    dropped_uids = []
    dropped_equip_uids = []
    current_spots_state = {}

    def update_seeds(resp):
        if isinstance(resp, dict) and "spot_act_info" in resp:
            for s in resp["spot_act_info"]:
                current_spots_state[str(s.get("spot_id"))] = int(s.get("seed", 0))

    print("[>] 正在请求组合信息……")
    if check_step_error(client.send_request(API_MISSION_COMBINFO, {"mission_id": mission_id}), "combInfo"):
        return None

    print("[>] 正在开始关卡 %d……" % mission_id)
    start_payload = {
        "mission_id": mission_id,
        "spots": [{"spot_id": start_spot, "team_id": team_id}],
        "squad_spots": [], "sangvis_spots": [], "vehicle_spots": [],
        "ally_spots": [], "mission_ally_spots": [],
        "ally_id": int(time.time())
    }
    start_resp = client.send_request(API_MISSION_START, start_payload)
    if check_step_error(start_resp, "startMission"):
        return None
    update_seeds(start_resp)

    curr_spot = start_spot
    for step, next_spot in enumerate(route, 1):
        print("[>] Step %d: Moving %d -> %d..." % (step, curr_spot, next_spot))
        move_payload = {
            "person_type": 1, "person_id": team_id,
            "from_spot_id": curr_spot, "to_spot_id": next_spot, "move_type": 1
        }
        move_resp = client.send_request(API_MISSION_TEAM_MOVE, move_payload)
        if check_step_error(move_resp, "teamMove(%d->%d)" % (curr_spot, next_spot)):
            return None
        update_seeds(move_resp)

        client.send_request(API_MISSION_COMBINFO, {"mission_id": mission_id})

        seed = current_spots_state.get(str(next_spot), 0)
        current_mvp = next(mvp_gen)
        print("[>] Battle at Node %d (Seed: %d, MVP: %d)..." % (next_spot, seed, current_mvp))

        selected_template = CONFIG.get("SELECTED_BATTLE_TEMPLATE")

        if selected_template:
            fairy_dict = {}
            current_fairy_id = get_current_fairy_id()
            if current_fairy_id:
                fairy_dict = {
                    str(current_fairy_id): {
                        "9": 1,
                        "68": 0
                    }
                }

            battle_payload = {
                "spot_id": next_spot,
                "if_enemy_die": True,
                "current_time": int(time.time()),
                "boss_hp": 0,
                "mvp": current_mvp,
                "last_battle_info": "",
                "use_skill_squads": [],
                "use_skill_ally_spots": [],
                "use_skill_vehicle_spots": [],
                "guns": build_battle_guns(),
                "user_rec": '{"seed":%d,"record":[]}' % seed,
                "1000": selected_template.get("1000", {}),
                "1001": selected_template.get("1001", {}),
                "1002": build_battle_1002(),
                "1003": fairy_dict,
                "1005": selected_template.get("1005", {}),
                "1007": selected_template.get("1007", {}),
                "1008": selected_template.get("1008", {}),
                "1009": selected_template.get("1009", {}),
                "battle_damage": {},
                "micalog": {
                    "user_device": CONFIG["USER_DEVICE"],
                    "user_ip": ""
                }
            }
        else:
            fairy_dict = {}
            current_fairy_id = get_current_fairy_id()
            if current_fairy_id:
                fairy_dict = {
                    str(current_fairy_id): {
                        "9": 1,
                        "68": 0
                    }
                }

            battle_payload = {
                "spot_id": next_spot,
                "if_enemy_die": True,
                "current_time": int(time.time()),
                "boss_hp": 0,
                "mvp": current_mvp,
                "last_battle_info": "",
                "use_skill_squads": [],
                "use_skill_ally_spots": [],
                "use_skill_vehicle_spots": [],
                "guns": build_battle_guns(),
                "user_rec": '{"seed":%d,"record":[]}' % seed,

                "1000": {"10": 18473, "11": 18473, "12": 18473, "13": 18473, "15": 27550, "16": 0, "17": 98, "33": 10017, "40": 50, "18": 0, "19": 0, "20": 0, "21": 0, "22": 0, "23": 0, "24": 25975, "25": 0, "26": 25975, "27": 4, "34": 63, "35": 63, "41": 519, "42": 0, "43": 0, "44": 0},
                "1001": {},
                "1002": build_battle_1002(),
                "1003": fairy_dict,
                "1005": {}, "1007": {}, "1008": {}, "1009": {},
                "battle_damage": {},
                "micalog": {
                    "user_device": CONFIG["USER_DEVICE"],
                    "user_ip": ""
                }
            }

        battle_resp = client.send_request(API_MISSION_BATTLE_FINISH, battle_payload)
        if check_step_error(battle_resp, "battleFinish(%d)" % next_spot):
            return None

        dropped_uids.extend(check_battle_drop(battle_resp, next_spot))
        battle_equip_drops = check_battle_equip_drop(battle_resp, next_spot)
        dropped_equip_uids.extend([x["equip_uid"] for x in battle_equip_drops])

        any_zero, all_zero = check_battle_exp(battle_resp, next_spot)
        if CONFIG.get("MODE_NAME") == "team":
            if all_zero:
                TEAM_SWITCH_PENDING = True
                mark_current_training_team_completed()
                print("    [*] 当前五人编队成员 EXP 均为 0，该梯队已完成。")
        else:
            if any_zero:
                if CONFIG.get("STOP_ON_MAX_LEVEL", True):
                    stop_macro_flag = True
                    stop_micro_flag = True
                    print("    [*] 为避免浪费 EXP，已触发自动停机。本轮结束后将安全停止。")
                else:
                    print("    [*] 检测到满级，但已关闭满级停机，程序将继续运行。")

        curr_spot = next_spot
        time.sleep(0.5)

    print("[>] 正在结束回合并计算胜利条件……")
    if check_step_error(client.send_request(API_MISSION_END_TURN, {}), "endTurn"):
        return None
    time.sleep(0.2)
    if check_step_error(client.send_request(API_MISSION_START_ENEMY_TURN, {}), "startEnemyTurn"):
        return None
    time.sleep(0.2)
    if check_step_error(client.send_request(API_MISSION_END_ENEMY_TURN, {}), "endEnemyTurn"):
        return None
    time.sleep(0.2)

    win_resp = client.send_request(API_MISSION_START_TURN, {})
    if check_step_error(win_resp, "startTurn"):
        return None

    dropped_uids.extend(check_win_drop(win_resp))
    win_equip_drops = check_win_equip_drop(win_resp)
    dropped_equip_uids.extend([x["equip_uid"] for x in win_equip_drops])

    return {"guns": dropped_uids, "equips": dropped_equip_uids}


def retire_guns(client: GFLClient, gun_uids: list):
    global stop_macro_flag, stop_micro_flag, RETIRE_NO_SPACE_COUNT

    if not gun_uids:
        return

    protected_ids = get_selected_protected_gun_ids()
    filtered_uids = []

    for gun_uid in gun_uids:
        gun_id = DROPPED_UID_TO_GUN_ID.get(gun_uid)
        if gun_id is not None:
            try:
                gun_id = int(gun_id)
            except Exception:
                pass
        if gun_id in protected_ids:
            print("[*] 已保留受保护掉落。Gun ID: %s | UID: %s" % (gun_id, gun_uid))
            continue
        filtered_uids.append(gun_uid)

    if protected_ids:
        print("[*] 已启用自动拆解保护，受保护 gun_id：%s" % sorted(protected_ids))

    if not filtered_uids:
        print("[*] 过滤后没有可自动拆解的人形。")
        return

    print("[*] 正在提交 %d 名人形进行自动拆解……" % len(filtered_uids))
    resp = client.send_request(API_GUN_RETIRE, filtered_uids)
    if resp.get("success"):
        RETIRE_NO_SPACE_COUNT = 0
        print("[+] 自动拆解成功！")
    else:
        print("[-] 拆解失败：%s" % str(resp))
        if is_no_space_retire_failure(resp):
            RETIRE_NO_SPACE_COUNT += 1
            print("[!] 检测到疑似仓库无空位导致的拆解失败次数：%d / %d" % (
                RETIRE_NO_SPACE_COUNT,
                CONFIG.get("STOP_AFTER_RETIRE_NO_SPACE_TIMES", 2),
            ))
            if RETIRE_NO_SPACE_COUNT >= CONFIG.get("STOP_AFTER_RETIRE_NO_SPACE_TIMES", 2):
                stop_macro_flag = True
                stop_micro_flag = True
                print("[!] 已触发自动停机：多次自动拆解后仓库似乎仍无空位。")
        else:
            RETIRE_NO_SPACE_COUNT = 0

    for gun_uid in gun_uids:
        if gun_uid in DROPPED_UID_TO_GUN_ID:
            del DROPPED_UID_TO_GUN_ID[gun_uid]


def retire_equips(client: GFLClient, equip_uids: list):
    # 夜战自动拆解功能暂未启用。
    return False


def perform_deferred_night_recovery():
    return


def farm_worker():
    global stop_macro_flag, stop_micro_flag, worker_mode, current_worker_thread, TEAM_SWITCH_PENDING

    if CONFIG["SIGN_KEY"] == DEFAULT_SIGN:
        print("[!] SIGN_KEY 为默认值，请先通过 -a 获取 UID / SIGN。")
        worker_mode, current_worker_thread = None, None
        return

    client = GFLClient(CONFIG["USER_UID"], CONFIG["SIGN_KEY"], CONFIG["BASE_URL"])
    mvp_gen = get_mvp_generator()

    reset_run_stats()
    RUN_STATS["start_time"] = time.time()
    init_run_target_counts()

    if CONFIG.get("MODE_NAME") == "team":
        schedule_label = "整队满级后切换" if CONFIG.get("TRAIN_SCHEDULE_MODE") == "full" else "均等练级轮转"
        print("[*] 当前为练级模式，将默认从梯队一开始轮转，共 %d 个梯队。" % len(CAPTURED_TEAM_CONFIGS))
        print("[*] 当前练级调度：%s" % schedule_label)
        reset_training_progress()
    else:
        print("[*] 当前为打捞模式，使用单人编队。")
    print("=== GFL Protocol Auto-Farming Started (EPA) ===")
    for macro in range(1, CONFIG["MACRO_LOOPS"] + 1):
        if stop_macro_flag:
            break
        print("\n=== MACRO BATCH %d / %d ===" % (macro, CONFIG['MACRO_LOOPS']))

        batch_guns = []
        batch_equips = []
        night_retire_attempted_after_failure = False
        for micro in range(1, CONFIG["MISSIONS_PER_RETIRE"] + 1):
            if stop_micro_flag or stop_macro_flag:
                break

            print("\n[*] 开始第 %d / %d 次 Micro 轮次……" % (micro, CONFIG["MISSIONS_PER_RETIRE"]))
            dropped = farm_mission_epa(client, get_current_team_id(), mvp_gen)

            if dropped is None:
                print("[-] 本轮失败或中止，正在放弃关卡……")
                client.send_request(API_MISSION_ABORT, {"mission_id": CONFIG["MISSION_ID"]})
                time.sleep(3)

                if CONFIG.get("SELECTED_DIFFICULTY") == "夜战":
                    print("[!] 夜战当前仅支持自动打捞，不支持自动拆解。")
                    print("[!] 若因仓库问题无法继续，请手动检查装备仓库空位后再重新运行。")
                    stop_macro_flag = True
                    stop_micro_flag = True
                    break

                continue

            batch_guns.extend(dropped.get("guns", []))
            if "batch_equips" not in locals():
                batch_equips = []
            new_equips = dropped.get("equips", [])
            batch_equips.extend(new_equips)

            night_retire_attempted_after_failure = False
            time.sleep(1)

            if CONFIG.get("MODE_NAME") == "team" and TEAM_SWITCH_PENDING:
                advance_to_next_training_team()
                break

            if CONFIG.get("MODE_NAME") == "team" and CONFIG.get("TRAIN_SCHEDULE_MODE") == "equal":
                switch_to_next_available_training_team("当前梯队已练级一轮")
                break

        if CONFIG.get("SELECTED_DIFFICULTY") == "夜战":
            if batch_equips:
                print("[*] 夜战模式：当前仅支持自动打捞，本轮不执行装备拆解。")
        else:
            retire_guns(client, batch_guns)
        time.sleep(2)
        if stop_micro_flag:
            break

    RUN_STATS["end_time"] = time.time()
    print("\n[*] 打捞运行结束。")
    print_run_summary()
    worker_mode, current_worker_thread = None, None
    reopen_stage_selection_menu()


if __name__ == '__main__':
    print_main_menu()
    while True:
        try:
            cmd = input("GFL-EPA> ").strip()
            if not cmd:
                continue
            cmd_prefix = cmd.split()[0]

            if handle_selection_input(cmd):
                continue

            if cmd_prefix == '-a':
                # 优先复用已抓到的动态密钥，直接请求 Index/index。
                if not CONFIG.get("INDEX_FETCH_READY", False) and not proxy_instance and has_usable_dynamic_keys() and CONFIG.get("MODE_SELECTED_EARLY"):
                    print("[*] 检测到已有可用动态密钥，优先复用当前 UID / SIGN 直接请求 Index/index。")
                    ok = request_index_and_prepare_configs()
                    if ok:
                        continue
                    print("[!] 复用当前 UID / SIGN 请求 Index/index 失败。")
                    print("[*] 将回退到重新开启代理并抓取 UID / SIGN 的流程。")

                # Phase 1: start proxy and capture UID/SIGN
                if not CONFIG.get("INDEX_FETCH_READY", False) and not proxy_instance:
                    if CONFIG.get("MODE_SELECTED_EARLY") and CONFIG.get("MODE_NAME") in ("team", "single"):
                        mode_cmd = "-team" if CONFIG.get("MODE_NAME") == "team" else "-single"
                        print("[*] 已保留上次选择的模式：%s" % ("练级模式" if mode_cmd == "-team" else "打捞模式"))
                    else:
                        print_gun_mode_menu()
                        mode_cmd = normalize_menu_input(input("GFL-EPA(模式)> ").strip())
                        if not mode_cmd:
                            mode_cmd = "-team"
                        if mode_cmd not in ("-team", "-single"):
                            print("[!] 无效输入，请重新输入 -a 后选择 -team 或 -single。")
                            continue

                    if mode_cmd == "-team":
                        CONFIG["MODE_NAME"] = "team"
                        CONFIG["SINGLE_GUN_MODE"] = False
                        CONFIG["MODE_SELECTED_EARLY"] = True

                        print("[*] 练级调度说明：")
                        print("    -full  = 先把当前梯队一直练到全员满级，再切换到下一梯队。（默认）")
                        print("    -equal = 每个梯队先各练一轮，再轮流继续，直到所有梯队满级。")
                        print("[*] 提示：直接按回车将使用默认配置（-full），输入 -back 或 b 可返回编队模式选择。")
                        schedule_cmd = normalize_menu_input(input("GFL-EPA(练级调度: -full/-equal, 默认-full)> ").strip())
                        if schedule_cmd == "-back":
                            print_gun_mode_menu()
                            continue
                        if schedule_cmd == "-equal":
                            CONFIG["TRAIN_SCHEDULE_MODE"] = "equal"
                            print("[*] 已选择均等练级：可以理解为每队轮流练一遍，再继续下一轮。")
                        else:
                            CONFIG["TRAIN_SCHEDULE_MODE"] = "full"
                            print("[*] 已选择整队练满：可以理解为先练满这一队，再换下一队。")

                        print("[*] 梯队数量说明：输入的数量表示从第一梯队开始，往后总共要练多少个梯队。")
                        print("[*] 例如输入 3，则表示练级梯队为：第1队、第2队、第3队。")
                        print("[*] 提示：直接按回车将使用默认配置（1）。")
                        print("[*] 提示：输入 -back 或 b 可返回练级调度选择。")
                        count_str = input("GFL-EPA(梯队数量, 默认1)> ").strip()
                        if count_str in ("-back", "b"):
                            print("[*] 已返回练级调度选择。")
                            continue
                        team_count = 1
                        if count_str:
                            try:
                                team_count = max(1, min(10, int(count_str)))
                            except Exception:
                                team_count = 1
                        CONFIG["TRAIN_TEAM_COUNT"] = team_count
                        CONFIG["AUTO_CAPTURE_EXPECTED_COUNT"] = team_count
                        reset_captured_team_configs()
                        reset_training_progress()
                        print("[*] 已选择练级模式，将默认从梯队一开始轮转，共需解析 %d 个梯队。" % team_count)
                    else:
                        CONFIG["MODE_NAME"] = "single"
                        CONFIG["SINGLE_GUN_MODE"] = True
                        CONFIG["MODE_SELECTED_EARLY"] = True
                        CONFIG["TRAIN_TEAM_COUNT"] = 1
                        CONFIG["AUTO_CAPTURE_EXPECTED_COUNT"] = 1
                        reset_captured_team_configs()
                        print("[*] 已选择打捞模式，将解析单人梯队配置。")
                        print("[*] 提示：single 模式仅使用梯队1，请在游戏内将梯队1配置为单人编队后再抓取。")

                    reset_auto_capture_state()
                    CONFIG["AUTO_MONITOR_MODE"] = True
                    CONFIG["INDEX_FETCH_READY"] = False
                    proxy_instance = GFLProxy(CONFIG["PROXY_PORT"], STATIC_KEY, on_traffic)
                    proxy_instance.start()
                    set_windows_proxy(True, "127.0.0.1:%d" % CONFIG['PROXY_PORT'])
                    worker_mode = 'a'
                    print("[*] 一体化代理已启动，端口 %d。Windows 代理已设置。" % CONFIG['PROXY_PORT'])
                    print("[*] 登录后会先自动获取 UID / SIGN。")
                    print("[*] 未使用 8080 端口，当前代理端口为 %d。" % CONFIG['PROXY_PORT'])
                    print("[*] 获取 UID/SIGN 后，请等待游戏完全进入指挥官主界面。")
                    print("[*] 然后再次输入 -a，程序会主动请求 Index/index 并解析梯队。")
                    continue

                # Phase 2: stop proxy and actively request Index/index
                if CONFIG.get("INDEX_FETCH_READY", False):
                    if proxy_instance:
                        print("[*] 发送 Index/index 请求前，正在停止代理……")
                        stop_proxy_instance()
                        time.sleep(1)
                    CONFIG["AUTO_MONITOR_MODE"] = False
                    CONFIG["INDEX_FETCH_READY"] = False
                    request_index_and_prepare_configs()
                    continue

                if proxy_instance:
                    print("[!] 代理已在运行！ 请先完成登录并等待 UID/SIGN 抓取。")
                    continue

                print("[!] 尚未抓取到有效 UID/SIGN，请先重新输入 -a 启动代理。")

            elif cmd_prefix == '-r':
                if MENU_STATE["selection_unlocked"]:
                    if CONFIG["SELECTED_DIFFICULTY"] is None or CONFIG["SELECTED_STAGE"] is None or CONFIG["SELECTED_TARGET_LABEL"] is None:
                        print("[!] 请先完成打捞菜单选择。")
                        continue
                    if MENU_STATE["awaiting_run_confirm"] or MENU_STATE["awaiting_stop_on_max"]:
                        print("[!] 请先完成满级停机设置与运行前确认，或输入 -back 返回上一级菜单。")
                        continue
                    if CONFIG.get("MODE_NAME") == "team" and not CAPTURED_TEAM_CONFIGS:
                        print("[!] 练级模式尚未抓取到有效梯队配置。请先执行 -a。")
                        continue

                if worker_mode == 'c' and proxy_instance:
                    print("[*] Stopping Proxy to begin farming...")
                    proxy_instance.stop()
                    set_windows_proxy(False)
                    proxy_instance = None
                    time.sleep(1)

                stop_macro_flag, stop_micro_flag = False, False
                worker_mode = 'r'
                current_worker_thread = threading.Thread(target=farm_worker)
                current_worker_thread.daemon = True
                current_worker_thread.start()

            elif cmd_prefix == '-q':
                stop_macro_flag = True
                print("[*] 将在当前 MACRO 批次结束后停止……")
            elif cmd_prefix == '-Q':
                stop_micro_flag = True
                print("[*] 将在当前 MICRO 轮次结束后停止……")
            elif cmd_prefix == '-s':
                if proxy_instance:
                    CONFIG["AUTO_MONITOR_MODE"] = False
                    stop_proxy_instance()
                    print("[*] 代理已安全停止。")
                else:
                    print("[!] 代理未在运行。")
            elif cmd_prefix == '-E':
                if proxy_instance:
                    proxy_instance.stop()
                set_windows_proxy(False)
                CONFIG["AUTO_MONITOR_MODE"] = False
                stop_macro_flag, stop_micro_flag = True, True
                print("[*] 已安全退出，Windows 代理已恢复。")
                sys.exit(0)
            else:
                if MENU_STATE["selection_unlocked"]:
                    if MENU_STATE["difficulty"] is None:
                        print("[!] 无效输入，请输入：普通 / 紧急 / 夜战，也可输入：p / j / y")
                    elif MENU_STATE["stage"] is None:
                        print("[!] 无效输入，请输入对应关卡名称，例如：A-10，也可输入 a10，或输入 -back / b 返回难度菜单")
                    elif MENU_STATE["awaiting_filter_protection"]:
                        print("[!] 无效输入，请输入 -protecton / -protectoff，或 on / off，或输入 -back / b 返回上一级菜单")
                    elif MENU_STATE["awaiting_stop_on_max"]:
                        print("[!] 无效输入，请输入 -stopmax / -keepmax，或 sm / km，或输入 -back / b 返回上一级菜单")
                    elif MENU_STATE["awaiting_run_confirm"]:
                        print("[!] 无效输入，请输入 -y 确认运行，或输入 -back 返回上一级菜单")
                    elif MENU_STATE["stage"] is not None and get_stage_data(MENU_STATE["difficulty"], MENU_STATE["stage"]):
                        opt_keys = list(get_stage_options(MENU_STATE["difficulty"], MENU_STATE["stage"]).keys())
                        print("[!] 无效输入，请输入 %s，也可直接输入数字 1/2/3...，或输入 -back / b 返回上一级菜单" % " / ".join(opt_keys))
                    else:
                        print("[!] 当前菜单暂未实现。")
                else:
                    print("[!] 未知命令: %s" % cmd)

        except KeyboardInterrupt:
            print("\n[!] Use '-E' to exit safely!")
