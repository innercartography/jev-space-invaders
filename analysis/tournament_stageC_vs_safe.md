# Tournament stageC_vs_safe

| arm | n | score | ex-bonus | median | SD | vs ref (ex-bonus) | W/T/L vs ref | vs sweep (ex-bonus) | flips | run | fire in flight | proj. safe pick | steps | calls/game | p50 ms | $/game |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| safe_sweepwords | 50 | 711 | 543 | 630 | 310.6 | +156 [+107,+211] (all: +168 [+86,+255]) | 37/0/13 | +278 [+220,+341] | 0.297 | 2.5814 | 0.0 | 1.0 | 1405 | 1404.6 | 110.5 | 0.03415 |
| safe | 50 | 542 | 386 | 525 | 161.7 | - (all: -) | - | +121 [+84,+159] | 0.1813 | 2.2146 | 0.498 | 0.9995 | 1097 | 1097.2 | 99.0 | 0.02614 |
| ref | 50 | 330 | 270 | 270 | 163.8 | -116 [-143,-88] (all: -212 [-269,-155]) | 7/0/43 | +5 [-36,+47] | 0.2944 | 2.9618 | 0.2524 | 0.1801 | 817 | 817.2 | 98.0 | 0.01934 |
| control_sweep | 50 | 281 | 265 | 288 | 138.5 | -121 [-159,-84] (all: -261 [-323,-203]) | 5/0/45 | - | 0.0219 | 43.2524 | 0.0 | 0.8928 | 672 | 0.0 | 0.0 | 0.0 |
| random__raw | 50 | 147 | 135 | 130 | 97.2 | -252 [-276,-227] (all: -396 [-445,-345]) | 1/0/49 | -130 [-168,-93] | 0.4988 | 1.504 | 0.5 | 0.4929 | 513 | 0.0 | 0.0 | 0.0 |

Brackets: bootstrap 95% CI of the paired mean difference. Ex-bonus = score minus bonus-ship (>=50 pt) rewards.

