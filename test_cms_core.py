import unittest

from cms_core import build_pdf_asset_path, build_target_path, render_markdown, slugify


class CmsCoreTests(unittest.TestCase):
  def test_slugify_normalizes_title(self):
    self.assertEqual(slugify("Hello, HAT World!"), "hello-hat-world")

  def test_render_markdown_includes_frontmatter(self):
    content = render_markdown(
      "post",
      {
        "title": "Welcome",
        "publishdate": "2026-04-08T10:30:00-05:00",
        "author": "Mark",
        "tags": "One, Two",
        "categories": "General",
        "draft": False,
        "body": "Body text",
      },
    )
    self.assertIn("title: Welcome", content)
    self.assertIn("publishdate: '2026-04-08T10:30:00-05:00'", content)
    self.assertIn("- One", content)
    self.assertTrue(content.endswith("Body text\n"))

  def test_build_target_path_uses_date_prefix(self):
    path = build_target_path(
      "/tmp/project",
      "site",
      "event",
      {
        "title": "Steering Committee Meeting",
        "publishDate": "2026-04-08T10:30:00-05:00",
        "filename_slug": "committee-meeting",
      },
    )
    self.assertEqual(str(path).endswith("site/content/event/2026-04-08_committee-meeting.md"), True)

  def test_build_target_path_uses_markdown_extension_for_plan(self):
    path = build_target_path(
      "/tmp/project",
      "site",
      "plan",
      {
        "title": "Annual Plan",
      },
    )
    self.assertEqual(str(path).endswith("site/content/plan/annual-plan.md"), True)

  def test_build_target_path_uses_pdf_extension_for_document(self):
    path = build_target_path(
      "/tmp/project",
      "site",
      "document",
      {
        "title": "Board Packet",
        "date": "2026-04-08",
      },
    )
    self.assertEqual(str(path).endswith("site/content/document/2026-04-08_board-packet.md"), True)

  def test_build_pdf_asset_path_for_document(self):
    path = build_pdf_asset_path(
      "/tmp/project",
      "site",
      "document",
      {
        "title": "Board Packet",
        "date": "2026-04-08",
      },
    )
    self.assertEqual(str(path).endswith("site/pdfs/2026-04-08_board-packet.pdf"), True)

  def test_build_pdf_asset_path_for_plan(self):
    path = build_pdf_asset_path(
      "/tmp/project",
      "site",
      "plan",
      {
        "title": "Annual Plan",
      },
    )
    self.assertEqual(str(path).endswith("site/pdfs/annual-plan.pdf"), True)

  def test_render_markdown_includes_pdf_embed_for_document(self):
    content = render_markdown(
      "document",
      {
        "title": "Board Packet",
        "date": "2026-04-08",
        "pdf_file": "/tmp/source.pdf",
        "pdf_embed_src": "./../../pdfs/2026-04-08_board-packet.pdf",
      },
    )
    self.assertIn('<embed width=100% height=1000 src="./../../pdfs/2026-04-08_board-packet.pdf"></embed>', content)

  def test_render_markdown_includes_pdf_embed_for_plan(self):
    content = render_markdown(
      "plan",
      {
        "title": "Annual Plan",
        "pdf_file": "/tmp/source.pdf",
        "pdf_embed_src": "./../../pdfs/annual-plan.pdf",
      },
    )
    self.assertIn('<embed width=100% height=1000 src="./../../pdfs/annual-plan.pdf"></embed>', content)


if __name__ == "__main__":
  unittest.main()