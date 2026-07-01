import json

from click.core import ParameterSource
from output import AppContext, OutputMode, emit, get_ctx, resolve_output
from rich.console import Console


class FakeContext:
    """Minimal stand-in for a Typer context: carries ``obj`` and a parameter source."""

    def __init__(self, app_ctx: AppContext, source: ParameterSource = ParameterSource.DEFAULT):
        self.obj = app_ctx
        self._source = source

    def get_parameter_source(self, name: str) -> ParameterSource:
        return self._source


def _app_ctx(mode: OutputMode, banner: str = "") -> AppContext:
    return AppContext(
        output=mode,
        stdout_console=Console(),
        stderr_console=Console(stderr=True),
        banner=banner,
    )


def _ctx(mode: OutputMode, source: ParameterSource = ParameterSource.DEFAULT) -> FakeContext:
    return FakeContext(_app_ctx(mode), source)


class TestAppContext:
    def test_get_ctx_returns_app_context(self):
        ctx = _ctx(OutputMode.RICH)
        assert get_ctx(ctx) is ctx.obj

    def test_is_json(self):
        assert _app_ctx(OutputMode.JSON).is_json is True
        assert _app_ctx(OutputMode.RICH).is_json is False

    def test_scan_console_routes_by_mode(self):
        # json mode routes scan/progress output to stderr, rich mode to stdout
        json_ctx = _app_ctx(OutputMode.JSON)
        rich_ctx = _app_ctx(OutputMode.RICH)
        assert json_ctx.scan_console is json_ctx.stderr_console
        assert rich_ctx.scan_console is rich_ctx.stdout_console


class TestEmit:
    def test_json_prints_serializable_and_skips_renderer(self, capsys):
        ctx = _ctx(OutputMode.JSON)
        called = []
        emit(ctx, {"a": [1, 2], "b": "x"}, render_rich=lambda: called.append(True))
        out = capsys.readouterr().out
        assert json.loads(out) == {"a": [1, 2], "b": "x"}
        assert called == []

    def test_rich_calls_renderer_and_prints_nothing_itself(self, capsys):
        ctx = _ctx(OutputMode.RICH)
        called = []
        emit(ctx, {"a": 1}, render_rich=lambda: called.append(True))
        out = capsys.readouterr().out
        # emit itself prints nothing in rich mode; the renderer owns output
        assert out == ""
        assert called == [True]


class TestResolveOutput:
    def test_commandline_value_overrides_root(self):
        # root is rich, command passes -o json explicitly -> json wins
        ctx = FakeContext(_app_ctx(OutputMode.RICH), ParameterSource.COMMANDLINE)
        resolve_output(ctx, OutputMode.JSON)
        assert ctx.obj.output is OutputMode.JSON

    def test_root_value_kept_when_flag_not_passed(self):
        # root is json, command left at its default -> root stands (not clobbered)
        ctx = FakeContext(_app_ctx(OutputMode.JSON), ParameterSource.DEFAULT)
        resolve_output(ctx, OutputMode.RICH)
        assert ctx.obj.output is OutputMode.JSON

    def test_prints_banner_in_rich_mode(self, capsys):
        ctx = FakeContext(_app_ctx(OutputMode.RICH, banner="gh-inspector v1.2.3"))
        resolve_output(ctx, OutputMode.RICH)
        assert "gh-inspector v1.2.3" in capsys.readouterr().out

    def test_suppresses_banner_in_json_mode(self, capsys):
        ctx = FakeContext(_app_ctx(OutputMode.JSON, banner="gh-inspector v1.2.3"))
        resolve_output(ctx, OutputMode.JSON)
        assert capsys.readouterr().out == ""
