from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


class WorkspaceContractTests(unittest.TestCase):
    def test_production_javascript_runtime(self):
        result=subprocess.run(['node','tests/role_workspace_runtime.cjs'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_shared_style_and_no_persistent_tokens_or_html_injection(self):
        page=(ROOT/'public/partner/index.html').read_text()
        source=(ROOT/'public/partner/workspace.js').read_text()
        self.assertIn('/personal/workspace.css',page)
        for forbidden in ('localStorage','sessionStorage','innerHTML','insertAdjacentHTML'):
            self.assertNotIn(forbidden,source)
        self.assertIn('expected_version:slot.version',source)
        self.assertIn('organization-operations/v1?organization_id=',source)
        self.assertIn('data.role',source)


if __name__=='__main__':unittest.main()
