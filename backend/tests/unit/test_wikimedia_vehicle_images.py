"""Unit tests for `app/services/wikimedia_vehicle_images.py` — pure
candidate/scoring/response-parsing/validation logic only. No test here
performs a network call (remote lookup is disabled process-wide in
tests/conftest.py; `resolve_remote_vehicle_image` itself is exercised
against the live API only in manual verification).
"""

from __future__ import annotations

import io

from PIL import Image

from app.services import wikimedia_vehicle_images as wv


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), color=(200, 10, 10)).save(buffer, format="PNG")
    return buffer.getvalue()


def _page(title: str, extract: str = "", thumb: str = "https://upload.wikimedia.org/x.jpg"):
    return wv.PageCandidate(title=title, extract=extract, thumbnail_url=thumb)


# Real-shaped fixtures for the two known-ambiguous India-market cases.
OLD_BALENO_EXTRACT = (
    "The Suzuki Baleno nameplate has been used by the Japanese manufacturer "
    "Suzuki to denote several different subcompact cars since 1996. From 1996 "
    "to 2002, the Baleno that was sold in Europe and Asia-Pacific was a "
    "rebadged Cultus Crescent. It was also produced and sold in India as the "
    "Maruti Suzuki Baleno until 2007."
)
NEW_BALENO_EXTRACT = (
    "The Suzuki Baleno is a subcompact car produced by the Japanese "
    "manufacturer Suzuki in India and some other countries since September "
    "2015 with a hatchback body style."
)
MG_ZS_EXTRACT = (
    "The MG ZS is a subcompact crossover SUV produced by the Chinese "
    "automotive manufacturer SAIC Motor under the British MG marque."
)


class TestCandidateTitles:
    def test_plain_make_model(self):
        assert wv.candidate_titles("Honda", "Civic") == ["Honda Civic"]

    def test_alias_expansion_for_indian_market_names(self):
        titles = wv.candidate_titles("Maruti Suzuki", "Swift")
        assert titles[0] == "Maruti Suzuki Swift"
        assert "Suzuki Swift" in titles
        assert "Maruti Swift" in titles

    def test_tata_motors_and_mg_motor_aliases(self):
        assert "Tata Nexon" in wv.candidate_titles("Tata Motors", "Nexon")
        assert "MG Astor" in wv.candidate_titles("MG Motor", "Astor")

    def test_model_name_never_stands_alone(self):
        for title in wv.candidate_titles("MG Motor", "Astor"):
            assert title.lower() != "astor"

    def test_deduplicates_case_insensitively(self):
        titles = wv.candidate_titles("MG", "Astor")
        assert len(titles) == len({t.lower() for t in titles})


