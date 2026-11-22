#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Algoritmo de Evaluación y Simulación de Progresión de ELO para PvPRivals (Season XXI).
Recreado a partir del historial real de partidas de AimReset (Gato), gianamont y oldg0d (Fuego).

Fórmula verificada empíricamente (K = 32, D = 400):
  E(R_jugador, R_rival) = 1 / (1 + 10 ^ ((R_rival - R_jugador) / 400))
  • Victoria: +max(1, floor(32 * (1 - E)))
  • Derrota:  -max(0, min(R_jugador - 1400, floor(32 * E)))

Cuanto MAYOR es el ELO del rival respecto al tuyo:
  -> Más ELO ganas al vencerle (hasta +30 ELO) y menos pierdes al caer (-1 a -5 ELO).
Cuanto MENOR es el ELO del rival respecto al tuyo:
  -> Menos ELO ganas al vencerle (+1 a +4 ELO) y más pierdes si haces quickdrop (-25 a -30 ELO).
"""

import math
from typing import Dict, Tuple, List

# Distribución empírica de rivales en cola Ranked de PvPRivals (extraída del historial de partidas)
QUEUE_DISTRIBUTION = [
    {"label": "Rival Base (~1450 ELO)", "elo": 1450, "weight": 0.45},
    {"label": "Rival Medio (~1650 ELO)", "elo": 1650, "weight": 0.35},
    {"label": "Rival Top (~1850 ELO)", "elo": 1850, "weight": 0.20},
]


def calc_match_delta(player_elo: int, opponent_elo: int) -> Tuple[int, int]:
    """
    Devuelve (elo_ganado_si_gana, elo_perdido_si_pierde) para un enfrentamiento
    entre player_elo y opponent_elo en PvPRivals.
    """
    expected = 1.0 / (1.0 + math.pow(10.0, (opponent_elo - player_elo) / 400.0))
    win_gain = max(1, int(32.0 * (1.0 - expected)))
    loss_penalty = -max(0, min(max(0, player_elo - 1400), int(32.0 * expected)))
    return win_gain, loss_penalty


def expected_gain_in_queue(player_elo: int) -> float:
    """Ganancia media ponderada por victoria en la cola real según tu ELO actual."""
    total_gain = 0.0
    for tier in QUEUE_DISTRIBUTION:
        w_gain, _ = calc_match_delta(player_elo, tier["elo"])
        total_gain += w_gain * tier["weight"]
    return total_gain


def simulate_wins_against_fixed_rival(start_elo: int, target_elo: int, rival_elo: int) -> int:
    """
    Simula partida a partida cuántas victorias reales hacen falta contra un rival de rival_elo
    teniendo en cuenta que cada vez que subes de ELO, el siguiente partido te da menos puntos.
    """
    if start_elo >= target_elo:
        return 0
    curr = start_elo
    wins = 0
    while curr < target_elo and wins < 500:
        gain, _ = calc_match_delta(curr, rival_elo)
        curr += gain
        wins += 1
    return wins


def simulate_wins_in_real_queue(start_elo: int, target_elo: int) -> Dict:
    """
    Integra paso a paso la subida desde start_elo hasta target_elo contra la distribución
    real de la cola (donde a mayor ELO propio, menor ganancia por victoria).
    """
    if start_elo >= target_elo:
        return {
            "wins_mixed_queue": 0,
            "wins_vs_1450": 0,
            "wins_vs_1650": 0,
            "wins_vs_1850": 0,
            "avg_gain_start": round(expected_gain_in_queue(start_elo), 1),
            "avg_gain_end": round(expected_gain_in_queue(target_elo), 1),
        }

    curr = float(start_elo)
    wins_mixed = 0
    while curr < target_elo and wins_mixed < 500:
        step = expected_gain_in_queue(int(round(curr)))
        curr += max(1.0, step)
        wins_mixed += 1

    return {
        "wins_mixed_queue": wins_mixed,
        "wins_vs_1450": simulate_wins_against_fixed_rival(start_elo, target_elo, 1450),
        "wins_vs_1650": simulate_wins_against_fixed_rival(start_elo, target_elo, 1650),
        "wins_vs_1850": simulate_wins_against_fixed_rival(start_elo, target_elo, 1850),
        "avg_gain_start": round(expected_gain_in_queue(start_elo), 1),
        "avg_gain_end": round(expected_gain_in_queue(target_elo), 1),
    }


def simulate_direct_snipe_vs_gato(player_elo: int, gato_elo: int) -> Dict:
    """
    Simula enfrentamientos directos (Queue Snipe) contra Gato:
    Cada victoria tuya te suma +X ELO y le resta -X ELO a Gato (doble impacto).
    """
    if player_elo > gato_elo:
        return {"snipe_wins_needed": 0, "first_match_gain": 0, "first_match_swing": 0}

    p_curr = player_elo
    g_curr = gato_elo
    first_gain, _ = calc_match_delta(p_curr, g_curr)
    wins = 0
    while p_curr <= g_curr and wins < 50:
        gain, _ = calc_match_delta(p_curr, g_curr)
        p_curr += gain
        g_curr -= gain
        wins += 1

    return {
        "snipe_wins_needed": wins,
        "first_match_gain": first_gain,
        "first_match_swing": first_gain * 2,
        "final_player_elo": p_curr,
        "final_gato_elo": g_curr
    }


def evaluate_player_mode(player_elo: int, gato_elo: int) -> Dict:
    """
    Genera la evaluación completa de un jugador respecto a Gato en un modo específico:
    - Tabla de ganancia/pérdida según ELO del rival (1450, 1650, 1850 y vs Gato)
    - Simulación real paso a paso de victorias necesarias
    """
    target_elo = gato_elo + 1
    gap = max(0, target_elo - player_elo)

    d_1450 = calc_match_delta(player_elo, 1450)
    d_1650 = calc_match_delta(player_elo, 1650)
    d_1850 = calc_match_delta(player_elo, 1850)
    d_gato = calc_match_delta(player_elo, gato_elo)

    sim = simulate_wins_in_real_queue(player_elo, target_elo)
    snipe = simulate_direct_snipe_vs_gato(player_elo, gato_elo)

    return {
        "player_elo": player_elo,
        "gato_elo": gato_elo,
        "target_elo": target_elo,
        "gap": gap,
        "deltas_by_rival": {
            "1450": {"win": f"+{d_1450[0]}", "loss": f"{d_1450[1]}"},
            "1650": {"win": f"+{d_1650[0]}", "loss": f"{d_1650[1]}"},
            "1850": {"win": f"+{d_1850[0]}", "loss": f"{d_1850[1]}"},
            "gato": {"win": f"+{d_gato[0]}", "loss": f"{d_gato[1]}"},
        },
        "simulation": sim,
        "snipe": snipe,
    }


if __name__ == "__main__":
    print("=== PRUEBA DE PRECISIÓN DEL ALGORITMO CON PARTIDAS REALES ===")
    sample_matches = [
        ("AimReset vs LUJKY_321 (Derrota)", 1874, 1402, False, -30),
        ("AimReset vs WIZAHHH (Derrota)", 2009, 1825, False, -23),
        ("AimReset vs xBeastPlayzZz (Derrota)", 1991, 1970, False, -16),
        ("AimReset vs Azerdium (Derrota)", 1868, 1933, False, -13),
        ("AimReset vs chair_destroyer (Victoria)", 2023, 1741, True, +5),
        ("AimReset vs WIZAHHH (Victoria)", 2011, 1855, True, +9),
        ("AimReset vs eLpEsCaDoR17cm (Victoria)", 2031, 1547, True, +1),
    ]
    for label, p_elo, o_elo, won, real_delta in sample_matches:
        w, l = calc_match_delta(p_elo, o_elo)
        pred = w if won else l
        print(f"  {label}: ELO {p_elo} vs {o_elo} -> Real: {real_delta:+d} | Algoritmo: {pred:+d}")
