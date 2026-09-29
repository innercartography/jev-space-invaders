# Tournament stageB_combos

| arm | n | score | ex-bonus | median | SD | vs ref (ex-bonus) | W/T/L vs ref | vs sweep (ex-bonus) | flips | run | fire in flight | proj. safe pick | steps | calls/game | p50 ms | $/game |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| safe_sweepwords | 20 | 756 | 586 | 678 | 295.4 | +344 [+255,+438] (all: +454 [+308,+601]) | 19/0/1 | +315 [+226,+416] | 0.2953 | 2.5985 | 0.0 | 1.0 | 1462 | 1462.2 | 114.9 | 0.03554 |
| safe_k4 | 20 | 599 | 429 | 590 | 205.2 | +188 [+132,+240] (all: +298 [+191,+400]) | 18/0/2 | +158 [+98,+217] | 0.0779 | 6.385 | 0.5695 | 0.6568 | 1192 | 298.6 | 114.1 | 0.00711 |
| safe_k2 | 20 | 609 | 409 | 625 | 177.2 | +168 [+111,+220] (all: +308 [+202,+404]) | 18/0/2 | +138 [+80,+195] | 0.1132 | 3.832 | 0.5205 | 0.7725 | 1144 | 572.5 | 112.0 | 0.01365 |
| safe_min | 20 | 542 | 392 | 550 | 122.7 | +151 [+114,+187] (all: +241 [+162,+310]) | 19/0/1 | +122 [+70,+174] | 0.1197 | 2.665 | 0.1169 | 0.9915 | 1107 | 1107.5 | 115.0 | 0.02401 |
| safe | 20 | 533 | 383 | 525 | 172.0 | +141 [+96,+182] (all: +231 [+138,+334]) | 17/0/3 | +112 [+62,+159] | 0.1886 | 2.1465 | 0.5039 | 1.0 | 1092 | 1091.8 | 103.1 | 0.026 |
| control_sweep | 20 | 271 | 271 | 290 | 117.5 | +29 [-34,+86] (all: -31 [-120,+52]) | 11/1/8 | - | 0.0221 | 42.875 | 0.0 | 0.8807 | 682 | 0.0 | 0.0 | 0.0 |
| ref | 20 | 302 | 242 | 232 | 167.2 | - (all: -) | - | -29 [-86,+34] | 0.2929 | 2.9725 | 0.2537 | 0.1723 | 751 | 750.8 | 102.3 | 0.01775 |

Brackets: bootstrap 95% CI of the paired mean difference. Ex-bonus = score minus bonus-ship (>=50 pt) rewards.

