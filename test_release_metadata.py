"""版本、WebUI、升级示例与实际养成配置保持一致。"""
import json
from pathlib import Path
import re
import unittest

from . import __version__
from .config_model import OngekiGachaPluginConfig
from .gacha_core import load_cards
from .growth_catalog import GrowthCatalog


class ReleaseMetadataTests(unittest.TestCase):
    def test_versions_and_upgrade_example(self):
        root = Path(__file__).parent
        config = OngekiGachaPluginConfig()
        self.assertEqual(config.plugin.config_version, __version__)
        metadata = (root / 'metadata.yaml').read_text(encoding='utf8')
        self.assertEqual(re.search(r'^version: "([^"]+)"', metadata, re.M).group(1), __version__)
        schema = json.loads((root / '_conf_schema.json').read_text(encoding='utf8'))
        self.assertEqual(schema['plugin']['items']['config_version']['default'], __version__)
        for name in ('README.md', 'USAGE.md'):
            self.assertIn(f'当前版本：{__version__}', (root / name).read_text(encoding='utf8'))
        self.assertIn(f'## {__version__} - ', (root / 'CHANGELOG.md').read_text(encoding='utf8'))
        defaults = config.model_dump()
        usage = (root / 'USAGE.md').read_text(encoding='utf8')
        examples = re.findall(r'```json\n(.*?)```', usage, re.S)
        self.assertTrue(examples)
        for example in examples:
            for section, fields in json.loads(example).items():
                for key, value in fields.items():
                    self.assertEqual(value, defaults[section][key], f'{section}.{key}')
        cards = load_cards(root / 'assets/card_data/card_info_merged.json')
        bundled = GrowthCatalog(root / 'assets/growth', cards).rules
        configured = GrowthCatalog(root / 'assets/growth', cards, config.growth.rule_overrides()).rules
        self.assertEqual(bundled, configured)
