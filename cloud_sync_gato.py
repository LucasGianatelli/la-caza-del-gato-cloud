#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLOUD SYNC ENGINE — LA CAZA DEL GATO (100% Serverless / Sin dependencia de PC)
Se ejecuta en la nube (GitHub Actions 24/7) sin necesidad de tener el ordenador encendido.
Consulta PvPRivals en tiempo real, regenera las infografías PNG con el Algoritmo de Evaluación Elo
y actualiza los 3 canales de Discord (🌍│global, ⚔️│final-uhc y ⛏️│cave-uhc) + contadores de voz
mediante la API REST v10 de Discord (sin WebSockets ni procesos locales).
"""

import os
import sys
import json
import time
import uuid
import ssl
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from visual_generator import generate_all_visuals
from elo_evaluator import evaluate_player_mode

DB_PATH = os.path.join(BASE_DIR, "gato_database.json")
CHANNELS_CONFIG_PATH = os.path.join(BASE_DIR, "discord_channels.json")
DISCORD_API = "https://discord.com/api/v10"
CET = timezone(timedelta(hours=1))


def load_json(path: str, default: dict) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Error leyendo {path}: {e}", flush=True)
    return default


def save_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fmt_dt_es(unix_ts: int) -> str:
    dt_cet = datetime.fromtimestamp(unix_ts, tz=CET)
    dt_utc = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    return f"{dt_cet.strftime('%d/%m/%Y %H:%M:%S')} CET ({dt_utc.strftime('%H:%M')} UTC)"


def fmt_duration(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s" if m > 0 else f"{s}s"


def unflatten_sveltekit(arr, idx=0):
    val = arr[idx]
    if val is None or not isinstance(val, (dict, list)):
        return val
    if isinstance(val, list):
        return [unflatten_sveltekit(arr, i) if isinstance(i, int) else i for i in val]
    out = {}
    for k, v in val.items():
        out[k] = unflatten_sveltekit(arr, v) if isinstance(v, int) else v
    return out


def fetch_url_json(url: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        txt = resp.read().decode("utf-8", errors="replace").strip()
        if not txt or txt.startswith("<!DOCTYPE"):
            raise ValueError(f"Respuesta no-JSON desde {url}")
        return json.loads(txt)


def fetch_player_svelte_data(username: str) -> dict:
    url = f"https://pvprivals.net/profile/{username}/__data.json"
    raw = fetch_url_json(url)
    nodes = raw.get("nodes", [])
    if len(nodes) > 1 and nodes[1] and "data" in nodes[1]:
        return unflatten_sveltekit(nodes[1]["data"], 0)
    return {}


def fetch_match_svelte_data(username: str, hex_id: str) -> dict:
    url = f"https://pvprivals.net/profile/{username}/match/{hex_id}/__data.json"
    raw = fetch_url_json(url)
    nodes = raw.get("nodes", [])
    if len(nodes) > 1 and nodes[1] and "data" in nodes[1]:
        return unflatten_sveltekit(nodes[1]["data"], 0)
    return {}


def update_player_in_db(db_player: dict, svelte_node: dict) -> dict:
    changes = {"came_online": False, "new_activity": False, "elo_changed": False, "mode_changes": []}
    if not svelte_node or not svelte_node.get("player"):
        return changes

    p_info = svelte_node["player"]
    was_online = bool(db_player.get("online", False))
    now_online = bool(p_info.get("online", False))
    old_last_played = int(db_player.get("lastPlayed", 0))
    new_last_played = int(p_info.get("lastPlayed", old_last_played))

    if not was_online and now_online:
        changes["came_online"] = True
    if new_last_played > old_last_played:
        changes["new_activity"] = True

    db_player["online"] = now_online
    db_player["lastPlayed"] = new_last_played

    stats_entries = (
        svelte_node.get("statistics", {})
        .get("stats", {})
        .get("entries", [])
    )
    if not stats_entries:
        return changes

    best_mode_entry = None
    for entry in stats_entries:
        enum_name = entry.get("enumName")
        title = entry.get("title")
        elo = int(entry.get("elo", 1400))
        peak = int(entry.get("highestElo", elo))
        ranking = int(entry.get("ranking", 0))
        matches = int(entry.get("matches", 0))
        wins = int(entry.get("wins", 0))
        losses = max(0, matches - wins)
        winstreak = int(entry.get("winstreak", 0))
        best_ws = int(entry.get("highestWinstreak", 0))
        winrate = round((wins / matches) * 100, 1) if matches > 0 else 0.0

        if enum_name == "UNKNOWN" or title == "Global":
            old_matches = db_player["global"].get("matches", matches)
            old_g_elo = db_player["global"].get("elo", elo)
            if matches > old_matches:
                changes["new_activity"] = True
            if elo != old_g_elo:
                changes["elo_changed"] = True
            db_player["global"].update({
                "elo": elo,
                "peak": peak,
                "ranking": ranking,
                "matches": matches,
                "wins": wins,
                "losses": losses,
                "winrate": winrate,
                "winstreak": winstreak,
                "bestWinstreak": best_ws,
            })
        else:
            prev_mode = db_player["modes"].get(enum_name, {})
            prev_elo = prev_mode.get("elo", elo)
            prev_matches = prev_mode.get("matches", matches)
            if matches != prev_matches or elo != prev_elo:
                changes["elo_changed"] = True
                changes["mode_changes"].append({
                    "title": title,
                    "old_elo": prev_elo,
                    "new_elo": elo,
                    "delta": elo - prev_elo,
                    "matches_delta": matches - prev_matches
                })
            db_player["modes"][enum_name] = {
                "title": title,
                "elo": elo,
                "peak": peak,
                "ranking": ranking,
                "matches": matches,
                "wins": wins
            }
            if best_mode_entry is None or elo > best_mode_entry["elo"]:
                best_mode_entry = {
                    "title": title,
                    "enumName": enum_name,
                    "elo": elo,
                    "peak": peak,
                    "ranking": ranking,
                    "es_ranking": 1 if enum_name == "CAVEUHC" else ranking,
                    "matches": matches,
                    "wins": wins,
                    "losses": losses,
                    "winrate": winrate,
                    "winstreak": winstreak,
                    "bestWinstreak": best_ws
                }

    if "best_mode" in db_player and best_mode_entry:
        db_player["best_mode"] = best_mode_entry

    return changes


def classify_defeat_from_match_details(hex_id: str, md: dict) -> dict:
    w = md["winnerTeam"][0]
    l = md["loserTeam"][0]
    kit = md.get("kit", "Cave UHC")
    duration = int(md.get("duration", 0))

    def format_heals(p_obj):
        gapples = int(p_obj.get("goldenApplesLeft", 0))
        pots = int(p_obj.get("potionsLeft", 0))
        inv = p_obj.get("inventory") or []
        heads = sum(int(it.get("amount", 1)) for it in inv if isinstance(it, dict) and it.get("goldenHead"))
        stews = sum(int(it.get("amount", 1)) for it in inv if isinstance(it, dict) and "mushroom_stew" in str(it.get("id", "")))
        if "Debuff" in kit or pots > 0:
            return f"{pots} Pots", pots
        if "HG" in kit or stews > 0:
            return f"{stews} Sopas", stews
        if heads > 0:
            return f"{gapples} Gapples + {heads} Golden Head", gapples + heads
        return f"{gapples} Gapples", gapples

    w_heals_str, _ = format_heals(w)
    l_heals_str, l_heals_cnt = format_heals(l)
    overhealed = round(float(l.get("overHealed", 0.0)), 2)

    is_quickdrop = (l_heals_cnt >= 3) or (duration <= 95 and l_heals_cnt >= 1)
    if is_quickdrop:
        loss_type = f"⚡ QUICKDROP ({fmt_duration(duration)} - Murió con {l_heals_str})"
    else:
        if l_heals_cnt == 0:
            loss_type = f"🧪 POR HEAL (Drain Total - 0 curas vs {w_heals_str})"
        else:
            loss_type = f"🧪 POR HEAL ({l_heals_str} vs {w_heals_str} + {round(overhealed/2, 1)}❤ desperdiciados)"

    return {
        "hexId": hex_id,
        "id": md.get("id", 0),
        "kit": kit,
        "map": md.get("map", "Unknown"),
        "date": int(md.get("date", 0)),
        "duration": duration,
        "opponent": w.get("playerName", "Unknown"),
        "opponent_elo_before": int(w.get("eloBeforeGame", 1400)),
        "opponent_elo_change": int(w.get("eloChange", 0)),
        "opponent_health_hp": round(float(w.get("health", 0.0)), 2),
        "opponent_heals_left": w_heals_str,
        "opponent_cps": round(float(w.get("averageCombatCps", 0.0)), 2),
        "gato_elo_before": int(l.get("eloBeforeGame", 1400)),
        "gato_elo_change": int(l.get("eloChange", 0)),
        "gato_heals_left": l_heals_str,
        "gato_overhealed_hp": overhealed,
        "gato_cps": round(float(l.get("averageCombatCps", 0.0)), 2),
        "loss_type": loss_type,
        "is_quickdrop": is_quickdrop,
        "notes": f"Partida detectada en vivo ({kit} en {md.get('map', 'Mapa')})."
    }


def build_global_embed_dict(db: dict) -> dict:
    gato = db["players"]["gato"]
    fuego = db["players"]["fuego"]
    gian = db["players"]["gian"]
    is_on = gato.get("online", False)

    target_g = gato["global"]["elo"] + 1
    gian_gap = max(0, target_g - gian["global"]["elo"])
    gian_modes_gap = gian_gap * 7

    return {
        "title": "🌍 ELO GLOBAL & RADAR DE GATO EN VIVO (24/7 CLOUD)",
        "description": (
            f"• **Estado de Gato (`AimReset`):** `{'🟢 ONLINE JUGANDO' if is_on else '🔴 OFFLINE'}` *(Últ. vez: <t:{gato['lastPlayed']}:R>)*\n"
            f"• **Marcador Global:** 🔥 **Fuego:** `{fuego['global']['elo']}` ✅ (`+{fuego['global']['elo'] - gato['global']['elo']}`) │ "
            f"🐱 **Gato:** `{gato['global']['elo']}` 🎯 │ "
            f"⚔️ **gianamont:** `{gian['global']['elo']}` *(Faltan `+{gian_gap} Global` = `+{gian_modes_gap} ELO` en modos)*\n"
            f"• **Progresión Real (`gianamont`):** Jugando modos en `1400 ELO` (*SG, Bow, NoDebuff, UHC, Digger*) ganas **`+18 a +29 ELO/win`** → necesitas **8 a 16 victorias** (`~2 wins/día`)."
        ),
        "color": 0x2ECC71 if is_on else 0xF1C40F,
        "image": {"url": "attachment://global_dashboard.png"},
        "footer": {"text": "Canal 1/3 • Cloud Bot 24/7 (Sin dependencia de PC)"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def build_final_uhc_embed_dict(db: dict) -> dict:
    gato = db["players"]["gato"]["modes"]["FINALUHC"]
    fuego = db["players"]["fuego"]["modes"]["FINALUHC"]
    gian = db["players"]["gian"]["modes"]["FINALUHC"]

    return {
        "title": "⚔️ FINAL UHC — SEGUIMIENTO Y ALGORITMO DE ELO (24/7 CLOUD)",
        "description": (
            f"• **Marcador Final UHC:** 🔥 **Fuego:** `{fuego['elo']}` (#{fuego['ranking']} 🌍, `+{fuego['elo'] - gato['elo']}` vs Gato) │ "
            f"⚔️ **gianamont:** `{gian['elo']}` (#{gian['ranking']} 🌍, `+{gian['elo'] - gato['elo']}` vs Gato) │ "
            f"🐱 **Gato:** `{gato['elo']}` (#{gato['ranking']} 🌍)\n"
            f"• **Evaluación por Rival (`K=32, D=400`):**\n"
            f"  - **gianamont (`{gian['elo']}`):** vs `1450` → **`+10 / -21`** │ vs `1650` → **`+18 / -13`** │ vs `1850` → **`+26 / -5`**\n"
            f"  - **Fuego (`{fuego['elo']}`):** vs `1450` → **`+5 / -26`** │ vs `1650` → **`+12 / -19`** │ vs `1850` → **`+21 / -10`**"
        ),
        "color": 0x00D2FF,
        "image": {"url": "attachment://final_uhc_dashboard.png"},
        "footer": {"text": "Canal 2/3 • Cloud Bot 24/7 • Cada +7 ELO en Final UHC suma +1 ELO Global"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def build_cave_uhc_embed_dict(db: dict) -> dict:
    gato = db["players"]["gato"]["modes"]["CAVEUHC"]
    fuego = db["players"]["fuego"]["modes"]["CAVEUHC"]
    gian = db["players"]["gian"]["modes"]["CAVEUHC"]

    f_ev = evaluate_player_mode(fuego["elo"], gato["elo"])
    gi_ev = evaluate_player_mode(gian["elo"], gato["elo"])

    return {
        "title": "⛏️ CAVE UHC (MEJOR MODO DE GATO) — ALGORITMO Y PROGRESIÓN REAL (24/7 CLOUD)",
        "description": (
            f"• **Marcador Cave UHC (Meta: `{gato['elo'] + 1}+`):** 🐱 **Gato:** `{gato['elo']}` (#1 🇪🇸 / #{gato['ranking']} 🌍) │ "
            f"🔥 **Fuego:** `{fuego['elo']}` *(Faltan `+{f_ev['gap']} ELO`)* │ "
            f"⚔️ **gianamont:** `{gian['elo']}` *(Faltan `+{gi_ev['gap']} ELO`)*\n"
            f"• **🔥 Fuego (`{fuego['elo']}` → `{gato['elo'] + 1}`):** "
            f"vs `1450` (`{f_ev['deltas_by_rival']['1450']['win']}/{f_ev['deltas_by_rival']['1450']['loss']}`, **{f_ev['simulation']['wins_vs_1450']}W**) │ "
            f"vs `1650` (`{f_ev['deltas_by_rival']['1650']['win']}/{f_ev['deltas_by_rival']['1650']['loss']}`, **{f_ev['simulation']['wins_vs_1650']}W**) │ "
            f"vs `1850` (`{f_ev['deltas_by_rival']['1850']['win']}/{f_ev['deltas_by_rival']['1850']['loss']}`, **{f_ev['simulation']['wins_vs_1850']}W**) │ "
            f"🎯 **vs Gato:** `{f_ev['deltas_by_rival']['gato']['win']}/{f_ev['deltas_by_rival']['gato']['loss']}` (**{f_ev['snipe']['snipe_wins_needed']}W directas**)\n"
            f"• **⚔️ gianamont (`{gian['elo']}` → `{gato['elo'] + 1}`):** "
            f"vs `1450` (`{gi_ev['deltas_by_rival']['1450']['win']}/{gi_ev['deltas_by_rival']['1450']['loss']}`, **{gi_ev['simulation']['wins_vs_1450']}W**) │ "
            f"vs `1650` (`{gi_ev['deltas_by_rival']['1650']['win']}/{gi_ev['deltas_by_rival']['1650']['loss']}`, **{gi_ev['simulation']['wins_vs_1650']}W**) │ "
            f"vs `1850` (`{gi_ev['deltas_by_rival']['1850']['win']}/{gi_ev['deltas_by_rival']['1850']['loss']}`, **{gi_ev['simulation']['wins_vs_1850']}W**) │ "
            f"🎯 **vs Gato:** `{gi_ev['deltas_by_rival']['gato']['win']}/{gi_ev['deltas_by_rival']['gato']['loss']}` (**{gi_ev['snipe']['snipe_wins_needed']}W directas**)"
        ),
        "color": 0xEB414B,
        "image": {"url": "attachment://cave_uhc_dashboard.png"},
        "footer": {"text": "Canal 3/3 • Cloud Bot 24/7 • Progresión integrada paso a paso"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def discord_json_request(method: str, endpoint: str, payload: dict, token: str):
    url = f"{DISCORD_API}{endpoint}"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
        "User-Agent": "DiscordBot (LaCazaDelGatoCloud, 4.0)"
    }
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        if e.code == 429:
            try:
                wait_s = float(json.loads(e.read().decode("utf-8")).get("retry_after", 1.5))
            except Exception:
                wait_s = 2.0
            time.sleep(wait_s)
        else:
            print(f"[Discord HTTP {e.code}] {method} {endpoint}: {e.read().decode('utf-8', errors='ignore')}", flush=True)
    except Exception as e:
        print(f"[Discord Error] {method} {endpoint}: {e}", flush=True)
    return None


def discord_multipart_patch_message(channel_id: int, message_id: int, embed_dict: dict, file_path: str, filename: str, token: str):
    boundary = f"----LaCazaDelGatoBoundary{uuid.uuid4().hex}"
    url = f"{DISCORD_API}/channels/{channel_id}/messages/{message_id}"

    payload_json = json.dumps({
        "embeds": [embed_dict],
        "attachments": [{"id": 0, "filename": filename}]
    }).encode("utf-8")

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    parts = []
    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(b'Content-Disposition: form-data; name="payload_json"\r\n')
    parts.append(b"Content-Type: application/json\r\n\r\n")
    parts.append(payload_json + b"\r\n")

    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(f'Content-Disposition: form-data; name="files[0]"; filename="{filename}"\r\n'.encode("utf-8"))
    parts.append(b"Content-Type: image/png\r\n\r\n")
    parts.append(file_bytes + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(parts)
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "User-Agent": "DiscordBot (LaCazaDelGatoCloud, 4.0)"
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[!] Error actualizando imagen {filename} en canal {channel_id}: {e}", flush=True)
        return None


def run_sync_cycle(token: str, force_update: bool = False) -> bool:
    db = load_json(DB_PATH, {})
    cfg = load_json(CHANNELS_CONFIG_PATH, {})
    if not db or not cfg:
        print("[!] Base de datos o configuración no encontrada.", flush=True)
        return False

    fetched_any = False
    changes_by_player = {}
    for key, uname in [("gato", "AimReset"), ("fuego", "oldg0d"), ("gian", "gianamont")]:
        try:
            s_data = fetch_player_svelte_data(uname)
            if s_data and s_data.get("player"):
                changes_by_player[key] = update_player_in_db(db["players"][key], s_data)
                fetched_any = True
            else:
                changes_by_player[key] = {"came_online": False, "new_activity": False, "elo_changed": False, "mode_changes": []}
        except Exception as e:
            print(f"[!] Aviso consultando PvPRivals ({uname}): {e}", flush=True)
            changes_by_player[key] = {"came_online": False, "new_activity": False, "elo_changed": False, "mode_changes": []}

    # Verificar nuevas derrotas de Gato
    new_defeats = []
    try:
        gato_uuid = db["players"]["gato"]["uuid"]
        mh_url = f"https://api.pvprivals.net/matchhistory/{gato_uuid}?beginIndex=0&length=10&platform=LEGACY&matchType=BOTH"
        mh_list = fetch_url_json(mh_url)
        known_ids = set(cfg.get("known_defeat_hex_ids", []))
        if isinstance(mh_list, list):
            for m in mh_list:
                mid_num = m.get("id")
                if not mid_num:
                    continue
                hex_id = hex(int(mid_num))[2:]
                if hex_id in known_ids:
                    continue
                loser_team = m.get("loserTeam") or []
                is_gato_loser = any(
                    (p.get("uuid") == gato_uuid or str(p.get("playerName", "")).lower() == "aimreset")
                    for p in loser_team if isinstance(p, dict)
                )
                if is_gato_loser:
                    m_svelte = fetch_match_svelte_data("AimReset", hex_id)
                    if m_svelte and m_svelte.get("matchDetails"):
                        parsed_defeat = classify_defeat_from_match_details(hex_id, m_svelte["matchDetails"])
                        new_defeats.append(parsed_defeat)
    except Exception:
        pass

    if new_defeats:
        for nd in reversed(new_defeats):
            db["gato_defeats"].insert(0, nd)
            if nd["hexId"] not in cfg.get("known_defeat_hex_ids", []):
                cfg.setdefault("known_defeat_hex_ids", []).insert(0, nd["hexId"])
        save_json(CHANNELS_CONFIG_PATH, cfg)

    gato = db["players"]["gato"]
    fuego = db["players"]["fuego"]
    gian = db["players"]["gian"]

    print(
        f"[{datetime.now(CET).strftime('%H:%M:%S CET')}] "
        f"Gato({ 'ON' if gato['online'] else 'OFF' }): G={gato['global']['elo']} F={gato['modes']['FINALUHC']['elo']} C={gato['modes']['CAVEUHC']['elo']} | "
        f"Fuego: G={fuego['global']['elo']} F={fuego['modes']['FINALUHC']['elo']} C={fuego['modes']['CAVEUHC']['elo']} | "
        f"gianamont: G={gian['global']['elo']} F={gian['modes']['FINALUHC']['elo']} C={gian['modes']['CAVEUHC']['elo']}",
        flush=True
    )

    gato_ch = changes_by_player["gato"]
    any_change = (
        force_update
        or gato_ch["came_online"]
        or gato_ch["new_activity"]
        or gato_ch["elo_changed"]
        or changes_by_player["fuego"]["elo_changed"]
        or changes_by_player["gian"]["elo_changed"]
        or bool(new_defeats)
    )

    if fetched_any or any_change:
        db["last_updated_unix"] = int(datetime.now(timezone.utc).timestamp())
        save_json(DB_PATH, db)

    if not any_change:
        return False

    # Regenerar imágenes y actualizar Discord via REST API
    visual_paths = generate_all_visuals(db)

    # 1. Actualizar #🌍│global
    if cfg.get("global_channel_id") and cfg.get("global_message_id"):
        discord_multipart_patch_message(
            cfg["global_channel_id"],
            cfg["global_message_id"],
            build_global_embed_dict(db),
            visual_paths["global_dashboard"],
            "global_dashboard.png",
            token
        )
        if gato_ch["came_online"] or gato_ch["new_activity"]:
            discord_json_request(
                "POST",
                f"/channels/{cfg['global_channel_id']}/messages",
                {
                    "content": (
                        f"@everyone 🚨 **¡ALERTA: GATO (`AimReset`) ESTÁ {'ONLINE' if gato['online'] else 'JUGANDO'} EN PVPRIVALS!** "
                        f"*(Global: `{gato['global']['elo']}` │ Cave UHC: `{gato['modes']['CAVEUHC']['elo']}`)*"
                    )
                },
                token
            )

    # 2. Actualizar #⚔️│final-uhc
    if cfg.get("final_uhc_channel_id") and cfg.get("final_uhc_message_id"):
        discord_multipart_patch_message(
            cfg["final_uhc_channel_id"],
            cfg["final_uhc_message_id"],
            build_final_uhc_embed_dict(db),
            visual_paths["final_uhc_dashboard"],
            "final_uhc_dashboard.png",
            token
        )

    # 3. Actualizar #⛏️│cave-uhc
    if cfg.get("cave_uhc_channel_id") and cfg.get("cave_uhc_message_id"):
        discord_multipart_patch_message(
            cfg["cave_uhc_channel_id"],
            cfg["cave_uhc_message_id"],
            build_cave_uhc_embed_dict(db),
            visual_paths["cave_uhc_dashboard"],
            "cave_uhc_dashboard.png",
            token
        )
        if (new_defeats or force_update) and cfg.get("cave_defeats_message_id"):
            def_emb = {
                "title": "💀 HISTORIAL DE DERROTAS DE GATO EN CAVE UHC (QUICKDROP vs HEAL)",
                "description": (
                    "• **67% por QUICKDROP:** Muere con **6 a 12 manzanas sin comer** (tiene `~6.3 CPS` de media).\n"
                    "• **Verdugos en Cave UHC:** `Azerdium` (**3W**, `-43 ELO`), `chair_destroyer` (**2W**, `-38 ELO`), `Ticketer` (**2W**, `-33 ELO`), `LUJKY_321` (`-30 ELO` en 16s), `WIZAHHH` (`-23 ELO`)."
                ),
                "color": 0xE74C3C,
                "image": {"url": "attachment://defeats_full_table.png"}
            }
            discord_multipart_patch_message(
                cfg["cave_uhc_channel_id"],
                cfg["cave_defeats_message_id"],
                def_emb,
                visual_paths["defeats_table"],
                "defeats_full_table.png",
                token
            )

        for nd in new_defeats:
            discord_json_request(
                "POST",
                f"/channels/{cfg['cave_uhc_channel_id']}/messages",
                {
                    "content": (
                        f"💀 **¡NUEVA DERROTA DE GATO vs `{nd['opponent']}` (`{nd['gato_elo_change']} ELO`)!** "
                        f"• `{nd['kit']}` ({nd['map']}) • **{nd['loss_type']}** • Fecha: `{fmt_dt_es(nd['date'])}`"
                    )
                },
                token
            )

    # 4. Actualizar contadores de voz en la barra lateral
    stat_updates = {
        "stat_gato_channel_id": f"{'🟢' if gato['online'] else '🔴'} Gato: {gato['global']['elo']}🌐 │ {gato['modes']['CAVEUHC']['elo']}⛏️",
        "stat_fuego_channel_id": f"🔥 Fuego: {fuego['global']['elo']}🌐 │ {fuego['modes']['CAVEUHC']['elo']}⛏️",
        "stat_gian_channel_id": f"⚔️ gianamont: {gian['global']['elo']}🌐 │ {gian['modes']['CAVEUHC']['elo']}⛏️",
    }
    for cfg_key, new_name in stat_updates.items():
        vc_id = cfg.get(cfg_key)
        if vc_id:
            discord_json_request("PATCH", f"/channels/{vc_id}", {"name": new_name}, token)

    print("[+] Paneles de Discord actualizados desde Cloud Sync Engine.", flush=True)
    return True


def main():
    parser = argparse.ArgumentParser(description="Cloud Sync Engine — La Caza del Gato")
    parser.add_argument("--loop-seconds", type=int, default=0, help="Segundos totales de bucle continuo")
    parser.add_argument("--interval", type=int, default=30, help="Intervalo en segundos entre chequeos")
    parser.add_argument("--force", action="store_true", help="Forzar regeneración y subida de paneles en el primer ciclo")
    args = parser.parse_args()

    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        print("[!] Error: Falta la variable de entorno DISCORD_BOT_TOKEN.", flush=True)
        sys.exit(1)

    if args.loop_seconds <= 0:
        run_sync_cycle(token, force_update=args.force)
    else:
        start_t = time.time()
        first = True
        while (time.time() - start_t) < args.loop_seconds:
            run_sync_cycle(token, force_update=(args.force and first))
            first = False
            if (time.time() - start_t) + args.interval >= args.loop_seconds:
                break
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
