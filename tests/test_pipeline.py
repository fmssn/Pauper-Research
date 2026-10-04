import json
from pathlib import Path

import pandas as pd
import pytest

from pauper_research import analysis
from pauper_research.archetypes import Archetype, Classifier, Condition
from pauper_research.loader import load


@pytest.fixture
def classifier() -> Classifier:
    madness = Archetype("Red Madness", False, [Condition("InMainboard", ["Fiery Temper"])],
                        variants=[Archetype("Rakdos Madness", False, [Condition("InMainboard", ["Kitchen Imp"])])])
    affinity = Archetype("Affinity", True, [Condition("OneOrMoreInMainboard", ["Myr Enforcer", "Frogmite"]),
                                            Condition("DoesNotContain", ["Pestilence"])])
    terror = Archetype("Terror", True, [Condition("TwoOrMoreInMainboard", ["Tolarian Terror", "Delver of Secrets", "Ninja"])])
    control = Archetype("Control", True, common_cards=["Counterspell", "Mulldrifter"])
    lands = {"Mountain": "R", "Island": "U", "Swamp": "B", "Seat of the Synod": "U", "Vault of Whispers": "B"}
    spells = {"Fiery Temper": "R", "Kitchen Imp": "B", "Myr Enforcer": "C", "Thoughtcast": "U", "Deadly Dispute": "B",
              "Tolarian Terror": "U", "Delver of Secrets": "U", "Counterspell": "U", "Mulldrifter": "U", "Pestilence": "B"}
    return Classifier([madness, affinity, terror], [control], lands, spells)


def test_variant_and_base(classifier):
    assert classifier.detect({"Fiery Temper": 4, "Mountain": 16}, {}).archetype == "Red Madness"
    d = classifier.detect({"Fiery Temper": 4, "Kitchen Imp": 4, "Mountain": 10, "Swamp": 6}, {})
    assert d.archetype == "Rakdos Madness" and d.color == "BR"


def test_color_needs_lands_and_spells(classifier):
    # Thoughtcast is blue, but without a blue land the deck isn't blue.
    d = classifier.detect({"Myr Enforcer": 4, "Thoughtcast": 4, "Deadly Dispute": 4, "Vault of Whispers": 4}, {})
    assert d.color == "B" and d.archetype == "Mono Black Affinity"


def test_does_not_contain_checks_sideboard(classifier):
    d = classifier.detect({"Frogmite": 4, "Seat of the Synod": 4, "Thoughtcast": 4}, {"Pestilence": 1})
    assert d.archetype != "Mono Blue Affinity"


def test_two_or_more_counts_distinct_cards(classifier):
    assert classifier.detect({"Tolarian Terror": 4, "Island": 16}, {}).archetype != "Mono Blue Terror"
    assert classifier.detect({"Tolarian Terror": 4, "Delver of Secrets": 4, "Island": 16}, {}).archetype == "Mono Blue Terror"


def test_conflict_prefers_simpler_and_fallback(classifier):
    d = classifier.detect({"Fiery Temper": 4, "Frogmite": 4, "Mountain": 10}, {})
    assert d.archetype == "Red Madness" and d.candidates == ["Red Madness", "Mono Red Affinity"]
    fb = classifier.detect({"Counterspell": 4, "Mulldrifter": 4, "Island": 18}, {})
    assert fb.archetype == "Mono Blue Control" and fb.is_fallback


def test_wilson():
    lo, hi = analysis.wilson(15, 30)
    assert lo == pytest.approx(0.332, abs=1e-3) and hi == pytest.approx(0.668, abs=1e-3)
    assert all(pd.isna(x) for x in analysis.wilson(0, 0))


def _deck(player, main, result="1st Place"):
    return {"Player": player, "Result": result, "Mainboard": [{"CardName": c, "Count": n} for c, n in main.items()],
            "Sideboard": []}


def _write_event(root: Path, rel: str, fmt: str, uri: str, decks, rounds):
    path = root / "Tournaments" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"Tournament": {"Date": "2026-09-01", "Name": "Test", "Uri": uri, "Formats": fmt},
                                "Decks": decks, "Rounds": rounds, "Standings": []}))


