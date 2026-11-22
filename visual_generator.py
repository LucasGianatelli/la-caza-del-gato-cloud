#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador Visual Simplificado para los 3 Canales de LA CAZA DEL GATO:
1. 🌍│global     -> global_dashboard.png
2. ⚔️│final-uhc  -> final_uhc_dashboard.png
3. ⛏️│cave-uhc   -> cave_uhc_dashboard.png + defeats_full_table.png

Usa el Algoritmo de Evaluación Elo real de PvPRivals (K=32, D=400) de elo_evaluator.py,
mostrando cuánto ELO se gana/pierde según el ELO del rival y cuántas victorias reales faltan.
"""

import os
import math
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

from elo_evaluator import (
    calc_match_delta,
    evaluate_player_mode,
    simulate_wins_against_fixed_rival,
)

CET = timezone(timedelta(hours=1))


def get_font(size: int, bold: bool = False):
    candidates = (
        [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        ]
        if bold else
        [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
        ]
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_rounded_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill=None, outline=None, width: int = 1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_progress_bar(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, pct: float, bar_color, bg_color=(26, 30, 46), border_color=(60, 72, 105)):
    pct_clamped = max(0.0, min(1.0, pct))
    draw_rounded_rect(draw, (x, y, x + w, y + h), radius=h // 2, fill=bg_color, outline=border_color, width=2)
    fill_w = int(w * pct_clamped)
    if fill_w > h:
        draw_rounded_rect(draw, (x, y, x + fill_w, y + h), radius=h // 2, fill=bar_color)
    elif fill_w > 0:
        draw_rounded_rect(draw, (x, y, x + h, y + h), radius=h // 2, fill=bar_color)


def _paste_banner(img: Image.Image, banner_filename: str, W: int, banner_h: int = 260):
    banner_path = os.path.join(ASSETS_DIR, banner_filename)
    if os.path.exists(banner_path):
        try:
            b_img = Image.open(banner_path).convert("RGBA")
            b_img = b_img.resize((W, banner_h), Image.Resampling.LANCZOS)
            mask = Image.new("L", (W, banner_h), 255)
            m_draw = ImageDraw.Draw(mask)
            for py in range(80, banner_h):
                alpha = int(255 * (1.0 - (py - 80) / float(banner_h - 80)))
                m_draw.line([(0, py), (W, py)], fill=max(18, alpha))
            img.paste(b_img, (0, 0), mask)
        except Exception:
            pass


def generate_global_dashboard(db: dict) -> str:
    """
    CANAL 1: #🌍│global
    Muestra:
    - Estado Online/Offline de Gato (AimReset)
    - Marcador ELO Global: Fuego (1542) vs Gato (1513) vs gianamont (1482)
    - Evaluación por ELO del rival para subir los puntos restantes de ELO Global
    - Comparativa limpia de los 7 modos que forman el ELO Global
    """
    out_path = os.path.join(ASSETS_DIR, "global_dashboard.png")
    W, H = 1360, 880
    img = Image.new("RGBA", (W, H), (12, 14, 24, 255))
    _paste_banner(img, "ai_banner_caza.jpg", W, 270)
    draw = ImageDraw.Draw(img)

    f_h1 = get_font(32, bold=True)
    f_h2 = get_font(23, bold=True)
    f_big = get_font(44, bold=True)
    f_b = get_font(18, bold=True)
    f_r = get_font(17, bold=False)
    f_s = get_font(15, bold=False)

    gato = db["players"]["gato"]
    fuego = db["players"]["fuego"]
    gian = db["players"]["gian"]

    gato_on = gato.get("online", False)
    now_str = datetime.now(CET).strftime("%d/%m/%Y %H:%M CET")

    # Header
    draw_rounded_rect(draw, (28, 18, W - 28, 96), radius=14, fill=(10, 13, 22, 225), outline=(241, 196, 15), width=2)
    draw.text((48, 26), "CANAL 1: ELO GLOBAL & RADAR DE GATO EN VIVO", font=f_h1, fill=(255, 255, 255))
    draw.text((48, 65), f"Fórmula Global: Promedio de los 7 modos clásicos (+7 ELO en modos = +1 ELO Global)  •  {now_str}", font=f_s, fill=(200, 215, 240))

    badge_col = (46, 204, 113) if gato_on else (231, 76, 60)
    badge_txt = "● GATO ONLINE" if gato_on else "● GATO OFFLINE"
    draw_rounded_rect(draw, (W - 265, 32, W - 45, 82), radius=10, fill=badge_col)
    draw.text((W - 235, 45), badge_txt, font=f_b, fill=(255, 255, 255))

    # 3 Tarjetas Superiores: Fuego, Gato, gianamont (y = 115..295)
    target_g = gato["global"]["elo"] + 1
    gian_gap_g = max(0, target_g - gian["global"]["elo"])
    gian_gap_modes = gian_gap_g * 7

    cards = [
        ("FUEGO (oldg0d)", fuego["global"]["elo"], f"#1 España  •  #{fuego['global']['ranking']} Mundial", f"SUPERADO (+{fuego['global']['elo'] - gato['global']['elo']} vs Gato)", (46, 204, 113), 28),
        ("GATO (AimReset)", gato["global"]["elo"], f"#2 España  •  #{gato['global']['ranking']} Mundial", f"OBJETIVO A SUPERAR ({target_g}+)", (235, 65, 75), 472),
        ("GIANAMONT", gian["global"]["elo"], f"#6 España  •  #{gian['global']['ranking']} Mundial", f"Faltan +{gian_gap_g} Global (+{gian_gap_modes} ELO en modos)", (0, 210, 255), 916),
    ]
    for name, elo_val, rank_str, status_str, col, cx in cards:
        draw_rounded_rect(draw, (cx, 115, cx + 416, 290), radius=16, fill=(18, 22, 36, 245), outline=col, width=3)
        draw.text((cx + 22, 130), name, font=f_h2, fill=(255, 255, 255))
        draw.text((cx + 22, 162), f"{elo_val}", font=f_big, fill=col)
        draw.text((cx + 155, 178), rank_str, font=f_r, fill=(190, 205, 230))
        pct = min(1.0, max(0.0, (elo_val - 1400) / max(1, target_g - 1400)))
        draw_progress_bar(draw, cx + 22, 226, 372, 18, pct, bar_color=col)
        draw.text((cx + 22, 254), status_str, font=f_s, fill=col)

    # Panel Izquierdo (y = 315..855): Comparativa de los 7 Modos del ELO Global
    draw_rounded_rect(draw, (28, 315, 680, 855), radius=16, fill=(18, 22, 36, 245), outline=(70, 85, 125), width=2)
    draw.text((48, 332), "DESGLOSE DE LOS 7 MODOS DEL ELO GLOBAL", font=f_h2, fill=(241, 196, 15))
    draw.text((48, 364), "Cada +7 ELO sumados en cualquiera de estos modos = +1 ELO Global", font=f_s, fill=(175, 190, 215))

    global_kits = ["CAVEUHC", "FINALUHC", "UHC", "DIGGER", "SG", "NODEBUFF", "BOW"]
    headers_l = ["MODO", "GATO", "FUEGO", "GIANAMONT", "ESTADO vs GATO"]
    hx_l = [48, 215, 310, 410, 535]
    draw_rounded_rect(draw, (42, 398, 666, 434), radius=8, fill=(32, 38, 62))
    for xh, htxt in zip(hx_l, headers_l):
        draw.text((xh, 407), htxt, font=f_s, fill=(241, 196, 15))

    ry = 444
    for idx, k in enumerate(global_kits):
        g_e = gato["modes"][k]["elo"]
        f_e = fuego["modes"][k]["elo"]
        gi_e = gian["modes"][k]["elo"]
        title = gato["modes"][k]["title"]

        row_bg = (24, 29, 46) if idx % 2 == 0 else (19, 23, 38)
        draw_rounded_rect(draw, (42, ry, 666, ry + 48), radius=7, fill=row_bg)
        draw.text((hx_l[0], ry + 13), title, font=f_b, fill=(255, 255, 255))
        draw.text((hx_l[1], ry + 13), str(g_e), font=f_r, fill=(255, 110, 115))
        draw.text((hx_l[2], ry + 13), str(f_e), font=f_r, fill=(255, 165, 70))
        draw.text((hx_l[3], ry + 13), str(gi_e), font=f_b, fill=(0, 215, 255))

        diff_gi = gi_e - g_e
        st_col = (46, 204, 113) if diff_gi >= 0 else (255, 180, 60)
        st_txt = f"Gian {diff_gi:+d}" if diff_gi != 0 else "Empate (1400)"
        draw.text((hx_l[4], ry + 13), st_txt, font=f_b, fill=st_col)
        ry += 55

    # Panel Derecho (y = 315..855): Algoritmo Real de Subida Global para gianamont
    draw_rounded_rect(draw, (704, 315, W - 28, 855), radius=16, fill=(18, 22, 36, 245), outline=(0, 210, 255), width=2)
    draw.text((726, 332), "ALGORITMO DE PROGRESIÓN GLOBAL (GIANAMONT)", font=f_h2, fill=(0, 210, 255))
    draw.text((726, 364), f"Objetivo: Subir +{gian_gap_g} ELO Global (+{gian_gap_modes} ELO entre modos secundarios)", font=f_r, fill=(230, 235, 245))

    # Tabla de cuánto da cada rival según tu ELO en el modo donde juegues
    draw.text((726, 404), "1. ¿Cuánto ELO ganas por victoria según el ELO del rival?", font=f_b, fill=(241, 196, 15))
    sub_headers = ["TU MODO / ELO", "vs RIVAL 1450", "vs RIVAL 1650", "vs RIVAL 1850"]
    sh_x = [736, 945, 1085, 1210]
    draw_rounded_rect(draw, (724, 436, W - 44, 470), radius=7, fill=(32, 38, 62))
    for xh, htxt in zip(sh_x, sub_headers):
        draw.text((xh, 445), htxt, font=f_s, fill=(241, 196, 15))

    mode_tiers = [
        ("Modos en 1400 (SG/Bow/ND)", 1400),
        ("UHC / Digger (~1420 ELO)", 1420),
        ("Final UHC (1585 ELO)", gian["modes"]["FINALUHC"]["elo"]),
        ("Cave UHC (1753 ELO)", gian["modes"]["CAVEUHC"]["elo"]),
    ]
    ry2 = 478
    for idx, (m_label, m_elo) in enumerate(mode_tiers):
        row_bg = (24, 29, 46) if idx % 2 == 0 else (19, 23, 38)
        draw_rounded_rect(draw, (724, ry2, W - 44, ry2 + 44), radius=7, fill=row_bg)
        d1450 = calc_match_delta(m_elo, 1450)
        d1650 = calc_match_delta(m_elo, 1650)
        d1850 = calc_match_delta(m_elo, 1850)
        draw.text((sh_x[0], ry2 + 11), m_label, font=f_s, fill=(255, 255, 255))
        draw.text((sh_x[1], ry2 + 11), f"+{d1450[0]} / {d1450[1]}", font=f_b, fill=(130, 230, 160))
        draw.text((sh_x[2], ry2 + 11), f"+{d1650[0]} / {d1650[1]}", font=f_b, fill=(0, 215, 255))
        draw.text((sh_x[3], ry2 + 11), f"+{d1850[0]} / {d1850[1]}", font=f_b, fill=(255, 200, 70))
        ry2 += 50

    # Conclusión de Progresión Real para los +224 ELO de modos
    draw.text((726, 690), f"2. Victorias Reales para alcanzar a Gato (+{gian_gap_modes} ELO de modos):", font=f_b, fill=(241, 196, 15))
    # Si se reparten los +224 ELO en 4 modos de 1400 (+56 ELO en cada uno: 1400 -> 1456):
    per_mode_target = 1400 + math.ceil(gian_gap_modes / 4.0)
    w_low = simulate_wins_against_fixed_rival(1400, per_mode_target, 1450) * 4
    w_mid = simulate_wins_against_fixed_rival(1400, per_mode_target, 1650) * 4
    w_high = simulate_wins_against_fixed_rival(1400, per_mode_target, 1850) * 4

    summary_lines = [
        f"• Jugando en tus modos de 1400 ELO (UHC, SG, Digger, Bow, NoDebuff):",
        f"   - Contra rivales de ~1450 ELO: {w_low} victorias totales (~{math.ceil(w_low/7)} wins/día en 7 días)",
        f"   - Contra rivales de ~1650 ELO: {w_mid} victorias totales (~{math.ceil(w_mid/7)} wins/día en 7 días)",
        f"   - Contra rivales de ~1850 ELO: {w_high} victorias totales (~{math.ceil(w_high/7)} wins/día en 7 días)",
    ]
    sy = 724
    for line in summary_lines:
        draw.text((726, sy), line, font=f_r, fill=(220, 230, 245))
        sy += 30

    img.convert("RGB").save(out_path, "PNG", optimize=True)
    return out_path


def generate_single_mode_dashboard(db: dict, mode_key: str, channel_num: int, out_filename: str, accent_main: tuple) -> str:
    """
    Genera el panel visual simplificado y exacto para:
    - CANAL 2: FINAL UHC (mode_key="FINALUHC")
    - CANAL 3: CAVE UHC (mode_key="CAVEUHC")
    """
    out_path = os.path.join(ASSETS_DIR, out_filename)
    W, H = 1360, 880
    img = Image.new("RGBA", (W, H), (12, 14, 24, 255))
    banner_file = "ai_banner_podium.jpg" if mode_key == "FINALUHC" else "ai_banner_caza.jpg"
    _paste_banner(img, banner_file, W, 260)
    draw = ImageDraw.Draw(img)

    f_h1 = get_font(32, bold=True)
    f_h2 = get_font(22, bold=True)
    f_big = get_font(44, bold=True)
    f_b = get_font(18, bold=True)
    f_r = get_font(17, bold=False)
    f_s = get_font(15, bold=False)

    gato = db["players"]["gato"]
    fuego = db["players"]["fuego"]
    gian = db["players"]["gian"]

    m_title = gato["modes"][mode_key]["title"].upper()
    g_m = gato["modes"][mode_key]
    f_m = fuego["modes"][mode_key]
    gi_m = gian["modes"][mode_key]

    g_elo = g_m["elo"]
    f_elo = f_m["elo"]
    gi_elo = gi_m["elo"]
    target_elo = g_elo + 1

    now_str = datetime.now(CET).strftime("%d/%m/%Y %H:%M CET")

    # Header
    draw_rounded_rect(draw, (28, 18, W - 28, 96), radius=14, fill=(10, 13, 22, 225), outline=accent_main, width=2)
    draw.text((48, 26), f"CANAL {channel_num}: {m_title} — SEGUIMIENTO Y ALGORITMO DE ELO", font=f_h1, fill=(255, 255, 255))
    sub_desc = (
        f"Mejor Modo de Gato ({g_elo} ELO) • Al menos uno debe superarle ({target_elo}+ ELO) • {now_str}"
        if mode_key == "CAVEUHC" else
        f"Comparativa en {m_title} y ganancia de ELO según nivel del rival (K=32, D=400) • {now_str}"
    )
    draw.text((48, 65), sub_desc, font=f_s, fill=(200, 215, 240))

    # 3 Tarjetas de Jugadores en este Modo (y = 115..295)
    def _card_status(p_elo):
        if p_elo > g_elo:
            return f"SUPERADO (+{p_elo - g_elo} ELO sobre Gato)", (46, 204, 113)
        return f"Faltan +{target_elo - p_elo} ELO para superar a Gato", (255, 165, 50)

    f_st_txt, f_st_col = _card_status(f_elo)
    gi_st_txt, gi_st_col = _card_status(gi_elo)

    cards = [
        ("FUEGO (oldg0d)", f_m, f_st_txt, (255, 140, 40), 28),
        ("GATO (AimReset)", g_m, f"REFERENCIA OBJETIVO: {g_elo} ELO", (235, 65, 75), 472),
        ("GIANAMONT", gi_m, gi_st_txt, (0, 210, 255), 916),
    ]

    max_bar_elo = max(g_elo, f_elo, gi_elo, 1750)
    for name, m_obj, st_txt, col, cx in cards:
        elo_v = m_obj["elo"]
        matches_v = m_obj["matches"]
        wins_v = m_obj["wins"]
        losses_v = max(0, matches_v - wins_v)
        wr_v = round((wins_v / matches_v) * 100, 1) if matches_v > 0 else 0.0

        draw_rounded_rect(draw, (cx, 115, cx + 416, 295), radius=16, fill=(18, 22, 36, 245), outline=col, width=3)
        draw.text((cx + 22, 128), name, font=f_h2, fill=(255, 255, 255))
        draw.text((cx + 22, 160), f"{elo_v}", font=f_big, fill=col)
        draw.text((cx + 155, 168), f"Rank #{m_obj['ranking']}  •  Peak {m_obj['peak']}", font=f_r, fill=(200, 210, 235))
        draw.text((cx + 155, 194), f"{wins_v}W - {losses_v}L ({wr_v}% WR)", font=f_s, fill=(165, 180, 205))

        pct = min(1.0, max(0.0, (elo_v - 1400) / max(1, (max_bar_elo - 1400))))
        draw_progress_bar(draw, cx + 22, 232, 372, 18, pct, bar_color=col)
        draw.text((cx + 22, 258), st_txt, font=f_s, fill=col)

    # Evaluación matemática para Fuego y gianamont
    # Si ya supera a Gato (ej. en Final UHC), evaluamos hacia un objetivo competitivo (+150 ELO para sumar +21 ELO Global)
    f_target = target_elo if f_elo <= g_elo else ((f_elo + 120) // 50) * 50
    gi_target = target_elo if gi_elo <= g_elo else ((gi_elo + 165) // 50) * 50

    f_eval = evaluate_player_mode(f_elo, f_target - 1)
    gi_eval = evaluate_player_mode(gi_elo, gi_target - 1)

    # Paneles Inferiores (Fuego a la izquierda, gianamont a la derecha)
    panels = [
        ("FUEGO (oldg0d)", f_elo, f_target, f_elo > g_elo, f_eval, (255, 140, 40), 28, 668),
        ("GIANAMONT", gi_elo, gi_target, gi_elo > g_elo, gi_eval, (0, 210, 255), 692, W - 28),
    ]

    for p_title, p_elo, p_target, beat_gato, ev, col, x1, x2 in panels:
        draw_rounded_rect(draw, (x1, 315, x2, 855), radius=16, fill=(18, 22, 36, 245), outline=col, width=2)
        draw.text((x1 + 22, 330), f"EVALUACIÓN Y PROGRESIÓN: {p_title}", font=f_h2, fill=col)

        gap_to_target = max(0, p_target - p_elo)
        if beat_gato:
            goal_str = f"¡Ya supera a Gato ({g_elo})!  •  Meta Push Global: {p_target} ELO (+{gap_to_target} ELO)"
        else:
            goal_str = f"Meta: Superar a Gato ({target_elo} ELO)  •  Faltan +{gap_to_target} ELO"
        draw.text((x1 + 22, 364), goal_str, font=f_r, fill=(235, 240, 250))

        # 1. Tabla de Ganancia/Pérdida por ELO del Rival
        draw.text((x1 + 22, 404), f"1. ELO que gana/pierde {p_title} ({p_elo}) según el rival:", font=f_b, fill=(241, 196, 15))
        th = ["NIVEL DEL RIVAL", "SI GANAS", "SI PIERDES", "WINS HASTA META"]
        tx = [x1 + 26, x1 + 235, x1 + 338, x1 + 448]
        draw_rounded_rect(draw, (x1 + 20, 436, x2 - 20, 470), radius=7, fill=(32, 38, 62))
        for cx_t, h_t in zip(tx, th):
            draw.text((cx_t, 445), h_t, font=f_s, fill=(241, 196, 15))

        d_gato_now = calc_match_delta(p_elo, g_elo)
        snipe_info = evaluate_player_mode(p_elo, g_elo)["snipe"]

        rival_rows = [
            ("Rival Base (~1450 ELO)", ev["deltas_by_rival"]["1450"]["win"], ev["deltas_by_rival"]["1450"]["loss"], f"{ev['simulation']['wins_vs_1450']} wins"),
            ("Rival Medio (~1650 ELO)", ev["deltas_by_rival"]["1650"]["win"], ev["deltas_by_rival"]["1650"]["loss"], f"{ev['simulation']['wins_vs_1650']} wins"),
            ("Rival Top (~1850 ELO)", ev["deltas_by_rival"]["1850"]["win"], ev["deltas_by_rival"]["1850"]["loss"], f"{ev['simulation']['wins_vs_1850']} wins"),
            (f"Directo vs Gato ({g_elo} ELO)", f"+{d_gato_now[0]}", f"{d_gato_now[1]}", f"{snipe_info['snipe_wins_needed']} wins (Snipe x2)" if not beat_gato else "Ya superado"),
        ]

        ry = 478
        for idx, (r_lbl, w_str, l_str, wins_str) in enumerate(rival_rows):
            r_bg = (24, 29, 46) if idx % 2 == 0 else (19, 23, 38)
            draw_rounded_rect(draw, (x1 + 20, ry, x2 - 20, ry + 44), radius=7, fill=r_bg)
            draw.text((tx[0], ry + 11), r_lbl, font=f_s, fill=(255, 255, 255))
            draw.text((tx[1], ry + 11), f"{w_str} ELO", font=f_b, fill=(46, 204, 113))
            draw.text((tx[2], ry + 11), f"{l_str} ELO", font=f_b, fill=(255, 95, 95))
            draw.text((tx[3], ry + 11), wins_str, font=f_b, fill=col)
            ry += 50

        # 2. Plan Diario Real Integrado
        draw.text((x1 + 22, 688), "2. Progresión Diaria Real (integrando caída de ganancia al subir):", font=f_b, fill=(241, 196, 15))
        w_mixed = ev["simulation"]["wins_mixed_queue"]
        w_1650 = ev["simulation"]["wins_vs_1650"]
        w_1850 = ev["simulation"]["wins_vs_1850"]

        p_lines = [
            f"• Ganancia media actual en cola: +{ev['simulation']['avg_gain_start']} ELO/win (baja a +{ev['simulation']['avg_gain_end']} cerca de {p_target})",
            f"• Plan 7 Días: +{math.ceil(gap_to_target/7)} ELO/día  ->  ~{math.ceil(w_1650/7)} wins/día (vs 1650)  ó  ~{math.ceil(w_1850/7)} wins/día (vs 1850+)",
            f"• Plan 14 Días: +{math.ceil(gap_to_target/14)} ELO/día ->  ~{math.ceil(w_1650/14)} wins/día (vs 1650)  ó  ~{math.ceil(w_1850/14)} wins/día (vs 1850+)",
        ]
        if not beat_gato:
            p_lines.append(
                f"• Queue Snipe vs Gato ({g_elo}): le quitas -{d_gato_now[0]} y sumas +{d_gato_now[0]} (recortas {d_gato_now[0]*2} ELO/partida)!"
            )
        else:
            p_lines.append(
                f"• Cada +7 ELO adicionales aquí te suman +1 ELO Global directo."
            )

        py = 720
        for pl in p_lines:
            draw.text((x1 + 22, py), pl, font=f_s, fill=(220, 230, 245))
            py += 30

    img.convert("RGB").save(out_path, "PNG", optimize=True)
    return out_path


def generate_defeats_table_image(db: dict) -> str:
    """
    Genera defeats_full_table.png (1400x980) para #⛏️│cave-uhc:
    Tabla visual con las 15 derrotas de Gato (Quickdrop vs Heal, rival, ELO perdido y fecha exacta).
    """
    out_path = os.path.join(ASSETS_DIR, "defeats_full_table.png")
    defeats = db.get("gato_defeats", [])[:15]
    W, H = 1400, 980
    img = Image.new("RGB", (W, H), (12, 14, 24))
    draw = ImageDraw.Draw(img)

    f_title = get_font(27, bold=True)
    f_sub = get_font(16, bold=False)
    f_head = get_font(14, bold=True)
    f_row_b = get_font(14, bold=True)
    f_row = get_font(14, bold=False)

    draw_rounded_rect(draw, (25, 18, W - 25, 92), radius=14, fill=(22, 26, 42), outline=(235, 65, 75), width=2)
    draw.text((45, 26), "HISTORIAL DE DERROTAS DE GATO (AimReset) — QUICKDROP vs HEAL Y VERDUGOS", font=f_title, fill=(255, 255, 255))
    draw.text((45, 63), "67% Derrotas por Quickdrop (muere con 6–12 manzanas por sus ~6.3 CPS) • Top Verdugos: Azerdium (3W), chair_destroyer (2W), Ticketer (2W)", font=f_sub, fill=(255, 165, 175))

    headers = ["#", "FECHA EXACTA (CET)", "RIVAL (VERDUGO)", "MODO / MAPA", "ELO", "DIAGNÓSTICO", "CURAS DE GATO vs RIVAL (VIDA FINAL)"]
    col_x = [38, 80, 260, 425, 655, 745, 945]

    draw_rounded_rect(draw, (25, 105, W - 25, 145), radius=8, fill=(35, 42, 68))
    for cx, h_txt in zip(col_x, headers):
        draw.text((cx, 116), h_txt, font=f_head, fill=(241, 196, 15))

    ry = 154
    for idx, d in enumerate(defeats, 1):
        row_bg = (22, 26, 40) if idx % 2 == 1 else (17, 20, 32)
        is_qd = d.get("is_quickdrop", False)
        accent = (255, 75, 95) if is_qd else (70, 180, 255)
        draw_rounded_rect(draw, (25, ry, W - 25, ry + 48), radius=7, fill=row_bg, outline=(40, 48, 72), width=1)

        dt_str = datetime.fromtimestamp(d["date"], tz=CET).strftime("%d/%m/%Y %H:%M:%S")
        elo_chg = d["gato_elo_change"]
        elo_txt = f"{elo_chg} ELO" if elo_chg != 0 else "0 (1400)"
        diag_txt = "QUICKDROP" if is_qd else "POR HEAL / DRAIN"
        opp_hearts = round(d["opponent_health_hp"] / 2.0, 1)
        g_heals = d["gato_heals_left"].replace("Golden Head", "Head")
        o_heals = d["opponent_heals_left"].replace("Golden Head", "Head")
        heals_txt = f"Gato: {g_heals} | Rival: {o_heals} ({opp_hearts} Cor.)"

        draw.text((col_x[0], ry + 15), f"#{idx:02d}", font=f_row_b, fill=(170, 180, 205))
        draw.text((col_x[1], ry + 15), dt_str, font=f_row, fill=(230, 235, 245))
        draw.text((col_x[2], ry + 15), d["opponent"], font=f_row_b, fill=(255, 255, 255))
        draw.text((col_x[3], ry + 15), f"{d['kit']} ({d['map']} • {d['duration']}s)", font=f_row, fill=(200, 210, 230))
        draw.text((col_x[4], ry + 15), elo_txt, font=f_row_b, fill=(255, 90, 90))

        pill_bg = (90, 22, 35) if is_qd else (20, 60, 95)
        draw_rounded_rect(draw, (col_x[5], ry + 9, col_x[5] + 185, ry + 39), radius=6, fill=pill_bg, outline=accent, width=1)
        draw.text((col_x[5] + 12, ry + 15), f"{diag_txt}", font=f_row_b, fill=accent)

        draw.text((col_x[6], ry + 15), heals_txt, font=f_row, fill=(225, 230, 240))
        ry += 54

    img.save(out_path, "PNG", optimize=True)
    return out_path


def generate_all_visuals(db: dict) -> dict:
    return {
        "global_dashboard": generate_global_dashboard(db),
        "final_uhc_dashboard": generate_single_mode_dashboard(db, "FINALUHC", 2, "final_uhc_dashboard.png", (0, 210, 255)),
        "cave_uhc_dashboard": generate_single_mode_dashboard(db, "CAVEUHC", 3, "cave_uhc_dashboard.png", (235, 65, 75)),
        "defeats_table": generate_defeats_table_image(db),
    }


if __name__ == "__main__":
    import json
    with open(os.path.join(BASE_DIR, "gato_database.json"), "r", encoding="utf-8") as f:
        db_data = json.load(f)
    paths = generate_all_visuals(db_data)
    print("Generated 3-channel visuals:", paths)
