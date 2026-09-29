# Tournament stageB_safe_ref

| arm | n | score | ex-bonus | median | SD | vs ref (ex-bonus) | W/T/L vs ref | vs sweep (ex-bonus) | flips | run | fire in flight | proj. safe pick | steps | calls/game | p50 ms | $/game |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| safe | 50 | 542 | 386 | 525 | 161.7 | +116 [+88,+143] (all: +212 [+155,+269]) | 43/0/7 | +121 [+84,+159] | 0.1813 | 2.2146 | 0.498 | 0.9995 | 1097 | 1097.2 | 99.0 | 0.02614 |
| ref | 50 | 330 | 270 | 270 | 163.8 | - (all: -) | - | +5 [-36,+47] | 0.2944 | 2.9618 | 0.2524 | 0.1801 | 817 | 817.2 | 98.0 | 0.01934 |
| control_sweep | 50 | 281 | 265 | 288 | 138.5 | -5 [-47,+36] (all: -49 [-113,+14]) | 23/1/26 | - | 0.0219 | 43.2524 | 0.0 | 0.8928 | 672 | 0.0 | 0.0 | 0.0 |
| control_right | 50 | 248 | 248 | 250 | 4.5 | -22 [-48,+4] (all: -82 [-128,-38]) | 20/1/29 | -17 [-51,+16] | 0.0 | 521.3 | 0.0 | 0.6609 | 521 | 0.0 | 0.0 | 0.0 |
| random__raw | 50 | 147 | 135 | 130 | 97.2 | -135 [-164,-106] (all: -183 [-227,-142]) | 3/2/45 | -130 [-168,-93] | 0.4988 | 1.504 | 0.5 | 0.4929 | 513 | 0.0 | 0.0 | 0.0 |

Brackets: bootstrap 95% CI of the paired mean difference. Ex-bonus = score minus bonus-ship (>=50 pt) rewards.

```
{
 "tag": "stageB_safe_ref",
 "exp": [
  "ufa/traces/exp006_tournament"
 ],
 "arms": {
  "control_right": {
   "n_games": 50,
   "performance": {
    "score_mean": 248.1,
    "score_median": 250.0,
    "score_sd": 4.5,
    "score_q10_q25_q75_q90": [
     240.0,
     250.0,
     250.0,
     250.0
    ],
    "score_min": 235.0,
    "score_max": 250.0,
    "score_ex_bonus_mean": 248.1,
    "score_ex_bonus_median": 250.0,
    "bonus_pts_per_game": 0.0,
    "games_with_bonus": 0,
    "steps_per_game": 521.3,
    "steps_per_life": 173.8,
    "points_per_100_steps": 48.314,
    "kills_per_100_steps": 3.4478,
    "top_row_kills_per_game": 2.0
   },
   "behavior": {
    "reversal_rate": 0.0,
    "run_length": 521.3,
    "move_rate": 1.0,
    "fire_occupancy": 0.3193,
    "fire_while_shot_active": 0.0,
    "fire_immediately_when_ready": 1.0,
    "left_wall_share": 0.0751,
    "right_wall_share": 0.725,
    "lane_threat_evasion_rate": 0.9346,
    "projected_threat_share": 0.0476,
    "projected_threat_safe_pick_rate": 0.6609,
    "deaths_by_region": {
     "right_wall": 150
    }
   },
   "system": {
    "model_calls_per_game": 0.0,
    "calls_per_step": 0.0,
    "latency_p50_ms_median_of_games": 0.0,
    "latency_p95_ms_median_of_games": 0.0,
    "input_chars_per_decision": 202.958,
    "input_tokens_per_call": null,
    "cost_per_decision_usd": null,
    "cost_per_game_usd": 0.0,
    "cost_total_usd": 0.0,
    "fallbacks_total": 0,
    "errors_by_status": {},
    "retries_total": 0,
    "mean_confidence": null,
    "served_models": [
     "scripted-right"
    ]
   },
   "vs_ref": {
    "score": {
     "n": 50,
     "mean": -81.6,
     "median": -22.5,
     "sd": 163.0,
     "ci95_bootstrap": [
      -127.8,
      -37.6
     ],
     "effect_size_dz": -0.5,
     "jev_wins": 20,
     "ties": 1,
     "jev_losses": 29,
     "sign_flip_p": 0.0009,
     "sign_test_p": 0.2529
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": -21.6,
     "median": -10.0,
     "sd": 96.2,
     "ci95_bootstrap": [
      -47.9,
      4.2
     ],
     "effect_size_dz": -0.22,
     "jev_wins": 21,
     "ties": 1,
     "jev_losses": 28,
     "sign_flip_p": 0.1175,
     "sign_test_p": 0.3916
    }
   },
   "vs_sweep": {
    "score": {
     "n": 50,
     "mean": -33.0,
     "median": -40.0,
     "sd": 138.9,
     "ci95_bootstrap": [
      -72.3,
      4.4
     ],
     "effect_size_dz": -0.24,
     "jev_wins": 17,
     "ties": 0,
     "jev_losses": 33,
     "sign_flip_p": 0.1001,
     "sign_test_p": 0.0328
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": -17.0,
     "median": -37.5,
     "sd": 120.1,
     "ci95_bootstrap": [
      -50.6,
      16.3
     ],
     "effect_size_dz": -0.14,
     "jev_wins": 19,
     "ties": 0,
     "jev_losses": 31,
     "sign_flip_p": 0.3284,
     "sign_test_p": 0.1189
    }
   }
  },
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
     "mean": -48.6,
     "median": -20.0,
     "sd": 227.6,
     "ci95_bootstrap": [
      -112.6,
      13.6
     ],
     "effect_size_dz": -0.21,
     "jev_wins": 23,
     "ties": 1,
     "jev_losses": 26,
     "sign_flip_p": 0.134,
     "sign_test_p": 0.7754
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": -4.6,
     "median": 17.5,
     "sd": 152.3,
     "ci95_bootstrap": [
      -47.1,
      36.3
     ],
     "effect_size_dz": -0.03,
     "jev_wins": 26,
     "ties": 1,
     "jev_losses": 23,
     "sign_flip_p": 0.8343,
     "sign_test_p": 0.7754
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
     "mean": -183.0,
     "median": -160.0,
     "sd": 155.3,
     "ci95_bootstrap": [
      -226.7,
      -141.5
     ],
     "effect_size_dz": -1.18,
     "jev_wins": 3,
     "ties": 2,
     "jev_losses": 45,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": -135.0,
     "median": -135.0,
     "sd": 106.4,
     "ci95_bootstrap": [
      -163.5,
      -105.8
     ],
     "effect_size_dz": -1.27,
     "jev_wins": 4,
     "ties": 3,
     "jev_losses": 43,
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
   "vs_ref": {
    "score": {
     "n": 50,
     "mean": 212.5,
     "median": 217.5,
     "sd": 209.5,
     "ci95_bootstrap": [
      154.7,
      269.3
     ],
     "effect_size_dz": 1.01,
     "jev_wins": 43,
     "ties": 0,
     "jev_losses": 7,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 50,
     "mean": 116.5,
     "median": 105.0,
     "sd": 103.2,
     "ci95_bootstrap": [
      88.1,
      143.1
     ],
     "effect_size_dz": 1.13,
     "jev_wins": 43,
     "ties": 1,
     "jev_losses": 6,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
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
  }
 }
}
```