class TestParsePageCandidates:
    def test_generation_disambiguated_title_is_identity_coupled(self):
        data = {
            "query": {
                "pages": {
                    "1": {"title": "Suzuki Baleno (2015)", "extract": NEW_BALENO_EXTRACT,
                          "thumbnail": {"source": "https://upload.wikimedia.org/new.jpg"}},
                }
            }
        }
        pages = wv.parse_page_candidates(data, ["Suzuki Baleno"])
        assert [p.title for p in pages] == ["Suzuki Baleno (2015)"]

    def test_prefixsearch_noise_is_dropped(self):
        data = {
            "query": {
                "pages": {
                    "1": {"title": "Masters of Horror", "extract": "A TV series."},
                    "2": {"title": "MG Motor", "extract": "A car company."},
                }
            }
        }
        assert wv.parse_page_candidates(data, ["MG Astor"]) == []

    def test_section_redirect_target_is_rejected(self):
        """"MG Astor" -> "MG ZS (crossover)#1st" means Astor is a section
        of another model's article — that article's lead image is a
        foreign-market ZS and must never be used for an Astor."""
        data = {
            "query": {
                "redirects": [
                    {"from": "MG Astor", "to": "MG ZS (crossover)", "tofragment": "1st"}
                ],
                "pages": {
                    "1": {"title": "MG ZS (crossover)", "extract": MG_ZS_EXTRACT,
                          "thumbnail": {"source": "https://upload.wikimedia.org/zs.jpg"}},
                },
            }
        }
        assert wv.parse_page_candidates(data, ["MG Astor"]) == []

    def test_whole_page_redirect_keeps_identity(self):
        """"Hyundai Verna" -> "Hyundai Accent" is a full-article redirect:
        the article's primary subject IS the same car under its
        international name, so it stays eligible."""
        data = {
            "query": {
                "redirects": [{"from": "Hyundai Verna", "to": "Hyundai Accent"}],
                "pages": {
                    "1": {"title": "Hyundai Accent", "extract": "The Hyundai Accent, or Hyundai Verna, is a subcompact car.",
                          "thumbnail": {"source": "https://upload.wikimedia.org/accent.jpg"}},
                },
            }
        }
        pages = wv.parse_page_candidates(data, ["Hyundai Verna"])
        assert [p.title for p in pages] == ["Hyundai Accent"]

    def test_redirect_from_unrelated_title_grants_no_identity(self):
        data = {
            "query": {
                "redirects": [{"from": "Some Other Car", "to": "Hyundai Accent"}],
                "pages": {"1": {"title": "Hyundai Accent", "extract": ""}},
            }
        }
        assert wv.parse_page_candidates(data, ["Hyundai Verna"]) == []

    def test_disambiguation_pages_are_rejected(self):
        data = {
            "query": {
                "pages": {
                    "1": {"title": "Suzuki Baleno", "pageprops": {"disambiguation": ""},
                          "thumbnail": {"source": "https://upload.wikimedia.org/d.jpg"}},
                }
            }
        }
        assert wv.parse_page_candidates(data, ["Suzuki Baleno"]) == []

    def test_missing_page_is_skipped(self):
        data = {"query": {"pages": {"-1": {"title": "Nope Car", "missing": ""}}}}
        assert wv.parse_page_candidates(data, ["Nope Car"]) == []


class TestScoring:
    def test_year_in_generation_disambiguator_earns_bonus(self):
        newer = wv.score_page(_page("Suzuki Baleno (2015)"), year=2018)
        future = wv.score_page(_page("Suzuki Baleno (2022)"), year=2018)
        assert newer > future

    def test_nameplate_index_articles_are_penalized(self):
        nameplate = wv.score_page(_page("Suzuki Baleno", OLD_BALENO_EXTRACT))
        specific = wv.score_page(_page("Suzuki Baleno (2015)", NEW_BALENO_EXTRACT))
        assert specific > nameplate

    def test_mentioning_nameplate_history_is_not_an_index_article(self):
        """The Suzuki Swift article mentions its nameplate's earlier use
        while still being the current model's article — it must not be
        penalized as a nameplate-index page (the regression that made
        Swift fall through to a Commons logo)."""
        swift_like = (
            "The Suzuki Swift is a supermini car produced by Suzuki. "
            "The Swift nameplate was previously applied to other models."
        )
        assert not wv._is_nameplate_index(swift_like)
        assert wv._is_nameplate_index(OLD_BALENO_EXTRACT)

    def test_india_market_context_earns_bonus(self):
        india = wv.score_page(_page("Tata Nexon", "A crossover SUV made in India."))
        elsewhere = wv.score_page(_page("Tata Nexon", "A crossover SUV."))
        assert india > elsewhere

    def test_matching_body_style_earns_bonus(self):
        match = wv.score_page(_page("Suzuki Baleno (2015)", NEW_BALENO_EXTRACT), vehicle_type="Hatchback")
        neutral = wv.score_page(_page("Suzuki Baleno (2015)", "A subcompact car."), vehicle_type="Hatchback")
        assert match > neutral

    def test_conflicting_body_style_is_penalized(self):
        sedan_page = _page("Some Car", "The Some Car is a compact sedan.")
        assert wv.score_page(sedan_page, vehicle_type="Hatchback") < wv.score_page(
            sedan_page, vehicle_type="Sedan"
        )

    def test_terminated_production_before_claim_year_is_penalized(self):
        discontinued = _page("Old Car", "Produced from 1999 to 2005.")
        assert wv.score_page(discontinued, year=2018) < wv.score_page(discontinued, year=2003)

    def test_production_year_signal_parsing(self):
        opens, ends = wv._production_year_signals(OLD_BALENO_EXTRACT)
        assert opens == [1996]
        assert 2002 in ends and 2007 in ends
        opens, ends = wv._production_year_signals(NEW_BALENO_EXTRACT)
        assert opens == [2015] and ends == []


