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
    assert {a["name"] for a in block["archetypes"]} == {"Red Madness", "Mono Blue Affinity"}
    html = dashboard.render(data, standalone=False)
    assert "/*__DATA__*/" not in html and "<!doctype" not in html
    assert dashboard.render(data).startswith("<!doctype html>")
