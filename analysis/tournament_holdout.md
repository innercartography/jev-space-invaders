# Tournament holdout

| arm | n | score | ex-bonus | median | SD | vs ref (ex-bonus) | W/T/L vs ref | vs sweep (ex-bonus) | flips | run | fire in flight | proj. safe pick | steps | calls/game | p50 ms | $/game |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jev_final | 100 | 709 | 565 | 620 | 254.2 | +285 [+247,+326] (all: +383 [+328,+442]) | 92/0/8 | +285 [+247,+326] | 0.2991 | 2.5763 | 0.0 | 0.9999 | 1413 | 1412.9 | 101.2 | 0.03435 |
| control_sweep | 100 | 326 | 280 | 320 | 135.0 | - (all: -) | - | - | 0.0218 | 43.4462 | 0.0 | 0.8861 | 683 | 0.0 | 0.0 | 0.0 |
| random__raw | 100 | 143 | 133 | 120 | 94.8 | -146 [-168,-124] (all: -182 [-212,-152]) | 11/0/89 | -146 [-168,-124] | 0.4983 | 1.504 | 0.5041 | 0.4842 | 500 | 0.0 | 0.0 | 0.0 |

Brackets: bootstrap 95% CI of the paired mean difference. Ex-bonus = score minus bonus-ship (>=50 pt) rewards.