```
{
 "tag": "stageC_vs_safe",
 "exp": [
  "ufa/traces/exp006_tournament"
 ],
 "arms": {
  "control_sweep": {
   "n_games": 50,
   "performance": {
    "score_mean": 281.1,
    "score_median": 287.5,
    "score_sd": 138.5,
    "score_q10_q25_q75_q90": [
     108.0,
     176.2,
     365.0,
     421.5
    ],
    "score_min": 55.0,
    "score_max": 775.0,
    "score_ex_bonus_mean": 265.1,
    "score_ex_bonus_median": 277.5,
    "bonus_pts_per_game": 16.0,
    "games_with_bonus": 4,
    "steps_per_game": 671.96,
    "steps_per_life": 240.0,
    "points_per_100_steps": 40.015,
    "kills_per_100_steps": 2.741,
    "top_row_kills_per_game": 1.3
   },
   "behavior": {
    "reversal_rate": 0.0219,
    "run_length": 43.2524,
    "move_rate": 1.0,
    "fire_occupancy": 0.2671,
    "fire_while_shot_active": 0.0,
    "fire_immediately_when_ready": 1.0,
    "left_wall_share": 0.0876,
    "right_wall_share": 0.0393,
    "lane_threat_evasion_rate": 0.6407,
    "projected_threat_share": 0.0912,
    "projected_threat_safe_pick_rate": 0.8928,
    "deaths_by_region": {
     "middle": 136,
     "left_wall": 3,
     "right_wall": 1
    }
   },
   "system": {
    "model_calls_per_game": 0.0,
    "calls_per_step": 0.0,
    "latency_p50_ms_median_of_games": 0.0,
    "latency_p95_ms_median_of_games": 0.0,
    "input_chars_per_decision": 205.452,
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
     "n": 50,
     "mean": -261.1,
     "median": -265.0,
     "sd": 215.2,
     "ci95_bootstrap": [
      -322.7,
      -202.6
     ],
     "effect_size_dz": -1.21,
     "jev_wins": 5,
     "ties": 0,
     "jev_losses": 45,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": -121.1,
     "median": -110.0,
     "sd": 135.1,
     "ci95_bootstrap": [
      -158.7,
      -83.7
     ],
     "effect_size_dz": -0.9,
     "jev_wins": 8,
     "ties": 0,
     "jev_losses": 42,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   }
  },
  "random__raw": {
   "n_games": 50,
   "performance": {
    "score_mean": 146.7,
    "score_median": 130.0,
    "score_sd": 97.2,
    "score_q10_q25_q75_q90": [
     45.0,
     75.0,
     208.8,
     255.5
    ],
    "score_min": 10.0,
    "score_max": 440.0,
    "score_ex_bonus_mean": 134.7,
    "score_ex_bonus_median": 130.0,
    "bonus_pts_per_game": 12.0,
    "games_with_bonus": 3,
    "steps_per_game": 512.72,
    "steps_per_life": 170.9,
    "points_per_100_steps": 26.8456,
    "kills_per_100_steps": 1.7664,
    "top_row_kills_per_game": 0.86
   },
   "behavior": {
    "reversal_rate": 0.4988,
    "run_length": 1.504,
    "move_rate": 0.6682,
    "fire_occupancy": 0.5036,
    "fire_while_shot_active": 0.5,
    "fire_immediately_when_ready": 0.5055,
    "left_wall_share": 0.3341,
    "right_wall_share": 0.004,
    "lane_threat_evasion_rate": 0.4107,
    "projected_threat_share": 0.1275,
    "projected_threat_safe_pick_rate": 0.4929,
    "deaths_by_region": {
     "left_wall": 28,
     "middle": 121,
     "right_wall": 1
    }
   },
   "system": {
    "model_calls_per_game": 0.0,
    "calls_per_step": 0.0,
    "latency_p50_ms_median_of_games": 0.0,
    "latency_p95_ms_median_of_games": 0.0,
    "input_chars_per_decision": 801.508,
    "input_tokens_per_call": null,
    "cost_per_decision_usd": null,
    "cost_per_game_usd": 0.0,
    "cost_total_usd": 0.0,
    "fallbacks_total": 0,
    "errors_by_status": {},
    "retries_total": 0,
    "mean_confidence": null,
    "served_models": [
     "random-policy"
    ]
   },
   "vs_ref": {
    "score": {
     "n": 50,
     "mean": -395.5,
     "median": -402.5,
     "sd": 186.2,
     "ci95_bootstrap": [
      -444.9,
      -344.9
     ],
     "effect_size_dz": -2.12,
     "jev_wins": 1,
     "ties": 0,
     "jev_losses": 49,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": -251.5,
     "median": -250.0,
     "sd": 88.9,
     "ci95_bootstrap": [
      -275.6,
      -227.4
     ],
     "effect_size_dz": -2.83,
     "jev_wins": 0,
     "ties": 0,
     "jev_losses": 50,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   },
   "vs_sweep": {
    "score": {
     "n": 50,
     "mean": -134.4,
     "median": -122.5,
     "sd": 165.3,
     "ci95_bootstrap": [
      -180.0,
      -88.7
     ],
     "effect_size_dz": -0.81,
     "jev_wins": 10,
     "ties": 1,
     "jev_losses": 39,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": -130.4,
     "median": -130.0,
     "sd": 137.2,
     "ci95_bootstrap": [
      -168.3,
      -92.8
     ],
     "effect_size_dz": -0.95,
     "jev_wins": 10,
     "ties": 1,
     "jev_losses": 39,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   }
  },
  "ref": {
   "n_games": 50,
   "performance": {
    "score_mean": 329.7,
    "score_median": 270.0,
    "score_sd": 163.8,
    "score_q10_q25_q75_q90": [
     178.5,
     210.0,
     457.5,
     533.5
    ],
    "score_min": 60.0,
    "score_max": 745.0,
    "score_ex_bonus_mean": 269.7,
    "score_ex_bonus_median": 260.0,
    "bonus_pts_per_game": 60.0,
    "games_with_bonus": 13,
    "steps_per_game": 817.24,
    "steps_per_life": 274.2,
    "points_per_100_steps": 38.9002,
    "kills_per_100_steps": 1.9886,
    "top_row_kills_per_game": 2.26
   },
   "behavior": {
    "reversal_rate": 0.2944,
    "run_length": 2.9618,
    "move_rate": 0.7452,
    "fire_occupancy": 0.4047,
    "fire_while_shot_active": 0.2524,
    "fire_immediately_when_ready": 0.8925,
    "left_wall_share": 0.7072,
    "right_wall_share": 0.0,
    "lane_threat_evasion_rate": 0.5593,
    "projected_threat_share": 0.1227,
    "projected_threat_safe_pick_rate": 0.1801,
    "deaths_by_region": {
     "left_wall": 110,
     "middle": 39
    }
   },
   "system": {
    "model_calls_per_game": 817.2,
    "calls_per_step": 1.0,
    "latency_p50_ms_median_of_games": 98.0,
    "latency_p95_ms_median_of_games": 174.0,
    "input_chars_per_decision": 203.506,
    "input_tokens_per_call": 563.5,
    "cost_per_decision_usd": 2.367e-05,
    "cost_per_game_usd": 0.01934,
    "cost_total_usd": 0.9671,
    "fallbacks_total": 0,
    "errors_by_status": {},
    "retries_total": 0,
    "mean_confidence": 0.226,
    "served_models": [
     "jev-1.13.0"
    ]
   },
   "vs_ref": {
    "score": {
     "n": 50,
     "mean": -212.5,
     "median": -217.5,
     "sd": 209.5,
     "ci95_bootstrap": [
      -269.3,
      -154.7
     ],
     "effect_size_dz": -1.01,
     "jev_wins": 7,
     "ties": 0,
     "jev_losses": 43,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": -116.5,
     "median": -105.0,
     "sd": 103.2,
     "ci95_bootstrap": [
      -143.1,
      -88.1
     ],
     "effect_size_dz": -1.13,
     "jev_wins": 6,
     "ties": 1,
     "jev_losses": 43,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   },
   "vs_sweep": {
    "score": {
     "n": 50,
     "mean": 48.6,
     "median": 20.0,
     "sd": 227.6,
     "ci95_bootstrap": [
      -13.6,
      112.6
     ],
     "effect_size_dz": 0.21,
     "jev_wins": 26,
     "ties": 1,
     "jev_losses": 23,
     "sign_flip_p": 0.134,
     "sign_test_p": 0.7754
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": 4.6,
     "median": -17.5,
     "sd": 152.3,
     "ci95_bootstrap": [
      -36.3,
      47.1
     ],
     "effect_size_dz": 0.03,
     "jev_wins": 23,
     "ties": 1,
     "jev_losses": 26,
     "sign_flip_p": 0.8343,
     "sign_test_p": 0.7754
    }
   }
  },
  "safe": {
   "n_games": 50,
   "performance": {
    "score_mean": 542.2,
    "score_median": 525.0,
    "score_sd": 161.7,
    "score_q10_q25_q75_q90": [
     315.0,
     420.0,
     640.0,
     780.0
    ],
    "score_min": 310.0,
    "score_max": 930.0,
    "score_ex_bonus_mean": 386.2,
    "score_ex_bonus_median": 390.0,
    "bonus_pts_per_game": 156.0,
    "games_with_bonus": 31,
    "steps_per_game": 1097.18,
    "steps_per_life": 945.8,
    "points_per_100_steps": 49.4186,
    "kills_per_100_steps": 2.1832,
    "top_row_kills_per_game": 3.22
   },
   "behavior": {
    "reversal_rate": 0.1813,
    "run_length": 2.2146,
    "move_rate": 0.347,
    "fire_occupancy": 0.5394,
    "fire_while_shot_active": 0.498,
    "fire_immediately_when_ready": 0.9105,
    "left_wall_share": 0.6281,
    "right_wall_share": 0.0,
    "lane_threat_evasion_rate": 0.3566,
    "projected_threat_share": 0.0464,
    "projected_threat_safe_pick_rate": 0.9995,
    "deaths_by_region": {
     "middle": 44,
     "left_wall": 14
    }
   },
   "system": {
    "model_calls_per_game": 1097.2,
    "calls_per_step": 1.0,
    "latency_p50_ms_median_of_games": 99.0,
    "latency_p95_ms_median_of_games": 175.3,
    "input_chars_per_decision": 209.182,
    "input_tokens_per_call": 567.2,
    "cost_per_decision_usd": 2.382e-05,
    "cost_per_game_usd": 0.02614,
    "cost_total_usd": 1.3068,
    "fallbacks_total": 0,
    "errors_by_status": {},
    "retries_total": 0,
    "mean_confidence": 0.207,
    "served_models": [
     "jev-1.13.0"
    ]
   },
   "vs_sweep": {
    "score": {
     "n": 50,
     "mean": 261.1,
     "median": 265.0,
     "sd": 215.2,
     "ci95_bootstrap": [
      202.6,
      322.7
     ],
     "effect_size_dz": 1.21,
     "jev_wins": 45,
     "ties": 0,
     "jev_losses": 5,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": 121.1,
     "median": 110.0,
     "sd": 135.1,
     "ci95_bootstrap": [
      83.7,
      158.7
     ],
     "effect_size_dz": 0.9,
     "jev_wins": 42,
     "ties": 0,
     "jev_losses": 8,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   }
  },
  "safe_sweepwords": {
   "n_games": 50,
   "performance": {
    "score_mean": 710.6,
    "score_median": 630.0,
    "score_sd": 310.6,
    "score_q10_q25_q75_q90": [
     358.0,
     496.2,
     838.8,
     1020.5
    ],
    "score_min": 315.0,
    "score_max": 1775.0,
    "score_ex_bonus_mean": 542.6,
    "score_ex_bonus_median": 545.0,
    "bonus_pts_per_game": 168.0,
    "games_with_bonus": 28,
    "steps_per_game": 1404.62,
    "steps_per_life": 949.1,
    "points_per_100_steps": 49.925,
    "kills_per_100_steps": 2.3168,
    "top_row_kills_per_game": 4.82
   },
   "behavior": {
    "reversal_rate": 0.297,
    "run_length": 2.5814,
    "move_rate": 0.6929,
    "fire_occupancy": 0.1335,
    "fire_while_shot_active": 0.0,
    "fire_immediately_when_ready": 1.0,
    "left_wall_share": 0.3232,
    "right_wall_share": 0.0033,
    "lane_threat_evasion_rate": 0.5747,
    "projected_threat_share": 0.0746,
    "projected_threat_safe_pick_rate": 1.0,
    "deaths_by_region": {
     "left_wall": 18,
     "middle": 54,
     "right_wall": 2
    }
   },
   "system": {
    "model_calls_per_game": 1404.6,
    "calls_per_step": 1.0,
    "latency_p50_ms_median_of_games": 110.5,
    "latency_p95_ms_median_of_games": 429.7,
    "input_chars_per_decision": 208.954,
    "input_tokens_per_call": 578.9,
    "cost_per_decision_usd": 2.431e-05,
    "cost_per_game_usd": 0.03415,
    "cost_total_usd": 1.7076,
    "fallbacks_total": 0,
    "errors_by_status": {
     "500": 2
    },
    "retries_total": 2,
    "mean_confidence": 0.4373,
    "served_models": [
     "jev-1.13.0"
    ]
   },
   "vs_ref": {
    "score": {
     "n": 50,
     "mean": 168.4,
     "median": 135.0,
     "sd": 303.5,
     "ci95_bootstrap": [
      85.7,
      255.0
     ],
     "effect_size_dz": 0.55,
     "jev_wins": 37,
     "ties": 0,
     "jev_losses": 13,
     "sign_flip_p": 0.0001,
     "sign_test_p": 0.0009
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": 156.4,
     "median": 127.5,
     "sd": 188.9,
     "ci95_bootstrap": [
      106.7,
      210.9
     ],
     "effect_size_dz": 0.83,
     "jev_wins": 43,
     "ties": 0,
     "jev_losses": 7,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   },
   "vs_sweep": {
    "score": {
     "n": 50,
     "mean": 429.5,
     "median": 395.0,
     "sd": 344.9,
     "ci95_bootstrap": [
      339.4,
      530.8
     ],
     "effect_size_dz": 1.25,
     "jev_wins": 47,
     "ties": 0,
     "jev_losses": 3,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": 277.5,
     "median": 235.0,
     "sd": 219.1,
     "ci95_bootstrap": [
      219.6,
      340.9
     ],
     "effect_size_dz": 1.27,
     "jev_wins": 45,
     "ties": 0,
     "jev_losses": 5,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   }
  }
 }
}
```
