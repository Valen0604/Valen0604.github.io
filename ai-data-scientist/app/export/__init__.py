"""
Exports: a report as a PDF file, or as a slide deck.

The pieces:

    markdown.py   turns the Markdown the agent writes into a list of blocks
    document.py   builds a document (title, sections, blocks, images) from a conversation,
                  or from Markdown the agent wrote on purpose
    pdf.py        draws a document as a PDF, with reportlab
    slides.py     draws a document as a .pptx, with python-pptx

Both renderers read the same document, so a PDF and a deck of the same answers agree.
"""