```
{
 "tag": "holdout",
 "exp": [
  "ufa/traces/exp008_holdout"
 ],
 "arms": {
  "control_sweep": {
   "n_games": 100,
   "performance": {
    "score_mean": 325.8,
    "score_median": 320.0,
    "score_sd": 135.0,
    "score_q10_q25_q75_q90": [
     150.0,
     213.8,
     418.8,
     520.0
    ],
    "score_min": 55.0,
    "score_max": 660.0,
    "score_ex_bonus_mean": 279.8,
    "score_ex_bonus_median": 297.5,
    "bonus_pts_per_game": 46.0,
    "games_with_bonus": 23,
    "steps_per_game": 683.0,
    "steps_per_life": 251.1,
    "points_per_100_steps": 46.7125,
    "kills_per_100_steps": 2.9177,
    "top_row_kills_per_game": 1.4
   },
   "behavior": {
    "reversal_rate": 0.0218,
    "run_length": 43.4462,
    "move_rate": 1.0,
    "fire_occupancy": 0.2629,
    "fire_while_shot_active": 0.0,
    "fire_immediately_when_ready": 1.0,
    "left_wall_share": 0.0855,
    "right_wall_share": 0.0393,
    "lane_threat_evasion_rate": 0.6299,
    "projected_threat_share": 0.095,
    "projected_threat_safe_pick_rate": 0.8861,
    "deaths_by_region": {
     "middle": 260,
     "left_wall": 8,
     "right_wall": 4
    }
   },
   "system": {
    "model_calls_per_game": 0.0,
    "calls_per_step": 0.0,
    "latency_p50_ms_median_of_games": 0.0,
    "latency_p95_ms_median_of_games": 0.0,
    "input_chars_per_decision": 206.276,
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
   }
  },
  "jev_final": {
   "n_games": 100,
   "performance": {
    "score_mean": 709.0,
    "score_median": 620.0,
    "score_sd": 254.2,
    "score_q10_q25_q75_q90": [
     450.0,
     556.2,
     805.0,
     1054.0
    ],
    "score_min": 330.0,
    "score_max": 1810.0,
    "score_ex_bonus_mean": 565.0,
    "score_ex_bonus_median": 545.0,
    "bonus_pts_per_game": 144.0,
    "games_with_bonus": 54,
    "steps_per_game": 1412.88,
    "steps_per_life": 872.1,
    "points_per_100_steps": 50.4257,
    "kills_per_100_steps": 2.3958,
    "top_row_kills_per_game": 5.08
   },
   "behavior": {
    "reversal_rate": 0.2991,
    "run_length": 2.5763,
    "move_rate": 0.6894,
    "fire_occupancy": 0.1384,
    "fire_while_shot_active": 0.0,
    "fire_immediately_when_ready": 1.0,
    "left_wall_share": 0.3274,
    "right_wall_share": 0.0036,
    "lane_threat_evasion_rate": 0.5669,
    "projected_threat_share": 0.0762,
    "projected_threat_safe_pick_rate": 0.9999,
    "deaths_by_region": {
     "left_wall": 48,
     "middle": 107,
     "right_wall": 7
    }
   },
   "system": {
    "model_calls_per_game": 1412.9,
    "calls_per_step": 1.0,
    "latency_p50_ms_median_of_games": 101.2,
    "latency_p95_ms_median_of_games": 183.3,
    "input_chars_per_decision": 208.777,
    "input_tokens_per_call": 578.8,
    "cost_per_decision_usd": 2.431e-05,
    "cost_per_game_usd": 0.03435,
    "cost_total_usd": 3.4346,
    "fallbacks_total": 0,
    "errors_by_status": {
     "529": 1
    },
    "retries_total": 1,
    "mean_confidence": 0.4421,
    "served_models": [
     "jev-1.13.0"
    ]
   },
   "vs_ref": {
    "score": {
     "n": 100,
     "mean": 383.3,
     "median": 372.5,
     "sd": 292.3,
     "ci95_bootstrap": [
      327.6,
      441.9
     ],
     "effect_size_dz": 1.31,
     "jev_wins": 92,
     "ties": 0,
     "jev_losses": 8,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 100,
     "mean": 285.3,
     "median": 255.0,
     "sd": 205.0,
     "ci95_bootstrap": [
      246.9,
      325.9
     ],
     "effect_size_dz": 1.39,
     "jev_wins": 95,
     "ties": 1,
     "jev_losses": 4,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   },
   "vs_sweep": {
    "score": {
     "n": 100,
     "mean": 383.3,
     "median": 372.5,
     "sd": 292.3,
     "ci95_bootstrap": [
      327.6,
      441.9
     ],
     "effect_size_dz": 1.31,
     "jev_wins": 92,
     "ties": 0,
     "jev_losses": 8,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 100,
     "mean": 285.3,
     "median": 255.0,
     "sd": 205.0,
     "ci95_bootstrap": [
      246.9,
      325.9
     ],
     "effect_size_dz": 1.39,
     "jev_wins": 95,
     "ties": 1,
     "jev_losses": 4,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   }
  },
  "random__raw": {
   "n_games": 100,
   "performance": {
    "score_mean": 143.3,
    "score_median": 120.0,
    "score_sd": 94.8,
    "score_q10_q25_q75_q90": [
     55.0,
     80.0,
     180.0,
     288.0
    ],
    "score_min": 10.0,
    "score_max": 460.0,
    "score_ex_bonus_mean": 133.3,
    "score_ex_bonus_median": 120.0,
    "bonus_pts_per_game": 10.0,
    "games_with_bonus": 5,
    "steps_per_game": 500.1,
    "steps_per_life": 167.8,
    "points_per_100_steps": 26.8431,
    "kills_per_100_steps": 1.7766,
    "top_row_kills_per_game": 0.85
   },
   "behavior": {
    "reversal_rate": 0.4983,
    "run_length": 1.504,
    "move_rate": 0.666,
    "fire_occupancy": 0.5026,
    "fire_while_shot_active": 0.5041,
    "fire_immediately_when_ready": 0.499,
    "left_wall_share": 0.3664,
    "right_wall_share": 0.0,
    "lane_threat_evasion_rate": 0.4131,
    "projected_threat_share": 0.1287,
    "projected_threat_safe_pick_rate": 0.4842,
    "deaths_by_region": {
     "left_wall": 64,
     "middle": 234
    }
   },
   "system": {
    "model_calls_per_game": 0.0,
    "calls_per_step": 0.0,
    "latency_p50_ms_median_of_games": 0.0,
    "latency_p95_ms_median_of_games": 0.0,
    "input_chars_per_decision": 799.751,
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
     "n": 100,
     "mean": -182.4,
     "median": -185.0,
     "sd": 154.8,
     "ci95_bootstrap": [
      -211.9,
      -152.1
     ],
     "effect_size_dz": -1.18,
     "jev_wins": 11,
     "ties": 0,
     "jev_losses": 89,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 100,
     "mean": -146.4,
     "median": -167.5,
     "sd": 111.2,
     "ci95_bootstrap": [
      -167.9,
      -124.5
     ],
     "effect_size_dz": -1.32,
     "jev_wins": 10,
     "ties": 0,
     "jev_losses": 90,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   },
   "vs_sweep": {
    "score": {
     "n": 100,
     "mean": -182.4,
     "median": -185.0,
     "sd": 154.8,
     "ci95_bootstrap": [
      -211.9,
      -152.1
     ],
     "effect_size_dz": -1.18,
     "jev_wins": 11,
     "ties": 0,
     "jev_losses": 89,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    },
    "score_ex_bonus": {
     "n": 100,
     "mean": -146.4,
     "median": -167.5,
     "sd": 111.2,
     "ci95_bootstrap": [
      -167.9,
      -124.5
     ],
     "effect_size_dz": -1.32,
     "jev_wins": 10,
     "ties": 0,
     "jev_losses": 90,
     "sign_flip_p": 0.0,
     "sign_test_p": 0.0
    }
   }
  }
 }
}
```
