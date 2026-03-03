#!/usr/bin/env python3
"""
Pokemonle Solver - 宝可梦猜谜辅助工具

Directly reads individual Pokémon data files from the original game's
serve/src/data/pokemon/ directory. No data merging or preprocessing needed.

Usage:
    python solver.py --data-dir /path/to/pokemonle/serve/src/data/pokemon
"""

import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

GENERATIONS = [
    "第一世代", "第二世代", "第三世代", "第四世代", "第五世代",
    "第六世代", "第七世代", "第八世代", "第九世代",
]


class PokedexReader:
    """Reads Pokémon data directly from individual JSON files in the game's
    data directory (serve/src/data/pokemon/). No merged file is needed."""

    def __init__(self, data_dir: str):
        """
        Args:
            data_dir: Path to the directory containing XXXX-name.json files
                      (typically serve/src/data/pokemon/ from the game repo).
        """
        self.data_dir = Path(data_dir)
        self._pokemon: Optional[List[Dict]] = None

    def load(self) -> List[Dict]:
        """Scan the data directory and load each Pokémon JSON file directly.

        Alternate forms that share the same Pokédex index are skipped so that
        only one entry per Pokémon number is kept, matching game behaviour.

        Each returned dict has an extra ``_generation`` key derived from the
        first entry in ``flavor_texts``.
        """
        if self._pokemon is not None:
            return self._pokemon

        seen_indexes: Set[str] = set()
        pokemon_list: List[Dict] = []

        for filepath in sorted(self.data_dir.glob("*.json")):
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            index = data.get("index", "")
            if index in seen_indexes:
                continue
            seen_indexes.add(index)

            generation = self._derive_generation(data)
            if generation is None:
                continue

            data["_generation"] = generation
            pokemon_list.append(data)

        self._pokemon = pokemon_list
        return pokemon_list

    @staticmethod
    def _derive_generation(data: Dict) -> Optional[str]:
        """Derive generation from the first flavor-text entry."""
        flavor_texts = data.get("flavor_texts", [])
        if flavor_texts:
            return flavor_texts[0].get("name")
        return None

    def get_by_name(self, name: str) -> Optional[Dict]:
        """Return the Pokémon dict with the given Chinese name, or None."""
        for pokemon in self.load():
            if pokemon["name"] == name:
                return pokemon
        return None

    def get_names(self) -> List[str]:
        """Return a list of all Pokémon names."""
        return [p["name"] for p in self.load()]


# ---------------------------------------------------------------------------
# Attribute extraction helpers (mirror game logic in pokeUtils.py)
# ---------------------------------------------------------------------------

def _types(p: Dict) -> List[str]:
    raw = p.get("forms", [{}])[0].get("types", [])
    return [raw[0], raw[1] if len(raw) > 1 else "无"]


def _power_sum(p: Dict) -> int:
    data = p.get("stats", [{}])[0].get("data", {})
    return sum(int(v) for v in data.values())


def _speed(p: Dict) -> int:
    data = p.get("stats", [{}])[0].get("data", {})
    return int(data.get("speed", 0))


def _abilities(p: Dict) -> List[str]:
    return [a["name"] for a in p.get("forms", [{}])[0].get("ability", [])]


def _egg_groups(p: Dict) -> List[str]:
    return p.get("forms", [{}])[0].get("egg_groups", [])


def _catch_rate(p: Dict) -> int:
    cr = p.get("forms", [{}])[0].get("catch_rate", {})
    return int(cr.get("number", 0))


def _shape(p: Dict) -> str:
    return p.get("forms", [{}])[0].get("shape", "")


def _color(p: Dict) -> str:
    return p.get("forms", [{}])[0].get("color", "")


def _attack_type(p: Dict) -> str:
    d = p.get("stats", [{}])[0].get("data", {})
    at, pt = int(d.get("attack", 0)), int(d.get("sp_attack", 0))
    if at == pt:
        return "物攻=特攻"
    return "物攻>特攻" if at > pt else "物攻<特攻"


def _defense_type(p: Dict) -> str:
    d = p.get("stats", [{}])[0].get("data", {})
    ad, pd = int(d.get("defense", 0)), int(d.get("sp_defense", 0))
    if ad == pd:
        return "物防=特防"
    return "物防>特防" if ad > pd else "物防<特防"


def _evolution_info(p: Dict) -> Tuple[str, Optional[str]]:
    """Return (stage, text) for this Pokémon."""
    chains = p.get("evolution_chains", [])
    if not chains:
        return "未进化/不进化", None
    for entry in chains[0]:
        if entry.get("name") == p["name"]:
            stage = entry.get("stage", "")
            text = entry.get("text")
            if stage in ("不进化", "未进化", "幼年"):
                stage = "未进化/不进化"
            return stage, text
    return "未进化/不进化", None