@pytest.fixture
def tables(tmp_path, classifier):
    madness = {"Fiery Temper": 4, "Mountain": 16}
    affinity = {"Frogmite": 4, "Seat of the Synod": 4, "Thoughtcast": 4}
    decks = [_deck("a", madness), _deck("b", affinity), _deck("c", {**madness, "Lightning Bolt": 4}),
             _deck("d", affinity)]
    rounds = [{"RoundName": "Round 1", "Matches": [
        {"Player1": "a", "Player2": "b", "Result": "2-1-0"},
        {"Player1": "c", "Player2": "d", "Result": "0-2-0"},
        {"Player1": "e", "Player2": "-", "Result": "2-0-0"},     # bye: dropped
        {"Player1": "a", "Player2": "c", "Result": "2-0-0"},     # mirror
    ]}, {"RoundName": "Round 2", "Matches": [
        {"Player1": "a", "Player2": "d", "Result": "1-1-1"},     # draw
        {"Player1": "b", "Player2": "x", "Result": "2-0-0"},     # opponent without list
    ]}]
    _write_event(tmp_path, "MTGmelee/2026/09/01/a.json", "Pauper", "u1", decks, rounds)
    _write_event(tmp_path, "MTGmelee/2026/09/01/dup.json", "Pauper", "u1", decks, rounds)   # duplicate
    _write_event(tmp_path, "MTGmelee/2026/09/01/m.json", "Modern", "u2", decks, rounds)     # other format
    return load(tmp_path, classifier)


def test_loader(tables):
    assert len(tables["events"]) == 1
    assert len(tables["decks"]) == 4
    m = tables["matches"]
    assert len(m) == 10  # 5 real matches, each from both sides
    draw = m[(m.player == "a") & (m.opponent == "d")]
    assert draw.score.item() == 0.5 and draw.games_drawn.item() == 1
    assert m[m.opponent == "x"].opp_archetype.item() == "Unknown"


def test_matchups_and_summary(tables):
    mu = analysis.matchup_table(tables["matches"]).set_index(["archetype", "opp_archetype"])
    # Madness vs Affinity: a beat b, c lost to d, a drew d -> 1.5 / 3
    assert mu.loc[("Red Madness", "Mono Blue Affinity"), "wins"] == 1.5
    assert mu.loc[("Mono Blue Affinity", "Red Madness"), "wins"] == 1.5
    summary = analysis.archetype_summary(tables["decks"], tables["matches"]).set_index("archetype")
    # Affinity also gets the win over the opponent with no list.
    assert summary.loc["Mono Blue Affinity", "matches"] == 4
    assert summary.loc["Mono Blue Affinity", "wins"] == 2.5


def test_card_impact(tables):
    impact = analysis.card_impact(tables["decks"], tables["deck_cards"], tables["matches"], "Red Madness", min_decks=1)
    bolt = impact.set_index("card").loc["Lightning Bolt"]
    assert bolt.decks_with == 1 and bolt.win_rate_with == 0.0 and bolt.win_rate_without == 0.75


def test_scopes(tables):
    # The fixture only has Melee events, so "online" is empty.
    t = tables
    online = analysis.filter_period(t, scope="online")
    paper = analysis.filter_period(t, scope="paper")
    assert online["matches"].empty and len(paper["matches"]) == len(t["matches"])
    with pytest.raises(ValueError):
        analysis.filter_period(t, scope="moon")
    comp = analysis.scope_comparison(t).set_index("archetype")
    assert comp.loc["Red Madness", "online_matches"] == 0
    assert comp.loc["Red Madness", "paper_matches"] == comp.loc["Red Madness", "combined_matches"]
    assert not comp["skew"].any()


def test_dashboard_renders(tables):
    from pauper_research import dashboard
    data = dashboard.build_data(tables)
    block = data["periods"]["30d"]["scopes"]["paper"]
    names = [a[0] for a in block["archetypes"]]
    assert set(names) == {"Red Madness", "Mono Blue Affinity"}
    # Both decks have each other as a matchup, stored by index.
    rm = names.index("Red Madness")
    assert [m[0] for m in block["mu"][rm]] == [names.index("Mono Blue Affinity")]
    assert set(block["cards"][rm]) == {"main", "side", "decks"}
    html = dashboard.render(data, standalone=False)
    assert "/*__DATA__*/" not in html and "<!doctype" not in html
    assert dashboard.render(data).startswith("<!doctype html>")


