from cc_code.ui.streaming_markdown import StreamingMarkdownWidget


def test_streaming_markdown_uses_balanced_block_spacing() -> None:
    widget = StreamingMarkdownWidget()
    blocks = widget._build_blocks("# Heading\n\nParagraph\n\n```\ncode\n```\n\n---\n")

    heading = blocks[0]
    paragraph = blocks[1]
    fence = blocks[2]
    hr = blocks[3]

    assert heading.block_type == "heading"
    assert heading.top_margin == 0
    assert heading.bottom_margin == 1

    assert paragraph.block_type == "paragraph"
    assert paragraph.bottom_margin == 1

    assert fence.block_type == "fence"
    assert fence.top_margin == 1
    assert fence.bottom_margin == 1
    assert fence.padding_top == 0
    assert fence.padding_bottom == 0

    assert hr.block_type == "hr"
    assert hr.top_margin == 1
    assert hr.bottom_margin == 1


def test_streaming_markdown_first_block_has_no_top_margin() -> None:
    widget = StreamingMarkdownWidget()

    heading_blocks = widget._build_blocks("# Heading\n\nParagraph\n")
    fence_blocks = widget._build_blocks("```\ncode\n```\n")

    assert heading_blocks[0].block_type == "heading"
    assert heading_blocks[0].top_margin == 0

    assert fence_blocks[0].block_type == "fence"
    assert fence_blocks[0].top_margin == 0