def _is_level_evo(text: Optional[str]) -> bool:
    return bool(text and re.search(r"等级\d+", text))


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class Solver:
    """Filter Pokémon candidates based on game feedback and suggest guesses.

    Data is consumed directly from PokedexReader — no merged file needed.
    """

    def __init__(self, reader: PokedexReader):
        self.reader = reader
        self.candidates: List[Dict] = list(reader.load())

    def reset(self) -> None:
        """Restore the full candidate list."""
        self.candidates = list(self.reader.load())

    @property
    def remaining_count(self) -> int:
        return len(self.candidates)

    def apply_feedback(self, guess_name: str, feedback: Dict) -> None:
        """Narrow down candidates using one round of game feedback.

        Args:
            guess_name: The Pokémon that was guessed (Chinese name).
            feedback:   Dict in the same format the game returns from /guess.
        """
        guess = self.reader.get_by_name(guess_name)
        if guess is None:
            raise ValueError(f"Unknown Pokémon: {guess_name}")
        self.candidates = [
            c for c in self.candidates
            if self._compatible(c, guess, feedback)
        ]

    def suggest(self, top_n: int = 5) -> List[str]:
        """Return up to *top_n* names from remaining candidates."""
        return [p["name"] for p in self.candidates[:top_n]]

    # ------------------------------------------------------------------
    # Compatibility check
    # ------------------------------------------------------------------

    def _compatible(self, candidate: Dict, guess: Dict, fb: Dict) -> bool:
        """Return True when *candidate* is consistent with feedback *fb*."""

        # --- Types -------------------------------------------------------
        if "type" in fb:
            guess_types = _types(guess)
            cand_types = _types(candidate)
            for t_info in fb["type"]:
                t = t_info["key"]
                if t == "无":
                    continue
                if t_info["value"] == "True" and t not in cand_types:
                    return False
                if t_info["value"] == "False" and t in cand_types:
                    return False

        # --- Total base stats --------------------------------------------
        if "pow" in fb:
            g_pow = _power_sum(guess)
            c_pow = _power_sum(candidate)
            v = fb["pow"]["value"]
            if v == "equiv" and c_pow != g_pow:
                return False
            if v == "low" and c_pow <= g_pow:
                return False
            if v == "high" and c_pow >= g_pow:
                return False

        # --- Speed -------------------------------------------------------
        if "speed" in fb:
            g_spd = _speed(guess)
            c_spd = _speed(candidate)
            v = fb["speed"]["value"]
            if v == "equiv" and c_spd != g_spd:
                return False
            if v == "low" and c_spd <= g_spd:
                return False
            if v == "high" and c_spd >= g_spd:
                return False

        # --- Generation --------------------------------------------------
        if "gen" in fb:
            try:
                g_gen = GENERATIONS.index(guess.get("_generation", ""))
                c_gen = GENERATIONS.index(candidate.get("_generation", ""))
                v = fb["gen"]["value"]
                if v == "equiv" and c_gen != g_gen:
                    return False
                if v == "low" and c_gen <= g_gen:
                    return False
                if v == "high" and c_gen >= g_gen:
                    return False
            except ValueError:
                pass

        # --- Attack / Defense type ---------------------------------------
        if "attack" in fb:
            match = fb["attack"]["value"] == "True"
            same = _attack_type(candidate) == _attack_type(guess)
            if match != same:
                return False

        if "defense" in fb:
            match = fb["defense"]["value"] == "True"
            same = _defense_type(candidate) == _defense_type(guess)
            if match != same:
                return False

        # --- Shape / Color -----------------------------------------------
        if "shape" in fb:
            match = fb["shape"]["value"] == "True"
            same = _shape(candidate) == _shape(guess)
            if match != same:
                return False

        if "col" in fb:
            match = fb["col"]["value"] == "True"
            same = _color(candidate) == _color(guess)
            if match != same:
                return False

        # --- Evolution stage and method ----------------------------------
        if "stage" in fb:
            g_stage, _ = _evolution_info(guess)
            c_stage, _ = _evolution_info(candidate)
            match = fb["stage"]["value"] == "True"
            same = c_stage == g_stage
            if match != same:
                return False

        if "evo" in fb:
            _, g_evo = _evolution_info(guess)
            _, c_evo = _evolution_info(candidate)
            v = fb["evo"]["value"]
            if v == "equiv" and c_evo != g_evo:
                return False
            if v == "near":
                # Both should share the same broad evolution category
                def _evo_category(text: Optional[str]) -> str:
                    if text is None:
                        return "none"
                    if _is_level_evo(text):
                        return "level"
                    if "使用" in text:
                        return "item"
                    if "来到" in text:
                        return "location"
                    if "亲密度" in text:
                        return "friendship"
                    return "other"
                if _evo_category(g_evo) != _evo_category(c_evo):
                    return False

        # --- Abilities ---------------------------------------------------
        if "ability" in fb:
            cand_abs = _abilities(candidate)
            for ab_info in fb["ability"]:
                if ab_info["value"] == "True" and ab_info["key"] not in cand_abs:
                    return False

        # --- Egg groups --------------------------------------------------
        if "egg" in fb:
            cand_eggs = _egg_groups(candidate)
            for egg_info in fb["egg"]:
                if egg_info["value"] == "True" and egg_info["key"] not in cand_eggs:
                    return False

        # --- Catch rate --------------------------------------------------
        if "catrate" in fb:
            g_cr = _catch_rate(guess)
            c_cr = _catch_rate(candidate)
            v = fb["catrate"]["value"]
            if v == "equiv" and c_cr != g_cr:
                return False
            if v == "low" and c_cr <= g_cr:
                return False
            if v == "high" and c_cr >= g_cr:
                return False

        return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_feedback_interactive() -> Tuple[str, Dict]:
    """Collect a single round of feedback from the user at the terminal."""
    guess_name = input("猜测的宝可梦名称: ").strip()

    fb: Dict = {}

    def _ask(prompt: str) -> str:
        return input(f"  {prompt} (直接回车跳过): ").strip()

    raw_types = _ask("属性 (如: 草,毒 / 草 / 无第二属性用'无')")
    raw_type_match = _ask("属性是否完全匹配? (y/n/部分, 如: True,True 或 True,False)")
    if raw_types:
        types = [t.strip() for t in raw_types.split(",")]
        matches = [m.strip() for m in raw_type_match.split(",")]
        fb["type"] = [
            {"key": t, "value": ("True" if m.lower() in ("y", "true", "yes") else "False")}
            for t, m in zip(types, matches)
        ]

    pow_val = _ask("种族值总和比较 (equiv/low/high)")
    if pow_val:
        fb["pow"] = {"value": pow_val}

    spd_val = _ask("速度比较 (equiv/low/high)")
    if spd_val:
        fb["speed"] = {"value": spd_val}

    gen_val = _ask("世代比较 (equiv/low/high)")
    if gen_val:
        fb["gen"] = {"value": gen_val}

    atk_val = _ask("攻击类型匹配? (True/False)")
    if atk_val:
        fb["attack"] = {"value": atk_val}

    def_val = _ask("防御类型匹配? (True/False)")
    if def_val:
        fb["defense"] = {"value": def_val}

    shp_val = _ask("外形匹配? (True/False)")
    if shp_val:
        fb["shape"] = {"value": shp_val}

    col_val = _ask("颜色匹配? (True/False)")
    if col_val:
        fb["col"] = {"value": col_val}

    stg_val = _ask("进化阶段匹配? (True/False)")
    if stg_val:
        fb["stage"] = {"value": stg_val}

    return guess_name, fb


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pokemonle 求解器 — 直接读取原游戏图鉴数据文件"
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="原游戏 serve/src/data/pokemon/ 目录路径",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="每轮显示的候选宝可梦数量 (默认 10)",
    )
    args = parser.parse_args()

    reader = PokedexReader(args.data_dir)
    solver = Solver(reader)

    print(f"已加载 {solver.remaining_count} 只宝可梦数据（直接读取自 {args.data_dir}）\n")

    while solver.remaining_count > 1:
        top = solver.suggest(args.top)
        print(f"剩余候选: {solver.remaining_count} 只")
        print(f"建议猜测: {', '.join(top)}\n")

        try:
            guess_name, feedback = _parse_feedback_interactive()
        except (EOFError, KeyboardInterrupt):
            print("\n退出")
            break

        try:
            solver.apply_feedback(guess_name, feedback)
        except ValueError as exc:
            print(f"错误: {exc}")
            continue

        print()

    if solver.remaining_count == 1:
        print(f"答案是: {solver.candidates[0]['name']}")
    elif solver.remaining_count == 0:
        print("没有符合条件的宝可梦，请检查输入的反馈是否正确。")


if __name__ == "__main__":
    main()
