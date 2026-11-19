window.LESSON = {
  "items": [
    {
      "id": "Q1",
      "stem": "解 x + 3 = 5",
      "answer": "2",
      "wrong_answer_map": {
        "8": "M1"
      },
      "kp": [
        "K8"
      ]
    },
    {
      "id": "Q2",
      "stem": "解 3x = 12",
      "answer": "4",
      "wrong_answer_map": {
        "1/4": "M6",
        "36": "M6"
      },
      "kp": [
        "K6"
      ]
    },
    {
      "id": "Q3",
      "stem": "解 −2x = 8",
      "answer": "-4",
      "wrong_answer_map": {
        "4": "M7",
        "-1/4": "M6"
      },
      "kp": [
        "K6"
      ]
    },
    {
      "id": "Q4",
      "stem": "解 2(x + 3) = 10",
      "answer": "2",
      "wrong_answer_map": {
        "7/2": "M5"
      },
      "kp": [
        "K9"
      ]
    },
    {
      "id": "Q5",
      "stem": "解 5 − 2(x − 1) = 3",
      "answer": "2",
      "wrong_answer_map": {
        "0": "M4"
      },
      "kp": [
        "K9"
      ]
    },
    {
      "id": "Q6",
      "stem": "解 x/2 + 1 = x/3",
      "answer": "-6",
      "wrong_answer_map": {
        "-1": "M2"
      },
      "kp": [
        "K10"
      ]
    },
    {
      "id": "Q7",
      "stem": "解 (x − 1)/2 = (x + 1)/3",
      "answer": "5",
      "wrong_answer_map": {
        "2": "M3"
      },
      "kp": [
        "K10"
      ]
    },
    {
      "id": "Q8",
      "stem": "解 4x − 3 = 2x + 5",
      "answer": "4",
      "wrong_answer_map": {
        "1/3": "M1"
      },
      "kp": [
        "K8"
      ]
    },
    {
      "id": "Q9",
      "stem": "不解方程，判断 x = 2 是不是 3x − 1 = 5 的解，说明理由",
      "answer": "是（代入两边均为5）",
      "wrong_answer_map": {
        "要先解方程": "M9"
      },
      "kp": [
        "K3"
      ]
    },
    {
      "id": "Q10",
      "stem": "「2x + 4 = 10 = 2x = 6 = x = 3」这样写对吗？",
      "answer": "不对",
      "wrong_answer_map": {
        "答案对就行": "M8"
      },
      "kp": [
        "P6"
      ]
    },
    {
      "id": "Q11",
      "stem": "甲班比乙班多5人，两班共85人，设乙班x人，列方程求解",
      "answer": "x + (x + 5) = 85；x = 40",
      "wrong_answer_map": {
        "x + (x − 5) = 85": "M10"
      },
      "kp": [
        "K12",
        "K13"
      ]
    },
    {
      "id": "Q12",
      "stem": "解 (x − 1)/2 − (x + 2)/3 = 1",
      "answer": "13",
      "wrong_answer_map": {
        "8": "M2",
        "5": "M4",
        "-1": "M1"
      },
      "kp": [
        "K10",
        "K9",
        "K8"
      ]
    }
  ],
  "students": [
    {
      "id": "S1",
      "name": "小川",
      "demo_answer": "8",
      "misconception": "M2",
      "wrong_steps": [
        "3(x−1) − 2(x+2) = 1",
        "3x − 3 − 2x − 4 = 1",
        "x − 7 = 1",
        "x = 8"
      ],
      "traits": {
        "confidence": "high",
        "hint_reliance": "low",
        "checks_answer": false,
        "preferred": "rule_clear"
      },
      "strategy": "代入检验制造认知冲突（x=8 代回左边=1/6≠1）+天平图“每份都乘6”",
      "transfer": {
        "q": "(2x + 1)/3 − 1 = x/2",
        "a": "4"
      },
      "disagree_demo": "我本来就会去分母 → 验证题 → 模型改为“会方法但不检验”",
      "responses": [
        {
          "item": "Q1",
          "response": "2",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 49
        },
        {
          "item": "Q2",
          "response": "4",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 43
        },
        {
          "item": "Q3",
          "response": "-4",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 74
        },
        {
          "item": "Q4",
          "response": "2",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 77
        },
        {
          "item": "Q5",
          "response": "2",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 72
        },
        {
          "item": "Q6",
          "response": "-1",
          "correct": false,
          "misconception": "M2",
          "used_hint": false,
          "time_sec": 85
        },
        {
          "item": "Q7",
          "response": "5",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 44
        },
        {
          "item": "Q8",
          "response": "4",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 75
        },
        {
          "item": "Q9",
          "response": "是（代入两边均为5）",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 92
        },
        {
          "item": "Q10",
          "response": "不对",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 54
        },
        {
          "item": "Q11",
          "response": "x + (x + 5) = 85；x = 40",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 77
        },
        {
          "item": "Q12",
          "response": "8",
          "correct": false,
          "misconception": "M2",
          "used_hint": false,
          "time_sec": 116
        }
      ]
    },
    {
      "id": "S2",
      "name": "小禾",
      "demo_answer": "5",
      "misconception": "M4",
      "wrong_steps": [
        "3(x−1) − 2(x+2) = 6",
        "3x − 3 − 2x + 4 = 6",
        "x + 1 = 6",
        "x = 5"
      ],
      "traits": {
        "confidence": "low",
        "hint_reliance": "high",
        "checks_answer": true,
        "preferred": "visual"
      },
      "strategy": "分步颜色拆解 (−2)·x 与 (−2)·2 + 慢速语音 + 鼓励反馈",
      "transfer": {
        "q": "4 − 3(x − 2) = 1",
        "a": "3"
      },
      "photo_diagnosis": "第2行 +4 处圈出",
      "responses": [
        {
          "item": "Q1",
          "response": "2",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 43
        },
        {
          "item": "Q2",
          "response": "4",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 42
        },
        {
          "item": "Q3",
          "response": "4",
          "correct": false,
          "misconception": "M7",
          "used_hint": true,
          "time_sec": 115
        },
        {
          "item": "Q4",
          "response": "2",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 58
        },
        {
          "item": "Q5",
          "response": "0",
          "correct": false,
          "misconception": "M4",
          "used_hint": true,
          "time_sec": 106
        },
        {
          "item": "Q6",
          "response": "-6",
          "correct": true,
          "misconception": null,
          "used_hint": true,
          "time_sec": 47
        },
        {
          "item": "Q7",
          "response": "5",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 75
        },
        {
          "item": "Q8",
          "response": "4",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 51
        },
        {
          "item": "Q9",
          "response": "是（代入两边均为5）",
          "correct": true,
          "misconception": null,
          "used_hint": true,
          "time_sec": 76
        },
        {
          "item": "Q10",
          "response": "不对",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 63
        },
        {
          "item": "Q11",
          "response": "x + (x + 5) = 85；x = 40",
          "correct": true,
          "misconception": null,
          "used_hint": true,
          "time_sec": 85
        },
        {
          "item": "Q12",
          "response": "5",
          "correct": false,
          "misconception": "M4",
          "used_hint": true,
          "time_sec": 84
        }
      ]
    },
    {
      "id": "S3",
      "name": "小远",
      "demo_answer": "-1",
      "misconception": "M1",
      "wrong_steps": [
        "3(x−1) − 2(x+2) = 6",
        "3x − 3 − 2x − 4 = 6",
        "x − 7 = 6",
        "x = 6 − 7",
        "x = −1"
      ],
      "traits": {
        "confidence": "medium",
        "hint_reliance": "medium",
        "checks_answer": false,
        "preferred": "real_life_context"
      },
      "strategy": "生活情境微课：天平两边同加7个砝码",
      "transfer": {
        "q": "5x − 7 = 2x + 8",
        "a": "5"
      },
      "checker_reject_demo": "初稿直接写出答案13 → 核查员以“直接泄题”退回 → 重做",
      "responses": [
        {
          "item": "Q1",
          "response": "8",
          "correct": false,
          "misconception": "M1",
          "used_hint": true,
          "time_sec": 116
        },
        {
          "item": "Q2",
          "response": "4",
          "correct": true,
          "misconception": null,
          "used_hint": true,
          "time_sec": 53
        },
        {
          "item": "Q3",
          "response": "-4",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 74
        },
        {
          "item": "Q4",
          "response": "2",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 60
        },
        {
          "item": "Q5",
          "response": "2",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 69
        },
        {
          "item": "Q6",
          "response": "-6",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 55
        },
        {
          "item": "Q7",
          "response": "5",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 84
        },
        {
          "item": "Q8",
          "response": "1/3",
          "correct": false,
          "misconception": "M1",
          "used_hint": true,
          "time_sec": 129
        },
        {
          "item": "Q9",
          "response": "是（代入两边均为5）",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 76
        },
        {
          "item": "Q10",
          "response": "不对",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 71
        },
        {
          "item": "Q11",
          "response": "x + (x + 5) = 85；x = 40",
          "correct": true,
          "misconception": null,
          "used_hint": false,
          "time_sec": 86
        },
        {
          "item": "Q12",
          "response": "-1",
          "correct": false,
          "misconception": "M1",
          "used_hint": true,
          "time_sec": 108
        }
      ]
    }
  ],
  "knowledge_points": [
    {
      "id": "P1",
      "title": "用字母表示数、代数式",
      "prerequisites": [],
      "group": "prereq"
    },
    {
      "id": "P2",
      "title": "有理数运算（含符号法则）",
      "prerequisites": [],
      "group": "prereq"
    },
    {
      "id": "P3",
      "title": "合并同类项",
      "prerequisites": [
        "P1"
      ],
      "group": "prereq"
    },
    {
      "id": "P4",
      "title": "去括号法则",
      "prerequisites": [
        "P2",
        "P3"
      ],
      "group": "prereq"
    },
    {
      "id": "P5",
      "title": "最小公倍数与分数的基本性质",
      "prerequisites": [],
      "group": "prereq"
    },
    {
      "id": "P6",
      "title": "等式与等号的意义",
      "prerequisites": [],
      "group": "prereq"
    },
    {
      "id": "K1",
      "title": "方程的概念",
      "prerequisites": [
        "P1",
        "P6"
      ],
      "group": "core"
    },
    {
      "id": "K2",
      "title": "一元一次方程的概念",
      "prerequisites": [
        "K1"
      ],
      "group": "core"
    },
    {
      "id": "K3",
      "title": "方程的解与检验",
      "prerequisites": [
        "K1",
        "P2"
      ],
      "group": "core"
    },
    {
      "id": "K4",
      "title": "等式的性质1（两边同加减）",
      "prerequisites": [
        "P6"
      ],
      "group": "core"
    },
    {
      "id": "K5",
      "title": "等式的性质2（两边同乘除非零数）",
      "prerequisites": [
        "P6"
      ],
      "group": "core"
    },
    {
      "id": "K6",
      "title": "系数化为1",
      "prerequisites": [
        "K5",
        "P2"
      ],
      "group": "solve"
    },
    {
      "id": "K7",
      "title": "合并同类项解方程",
      "prerequisites": [
        "P3",
        "K6"
      ],
      "group": "solve"
    },
    {
      "id": "K8",
      "title": "移项",
      "prerequisites": [
        "K4"
      ],
      "group": "solve"
    },
    {
      "id": "K9",
      "title": "去括号解方程",
      "prerequisites": [
        "P4",
        "K8"
      ],
      "group": "solve"
    },
    {
      "id": "K10",
      "title": "去分母解方程",
      "prerequisites": [
        "P5",
        "K5",
        "K9"
      ],
      "group": "solve"
    },
    {
      "id": "K11",
      "title": "解一元一次方程的一般步骤",
      "prerequisites": [
        "K6",
        "K7",
        "K8",
        "K9",
        "K10"
      ],
      "group": "solve"
    },
    {
      "id": "K12",
      "title": "设未知数、找等量关系",
      "prerequisites": [
        "K1"
      ],
      "group": "apply"
    },
    {
      "id": "K13",
      "title": "和差倍分问题",
      "prerequisites": [
        "K12",
        "K11"
      ],
      "group": "apply"
    },
    {
      "id": "K14",
      "title": "行程问题",
      "prerequisites": [
        "K12",
        "K11"
      ],
      "group": "apply"
    },
    {
      "id": "K15",
      "title": "工程问题",
      "prerequisites": [
        "K12",
        "K11"
      ],
      "group": "apply"
    },
    {
      "id": "K16",
      "title": "解的合理性检验",
      "prerequisites": [
        "K3",
        "K12"
      ],
      "group": "apply"
    }
  ]
};