class TestSelectBestPage:
    def test_2018_hatchback_baleno_selects_2015_generation_article(self):
        """The exact reported bug: a 2018 Maruti Suzuki Baleno hatchback
        must resolve to the 2015-generation hatchback article, not the
        1995 nameplate/sedan article."""
        pages = [
            _page("Suzuki Baleno", OLD_BALENO_EXTRACT, "https://upload.wikimedia.org/old-sedan.jpg"),
            _page("Suzuki Baleno (2015)", NEW_BALENO_EXTRACT, "https://upload.wikimedia.org/new-hatch.jpg"),
        ]
        best = wv.select_best_page(pages, year=2018, vehicle_type="Hatchback")
        assert best is not None
        assert best.title == "Suzuki Baleno (2015)"

    def test_nothing_above_threshold_returns_none(self):
        pages = [
            _page("Old Car", "A sedan produced from 1995 to 2002.", "https://upload.wikimedia.org/old.jpg")
        ]
        assert wv.select_best_page(pages, year=2020, vehicle_type="Hatchback") is None

    def test_page_without_thumbnail_is_never_selected(self):
        pages = [_page("Tata Nexon", "A crossover SUV made in India since 2017.", thumb=None)]
        assert wv.select_best_page(pages, year=2020, vehicle_type="SUV") is None

    def test_empty_input_returns_none(self):
        assert wv.select_best_page([]) is None


class TestPreferCommonsFile:
    FILES = [
        "File:2021 MG Astor rear view.png",
        "File:2021 MG Astor Sharp 220 Turbo (India) rear view.png",
        "File:2021 MG Astor Sharp 220 Turbo (India) front view.png",
        "File:MG Astor at dealer.jpg",
    ]

    def test_prefers_india_front_view(self):
        assert wv.prefer_commons_file(self.FILES) == (
            "File:2021 MG Astor Sharp 220 Turbo (India) front view.png"
        )

    def test_prefers_india_over_generic_front(self):
        files = ["File:MG Astor front.jpg", "File:MG Astor (India) rear.jpg"]
        assert wv.prefer_commons_file(files) == "File:MG Astor (India) rear.jpg"

    def test_falls_back_to_first_file(self):
        assert wv.prefer_commons_file(["File:A.jpg", "File:B.jpg"]) == "File:A.jpg"

    def test_brand_art_is_never_selected(self):
        files = ["File:Suzuki Swift logo.png", "File:Swift wordmark.svg"]
        assert wv.prefer_commons_file(files) is None
        files.append("File:2020 Suzuki Swift front.jpg")
        assert wv.prefer_commons_file(files) == "File:2020 Suzuki Swift front.jpg"

    def test_empty_list_returns_none(self):
        assert wv.prefer_commons_file([]) is None


class TestImageValidation:
    def test_real_png_passes_and_maps_extension(self):
        assert wv._validated_image(_png_bytes()) == "png"

    def test_html_masquerading_as_image_is_rejected(self):
        assert wv._validated_image(b"<html><body>error page</body></html>") is None

    def test_truncated_bytes_are_rejected(self):
        assert wv._validated_image(_png_bytes()[:8]) is None
