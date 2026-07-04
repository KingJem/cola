import json
import sys
import textwrap

import pytest

from cola.runner import discover_spiders, main

SPIDER_MODULE = textwrap.dedent('''
    from cola.spiders import Spider

    class NoopSpider(Spider):
        start_urls = []

    class OtherSpider(Spider):
        start_urls = []
''')


@pytest.fixture
def sample_project(tmp_path):
    pkg = tmp_path / 'spiders'
    pkg.mkdir()
    (pkg / '__init__.py').write_text('')
    (pkg / 'noop.py').write_text(SPIDER_MODULE, encoding='utf-8')
    yield tmp_path
    # 清理 sys.modules / sys.path,避免污染其他测试
    for name in [n for n in sys.modules if n == 'spiders'
                 or n.startswith('spiders.')]:
        del sys.modules[name]
    for p in (str(tmp_path), str(tmp_path.parent)):
        if p in sys.path:
            sys.path.remove(p)


def test_discover_spiders(sample_project):
    found = discover_spiders(str(sample_project))
    assert set(found) == {'NoopSpider', 'OtherSpider'}


def test_runner_list(sample_project, capsys):
    main(['--project-dir', str(sample_project), '--list'])
    assert json.loads(capsys.readouterr().out) == ['NoopSpider', 'OtherSpider']


def test_runner_runs_spider(sample_project):
    main(['--project-dir', str(sample_project), '--spider', 'NoopSpider',
          '--settings', '{"PROJECT_NAME": "runner_test"}'])


def test_runner_unknown_spider(sample_project):
    with pytest.raises(SystemExit):
        main(['--project-dir', str(sample_project), '--spider', 'Missing'])


def test_runner_missing_spiders_pkg(tmp_path):
    with pytest.raises(SystemExit):
        discover_spiders(str(tmp_path))
