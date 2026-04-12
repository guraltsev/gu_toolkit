"""Internal shell arrangement specs for figure layout composition.

This module keeps the declarative shell presets used by
:mod:`gu_toolkit.figure_layout`.  The public figure API still exposes widget
surfaces through :class:`gu_toolkit.figure_layout.FigureLayout`, while the
arrangement presets here describe *where* those stable section roots should be
mounted.
"""

from __future__ import annotations

from dataclasses import dataclass


_VALID_SECTION_IDS = ("legend", "parameters", "info")


@dataclass(frozen=True)
class _ShellPageSpec:
    page_id: str
    title: str
    include_navigation: bool = False
    include_stage: bool = False
    main_sections: tuple[str, ...] = ()
    left_sections: tuple[str, ...] = ()
    right_sections: tuple[str, ...] = ()
    bottom_sections: tuple[str, ...] = ()

    def _all_sections(self) -> tuple[str, ...]:
        ordered: list[str] = []
        for group in (
            self.main_sections,
            self.left_sections,
            self.right_sections,
            self.bottom_sections,
        ):
            for section_id in group:
                key = str(section_id)
                if key not in ordered:
                    ordered.append(key)
        return tuple(ordered)


@dataclass(frozen=True)
class _FigureShellSpec:
    name: str
    default_page_id: str
    pages: tuple[_ShellPageSpec, ...]
    show_full_width_toggle: bool = False

    def _page_ids(self) -> tuple[str, ...]:
        return tuple(page.page_id for page in self.pages)


def _page(
    page_id: str,
    title: str,
    *,
    include_navigation: bool = False,
    include_stage: bool = False,
    main_sections: tuple[str, ...] = (),
    left_sections: tuple[str, ...] = (),
    right_sections: tuple[str, ...] = (),
    bottom_sections: tuple[str, ...] = (),
) -> _ShellPageSpec:
    return _ShellPageSpec(
        page_id=str(page_id),
        title=str(title),
        include_navigation=bool(include_navigation),
        include_stage=bool(include_stage),
        main_sections=tuple(str(section_id) for section_id in main_sections),
        left_sections=tuple(str(section_id) for section_id in left_sections),
        right_sections=tuple(str(section_id) for section_id in right_sections),
        bottom_sections=tuple(str(section_id) for section_id in bottom_sections),
    )


def _validate_shell_spec(spec: _FigureShellSpec) -> _FigureShellSpec:
    seen_pages: set[str] = set()
    stage_pages = 0
    seen_sections: set[str] = set()
    for page in spec.pages:
        if page.page_id in seen_pages:
            raise ValueError(f"Duplicate shell page id: {page.page_id}")
        seen_pages.add(page.page_id)
        if page.include_stage:
            stage_pages += 1
        for section_id in page._all_sections():
            if section_id not in _VALID_SECTION_IDS:
                raise ValueError(f"Unknown shell section id: {section_id}")
            if section_id in seen_sections:
                raise ValueError(
                    f"Shell section {section_id!r} is mounted more than once in shell preset {spec.name!r}."
                )
            seen_sections.add(section_id)
    if stage_pages != 1:
        raise ValueError(
            f"Shell preset {spec.name!r} must include exactly one stage page; found {stage_pages}."
        )
    if spec.default_page_id not in seen_pages:
        raise ValueError(
            f"Shell preset {spec.name!r} default page {spec.default_page_id!r} is missing."
        )
    return spec


def _normalize_shell_name(value: str | None) -> str:
    raw = "default" if value is None else str(value).strip().lower()
    normalized = raw.replace("-", "_").replace(" ", "_")
    aliases = {
        "default": "default",
        "legend_right": "default",
        "right": "default",
        "legend_left": "legend_left",
        "left": "legend_left",
        "legend_bottom": "legend_bottom",
        "bottom": "legend_bottom",
        "below": "legend_bottom",
        "legend_hidden": "legend_hidden",
        "hidden": "legend_hidden",
        "none": "legend_hidden",
        "legend_page": "legend_page",
        "legend_tab": "legend_page",
        "page": "legend_page",
        "tab": "legend_page",
    }
    if normalized not in aliases:
        supported = ", ".join(sorted(aliases))
        raise ValueError(
            f"Unknown shell preset {value!r}. Supported presets/aliases: {supported}."
        )
    return aliases[normalized]


def _resolve_figure_shell_spec(shell: str | None) -> _FigureShellSpec:
    key = _normalize_shell_name(shell)
    figure_page = {
        "page_id": "figure",
        "title": "Figure",
        "include_navigation": True,
        "include_stage": True,
    }
    specs: dict[str, _FigureShellSpec] = {
        "default": _FigureShellSpec(
            name="default",
            default_page_id="figure",
            pages=(
                _page(
                    **figure_page,
                    right_sections=("legend", "parameters", "info"),
                ),
            ),
        ),
        "legend_left": _FigureShellSpec(
            name="legend_left",
            default_page_id="figure",
            pages=(
                _page(
                    **figure_page,
                    left_sections=("legend",),
                    right_sections=("parameters", "info"),
                ),
            ),
        ),
        "legend_bottom": _FigureShellSpec(
            name="legend_bottom",
            default_page_id="figure",
            pages=(
                _page(
                    **figure_page,
                    right_sections=("parameters", "info"),
                    bottom_sections=("legend",),
                ),
            ),
        ),
        "legend_hidden": _FigureShellSpec(
            name="legend_hidden",
            default_page_id="figure",
            pages=(
                _page(
                    **figure_page,
                    right_sections=("parameters", "info"),
                ),
            ),
        ),
        "legend_page": _FigureShellSpec(
            name="legend_page",
            default_page_id="figure",
            pages=(
                _page(
                    **figure_page,
                    right_sections=("parameters", "info"),
                ),
                _page(
                    "legend",
                    "Legend",
                    main_sections=("legend",),
                ),
            ),
        ),
    }
    return _validate_shell_spec(specs[key])