def test_newcombe():
    # Newcombe (1998), example (a): 56/70 vs 48/80 -> 0.0524 to 0.3339
    lo, hi = analysis.newcombe(56, 70, 48, 80)
    assert lo == pytest.approx(0.0524, abs=1e-3) and hi == pytest.approx(0.3339, abs=1e-3)


def test_card_effects_by_opponent(tables):
    eff = analysis.card_effects(tables["decks"], tables["deck_cards"], tables["matches"], "Red Madness",
                                by_opponent=True, min_decks=1)
    bolt = eff[eff.card == "Lightning Bolt"].set_index("opponent")
    # Only deck c plays Bolt: it lost to d. Deck a (no Bolt) beat b and drew d.
    row = bolt.loc["Mono Blue Affinity"]
    assert (row.matches_with, row.wins_with, row.matches_without, row.wins_without) == (1, 0.0, 2, 1.5)


def test_image_sheets(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    from PIL import Image
    from pauper_research import scryfall
    names = [f"Card {i}" for i in range(11)]
    paths = {}
    for i, n in enumerate(names):
        p = tmp_path / f"{i}.jpg"
        Image.new("RGB", (488, 680), (i * 20, 0, 0)).save(p)
        paths[n] = p
    monkeypatch.setattr(scryfall, "lookup", lambda ns: {n: {} for n in ns})
    monkeypatch.setattr(scryfall, "download", lambda entries: {n: paths[n] for n in entries})
    index = scryfall.build_sheets(names, tmp_path / "out")
    per = scryfall.SHEET_COLS * scryfall.SHEET_ROWS
    assert len(index["sheets"]) == -(-len(names) // per)
    assert index["cards"]["Card 10"] == [10 // per, 10 % per]
    last = Image.open(tmp_path / "out" / index["sheets"][-1]["file"])
    assert last.size == (scryfall.SHEET_COLS * 488, index["sheets"][-1]["rows"] * 680)


def test_normalize_name():
    from pauper_research.ratings import normalize_name
    assert normalize_name(" Tim  Bunnik ") == normalize_name("tim bunnik") == "tim bunnik"
    assert normalize_name("xXPeregrinoXx") == normalize_name("XxPeregrinoxX")
    assert normalize_name(None) == ""


def _confounded_matches(seed=3, n_players=200, n_events=120, per_event=16, rounds=4):
    """Two equally strong decks, but the strongest players all register "Strong Pilots".
    Lightning Bolt is played only by the strong players' lists."""
    import numpy as np
    rng = np.random.default_rng(seed)
    skill = rng.normal(0, 0.8, n_players)
    strong = skill > np.quantile(skill, 0.75)
    rows, decks, cards, did = [], [], [], 0
    for e in range(n_events):
        date = pd.Timestamp("2026-01-01") + pd.Timedelta(days=int(rng.integers(0, 240)))
        players = rng.choice(n_players, per_event, replace=False)
        deck = {}
        for p in players:
            arch = "Strong Pilots" if strong[p] or rng.random() < 0.15 else "Everyone"
            deck[p] = (did, arch)
            decks.append({"deck_id": did, "event_id": e, "date": date, "source": "MTGmelee", "player": f"P{p}",
                          "archetype": arch})
            cards.append({"deck_id": did, "card": "Lightning Bolt" if strong[p] else "Chain Lightning",
                          "board": "main", "count": 4})
            did += 1
        for _ in range(rounds):
            order = rng.permutation(players)
            for a, b in zip(order[::2], order[1::2]):
                s = float(rng.random() < 1 / (1 + np.exp(-(skill[a] - skill[b]))))
                for me, opp, sc in ((a, b, s), (b, a, 1 - s)):
                    rows.append({"event_id": e, "date": date, "source": "MTGmelee", "round": "R",
                                 "player": f"P{me}", "opponent": f"P{opp}", "deck_id": deck[me][0],
                                 "opp_deck_id": deck[opp][0], "score": sc,
                                 "archetype": deck[me][1], "opp_archetype": deck[opp][1]})
    return pd.DataFrame(rows), pd.DataFrame(decks), pd.DataFrame(cards)


def test_pilot_adjustment_removes_pilot_edge():
    from pauper_research import ratings
    matches, decks, cards = _confounded_matches()
    pilot = ratings.fit(matches, matches["date"].max(), bootstrap=5)
    assert pilot.lam in ratings.LAMBDA_GRID and pilot.boot.shape == (len(matches), 5)
    # Lifts are antisymmetric: every match's two sides cancel out.
    assert pilot.lift.sum() == pytest.approx(0, abs=1e-6)

    s = analysis.archetype_summary(decks, matches, pilot).set_index("archetype")
    strong = s.loc["Strong Pilots"]
    assert strong.win_rate > 0.55 and strong.pilot_lift > 0.03
    # The decks are equally strong: adjusting moves the win rate towards 50%.
    assert abs(strong.adj_win_rate - 0.5) < abs(strong.win_rate - 0.5)
    assert s.loc["Everyone", "pilot_lift"] < 0
    # The lift's own uncertainty makes the interval wider than the shifted Wilson interval.
    assert strong.adj_ci_high - strong.adj_ci_low > strong.ci_high - strong.ci_low

    mu = analysis.matchup_table(matches, pilot=pilot).set_index(["archetype", "opp_archetype"])
    assert mu.loc[("Strong Pilots", "Everyone"), "pilot_lift"] == pytest.approx(
        -mu.loc[("Everyone", "Strong Pilots"), "pilot_lift"])


def test_card_effects_adjusted_for_pilots():
    from pauper_research import ratings
    matches, decks, cards = _confounded_matches()
    pilot = ratings.fit(matches, matches["date"].max(), bootstrap=5)
    eff = analysis.card_impact(decks, cards, matches, "Strong Pilots", min_decks=3, pilot=pilot).set_index("card")
    bolt = eff.loc["Lightning Bolt"]
    # Bolt "wins more" only because strong players play it; the adjustment shrinks that.
    assert bolt.delta > 0.05 and bolt.lift_with > bolt.lift_without
    assert bolt.delta_adj < bolt.delta
    assert bolt.delta_adj_ci_low < bolt.delta_adj < bolt.delta_adj_ci_high
    without_pilot = analysis.card_impact(decks, cards, matches, "Strong Pilots", min_decks=3)
    assert "delta_adj" not in without_pilot.columns


def test_dashboard_carries_pilot_lift():
    from pauper_research import dashboard
    matches, decks, cards = _confounded_matches()
    events = decks.groupby("event_id").agg(date=("date", "first"), source=("source", "first")).reset_index()
    decks = decks.assign(color="R")
    tables = {"events": events, "decks": decks, "deck_cards": cards, "matches": matches}
    data = dashboard.build_data(tables, bootstrap=3)
    block = data["periods"]["180d"]["scopes"]["paper"]
    by_name = {a[0]: a for a in block["archetypes"]}
    assert by_name["Strong Pilots"][6] > 0 and by_name["Everyone"][6] < 0
    assert block["pilot"]["rated"] > 0
    assert all(len(m) == 5 for ms in block["mu"].values() for m in ms)
    # Both decks have enough matches for a skill sensitivity: [value, ci_low, ci_high, matches].
    assert set(block["skill"]) == {0, 1} and all(len(v) == 4 for v in block["skill"].values())


def test_methods_page_in_sync():
    """Every value the methods page shows is filled by the page script, and every
    model setting it documents comes from the build data."""
    import re
    from pauper_research import dashboard, ratings
    template = dashboard.TEMPLATE.read_text(encoding="utf-8")
    shown = set(re.findall(r'data-k="(\w+)"', template))
    script = template[template.index("function renderMethods"):template.index("function typeset")]
    filled = set(re.findall(r"(\w+):", script[script.index("const vals"):]))
    assert shown and shown <= filled, f"methods page shows values nobody fills: {shown - filled}"
    for section in ("m-sources", "m-refs", "m-results", "m-share", "m-winrate", "m-wilson", "m-labels", "m-cards", "m-builds", "m-pilot", "m-skill",
                    "m-thresholds"):
        assert f'id="{section}"' in template
    matches, decks, cards = _confounded_matches(n_events=30)
    events = decks.groupby("event_id").agg(date=("date", "first"), source=("source", "first")).reset_index()
    data = dashboard.build_data({"events": events, "decks": decks.assign(color="R"), "deck_cards": cards,
                                 "matches": matches}, bootstrap=0)
    assert data["methods"]["lambda_grid"] == list(ratings.LAMBDA_GRID)
    assert data["methods"]["half_life_days"] == ratings.HALF_LIFE_DAYS
    assert data["periods"]["180d"]["scopes"]["paper"]["pilot"]["lam"] in ratings.LAMBDA_GRID
    assert data["methods"]["slope_lambda"] == ratings.SLOPE_LAMBDA
    # Every source's contribution to each statistic adds up to the totals.
    assert set(data["sources"]["sites"]) >= {src for v in data["sources"]["scopes"].values() if v for src in v}
    block = data["periods"]["180d"]["scopes"]["combined"]
    rows = block["coverage"]["by_source"]
    assert sum(r["decks"] for r in rows) == block["coverage"]["decks"]
    assert sum(r["matches"] for r in rows) == block["coverage"]["matches"]
    assert all({"winrate", "matchup", "weight"} <= set(r) for r in rows)
    assert sum(r["weight"] for r in rows) > 0


def _skill_matches(seed=5, n_players=300, n_events=200, per_event=16, rounds=5):
    """Three decks of equal strength, picked at random. On "Combo" a rating edge
    counts twice as much, on "Burn" half as much."""
    import numpy as np
    rng = np.random.default_rng(seed)
    skill = rng.normal(0, 0.8, n_players)
    factor = {"Combo": 2.0, "Midrange": 1.0, "Burn": 0.5}
    rows = []
    for e in range(n_events):
        date = pd.Timestamp("2026-01-01") + pd.Timedelta(days=int(rng.integers(0, 300)))
        players = rng.choice(n_players, per_event, replace=False)
        deck = {p: rng.choice(list(factor)) for p in players}
        for _ in range(rounds):
            order = rng.permutation(players)
            for a, b in zip(order[::2], order[1::2]):
                eta = factor[deck[a]] * skill[a] - factor[deck[b]] * skill[b]
                s = float(rng.random() < 1 / (1 + np.exp(-eta)))
                for me, opp, sc in ((a, b, s), (b, a, 1 - s)):
                    rows.append({"event_id": e, "date": date, "source": "MTGmelee", "player": f"P{me}",
                                 "opponent": f"P{opp}", "score": sc, "archetype": deck[me],
                                 "opp_archetype": deck[opp]})
    return pd.DataFrame(rows)


def test_skill_sensitivity():
    from pauper_research import ratings
    matches = _skill_matches()
    pilot = ratings.fit(matches, matches["date"].max(), bootstrap=20)
    sk = pilot.skill
    # Relative to the average deck (factor 3.5 / 3): Combo 1.71, Midrange 0.86, Burn 0.43.
    assert sk.loc["Combo", "sensitivity"] == pytest.approx(1.71, abs=0.15)
    assert sk.loc["Midrange", "sensitivity"] == pytest.approx(0.86, abs=0.1)
    assert sk.loc["Burn", "sensitivity"] == pytest.approx(0.43, abs=0.1)
    assert sk.loc["Combo", "ci_low"] > 1 > sk.loc["Burn", "ci_high"]
    weights = sk["matches"] / sk["matches"].sum()
    assert (weights * sk["sensitivity"]).sum() == pytest.approx(1)


def _two_builds(seed=1, n=200):
    """A deck in two builds (Ninja + Delver, or Counterspell + Mulldrifter), a 4-card slot of
    Bolt and Chain Lightning, 17 or 18 Island, and 4 Brainstorm everywhere. The Ninja build
    wins 70% of its matches, the other 40%."""
    import numpy as np
    rng = np.random.default_rng(seed)
    cards, matches = [], []
    for d in range(n):
        ninja = d < n // 2
        bolt = int(rng.choice([4, 3, 2], p=[0.6, 0.3, 0.1]))
        main = {"Brainstorm": 4, "Island": int(rng.choice([17, 18])), "Lightning Bolt": bolt, "Chain Lightning": 4 - bolt,
                **({"Ninja": 4, "Delver of Secrets": 4} if ninja else {"Counterspell": 4, "Mulldrifter": 4})}
        cards += [{"deck_id": d, "card": c, "board": "main", "count": k} for c, k in main.items() if k]
        for r in range(4):
            opp = "Elves" if r % 2 else "Affinity"
            win = rng.random() < (0.7 if ninja else 0.4)
            matches.append({"deck_id": d, "archetype": "Terror", "opp_archetype": opp, "score": float(win)})
    decks = pd.DataFrame({"deck_id": range(n), "archetype": "Terror"})
    return decks, pd.DataFrame(cards), pd.DataFrame(matches)


def test_decisions_builds_and_slots():
    from pauper_research import decisions
    decks, cards, matches = _two_builds()
    rec = decisions.Records(matches, None)
    out = decisions.archetype(decks, cards, "Terror", rec, {"Elves": 0, "Affinity": 1})
    main = out["main"]
    assert main["lists"] == 200 and "side" not in out
    # The first question splits the two builds; within them, the slot is most of what's left to
    # explain, so builds can split further on it. The largest build is the stock list.
    ls = main["builds"]
    # Other builds are named by how they differ from it: "Counterspell build", "…, 2 Chain Lightning".
    assert ls[0]["name"] == "Stock list" and "Counterspell build" in [b["name"] for b in ls]
    assert len({b["name"] for b in ls}) == len(ls) and sum(b["lists"] for b in ls) == 200
    assert all(b["path"][0][0] in {"Ninja", "Delver of Secrets", "Counterspell", "Mulldrifter"} for b in ls)
    ninja = [b for b in ls if dict(b["list"]).get("Ninja")]
    assert sum(b["lists"] for b in ninja) == 100
    assert all(dict(b["list"])["Delver of Secrets"] == 4 and "Counterspell" not in dict(b["list"]) for b in ninja)
    # Records are [wins, matches, lift, sd]; build matchups compare with the deck's other lists.
    rate = lambda bs: sum(b["win"][0] for b in bs) / sum(b["win"][1] for b in bs)
    assert sum(b["win"][1] for b in ninja) == 400 and rate(ninja) > 0.6 > rate([b for b in ls if b not in ninja])
    assert all(e[0] in (0, 1) and len(e) == 8 for b in ls for e in b["mu"])
    assert all(b["cmp"][1] + b["cmp"][4] == 800 for b in ls)
    # Within the whole deck: Bolt and Chain fill one 4-card slot, Island is a copy-count decision.
    dec = main["dec"]
    slot = next(s for s in dec["slots"] if "Lightning Bolt" in s["cards"])
    assert set(slot["cards"]) == {"Lightning Bolt", "Chain Lightning"} and slot["total"] == 4
    # Each split is an option: [counts, share, record, comparison with the other lists, matchups].
    assert slot["configs"][0][0] == [4, 0] and len(slot["configs"][0]) == 5
    assert dec["cards"]["Brainstorm"] == ["fixed", 4]
    island = dec["cards"]["Island"]
    assert island[0] == "count" and island[3][:2] == [18, 17] and len(island[4]) == 2
    # In/out cards compare lists with the card against lists without it.
    ninja_card = dec["cards"]["Ninja"]
    assert ninja_card[0] == "inout" and ninja_card[3][1] == 400 and ninja_card[3][4] == 400
    # Inside a build, the other build's cards don't show up as choices.
    assert all("Counterspell" not in b["dec"]["cards"] for b in ninja)


def test_decisions_need_enough_lists():
    from pauper_research import decisions
    decks, cards, matches = _two_builds(n=decisions.MIN_LISTS - 2)
    rec = decisions.Records(matches, None)
    assert decisions.archetype(decks, cards, "Terror", rec, {}) is None