```
{
 "tag": "stageB_combos",
 "exp": [
  "ufa/traces/exp006_tournament"
 ],
 "arms": {
  "control_sweep": {
   "n_games": 20,
   "performance": {
    "score_mean": 270.8,
    "score_median": 290.0,
    "score_sd": 117.5,
    "score_q10_q25_q75_q90": [
     135.0,
     170.0,
     365.0,
     394.5
    ],
    "score_min": 55.0,
    "score_max": 470.0,
    "score_ex_bonus_mean": 270.8,
    "score_ex_bonus_median": 290.0,
    "bonus_pts_per_game": 0.0,
    "games_with_bonus": 0,
    "steps_per_game": 682.1,
    "steps_per_life": 239.3,
    "points_per_100_steps": 38.1905,
    "kills_per_100_steps": 2.759,
    "top_row_kills_per_game": 1.35
   },
   "behavior": {
    "reversal_rate": 0.0221,
    "run_length": 42.875,
    "move_rate": 1.0,
    "fire_occupancy": 0.2698,
    "fire_while_shot_active": 0.0,
    "fire_immediately_when_ready": 1.0,
    "left_wall_share": 0.086,
    "right_wall_share": 0.0388,
    "lane_threat_evasion_rate": 0.6348,
    "projected_threat_share": 0.0911,
    "projected_threat_safe_pick_rate": 0.8807,
    "deaths_by_region": {
     "middle": 56,
     "left_wall": 1
    }
   },
   "system": {
    "model_calls_per_game": 0.0,
    "calls_per_step": 0.0,
    "latency_p50_ms_median_of_games": 0.0,
    "latency_p95_ms_median_of_games": 0.0,
    "input_chars_per_decision": 205.73,
    "input_tokens_per_call": null,
    "cost_per_decision_usd": null,
    "cost_per_game_usd": 0.0,
    "cost_total_usd": 0.0,
    "fallbacks_total": 0,
    "errors_by_status": {},
    "retries_total": 0,
    "mean_confidence": null,
    "served_models": [
     "scripted-sweep"
    ]
   },
   "vs_ref": {
    "score": {
     "n": 20,
     "mean": -31.0,
     "median": 50.0,
     "sd": 203.4,
     "ci95_bootstrap": [
      -120.5,
      52.5
     ],
     "effect_size_dz": -0.15,
     "jev_wins": 11,
     "ties": 1,
     "jev_losses": 8,
     "sign_flip_p": 0.5014,
     "sign_test_p": 0.6476
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": 29.0,
     "median": 50.0,
     "sd": 141.9,
     "ci95_bootstrap": [
      -34.2,
      86.2
     ],
     "effect_size_dz": 0.2,
     "jev_wins": 13,
     "ties": 1,
     "jev_losses": 6,
     "sign_flip_p": 0.3826,
     "sign_test_p": 0.1671
    }
   }
  },
  "ref": {
   "n_games": 20,
   "performance": {
    "score_mean": 301.8,
    "score_median": 232.5,
    "score_sd": 167.2,
    "score_q10_q25_q75_q90": [
     159.0,
     180.0,
     420.0,
     536.0
    ],
    "score_min": 80.0,
    "score_max": 685.0,
    "score_ex_bonus_mean": 241.8,
    "score_ex_bonus_median": 217.5,
    "bonus_pts_per_game": 60.0,
    "games_with_bonus": 5,
    "steps_per_game": 750.8,
    "steps_per_life": 250.3,
    "points_per_100_steps": 38.5205,
    "kills_per_100_steps": 1.9375,
    "top_row_kills_per_game": 2.05
   },
   "behavior": {
    "reversal_rate": 0.2929,
    "run_length": 2.9725,
    "move_rate": 0.7288,
    "fire_occupancy": 0.4135,
    "fire_while_shot_active": 0.2537,
    "fire_immediately_when_ready": 0.8881,
    "left_wall_share": 0.7182,
    "right_wall_share": 0.0,
    "lane_threat_evasion_rate": 0.5469,
    "projected_threat_share": 0.1284,
    "projected_threat_safe_pick_rate": 0.1723,
    "deaths_by_region": {
     "left_wall": 45,
     "middle": 15
    }
   },
   "system": {
    "model_calls_per_game": 750.8,
    "calls_per_step": 1.0,
    "latency_p50_ms_median_of_games": 102.3,
    "latency_p95_ms_median_of_games": 175.2,
    "input_chars_per_decision": 202.565,
    "input_tokens_per_call": 563.0,
    "cost_per_decision_usd": 2.364e-05,
    "cost_per_game_usd": 0.01775,
    "cost_total_usd": 0.355,
    "fallbacks_total": 0,
    "errors_by_status": {},
    "retries_total": 0,
    "mean_confidence": 0.2317,
    "served_models": [
     "jev-1.13.0"
    ]
   },
   "vs_sweep": {
    "score": {
     "n": 20,
     "mean": 31.0,
     "median": -50.0,
     "sd": 203.4,
     "ci95_bootstrap": [
      -52.5,
      120.5
     ],
     "effect_size_dz": 0.15,
     "jev_wins": 8,
     "ties": 1,
     "jev_losses": 11,
     "sign_flip_p": 0.5014,
     "sign_test_p": 0.6476
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": -29.0,
     "median": -50.0,
     "sd": 141.9,
     "ci95_bootstrap": [
      -86.2,
      34.2
     ],
     "effect_size_dz": -0.2,
     "jev_wins": 6,
     "ties": 1,
     "jev_losses": 13,
     "sign_flip_p": 0.3826,
     "sign_test_p": 0.1671
    }
   }
  },
  "safe": {
   "n_games": 20,
   "performance": {
    "score_mean": 533.0,
    "score_median": 525.0,
    "score_sd": 172.0,
    "score_q10_q25_q75_q90": [
     315.0,
     382.5,
     642.5,
     708.0
    ],
    "score_min": 310.0,
    "score_max": 930.0,
    "score_ex_bonus_mean": 383.0,
    "score_ex_bonus_median": 385.0,
    "bonus_pts_per_game": 150.0,
    "games_with_bonus": 12,
    "steps_per_game": 1091.8,
    "steps_per_life": 839.8,
    "points_per_100_steps": 48.765,
    "kills_per_100_steps": 2.1585,
    "top_row_kills_per_game": 3.25
   },
   "behavior": {
    "reversal_rate": 0.1886,
    "run_length": 2.1465,
    "move_rate": 0.341,
    "fire_occupancy": 0.5462,
    "fire_while_shot_active": 0.5039,
    "fire_immediately_when_ready": 0.9088,
    "left_wall_share": 0.6121,
    "right_wall_share": 0.0,
    "lane_threat_evasion_rate": 0.3591,
    "projected_threat_share": 0.0454,
    "projected_threat_safe_pick_rate": 1.0,
    "deaths_by_region": {
     "middle": 18,
     "left_wall": 8
    }
   },
   "system": {
    "model_calls_per_game": 1091.8,
    "calls_per_step": 1.0,
    "latency_p50_ms_median_of_games": 103.1,
    "latency_p95_ms_median_of_games": 178.9,
    "input_chars_per_decision": 208.87,
    "input_tokens_per_call": 567.0,
    "cost_per_decision_usd": 2.381e-05,
    "cost_per_game_usd": 0.026,
    "cost_total_usd": 0.52,
    "fallbacks_total": 0,
    "errors_by_status": {},
    "retries_total": 0,
    "mean_confidence": 0.2102,
    "served_models": [
     "jev-1.13.0"
    ]
   },
   "vs_ref": {
    "score": {
     "n": 20,
     "mean": 231.2,
     "median": 197.5,
     "sd": 227.5,
     "ci95_bootstrap": [
      138.2,
      333.8
     ],
     "effect_size_dz": 1.02,
     "jev_wins": 17,
     "ties": 0,
     "jev_losses": 3,
     "sign_flip_p": 0.0003,
     "sign_test_p": 0.0026
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": 141.2,
     "median": 160.0,
     "sd": 101.6,
     "ci95_bootstrap": [
      95.8,
      181.8
     ],
     "effect_size_dz": 1.39,
     "jev_wins": 18,
     "ties": 0,
     "jev_losses": 2,
     "sign_flip_p": 0.0002,
     "sign_test_p": 0.0004
    }
   },
   "vs_sweep": {
    "score": {
     "n": 20,
     "mean": 262.2,
     "median": 272.5,
     "sd": 229.3,
     "ci95_bootstrap": [
      168.5,
      362.5
     ],
     "effect_size_dz": 1.14,
     "jev_wins": 19,
     "ties": 0,
     "jev_losses": 1,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": 112.2,
     "median": 112.5,
     "sd": 114.3,
     "ci95_bootstrap": [
      62.5,
      159.2
     ],
     "effect_size_dz": 0.98,
     "jev_wins": 18,
     "ties": 0,
     "jev_losses": 2,
     "sign_flip_p": 0.0006,
     "sign_test_p": 0.0004
    }
   }
  },
  "safe_k2": {
   "n_games": 20,
   "performance": {
    "score_mean": 609.2,
    "score_median": 625.0,
    "score_sd": 177.2,
    "score_q10_q25_q75_q90": [
     360.0,
     515.0,
     682.5,
     825.0
    ],
    "score_min": 300.0,
    "score_max": 1005.0,
    "score_ex_bonus_mean": 409.2,
    "score_ex_bonus_median": 420.0,
    "bonus_pts_per_game": 200.0,
    "games_with_bonus": 15,
    "steps_per_game": 1144.45,
    "steps_per_life": 915.6,
    "points_per_100_steps": 53.1485,
    "kills_per_100_steps": 2.2035,
    "top_row_kills_per_game": 3.6
   },
   "behavior": {
    "reversal_rate": 0.1132,
    "run_length": 3.832,
    "move_rate": 0.3444,
    "fire_occupancy": 0.5491,
    "fire_while_shot_active": 0.5205,
    "fire_immediately_when_ready": 0.7409,
    "left_wall_share": 0.5846,
    "right_wall_share": 0.0,
    "lane_threat_evasion_rate": 0.4309,
    "projected_threat_share": 0.0582,
    "projected_threat_safe_pick_rate": 0.7725,
    "deaths_by_region": {
     "middle": 18,
     "left_wall": 7
    }
   },
   "system": {
    "model_calls_per_game": 572.5,
    "calls_per_step": 0.5,
    "latency_p50_ms_median_of_games": 112.0,
    "latency_p95_ms_median_of_games": 200.6,
    "input_chars_per_decision": 210.125,
    "input_tokens_per_call": 567.7,
    "cost_per_decision_usd": 2.385e-05,
    "cost_per_game_usd": 0.01365,
    "cost_total_usd": 0.273,
    "fallbacks_total": 0,
    "errors_by_status": {},
    "retries_total": 0,
    "mean_confidence": 0.2105,
    "served_models": [
     "jev-1.13.0"
    ]
   },
   "vs_ref": {
    "score": {
     "n": 20,
     "mean": 307.5,
     "median": 345.0,
     "sd": 235.2,
     "ci95_bootstrap": [
      202.0,
      403.8
     ],
     "effect_size_dz": 1.31,
     "jev_wins": 18,
     "ties": 0,
     "jev_losses": 2,
     "sign_flip_p": 0.0001,
     "sign_test_p": 0.0004
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": 167.5,
     "median": 190.0,
     "sd": 128.0,
     "ci95_bootstrap": [
      110.8,
      220.0
     ],
     "effect_size_dz": 1.31,
     "jev_wins": 17,
     "ties": 0,
     "jev_losses": 3,
     "sign_flip_p": 0.0001,
     "sign_test_p": 0.0026
    }
   },
   "vs_sweep": {
    "score": {
     "n": 20,
     "mean": 338.5,
     "median": 317.5,
     "sd": 187.8,
     "ci95_bootstrap": [
      262.2,
      421.2
     ],
     "effect_size_dz": 1.8,
     "jev_wins": 20,
     "ties": 0,
     "jev_losses": 0,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": 138.5,
     "median": 152.5,
     "sd": 137.2,
     "ci95_bootstrap": [
      79.5,
      194.8
     ],
     "effect_size_dz": 1.01,
     "jev_wins": 16,
     "ties": 0,
     "jev_losses": 4,
     "sign_flip_p": 0.0005,
     "sign_test_p": 0.0118
    }
   }
  },
  "safe_k4": {
   "n_games": 20,
   "performance": {
    "score_mean": 599.2,
    "score_median": 590.0,
    "score_sd": 205.2,
    "score_q10_q25_q75_q90": [
     375.5,
     442.5,
     687.5,
     825.5
    ],
    "score_min": 315.0,
    "score_max": 1045.0,
    "score_ex_bonus_mean": 429.2,
    "score_ex_bonus_median": 422.5,
    "bonus_pts_per_game": 170.0,
    "games_with_bonus": 13,
    "steps_per_game": 1192.4,
    "steps_per_life": 851.7,
    "points_per_100_steps": 50.13,
    "kills_per_100_steps": 2.211,
    "top_row_kills_per_game": 3.8
   },
   "behavior": {
    "reversal_rate": 0.0779,
    "run_length": 6.385,
    "move_rate": 0.3527,
    "fire_occupancy": 0.5571,
    "fire_while_shot_active": 0.5695,
    "fire_immediately_when_ready": 0.7247,
    "left_wall_share": 0.5941,
    "right_wall_share": 0.0,
    "lane_threat_evasion_rate": 0.3808,
    "projected_threat_share": 0.062,
    "projected_threat_safe_pick_rate": 0.6568,
    "deaths_by_region": {
     "middle": 21,
     "left_wall": 7
    }
   },
   "system": {
    "model_calls_per_game": 298.6,
    "calls_per_step": 0.25,
    "latency_p50_ms_median_of_games": 114.1,
    "latency_p95_ms_median_of_games": 198.0,
    "input_chars_per_decision": 208.8,
    "input_tokens_per_call": 566.9,
    "cost_per_decision_usd": 2.381e-05,
    "cost_per_game_usd": 0.00711,
    "cost_total_usd": 0.1422,
    "fallbacks_total": 0,
    "errors_by_status": {},
    "retries_total": 0,
    "mean_confidence": 0.2248,
    "served_models": [
     "jev-1.13.0"
    ]
   },
   "vs_ref": {
    "score": {
     "n": 20,
     "mean": 297.5,
     "median": 290.0,
     "sd": 244.7,
     "ci95_bootstrap": [
      190.8,
      399.5
     ],
     "effect_size_dz": 1.22,
     "jev_wins": 18,
     "ties": 0,
     "jev_losses": 2,
     "sign_flip_p": 0.0001,
     "sign_test_p": 0.0004
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": 187.5,
     "median": 205.0,
     "sd": 127.4,
     "ci95_bootstrap": [
      132.5,
      240.0
     ],
     "effect_size_dz": 1.47,
     "jev_wins": 18,
     "ties": 0,
     "jev_losses": 2,
     "sign_flip_p": 0.0001,
     "sign_test_p": 0.0004
    }
   },
   "vs_sweep": {
    "score": {
     "n": 20,
     "mean": 328.5,
     "median": 300.0,
     "sd": 231.4,
     "ci95_bootstrap": [
      228.8,
      427.8
     ],
     "effect_size_dz": 1.42,
     "jev_wins": 19,
     "ties": 0,
     "jev_losses": 1,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": 158.5,
     "median": 142.5,
     "sd": 140.9,
     "ci95_bootstrap": [
      98.0,
      217.0
     ],
     "effect_size_dz": 1.12,
     "jev_wins": 18,
     "ties": 0,
     "jev_losses": 2,
     "sign_flip_p": 0.0001,
     "sign_test_p": 0.0004
    }
   }
  },
  "safe_min": {
   "n_games": 20,
   "performance": {
    "score_mean": 542.5,
    "score_median": 550.0,
    "score_sd": 122.7,
    "score_q10_q25_q75_q90": [
     374.5,
     443.8,
     625.0,
     652.0
    ],
    "score_min": 315.0,
    "score_max": 805.0,
    "score_ex_bonus_mean": 392.5,
    "score_ex_bonus_median": 405.0,
    "bonus_pts_per_game": 150.0,
    "games_with_bonus": 14,
    "steps_per_game": 1107.45,
    "steps_per_life": 886.0,
    "points_per_100_steps": 48.9215,
    "kills_per_100_steps": 2.2315,
    "top_row_kills_per_game": 3.3
   },
   "behavior": {
    "reversal_rate": 0.1197,
    "run_length": 2.665,
    "move_rate": 0.3369,
    "fire_occupancy": 0.2206,
    "fire_while_shot_active": 0.1169,
    "fire_immediately_when_ready": 0.9558,
    "left_wall_share": 0.623,
    "right_wall_share": 0.0,
    "lane_threat_evasion_rate": 0.4434,
    "projected_threat_share": 0.0496,
    "projected_threat_safe_pick_rate": 0.9915,
    "deaths_by_region": {
     "middle": 17,
     "left_wall": 8
    }
   },
   "system": {
    "model_calls_per_game": 1107.5,
    "calls_per_step": 1.0,
    "latency_p50_ms_median_of_games": 115.0,
    "latency_p95_ms_median_of_games": 203.4,
    "input_chars_per_decision": 127.03,
    "input_tokens_per_call": 516.3,
    "cost_per_decision_usd": 2.168e-05,
    "cost_per_game_usd": 0.02401,
    "cost_total_usd": 0.4803,
    "fallbacks_total": 0,
    "errors_by_status": {},
    "retries_total": 0,
    "mean_confidence": 0.2587,
    "served_models": [
     "jev-1.13.0"
    ]
   },
   "vs_ref": {
    "score": {
     "n": 20,
     "mean": 240.8,
     "median": 280.0,
     "sd": 177.1,
     "ci95_bootstrap": [
      162.2,
      310.5
     ],
     "effect_size_dz": 1.36,
     "jev_wins": 19,
     "ties": 0,
     "jev_losses": 1,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": 150.8,
     "median": 157.5,
     "sd": 84.7,
     "ci95_bootstrap": [
      114.5,
      187.0
     ],
     "effect_size_dz": 1.78,
     "jev_wins": 19,
     "ties": 0,
     "jev_losses": 1,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   },
   "vs_sweep": {
    "score": {
     "n": 20,
     "mean": 271.8,
     "median": 237.5,
     "sd": 186.6,
     "ci95_bootstrap": [
      193.0,
      352.0
     ],
     "effect_size_dz": 1.46,
     "jev_wins": 19,
     "ties": 0,
     "jev_losses": 1,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": 121.8,
     "median": 145.0,
     "sd": 124.0,
     "ci95_bootstrap": [
      69.5,
      174.0
     ],
     "effect_size_dz": 0.98,
     "jev_wins": 16,
     "ties": 1,
     "jev_losses": 3,
     "sign_flip_p": 0.0005,
     "sign_test_p": 0.0044
    }
   }
  },
  "safe_sweepwords": {
   "n_games": 20,
   "performance": {
    "score_mean": 755.8,
    "score_median": 677.5,
    "score_sd": 295.4,
    "score_q10_q25_q75_q90": [
     489.0,
     563.8,
     921.2,
     1138.5
    ],
    "score_min": 320.0,
    "score_max": 1425.0,
    "score_ex_bonus_mean": 585.8,
    "score_ex_bonus_median": 557.5,
    "bonus_pts_per_game": 170.0,
    "games_with_bonus": 12,
    "steps_per_game": 1462.15,
    "steps_per_life": 886.2,
    "points_per_100_steps": 51.4805,
    "kills_per_100_steps": 2.409,
    "top_row_kills_per_game": 5.2
   },
   "behavior": {
    "reversal_rate": 0.2953,
    "run_length": 2.5985,
    "move_rate": 0.6956,
    "fire_occupancy": 0.1385,
    "fire_while_shot_active": 0.0,
    "fire_immediately_when_ready": 1.0,
    "left_wall_share": 0.3184,
    "right_wall_share": 0.0048,
    "lane_threat_evasion_rate": 0.5811,
    "projected_threat_share": 0.0761,
    "projected_threat_safe_pick_rate": 1.0,
    "deaths_by_region": {
     "left_wall": 10,
     "middle": 21,
     "right_wall": 2
    }
   },
   "system": {
    "model_calls_per_game": 1462.2,
    "calls_per_step": 1.0,
    "latency_p50_ms_median_of_games": 114.9,
    "latency_p95_ms_median_of_games": 214.5,
    "input_chars_per_decision": 208.84,
    "input_tokens_per_call": 578.8,
    "cost_per_decision_usd": 2.431e-05,
    "cost_per_game_usd": 0.03554,
    "cost_total_usd": 0.7109,
    "fallbacks_total": 0,
    "errors_by_status": {},
    "retries_total": 0,
    "mean_confidence": 0.4382,
    "served_models": [
     "jev-1.13.0"
    ]
   },
   "vs_ref": {
    "score": {
     "n": 20,
     "mean": 454.0,
     "median": 442.5,
     "sd": 338.1,
     "ci95_bootstrap": [
      308.2,
      601.0
     ],
     "effect_size_dz": 1.34,
     "jev_wins": 19,
     "ties": 0,
     "jev_losses": 1,
     "sign_flip_p": 0.0001,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": 344.0,
     "median": 285.0,
     "sd": 215.4,
     "ci95_bootstrap": [
      255.2,
      438.5
     ],
     "effect_size_dz": 1.6,
     "jev_wins": 19,
     "ties": 0,
     "jev_losses": 1,
     "sign_flip_p": 0.0001,
     "sign_test_p": 0.0
    }
   },
   "vs_sweep": {
    "score": {
     "n": 20,
     "mean": 485.0,
     "median": 425.0,
     "sd": 334.0,
     "ci95_bootstrap": [
      349.2,
      630.5
     ],
     "effect_size_dz": 1.45,
     "jev_wins": 20,
     "ties": 0,
     "jev_losses": 0,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 20,
     "mean": 315.0,
     "median": 232.5,
     "sd": 226.1,
     "ci95_bootstrap": [
      226.2,
      415.8
     ],
     "effect_size_dz": 1.39,
     "jev_wins": 20,
     "ties": 0,
     "jev_losses": 0,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   }
  }
 }
}
```
